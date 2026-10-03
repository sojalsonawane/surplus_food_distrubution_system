"""
Input validation utilities for Surplus Food Distribution System.
Provides strict server-side validation for registration, authentication,
profiles, contact details, and file uploads.
"""

import re
import os
import uuid
from werkzeug.utils import secure_filename
from database.db import execute_query

EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$')
INDIAN_PHONE_REGEX = re.compile(r'^[6-9]\d{9}$')
PINCODE_REGEX = re.compile(r'^[1-9]\d{5}$')

ALLOWED_DOCUMENT_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg'}
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg'}
MAX_UPLOAD_SIZE = 5 * 1024 * 1024  # 5 MB


def is_valid_email(email):
    """Check if email matches standard pattern."""
    if not email or not isinstance(email, str):
        return False
    return bool(EMAIL_REGEX.match(email.strip()))


def is_valid_indian_mobile(mobile):
    """
    Check if mobile is a 10-digit Indian number starting with 6, 7, 8, or 9.
    """
    if not mobile or not isinstance(mobile, str):
        return False
    return bool(INDIAN_PHONE_REGEX.match(mobile.strip()))


def is_valid_pincode(pincode):
    """Check if pincode is exactly 6 digits."""
    if not pincode or not isinstance(pincode, str):
        return False
    return bool(PINCODE_REGEX.match(pincode.strip()))


def validate_password_strength(password):
    """
    Validates password strength:
    - Minimum 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one number
    - At least one special character
    Returns (is_valid: bool, error_message: str or None)
    """
    if not password or len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter."
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter."
    if not re.search(r'\d', password):
        return False, "Password must contain at least one numeric digit."
    if not re.search(r'[@$!%*?&#^()_+={}\[\]:;"\'<>,.?\/\\|`~-]', password):
        return False, "Password must contain at least one special character (e.g. @, #, $, %, !)."
    return True, None


def validate_user_common_fields(name, email, phone, password, confirm_password, check_email_unique=True):
    """
    Validates shared user fields across all roles.
    Returns list of error messages (empty list if valid).
    """
    errors = []

    # Name validation
    if not name or not name.strip():
        errors.append("Full name is required.")
    else:
        name_clean = name.strip()
        if len(name_clean) < 2:
            errors.append("Name must be at least 2 characters long.")
        elif len(name_clean) > 100:
            errors.append("Name cannot exceed 100 characters.")
        elif name_clean.isdigit():
            errors.append("Name cannot consist of only numbers.")

    # Email validation
    if not email or not email.strip():
        errors.append("Email address is required.")
    elif not is_valid_email(email):
        errors.append("Please enter a valid email address format (e.g., user@example.com).")
    elif check_email_unique:
        existing = execute_query("SELECT id FROM users WHERE email = %s", (email.strip().lower(),), fetchone=True)
        if existing:
            errors.append("An account with this email address already exists. Please login instead.")

    # Phone validation
    if not phone or not phone.strip():
        errors.append("Mobile number is required.")
    elif not is_valid_indian_mobile(phone):
        errors.append("Please enter a valid 10-digit Indian mobile number starting with 6, 7, 8, or 9.")

    # Password validation
    if password is not None:
        pw_ok, pw_err = validate_password_strength(password)
        if not pw_ok:
            errors.append(pw_err)

        if password != confirm_password:
            errors.append("Password and confirm password do not match.")

    return errors


def validate_donor_profile(donor_type, organization_name, address, city, area, pincode):
    """Validates donor specific registration fields."""
    errors = []
    allowed_types = ['individual', 'restaurant', 'hotel', 'caterer', 'corporate', 'supermarket', 'other']

    if not donor_type or donor_type not in allowed_types:
        errors.append(f"Invalid donor type selected. Must be one of: {', '.join(allowed_types)}.")

    if donor_type != 'individual' and (not organization_name or not organization_name.strip()):
        errors.append("Organization or business name is required for commercial/organization donors.")

    if not address or len(address.strip()) < 5:
        errors.append("Please provide a detailed pickup/donor street address (min 5 characters).")

    if not city or not city.strip():
        errors.append("City is required.")

    if not area or not area.strip():
        errors.append("Area / locality is required.")

    if not pincode or not is_valid_pincode(pincode):
        errors.append("Please provide a valid 6-digit Indian PIN code.")

    return errors


def validate_ngo_profile(ngo_name, registration_number, contact_person, address, city, state, pincode, ngo_type):
    """Validates NGO registration details."""
    errors = []
    allowed_types = ['shelter', 'orphanage', 'food_bank', 'charity', 'community_kitchen', 'old_age_home', 'other']

    if not ngo_name or len(ngo_name.strip()) < 3:
        errors.append("NGO organization name is required (min 3 characters).")

    if not registration_number or not registration_number.strip():
        errors.append("Government registration / NGO Darpan / Trust number is required.")
    else:
        existing = execute_query("SELECT id FROM ngos WHERE registration_number = %s", (registration_number.strip(),), fetchone=True)
        if existing:
            errors.append("An NGO with this registration number is already registered.")

    if not contact_person or len(contact_person.strip()) < 2:
        errors.append("Contact person name is required.")

    if not address or len(address.strip()) < 5:
        errors.append("NGO physical address is required.")

    if not city or not city.strip():
        errors.append("City is required.")

    if not state or not state.strip():
        errors.append("State is required.")

    if not pincode or not is_valid_pincode(pincode):
        errors.append("Please provide a valid 6-digit Indian PIN code.")

    if not ngo_type or ngo_type not in allowed_types:
        errors.append(f"Invalid NGO type selected. Allowed: {', '.join(allowed_types)}.")

    return errors


def validate_volunteer_profile(address, city, pincode, vehicle_type):
    """Validates volunteer profile fields."""
    errors = []
    allowed_vehicles = ['two_wheeler', 'four_wheeler', 'van', 'bicycle', 'none']

    if not address or len(address.strip()) < 5:
        errors.append("Residential address is required (min 5 characters).")

    if not city or not city.strip():
        errors.append("City is required.")

    if not pincode or not is_valid_pincode(pincode):
        errors.append("Please provide a valid 6-digit PIN code.")

    if not vehicle_type or vehicle_type not in allowed_vehicles:
        errors.append(f"Please select a valid transport/vehicle option.")

    return errors


def save_secure_upload(file_storage, target_folder, allowed_extensions=ALLOWED_DOCUMENT_EXTENSIONS):
    """
    Securely validates and saves an uploaded file.
    Validates extension, size, and generates a non-guessable secure filename.
    Returns (success: bool, filename_or_error: str)
    """
    if not file_storage or not file_storage.filename:
        return False, "No file provided."

    original_filename = secure_filename(file_storage.filename)
    if not original_filename:
        return False, "Invalid filename."

    ext = original_filename.rsplit('.', 1)[-1].lower() if '.' in original_filename else ''
    if ext not in allowed_extensions:
        return False, f"Unsupported file type (.{ext}). Allowed formats: {', '.join(allowed_extensions).upper()}."

    # Validate file size by seeking
    file_storage.seek(0, os.SEEK_END)
    file_size = file_storage.tell()
    file_storage.seek(0)  # Reset to beginning

    if file_size > MAX_UPLOAD_SIZE:
        return False, f"File exceeds maximum allowed limit of {MAX_UPLOAD_SIZE // (1024 * 1024)} MB."

    if file_size == 0:
        return False, "Uploaded file is empty."

    # Generate safe unique filename
    unique_filename = f"{uuid.uuid4().hex}_{original_filename}"
    os.makedirs(target_folder, exist_ok=True)
    destination_path = os.path.join(target_folder, unique_filename)
    file_storage.save(destination_path)

    return True, unique_filename


def validate_food_donation_fields(food_name, food_category, quantity_str, unit, servings_str, food_type,
                                   prep_dt_str, best_before_str, pickup_address, city, area, pincode, contact_number):
    """
    Validates surplus food donation data with strict safety standards.
    Returns (is_valid: bool, errors: list, parsed_data: dict)
    """
    from datetime import datetime
    errors = []
    parsed = {}

    # Food Name
    if not food_name or len(food_name.strip()) < 2:
        errors.append("Food name is required (at least 2 characters).")
    elif len(food_name.strip()) > 150:
        errors.append("Food name cannot exceed 150 characters.")
    else:
        parsed['food_name'] = food_name.strip()

    # Category
    allowed_categories = ['cooked_meals', 'raw_ingredients', 'bakery_items', 'packaged_foods', 'fruits_vegetables', 'dairy_products', 'beverages', 'other']
    if not food_category or food_category not in allowed_categories:
        errors.append(f"Invalid food category. Allowed: {', '.join(allowed_categories)}.")
    else:
        parsed['food_category'] = food_category

    # Food Type
    if food_type not in ['veg', 'non_veg']:
        errors.append("Please specify whether the food is Vegetarian or Non-Vegetarian.")
    else:
        parsed['food_type'] = food_type

    # Quantity
    try:
        qty = float(quantity_str)
        if qty <= 0:
            errors.append("Food quantity must be greater than 0.")
        else:
            parsed['quantity'] = qty
    except (ValueError, TypeError):
        errors.append("Please enter a valid numeric food quantity.")

    # Unit
    allowed_units = ['kg', 'liters', 'packets', 'servings', 'boxes', 'trays']
    if not unit or unit not in allowed_units:
        errors.append(f"Please select a valid unit ({', '.join(allowed_units)}).")
    else:
        parsed['unit'] = unit

    # Servings Estimate
    try:
        servings = int(servings_str)
        if servings <= 0:
            errors.append("Estimated number of people it can serve must be at least 1.")
        else:
            parsed['servings_estimate'] = servings
    except (ValueError, TypeError):
        errors.append("Please enter a valid whole number of estimated servings.")

    # Preparation and Best Before Dates
    prep_dt = None
    best_before_dt = None

    if not prep_dt_str:
        errors.append("Preparation date and time is required.")
    else:
        try:
            # HTML datetime-local format: 'YYYY-MM-DDTHH:MM'
            prep_dt = datetime.fromisoformat(prep_dt_str.replace(' ', 'T'))
            parsed['preparation_datetime'] = prep_dt.strftime('%Y-%m-%d %H:%M:%S')
        except ValueError:
            errors.append("Invalid preparation date/time format.")

    if not best_before_str:
        errors.append("Best-before date and time is required.")
    else:
        try:
            best_before_dt = datetime.fromisoformat(best_before_str.replace(' ', 'T'))
            parsed['best_before_datetime'] = best_before_dt.strftime('%Y-%m-%d %H:%M:%S')
        except ValueError:
            errors.append("Invalid best-before date/time format.")

    # Strict Food Safety Chronological Validation
    if prep_dt and best_before_dt:
        now = datetime.now()
        if best_before_dt <= prep_dt:
            errors.append("Best-before date and time must be later than preparation date and time.")
        if best_before_dt <= now:
            errors.append("Best-before date and time must be in the future. Expired food cannot be accepted for donation.")

    # Location
    if not pickup_address or len(pickup_address.strip()) < 5:
        errors.append("Please provide a detailed street address for pickup.")
    else:
        parsed['pickup_address'] = pickup_address.strip()

    if not city or not city.strip():
        errors.append("City is required.")
    else:
        parsed['city'] = city.strip()

    if not area or not area.strip():
        errors.append("Area / locality is required.")
    else:
        parsed['area'] = area.strip()

    if not pincode or not is_valid_pincode(pincode):
        errors.append("Please provide a valid 6-digit Indian PIN code.")
    else:
        parsed['pincode'] = pincode.strip()

    # Contact
    if not contact_number or not is_valid_indian_mobile(contact_number):
        errors.append("Please provide a valid 10-digit Indian mobile number for pickup coordination.")
    else:
        parsed['contact_number'] = contact_number.strip()

    is_valid = len(errors) == 0
    return is_valid, errors, parsed
