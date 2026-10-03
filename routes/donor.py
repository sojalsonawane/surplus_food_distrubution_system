"""
Donor Blueprint for Surplus Food Distribution System.
Handles donor dashboard, food donation creation (with strict food safety validation),
editing before pickup, cancellation, donation tracking, and profile management.
"""

import os
from pathlib import Path
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from utils.decorators import donor_required
from utils.pagination import Pagination
from utils.audit import log_audit
from utils.notifications import create_notification
from utils.validators import (
    validate_food_donation_fields,
    validate_donor_profile,
    is_valid_indian_mobile,
    save_secure_upload,
    ALLOWED_IMAGE_EXTENSIONS
)
from database.db import execute_query, execute_update, execute_insert, db_transaction

donor_bp = Blueprint('donor', __name__, url_prefix='/donor')


def get_donor_record(user_id):
    """Retrieve donor profile and user info."""
    return execute_query("""
        SELECT d.*, u.name, u.email, u.phone, u.status AS user_status
        FROM donors d
        JOIN users u ON d.user_id = u.id
        WHERE d.user_id = %s
    """, (user_id,), fetchone=True)


# ------------------------------------------------------------------------------
# 1. Donor Dashboard
# ------------------------------------------------------------------------------
@donor_bp.route('/dashboard')
@donor_required
def dashboard():
    """Donor overview showing stats, quick actions, and recent surplus postings."""
    user_id = session.get('user_id')
    donor = get_donor_record(user_id)
    if not donor:
        flash("Donor profile not found.", "danger")
        return redirect(url_for('auth.logout'))

    donor_id = donor['id']
    stats = {'total': 0, 'pending': 0, 'approved': 0, 'completed': 0, 'cancelled': 0}

    stats_res = execute_query("""
        SELECT 
            COUNT(*) AS total,
            SUM(CASE WHEN status = 'Pending' THEN 1 ELSE 0 END) AS pending,
            SUM(CASE WHEN status IN ('Approved', 'Pickup Assigned', 'Pickup Accepted', 'Picked Up', 'Delivered', 'Distributed') THEN 1 ELSE 0 END) AS approved,
            SUM(CASE WHEN status = 'Completed' THEN 1 ELSE 0 END) AS completed,
            SUM(CASE WHEN status = 'Cancelled' THEN 1 ELSE 0 END) AS cancelled
        FROM food_donations
        WHERE donor_id = %s
    """, (donor_id,), fetchone=True)

    if stats_res:
        stats['total'] = stats_res['total'] or 0
        stats['pending'] = stats_res['pending'] or 0
        stats['approved'] = stats_res['approved'] or 0
        stats['completed'] = stats_res['completed'] or 0
        stats['cancelled'] = stats_res['cancelled'] or 0

    recent_donations = execute_query("""
        SELECT * FROM food_donations 
        WHERE donor_id = %s 
        ORDER BY created_at DESC 
        LIMIT 5
    """, (donor_id,))

    return render_template('donor/dashboard.html', donor=donor, stats=stats, recent_donations=recent_donations)


# ------------------------------------------------------------------------------
# 2. Add Surplus Food Donation
# ------------------------------------------------------------------------------
@donor_bp.route('/donation/create', methods=['GET', 'POST'])
@donor_required
def create_donation():
    """Create a new surplus food donation with strict food safety verification."""
    user_id = session.get('user_id')
    donor = get_donor_record(user_id)
    if not donor:
        flash("Donor record not found.", "danger")
        return redirect(url_for('auth.logout'))

    if request.method == 'POST':
        food_name = request.form.get('food_name', '')
        food_category = request.form.get('food_category', '')
        food_type = request.form.get('food_type', 'veg')
        quantity_str = request.form.get('quantity', '')
        unit = request.form.get('unit', 'kg')
        servings_str = request.form.get('servings_estimate', '')
        prep_dt_str = request.form.get('preparation_datetime', '')
        best_before_str = request.form.get('best_before_datetime', '')
        pickup_address = request.form.get('pickup_address', '')
        city = request.form.get('city', '')
        area = request.form.get('area', '')
        pincode = request.form.get('pincode', '')
        contact_number = request.form.get('contact_number', '')
        special_instructions = request.form.get('special_instructions', '').strip()

        # Run strict server-side validation
        is_valid, errors, parsed = validate_food_donation_fields(
            food_name, food_category, quantity_str, unit, servings_str, food_type,
            prep_dt_str, best_before_str, pickup_address, city, area, pincode, contact_number
        )

        # Handle optional food image upload
        image_filename = None
        image_file = request.files.get('food_image')
        if image_file and image_file.filename:
            target_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'food_images')
            ok, res = save_secure_upload(image_file, target_dir, ALLOWED_IMAGE_EXTENSIONS)
            if ok:
                image_filename = res
            else:
                errors.append(f"Image upload error: {res}")

        if not is_valid or errors:
            for err in errors:
                flash(err, "danger")
            return render_template('donor/create_donation.html', donor=donor, form=request.form)

        # Insert food donation record
        try:
            donation_id = execute_insert("""
                INSERT INTO food_donations (
                    donor_id, food_name, food_category, quantity, unit, servings_estimate,
                    food_type, preparation_datetime, best_before_datetime, pickup_address,
                    city, area, pincode, contact_number, special_instructions, food_image, status
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'Pending')
            """, (
                donor['id'], parsed['food_name'], parsed['food_category'], parsed['quantity'],
                parsed['unit'], parsed['servings_estimate'], parsed['food_type'],
                parsed['preparation_datetime'], parsed['best_before_datetime'],
                parsed['pickup_address'], parsed['city'], parsed['area'], parsed['pincode'],
                parsed['contact_number'], special_instructions or None, image_filename
            ))

            log_audit(
                user_id=user_id,
                action='DONATION_CREATED',
                entity_type='food_donation',
                entity_id=donation_id,
                details=f"Posted {parsed['quantity']} {parsed['unit']} of {parsed['food_name']} (serves ~{parsed['servings_estimate']})"
            )

            # Notify all active admins of new surplus posting
            admins = execute_query("SELECT id FROM users WHERE role = 'admin' AND status = 'active'")
            for adm in admins:
                create_notification(
                    user_id=adm['id'],
                    title="New Food Donation Posted",
                    message=f"New surplus food '{parsed['food_name']}' posted by {donor['name']} ({parsed['city']}). Awaiting verification.",
                    notif_type="info",
                    related_link=f"/admin/donations/{donation_id}"
                )

            flash(f"Surplus food '{parsed['food_name']}' posted successfully! It is now pending administrative verification.", "success")
            return redirect(url_for('donor.donations'))

        except Exception as e:
            flash(f"Error saving food donation: {str(e)}", "danger")
            return render_template('donor/create_donation.html', donor=donor, form=request.form)

    # Pre-fill address and phone from donor profile
    prefill = {
        'pickup_address': donor['address'],
        'city': donor['city'],
        'area': donor['area'],
        'pincode': donor['pincode'],
        'contact_number': donor['phone']
    }
    return render_template('donor/create_donation.html', donor=donor, form=prefill)


# ------------------------------------------------------------------------------
# 3. My Donations Listing
# ------------------------------------------------------------------------------
@donor_bp.route('/donations')
@donor_required
def donations():
    """List all donations posted by the current donor with filtering and pagination."""
    user_id = session.get('user_id')
    donor = get_donor_record(user_id)
    if not donor:
        flash("Donor profile not found.", "danger")
        return redirect(url_for('auth.logout'))

    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', '').strip()
    per_page = 8

    where_clauses = ["donor_id = %s"]
    params = [donor['id']]

    if status_filter:
        where_clauses.append("status = %s")
        params.append(status_filter)

    where_str = " AND ".join(where_clauses)

    count_sql = f"SELECT COUNT(*) AS total FROM food_donations WHERE {where_str}"
    total_res = execute_query(count_sql, tuple(params), fetchone=True)
    total_items = total_res['total'] if total_res else 0

    pagination = Pagination(page=page, per_page=per_page, total_items=total_items)

    list_sql = f"""
        SELECT fd.*, 
               (SELECT u.name FROM pickup_assignments pa JOIN volunteers v ON pa.volunteer_id = v.id JOIN users u ON v.user_id = u.id WHERE pa.donation_id = fd.id ORDER BY pa.assigned_at DESC LIMIT 1) AS volunteer_name
        FROM food_donations fd
        WHERE {where_str}
        ORDER BY created_at DESC
        LIMIT %s OFFSET %s
    """
    params.extend([pagination.per_page, pagination.offset])
    donations_list = execute_query(list_sql, tuple(params))

    return render_template(
        'donor/donations.html',
        donations=donations_list,
        pagination=pagination,
        status_filter=status_filter
    )


# ------------------------------------------------------------------------------
# 4. Donation Details
# ------------------------------------------------------------------------------
@donor_bp.route('/donation/<int:donation_id>')
@donor_required
def donation_detail(donation_id):
    """View full status lifecycle, timeline, and volunteer assignment details."""
    user_id = session.get('user_id')
    donor = get_donor_record(user_id)
    if not donor:
        flash("Donor profile not found.", "danger")
        return redirect(url_for('auth.logout'))

    donation = execute_query("""
        SELECT * FROM food_donations 
        WHERE id = %s AND donor_id = %s
    """, (donation_id, donor['id']), fetchone=True)

    if not donation:
        flash("Donation not found or access denied.", "danger")
        return redirect(url_for('donor.donations'))

    # Retrieve assigned volunteer info if any
    pickup = execute_query("""
        SELECT pa.*, u.name AS volunteer_name, u.phone AS volunteer_phone, v.vehicle_type
        FROM pickup_assignments pa
        JOIN volunteers v ON pa.volunteer_id = v.id
        JOIN users u ON v.user_id = u.id
        WHERE pa.donation_id = %s AND pa.status != 'cancelled'
        ORDER BY pa.assigned_at DESC
        LIMIT 1
    """, (donation_id,), fetchone=True)

    # Retrieve distribution history if completed
    distributions = execute_query("""
        SELECT dr.*, n.ngo_name, n.city AS ngo_city
        FROM distribution_records dr
        JOIN ngos n ON dr.ngo_id = n.id
        WHERE dr.donation_id = %s
        ORDER BY dr.distribution_date DESC
    """, (donation_id,))

    return render_template(
        'donor/donation_detail.html',
        donation=donation,
        pickup=pickup,
        distributions=distributions
    )


# ------------------------------------------------------------------------------
# 5. Edit Donation (Allowed ONLY before pickup)
# ------------------------------------------------------------------------------
@donor_bp.route('/donation/<int:donation_id>/edit', methods=['GET', 'POST'])
@donor_required
def edit_donation(donation_id):
    """Edit surplus food donation details before volunteer pickup."""
    user_id = session.get('user_id')
    donor = get_donor_record(user_id)

    donation = execute_query("""
        SELECT * FROM food_donations 
        WHERE id = %s AND donor_id = %s
    """, (donation_id, donor['id']), fetchone=True)

    if not donation:
        flash("Donation record not found.", "danger")
        return redirect(url_for('donor.donations'))

    # Business Rule: Cannot edit if already in pickup transit or completed
    if donation['status'] not in ['Pending', 'Approved']:
        flash(f"Donation cannot be edited in its current status ('{donation['status']}'). Modifications are only allowed prior to volunteer assignment.", "warning")
        return redirect(url_for('donor.donation_detail', donation_id=donation_id))

    if request.method == 'POST':
        food_name = request.form.get('food_name', '')
        food_category = request.form.get('food_category', '')
        food_type = request.form.get('food_type', 'veg')
        quantity_str = request.form.get('quantity', '')
        unit = request.form.get('unit', 'kg')
        servings_str = request.form.get('servings_estimate', '')
        prep_dt_str = request.form.get('preparation_datetime', '')
        best_before_str = request.form.get('best_before_datetime', '')
        pickup_address = request.form.get('pickup_address', '')
        city = request.form.get('city', '')
        area = request.form.get('area', '')
        pincode = request.form.get('pincode', '')
        contact_number = request.form.get('contact_number', '')
        special_instructions = request.form.get('special_instructions', '').strip()

        is_valid, errors, parsed = validate_food_donation_fields(
            food_name, food_category, quantity_str, unit, servings_str, food_type,
            prep_dt_str, best_before_str, pickup_address, city, area, pincode, contact_number
        )

        image_filename = donation['food_image']
        image_file = request.files.get('food_image')
        if image_file and image_file.filename:
            target_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'food_images')
            ok, res = save_secure_upload(image_file, target_dir, ALLOWED_IMAGE_EXTENSIONS)
            if ok:
                image_filename = res
            else:
                errors.append(f"Image error: {res}")

        if not is_valid or errors:
            for err in errors:
                flash(err, "danger")
            return render_template('donor/edit_donation.html', donation=donation, form=request.form)

        execute_update("""
            UPDATE food_donations SET
                food_name = %s, food_category = %s, food_type = %s, quantity = %s,
                unit = %s, servings_estimate = %s, preparation_datetime = %s,
                best_before_datetime = %s, pickup_address = %s, city = %s, area = %s,
                pincode = %s, contact_number = %s, special_instructions = %s,
                food_image = %s
            WHERE id = %s AND donor_id = %s
        """, (
            parsed['food_name'], parsed['food_category'], parsed['food_type'], parsed['quantity'],
            parsed['unit'], parsed['servings_estimate'], parsed['preparation_datetime'],
            parsed['best_before_datetime'], parsed['pickup_address'], parsed['city'],
            parsed['area'], parsed['pincode'], parsed['contact_number'],
            special_instructions or None, image_filename, donation_id, donor['id']
        ))

        log_audit(
            user_id=user_id,
            action='DONATION_EDITED',
            entity_type='food_donation',
            entity_id=donation_id,
            details=f"Updated food donation '{parsed['food_name']}'"
        )

        flash("Donation details have been updated successfully.", "success")
        return redirect(url_for('donor.donation_detail', donation_id=donation_id))

    return render_template('donor/edit_donation.html', donation=donation, form=donation)


# ------------------------------------------------------------------------------
# 6. Cancel Donation
# ------------------------------------------------------------------------------
@donor_bp.route('/donation/<int:donation_id>/cancel', methods=['POST'])
@donor_required
def cancel_donation(donation_id):
    """Cancel a food donation before it is picked up."""
    user_id = session.get('user_id')
    donor = get_donor_record(user_id)

    donation = execute_query("""
        SELECT * FROM food_donations 
        WHERE id = %s AND donor_id = %s
    """, (donation_id, donor['id']), fetchone=True)

    if not donation:
        flash("Donation record not found.", "danger")
        return redirect(url_for('donor.donations'))

    # Business Rule: Cannot cancel if already picked up, delivered, or completed
    if donation['status'] in ['Picked Up', 'Delivered', 'Distributed', 'Completed']:
        flash(f"Cannot cancel donation in '{donation['status']}' state. Food has already been collected.", "danger")
        return redirect(url_for('donor.donation_detail', donation_id=donation_id))

    with db_transaction() as (conn, cursor):
        cursor.execute("UPDATE food_donations SET status = 'Cancelled' WHERE id = %s", (donation_id,))
        # If volunteer assignment exists, cancel it
        cursor.execute("""
            UPDATE pickup_assignments 
            SET status = 'cancelled', volunteer_notes = 'Cancelled by donor prior to pickup' 
            WHERE donation_id = %s AND status IN ('assigned', 'accepted')
        """, (donation_id,))

    log_audit(
        user_id=user_id,
        action='DONATION_CANCELLED',
        entity_type='food_donation',
        entity_id=donation_id,
        details=f"Donor cancelled donation '{donation['food_name']}'"
    )

    flash(f"Donation '{donation['food_name']}' has been cancelled.", "info")
    return redirect(url_for('donor.donations'))


# ------------------------------------------------------------------------------
# 7. Donor Profile Management
# ------------------------------------------------------------------------------
@donor_bp.route('/profile', methods=['GET', 'POST'])
@donor_required
def profile():
    """Manage donor contact information and address."""
    user_id = session.get('user_id')
    donor = get_donor_record(user_id)
    if not donor:
        flash("Donor record not found.", "danger")
        return redirect(url_for('auth.logout'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        donor_type = request.form.get('donor_type', 'individual')
        org_name = request.form.get('organization_name', '').strip()
        address = request.form.get('address', '').strip()
        city = request.form.get('city', '').strip()
        area = request.form.get('area', '').strip()
        pincode = request.form.get('pincode', '').strip()

        errors = []
        if not name or len(name) < 2:
            errors.append("Contact name is required (at least 2 characters).")
        if not is_valid_indian_mobile(phone):
            errors.append("Please provide a valid 10-digit Indian mobile number.")

        errors.extend(validate_donor_profile(donor_type, org_name, address, city, area, pincode))

        if errors:
            for err in errors:
                flash(err, "danger")
            return render_template('donor/profile.html', donor=donor, form=request.form)

        with db_transaction() as (conn, cursor):
            cursor.execute("UPDATE users SET name = %s, phone = %s WHERE id = %s", (name, phone, user_id))
            cursor.execute("""
                UPDATE donors SET 
                    donor_type = %s, organization_name = %s, address = %s,
                    city = %s, area = %s, pincode = %s
                WHERE id = %s
            """, (donor_type, org_name or None, address, city, area, pincode, donor['id']))

        session['user_name'] = name
        log_audit(user_id=user_id, action='PROFILE_UPDATED', entity_type='donor', entity_id=donor['id'])
        flash("Donor profile updated successfully.", "success")
        return redirect(url_for('donor.profile'))

    return render_template('donor/profile.html', donor=donor, form=donor)
