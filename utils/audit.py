"""
Audit logging utility for Surplus Food Distribution System.
Records security, authentication, and workflow events to the database audit_logs table.
"""

import logging
from flask import request, has_request_context
from database.db import execute_insert

logger = logging.getLogger(__name__)


def log_audit(user_id, action, entity_type, entity_id=None, details=None, ip_address=None):
    """
    Log an event to the audit_logs table.
    
    :param user_id: ID of the user performing the action (or None for system/anonymous actions).
    :param action: Short action string e.g. 'LOGIN', 'LOGOUT', 'REGISTER', 'DONATION_CREATE'.
    :param entity_type: Type of record impacted e.g. 'user', 'food_donation', 'ngo'.
    :param entity_id: ID of the related entity record (optional).
    :param details: Informative string describing the action details.
    :param ip_address: IP address (auto-detected from request context if omitted).
    """
    try:
        if ip_address is None and has_request_context():
            # Respect X-Forwarded-For if running behind reverse proxy, else fallback to remote_addr
            ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
            if ip_address and ',' in ip_address:
                ip_address = ip_address.split(',')[0].strip()

        # Truncate IP to max 45 chars for IPv6 safety
        if ip_address:
            ip_address = str(ip_address)[:45]

        execute_insert("""
            INSERT INTO audit_logs (user_id, action, entity_type, entity_id, details, ip_address)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (user_id, str(action)[:100], str(entity_type)[:50], entity_id, details, ip_address))

    except Exception as e:
        # Never let audit log failure crash the user application flow, but log error
        logger.error(f"Failed to record audit log: {e}")
