# 📖 Setup & Configuration Instructions

> Detailed step-by-step guide for setting up the project on **Windows** with **Python 3.12+**, including database configuration, environment setup, Google OAuth, Semaphore SMS, and key portal endpoints.

---

## 📋 Table of Contents

- [Prerequisites](#-prerequisites)
- [1. Clone the Repository](#1-clone-the-repository)
- [2. Set Up a Virtual Environment](#2-set-up-a-virtual-environment)
- [3. Install Dependencies](#3-install-dependencies)
- [4. Configure the Database](#4-configure-the-database)
  - [Option A — PostgreSQL (Recommended & Production)](#option-a--postgresql-recommended--production)
  - [Option B — SQLite (Quick Local Evaluation)](#option-b--sqlite-quick-local-evaluation)
- [5. External Services & Security Configuration](#5-external-services--security-configuration)
  - [Google OAuth 2.0 & Drive Picker](#google-oauth-20--drive-picker)
  - [Semaphore SMS Gateway](#semaphore-sms-gateway)
- [6. Run Migrations & Seed Reference Data](#6-run-migrations--seed-reference-data)
- [7. Create a Superuser & Sync OAuth](#7-create-a-superuser--sync-oauth)
- [8. Start the Development Server](#8-start-the-development-server)
- [9. Key Portal & Authentication Endpoints](#9-key-portal--authentication-endpoints)
- [Troubleshooting](#-troubleshooting)
- [Running in Production](#-running-in-production)

---

### 🏗️ Local Development Setup Pipeline

![Local Development Setup Pipeline](docs/local_setup_pipeline.drawio.svg)
> ✏️ **Draw.io Source File:** [`docs/local_setup_pipeline.drawio`](docs/local_setup_pipeline.drawio) *(Editable in [Draw.io / app.diagrams.net](https://app.diagrams.net/))*

---

## ✅ Prerequisites

Make sure the following tools are installed on your Windows machine before you begin:

| Tool | Minimum Version | Download Link |
|---|---|---|
| **Python** | 3.12+ | [python.org/downloads](https://www.python.org/downloads/) |
| **pip** | Latest | Bundled with Python installer |
| **Git** | Any | [git-scm.com/download/win](https://git-scm.com/download/win) |
| **Node.js & npm** | 18+ (LTS) | [nodejs.org/en/download](https://nodejs.org/en/download/) *(Required for Tailwind CSS 4)* |
| **PostgreSQL** *(recommended)* | 14+ | [postgresql.org/download/windows](https://www.postgresql.org/download/windows/) |

> 💡 During Python installation on Windows, ensure you check **"Add Python to PATH"** so `python` and `pip` are accessible directly from PowerShell.

---

## 1. Clone the Repository

Open **PowerShell** and run:

```powershell
git clone https://github.com/TheUnshackled1/capstone-talisay_housing.git capstone
cd capstone
```

---

## 2. Set Up a Virtual Environment

It is strongly recommended to use a virtual environment to isolate project dependencies:

```powershell
# Create the virtual environment
python -m venv venv

# Activate it in PowerShell
.\venv\Scripts\Activate
```

You should see `(venv)` prepended to your PowerShell prompt, confirming activation.

> ⚠️ If you encounter a script execution policy error on Windows, run this command once:
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```

To deactivate the virtual environment at any time:
```powershell
deactivate
```

---

## 3. Install Dependencies

With your virtual environment active, install both the backend Python packages and frontend Tailwind tooling:

### Step 3.1 — Install Python Packages
```powershell
pip install -r requirements.txt
```

This installs:
- **Django 6.0.6** (Core Web Framework)
- **PyMuPDF / fitz** (Application form PDF generation & 2x2 photo overlay)
- **django-allauth** (Google OAuth 2.0 authentication engine)
- **whitenoise** (High-efficiency static asset streaming)
- **psycopg[binary] 3.3.4 & dj-database-url** (PostgreSQL adapter — psycopg 3 for Django 6 — & connection parsing)
- **requests & python-dotenv** (API calls & environment variable loading)

### Step 3.2 — Install Frontend Assets (Tailwind CSS 4)
```powershell
npm install
```

> 💡 If you encounter pip errors, ensure pip is updated:
> ```powershell
> python -m pip install --upgrade pip
> ```

---

## 4. Configure the Database

Create your local `.env` configuration file from the provided template:

```powershell
copy .env.example .env
```

### Option A — PostgreSQL *(Recommended & Production)*

PostgreSQL is the official database engine for IHSMS in production.

**Step 1 — Create the database in psql or pgAdmin:**

```sql
CREATE DATABASE talisay_housing_db;
CREATE USER postgres WITH PASSWORD '1234';
GRANT ALL PRIVILEGES ON DATABASE talisay_housing_db TO postgres;
```

**Step 2 — Configure `.env`:**

```env
DATABASE_URL=postgresql://postgres:1234@localhost:5432/talisay_housing_db
```

---

### Option B — SQLite *(Quick Local Evaluation)*

If you wish to run a quick test without installing PostgreSQL, you can use SQLite:

In `talisay_housing/settings.py` (or by omitting `DATABASE_URL` in `.env`), set `DATABASES` to:

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}
```

---

## 5. External Services & Security Configuration

Edit `.env` to configure application security, Google OAuth, and SMS delivery:

```env
DEBUG=True
SECRET_KEY=local-dev-secret-key-change-in-production
ALLOWED_HOSTS=localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000
```

### Google OAuth 2.0 & Drive Picker

Staff sign-in uses Google Cloud credentials ([console.cloud.google.com](https://console.cloud.google.com/apis/credentials)):

```env
GOOGLE_OAUTH_CLIENT_ID=your_client_id.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=your_client_secret
GOOGLE_OAUTH_ALLOWED_DOMAINS=gmail.com,talisayhousing.gov.ph,chmsu.edu.ph
GOOGLE_PICKER_API_KEY=your_picker_api_key
```

> 💡 In the Google Cloud Console, add `http://localhost:8000/auth/google/login/callback/` to **Authorized Redirect URIs**.

### Semaphore SMS Gateway

IHSMS dispatches automated SMS notices to housing beneficiaries:

```env
SMS_ENABLED=True
# Use 'console' for free local terminal testing; switch to 'semaphore' for live SMS sends
SMS_SERVICE=console
SEMAPHORE_API_KEY=your_semaphore_api_key_here
SEMAPHORE_SENDER_NAME=THAOFFICE
```

---

## 6. Run Migrations & Seed Reference Data

Apply all database migrations and populate default Talisay City housing data:

```powershell
# 1. Run core schema migrations
python manage.py migrate

# 2. Seed 27 Talisay City barangays & required housing documents
python seed_requirements.py

# 3. Create database cache table for session storage
python manage.py createcachetable
```

Expected output: All migrations return `OK`, and `seed_requirements.py` reports default barangays and document rules created.

---

## 7. Create a Superuser & Sync OAuth

### 7.1 Create Admin User
```powershell
python manage.py createsuperuser
```
Enter your desired username, email address, and administrative password.

### 7.2 Synchronize Google OAuth Site Domain
Ensure the `django.contrib.sites` table matches your local host:
```powershell
python manage.py setup_google_oauth --site-domain "localhost:8000" --site-name "IHSMS"
```

---

## 8. Start the Development Server

Start the Django backend:

```powershell
python manage.py runserver
```

In a separate PowerShell terminal, run the Tailwind CSS compiler watcher:

```powershell
npm run watch:tailwind
```

The application is now accessible at:

| Portal | Local URL | Description |
|---|---|---|
| **Public Landing Page** | [http://127.0.0.1:8000/](http://127.0.0.1:8000/) | Public homepage, live statistics, and housing requirements |
| **Public Applicant Status Tracker** | [http://127.0.0.1:8000/status/<ref>/](http://127.0.0.1:8000/status/APP-20260827-1234/) | Unauthenticated status tracker (SMS deep-link for applicants) |
| **Staff & Member Login** | [http://127.0.0.1:8000/login/](http://127.0.0.1:8000/login/) | Role-gated portal login with Google OAuth integration |
| **Second Member Portal** | [http://127.0.0.1:8000/dashboard/second-member/](http://127.0.0.1:8000/dashboard/second-member/) | Intake overview, Module 1 & 2 queues, and executive analytics |
| **Fourth Member Portal** | [http://127.0.0.1:8000/dashboard/fourth-member/](http://127.0.0.1:8000/dashboard/fourth-member/) | Application pipeline, lot awarding queue, and analytics |
| **Caretaker Monitoring Portal** | [http://127.0.0.1:8000/dashboard/caretaker/](http://127.0.0.1:8000/dashboard/caretaker/) | Caretaker monitoring tasks, unit inspections, and reports |
| **Field Staff Portal** | [http://127.0.0.1:8000/dashboard/field/](http://127.0.0.1:8000/dashboard/field/) | Field verification, CDRRMO hazard certification, and case desk |
| **Django Admin** | [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/) | Complete system models, Jazzmin admin, and user management |

---

## 9. Key Portal & Authentication Endpoints

| Endpoint | Method | Role / Guard | Description |
|---|---|---|---|
| `/login/google/?role=second_member` | `GET` | Staff / Google Auth | Initiates Google OAuth flow tagged for Second Member portal access. |
| `/login/google/?role=fourth_member` | `GET` | Staff / Google Auth | Initiates Google OAuth flow tagged for Fourth Member portal access. |
| `/login/google/?role=caretaker` | `GET` | Staff / Google Auth | Initiates Google OAuth flow tagged for Caretaker portal access. |
| `/login/google/?role=field` | `GET` | Staff / Google Auth | Initiates Google OAuth flow tagged for Field Staff portal access. |
| `/applications/staff/<position>/application-form-pdf/<uuid>/` | `GET` | Staff (`@login_required`) | Generates filled 2-page `APPLICATION-FORM-THA.pdf` using PyMuPDF. |
| `/housing-units/<position>/` | `GET` | Staff / Admin | Interactive relocation site block & lot subdivision map with unit statuses. |
| `/cases/<position>/create/` | `POST` | Staff / Mediator | Logs community disputes/violations with automated timeline tracking. |
| `/documents/<position>/management/` | `GET` | Staff / Admin | Central digital vault with Google Drive Picker & scanned file uploads. |

---

## 🔧 Troubleshooting

### `'python' is not recognized as an internal or external command`
Python is not configured in your system PATH. Re-run the Python installer, select **Modify**, and check **"Add Python to PATH"**.

---

### `ModuleNotFoundError: No module named 'django'`
Your virtual environment is not active. Activate it via:
```powershell
.\venv\Scripts\Activate
```

---

### Script execution policy error on `Activate`
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

---

### `DoesNotExist at /login/google/` or SocialApp Matching Query Does Not Exist
The Google OAuth application record in the database does not match the active site domain. Run:
```powershell
python manage.py setup_google_oauth --site-domain "localhost:8000" --site-name "IHSMS"
```

---

### Tailwind CSS styling not updating
Compile the Tailwind bundle explicitly:
```powershell
npm run build:tailwind
```
Or run the watcher in a background terminal:
```powershell
npm run watch:tailwind
```

---

### `django.db.utils.OperationalError: connection to server on socket failed`
PostgreSQL service is not running on Windows. Open `services.msc` and ensure the **postgresql-x64-XX** service is Started, or switch to SQLite for local development.

---

## 🌐 Running in Production

For deploying IHSMS to cloud environments:
- See the complete [Production Deployment Guide (DEPLOYMENT.md)](DEPLOYMENT.md) for Railway, PythonAnywhere, and Linux VPS instructions.
- Ensure `DEBUG=False` and secure `SECRET_KEY` are provided.
- Run `python manage.py collectstatic --noinput`.
- Enforce HTTPS and verify `CSRF_TRUSTED_ORIGINS`.

---

## 🗂️ Quick Reference

```powershell
# Complete Windows bootstrap from scratch (PowerShell)
git clone https://github.com/TheUnshackled1/capstone-talisay_housing.git capstone
cd capstone
python -m venv venv
.\venv\Scripts\Activate
pip install -r requirements.txt
npm install
copy .env.example .env
python manage.py migrate
python seed_requirements.py
python manage.py createcachetable
python manage.py setup_google_oauth --site-domain "localhost:8000" --site-name "IHSMS"
python manage.py createsuperuser
python manage.py runserver
```

---

*For contributing guidelines, see [CONTRIBUTING.md](CONTRIBUTING.md). For security policies, see [SECURITY.md](SECURITY.md).*
