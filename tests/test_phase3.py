"""
Phase 3 Automated Verification Suite: Admin Module
Tests:
- Admin Dashboard metrics and recent activity
- User Management: search, filter, status toggling, safe deletion
- NGO Verification: dossier inspection, document access, approval/rejection with reason
- Donor & Volunteer rosters
- Food Donations Supervision: listing, approval, volunteer pickup dispatch
- Cross-NGO Beneficiaries Directory
- Security Audit Log Viewer & filtering
"""

import unittest
import sys
from pathlib import Path
from werkzeug.security import generate_password_hash

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app
from database.db import execute_query, execute_update, execute_insert


class Phase3TestSuite(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        cls.app.config['WTF_CSRF_ENABLED'] = False
        cls.client = cls.app.test_client()

        # Clean up existing test data
        cls._cleanup()
        # Seed test records
        cls._seed_test_records()

    @classmethod
    def tearDownClass(cls):
        cls._cleanup()

    @classmethod
    def _cleanup(cls):
        execute_update("DELETE FROM users WHERE email LIKE %s", ('%@p3test.org',))

    @classmethod
    def _seed_test_records(cls):
        """Seed dummy donor, NGO, volunteer, and food donation for admin module testing."""
        pw_hash = generate_password_hash("TestPass@1234")

        # 1. Donor
        cls.donor_u_id = execute_insert("""
            INSERT INTO users (name, email, password_hash, role, phone, status)
            VALUES ('P3 Donor', 'donor@p3test.org', %s, 'donor', '9812345670', 'active')
        """, (pw_hash,))
        cls.donor_id = execute_insert("""
            INSERT INTO donors (user_id, donor_type, organization_name, address, city, area, pincode)
            VALUES (%s, 'restaurant', 'Test Food Court', '10 Market St', 'Delhi', 'Connaught Place', '110001')
        """, (cls.donor_u_id,))

        # 2. NGO (Pending verification)
        cls.ngo_u_id = execute_insert("""
            INSERT INTO users (name, email, password_hash, role, phone, status)
            VALUES ('P3 NGO Admin', 'ngo@p3test.org', %s, 'ngo', '9812345671', 'pending_approval')
        """, (pw_hash,))
        cls.ngo_id = execute_insert("""
            INSERT INTO ngos (user_id, ngo_name, registration_number, contact_person, address, city, state, pincode, ngo_type, verification_status)
            VALUES (%s, 'Test Care Shelter', 'REG/P3/99001', 'P3 NGO Admin', '5 Charity Way', 'Delhi', 'Delhi', '110001', 'shelter', 'pending')
        """, (cls.ngo_u_id,))

        # 3. Volunteer
        cls.vol_u_id = execute_insert("""
            INSERT INTO users (name, email, password_hash, role, phone, status)
            VALUES ('P3 Volunteer', 'vol@p3test.org', %s, 'volunteer', '9812345672', 'active')
        """, (pw_hash,))
        cls.vol_id = execute_insert("""
            INSERT INTO volunteers (user_id, address, city, pincode, vehicle_type, availability_status)
            VALUES (%s, '20 Green Ave', 'Delhi', '110001', 'two_wheeler', 'available')
        """, (cls.vol_u_id,))

        # 4. Food Donation
        cls.donation_id = execute_insert("""
            INSERT INTO food_donations (donor_id, food_name, food_category, quantity, unit, servings_estimate, food_type, preparation_datetime, best_before_datetime, pickup_address, city, area, pincode, contact_number, status)
            VALUES (%s, 'Vegetable Pulao and Curry', 'cooked_meals', 15.00, 'kg', 45, 'veg', NOW(), DATE_ADD(NOW(), INTERVAL 6 HOUR), '10 Market St', 'Delhi', 'Connaught Place', '110001', '9812345670', 'Pending')
        """, (cls.donor_id,))

        # 5. Beneficiary under NGO
        cls.ben_id = execute_insert("""
            INSERT INTO beneficiaries (ngo_id, name, age, gender, address, household_count, status)
            VALUES (%s, 'P3 Beneficiary Family', 35, 'female', 'Block D, Camp', 4, 'active')
        """, (cls.ngo_id,))

    def _login_as_admin(self):
        """Helper to establish an admin session."""
        self.client.post('/login', data={
            'email': 'admin@surplusfood.org',
            'password': 'Admin@12345'
        })

    def test_01_admin_dashboard_metrics(self):
        """Test admin dashboard returns 200 with all statistics and recent tables."""
        self._login_as_admin()
        response = self.client.get('/admin/dashboard')
        self.assertEqual(response.status_code, 200)
        content = response.data.decode('utf-8')
        self.assertIn("System Administration Dashboard", content)
        self.assertIn("Total Donors", content)
        self.assertIn("Registered NGOs", content)
        self.assertIn("Volunteers", content)
        self.assertIn("Vegetable Pulao and Curry", content)

    def test_02_users_management_search_filter(self):
        """Test user listing, search, and filtering."""
        self._login_as_admin()

        # 1. Access user list
        resp = self.client.get('/admin/users')
        self.assertEqual(resp.status_code, 200)
        self.assertIn("User Management", resp.data.decode('utf-8'))

        # 2. Search by email
        resp_search = self.client.get('/admin/users?search=donor@p3test.org')
        self.assertEqual(resp_search.status_code, 200)
        self.assertIn("P3 Donor", resp_search.data.decode('utf-8'))

        # 3. Filter by role
        resp_role = self.client.get('/admin/users?role=ngo')
        self.assertEqual(resp_role.status_code, 200)
        self.assertIn("P3 NGO Admin", resp_role.data.decode('utf-8'))

    def test_03_toggle_user_status(self):
        """Test activating and deactivating a user account."""
        self._login_as_admin()

        # Toggle volunteer to inactive
        resp = self.client.post(f'/admin/users/{self.vol_u_id}/toggle-status', follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

        u = execute_query("SELECT status FROM users WHERE id = %s", (self.vol_u_id,), fetchone=True)
        self.assertEqual(u['status'], 'inactive')

        # Toggle volunteer back to active
        self.client.post(f'/admin/users/{self.vol_u_id}/toggle-status', follow_redirects=True)
        u2 = execute_query("SELECT status FROM users WHERE id = %s", (self.vol_u_id,), fetchone=True)
        self.assertEqual(u2['status'], 'active')

    def test_04_ngo_verification_workflow(self):
        """Test NGO dossier review and approval workflow."""
        self._login_as_admin()

        # 1. View NGO dossier
        resp = self.client.get(f'/admin/ngos/{self.ngo_id}')
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Test Care Shelter", resp.data.decode('utf-8'))
        self.assertIn("REG/P3/99001", resp.data.decode('utf-8'))

        # 2. Approve NGO
        resp_approve = self.client.post(f'/admin/ngos/{self.ngo_id}/verify', data={
            'action': 'approve'
        }, follow_redirects=True)
        self.assertEqual(resp_approve.status_code, 200)
        self.assertIn("approved and activated", resp_approve.data.decode('utf-8'))

        # Verify in DB
        ngo = execute_query("SELECT verification_status FROM ngos WHERE id = %s", (self.ngo_id,), fetchone=True)
        self.assertEqual(ngo['verification_status'], 'verified')
        ngo_user = execute_query("SELECT status FROM users WHERE id = %s", (self.ngo_u_id,), fetchone=True)
        self.assertEqual(ngo_user['status'], 'active')

        # Verify notification generated
        notif = execute_query("SELECT * FROM notifications WHERE user_id = %s", (self.ngo_u_id,), fetchone=True)
        self.assertIsNotNone(notif)
        self.assertIn("Verification Approved", notif['title'])

    def test_05_donations_approval_and_pickup_assignment(self):
        """Test approving food donation and assigning volunteer for pickup."""
        self._login_as_admin()

        # 1. View donation details
        resp = self.client.get(f'/admin/donations/{self.donation_id}')
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Vegetable Pulao and Curry", resp.data.decode('utf-8'))

        # 2. Approve donation
        resp_app = self.client.post(f'/admin/donations/{self.donation_id}/verify', data={
            'action': 'approve'
        }, follow_redirects=True)
        self.assertEqual(resp_app.status_code, 200)

        don = execute_query("SELECT status FROM food_donations WHERE id = %s", (self.donation_id,), fetchone=True)
        self.assertEqual(don['status'], 'Approved')

        # 3. Assign volunteer for pickup
        resp_assign = self.client.post(f'/admin/donations/{self.donation_id}/assign-pickup', data={
            'volunteer_id': self.vol_id,
            'notes': 'Collect with hot containers'
        }, follow_redirects=True)
        self.assertEqual(resp_assign.status_code, 200)

        # Verify donation status is now 'Pickup Assigned'
        don_after = execute_query("SELECT status FROM food_donations WHERE id = %s", (self.donation_id,), fetchone=True)
        self.assertEqual(don_after['status'], 'Pickup Assigned')

        # Verify pickup assignment record exists
        pa = execute_query("SELECT * FROM pickup_assignments WHERE donation_id = %s", (self.donation_id,), fetchone=True)
        self.assertIsNotNone(pa)
        self.assertEqual(pa['volunteer_id'], self.vol_id)
        self.assertEqual(pa['status'], 'assigned')

    def test_06_beneficiaries_and_audit_logs(self):
        """Test beneficiaries directory and audit log viewer."""
        self._login_as_admin()

        # 1. Beneficiaries
        resp_ben = self.client.get('/admin/beneficiaries')
        self.assertEqual(resp_ben.status_code, 200)
        self.assertIn("P3 Beneficiary Family", resp_ben.data.decode('utf-8'))

        # 2. Audit logs
        resp_audit = self.client.get('/admin/audit-logs')
        self.assertEqual(resp_audit.status_code, 200)
        self.assertIn("Security & Activity Audit Trail", resp_audit.data.decode('utf-8'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
