# 🌐 Production Deployment Guide — PythonAnywhere, Railway & Linux

> Comprehensive, step-by-step production deployment guide for the **Integrated Housing Services and Monitoring System (IHSMS)** on **PythonAnywhere**, **Railway Cloud**, and **Linux VPS** servers (Nginx + Gunicorn + PostgreSQL).

---

## 📋 Table of Contents

- [Live Demo Target](#-live-demo-target)
- [Prerequisites](#-prerequisites)
- [PythonAnywhere Deployment](#-pythonanywhere-deployment)
  - [Step 1: Clone the Repository](#step-1-clone-the-repository)
  - [Step 2: Create & Activate Virtual Environment](#step-2-create--activate-virtual-environment)
  - [Step 3: Install Dependencies](#step-3-install-dependencies)
  - [Step 4: Configure Environment Variables](#step-4-configure-environment-variables)
  - [Step 5: Database Setup & Migrations](#step-5-database-setup--migrations)
  - [Step 6: Collect Static Files](#step-6-collect-static-files)
  - [Step 7: Configure PythonAnywhere Web Tab & WSGI](#step-7-configure-pythonanywhere-web-tab--wsgi)
  - [Step 8: Configure Static File Mappings](#step-8-configure-static-file-mappings)
  - [Step 9: Enable HTTPS / SSL](#step-9-enable-https--ssl)
- [Railway Cloud Deployment (Primary Production)](#-railway-cloud-deployment-primary-production)
- [Linux VPS Deployment (Nginx + Gunicorn + PostgreSQL)](#-linux-vps-deployment-nginx--gunicorn--postgresql)
- [Post-Deployment Health Check](#-post-deployment-health-check)

---

## 🌐 Live Demo Target

The official live production instance is deployed at:  
**[`https://ihsms.up.railway.app/`](https://ihsms.up.railway.app/)**

### 🏗️ Production Deployment Topology

![Production Deployment Topology](docs/deployment_architecture.drawio.svg)
> ✏️ **Draw.io Source File:** [`docs/deployment_architecture.drawio`](docs/deployment_architecture.drawio) *(Editable in [Draw.io / app.diagrams.net](https://app.diagrams.net/))*

---

## ✅ Prerequisites

Before deploying, ensure you have:
- A **PythonAnywhere Account** (Hacker/Custom plan recommended for outbound APIs like Semaphore and Google OAuth) or **Railway Account**.
- **Python 3.12+** selected as the default application runtime.
- A **Google Cloud Console OAuth 2.0 Client ID & Secret** for staff portal single sign-on.
- A **Semaphore API Key** for automated SMS notices to housing applicants.
- A **PostgreSQL** database (Cloud-managed or PythonAnywhere MySQL/Postgres).

---

## ☁️ PythonAnywhere Deployment

![PythonAnywhere Deployment Pipeline](docs/pythonanywhere_pipeline.drawio.svg)
> ✏️ **Draw.io Source File:** [`docs/pythonanywhere_pipeline.drawio`](docs/pythonanywhere_pipeline.drawio) *(Editable in [Draw.io / app.diagrams.net](https://app.diagrams.net/))*

### Step 1: Clone the Repository

Log into PythonAnywhere, open a **Bash Console**, and clone the project into your home directory:

```bash
cd ~
git clone https://github.com/TheUnshackled1/capstone-talisay_housing.git system
cd system
```

---

### Step 2: Create & Activate Virtual Environment

Create a dedicated virtual environment using Python 3.12:

```bash
python3.12 -m venv env
source env/bin/activate
```

---

### Step 3: Install Dependencies

Upgrade `pip` and install all required packages:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

This installs Django 6.0.6, `pymupdf` (fitz), `django-allauth`, `whitenoise`, `psycopg[binary] 3.3.4`, `dj-database-url`, `requests`, and related IHSMS dependencies.

---

### Step 4: Configure Environment Variables

Create a `.env` file in the project root (`~/system/.env`):

```bash
nano ~/system/.env
```

Add the following production configuration:

```env
DEBUG=False
SECRET_KEY=your-secure-random-production-secret-key-here
ALLOWED_HOSTS=yourusername.pythonanywhere.com,localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=https://yourusername.pythonanywhere.com

# Database (PostgreSQL URL or leave blank for local SQLite)
DATABASE_URL=postgresql://user:password@host:5432/dbname

# SMS Integration (Semaphore)
SMS_ENABLED=True
SMS_SERVICE=semaphore
SEMAPHORE_API_KEY=your_semaphore_api_key_here
SEMAPHORE_SENDER_NAME=THAOFFICE

# Google OAuth (Staff Portal)
GOOGLE_OAUTH_CLIENT_ID=your_google_client_id.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=your_google_client_secret
GOOGLE_OAUTH_ALLOWED_DOMAINS=gmail.com,talisayhousing.gov.ph,chmsu.edu.ph
GOOGLE_PICKER_API_KEY=your_google_picker_api_key
```

---

### Step 5: Database Setup & Migrations

Run database migrations, seed initial Talisay City housing requirements, and create an admin superuser:

```bash
python manage.py migrate
python manage.py createcachetable
python seed_requirements.py
python manage.py createsuperuser
```

Synchronize Google OAuth site credentials:
```bash
python manage.py setup_google_oauth --site-domain "yourusername.pythonanywhere.com" --site-name "IHSMS"
```

---

### Step 6: Collect Static Files

Gather all static assets (CSS, JS, images, forms, and admin assets) into the `staticfiles` directory:

```bash
python manage.py collectstatic --noinput
```

---

### Step 7: Configure PythonAnywhere Web Tab & WSGI

1. Navigate to the **Web Tab** in your PythonAnywhere dashboard.
2. Select **Manual Configuration** and choose **Python 3.12**.
3. Set **Virtualenv Path**:
   ```
   /home/yourusername/system/env
   ```
4. Set **Source Code Path**:
   ```
   /home/yourusername/system
   ```
5. Click on the **WSGI Configuration File** link (`/var/www/yourusername_pythonanywhere_com_wsgi.py`) and replace its content with:

```python
import os
import sys

# Path to your project directory
path = '/home/yourusername/system'
if path not in sys.path:
    sys.path.append(path)

# Load environment variables from .env
from dotenv import load_dotenv
load_dotenv(os.path.join(path, '.env'))

os.environ['DJANGO_SETTINGS_MODULE'] = 'talisay_housing.settings'

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

*(Replace `yourusername` with your actual PythonAnywhere username).*

---

### Step 8: Configure Static File Mappings

In the **Web Tab** under **Static Files**, configure the URL-to-directory mappings:

| URL | Directory Path |
|---|---|
| `/static/` | `/home/yourusername/system/static/` |
| `/staticfiles/` | `/home/yourusername/system/staticfiles/` |
| `/media/` | `/home/yourusername/system/media/` |

---

### Step 9: Enable HTTPS / SSL

1. In the **Web Tab**, scroll down to the **Security** section.
2. Turn ON **"Force HTTPS"**.
3. Click the green **"Reload yourusername.pythonanywhere.com"** button at the top of the Web Tab.

---

## 🚂 Railway Cloud Deployment (Primary Production)

The live production instance is hosted on **Railway** utilizing automated Nixpacks containerization.

### 1. Build & Deploy Configuration (`railway.toml`)
The repository includes a pre-configured `railway.toml`:
```toml
[build]
builder = "nixpacks"
buildCommand = "python manage.py collectstatic --noinput"

[deploy]
startCommand = "bash scripts/start.sh"
healthcheckPath = "/"
healthcheckTimeout = 300
restartPolicyType = "on_failure"
```

### 2. Startup Script (`scripts/start.sh`)
Railway automatically invokes `scripts/start.sh` on container boot:
- Applies pending database migrations (`migrate --noinput --skip-checks`).
- Generates the database cache table (`createcachetable`).
- Syncs the Google OAuth domain (`setup_google_oauth --site-domain "ihsms.up.railway.app"`).
- Drops expired sessions (`clearsessions`).
- Launches Gunicorn with 2 workers and 4 threads (`gunicorn talisay_housing.wsgi:application --timeout 180`).

### 3. Railway Environment Variables
Set the following variables in the Railway project dashboard:
- `DEBUG` = `False`
- `SECRET_KEY` = `[Production Secret Key]`
- `ALLOWED_HOSTS` = `ihsms.up.railway.app,.railway.app,localhost`
- `CSRF_TRUSTED_ORIGINS` = `https://ihsms.up.railway.app,https://*.railway.app`
- `DATABASE_URL` = `[Railway PostgreSQL Public/Private Connection URL]`
- `GOOGLE_OAUTH_CLIENT_ID` = `[Google OAuth Client ID]`
- `GOOGLE_OAUTH_CLIENT_SECRET` = `[Google OAuth Client Secret]`
- `SEMAPHORE_API_KEY` = `[Semaphore API Key]`

---

## 🐧 Linux VPS Deployment (Nginx + Gunicorn + PostgreSQL)

For production deployments on Ubuntu/Debian Linux VPS instances:

### 1. Install System Packages
```bash
sudo apt update && sudo apt install -y python3.12 python3.12-venv postgresql postgresql-contrib nginx curl git
```

### 2. Configure PostgreSQL
```sql
sudo -u postgres psql
CREATE DATABASE talisay_housing_db;
CREATE USER talisay_user WITH PASSWORD 'secure_production_password';
GRANT ALL PRIVILEGES ON DATABASE talisay_housing_db TO talisay_user;
\q
```

### 3. Gunicorn Systemd Service (`/etc/systemd/system/ihsms.service`)
```ini
[Unit]
Description=Gunicorn daemon for Talisay Housing Authority (IHSMS)
After=network.target

[Service]
User=ubuntu
Group=www-data
WorkingDirectory=/var/www/system
EnvironmentFile=/var/www/system/.env
ExecStart=/var/www/system/env/bin/gunicorn \
          --workers 3 \
          --threads 2 \
          --timeout 180 \
          --bind unix:/var/www/system/ihsms.sock \
          talisay_housing.wsgi:application

[Install]
WantedBy=multi-user.target
```

Enable and start the service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now ihsms
```

### 4. Nginx Server Block (`/etc/nginx/sites-available/ihsms`)
```nginx
server {
    listen 80;
    server_name yourdomain.gov.ph;

    location = /favicon.ico { access_log off; log_not_found off; }

    location /static/ {
        alias /var/www/system/staticfiles/;
    }

    location /media/ {
        alias /var/www/system/media/;
    }

    location / {
        include proxy_params;
        proxy_pass http://unix:/var/www/system/ihsms.sock;
    }
}
```

Enable site and install SSL certificate:
```bash
sudo ln -s /etc/nginx/sites-available/ihsms /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d yourdomain.gov.ph
```

---

## 🧪 Post-Deployment Health Check

After reloading the application, verify the following:

1. **Dashboard & Views**: Visit your domain — verify that Tailwind CSS styling, glassmorphism tokens, and icons render correctly.
2. **Staff Google OAuth**: Test logging in via `/login/google/?role=second_member` and `/login/google/?role=caretaker` (or `field`) to confirm callback domain matching.
3. **PDF Generation (PyMuPDF)**: Click **Open PDF** on an applicant in the Form Generation queue to verify overlay text and N/A coordinates render cleanly on `APPLICATION-FORM-THA.pdf`.
4. **SMS Delivery**: Trigger an applicant status update or notice to confirm live Semaphore SMS messages deliver to beneficiary mobile numbers.
5. **System Health**: Run `python manage.py check` to verify zero system issues or warnings.
