"""File names in a backup are not trusted, and shared files are not removed."""
import io
import json
import os
import zipfile
from datetime import date

import pytest

from app import db
from app.models import AppSettings, Attachment, Document, FuelLog, User, Vehicle
from app.services.backup_restore import read_backup, restore_backup
from app.services.uploads import remove_unused_upload


@pytest.fixture
def uploads(app, tmp_path):
    folder = tmp_path / 'uploads'
    folder.mkdir()
    app.config['UPLOAD_FOLDER'] = str(folder)
    return folder


@pytest.fixture
def other_user(app):
    user = User(username='other', email='other@example.com')
    user.set_password('TestPass123!')
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def restore(tmp_path, uploads):
    def run(user, vehicle, files, dry_run=False):
        archive = tmp_path / 'backup.zip'
        with zipfile.ZipFile(archive, 'w') as zf:
            zf.writestr('data.json', json.dumps(
                {'vehicles': [vehicle] if vehicle else []}))
            for name, body in files.items():
                zf.writestr(f'uploads/{name}', body)
        data, zip_path = read_backup(str(archive))
        return restore_backup(data, user, zip_path=zip_path,
                              upload_folder=str(uploads), dry_run=dry_run)
    return run


def _document(filename):
    return {'title': 'Paper', 'document_type': 'other', 'filename': filename,
            'original_filename': 'paper.pdf'}


def _car_with(**sections):
    return dict({'name': 'Restored', 'vehicle_type': 'car'}, **sections)


def _existing_document(vehicle, uploads, filename, body=b'original'):
    document = Document(vehicle_id=vehicle.id, user_id=vehicle.owner_id, title='Paper',
                        document_type='other', filename=filename,
                        original_filename='paper.pdf')
    db.session.add(document)
    db.session.commit()
    if body is not None:
        (uploads / filename).write_bytes(body)
    return document


def _restored_documents(user):
    return Document.query.join(Vehicle).filter(Vehicle.owner_id == user.id).all()


class TestWhatGetsWritten:
    def test_files_no_record_refers_to_are_left_out(self, restore, test_user, uploads):
        summary = restore(test_user, None, {'page.html': b'x', 'loose.pdf': b'x'})
        assert os.listdir(uploads) == []
        assert summary['files'] == {'added': 0, 'skipped': 2}

    @pytest.mark.parametrize('name', [
        'page.html', 'page.HTM', 'image.svg', 'data.xml', 'code.js', 'page.html.',
        '.hidden.lock',
    ])
    def test_types_the_upload_forms_refuse_are_not_restored(
            self, restore, test_user, uploads, name):
        vehicle = _car_with(image_filename=name, documents=[_document(name)],
                            attachments=[{'filename': name}])
        restore(test_user, vehicle, {name: b'x'})
        assert os.listdir(uploads) == []
        assert Document.query.count() == 0
        assert Attachment.query.count() == 0
        assert Vehicle.query.one().image_filename is None

    @pytest.mark.parametrize('name', ['abc_scan.PDF', 'abc_pdf', 'abc_book.epub'])
    def test_ordinary_upload_names_are_kept(self, restore, test_user, uploads, name):
        restore(test_user, _car_with(documents=[_document(name)]), {name: b'body'})
        assert Document.query.one().filename == name
        assert (uploads / name).read_bytes() == b'body'

    def test_preview_writes_nothing(self, restore, test_user, uploads):
        summary = restore(test_user, _car_with(documents=[_document('a.pdf')]),
                          {'a.pdf': b'body'}, dry_run=True)
        assert summary['files']['added'] == 1
        assert os.listdir(uploads) == []


class TestNamesAlreadyInUse:
    @pytest.mark.parametrize('claimed', ['doc_abc.pdf', 'DOC_ABC.PDF'])
    @pytest.mark.parametrize('body', [b'something else', b'original'])
    def test_another_accounts_file_is_never_shared(
            self, restore, test_user, other_user, sample_vehicle, uploads, claimed, body):
        theirs = _existing_document(sample_vehicle, uploads, 'doc_abc.pdf')

        restore(other_user, _car_with(documents=[_document(claimed)]), {claimed: body})

        [mine] = _restored_documents(other_user)
        assert mine.filename.lower() != theirs.filename.lower()
        assert (uploads / mine.filename).read_bytes() == body
        assert (uploads / theirs.filename).read_bytes() == b'original'

        db.session.delete(mine)
        db.session.commit()
        remove_unused_upload(str(uploads), mine.filename)
        assert (uploads / theirs.filename).exists()

    def test_restoring_twice_adds_nothing_more(
            self, restore, test_user, other_user, sample_vehicle, uploads):
        _existing_document(sample_vehicle, uploads, 'doc_abc.pdf')
        vehicle = _car_with(image_filename='doc_abc.pdf',
                            documents=[_document('doc_abc.pdf')],
                            attachments=[{'filename': 'doc_abc.pdf'}])

        restore(other_user, vehicle, {'doc_abc.pdf': b'copy'})
        files = sorted(os.listdir(uploads))
        second = restore(other_user, vehicle, {'doc_abc.pdf': b'copy'})

        assert second['total_added'] == 0
        assert sorted(os.listdir(uploads)) == files
        assert len(files) == 2
        assert len(_restored_documents(other_user)) == 1

    def test_the_instance_logo_is_not_shared(self, restore, other_user, uploads):
        (uploads / 'logo_abc.png').write_bytes(b'logo')
        AppSettings.set('logo_filename', 'logo_abc.png')

        restore(other_user, _car_with(documents=[_document('logo_abc.png')]),
                {'logo_abc.png': b'logo'})

        assert _restored_documents(other_user)[0].filename != 'logo_abc.png'

    def test_a_leftover_file_with_other_content_is_not_picked_up(
            self, restore, test_user, uploads):
        (uploads / 'doc_left.pdf').write_bytes(b'from a deleted vehicle')

        restore(test_user, _car_with(documents=[_document('doc_left.pdf')]),
                {'doc_left.pdf': b'mine'})

        document = Document.query.one()
        assert document.filename != 'doc_left.pdf'
        assert (uploads / document.filename).read_bytes() == b'mine'


class TestMissingFiles:
    def test_a_full_backup_puts_back_lost_files(
            self, restore, test_user, sample_vehicle, sample_fuel_log, uploads):
        _existing_document(sample_vehicle, uploads, 'doc_lost.pdf', body=None)
        sample_vehicle.image_filename = 'car.jpg'
        db.session.add(Attachment(fuel_log_id=sample_fuel_log.id, filename='receipt.pdf',
                                  original_filename='receipt.pdf'))
        db.session.commit()
        vehicle = {
            'name': sample_vehicle.name, 'make': sample_vehicle.make,
            'model': sample_vehicle.model, 'year': sample_vehicle.year,
            'vehicle_type': 'car', 'image_filename': 'car.jpg',
            'documents': [_document('doc_lost.pdf')],
            'fuel_logs': [{
                'date': sample_fuel_log.date.isoformat(),
                'odometer': sample_fuel_log.odometer, 'volume': sample_fuel_log.volume,
                'attachments': [{'filename': 'receipt.pdf'}],
            }],
        }

        summary = restore(test_user, vehicle, {
            'doc_lost.pdf': b'a', 'car.jpg': b'b', 'receipt.pdf': b'c'})

        assert summary['files']['added'] == 3
        assert sorted(os.listdir(uploads)) == ['car.jpg', 'doc_lost.pdf', 'receipt.pdf']
        assert Document.query.count() == 1
        assert FuelLog.query.count() == 1

    def test_another_accounts_missing_file_is_not_filled_in(
            self, restore, test_user, other_user, sample_vehicle, uploads):
        _existing_document(sample_vehicle, uploads, 'doc_lost.pdf', body=None)

        restore(other_user, _car_with(documents=[_document('doc_lost.pdf')]),
                {'doc_lost.pdf': b'not theirs'})

        assert not (uploads / 'doc_lost.pdf').exists()


class TestRemoval:
    def test_a_file_another_record_uses_is_kept(
            self, auth_client, sample_vehicle, sample_expense, uploads):
        document = _existing_document(sample_vehicle, uploads, 'both.pdf')
        db.session.add(Attachment(expense_id=sample_expense.id, filename='both.pdf',
                                  original_filename='both.pdf'))
        db.session.commit()

        auth_client.post(f'/documents/{document.id}/delete')
        assert (uploads / 'both.pdf').exists()

        auth_client.post(f'/expenses/{sample_expense.id}/delete')
        assert not (uploads / 'both.pdf').exists()

    def test_replacing_the_vehicle_picture_removes_the_old_one(
            self, auth_client, sample_vehicle, uploads):
        (uploads / 'old.png').write_bytes(b'old')
        sample_vehicle.image_filename = 'old.png'
        db.session.commit()

        auth_client.post(f'/vehicles/{sample_vehicle.id}/edit', data={
            'name': 'Test Car', 'vehicle_type': 'car', 'fuel_type': 'petrol',
            'image': (io.BytesIO(b'new'), 'new.png'),
        }, content_type='multipart/form-data')

        assert not (uploads / 'old.png').exists()
        assert (uploads / sample_vehicle.image_filename).read_bytes() == b'new'


class TestServing:
    def _get(self, client, uploads, name):
        (uploads / name).write_bytes(b'body')
        response = client.get(f'/api/uploads/{name}')
        assert response.status_code == 200
        disposition = response.headers.get('Content-Disposition', '')
        return disposition.startswith('attachment'), response.headers.get(
            'Content-Security-Policy')

    @pytest.mark.parametrize('name', ['a.png', 'a.JPG', 'a.pdf'])
    def test_pictures_and_pdfs_open_in_the_browser(self, client, uploads, name):
        assert self._get(client, uploads, name) == (False, None)

    @pytest.mark.parametrize('name', [
        'a.html', 'a.HTML', 'a.xml', 'a.js', 'a.txt', 'a.docx', 'noextension'])
    def test_everything_else_downloads_sandboxed(self, client, uploads, name):
        assert self._get(client, uploads, name) == (True, 'sandbox')

    def test_the_svg_logo_shows_but_cannot_run_script(self, client, uploads):
        assert self._get(client, uploads, 'logo.svg') == (False, 'sandbox')
