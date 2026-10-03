"""
Volunteer blueprint for Surplus Food Distribution System.
Protected by @volunteer_required decorator.
"""

from flask import Blueprint, render_template, session, request, redirect, url_for, flash
from utils.decorators import volunteer_required
from database.db import execute_query, execute_update

volunteer_bp = Blueprint('volunteer', __name__, url_prefix='/volunteer')


@volunteer_bp.route('/dashboard')
@volunteer_required
def dashboard():
    """Volunteer dashboard overview showing assigned pickup duties."""
    user_id = session.get('user_id')
    volunteer_info = None
    stats = {
        'assigned': 0,
        'accepted': 0,
        'picked_up': 0,
        'completed': 0
    }
    tasks = []

    try:
        volunteer_info = execute_query("SELECT * FROM volunteers WHERE user_id = %s", (user_id,), fetchone=True)
        if volunteer_info:
            vol_id = volunteer_info['id']

            res = execute_query("""
                SELECT 
                    COUNT(*) AS total_assigned,
                    SUM(CASE WHEN status = 'assigned' THEN 1 ELSE 0 END) AS pending,
                    SUM(CASE WHEN status = 'accepted' THEN 1 ELSE 0 END) AS accepted,
                    SUM(CASE WHEN status = 'picked_up' THEN 1 ELSE 0 END) AS picked_up,
                    SUM(CASE WHEN status = 'delivered' THEN 1 ELSE 0 END) AS completed
                FROM pickup_assignments
                WHERE volunteer_id = %s
            """, (vol_id,), fetchone=True)
            if res:
                stats['assigned'] = res['pending'] or 0
                stats['accepted'] = res['accepted'] or 0
                stats['picked_up'] = res['picked_up'] or 0
                stats['completed'] = res['completed'] or 0

            tasks = execute_query("""
                SELECT pa.*, fd.food_name, fd.quantity, fd.unit, fd.pickup_address, fd.city, fd.contact_number, fd.best_before_datetime
                FROM pickup_assignments pa
                JOIN food_donations fd ON pa.donation_id = fd.id
                WHERE pa.volunteer_id = %s
                ORDER BY pa.assigned_at DESC
                LIMIT 5
            """, (vol_id,))
    except Exception:
        pass

    return render_template('volunteer/dashboard.html', volunteer=volunteer_info, stats=stats, tasks=tasks)


def get_current_volunteer():
    """Return the volunteer profile for the logged-in user."""
    return execute_query("SELECT * FROM volunteers WHERE user_id = %s", (session.get('user_id'),), fetchone=True)


def get_volunteer_pickup(pickup_id, volunteer_id):
    """Return one pickup only when it belongs to the current volunteer."""
    return execute_query("""
        SELECT pa.*, fd.food_name, fd.food_category, fd.food_type, fd.food_image,
               fd.quantity, fd.unit, fd.servings_estimate, fd.pickup_address,
               fd.city, fd.area, fd.pincode, fd.contact_number,
               fd.preparation_datetime, fd.best_before_datetime
        FROM pickup_assignments pa
        JOIN food_donations fd ON pa.donation_id = fd.id
        WHERE pa.id = %s AND pa.volunteer_id = %s
    """, (pickup_id, volunteer_id), fetchone=True)


@volunteer_bp.route('/pickups')
@volunteer_required
def pickups():
    """List active and completed pickups assigned to the current volunteer."""
    volunteer = get_current_volunteer()
    assignments = []
    if volunteer:
        assignments = execute_query("""
            SELECT pa.*, fd.food_name, fd.quantity, fd.unit, fd.city,
                   fd.area, fd.pickup_address, fd.best_before_datetime
            FROM pickup_assignments pa
            JOIN food_donations fd ON pa.donation_id = fd.id
            WHERE pa.volunteer_id = %s AND pa.status NOT IN ('delivered', 'cancelled', 'rejected')
            ORDER BY pa.assigned_at DESC
        """, (volunteer['id'],))
    return render_template('volunteer/pickups.html', volunteer=volunteer, assignments=assignments)


@volunteer_bp.route('/history')
@volunteer_required
def history():
    """List completed and cancelled pickup assignments."""
    volunteer = get_current_volunteer()
    assignments = []
    if volunteer:
        assignments = execute_query("""
            SELECT pa.*, fd.food_name, fd.quantity, fd.unit, fd.city,
                   fd.area, fd.best_before_datetime
            FROM pickup_assignments pa
            JOIN food_donations fd ON pa.donation_id = fd.id
            WHERE pa.volunteer_id = %s AND pa.status IN ('delivered', 'cancelled', 'rejected')
            ORDER BY pa.updated_at DESC
        """, (volunteer['id'],))
    return render_template('volunteer/history.html', volunteer=volunteer, assignments=assignments)


@volunteer_bp.route('/pickup/<int:pickup_id>')
@volunteer_required
def pickup_detail(pickup_id):
    """Show details for an assigned pickup owned by the current volunteer."""
    volunteer = get_current_volunteer()
    pickup = get_volunteer_pickup(pickup_id, volunteer['id']) if volunteer else None
    if not pickup:
        return render_template('errors/404.html'), 404
    return render_template('volunteer/pickup_detail.html', volunteer=volunteer, pickup=pickup)


@volunteer_bp.route('/pickup/<int:pickup_id>/update', methods=['POST'])
@volunteer_required
def update_pickup(pickup_id):
    """Advance a volunteer pickup through its delivery lifecycle."""
    volunteer = get_current_volunteer()
    pickup = get_volunteer_pickup(pickup_id, volunteer['id']) if volunteer else None
    next_status = request.form.get('status')
    transitions = {
        'assigned': ('accepted', 'Pickup Accepted', 'accepted_at'),
        'accepted': ('picked_up', 'Picked Up', 'picked_up_at'),
        'picked_up': ('delivered', 'Delivered', 'delivered_at')
    }

    if not pickup or pickup['status'] not in transitions or next_status != transitions[pickup['status']][0]:
        flash('This pickup cannot be updated from its current status.', 'warning')
        return redirect(url_for('volunteer.pickup_detail', pickup_id=pickup_id))

    assignment_status, donation_status, timestamp_column = transitions[pickup['status']]
    execute_update(
        f"UPDATE pickup_assignments SET status = %s, {timestamp_column} = NOW() WHERE id = %s AND volunteer_id = %s",
        (assignment_status, pickup_id, volunteer['id'])
    )
    execute_update(
        "UPDATE food_donations SET status = %s WHERE id = %s",
        (donation_status, pickup['donation_id'])
    )
    flash(f"Pickup marked as {donation_status.lower()}.", 'success')
    return redirect(url_for('volunteer.pickup_detail', pickup_id=pickup_id))


@volunteer_bp.route('/profile')
@volunteer_required
def profile():
    """Show the volunteer vehicle and pickup area profile."""
    volunteer = get_current_volunteer()
    return render_template('volunteer/profile.html', volunteer=volunteer)
