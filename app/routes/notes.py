from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from flask_babel import gettext as _
from app import db
from app.utils import parse_decimal
from app.models import Vehicle, Note
from app.security import get_safe_redirect_url

bp = Blueprint('notes', __name__, url_prefix='/notes')

NOTES_PER_PAGE = 50


@bp.route('/')
@login_required
def index():
    from app.routes.log_helpers import group_by_month

    vehicles = current_user.get_all_vehicles()
    selected_vehicle = next((v for v in vehicles if v.id == request.args.get('vehicle', type=int)), None)
    vehicle_ids = [selected_vehicle.id] if selected_vehicle else [v.id for v in vehicles]

    pagination = Note.query.filter(
        Note.vehicle_id.in_(vehicle_ids)
    ).order_by(Note.date.desc(), Note.id.desc()).paginate(
        page=request.args.get('page', 1, type=int), per_page=NOTES_PER_PAGE, error_out=False)
    notes = pagination.items

    return render_template('notes/index.html',
                           notes=notes,
                           pagination=pagination,
                           groups=group_by_month(notes, lambda n: n.date),
                           vehicles=vehicles,
                           selected_vehicle=selected_vehicle)


@bp.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    vehicles = current_user.get_all_vehicles()

    if not vehicles:
        flash(_('Please add a vehicle first'), 'info')
        return redirect(url_for('vehicles.new'))

    if request.method == 'POST':
        vehicle_id = int(request.form.get('vehicle_id'))
        vehicle = db.get_or_404(Vehicle, vehicle_id)

        # Check access
        if vehicle not in vehicles:
            flash(_('Access denied'), 'error')
            return redirect(url_for('notes.index'))

        try:
            date_str = request.form.get('date')
            note = Note(
                vehicle_id=vehicle_id,
                user_id=current_user.id,
                date=datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else datetime.now().date(),
                title=request.form.get('title') or None,
                content=request.form.get('content'),
                odometer=parse_decimal(request.form.get('odometer')) if request.form.get('odometer') else None,
            )
        except (ValueError, TypeError):
            flash(_('Invalid data submitted. Please check the date and odometer fields.'), 'error')
            return render_template('notes/form.html', note=None, vehicles=vehicles,
                                   selected_vehicle_id=vehicle_id)

        if not note.content:
            flash(_('Please enter some note text'), 'error')
            return render_template('notes/form.html', note=None, vehicles=vehicles,
                                   selected_vehicle_id=vehicle_id)

        db.session.add(note)
        db.session.commit()
        flash(_('Note added successfully'), 'success')

        # Redirect back to vehicle page if we came from there (#283)
        if request.form.get('return_to') == 'vehicle':
            return redirect(url_for('vehicles.view', vehicle_id=vehicle_id))

        return redirect(url_for('notes.index'))

    selected_vehicle_id = request.args.get('vehicle_id', type=int) or current_user.default_vehicle_id

    return render_template('notes/form.html', note=None, vehicles=vehicles,
                           selected_vehicle_id=selected_vehicle_id)


@bp.route('/<int:note_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(note_id):
    note = db.get_or_404(Note, note_id)
    vehicles = current_user.get_all_vehicles()

    # Check access
    if note.vehicle not in vehicles:
        flash(_('Access denied'), 'error')
        return redirect(url_for('notes.index'))

    if request.method == 'POST':
        try:
            date_str = request.form.get('date')
            note.date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else note.date
            note.title = request.form.get('title') or None
            note.content = request.form.get('content')
            note.odometer = parse_decimal(request.form.get('odometer')) if request.form.get('odometer') else None
        except (ValueError, TypeError):
            flash(_('Invalid data submitted. Please check the date and odometer fields.'), 'error')
            return render_template('notes/form.html', note=note, vehicles=vehicles,
                                   selected_vehicle_id=note.vehicle_id)

        if not note.content:
            flash(_('Please enter some note text'), 'error')
            return render_template('notes/form.html', note=note, vehicles=vehicles,
                                   selected_vehicle_id=note.vehicle_id)

        db.session.commit()
        flash(_('Note updated successfully'), 'success')

        # Redirect back to vehicle page if we came from there (#283)
        if request.form.get('return_to') == 'vehicle':
            return redirect(url_for('vehicles.view', vehicle_id=note.vehicle_id))

        return redirect(url_for('notes.index'))

    return render_template('notes/form.html', note=note, vehicles=vehicles,
                           selected_vehicle_id=note.vehicle_id)


@bp.route('/<int:note_id>/delete', methods=['POST'])
@login_required
def delete(note_id):
    note = db.get_or_404(Note, note_id)
    vehicles = current_user.get_all_vehicles()

    # Check access
    if note.vehicle not in vehicles:
        flash(_('Access denied'), 'error')
        return redirect(url_for('notes.index'))

    vehicle_id = note.vehicle_id
    db.session.delete(note)
    db.session.commit()
    flash(_('Note deleted successfully'), 'success')

    # Redirect back to vehicle page if we came from there (#283)
    if request.args.get('return_to') == 'vehicle':
        return redirect(url_for('vehicles.view', vehicle_id=vehicle_id))

    return redirect(get_safe_redirect_url(request.form.get('next'), 'notes.index'))
