"""
Database connection manager and query execution helpers.
Provides safe parameterized query execution, transaction handling,
and connection lifecycle management using PyMySQL with DictCursor.
"""

import logging
from contextlib import contextmanager
import pymysql
from pymysql.cursors import DictCursor
from config import get_config

logger = logging.getLogger(__name__)
config = get_config()


def get_db_connection(use_database=True):
    """
    Establish and return a new PyMySQL connection.
    Uses DictCursor so columns can be accessed by name.
    """
    conn_params = {
        'host': config.MYSQL_HOST,
        'port': config.MYSQL_PORT,
        'user': config.MYSQL_USER,
        'password': config.MYSQL_PASSWORD,
        'charset': 'utf8mb4',
        'cursorclass': DictCursor,
        'autocommit': False
    }
    if use_database:
        conn_params['database'] = config.MYSQL_DATABASE

    return pymysql.connect(**conn_params)


@contextmanager
def get_db_cursor(commit=False):
    """
    Context manager that yields a cursor from a connection.
    Commits on exit if commit=True, and automatically rolls back on exception.
    Always safely closes cursor and connection.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        yield cursor
        if commit:
            conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Database error during operation: {e}")
        raise
    finally:
        cursor.close()
        conn.close()


@contextmanager
def db_transaction():
    """
    Context manager for multi-step transactional operations.
    Yields (connection, cursor).
    Commits all steps together or rolls back cleanly if any step fails.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        yield conn, cursor
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Transaction rolled back due to error: {e}")
        raise
    finally:
        cursor.close()
        conn.close()


def execute_query(sql, params=None, fetchone=False):
    """
    Execute a parameterized SELECT query.
    
    :param sql: SQL query string with %s placeholders.
    :param params: Tuple or dict of parameters (never concatenate user input).
    :param fetchone: If True returns a single row dict; otherwise returns list of dicts.
    :return: dict, list of dicts, or None.
    """
    with get_db_cursor(commit=False) as cursor:
        if params is not None:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)
        if fetchone:
            return cursor.fetchone()
        return cursor.fetchall()


def execute_insert(sql, params=None):
    """
    Execute a parameterized INSERT statement.
    
    :param sql: SQL INSERT string with %s placeholders.
    :param params: Parameter tuple or dict.
    :return: The last inserted auto-increment ID (cursor.lastrowid).
    """
    with get_db_cursor(commit=True) as cursor:
        if params is not None:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)
        return cursor.lastrowid


def execute_update(sql, params=None):
    """
    Execute a parameterized UPDATE or DELETE statement.
    
    :param sql: SQL statement with %s placeholders.
    :param params: Parameter tuple or dict.
    :return: The number of rows affected (cursor.rowcount).
    """
    with get_db_cursor(commit=True) as cursor:
        if params is not None:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)
        return cursor.rowcount


def check_db_health():
    """
    Verifies that the database server is reachable and the database exists.
    Returns (status: bool, message: str).
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1 AS health_check, VERSION() AS mysql_version")
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return True, f"Connected to MySQL {result['mysql_version']}"
    except Exception as e:
        return False, str(e)
