# Surplus Food Distribution System

A secure, responsive, database-driven web application connecting surplus food donors (individuals, restaurants, caterers) with verified NGOs, volunteers, and beneficiaries to prevent food waste and nourish communities.

---

## Technology Stack

- **Backend**: Python 3.12, Flask Framework (Application Factory & Blueprints)
- **Database**: MySQL 8.0+ (InnoDB, UTF8mb4, parameterized queries, transactions)
- **Frontend**: HTML5, CSS3, JavaScript (Vanilla ES6+), Bootstrap 5.3, Font Awesome 6
- **Security**: Werkzeug password hashing, parameter-safe SQL, security headers, role-based protection

---

## Project Structure

```text
surplus_food_system/
├── app.py                      # Application factory, error handlers, security headers
├── config.py                   # Environment configuration loader
├── requirements.txt            # Python dependencies
├── .env.example                # Environment variables template
├── .env                        # Local credentials (git-ignored)
├── database/
│   ├── schema.sql              # Normalized 11-table MySQL schema with foreign keys
│   ├── db.py                   # Thread-safe PyMySQL query helpers & transactions
│   └── init_db.py              # CLI utility to create database and seed default admin
├── routes/
│   ├── __init__.py
│   └── main.py                 # Public routes: /, /about, /how-it-works, /food-safety, /contact
├── static/
│   ├── css/
│   │   └── style.css           # Green & dark green theme, accessibility, card hover effects
│   ├── js/
│   │   └── main.js             # Form validation, alert auto-dismiss, food date checks
│   └── uploads/
│       ├── food_images/        # Upload directory for donor food photos
│       └── ngo_documents/      # Upload directory for NGO registration documents
├── templates/
│   ├── base.html               # Responsive master layout with navigation and alerts
│   ├── index.html              # Landing page (hero, stats, workflow, CTA)
│   ├── about.html              # Mission, objectives, architectural pillars
│   ├── how_it_works.html       # 6-step lifecycle workflow
│   ├── food_safety.html        # Food safety guidelines & validation disclaimer
│   ├── contact.html            # Contact info & inquiry form
│   └── errors/                 # Standardized error pages (400, 401, 403, 404, 405, 500)
└── tests/
    └── test_phase1.py          # Automated verification test suite
```

---

## Database Design (11 Tables)

1. `users`: System accounts (admin, donor, ngo, volunteer) with hashed passwords.
2. `donors`: Donor profiles, locations, donor types.
3. `ngos`: NGO registration numbers, document verification status.
4. `volunteers`: Vehicle type, availability status, city.
5. `beneficiaries`: Groups/individuals supported by NGOs.
6. `food_donations`: Core surplus listings, preparation and best-before datetimes, categories, status.
7. `food_requests`: NGO requests for available food parcels.
8. `pickup_assignments`: Volunteer assignments, collection logs, status tracking.
9. `distribution_records`: Community distribution records with quantity reconciliation.
10. `notifications`: In-app user notifications.
11. `audit_logs`: Immutable audit trail for all critical operations.

---

## Setup & Running Instructions

### 1. Install Dependencies
```bash
python -m pip install -r requirements.txt
```

### 2. Configure Environment
Copy `.env.example` to `.env` and configure your local MySQL credentials:
```env
SECRET_KEY=your_secret_key
FLASK_ENV=development
FLASK_DEBUG=True
PORT=5000

MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=surplus_food_db
```

### 3. Initialize Database
Run the initialization script to automatically create `surplus_food_db`, run `schema.sql`, verify all 11 tables, and seed the default administrator:
```bash
python database/init_db.py
```

Default Admin credentials:
- **Email**: `admin@surplusfood.org`
- **Password**: `Admin@12345`

### 4. Run Automated Tests
```bash
python tests/test_phase1.py
```

### 5. Launch Application
```bash
python app.py
```
Open [http://127.0.0.1:5000](http://127.0.0.1:5000) in your web browser.
Health check endpoint: [http://127.0.0.1:5000/health](http://127.0.0.1:5000/health)
