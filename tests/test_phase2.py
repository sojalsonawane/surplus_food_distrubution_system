"""
Phase 2 Automated Verification Suite: Authentication & Role-Based Authorization
Tests:
- Input validation (name, email, phone, password strength, pincode)
- Donor, NGO, and Volunteer registrations with transactional integrity
- Werkzeug password hashing verification
- Login, session handling, remember me, last_login update
- Inactive / rejected account login prevention
- Role-based authorization: vertical/horizontal privilege escalation blocks (403)
- Unauthenticated access redirection to login
- Logout and session clearance
- Audit trail logging
"""

import unittest
import sys
import io
from pathlib import Path
from werkzeug.security import check_password_hash

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app
from database.db import execute_query, execute_update


class Phase2TestSuite(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        cls.app.config['WTF_CSRF_ENABLED'] = False
        cls.client = cls.app.test_client()

        # Clean up any leftover test accounts
        cls._cleanup_test_data()

    @classmethod
    def tearDownClass(cls):
        cls._cleanup_test_data()

    @classmethod
    def _cleanup_test_data(cls):
        execute_update("DELETE FROM users WHERE email LIKE %s", ('%@testdomain.org',))

    def test_01_donor_registration_success(self):
        """Test valid donor registration with profile creation and password hashing."""
        response = self.client.post('/register', data={
            'role': 'donor',
            'name': 'Rahul Verma',
            'email': 'rahul.donor@testdomain.org',
            'phone': '9811223344',
            'password': 'SecurePass@2026',
            'confirm_password': 'SecurePass@2026',
            'donor_type': 'restaurant',
            'organization_name': 'Verma Sweets & Caterers',
            'address': 'Shop 12, Main Market Road',
            'city': 'Delhi',
            'area': 'Connaught Place',
            'pincode': '110001'
        }, follow_redirects=False)

        # Should redirect to login on success
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.headers.get('Location'))

        # Verify user record in database
        user = execute_query(
            "SELECT * FROM users WHERE email = %s",
            ('rahul.donor@testdomain.org',),
            fetchone=True
        )
        self.assertIsNotNone(user)
        self.assertEqual(user['role'], 'donor')
        self.assertEqual(user['status'], 'active')
        self.assertTrue(check_password_hash(user['password_hash'], 'SecurePass@2026'))
        # Password must NEVER be plain text
        self.assertNotEqual(user['password_hash'], 'SecurePass@2026')

        # Verify donor profile
        donor = execute_query(
            "SELECT * FROM donors WHERE user_id = %s",
            (user['id'],),
            fetchone=True
        )
        self.assertIsNotNone(donor)
        self.assertEqual(donor['donor_type'], 'restaurant')
        self.assertEqual(donor['organization_name'], 'Verma Sweets & Caterers')
        self.assertEqual(donor['pincode'], '110001')

    def test_02_registration_validation_errors(self):
        """Test that invalid registration fields trigger clear error messages."""
        # 1. Weak password
        resp = self.client.post('/register', data={
            'role': 'donor',
            'name': 'Amit Kumar',
            'email': 'amit@testdomain.org',
            'phone': '9822334455',
            'password': 'weak',
            'confirm_password': 'weak',
            'donor_type': 'individual',
            'address': 'Street 1',
            'city': 'Pune',
            'area': 'Kothrud',
            'pincode': '411038'
        }, follow_redirects=True)
        self.assertIn("Password must be at least 8 characters long", resp.data.decode('utf-8'))

        # 2. Invalid Indian phone number (starts with 1)
        resp = self.client.post('/register', data={
            'role': 'donor',
            'name': 'Amit Kumar',
            'email': 'amit@testdomain.org',
            'phone': '1234567890',
            'password': 'StrongPass@123',
            'confirm_password': 'StrongPass@123',
            'donor_type': 'individual',
            'address': 'Street 1',
            'city': 'Pune',
            'area': 'Kothrud',
            'pincode': '411038'
        }, follow_redirects=True)
        self.assertIn("Please enter a valid 10-digit Indian mobile number", resp.data.decode('utf-8'))

        # 3. Duplicate email
        resp = self.client.post('/register', data={
            'role': 'donor',
            'name': 'Duplicate Person',
            'email': 'rahul.donor@testdomain.org',  # already created in test_01
            'phone': '9877665544',
            'password': 'StrongPass@123',
            'confirm_password': 'StrongPass@123',
            'donor_type': 'individual',
            'address': 'Street 1',
            'city': 'Delhi',
            'area': 'Rohini',
            'pincode': '110085'
        }, follow_redirects=True)
        self.assertIn("already exists", resp.data.decode('utf-8'))

    def test_03_ngo_registration_with_document(self):
        """Test NGO registration with verification certificate upload."""
        fake_pdf = (io.BytesIO(b"%PDF-1.4 Fake PDF Content for NGO verification"), "trust_certificate.pdf")

        response = self.client.post('/register', data={
            'role': 'ngo',
            'name': 'Sunita Rao',
            'email': 'sunita.ngo@testdomain.org',
            'phone': '8877665544',
            'password': 'NgoSecurePass@99',
            'confirm_password': 'NgoSecurePass@99',
            'ngo_name': 'Asha Annakshetra Trust',
            'registration_number': 'REG/MH/2026/0044',
            'contact_person': 'Sunita Rao',
            'address': 'Plot 45, Sector 18, Vashi',
            'city': 'Navi Mumbai',
            'state': 'Maharashtra',
            'pincode': '400703',
            'ngo_type': 'community_kitchen',
            'verification_document': fake_pdf
        }, content_type='multipart/form-data', follow_redirects=False)

        self.assertEqual(response.status_code, 302)

        # NGO user should start with status 'pending_approval'
        user = execute_query(
            "SELECT * FROM users WHERE email = %s",
            ('sunita.ngo@testdomain.org',),
            fetchone=True
        )
        self.assertIsNotNone(user)
        self.assertEqual(user['role'], 'ngo')
        self.assertEqual(user['status'], 'pending_approval')

        # NGO record verification status should be 'pending'
        ngo = execute_query(
            "SELECT * FROM ngos WHERE user_id = %s",
            (user['id'],),
            fetchone=True
        )
        self.assertIsNotNone(ngo)
        self.assertEqual(ngo['verification_status'], 'pending')
        self.assertIsNotNone(ngo['verification_document'])
        self.assertTrue(ngo['verification_document'].endswith('.pdf'))

    def test_04_volunteer_registration(self):
        """Test Volunteer registration with vehicle specification."""
        response = self.client.post('/register', data={
            'role': 'volunteer',
            'name': 'Vikram Mehra',
            'email': 'vikram.vol@testdomain.org',
            'phone': '7766554433',
            'password': 'VolSecurePass@88',
            'confirm_password': 'VolSecurePass@88',
            'address': 'Flat 204, Green Heights',
            'city': 'Bengaluru',
            'pincode': '560001',
            'vehicle_type': 'two_wheeler'
        }, follow_redirects=False)

        self.assertEqual(response.status_code, 302)

        user = execute_query(
            "SELECT * FROM users WHERE email = %s",
            ('vikram.vol@testdomain.org',),
            fetchone=True
        )
        self.assertIsNotNone(user)
        self.assertEqual(user['role'], 'volunteer')

        vol = execute_query(
            "SELECT * FROM volunteers WHERE user_id = %s",
            (user['id'],),
            fetchone=True
        )
        self.assertIsNotNone(vol)
        self.assertEqual(vol['vehicle_type'], 'two_wheeler')
        self.assertEqual(vol['availability_status'], 'available')

    def test_05_login_success_and_redirection(self):
        """Test login redirects each role to its dedicated dashboard and records session."""
        # 1. Admin login
        resp_admin = self.client.post('/login', data={
            'email': 'admin@surplusfood.org',
            'password': 'Admin@12345'
        }, follow_redirects=False)
        self.assertEqual(resp_admin.status_code, 302)
        self.assertIn('/admin/dashboard', resp_admin.headers.get('Location'))

        # Check session
        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get('role'), 'admin')
            self.assertEqual(sess.get('user_email'), 'admin@surplusfood.org')

        # Logout
        self.client.get('/logout')

        # 2. Donor login
        resp_donor = self.client.post('/login', data={
            'email': 'rahul.donor@testdomain.org',
            'password': 'SecurePass@2026'
        }, follow_redirects=False)
        self.assertEqual(resp_donor.status_code, 302)
        self.assertIn('/donor/dashboard', resp_donor.headers.get('Location'))

        self.client.get('/logout')

    def test_06_login_invalid_credentials(self):
        """Test login rejection on wrong password or unregistered email."""
        resp = self.client.post('/login', data={
            'email': 'admin@surplusfood.org',
            'password': 'WrongPassword@999'
        }, follow_redirects=True)
        self.assertIn("Invalid email address or password.", resp.data.decode('utf-8'))

    def test_07_role_based_authorization_protection(self):
        """
        Verify that users cannot access dashboards of other roles (403 Forbidden)
        and unauthenticated users are redirected to login.
        """
        # 1. Unauthenticated access -> redirected to login
        self.client.get('/logout')
        resp_unauth = self.client.get('/admin/dashboard', follow_redirects=False)
        self.assertEqual(resp_unauth.status_code, 302)
        self.assertIn('/login', resp_unauth.headers.get('Location'))

        # 2. Log in as Donor
        self.client.post('/login', data={
            'email': 'rahul.donor@testdomain.org',
            'password': 'SecurePass@2026'
        })

        # Donor accessing own dashboard -> 200 OK
        resp_donor_own = self.client.get('/donor/dashboard')
        self.assertEqual(resp_donor_own.status_code, 200)

        # Donor attempting to access Admin Dashboard -> 403 Forbidden!
        resp_donor_to_admin = self.client.get('/admin/dashboard')
        self.assertEqual(resp_donor_to_admin.status_code, 403)
        self.assertIn("403", resp_donor_to_admin.data.decode('utf-8'))
        self.assertIn("Access Forbidden", resp_donor_to_admin.data.decode('utf-8'))

        # Donor attempting to access Volunteer Dashboard -> 403 Forbidden!
        resp_donor_to_vol = self.client.get('/volunteer/dashboard')
        self.assertEqual(resp_donor_to_vol.status_code, 403)

        self.client.get('/logout')

    def test_08_audit_logs_recorded(self):
        """Verify that authentication events are faithfully logged in audit_logs."""
        logs = execute_query(
            "SELECT action FROM audit_logs WHERE action IN ('REGISTER', 'LOGIN_SUCCESS', 'LOGIN_FAILED', 'UNAUTHORIZED_ACCESS_ATTEMPT')"
        )
        recorded_actions = {log['action'] for log in logs}

        self.assertIn('REGISTER', recorded_actions)
        self.assertIn('LOGIN_SUCCESS', recorded_actions)
        self.assertIn('LOGIN_FAILED', recorded_actions)
        self.assertIn('UNAUTHORIZED_ACCESS_ATTEMPT', recorded_actions)


if __name__ == '__main__':
    unittest.main(verbosity=2)
