"""
In-app notification helper for Surplus Food Distribution System.
"""

from database.db import execute_insert


def create_notification(user_id, title, message, notif_type='info', related_link=None):
    """
    Creates an in-app notification for a user.
    :param user_id: Target user ID
    :param title: Short title header
    :param message: Notification body
    :param notif_type: 'info', 'success', 'warning', 'danger'
    :param related_link: URL link for user action
    """
    try:
        execute_insert("""
            INSERT INTO notifications (user_id, title, message, type, related_link)
            VALUES (%s, %s, %s, %s, %s)
        """, (user_id, title[:150], message, notif_type, related_link))
        return True
    except Exception:
        return False
