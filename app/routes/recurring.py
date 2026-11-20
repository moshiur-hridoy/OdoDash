import hashlib
import json

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from flask_babel import gettext as _
from app import db
from app.services.loan_interest import submitted_terms
from app.utils import parse_decimal
from app.models import RecurringExpense, Vehicle, EXPENSE_CATEGORIES
from app.routes.expenses import _known_vendors, loan_preview
from app.services.loan_history import loan_history
from app.services.loan_interest import PER_YEAR
from app.services.recurring_processor import expense_for_period, generate_expense_for_period
from datetime import date

bp = Blueprint('recurring', __name__, url_prefix='/recurring')


bp.add_url_rule('/loan-estimate', view_func=loan_preview, methods=['POST'])


@bp.route('/')
@login_required
def index():
    """List all recurring expenses."""
    vehicles = current_user.get_all_vehicles()
    vehicle_ids = [v.id for v in vehicles]

    recurring = RecurringExpense.query.filter(
        RecurringExpense.vehicle_id.in_(vehicle_ids)
    ).order_by(RecurringExpense.next_due.asc()).all()

    return render_template('recurring/index.html',
                         recurring=recurring,
                         vehicles=vehicles,
                         categories=EXPENSE_CATEGORIES, today=date.today())


@bp.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    """Create a new recurring expense."""
    vehicles = current_user.get_all_vehicles()

    if not vehicles:
        flash(_('Please add a vehicle first.'), 'warning')
        return redirect(url_for('vehicles.new'))

    if request.method == 'POST':
        vehicle_id = request.form.get('vehicle_id', type=int)

        # Verify user has access to vehicle
        vehicle = db.session.get(Vehicle, vehicle_id)
        if not vehicle or vehicle not in vehicles:
            flash(_('Invalid vehicle.'), 'error')
            return redirect(url_for('recurring.new'))

        # Parse dates
        start_date = None
        next_due = None
        if request.form.get('start_date'):
            start_date = date.fromisoformat(request.form['start_date'])
            next_due = start_date

        recurring = RecurringExpense(
            vehicle_id=vehicle_id,
            user_id=current_user.id,
            name=request.form['name'],
            category=request.form['category'],
            frequency=request.form['frequency'],
            amount=parse_decimal(request.form['amount']) if request.form.get('amount') else None,
            vendor=request.form.get('vendor'),
            start_date=start_date,
            next_due=next_due,
            description=request.form.get('description'),
            auto_create=request.form.get('auto_create') == 'on',
            notify_before_days=int(request.form.get('remind_days_before', 7))
        )

        try:
            terms = submitted_terms(request.form, recurring.amount, start_date, recurring.frequency)
            if terms:
                # Start Date is instalment one, even when tracking begins later.
                recurring.loan_terms = terms
            if recurring.category == 'loan_payment' and recurring.frequency not in PER_YEAR:
                raise ValueError('Unknown loan frequency')
            if recurring.category == 'loan_payment' and start_date and start_date < date.today():
                recurring.next_due = loan_history(recurring, date.today())[2]
                if recurring.next_due is None:
                    recurring.is_active = False
        except (TypeError, ValueError, OverflowError):
            flash(_('Check the loan terms, payment amount and payment date.'), 'error')
            return redirect(url_for('recurring.new'))
        db.session.add(recurring)
        db.session.commit()

        if recurring.category == 'loan_payment' and start_date and start_date < date.today():
            return redirect(url_for('recurring.history', recurring_id=recurring.id))
        flash(_('Recurring expense created.'), 'success')
        return redirect(url_for('recurring.index'))

    return render_template('recurring/form.html',
                         vehicles=vehicles,
                         categories=EXPENSE_CATEGORIES,
                         known_vendors=_known_vendors([v.id for v in vehicles]),
                         selected_vehicle=request.args.get('vehicle'))


@bp.route('/<int:recurring_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(recurring_id):
    """Edit a recurring expense."""
    vehicles = current_user.get_all_vehicles()
    vehicle_ids = [v.id for v in vehicles]
    recurring = RecurringExpense.query.filter(
        RecurringExpense.id == recurring_id,
        RecurringExpense.vehicle_id.in_(vehicle_ids)
    ).first_or_404()

    if request.method == 'POST':
        # Parse dates
        start_date = None
        if request.form.get('start_date'):
            start_date = date.fromisoformat(request.form['start_date'])

        next_due = None
        if request.form.get('next_due'):
            next_due = date.fromisoformat(request.form['next_due'])

        try:
            recurring.loan_terms = submitted_terms(request.form, parse_decimal(request.form.get('amount')),
                                                  next_due or recurring.last_generated, request.form['frequency'])
        except (TypeError, ValueError, OverflowError):
            flash(_('Check the loan terms, payment amount and payment date.'), 'error')
            return redirect(url_for('recurring.edit', recurring_id=recurring.id))
        schedule_changed = (start_date != recurring.start_date or request.form['frequency'] != recurring.frequency
                            or request.form['category'] != recurring.category)
        if schedule_changed:
            recurring.history_reviewed_on = None
        recurring.name = request.form['name']
        recurring.category = request.form['category']
        recurring.frequency = request.form['frequency']
        recurring.amount = parse_decimal(request.form['amount']) if request.form.get('amount') else None
        recurring.vendor = request.form.get('vendor')
        recurring.start_date = start_date or recurring.start_date
        recurring.next_due = next_due
        recurring.description = request.form.get('description')
        recurring.auto_create = request.form.get('auto_create') == 'on'
        recurring.notify_before_days = int(request.form.get('remind_days_before', 7))
        if (schedule_changed and recurring.category == 'loan_payment' and recurring.start_date < date.today()
                and recurring.frequency in PER_YEAR and (not next_due or next_due < date.today())):
            recurring.next_due = loan_history(recurring, date.today())[2]
            if recurring.next_due is None:
                recurring.is_active = False

        db.session.commit()

        if recurring.category == 'loan_payment' and recurring.start_date < date.today() and not recurring.history_reviewed_on:
            return redirect(url_for('recurring.history', recurring_id=recurring.id))
        flash(_('Recurring expense updated.'), 'success')
        return redirect(url_for('recurring.index'))

    return render_template('recurring/form.html',
                         recurring=recurring,
                         vehicles=[recurring.vehicle],
                         categories=EXPENSE_CATEGORIES,
                         known_vendors=_known_vendors(vehicle_ids))


@bp.route('/<int:recurring_id>/history', methods=['GET', 'POST'])
@login_required
def history(recurring_id):
    ids = [v.id for v in current_user.get_all_vehicles()]
    query = RecurringExpense.query.filter(RecurringExpense.id == recurring_id,
                                         RecurringExpense.vehicle_id.in_(ids),
                                         RecurringExpense.category == 'loan_payment')
    schedule = query.first_or_404()
    today = date.today()
    if schedule.history_reviewed_on or schedule.frequency not in PER_YEAR:
        return redirect(url_for('recurring.index'))

    if request.method == 'POST':
        action = request.form.get('action')
        if action not in ('add', 'skip'):
            return redirect(url_for('recurring.history', recurring_id=schedule.id))
        # Claim the decision before reading entries; a double submit cannot post twice.
        if not query.filter(RecurringExpense.history_reviewed_on.is_(None)).update(
                {RecurringExpense.history_reviewed_on: today}, synchronize_session=False):
            db.session.rollback()
            return redirect(url_for('recurring.index'))
        db.session.refresh(schedule)

    candidates, entries, next_due = loan_history(schedule, today)
    state = [schedule.start_date, schedule.next_due, schedule.frequency, schedule.amount, schedule.loan_terms,
             candidates, [(entry.id, entry.date, entry.cost) for entry in entries], today]
    version = hashlib.sha256(json.dumps(state, default=str, sort_keys=True).encode()).hexdigest()
    if request.method == 'POST':
        if request.form.get('version') != version:
            db.session.rollback()
            return redirect(url_for('recurring.history', recurring_id=schedule.id))
        selected = set(request.form.getlist('payment_date'))
        allowed = {due.isoformat() for due, _ in candidates}
        if action == 'add' and (not selected or not selected <= allowed or not schedule.amount):
            db.session.rollback()
            return redirect(url_for('recurring.history', recurring_id=schedule.id))
        if action == 'add':
            for due, _ in candidates:
                if due.isoformat() in selected:
                    expense_for_period(schedule, due)
        schedule.next_due = next_due
        if next_due is None:
            schedule.is_active = False
        db.session.commit()
        return redirect(url_for('recurring.index'))
    return render_template('recurring/history.html', schedule=schedule, candidates=candidates,
                           entries=entries, next_due=next_due, version=version)


@bp.route('/<int:recurring_id>/delete', methods=['POST'])
@login_required
def delete(recurring_id):
    """Delete a recurring expense."""
    vehicles = current_user.get_all_vehicles()
    vehicle_ids = [v.id for v in vehicles]
    recurring = RecurringExpense.query.filter(
        RecurringExpense.id == recurring_id,
        RecurringExpense.vehicle_id.in_(vehicle_ids)
    ).first_or_404()

    db.session.delete(recurring)
    db.session.commit()

    flash(_('Recurring expense deleted.'), 'success')
    return redirect(url_for('recurring.index'))


@bp.route('/<int:recurring_id>/generate', methods=['POST'])
@login_required
def generate(recurring_id):
    """Manually generate an expense entry from a recurring expense."""
    vehicles = current_user.get_all_vehicles()
    vehicle_ids = [v.id for v in vehicles]
    recurring = RecurringExpense.query.filter(
        RecurringExpense.id == recurring_id,
        RecurringExpense.vehicle_id.in_(vehicle_ids)
    ).first_or_404()

    # Create a single expense for the current period and advance the schedule,
    # sharing the same logic as the background auto-generation processor.
    if generate_expense_for_period(recurring) is None:
        return redirect(url_for('recurring.index'))
    db.session.commit()

    flash(_('Expense created for %(name)s.') % {'name': recurring.name}, 'success')
    return redirect(url_for('recurring.index'))


@bp.route('/<int:recurring_id>/toggle', methods=['POST'])
@login_required
def toggle_active(recurring_id):
    """Toggle active status of a recurring expense."""
    vehicles = current_user.get_all_vehicles()
    vehicle_ids = [v.id for v in vehicles]
    recurring = RecurringExpense.query.filter(
        RecurringExpense.id == recurring_id,
        RecurringExpense.vehicle_id.in_(vehicle_ids)
    ).first_or_404()

    recurring.is_active = not recurring.is_active
    db.session.commit()

    status = 'activated' if recurring.is_active else 'paused'
    flash(_('Recurring expense %(status)s.') % {'status': status}, 'success')
    return redirect(url_for('recurring.index'))
