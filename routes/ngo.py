"""
NGO blueprint for Surplus Food Distribution System.
Protected by @ngo_required decorator.
"""

from flask import Blueprint, render_template, session, request, redirect, url_for, flash
from utils.decorators import ngo_required
from database.db import execute_query

ngo_bp = Blueprint('ngo', __name__, url_prefix='/ngo')


@ngo_bp.route('/dashboard')
@ngo_required
def dashboard():
    """NGO dashboard overview showing verification status and food claims."""
    user_id = session.get('user_id')
    ngo_info = None
    stats = {
        'available_food': 0,
        'requested_food': 0,
        'received_food': 0,
        'distributed_food': 0,
        'total_beneficiaries': 0
    }
    received_deliveries = []

    try:
        ngo_info = execute_query("SELECT * FROM ngos WHERE user_id = %s", (user_id,), fetchone=True)
        if ngo_info:
            ngo_id = ngo_info['id']

            # Available food count in same city or overall
            avail_res = execute_query(
                "SELECT COUNT(*) AS cnt FROM food_donations WHERE status IN ('Approved', 'Pending') AND best_before_datetime > NOW()",
                fetchone=True
            )
            if avail_res:
                stats['available_food'] = avail_res['cnt']

            # Requests count
            req_res = execute_query(
                "SELECT COUNT(*) AS cnt FROM food_requests WHERE ngo_id = %s",
                (ngo_id,),
                fetchone=True
            )
            if req_res:
                stats['requested_food'] = req_res['cnt']

            # Beneficiaries count
            ben_res = execute_query(
                "SELECT COUNT(*) AS cnt FROM beneficiaries WHERE ngo_id = %s AND status = 'active'",
                (ngo_id,),
                fetchone=True
            )
            if ben_res:
                stats['total_beneficiaries'] = ben_res['cnt']

            # Distributions count
            dist_res = execute_query(
                "SELECT COUNT(*) AS cnt, COALESCE(SUM(servings_distributed), 0) AS servings FROM distribution_records WHERE ngo_id = %s",
                (ngo_id,),
                fetchone=True
            )
            if dist_res:
                stats['distributed_food'] = dist_res['cnt']
                stats['servings_distributed'] = int(dist_res['servings'])

            received_deliveries = execute_query("""
                SELECT fd.id, fd.food_name, fd.food_image, fd.quantity, fd.unit,
                       fd.city, fd.area, fd.status, pa.delivered_at
                FROM food_donations fd
                JOIN food_requests fr ON fr.donation_id = fd.id
                JOIN pickup_assignments pa ON pa.donation_id = fd.id
                WHERE fr.ngo_id = %s AND fr.status IN ('approved', 'fulfilled')
                  AND pa.status = 'delivered' AND fd.status IN ('Delivered', 'Distributed')
                ORDER BY pa.delivered_at DESC
            """, (ngo_id,))
    except Exception:
        pass

    return render_template('ngo/dashboard.html', ngo=ngo_info, stats=stats, received_deliveries=received_deliveries)


@ngo_bp.route('/delivery/<int:donation_id>/receive', methods=['POST'])
@ngo_required
def receive_delivery(donation_id):
    """Confirm receipt of a delivered donation requested by this NGO."""
    ngo = execute_query("SELECT id FROM ngos WHERE user_id = %s", (session.get('user_id'),), fetchone=True)
    delivery = execute_query("""
        SELECT fd.id FROM food_donations fd
        JOIN food_requests fr ON fr.donation_id = fd.id
        JOIN pickup_assignments pa ON pa.donation_id = fd.id
        WHERE fd.id = %s AND fr.ngo_id = %s AND fr.status IN ('approved', 'fulfilled')
          AND pa.status = 'delivered' AND fd.status = 'Delivered'
    """, (donation_id, ngo['id'] if ngo else 0), fetchone=True)

    if not delivery:
        flash('This delivery is not available for receipt confirmation.', 'warning')
        return redirect(url_for('ngo.dashboard'))

    execute_update("UPDATE food_donations SET status = 'Distributed' WHERE id = %s", (donation_id,))
    flash('Delivery received successfully. The donation is now marked as Distributed.', 'success')
    return redirect(url_for('ngo.dashboard'))
