"""
Database Initialization Script.
Creates database if missing, executes schema.sql, verifies all 11 tables,
and creates default admin user with hashed password.
"""

import os
import sys
from pathlib import Path
from werkzeug.security import generate_password_hash

# Add root directory to sys.path to ensure modules can be imported
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import get_config
from database.db import get_db_connection

config = get_config()

REQUIRED_TABLES = [
    'users',
    'donors',
    'ngos',
    'volunteers',
    'beneficiaries',
    'food_donations',
    'food_requests',
    'pickup_assignments',
    'distribution_records',
    'notifications',
    'audit_logs'
]


def create_database_if_not_exists():
    """Connect to MySQL without database selected and create target DB."""
    print(f"[*] Checking MySQL connection on {config.MYSQL_HOST}:{config.MYSQL_PORT}...")
    conn = get_db_connection(use_database=False)
    cursor = conn.cursor()
    try:
        sql = f"CREATE DATABASE IF NOT EXISTS `{config.MYSQL_DATABASE}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
        cursor.execute(sql)
        conn.commit()
        print(f"[+] Database `{config.MYSQL_DATABASE}` ensured successfully.")
    finally:
        cursor.close()
        conn.close()


def run_schema_file():
    """Read schema.sql and execute all SQL statements."""
    schema_path = PROJECT_ROOT / 'database' / 'schema.sql'
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found at {schema_path}")

    print(f"[*] Executing schema from: {schema_path}")
    with open(schema_path, 'r', encoding='utf-8') as f:
        schema_sql = f.read()

    conn = get_db_connection(use_database=True)
    cursor = conn.cursor()
    try:
        # Split by semicolon while ignoring comments
        statements = []
        current = []
        for line in schema_sql.splitlines():
            stripped = line.strip()
            if stripped.startswith('--') or not stripped:
                continue
            current.append(line)
            if stripped.endswith(';'):
                stmt = '\n'.join(current).strip()
                if stmt:
                    statements.append(stmt)
                current = []

        for stmt in statements:
            if stmt:
                cursor.execute(stmt)
        conn.commit()
        print(f"[+] Executed {len(statements)} schema statements successfully.")
    except Exception as e:
        conn.rollback()
        print(f"[-] Error executing schema: {e}")
        raise
    finally:
        cursor.close()
        conn.close()


def verify_tables():
    """Verify that all 11 required tables exist."""
    conn = get_db_connection(use_database=True)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT TABLE_NAME 
            FROM information_schema.tables 
            WHERE table_schema = %s
        """, (config.MYSQL_DATABASE,))
        existing_tables = {
            (row.get('TABLE_NAME') or row.get('table_name'))
            for row in cursor.fetchall()
        }

        print("\n[*] Verifying required tables in database:")
        all_present = True
        for table in REQUIRED_TABLES:
            if table in existing_tables:
                print(f"  [OK] Table '{table}' exists.")
            else:
                print(f"  [MISSING] Table '{table}' NOT FOUND!")
                all_present = False

        if not all_present:
            raise RuntimeError("One or more required tables were not created.")
        print("[+] All 11 required tables successfully verified!\n")
    finally:
        cursor.close()
        conn.close()


def seed_default_admin():
    """Seed initial system administrator if not already present."""
    admin_email = "admin@surplusfood.org"
    admin_password = "Admin@12345"  # Matches strong password policy (Upper, lower, digit, special, >=8 chars)
    admin_name = "System Administrator"
    admin_phone = "9876543210"

    conn = get_db_connection(use_database=True)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, email FROM users WHERE email = %s", (admin_email,))
        existing_admin = cursor.fetchone()
        if existing_admin:
            print(f"[i] Default admin already exists (ID: {existing_admin['id']}, Email: {admin_email}). Skipping seed.")
        else:
            hashed_pw = generate_password_hash(admin_password)
            cursor.execute("""
                INSERT INTO users (name, email, password_hash, role, phone, status)
                VALUES (%s, %s, %s, 'admin', %s, 'active')
            """, (admin_name, admin_email, hashed_pw, admin_phone))
            conn.commit()
            print("[+] Seeded default administrator account:")
            print(f"    - Email:    {admin_email}")
            print(f"    - Password: {admin_password}")
            print(f"    - Role:     admin")
    except Exception as e:
        conn.rollback()
        print(f"[-] Failed to seed admin user: {e}")
        raise
    finally:
        cursor.close()
        conn.close()


def main():
    print("==================================================================")
    print(" Surplus Food Distribution System - Database Initializer")
    print("==================================================================")
    try:
        create_database_if_not_exists()
        run_schema_file()
        verify_tables()
        seed_default_admin()
        print("==================================================================")
        print("[SUCCESS] Database initialization completed successfully.")
        print("==================================================================")
    except Exception as e:
        print(f"\n[FATAL] Database initialization failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
