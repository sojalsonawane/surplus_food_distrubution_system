"""
Phase 1 Automated Verification Suite
Tests:
- Flask App initialization
- Database connectivity & health endpoint
- All public routes (/, /about, /how-it-works, /food-safety, /contact)
- Custom error handlers (404)
- Security HTTP response headers
- DB query helpers (execute_query, execute_insert, execute_update)
"""

import unittest
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app
from database.db import check_db_health, execute_query, execute_insert, execute_update


class Phase1TestSuite(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.client = cls.app.test_client()

    def test_01_db_health(self):
        """Verify database connection is active and healthy."""
        db_ok, msg = check_db_health()
        self.assertTrue(db_ok, f"Database health check failed: {msg}")
        self.assertIn("Connected to MySQL", msg)

    def test_02_health_endpoint(self):
        """Verify /health endpoint returns JSON status 200 with healthy state."""
        response = self.client.get('/health')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['status'], 'healthy')
        self.assertTrue(data['database']['connected'])

    def test_03_index_route(self):
        """Verify landing page loads and contains hero slogan and CTA."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        content = response.data.decode('utf-8')
        self.assertIn("Reduce Food Waste. Share Food. Serve Communities.", content)
        self.assertIn("Donate Food", content)
        self.assertIn("Find Food", content)
        self.assertIn("Join as Volunteer", content)

    def test_04_about_route(self):
        """Verify /about page loads with mission and objectives."""
        response = self.client.get('/about')
        self.assertEqual(response.status_code, 200)
        content = response.data.decode('utf-8')
        self.assertIn("About Our Platform", content)
        self.assertIn("Our Core Mission", content)

    def test_05_how_it_works_route(self):
        """Verify /how-it-works page loads with complete workflow sequence."""
        response = self.client.get('/how-it-works')
        self.assertEqual(response.status_code, 200)
        content = response.data.decode('utf-8')
        self.assertIn("How It Works", content)
        self.assertIn("Step 1: Donation Creation", content)
        self.assertIn("Step 6: Community Distribution", content)

    def test_06_food_safety_route(self):
        """Verify /food-safety page contains mandatory safety warning text."""
        response = self.client.get('/food-safety')
        self.assertEqual(response.status_code, 200)
        content = response.data.decode('utf-8')
        self.assertIn("Only safe and edible surplus food should be donated", content)
        self.assertIn("Acceptable Food Categories", content)
        self.assertIn("Strictly Prohibited Items", content)

    def test_07_contact_route_get_and_post(self):
        """Verify GET and POST handling for /contact."""
        # GET request
        response_get = self.client.get('/contact')
        self.assertEqual(response_get.status_code, 200)
        self.assertIn("Contact Our Support Team", response_get.data.decode('utf-8'))

        # POST request with valid data
        response_post = self.client.post('/contact', data={
            'name': 'Priya Singh',
            'email': 'priya.singh@example.org',
            'subject': 'Food Donation Drive',
            'message': 'We have monthly excess bakery supplies for collection.'
        }, follow_redirects=True)
        self.assertEqual(response_post.status_code, 200)
        self.assertIn("Thank you for reaching out!", response_post.data.decode('utf-8'))

    def test_08_error_handling_404(self):
        """Verify customized 404 error page on invalid route."""
        response = self.client.get('/non-existent-page-url-xyz')
        self.assertEqual(response.status_code, 404)
        content = response.data.decode('utf-8')
        self.assertIn("404", content)
        self.assertIn("Page Not Found", content)

    def test_09_security_headers(self):
        """Verify required security headers on all responses."""
        response = self.client.get('/')
        self.assertEqual(response.headers.get('X-Content-Type-Options'), 'nosniff')
        self.assertEqual(response.headers.get('X-Frame-Options'), 'SAMEORIGIN')
        self.assertEqual(response.headers.get('X-XSS-Protection'), '1; mode=block')
        self.assertEqual(response.headers.get('Referrer-Policy'), 'strict-origin-when-cross-origin')

    def test_10_database_parameterized_crud(self):
        """Verify parameterized queries and transaction integrity."""
        test_email = "param_test_audit@surplusfood.org"
        
        # Test execute_insert
        insert_id = execute_insert(
            "INSERT INTO audit_logs (user_id, action, entity_type, details) VALUES (%s, %s, %s, %s)",
            (None, 'TEST_ACTION', 'test_entity', 'Automated test record')
        )
        self.assertIsNotNone(insert_id)
        self.assertGreater(insert_id, 0)

        # Test execute_query (fetchone)
        record = execute_query(
            "SELECT * FROM audit_logs WHERE id = %s",
            (insert_id,),
            fetchone=True
        )
        self.assertIsNotNone(record)
        self.assertEqual(record['action'], 'TEST_ACTION')

        # Test execute_update
        updated_rows = execute_update(
            "UPDATE audit_logs SET details = %s WHERE id = %s",
            ('Updated test record', insert_id)
        )
        self.assertEqual(updated_rows, 1)

        # Clean up test record
        execute_update("DELETE FROM audit_logs WHERE id = %s", (insert_id,))


if __name__ == '__main__':
    unittest.main(verbosity=2)
