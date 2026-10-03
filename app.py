"""
Surplus Food Distribution System - Flask Application Entrypoint & Factory
"""

import os
from pathlib import Path
from flask import Flask, render_template, jsonify
from config import get_config, config_by_name
from database.db import check_db_health, db_transaction


def create_app(config_name=None):
    """
    Application factory for Surplus Food Distribution System.
    Configures app, registers error handlers, security headers, and blueprints.
    """
    app = Flask(__name__)

    # Load configuration
    if config_name and config_name in config_by_name:
        app.config.from_object(config_by_name[config_name])
    else:
        app.config.from_object(get_config())

    # Ensure required upload directories exist
    upload_base = Path(app.config['UPLOAD_FOLDER'])
    (upload_base / 'food_images').mkdir(parents=True, exist_ok=True)
    (upload_base / 'ngo_documents').mkdir(parents=True, exist_ok=True)

    # Add the contact inbox table to existing installations without resetting data.
    try:
        with db_transaction() as (conn, cursor):
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS contact_inquiries (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    email VARCHAR(150) NOT NULL,
                    subject VARCHAR(200) NOT NULL,
                    message TEXT NOT NULL,
                    status ENUM('new', 'read', 'resolved') NOT NULL DEFAULT 'new',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_contact_inquiries_status (status),
                    INDEX idx_contact_inquiries_created (created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
    except Exception:
        # The app can still start when the database is temporarily unavailable.
        pass

    # --------------------------------------------------------------------------
    # Register Blueprints
    # --------------------------------------------------------------------------
    from routes.main import main_bp
    from routes.auth import auth_bp
    from routes.admin import admin_bp
    from routes.donor import donor_bp
    from routes.ngo import ngo_bp
    from routes.volunteer import volunteer_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(donor_bp)
    app.register_blueprint(ngo_bp)
    app.register_blueprint(volunteer_bp)

    # --------------------------------------------------------------------------
    # Security Response Headers
    # --------------------------------------------------------------------------
    @app.after_request
    def set_security_headers(response):
        """Set standard security headers on all responses."""
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        return response

    # --------------------------------------------------------------------------
    # Custom Error Handlers (400, 401, 403, 404, 405, 500)
    # --------------------------------------------------------------------------
    @app.errorhandler(400)
    def handle_bad_request(e):
        return render_template('errors/400.html'), 400

    @app.errorhandler(401)
    def handle_unauthorized(e):
        return render_template('errors/401.html'), 401

    @app.errorhandler(403)
    def handle_forbidden(e):
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def handle_not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(405)
    def handle_method_not_allowed(e):
        return render_template('errors/405.html'), 405

    @app.errorhandler(500)
    def handle_server_error(e):
        return render_template('errors/500.html'), 500

    # --------------------------------------------------------------------------
    # Diagnostic / Health Check Route
    # --------------------------------------------------------------------------
    @app.route('/health')
    def health_check():
        db_ok, db_msg = check_db_health()
        status_code = 200 if db_ok else 500
        return jsonify({
            'status': 'healthy' if db_ok else 'unhealthy',
            'database': {
                'connected': db_ok,
                'message': db_msg
            },
            'app': 'Surplus Food Distribution System',
            'phase': 'Phase 1 - Architecture & Database Foundation'
        }), status_code

    return app


if __name__ == '__main__':
    application = create_app()
    port = int(os.getenv('PORT', 5000))
    debug_mode = os.getenv('FLASK_DEBUG', 'True').lower() in ('true', '1', 't')
    print(f"\n==================================================================")
    print(f" Surplus Food Distribution System running at http://127.0.0.1:{port}")
    print(f" Health check available at http://127.0.0.1:{port}/health")
    print(f"==================================================================\n")
    application.run(host='0.0.0.0', port=port, debug=debug_mode)
