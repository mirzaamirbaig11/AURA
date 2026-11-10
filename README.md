# AURA Clothing Store

A complete, fully functional premium fashion e-commerce website built with Python, Flask, and PostgreSQL.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Database Setup](#database-setup)
5. [Running the Application](#running-the-application)
6. [Testing](#testing)
7. [Project Structure](#project-structure)
8. [Key Features](#key-features)

## Prerequisites

### 1. Python Installation

Install Python 3.10+ from [python.org](https://www.python.org/downloads/).

After installation, open PowerShell and verify:
```powershell
python --version
```

Ensure pip is up to date:
```powershell
python -m pip install --upgrade pip
```

### 2. PostgreSQL Installation

Download and install PostgreSQL from [postgresql.org](https://www.postgresql.org/download/windows/).

During installation, note the password you set for the `postgres` user.

Verify installation:
```powershell
psql --version
```

## Installation

### 1. Clone or Download the Project

Navigate to your desired location and download the AURA project.

### 2. Create Virtual Environment

```powershell
cd C:\Users\mirza\OneDrive\เอกสาร\AURA
python -m venv .venv
```

### 3. Activate Virtual Environment

```powershell
.\.venv\Scripts\Activate.ps1
```

If you encounter execution policy errors, run:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### 4. Install Dependencies

```powershell
pip install -r requirements.txt
```

## Configuration

### 1. Set Environment Variables

Create a `.env` file in the project root:

```powershell
Copy-Item .env.example .env
```

Edit `.env` and update the values:

```
SECRET_KEY=your-secret-key-here
DATABASE_URL=postgresql://postgres:your-password@localhost:5432/aura_db
ADMIN_EMAIL=admin@aura.com
ADMIN_PASSWORD=your-secure-admin-password
```

### 2. Payment Mode

The application supports two payment modes:

**Cash on Delivery (COD - Default)**
- Set `ENABLE_ONLINE_PAYMENT=false` in `.env`
- No Stripe keys required
- Orders are confirmed immediately upon checkout

**Online Payments (Stripe)**
- Set `ENABLE_ONLINE_PAYMENT=true` in `.env`
- Configure Stripe keys:
  - `STRIPE_PUBLISHABLE_KEY`
  - `STRIPE_SECRET_KEY`
  - `STRIPE_WEBHOOK_SECRET`
- Orders require payment completion before confirmation

### 3. Store Logo

Place the AURA logo at:
```
frontend/static/images/logo.png
```

The logo should be:
- Red gradient background
- Black and silver infinity symbol
- White "AURA" text
- Square 1:1 aspect ratio

### 4. Update Store Settings

Store settings (WhatsApp, Instagram, Google Maps) are configured in `.env`:
```
WHATSAPP_NUMBER=8527756728
INSTAGRAM_URL=https://instagram.com/aura_clothing
GOOGLE_MAPS_URL=https://maps.app.goo.gl/pRC9ZQcwyDGbPo5Q9
```

## Database Setup

### 1. Create PostgreSQL Database

Open Command Prompt and run:
```cmd
psql -U postgres
```

In psql, run:
```sql
CREATE DATABASE aura_db;
CREATE USER aura_user WITH PASSWORD 'your-password';
GRANT ALL PRIVILEGES ON DATABASE aura_db TO aura_user;
\q
```

Update `.env` with correct credentials:
```
DATABASE_URL=postgresql://aura_user:your-password@localhost:5432/aura_db
```

### 2. Initialize Database

```powershell
cd backend
flask --app run.py db init
flask --app run.py db migrate -m "Initial migration"
flask --app run.py db upgrade
```

### 3. Create Admin User

Run the following Python script:

```powershell
python create_admin.py
```

Or use the interactive script:
```powershell
python -c "
from app import create_app, db
from app.models import Admin
app = create_app()
with app.app_context():
    admin = Admin(email='admin@aura.com', name='Admin User')
    admin.set_password('your-password')
    db.session.add(admin)
    db.session.commit()
    print('Admin user created!')
"
```

## Running the Application

### Development Server

```powershell
cd C:\Users\mirza\OneDrive\เอกสาร\AURA\backend
flask --app run.py run
```

The application will be available at: http://localhost:5000

### Storefront
- Home: http://localhost:5000/
- Shop: http://localhost:5000/shop
- Admin: http://localhost:5000/admin/login

## Testing

### Run Tests

```powershell
cd C:\Users\mirza\OneDrive\เอกสาร\AURA\backend
python -m pytest tests/test_aura.py -v
```

### Test Coverage

Tests cover:
- Application startup
- Database connection
- Admin authentication
- Customer registration and login
- Product management
- Cart operations
- Checkout flow
- Order creation

## Project Structure

```
aura-clothing-store/
│
├── backend/
│   ├── app/
│   │   ├── __init__.py          # Application factory
│   │   ├── config.py            # Configuration
│   │   ├── extensions.py      # Flask extensions
│   │   ├── models/            # Database models
│   │   │   ├── admin.py
│   │   │   ├── customer.py
│   │   │   ├── product.py
│   │   │   ├── category.py
│   │   │   ├── order.py
│   │   │   └── ... (all models)
│   │   ├── routes/            # URL routes
│   │   │   ├── frontend.py    # Customer-facing routes
│   │   │   ├── admin.py       # Admin dashboard routes
│   │   │   ├── auth.py        # Authentication routes
│   │   │   └── api.py         # REST API routes
│   │   ├── templates/       # Jinja2 templates
│   │   │   ├── base.html
│   │   │   ├── frontend/
│   │   │   └── admin/
│   │   └── utils/           # Utilities and helpers
│   │
│   ├── migrations/          # Alembic migrations
│   ├── tests/               # Automated tests
│   ├── requirements.txt
│   └── run.py              # Application entry point
│
├── frontend/
│   ├── static/
│   │   ├── css/
│   │   │   ├── style.css     # Frontend styles
│   │   │   └── admin.css     # Admin dashboard styles
│   │   ├── js/
│   │   │   ├── main.js       # Frontend scripts
│   │   │   └── admin.js      # Admin scripts
│   │   ├── images/          # Static images
│   │   └── uploads/         # Product/category uploads
│   │
├── docs/                  # Documentation
├── .env.example           # Environment template
├── .gitignore
└── README.md

```

## Key Features

### Customer Website
- ✅ Premium responsive design
- ✅ Product catalog with search and filters
- ✅ Shopping cart with quantity management
- ✅ Checkout with address selection
- ✅ Order confirmation and tracking
- ✅ Wishlist functionality
- ✅ Newsletter subscription

### Admin Dashboard
- ✅ Dashboard with sales statistics
- ✅ Product management (add/edit/delete)
- ✅ Category management
- ✅ Order management with status updates
- ✅ Inventory management
- ✅ Customer management
- ✅ Settings configuration

### Security
- ✅ Password hashing with Werkzeug
- ✅ CSRF protection
- ✅ Role-based access control
- ✅ Rate limiting
- ✅ Input validation
- ✅ Secure session configuration

### Database Architecture
- ✅ PostgreSQL with SQLAlchemy ORM
- ✅ Normalized database schema (18+ tables)
- ✅ Alembic migrations
- ✅ Foreign key constraints
- ✅ Database indexes for performance

## Default Categories

The following 8 categories are pre-configured:
1. Jersey
2. Jeans
3. T-Shirts
4. Shirts
5. Hoodies
6. Cargoes
7. Trousers
8. Jackets

## Brand Information

- **WhatsApp**: https://wa.me/918527756728
- **Instagram**: https://instagram.com/aura_clothing
- **Google Maps**: https://maps.app.goo.gl/pRC9ZQcwyDGbPo5Q9

## Deployment

For production deployment:
1. Set `FLASK_ENV=production`
2. Set `SECRET_KEY` to a secure random value
3. Set `SESSION_COOKIE_SECURE=True`
4. Use a production WSGI server (gunicorn, uWSGI)
5. Configure HTTPS
6. Set up a production database

Example with gunicorn:
```powershell
pip install gunicorn
gunicorn "backend.run:app" --bind 0.0.0.0:8000 --workers 4
```

## Troubleshooting

### "Error: Could not connect to PostgreSQL"
- Ensure PostgreSQL is running
- Check your DATABASE_URL credentials

### "ModuleNotFoundError: No module named 'app'"
- Ensure you're in the `backend` directory
- The application expects to find the `app` package in the current directory

### "403 Forbidden on login"
- Verify admin credentials in database
- Check admin account is active

### "Database migration failed"
- Ensure all models are imported in `models/__init__.py`
- Check for circular imports

### "Stripe payment issues"
- Ensure `ENABLE_ONLINE_PAYMENT=true` in `.env`
- Verify `STRIPE_PUBLISHABLE_KEY` and `STRIPE_SECRET_KEY` are set
- For webhooks, configure `STRIPE_WEBHOOK_SECRET`#   A U R A  
 