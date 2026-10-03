"""
Main public routes for the Surplus Food Distribution System.
Provides public landing page, about, how it works, food safety guidelines, and contact page.
"""

from flask import Blueprint, render_template, request, flash, redirect, url_for
from database.db import execute_query, execute_insert

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    """Landing page displaying hero section, impact metrics, workflow, and safety notice."""
    stats = {
        'total_donations': 0,
        'completed_donations': 0,
        'total_ngos': 0,
        'total_volunteers': 0,
        'meals_served': 0,
        'is_demo_data': False
    }

    try:
        donations_res = execute_query(
            "SELECT COUNT(*) AS total, SUM(CASE WHEN status = 'Completed' THEN 1 ELSE 0 END) AS completed FROM food_donations",
            fetchone=True
        )
        if donations_res:
            stats['total_donations'] = donations_res['total'] or 0
            stats['completed_donations'] = donations_res['completed'] or 0

        ngos_res = execute_query(
            "SELECT COUNT(*) AS total FROM ngos WHERE verification_status = 'verified'",
            fetchone=True
        )
        if ngos_res:
            stats['total_ngos'] = ngos_res['total'] or 0

        volunteers_res = execute_query(
            "SELECT COUNT(*) AS total FROM volunteers WHERE availability_status != 'inactive'",
            fetchone=True
        )
        if volunteers_res:
            stats['total_volunteers'] = volunteers_res['total'] or 0

        dist_res = execute_query(
            "SELECT COALESCE(SUM(servings_distributed), 0) AS total_servings FROM distribution_records",
            fetchone=True
        )
        if dist_res:
            stats['meals_served'] = int(dist_res['total_servings'] or 0)

        # If zero records exist yet in dev, provide clearly marked demonstration benchmark metrics
        if stats['total_donations'] == 0:
            stats['demo_donations'] = "1,250+"
            stats['demo_meals'] = "15,000+"
            stats['demo_ngos'] = "48"
            stats['demo_volunteers'] = "120"
            stats['is_demo_data'] = True

    except Exception:
        # Fallback in case of database connectivity issues
        stats['is_demo_data'] = True
        stats['demo_donations'] = "1,250+"
        stats['demo_meals'] = "15,000+"
        stats['demo_ngos'] = "48"
        stats['demo_volunteers'] = "120"

    return render_template('index.html', stats=stats)


@main_bp.route('/about')
def about():
    """About page outlining mission, redistribution objectives, and societal impact."""
    return render_template('about.html')


@main_bp.route('/how-it-works')
def how_it_works():
    """Step-by-step interactive workflow explainer from donor to beneficiary."""
    return render_template('how_it_works.html')


@main_bp.route('/food-safety')
def food_safety():
    """Food safety guidelines, acceptable criteria, and mandatory safety disclaimer."""
    return render_template('food_safety.html')


@main_bp.route('/contact', methods=['GET', 'POST'])
def contact():
    """Contact page with system information and contact form."""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        subject = request.form.get('subject', '').strip()
        message = request.form.get('message', '').strip()

        if not name or not email or not subject or not message:
            flash('Please fill in all required fields.', 'danger')
            return render_template('contact.html', name=name, email=email, subject=subject, message=message)

        execute_insert("""
            INSERT INTO contact_inquiries (name, email, subject, message)
            VALUES (%s, %s, %s, %s)
        """, (name, email, subject, message))
        flash('Thank you for reaching out! Your message has been received and our team will get back to you shortly.', 'success')
        return redirect(url_for('main.contact'))

    return render_template('contact.html')
