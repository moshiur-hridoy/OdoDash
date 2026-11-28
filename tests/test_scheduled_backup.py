"""Scheduled backups (#29): when copies are written, which are kept, and who
can reach them."""
import io
import json
import os
import zipfile
from datetime import timedelta

import pytest

from app import db
from app.models import AppSettings, FuelStation, User, Vehicle
from app.services import scheduled_backup
from app.utils import utcnow

NOW = utcnow().replace(microsecond=0)


@pytest.fixture(autouse=True)
def backup_folder(app, tmp_path):
    app.config['BACKUP_FOLDER'] = str(tmp_path / 'backups')
    return app.config['BACKUP_FOLDER']


def _schedule(frequency, keep=7):
    AppSettings.set(scheduled_backup.SETTING_FREQUENCY, frequency)
    AppSettings.set(scheduled_backup.SETTING_KEEP, str(keep))


def _names(user):
    return [backup.filename for backup in scheduled_backup.list_backups(user)]


def _other_user(name='otheruser'):
    user = User(username=name, email=f'{name}@example.com')
    user.set_password('TestPass123!')
    db.session.add(user)
    db.session.commit()
    return user


def _login(client, username, password='TestPass123!'):
    client.post('/auth/login', data={'username': username, 'password': password},
                follow_redirects=True)


class TestSettings:
    def test_off_with_seven_copies_by_default(self, app):
        assert scheduled_backup.get_frequency() == 'off'
        assert scheduled_backup.get_keep() == 7

    @pytest.mark.parametrize('stored, expected', [('0', 1), ('99', 30), ('junk', 7)])
    def test_a_bad_stored_count_is_kept_in_range(self, app, stored, expected):
        AppSettings.set(scheduled_backup.SETTING_KEEP, stored)
        assert scheduled_backup.get_keep() == expected


class TestRun:
    def test_nothing_is_written_while_off(self, test_user, sample_vehicle):
        assert scheduled_backup.run_scheduled_backups(NOW) == {'created': 0, 'failed': 0}
        assert _names(test_user) == []

    def test_a_copy_is_a_full_backup(self, test_user, sample_vehicle):
        _schedule('daily')
        assert scheduled_backup.run_scheduled_backups(NOW) == {'created': 1, 'failed': 0}

        [name] = _names(test_user)
        with zipfile.ZipFile(scheduled_backup.backup_path(test_user, name)) as zf:
            data = json.loads(zf.read('data.json'))
            assert 'manifest.json' in zf.namelist()
        assert data['export_info']['username'] == 'testuser'
        assert [v['name'] for v in data['vehicles']] == [sample_vehicle.name]

    @pytest.mark.parametrize('frequency, too_soon, due', [
        ('daily', timedelta(hours=22), timedelta(hours=24)),
        ('weekly', timedelta(days=6), timedelta(days=7)),
    ])
    def test_the_next_copy_waits_for_the_interval(self, test_user, sample_vehicle,
                                                  frequency, too_soon, due):
        _schedule(frequency)
        scheduled_backup.run_scheduled_backups(NOW)

        assert scheduled_backup.run_scheduled_backups(NOW + too_soon)['created'] == 0
        assert scheduled_backup.run_scheduled_backups(NOW + due)['created'] == 1
        assert len(_names(test_user)) == 2

    def test_a_wake_up_slightly_early_still_counts(self, test_user, sample_vehicle):
        _schedule('daily')
        scheduled_backup.run_scheduled_backups(NOW)

        early = NOW + timedelta(days=1) - timedelta(minutes=5)
        assert scheduled_backup.run_scheduled_backups(early)['created'] == 1

    def test_only_the_newest_copies_are_kept(self, test_user, sample_vehicle):
        _schedule('daily', keep=2)
        for day in range(4):
            scheduled_backup.run_scheduled_backups(NOW + timedelta(days=day))

        assert [b.created for b in scheduled_backup.list_backups(test_user)] == [
            NOW + timedelta(days=3), NOW + timedelta(days=2)]

    def test_the_copy_just_written_survives_a_clock_set_back(self, test_user,
                                                              sample_vehicle):
        _schedule('daily', keep=1)
        scheduled_backup.create_backup(test_user, NOW + timedelta(days=30))
        newest = scheduled_backup.create_backup(test_user, NOW)
        scheduled_backup.prune_backups(test_user, 1, newest)

        assert _names(test_user) == [newest]

    def test_each_account_gets_only_its_own(self, test_user, sample_vehicle):
        other = _other_user()
        db.session.add(Vehicle(owner_id=other.id, name='Their Car', vehicle_type='car',
                               fuel_type='petrol'))
        db.session.commit()
        _schedule('daily')

        assert scheduled_backup.run_scheduled_backups(NOW)['created'] == 2
        for user, vehicle in ((test_user, sample_vehicle.name), (other, 'Their Car')):
            [name] = _names(user)
            with zipfile.ZipFile(scheduled_backup.backup_path(user, name)) as zf:
                data = json.loads(zf.read('data.json'))
            assert [v['name'] for v in data['vehicles']] == [vehicle]

    def test_an_account_with_nothing_of_its_own_is_skipped(self, test_user,
                                                           sample_vehicle):
        viewer = _other_user('viewer')
        viewer.shared_vehicles.append(sample_vehicle)
        db.session.commit()
        _schedule('daily')

        scheduled_backup.run_scheduled_backups(NOW)

        assert _names(viewer) == []

    def test_a_station_alone_is_worth_a_copy(self, test_user):
        db.session.add(FuelStation(user_id=test_user.id, name='Corner Station'))
        db.session.commit()
        _schedule('daily')

        scheduled_backup.run_scheduled_backups(NOW)

        assert len(_names(test_user)) == 1

    def test_a_failure_leaves_no_file_and_spares_other_accounts(
            self, test_user, sample_vehicle, monkeypatch):
        other = _other_user()
        db.session.add(Vehicle(owner_id=other.id, name='Their Car', vehicle_type='car',
                               fuel_type='petrol'))
        db.session.commit()
        _schedule('daily')
        real = scheduled_backup.build_full_backup

        def disk_full_for_test_user(user, upload_folder, out):
            if user.username == 'testuser':
                with open(out, 'wb') as handle:
                    handle.write(b'half a zip')
                raise OSError('No space left on device')
            real(user, upload_folder, out)

        monkeypatch.setattr(scheduled_backup, 'build_full_backup', disk_full_for_test_user)

        assert scheduled_backup.run_scheduled_backups(NOW) == {'created': 1, 'failed': 1}
        assert os.listdir(scheduled_backup.user_folder(test_user)) == []
        assert len(_names(other)) == 1

    def test_a_failure_keeps_the_older_copies(self, test_user, sample_vehicle, monkeypatch):
        _schedule('daily', keep=1)
        scheduled_backup.run_scheduled_backups(NOW)
        before = _names(test_user)

        def fail(user, upload_folder, out):
            raise OSError('No space left on device')

        monkeypatch.setattr(scheduled_backup, 'build_full_backup', fail)
        scheduled_backup.run_scheduled_backups(NOW + timedelta(days=1))

        assert _names(test_user) == before

    def test_a_reused_account_id_does_not_inherit_copies(self, test_user, sample_vehicle):
        scheduled_backup.create_backup(test_user, NOW)
        successor = User(id=test_user.id, created_at=test_user.created_at + timedelta(seconds=1))

        assert scheduled_backup.list_backups(successor) == []


class TestScheduleRoute:
    def test_an_admin_sets_the_schedule(self, admin_client):
        response = admin_client.post('/backups/schedule', data={
            'backup_frequency': 'weekly', 'backup_keep': '4'})

        assert response.status_code == 302
        assert response.location.endswith('#integrations')
        assert scheduled_backup.get_frequency() == 'weekly'
        assert scheduled_backup.get_keep() == 4

    @pytest.mark.parametrize('frequency, keep', [
        ('hourly', '4'), ('daily', '0'), ('daily', '31'), ('daily', ''), ('daily', 'x')])
    def test_a_bad_schedule_is_refused(self, admin_client, frequency, keep):
        admin_client.post('/backups/schedule', data={
            'backup_frequency': frequency, 'backup_keep': keep})

        assert scheduled_backup.get_frequency() == 'off'
        assert scheduled_backup.get_keep() == 7

    def test_other_accounts_cannot_set_it(self, auth_client):
        auth_client.post('/backups/schedule', data={
            'backup_frequency': 'daily', 'backup_keep': '4'})

        assert scheduled_backup.get_frequency() == 'off'


class TestCopies:
    def test_the_owner_downloads_a_copy(self, auth_client, test_user, sample_vehicle):
        name = scheduled_backup.create_backup(test_user, NOW)

        response = auth_client.get(f'/backups/{name}')

        assert response.status_code == 200
        assert response.mimetype == 'application/zip'
        assert name in response.headers['Content-Disposition']
        assert zipfile.is_zipfile(io.BytesIO(response.data))

    def test_signed_out_visitors_get_nothing(self, client, test_user, sample_vehicle):
        name = scheduled_backup.create_backup(test_user, NOW)

        response = client.get(f'/backups/{name}')

        assert response.status_code == 302
        assert '/auth/login' in response.location

    @pytest.mark.parametrize('username', ['otheruser', 'admin'])
    def test_no_other_account_can_reach_a_copy(self, client, admin_user, test_user,
                                               sample_vehicle, username):
        name = scheduled_backup.create_backup(test_user, NOW)
        if username == 'admin':
            _login(client, 'admin', 'AdminPass123!')
        else:
            _other_user(username)
            _login(client, username)

        assert client.get(f'/backups/{name}').status_code == 404
        assert client.post(f'/backups/{name}/delete').status_code == 404
        assert _names(test_user) == [name]

    @pytest.mark.parametrize('name', [
        'ododash_backup_20240101_000000.zip', 'notes.txt', '..%2F..%2Fmay.db'])
    def test_anything_else_is_not_found(self, auth_client, name):
        assert auth_client.get(f'/backups/{name}').status_code == 404

    def test_copies_are_not_served_as_uploads(self, auth_client, test_user, sample_vehicle):
        name = scheduled_backup.create_backup(test_user, NOW)

        assert auth_client.get(f'/api/uploads/{name}').status_code != 200

    def test_the_owner_deletes_a_copy(self, auth_client, test_user, sample_vehicle):
        name = scheduled_backup.create_backup(test_user, NOW)

        response = auth_client.post(f'/backups/{name}/delete')

        assert response.status_code == 302
        assert _names(test_user) == []

    def test_a_viewer_may_delete_their_own(self, client, test_user, sample_vehicle):
        test_user.role = 'viewer'
        db.session.commit()
        name = scheduled_backup.create_backup(test_user, NOW)
        _login(client, 'testuser')

        client.post(f'/backups/{name}/delete')

        assert _names(test_user) == []

    def test_deleting_an_account_removes_its_copies(self, admin_client):
        leaver = _other_user('leaver')
        leaver_id = leaver.id
        scheduled_backup.create_backup(leaver, NOW)
        folder = scheduled_backup.user_folder(leaver)

        admin_client.post(f'/auth/users/{leaver_id}/delete')

        assert db.session.get(User, leaver_id) is None
        assert not os.path.exists(folder)


class TestSettingsPage:
    def test_it_lists_the_account_copies(self, auth_client, test_user, sample_vehicle):
        name = scheduled_backup.create_backup(test_user, NOW)

        page = auth_client.get('/auth/settings').get_data(as_text=True)

        assert f'/backups/{name}' in page
        assert 'name="backup_frequency"' not in page

    def test_admins_see_the_schedule(self, admin_client):
        page = admin_client.get('/auth/settings').get_data(as_text=True)

        assert 'name="backup_frequency"' in page
        assert 'Scheduled backups are off.' in page
