"""
Admin blueprint for Surplus Food Distribution System.
Handles complete administrative oversight:
- Dashboard KPIs & analytics
- User management (search, filter, activate/deactivate, delete)
- NGO verifications (document viewer, approve/reject workflow)
- Donor & Volunteer rosters
- Food donations supervision (approval, volunteer assignment)
- Beneficiary overview
- Audit logs inspection
- Secure document serving
"""

import os
from pathlib import Path
from flask import (
    Blueprint, render_template, request, redirect, url_for,
    flash, session, send_from_directory, current_app, abort
)
from utils.decorators import admin_required
from utils.pagination import Pagination
from utils.audit import log_audit
from utils.notifications import create_notification
from database.db import execute_query, execute_update, execute_insert, db_transaction

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


# ------------------------------------------------------------------------------
# 1. Admin Dashboard
# ------------------------------------------------------------------------------
@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    """Main administrative dashboard with live counters and recent activity."""
    counts = {
        'total_users': 0,
        'total_donors': 0,
        'total_ngos': 0,
        'total_volunteers': 0,
        'pending_ngos': 0,
        'total_donations': 0,
        'pending_donations': 0,
        'approved_donations': 0,
        'completed_donations': 0,
        'pending_pickups': 0,
        'completed_distributions': 0,
        'meals_served': 0
    }

    try:
        # User counts by role
        user_rows = execute_query("SELECT role, COUNT(*) AS cnt FROM users GROUP BY role")
        for row in user_rows:
            counts['total_users'] += row['cnt']
            if row['role'] == 'donor':
                counts['total_donors'] = row['cnt']
            elif row['role'] == 'ngo':
                counts['total_ngos'] = row['cnt']
            elif row['role'] == 'volunteer':
                counts['total_volunteers'] = row['cnt']

        # Pending NGO approvals
        pending_ngo_res = execute_query(
            "SELECT COUNT(*) AS cnt FROM ngos WHERE verification_status = 'pending'",
            fetchone=True
        )
        if pending_ngo_res:
            counts['pending_ngos'] = pending_ngo_res['cnt']

        # Donation counts by status
        donation_stats = execute_query("""
            SELECT 
                COUNT(*) AS total,
                SUM(CASE WHEN status = 'Pending' THEN 1 ELSE 0 END) AS pending,
                SUM(CASE WHEN status = 'Approved' THEN 1 ELSE 0 END) AS approved,
                SUM(CASE WHEN status = 'Completed' THEN 1 ELSE 0 END) AS completed,
                SUM(CASE WHEN status IN ('Pickup Assigned', 'Pickup Accepted') THEN 1 ELSE 0 END) AS pending_pickups
            FROM food_donations
        """, fetchone=True)
        if donation_stats:
            counts['total_donations'] = donation_stats['total'] or 0
            counts['pending_donations'] = donation_stats['pending'] or 0
            counts['approved_donations'] = donation_stats['approved'] or 0
            counts['completed_donations'] = donation_stats['completed'] or 0
            counts['pending_pickups'] = donation_stats['pending_pickups'] or 0

        # Distribution metrics
        dist_stats = execute_query("""
            SELECT COUNT(*) AS total_dist, COALESCE(SUM(servings_distributed), 0) AS servings
            FROM distribution_records
        """, fetchone=True)
        if dist_stats:
            counts['completed_distributions'] = dist_stats['total_dist'] or 0
            counts['meals_served'] = int(dist_stats['servings'] or 0)

        # Recent registrations (last 5)
        recent_users = execute_query("""
            SELECT id, name, email, role, status, created_at 
            FROM users 
            ORDER BY created_at DESC 
            LIMIT 5
        """)

        # Pending NGOs awaiting verification (last 5)
        pending_ngos = execute_query("""
            SELECT n.id, n.ngo_name, n.registration_number, n.contact_person, n.city, n.created_at, u.phone
            FROM ngos n
            JOIN users u ON n.user_id = u.id
            WHERE n.verification_status = 'pending'
            ORDER BY n.created_at ASC
            LIMIT 5
        """)

        # Recent food donations (last 5)
        recent_donations = execute_query("""
            SELECT fd.id, fd.food_name, fd.quantity, fd.unit, fd.status, fd.created_at, u.name AS donor_name
            FROM food_donations fd
            JOIN donors d ON fd.donor_id = d.id
            JOIN users u ON d.user_id = u.id
            ORDER BY fd.created_at DESC
            LIMIT 5
        """)

        # Recent security audit trail (last 6)
        recent_logs = execute_query("""
            SELECT a.*, u.name AS user_name, u.role AS user_role 
            FROM audit_logs a 
            LEFT JOIN users u ON a.user_id = u.id 
            ORDER BY a.created_at DESC 
            LIMIT 6
        """)

    except Exception:
        recent_users = []
        pending_ngos = []
        recent_donations = []
        recent_logs = []

    return render_template(
        'admin/dashboard.html',
        counts=counts,
        recent_users=recent_users,
        pending_ngos=pending_ngos,
        recent_donations=recent_donations,
        recent_logs=recent_logs
    )


@admin_bp.route('/inquiries')
@admin_required
def inquiries():
    """Show contact form inquiries to administrators."""
    inquiries_list = execute_query("""
        SELECT id, name, email, subject, message, status, created_at
        FROM contact_inquiries
        ORDER BY created_at DESC
    """)
    return render_template('admin/inquiries.html', inquiries=inquiries_list)


@admin_bp.route('/inquiries/<int:inquiry_id>/status', methods=['POST'])
@admin_required
def update_inquiry_status(inquiry_id):
    """Update the workflow status of a contact inquiry."""
    status = request.form.get('status', 'read')
    if status not in ('new', 'read', 'resolved'):
        flash('Invalid inquiry status.', 'danger')
        return redirect(url_for('admin.inquiries'))
    execute_update("UPDATE contact_inquiries SET status = %s WHERE id = %s", (status, inquiry_id))
    flash('Inquiry status updated.', 'success')
    return redirect(url_for('admin.inquiries'))


# ------------------------------------------------------------------------------
# 2. User Management
# ------------------------------------------------------------------------------
@admin_bp.route('/users')
@admin_required
def users():
    """List all registered system users with filtering, search, and pagination."""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    role = request.args.get('role', '').strip()
    status = request.args.get('status', '').strip()
    per_page = 12

    where_clauses = ["1=1"]
    params = []

    if search:
        where_clauses.append("(name LIKE %s OR email LIKE %s OR phone LIKE %s)")
        like_pattern = f"%{search}%"
        params.extend([like_pattern, like_pattern, like_pattern])

    if role:
        where_clauses.append("role = %s")
        params.append(role)

    if status:
        where_clauses.append("status = %s")
        params.append(status)

    where_str = " AND ".join(where_clauses)

    # Count matching users
    count_sql = f"SELECT COUNT(*) AS total FROM users WHERE {where_str}"
    total_res = execute_query(count_sql, tuple(params), fetchone=True)
    total_users = total_res['total'] if total_res else 0

    pagination = Pagination(page=page, per_page=per_page, total_items=total_users)

    # Query page items
    list_sql = f"""
        SELECT id, name, email, phone, role, status, last_login, created_at
        FROM users
        WHERE {where_str}
        ORDER BY created_at DESC
        LIMIT %s OFFSET %s
    """
    params.extend([pagination.per_page, pagination.offset])
    user_list = execute_query(list_sql, tuple(params))

    return render_template(
        'admin/users.html',
        users=user_list,
        pagination=pagination,
        search=search,
        role=role,
        status=status
    )


@admin_bp.route('/users/<int:user_id>/toggle-status', methods=['POST'])
@admin_required
def toggle_user_status(user_id):
    """Toggle user between active and inactive status."""
    current_admin_id = session.get('user_id')
    if user_id == current_admin_id:
        flash("You cannot change the status of your own administrator account.", "danger")
        return redirect(url_for('admin.users'))

    user = execute_query("SELECT id, name, email, role, status FROM users WHERE id = %s", (user_id,), fetchone=True)
    if not user:
        flash("User not found.", "danger")
        return redirect(url_for('admin.users'))

    new_status = 'inactive' if user['status'] == 'active' else 'active'
    execute_update("UPDATE users SET status = %s WHERE id = %s", (new_status, user_id))

    log_audit(
        user_id=current_admin_id,
        action='USER_STATUS_CHANGE',
        entity_type='user',
        entity_id=user_id,
        details=f"Admin changed status of {user['email']} from {user['status']} to {new_status}"
    )

    create_notification(
        user_id=user_id,
        title="Account Status Updated",
        message=f"Your account has been marked as {new_status} by the system administrator.",
        notif_type="info" if new_status == "active" else "warning"
    )

    flash(f"User {user['name']} is now marked as {new_status.title()}.", "success")
    return redirect(request.referrer or url_for('admin.users'))


@admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@admin_required
def delete_user(user_id):
    """Safely delete a user and cascading dependent records."""
    current_admin_id = session.get('user_id')
    if user_id == current_admin_id:
        flash("You cannot delete your own administrator account.", "danger")
        return redirect(url_for('admin.users'))

    user = execute_query("SELECT id, name, email, role FROM users WHERE id = %s", (user_id,), fetchone=True)
    if not user:
        flash("User not found.", "danger")
        return redirect(url_for('admin.users'))

    if user['role'] == 'admin':
        flash("Administrator accounts cannot be deleted directly via this action.", "danger")
        return redirect(url_for('admin.users'))

    # Cascade deletion is handled by MySQL foreign keys
    execute_update("DELETE FROM users WHERE id = %s", (user_id,))

    log_audit(
        user_id=current_admin_id,
        action='USER_DELETED',
        entity_type='user',
        entity_id=user_id,
        details=f"Deleted user {user['name']} ({user['email']}, role: {user['role']})"
    )

    flash(f"User '{user['name']}' and associated records have been removed.", "info")
    return redirect(request.referrer or url_for('admin.users'))


# ------------------------------------------------------------------------------
# 3. NGO Management & Verification
# ------------------------------------------------------------------------------
@admin_bp.route('/ngos')
@admin_required
def ngos():
    """List all registered NGOs with verification filters."""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    status = request.args.get('status', '').strip()
    per_page = 10

    where_clauses = ["1=1"]
    params = []

    if search:
        where_clauses.append("(n.ngo_name LIKE %s OR n.registration_number LIKE %s OR n.city LIKE %s OR u.name LIKE %s)")
        pat = f"%{search}%"
        params.extend([pat, pat, pat, pat])

    if status:
        where_clauses.append("n.verification_status = %s")
        params.append(status)

    where_str = " AND ".join(where_clauses)

    count_sql = f"SELECT COUNT(*) AS total FROM ngos n JOIN users u ON n.user_id = u.id WHERE {where_str}"
    total_res = execute_query(count_sql, tuple(params), fetchone=True)
    total_items = total_res['total'] if total_res else 0

    pagination = Pagination(page=page, per_page=per_page, total_items=total_items)

    list_sql = f"""
        SELECT 
            n.*, u.name AS account_name, u.email, u.phone, u.status AS user_status,
            (SELECT COUNT(*) FROM beneficiaries b WHERE b.ngo_id = n.id) AS beneficiary_count
        FROM ngos n
        JOIN users u ON n.user_id = u.id
        WHERE {where_str}
        ORDER BY 
            CASE WHEN n.verification_status = 'pending' THEN 0 ELSE 1 END,
            n.created_at DESC
        LIMIT %s OFFSET %s
    """
    params.extend([pagination.per_page, pagination.offset])
    ngo_list = execute_query(list_sql, tuple(params))

    return render_template(
        'admin/ngos.html',
        ngos=ngo_list,
        pagination=pagination,
        search=search,
        status=status
    )


@admin_bp.route('/ngos/<int:ngo_id>')
@admin_required
def ngo_detail(ngo_id):
    """View full NGO dossier, documents, and verification actions."""
    ngo = execute_query("""
        SELECT n.*, u.name AS account_name, u.email, u.phone, u.status AS user_status,
               v.name AS verified_by_name
        FROM ngos n
        JOIN users u ON n.user_id = u.id
        LEFT JOIN users v ON n.verified_by = v.id
        WHERE n.id = %s
    """, (ngo_id,), fetchone=True)

    if not ngo:
        flash("NGO record not found.", "danger")
        return redirect(url_for('admin.ngos'))

    # Get beneficiary count and distribution count
    ben_count = execute_query("SELECT COUNT(*) AS cnt FROM beneficiaries WHERE ngo_id = %s", (ngo_id,), fetchone=True)
    dist_count = execute_query("SELECT COUNT(*) AS cnt, COALESCE(SUM(servings_distributed), 0) AS servings FROM distribution_records WHERE ngo_id = %s", (ngo_id,), fetchone=True)

    return render_template(
        'admin/ngo_detail.html',
        ngo=ngo,
        beneficiary_count=ben_count['cnt'] if ben_count else 0,
        distribution_count=dist_count['cnt'] if dist_count else 0,
        servings_count=int(dist_count['servings']) if dist_count else 0
    )


@admin_bp.route('/ngos/<int:ngo_id>/verify', methods=['POST'])
@admin_required
def verify_ngo(ngo_id):
    """Approve or reject NGO credentials."""
    action = request.form.get('action', '').lower()
    reason = request.form.get('reason', '').strip()
    admin_id = session.get('user_id')

    ngo = execute_query("SELECT id, user_id, ngo_name, verification_status FROM ngos WHERE id = %s", (ngo_id,), fetchone=True)
    if not ngo:
        flash("NGO not found.", "danger")
        return redirect(url_for('admin.ngos'))

    if action == 'approve':
        with db_transaction() as (conn, cursor):
            cursor.execute("""
                UPDATE ngos 
                SET verification_status = 'verified', 
                    verified_at = CURRENT_TIMESTAMP, 
                    verified_by = %s,
                    rejection_reason = NULL
                WHERE id = %s
            """, (admin_id, ngo_id))
            cursor.execute("UPDATE users SET status = 'active' WHERE id = %s", (ngo['user_id'],))

        log_audit(
            user_id=admin_id,
            action='NGO_APPROVED',
            entity_type='ngo',
            entity_id=ngo_id,
            details=f"Approved NGO: {ngo['ngo_name']}"
        )
        create_notification(
            user_id=ngo['user_id'],
            title="NGO Verification Approved",
            message=f"Congratulations! Your organization '{ngo['ngo_name']}' has been officially verified. You can now browse and claim surplus food.",
            notif_type="success",
            related_link="/ngo/food"
        )
        flash(f"NGO '{ngo['ngo_name']}' has been successfully approved and activated.", "success")

    elif action == 'reject':
        if not reason:
            flash("Please provide a reason for rejecting the NGO registration.", "danger")
            return redirect(url_for('admin.ngo_detail', ngo_id=ngo_id))

        with db_transaction() as (conn, cursor):
            cursor.execute("""
                UPDATE ngos 
                SET verification_status = 'rejected', 
                    rejection_reason = %s,
                    verified_by = %s,
                    verified_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (reason, admin_id, ngo_id))
            cursor.execute("UPDATE users SET status = 'rejected' WHERE id = %s", (ngo['user_id'],))

        log_audit(
            user_id=admin_id,
            action='NGO_REJECTED',
            entity_type='ngo',
            entity_id=ngo_id,
            details=f"Rejected NGO '{ngo['ngo_name']}'. Reason: {reason}"
        )
        create_notification(
            user_id=ngo['user_id'],
            title="NGO Verification Rejected",
            message=f"Your NGO verification was rejected. Reason: {reason}",
            notif_type="danger"
        )
        flash(f"NGO '{ngo['ngo_name']}' registration has been rejected.", "warning")

    return redirect(url_for('admin.ngo_detail', ngo_id=ngo_id))


# ------------------------------------------------------------------------------
# 4. Donor & Volunteer Directories
# ------------------------------------------------------------------------------
@admin_bp.route('/donors')
@admin_required
def donors():
    """List registered food donors with donation statistics."""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    donor_type = request.args.get('donor_type', '').strip()
    per_page = 10

    where_clauses = ["1=1"]
    params = []

    if search:
        where_clauses.append("(u.name LIKE %s OR d.organization_name LIKE %s OR d.city LIKE %s OR u.email LIKE %s)")
        pat = f"%{search}%"
        params.extend([pat, pat, pat, pat])

    if donor_type:
        where_clauses.append("d.donor_type = %s")
        params.append(donor_type)

    where_str = " AND ".join(where_clauses)

    count_sql = f"SELECT COUNT(*) AS total FROM donors d JOIN users u ON d.user_id = u.id WHERE {where_str}"
    total_res = execute_query(count_sql, tuple(params), fetchone=True)
    total_items = total_res['total'] if total_res else 0

    pagination = Pagination(page=page, per_page=per_page, total_items=total_items)

    list_sql = f"""
        SELECT 
            d.*, u.name AS contact_name, u.email, u.phone, u.status AS user_status,
            (SELECT COUNT(*) FROM food_donations fd WHERE fd.donor_id = d.id) AS total_donations,
            (SELECT COUNT(*) FROM food_donations fd WHERE fd.donor_id = d.id AND fd.status = 'Completed') AS completed_donations
        FROM donors d
        JOIN users u ON d.user_id = u.id
        WHERE {where_str}
        ORDER BY d.created_at DESC
        LIMIT %s OFFSET %s
    """
    params.extend([pagination.per_page, pagination.offset])
    donor_list = execute_query(list_sql, tuple(params))

    return render_template(
        'admin/donors.html',
        donors=donor_list,
        pagination=pagination,
        search=search,
        donor_type=donor_type
    )


@admin_bp.route('/volunteers')
@admin_required
def volunteers():
    """List registered volunteers with transport details and pickup metrics."""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    vehicle = request.args.get('vehicle_type', '').strip()
    availability = request.args.get('availability', '').strip()
    per_page = 10

    where_clauses = ["1=1"]
    params = []

    if search:
        where_clauses.append("(u.name LIKE %s OR v.city LIKE %s OR u.phone LIKE %s)")
        pat = f"%{search}%"
        params.extend([pat, pat, pat])

    if vehicle:
        where_clauses.append("v.vehicle_type = %s")
        params.append(vehicle)

    if availability:
        where_clauses.append("v.availability_status = %s")
        params.append(availability)

    where_str = " AND ".join(where_clauses)

    count_sql = f"SELECT COUNT(*) AS total FROM volunteers v JOIN users u ON v.user_id = u.id WHERE {where_str}"
    total_res = execute_query(count_sql, tuple(params), fetchone=True)
    total_items = total_res['total'] if total_res else 0

    pagination = Pagination(page=page, per_page=per_page, total_items=total_items)

    list_sql = f"""
        SELECT 
            v.*, u.name, u.email, u.phone, u.status AS user_status,
            (SELECT COUNT(*) FROM pickup_assignments pa WHERE pa.volunteer_id = v.id) AS total_assigned,
            (SELECT COUNT(*) FROM pickup_assignments pa WHERE pa.volunteer_id = v.id AND pa.status = 'delivered') AS total_delivered
        FROM volunteers v
        JOIN users u ON v.user_id = u.id
        WHERE {where_str}
        ORDER BY v.created_at DESC
        LIMIT %s OFFSET %s
    """
    params.extend([pagination.per_page, pagination.offset])
    volunteer_list = execute_query(list_sql, tuple(params))

    return render_template(
        'admin/volunteers.html',
        volunteers=volunteer_list,
        pagination=pagination,
        search=search,
        vehicle_type=vehicle,
        availability=availability
    )


# ------------------------------------------------------------------------------
# 5. Food Donations Supervision & Volunteer Dispatch
# ------------------------------------------------------------------------------
@admin_bp.route('/donations')
@admin_required
def donations():
    """Supervise all surplus food donation postings across the platform."""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    status = request.args.get('status', '').strip()
    category = request.args.get('category', '').strip()
    per_page = 10

    where_clauses = ["1=1"]
    params = []

    if search:
        where_clauses.append("(fd.food_name LIKE %s OR fd.city LIKE %s OR u.name LIKE %s)")
        pat = f"%{search}%"
        params.extend([pat, pat, pat])

    if status:
        where_clauses.append("fd.status = %s")
        params.append(status)

    if category:
        where_clauses.append("fd.food_category = %s")
        params.append(category)

    where_str = " AND ".join(where_clauses)

    count_sql = f"""
        SELECT COUNT(*) AS total 
        FROM food_donations fd 
        JOIN donors d ON fd.donor_id = d.id 
        JOIN users u ON d.user_id = u.id 
        WHERE {where_str}
    """
    total_res = execute_query(count_sql, tuple(params), fetchone=True)
    total_items = total_res['total'] if total_res else 0

    pagination = Pagination(page=page, per_page=per_page, total_items=total_items)

    list_sql = f"""
        SELECT 
            fd.*, u.name AS donor_name, u.phone AS donor_phone,
            (SELECT COUNT(*) FROM food_requests fr WHERE fr.donation_id = fd.id) AS request_count
        FROM food_donations fd
        JOIN donors d ON fd.donor_id = d.id
        JOIN users u ON d.user_id = u.id
        WHERE {where_str}
        ORDER BY 
            CASE WHEN fd.status = 'Pending' THEN 0 WHEN fd.status = 'Approved' THEN 1 ELSE 2 END,
            fd.created_at DESC
        LIMIT %s OFFSET %s
    """
    params.extend([pagination.per_page, pagination.offset])
    donation_list = execute_query(list_sql, tuple(params))

    return render_template(
        'admin/donations.html',
        donations=donation_list,
        pagination=pagination,
        search=search,
        status=status,
        category=category
    )


@admin_bp.route('/donations/<int:donation_id>')
@admin_required
def donation_detail(donation_id):
    """Detailed inspection of a food donation batch with volunteer assignment dropdown."""
    donation = execute_query("""
        SELECT fd.*, u.name AS donor_name, u.email AS donor_email, u.phone AS donor_phone,
               d.donor_type, d.organization_name
        FROM food_donations fd
        JOIN donors d ON fd.donor_id = d.id
        JOIN users u ON d.user_id = u.id
        WHERE fd.id = %s
    """, (donation_id,), fetchone=True)

    if not donation:
        flash("Food donation record not found.", "danger")
        return redirect(url_for('admin.donations'))

    # Retrieve current active pickup assignment if any
    current_pickup = execute_query("""
        SELECT pa.*, u.name AS volunteer_name, u.phone AS volunteer_phone, v.vehicle_type
        FROM pickup_assignments pa
        JOIN volunteers v ON pa.volunteer_id = v.id
        JOIN users u ON v.user_id = u.id
        WHERE pa.donation_id = %s AND pa.status != 'cancelled'
        ORDER BY pa.assigned_at DESC
        LIMIT 1
    """, (donation_id,), fetchone=True)

    # Active available volunteers in the same city or overall for assignment
    available_volunteers = execute_query("""
        SELECT v.id, u.name, u.phone, v.city, v.vehicle_type, v.availability_status
        FROM volunteers v
        JOIN users u ON v.user_id = u.id
        WHERE u.status = 'active' AND v.availability_status != 'inactive'
        ORDER BY CASE WHEN v.city = %s THEN 0 ELSE 1 END, u.name ASC
    """, (donation['city'],))

    return render_template(
        'admin/donation_detail.html',
        donation=donation,
        pickup=current_pickup,
        volunteers=available_volunteers
    )


@admin_bp.route('/donations/<int:donation_id>/verify', methods=['POST'])
@admin_required
def verify_donation(donation_id):
    """Approve or reject a pending surplus food posting."""
    action = request.form.get('action', '').lower()
    reason = request.form.get('reason', '').strip()
    admin_id = session.get('user_id')

    donation = execute_query("""
        SELECT fd.id, fd.food_name, fd.status, d.user_id AS donor_user_id 
        FROM food_donations fd
        JOIN donors d ON fd.donor_id = d.id
        WHERE fd.id = %s
    """, (donation_id,), fetchone=True)

    if not donation:
        flash("Donation record not found.", "danger")
        return redirect(url_for('admin.donations'))

    if action == 'approve':
        execute_update("""
            UPDATE food_donations 
            SET status = 'Approved', approved_by = %s 
            WHERE id = %s
        """, (admin_id, donation_id))

        log_audit(
            user_id=admin_id,
            action='DONATION_APPROVED',
            entity_type='food_donation',
            entity_id=donation_id,
            details=f"Approved food donation: {donation['food_name']}"
        )
        create_notification(
            user_id=donation['donor_user_id'],
            title="Food Donation Approved",
            message=f"Your surplus food listing '{donation['food_name']}' has been approved and is now visible for NGO requests and volunteer pickup dispatch.",
            notif_type="success"
        )
        flash(f"Donation '{donation['food_name']}' approved successfully.", "success")

    elif action == 'reject':
        execute_update("""
            UPDATE food_donations 
            SET status = 'Rejected', rejection_reason = %s, approved_by = %s 
            WHERE id = %s
        """, (reason or 'Does not meet food safety criteria', admin_id, donation_id))

        log_audit(
            user_id=admin_id,
            action='DONATION_REJECTED',
            entity_type='food_donation',
            entity_id=donation_id,
            details=f"Rejected food donation '{donation['food_name']}'. Reason: {reason}"
        )
        create_notification(
            user_id=donation['donor_user_id'],
            title="Food Donation Listing Rejected",
            message=f"Your food donation listing '{donation['food_name']}' was rejected. Reason: {reason or 'Does not meet food safety criteria'}.",
            notif_type="danger"
        )
        flash(f"Donation '{donation['food_name']}' has been marked as Rejected.", "warning")

    return redirect(url_for('admin.donation_detail', donation_id=donation_id))


@admin_bp.route('/donations/<int:donation_id>/assign-pickup', methods=['POST'])
@admin_required
def assign_pickup(donation_id):
    """Assign an active volunteer for a food pickup."""
    volunteer_id = request.form.get('volunteer_id', type=int)
    notes = request.form.get('notes', '').strip()
    admin_id = session.get('user_id')

    donation = execute_query("""
        SELECT fd.id, fd.food_name, fd.status, d.user_id AS donor_user_id 
        FROM food_donations fd
        JOIN donors d ON fd.donor_id = d.id
        WHERE fd.id = %s
    """, (donation_id,), fetchone=True)

    if not donation:
        flash("Donation not found.", "danger")
        return redirect(url_for('admin.donations'))

    if donation['status'] in ['Completed', 'Cancelled', 'Expired']:
        flash(f"Cannot assign pickup for donation with status '{donation['status']}'.", "danger")
        return redirect(url_for('admin.donation_detail', donation_id=donation_id))

    volunteer = execute_query("""
        SELECT v.id, v.user_id, u.name 
        FROM volunteers v 
        JOIN users u ON v.user_id = u.id 
        WHERE v.id = %s AND u.status = 'active'
    """, (volunteer_id,), fetchone=True)

    if not volunteer:
        flash("Please select a valid active volunteer.", "danger")
        return redirect(url_for('admin.donation_detail', donation_id=donation_id))

    with db_transaction() as (conn, cursor):
        # Create assignment
        cursor.execute("""
            INSERT INTO pickup_assignments (donation_id, volunteer_id, assigned_by, status, volunteer_notes)
            VALUES (%s, %s, %s, 'assigned', %s)
        """, (donation_id, volunteer_id, admin_id, notes or None))
        
        # Update donation status
        cursor.execute("""
            UPDATE food_donations 
            SET status = 'Pickup Assigned' 
            WHERE id = %s
        """, (donation_id,))

    log_audit(
        user_id=admin_id,
        action='PICKUP_ASSIGNED',
        entity_type='pickup_assignment',
        entity_id=donation_id,
        details=f"Assigned volunteer {volunteer['name']} to donation '{donation['food_name']}'"
    )

    # Notify volunteer
    create_notification(
        user_id=volunteer['user_id'],
        title="New Pickup Duty Assigned",
        message=f"You have been assigned to collect surplus food '{donation['food_name']}'. Please accept or reject this assignment in your portal.",
        notif_type="warning",
        related_link="/volunteer/dashboard"
    )

    # Notify donor
    create_notification(
        user_id=donation['donor_user_id'],
        title="Volunteer Assigned for Pickup",
        message=f"Volunteer {volunteer['name']} has been assigned to pick up your food donation '{donation['food_name']}'.",
        notif_type="info"
    )

    flash(f"Volunteer {volunteer['name']} has been assigned for pickup of '{donation['food_name']}'.", "success")
    return redirect(url_for('admin.donation_detail', donation_id=donation_id))


# ------------------------------------------------------------------------------
# 6. Beneficiaries Overview
# ------------------------------------------------------------------------------
@admin_bp.route('/beneficiaries')
@admin_required
def beneficiaries():
    """View community beneficiaries registered under all NGOs."""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    ngo_filter = request.args.get('ngo_id', type=int)
    per_page = 12

    where_clauses = ["1=1"]
    params = []

    if search:
        where_clauses.append("(b.name LIKE %s OR b.address LIKE %s)")
        pat = f"%{search}%"
        params.extend([pat, pat])

    if ngo_filter:
        where_clauses.append("b.ngo_id = %s")
        params.append(ngo_filter)

    where_str = " AND ".join(where_clauses)

    count_sql = f"SELECT COUNT(*) AS total FROM beneficiaries b WHERE {where_str}"
    total_res = execute_query(count_sql, tuple(params), fetchone=True)
    total_items = total_res['total'] if total_res else 0

    pagination = Pagination(page=page, per_page=per_page, total_items=total_items)

    list_sql = f"""
        SELECT b.*, n.ngo_name, n.city AS ngo_city
        FROM beneficiaries b
        JOIN ngos n ON b.ngo_id = n.id
        WHERE {where_str}
        ORDER BY b.created_at DESC
        LIMIT %s OFFSET %s
    """
    params.extend([pagination.per_page, pagination.offset])
    beneficiary_list = execute_query(list_sql, tuple(params))

    # All NGOs list for filter dropdown
    all_ngos = execute_query("SELECT id, ngo_name FROM ngos ORDER BY ngo_name ASC")

    return render_template(
        'admin/beneficiaries.html',
        beneficiaries=beneficiary_list,
        ngos=all_ngos,
        pagination=pagination,
        search=search,
        selected_ngo=ngo_filter
    )


# ------------------------------------------------------------------------------
# 7. Security Audit Log Viewer
# ------------------------------------------------------------------------------
@admin_bp.route('/audit-logs')
@admin_required
def audit_logs():
    """Searchable, filterable security and activity audit trail."""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    action = request.args.get('action', '').strip()
    per_page = 15

    where_clauses = ["1=1"]
    params = []

    if search:
        where_clauses.append("(a.details LIKE %s OR a.ip_address LIKE %s OR u.name LIKE %s OR u.email LIKE %s)")
        pat = f"%{search}%"
        params.extend([pat, pat, pat, pat])

    if action:
        where_clauses.append("a.action = %s")
        params.append(action)

    where_str = " AND ".join(where_clauses)

    count_sql = f"""
        SELECT COUNT(*) AS total 
        FROM audit_logs a 
        LEFT JOIN users u ON a.user_id = u.id 
        WHERE {where_str}
    """
    total_res = execute_query(count_sql, tuple(params), fetchone=True)
    total_items = total_res['total'] if total_res else 0

    pagination = Pagination(page=page, per_page=per_page, total_items=total_items)

    list_sql = f"""
        SELECT a.*, u.name AS user_name, u.email AS user_email, u.role AS user_role
        FROM audit_logs a
        LEFT JOIN users u ON a.user_id = u.id
        WHERE {where_str}
        ORDER BY a.created_at DESC
        LIMIT %s OFFSET %s
    """
    params.extend([pagination.per_page, pagination.offset])
    log_list = execute_query(list_sql, tuple(params))

    # Distinct actions for filter dropdown
    distinct_actions = execute_query("SELECT DISTINCT action FROM audit_logs ORDER BY action ASC")

    return render_template(
        'admin/audit_logs.html',
        logs=log_list,
        pagination=pagination,
        actions=distinct_actions,
        search=search,
        selected_action=action
    )


# ------------------------------------------------------------------------------
# 8. Secure Document Viewer (for NGO certificates)
# ------------------------------------------------------------------------------
@admin_bp.route('/document/<path:filename>')
@admin_required
def view_document(filename):
    """Secure endpoint to view uploaded NGO verification certificates."""
    upload_dir = Path(current_app.config['UPLOAD_FOLDER']) / 'ngo_documents'
    safe_path = upload_dir / filename

    if not safe_path.exists():
        abort(404)

    return send_from_directory(upload_dir, filename)
