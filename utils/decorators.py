"""
Authentication and role-based authorization decorators.
Enforces strict session verification and prevents horizontal/vertical privilege escalation.
"""

from functools import wraps
from flask import session, flash, redirect, url_for, request, render_template
from utils.audit import log_audit


def login_required(f):
    """
    Ensures the user has an active authenticated session.
    Redirects to login page with next parameter if unauthenticated.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id'):
            flash("Please log in to access this page.", "warning")
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


def role_required(*allowed_roles):
    """
    Decorator factory that restricts route access to specified roles.
    If unauthenticated, redirects to login.
    If authenticated but role is forbidden, logs security event and renders 403 Forbidden.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user_id = session.get('user_id')
            user_role = session.get('role')

            if not user_id:
                flash("Please log in to access this area.", "warning")
                return redirect(url_for('auth.login', next=request.url))

            if user_role not in allowed_roles:
                log_audit(
                    user_id=user_id,
                    action='UNAUTHORIZED_ACCESS_ATTEMPT',
                    entity_type='route',
                    details=f"Role '{user_role}' attempted access to protected endpoint requiring {allowed_roles}: {request.path}"
                )
                return render_template('errors/403.html'), 403

            return f(*args, **kwargs)
        return decorated_function
    return decorator


def admin_required(f):
    """Restricts access to system administrators."""
    return role_required('admin')(f)


def donor_required(f):
    """Restricts access to registered food donors."""
    return role_required('donor')(f)


def ngo_required(f):
    """Restricts access to registered NGOs."""
    return role_required('ngo')(f)


def volunteer_required(f):
    """Restricts access to registered volunteers."""
    return role_required('volunteer')(f)
