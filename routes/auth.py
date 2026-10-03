"""
Authentication blueprint for Surplus Food Distribution System.
Handles registration (Donor, NGO, Volunteer), login, logout, password hashing,
session lifecycle, and password resets.
"""

import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from database.db import execute_query, execute_insert, execute_update, db_transaction
from utils.validators import (
    validate_user_common_fields,
    validate_donor_profile,
    validate_ngo_profile,
    validate_volunteer_profile,
    save_secure_upload
)
from utils.audit import log_audit

auth_bp = Blueprint('auth', __name__)


def get_role_redirect(role):
    """Returns the default landing dashboard URL for each user role."""
    mapping = {
        'admin': 'admin.dashboard',
        'donor': 'donor.dashboard',
        'ngo': 'ngo.dashboard',
        'volunteer': 'volunteer.dashboard'
    }
    endpoint = mapping.get(role, 'main.index')
    return url_for(endpoint)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Secure user login with status checking, password hashing, and session creation."""
    # If already authenticated, redirect to appropriate role dashboard
    if session.get('user_id') and session.get('role'):
        return redirect(get_role_redirect(session.get('role')))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        remember = bool(request.form.get('remember'))
        next_url = request.args.get('next')

        # Basic input check
        if not email or not password:
            flash("Please enter both email address and password.", "danger")
            return render_template('auth/login.html', email=email)

        # Retrieve user from database
        user = execute_query(
            "SELECT id, name, email, password_hash, role, status FROM users WHERE email = %s",
            (email,),
            fetchone=True
        )

        # Check user existence and verify Werkzeug password hash
        if not user or not check_password_hash(user['password_hash'], password):
            log_audit(
                user_id=user['id'] if user else None,
                action='LOGIN_FAILED',
                entity_type='user',
                details=f"Failed login attempt for email: {email}"
            )
            flash("Invalid email address or password.", "danger")
            return render_template('auth/login.html', email=email)

        # Check account status
        if user['status'] == 'inactive':
            log_audit(user_id=user['id'], action='LOGIN_BLOCKED_INACTIVE', entity_type='user')
            flash("Your account has been deactivated. Please contact support.", "warning")
            return render_template('auth/login.html', email=email)

        if user['status'] == 'rejected':
            log_audit(user_id=user['id'], action='LOGIN_BLOCKED_REJECTED', entity_type='user')
            flash("Your registration was rejected. Please contact support for assistance.", "danger")
            return render_template('auth/login.html', email=email)

        # Setup authenticated session
        session.clear()
        session['user_id'] = user['id']
        session['user_name'] = user['name']
        session['user_email'] = user['email']
        session['role'] = user['role']
        session.permanent = remember

        # Update last login timestamp
        execute_update(
            "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = %s",
            (user['id'],)
        )

        log_audit(
            user_id=user['id'],
            action='LOGIN_SUCCESS',
            entity_type='user',
            details=f"User logged in with role: {user['role']}"
        )

        flash(f"Welcome back, {user['name']}!", "success")

        # Safely handle next redirect (prevent open redirects)
        if next_url and next_url.startswith('/') and not next_url.startswith('//'):
            return redirect(next_url)

        return redirect(get_role_redirect(user['role']))

    return render_template('auth/login.html')


@auth_bp.route('/logout')
def logout():
    """Clears user session and logs the logout event."""
    user_id = session.get('user_id')
    if user_id:
        log_audit(user_id=user_id, action='LOGOUT', entity_type='user')

    session.clear()
    flash("You have been successfully logged out.", "info")
    return redirect(url_for('auth.login'))


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """
    Role-based registration with multi-table atomic transactions.
    Supports Donor, NGO, and Volunteer registrations.
    """
    if session.get('user_id'):
        return redirect(get_role_redirect(session.get('role')))

    selected_role = request.args.get('role', 'donor').lower()
    if selected_role not in ['donor', 'ngo', 'volunteer']:
        selected_role = 'donor'

    if request.method == 'POST':
        role = request.form.get('role', 'donor').lower()
        if role not in ['donor', 'ngo', 'volunteer']:
            flash("Invalid role selected for registration.", "danger")
            return redirect(url_for('auth.register'))

        # Shared user fields
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        phone = request.form.get('phone', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        # 1. Server-side validation of common user credentials
        errors = validate_user_common_fields(name, email, phone, password, confirm_password)

        # Role-specific fields extraction & validation
        form_data = {
            'role': role,
            'name': name,
            'email': email,
            'phone': phone
        }

        uploaded_doc_filename = None

        if role == 'donor':
            donor_type = request.form.get('donor_type', 'individual')
            org_name = request.form.get('organization_name', '').strip()
            address = request.form.get('address', '').strip()
            city = request.form.get('city', '').strip()
            area = request.form.get('area', '').strip()
            pincode = request.form.get('pincode', '').strip()

            form_data.update({
                'donor_type': donor_type,
                'organization_name': org_name,
                'address': address,
                'city': city,
                'area': area,
                'pincode': pincode
            })
            errors.extend(validate_donor_profile(donor_type, org_name, address, city, area, pincode))

        elif role == 'ngo':
            ngo_name = request.form.get('ngo_name', '').strip()
            registration_number = request.form.get('registration_number', '').strip()
            contact_person = request.form.get('contact_person', '').strip()
            address = request.form.get('address', '').strip()
            city = request.form.get('city', '').strip()
            state = request.form.get('state', '').strip()
            pincode = request.form.get('pincode', '').strip()
            ngo_type = request.form.get('ngo_type', 'shelter')

            form_data.update({
                'ngo_name': ngo_name,
                'registration_number': registration_number,
                'contact_person': contact_person,
                'address': address,
                'city': city,
                'state': state,
                'pincode': pincode,
                'ngo_type': ngo_type
            })
            errors.extend(validate_ngo_profile(ngo_name, registration_number, contact_person, address, city, state, pincode, ngo_type))

            # Verification document handling (optional or required)
            doc_file = request.files.get('verification_document')
            if doc_file and doc_file.filename:
                target_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'ngo_documents')
                saved_ok, res = save_secure_upload(doc_file, target_dir)
                if saved_ok:
                    uploaded_doc_filename = res
                else:
                    errors.append(f"Document upload error: {res}")

        elif role == 'volunteer':
            address = request.form.get('address', '').strip()
            city = request.form.get('city', '').strip()
            pincode = request.form.get('pincode', '').strip()
            vehicle_type = request.form.get('vehicle_type', 'none')

            form_data.update({
                'address': address,
                'city': city,
                'pincode': pincode,
                'vehicle_type': vehicle_type
            })
            errors.extend(validate_volunteer_profile(address, city, pincode, vehicle_type))

        # If any validation errors occurred, display and re-render
        if errors:
            for err in errors:
                flash(err, "danger")
            return render_template('auth/register.html', role=role, data=form_data)

        # 2. Database Insertion with Transactional Integrity
        try:
            hashed_pw = generate_password_hash(password)
            user_status = 'pending_approval' if role == 'ngo' else 'active'

            with db_transaction() as (conn, cursor):
                # Insert into users table
                cursor.execute("""
                    INSERT INTO users (name, email, password_hash, role, phone, status)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (name, email, hashed_pw, role, phone, user_status))
                user_id = cursor.lastrowid

                # Insert into corresponding profile table
                if role == 'donor':
                    cursor.execute("""
                        INSERT INTO donors (user_id, donor_type, organization_name, address, city, area, pincode)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (user_id, donor_type, org_name or None, address, city, area, pincode))

                elif role == 'ngo':
                    cursor.execute("""
                        INSERT INTO ngos (user_id, ngo_name, registration_number, contact_person, address, city, state, pincode, ngo_type, verification_document, verification_status)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending')
                    """, (user_id, ngo_name, registration_number, contact_person, address, city, state, pincode, ngo_type, uploaded_doc_filename))

                elif role == 'volunteer':
                    cursor.execute("""
                        INSERT INTO volunteers (user_id, address, city, pincode, vehicle_type, availability_status, verified_status)
                        VALUES (%s, %s, %s, %s, %s, 'available', 'verified')
                    """, (user_id, address, city, pincode, vehicle_type))

            # Log audit event
            log_audit(
                user_id=user_id,
                action='REGISTER',
                entity_type='user',
                entity_id=user_id,
                details=f"Registered new {role} user: {email}"
            )

            if role == 'ngo':
                flash("NGO registration submitted successfully! Your account will be activated once our administrator verifies your credentials.", "success")
            else:
                flash("Registration successful! You can now log in with your credentials.", "success")

            return redirect(url_for('auth.login'))

        except Exception as e:
            flash(f"Registration failed due to a system error: {str(e)}", "danger")
            return render_template('auth/register.html', role=role, data=form_data)

    return render_template('auth/register.html', role=selected_role, data={})


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Password recovery request view."""
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        if not email:
            flash("Please enter your registered email address.", "danger")
            return render_template('auth/forgot_password.html')

        user = execute_query("SELECT id FROM users WHERE email = %s", (email,), fetchone=True)
        # Always display consistent confirmation to avoid user enumeration
        flash("If an account exists with that email, password reset instructions have been dispatched.", "info")
        if user:
            log_audit(user_id=user['id'], action='PASSWORD_RESET_REQUESTED', entity_type='user')
        return redirect(url_for('auth.login'))

    return render_template('auth/forgot_password.html')
