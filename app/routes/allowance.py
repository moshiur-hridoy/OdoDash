from datetime import date, datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from flask_babel import gettext as _
from app import db
from app.utils import parse_decimal
from app.models import Vehicle, MileageAllowance
from app.security import get_safe_redirect_url

bp = Blueprint('allowance', __name__, url_prefix='/allowance')


ALLOWANCES_PER_PAGE = 50


@bp.route('/')
@login_required
def index():
    from app.routes.log_helpers import month_start, group_by_month, monthly_totals
    from app.utils import utcnow

    vehicles = current_user.get_all_vehicles()
    selected_vehicle = next((v for v in vehicles if v.id == request.args.get('vehicle', type=int)), None)
    vehicle_ids = [selected_vehicle.id] if selected_vehicle else [v.id for v in vehicles]
    query = MileageAllowance.query.filter(MileageAllowance.vehicle_id.in_(vehicle_ids))

    pagination = query.order_by(MileageAllowance.date.desc(), MileageAllowance.id.desc()).paginate(
        page=request.args.get('page', 1, type=int), per_page=ALLOWANCES_PER_PAGE, error_out=False)
    allowances = pagination.items
    totals = monthly_totals(MileageAllowance, MileageAllowance.amount, vehicle_ids,
                            [month_start(a.date) for a in allowances if a.date])

    def amount_since(since=None):
        q = db.session.query(db.func.sum(MileageAllowance.amount)).filter(
            MileageAllowance.vehicle_id.in_(vehicle_ids))
        if since:
            q = q.filter(MileageAllowance.date >= since)
        return q.scalar() or 0

    now = utcnow()
    summary = {
        'year': amount_since(date(now.year, 1, 1)),
        'total': amount_since(),
        'count': pagination.total,
    }

    return render_template('allowance/index.html',
                           allowances=allowances,
                           pagination=pagination,
                           groups=group_by_month(allowances, lambda a: a.date, totals),
                           summary=summary,
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
            return redirect(url_for('allowance.index'))

        try:
            date_str = request.form.get('date')
            allowance = MileageAllowance(
                vehicle_id=vehicle_id,
                user_id=current_user.id,
                date=datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else datetime.now().date(),
                description=request.form.get('description') or None,
                distance=parse_decimal(request.form.get('distance')) if request.form.get('distance') else None,
                rate_per_unit=parse_decimal(request.form.get('rate_per_unit')) if request.form.get('rate_per_unit') else None,
                amount=parse_decimal(request.form.get('amount')),
            )
        except (ValueError, TypeError):
            flash(_('Invalid data submitted. Please check the date and amount fields.'), 'error')
            return render_template('allowance/form.html', allowance=None, vehicles=vehicles,
                                   selected_vehicle_id=vehicle_id)

        db.session.add(allowance)
        db.session.commit()
        flash(_('Mileage allowance added successfully'), 'success')
        return redirect(url_for('vehicles.view', vehicle_id=vehicle_id))

    selected_vehicle_id = request.args.get('vehicle_id', type=int) or current_user.default_vehicle_id

    return render_template('allowance/form.html', allowance=None, vehicles=vehicles,
                           selected_vehicle_id=selected_vehicle_id)


@bp.route('/<int:allowance_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(allowance_id):
    allowance = db.get_or_404(MileageAllowance, allowance_id)
    vehicles = current_user.get_all_vehicles()

    # Check access
    if allowance.vehicle not in vehicles:
        flash(_('Access denied'), 'error')
        return redirect(url_for('allowance.index'))

    if request.method == 'POST':
        try:
            date_str = request.form.get('date')
            allowance.date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else allowance.date
            allowance.description = request.form.get('description') or None
            allowance.distance = parse_decimal(request.form.get('distance')) if request.form.get('distance') else None
            allowance.rate_per_unit = parse_decimal(request.form.get('rate_per_unit')) if request.form.get('rate_per_unit') else None
            allowance.amount = parse_decimal(request.form.get('amount'))
        except (ValueError, TypeError):
            flash(_('Invalid data submitted. Please check the date and amount fields.'), 'error')
            return render_template('allowance/form.html', allowance=allowance, vehicles=vehicles,
                                   selected_vehicle_id=allowance.vehicle_id)

        db.session.commit()
        flash(_('Mileage allowance updated successfully'), 'success')
        return redirect(url_for('vehicles.view', vehicle_id=allowance.vehicle_id))

    return render_template('allowance/form.html', allowance=allowance, vehicles=vehicles,
                           selected_vehicle_id=allowance.vehicle_id)


@bp.route('/<int:allowance_id>/delete', methods=['POST'])
@login_required
def delete(allowance_id):
    allowance = db.get_or_404(MileageAllowance, allowance_id)
    vehicles = current_user.get_all_vehicles()

    # Check access
    if allowance.vehicle not in vehicles:
        flash(_('Access denied'), 'error')
        return redirect(url_for('allowance.index'))

    vehicle_id = allowance.vehicle_id
    db.session.delete(allowance)
    db.session.commit()
    flash(_('Mileage allowance deleted successfully'), 'success')
    # The list page sends where to go back to; the vehicle page does not.
    if request.form.get('next'):
        return redirect(get_safe_redirect_url(request.form.get('next'), 'allowance.index'))
    return redirect(url_for('vehicles.view', vehicle_id=vehicle_id))
