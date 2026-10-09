# 🏠 IHSMS — Integrated Housing Services and Monitoring System

> **A full-stack Django web application built for the Talisay City Housing Authority (THA). Designed to manage the complete lifecycle of socialized housing applicants — from initial walk-in registration, multi-layer eligibility screening, document vault management, application form generation, lot awarding, to housing unit monitoring and community case management.**

🌐 **Live Demo:** [ihsms.up.railway.app](https://ihsms.up.railway.app/)

📄 **Quick File Links:**
[![ERD Diagram](https://img.shields.io/badge/🗂️_Entity_Relationship_Diagram-docs/ERD.md-2563eb?style=flat-square)](docs/ERD.md)
[![User Guide](https://img.shields.io/badge/📖_Staff_User_Guide-notes/user__guide.md-6366f1?style=flat-square)](notes/user_guide.md)
[![Dashboard Analytics](https://img.shields.io/badge/📊_Analytics_Explainer-notes/dashboard__analytics__explainer.md-0891b2?style=flat-square)](notes/dashboard_analytics_explainer.md)
[![Environment Variables](https://img.shields.io/badge/⚙️_Environment_Variables-.env.example-d97706?style=flat-square)](.env.example)
[![Requirements](https://img.shields.io/badge/📦_Dependencies-requirements.txt-16a34a?style=flat-square)](requirements.txt)
[![ERD Source](https://img.shields.io/badge/🖊️_ERD_Draw.io-docs/ERD.drawio-8b5cf6?style=flat-square)](docs/ERD.drawio)
[![Code of Conduct](https://img.shields.io/badge/📜_Code_of_Conduct-CODE__OF__CONDUCT.md-f43f5e?style=flat-square)](CODE_OF_CONDUCT.md)

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-6.0.6-092E20?logo=django&logoColor=white)](https://www.djangoproject.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Primary_DB-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![TailwindCSS](https://img.shields.io/badge/Tailwind_CSS-4.2.4_(Compiled)-06B6D4?logo=tailwindcss&logoColor=white)](https://tailwindcss.com/)
[![Railway](https://img.shields.io/badge/Deployed_on-Railway-0B0D0E?logo=railway&logoColor=white)](https://railway.app/)
[![License](https://img.shields.io/badge/License-ISC-22c55e?logo=opensourceinitiative&logoColor=white)](package.json)

---

## 📋 Table of Contents

### 📌 System Overview & Core Guides
- 🔍 [Overview](#-overview)
- 🎯 [Objectives](#-objectives)
- ✨ [Core Features](#-core-features)
- 🏗️ [System Architecture](#-system-architecture)
- 🛠️ [Tech Stack](#-tech-stack)
- 🚀 [Setup & Installation](#-setup--installation)
- 🔗 [URL & API Endpoints](#-url--api-endpoints)
- 🛡️ [Configuration & Security](#-configuration--security)
- 📁 [Project Structure](#-project-structure)
- 🧑‍💻 [About](#-about)

### 📄 Detailed Documentation Files
- 🗂️ [Entity Relationship Diagram (`docs/ERD.md`)](docs/ERD.md)
- 📖 [Staff User Guide (`notes/user_guide.md`)](notes/user_guide.md)
- 📊 [Dashboard Analytics Explainer (`notes/dashboard_analytics_explainer.md`)](notes/dashboard_analytics_explainer.md)
- ⚙️ [Environment Variable Reference (`.env.example`)](.env.example)

---

## 🔍 Overview

Managing housing applicants across multiple intake stages with physical folders and spreadsheets is slow, error-prone, and impossible to audit. The **Integrated Housing Services and Monitoring System (IHSMS)** is a full-stack Django web application that digitizes the entire housing applicant lifecycle for the **Talisay City Housing Authority** — from a person walking in off the street to having their lot formally awarded and their occupancy monitored.

The system provides five core modules:

1. **Module 1 — Intake & Registration** — Walk-in applicant registration with multi-layer eligibility screening, CDRRMO hazard verification, duplicate detection, and automatic SMS notifications.
2. **Module 2 — Application & Evaluation** — Deep eligibility evaluation with field verification workflows, government form PDF generation, and lot awarding queue management.
3. **Module 3 — Document Vault** — Centralized digital archive for scanned applicant documents (PDF/image), requirement tracking per applicant, and Google Drive integration for upload.
4. **Module 4 — Housing Unit Monitoring** — Interactive block/lot map of relocation sites, occupancy status tracking, caretaker dashboard, compliance notice issuance, and 30/60/90-day monitoring task workflows.
5. **Module 5 — Case Management** — Community complaint and violation tracking with case timelines, evidence uploads, field settlement recording, and role-separated desk feeds.

The result: a unified, role-gated platform that gives every THA staff position — Second Member, Fourth Member, Ronda, and Field — exactly the tools they need, and a public applicant status tracker that residents can check via SMS deep-link.

---

## 🎯 Objectives

| Goal | Description |
|---|---|
| 📋 **Digitize Registration** | Replace paper-based walk-in registration with a searchable, auditable applicant database. |
| 🔍 **Enforce Eligibility Rules** | Apply multi-layer eligibility criteria (income, residency, property ownership, blacklist, CDRRMO hazard) automatically. |
| 📁 **Centralize Documents** | Replace physical document folders with a digital vault — scan, upload, track, and verify all requirements in one place. |
| 📄 **Automate Form Generation** | Generate the official THA housing application form as a filled PDF once all requirements are verified. |
| 🏘️ **Monitor Occupancy** | Track every housing unit at every relocation site — status, occupant, notice timeline, construction progress — in real time. |
| ⚖️ **Track Community Cases** | Give staff a structured system to receive, route, and resolve community complaints and occupancy violations. |
| 📱 **Notify Applicants via SMS** | Send automated Semaphore SMS notifications on registration, eligibility result, and lot awarding — with a public status tracker. |
| 🔐 **Role-Based Access** | Segment every dashboard, data table, and action button by staff position so each role sees only what they need. |

---

## ✨ Core Features

### 🌐 Public Landing Page & Applicant Status Tracker
- **Live Statistics** — Cached homepage counters for active barangays, total applicants, housing units, and applications.
- **Public Status Tracker** — Unauthenticated endpoint (`/status/<ref>/`) deep-linked from SMS messages so applicants can check their application status without a login.
- **Clean Landing Design** — Navigation links to Help, Requirements, and Contact; fully responsive.

### 🔐 Authentication & Role-Based Dashboards
- **Dual-Method Login** — Username/password or Google Workspace OAuth (`django-allauth`), with domain-restricted sign-in (`talisayhousing.gov.ph`, `chmsu.edu.ph`, `gmail.com`).
- **Role Portal Routing** — Staff are routed to their position-specific dashboard after login: Second Member, Fourth Member, Caretaker (Ronda), or Field.
- **Persistent Portal Cookie** — `LastPortalRoleCookieMiddleware` remembers the last portal role across sessions.
- **Google Drive OAuth** — Separate OAuth flow for the Document Vault "Upload from Drive" button.
- **Staff Activity Logging** — `staff_activity.py` tracks staff actions for audit trail purposes.
- **Session Management** — 5-hour session TTL; expires on browser close.

### 📥 Module 1 — Applicant Registration & Eligibility

- **Walk-In Registration** — Comprehensive modal form capturing name, civil status, barangay, household size, monthly income, danger zone details, and document checklist.
- **Duplicate Detection** — Pre-registration duplicate-preview check to prevent repeat registrations.
- **Multi-Layer Eligibility Screening** — Automated gate checks: income ceiling (₱10,000/month), Talisay residency, no existing property, blacklist check, CDRRMO hazard certification routing.
- **CDRRMO Verification Workflow** — Applicants with hazard claims are routed to Field/Ronda staff for physical situation certification before eligibility is confirmed.
- **Queue System** — Priority and walk-in queue entries for eligible applicants proceeding to Module 2.
- **SMS Notifications** — Automatic Semaphore SMS on registration confirmation and eligibility result.
- **Archive System** — Formally archive or restore applicant records with full audit snapshot at point of archival.
- **Document Deadline Tracking** — Set and track deadlines for baseline required document submission.
- **Household Members** — Register all household members linked to an applicant for occupancy compliance.

### 📋 Module 2 — Application & Evaluation

- **Eligibility Snapshot** — Pre-check deep dive with field-by-field eligibility breakdown for staff review.
- **Ready-for-Form Queue** — Applicants who pass all requirements are promoted to a dedicated "Ready for Form" queue.
- **Application Form PDF Generation** — Generate the official THA housing application form as a filled PDF (PyMuPDF + pypdf) with applicant data pre-populated.
- **Lot Awarding Queue** — Once fully approved, applicants enter the lot awarding queue with a position number. Bulk SMS notify all queue members at once.
- **Lot Award** — Formally award a specific block/lot at a relocation site to an approved applicant; transitions the housing unit to Occupied.
- **Field Verification** — Notify Ronda/Field staff to physically verify an applicant's situation on the ground.
- **CDRRMO Certification Management** — Attach, update, and view CDRRMO certification status and documents per applicant.
- **Auto-Disqualification** — Blacklisted applicants are automatically disqualified with reason text written to their record.

### 📁 Module 3 — Document Vault

- **Centralized Digital Archive** — All scanned applicant documents (PDF, image) stored in a single searchable vault, replacing physical folders.
- **Requirement Tracking** — Define required document types (Group A, B, C); track submission and verification status per applicant.
- **Google Drive Integration** — Staff can upload documents directly from Google Drive using the browser Google Picker API.
- **Binary Blob Storage** — `DocumentBlob` model stores raw file bytes in PostgreSQL, with a fast subquery-based `with_file_payload()` queryset to avoid loading heavy data on list views.
- **Download Endpoint** — `/documents/<position>/blob/<uuid>/` serves stored document binary with correct MIME type.
- **Mark Present** — Quick "mark present" action for documents that exist physically but have not been scanned yet.

### 🏘️ Module 4 — Housing Units & Monitoring

- **Interactive Lot Map** — Clickable polygon lot plan overlay linking map boxes to inventory rows; staff link a DB unit to a plan polygon by clicking the map.
- **Relocation Site Management** — Create and manage multiple relocation sites (e.g., GK Cabatangan), each with blocks, lots, and a caretaker assignment.
- **Historical Beneficiary Import** — Bulk import historical beneficiary records via CSV template for pre-system occupants.
- **Occupancy Status Tracking** — Per-unit status: Vacant, Occupied, Under Notice (30-day), Final Notice (10-day), Repossessed, Under Maintenance.
- **Compliance Notice Issuance** — Issue 30-day or 10-day compliance notices to non-compliant occupants, with SMS notification.
- **Caretaker Monitoring Dashboard** — Caretaker-specific dashboard showing pending monitoring tasks with deadlines, assessment workflow, and report submission.
- **30/60/90-Day Monitoring Workflows** — Automated task scheduling post-lot-award: initial inspection, midpoint confirmation, and final inspection tasks.
- **Explanation Letter Tracking** — Upload, set deadline for, and SMS-notify beneficiaries regarding explanation letter requirements.
- **Blacklist Management** — Add, view, and manage blacklisted individuals; automatically gates them out of the application pipeline.
- **GK Masterlist** — Dedicated masterlist view of all occupants at GK Cabatangan relocation site.
- **Static Settlement Maps** — Upload and display map images for Settlement 2+ sites (Settlement 1 is the live interactive map).

### ⚖️ Module 5 — Case Management

- **Case Creation** — Log community complaints and violations with type (noise, illegal occupant, lot boundary, community quarrel, etc.), complainant, subject unit, and initial description.
- **Sequential Case Numbers** — Thread-safe office-controlled case IDs: `CASE-YYYY-NNNN` with `select_for_update()` per calendar year.
- **Case Timeline & Actions** — Append case actions (notes, decisions, updates) to an ordered timeline per case.
- **Evidence Upload** — Attach photo or document evidence to any case record.
- **Field Settlement Recording** — Field staff can record on-site settlement outcomes with notes.
- **Role-Separated Desk Feeds** — Second Member, Fourth Member, and Field staff each see a filtered desk feed of cases relevant to their role.
- **Beneficiary Search** — Search existing beneficiaries from within the case creation form to link a case to a known occupant.
- **Settled Incident Log** — Maintain a separate log of all fully settled incidents for historical reference.

### 📊 Analytics Dashboard

- **Role-Specific Dashboards** — Each staff position sees a dashboard tailored to their workflow: intake stats, evaluation pipeline, housing map, or field monitoring.
- **Live Database Statistics** — Applicant counts, housing unit availability, application pipeline stages, case counts — all queried live and cached.
- **10-Minute Cache** — Homepage statistics use `cache.get/set` with a 600-second TTL to avoid redundant `COUNT(*)` queries on every page load.
- **Barangay Breakdown** — Applicant distribution by barangay of origin visualized in the analytics section.

---

## 🏗️ System Architecture

### Entity Relationship Diagram

> 🖊️ **Draw.io Source File:** [`docs/ERD.drawio`](docs/ERD.drawio) *(Editable in [Draw.io / app.diagrams.net](https://app.diagrams.net/))*
>
> 📄 **Markdown ERD Reference:** [`docs/ERD.md`](docs/ERD.md) — Codebase-accurate Mermaid diagrams for all 38 managed models across 5 pages: System Overview, Intake, Applications + Documents, Units, Cases.

```mermaid
erDiagram
  User ||--o{ Applicant : "registers / reviews"
  Barangay ||--o{ Applicant : "resides_in"
  Applicant ||--o| Application : "has"
  Applicant ||--o| CDRRMOCertification : "certifies"
  Applicant ||--o| Blacklist : "may_have"
  Applicant ||--o{ HouseholdMember : "includes"
  Applicant ||--o{ Document : "uploads"
  Applicant ||--o{ QueueEntry : "queues"
  Application ||--o{ LotAward : "awards"
  RelocationSite ||--o{ HousingUnit : "contains"
  HousingUnit ||--o{ LotAward : "occupied_by"
  Case }o--o| Applicant : "complainant_or_subject"
  Case }o--o| HousingUnit : "related_unit"
  Case ||--o{ CaseAction : "actions"
  Case ||--o{ CaseEvidence : "evidence"
```

### Application Workflow

```
Walk-In → [Module 1: Registration] → Eligibility Check → CDRRMO (if hazard)
       → [Module 2: Evaluation] → Form Generation → Lot Awarding Queue
       → [Module 3: Documents] → Requirement Verification
       → [Module 4: Housing] → Unit Assignment → Monitoring Tasks
       → [Module 5: Cases] → Complaint Resolution (ongoing)
```

### Staff Role Routing

| Role | Portal | Primary Modules |
|---|---|---|
| **Second Member** | `second_member` | Module 1 intake, Module 2 evaluation, Module 5 cases |
| **Fourth Member** | `fourth_member` | Module 2 evaluation, Module 2 lot awarding, analytics |
| **Ronda** | `ronda` / `field` | Module 1 CDRRMO field verification, Module 4 monitoring |
| **Field** | `field` | Module 4 housing monitoring, Module 5 field settlement |

---

## 🛠️ Tech Stack

| Layer / Feature | Technology & Tools | Description |
|---|---|---|
| **Web Framework** | Django 6.0.6 | Full-stack Python web framework with built-in ORM, routing & auth |
| **Language** | Python 3.12 | Core backend logic, SMS engine, PDF generation & all API views |
| **Database** | PostgreSQL (psycopg 3.3.4) | Primary relational database — local dev + Railway production |
| **Frontend Styling** | Tailwind CSS 4.2.4 | Locally compiled utility-first CSS (`npm run build:tailwind`) — not CDN |
| **Custom CSS** | Vanilla CSS (per-page) | Per-module hand-crafted stylesheets (22 CSS files, ~1.4 MB total) |
| **Admin Portal** | django-jazzmin 3.0.4 | Customized Django Admin with icon mapping, search, and NavBar theming |
| **Authentication** | django-allauth 65.14.0 | Google OAuth 2.0 (domain-restricted) + username/password dual-method login |
| **PDF Generation** | PyMuPDF (`fitz`) + pypdf | Official THA application form PDF population and rendering |
| **SMS Gateway** | Semaphore (Philippines) | Live SMS via Semaphore API — registration, eligibility, lot awarding notifications |
| **Static Files** | Whitenoise 6.12.0 | Serves `STATIC_ROOT` in production with gzip compression |
| **Deployment** | Railway.app (Nixpacks) | Cloud PaaS with `railway.toml` + Gunicorn gthread server |
| **WSGI Server** | Gunicorn 26.2.0 | 2 workers × 4 threads, 180-second timeout, gthread worker class |
| **Cache** | LocMemCache → Redis → DatabaseCache | Tiered cache: in-process dev, Redis prod, DB fallback |
| **Database URL** | dj-database-url 3.1.2 | `DATABASE_URL` env var parsing for Railway PostgreSQL |
| **Environment** | python-dotenv | `.env` file loading with `override=True` for local dev |
| **Image Handling** | Pillow 12.2.0 | Settlement map image uploads and processing |
| **Diagrams & Docs** | Draw.io (XML) | ERD entity relationship diagrams (editable source + Mermaid export) |
| **Icons** | Font Awesome 5 (Jazzmin) + Inline SVG | Admin icons + custom SVG icons throughout staff UI |

---

## 🚀 Setup & Installation

> Detailed step-by-step guide for setting up the project on **Windows** with **Python 3.12+** and **PostgreSQL**.

### ✅ Prerequisites

| Tool | Minimum Version | Download |
|---|---|---|
| **Python** | 3.12 | [python.org/downloads](https://www.python.org/downloads/) |
| **pip** | Latest | Bundled with Python |
| **PostgreSQL** | 14+ | [postgresql.org/download/windows](https://www.postgresql.org/download/windows/) |
| **Node.js** | 18+ (for Tailwind CSS build) | [nodejs.org](https://nodejs.org/) |
| **Git** | Any | [git-scm.com/download/win](https://git-scm.com/download/win) |

---

### 1. Clone the Repository

```powershell
git clone https://github.com/TheUnshackled1/capstone-talisay_housing.git
cd capstone-talisay_housing
```

---

### 2. Set Up a Virtual Environment

```powershell
# Create the virtual environment
python -m venv venv

# Activate it (PowerShell)
.\venv\Scripts\Activate

# Or activate it (Command Prompt)
venv\Scripts\activate.bat
```

---

### 3. Install Python Dependencies

```powershell
pip install -r requirements.txt
```

This installs:
- **Django 6.0.6** (Web framework)
- **psycopg[binary] 3.3.4** (PostgreSQL driver — psycopg 3 for Django 6)
- **django-jazzmin 3.0.4** (Admin UI customization)
- **django-allauth 65.14.0** (Google OAuth + account management)
- **PyMuPDF + pypdf** (PDF generation for housing application forms)
- **Pillow 12.2.0** (Settlement map image handling)
- **Gunicorn + Whitenoise + dj-database-url** (Production serving)
- **python-dotenv, requests, cryptography** (Environment & HTTP utilities)

---

### 4. Configure Environment Variables

```powershell
copy .env.example .env
```

Edit `.env` and fill in your values:

```ini
DEBUG=True
SECRET_KEY=your-secret-key-here
ALLOWED_HOSTS=localhost,127.0.0.1

# PostgreSQL
# DATABASE_URL=postgresql://postgres:yourpassword@localhost:5432/talisay_housing_db

# SMS — leave as console for local dev (outputs to terminal, no real SMS sent)
SMS_SERVICE=console
SEMAPHORE_API_KEY=

# Google OAuth (optional for local dev)
GOOGLE_OAUTH_CLIENT_ID=
GOOGLE_OAUTH_CLIENT_SECRET=
GOOGLE_OAUTH_ALLOWED_DOMAINS=gmail.com,talisayhousing.gov.ph,chmsu.edu.ph
```

---

### 5. Create PostgreSQL Database

```sql
CREATE DATABASE talisay_housing_db;
```

---

### 6. Run Migrations

```powershell
python manage.py migrate
```

---

### 7. Seed Reference Data (Barangays)

```powershell
python seed_requirements.py
```

Seeds the 27 Talisay City barangays required for the applicant registration form dropdown.

---

### 8. Create a Superuser

```powershell
python manage.py createsuperuser
```

---

### 9. Build Tailwind CSS

```powershell
npm install
npm run build:tailwind
# Or watch during development:
npm run watch:tailwind
```

---

### 10. Start the Development Server

```powershell
python manage.py runserver
```

The application will be available at `http://127.0.0.1:8000/`.

> **Staff Login:** Navigate to `http://127.0.0.1:8000/login/` and sign in with your superuser credentials. You will be redirected to the role-specific dashboard.

---

## 🔗 URL & API Endpoints

### Public Routes

| Endpoint | Method | Route Name | Description |
|---|---|---|---|
| `/` | `GET` | `dashboard:home` | Public landing page with live housing statistics |
| `/status/<ref>/` | `GET` | `applicant_status_tracker` | Applicant status tracker (SMS deep-link, no login required) |
| `/login/` | `GET/POST` | `accounts:login` | Staff authentication portal (username/password + Google OAuth) |
| `/login/google/` | `GET` | `accounts:google_login_start` | Initiate Google OAuth sign-in flow |
| `/logout/` | `POST` | `accounts:logout` | Log out active session and redirect to login |

### Dashboard & Role Routing

| Endpoint | Method | Route Name | Description |
|---|---|---|---|
| `/dashboard/` | `GET` | `accounts:dashboard` | Smart redirect to position-specific dashboard |
| `/dashboard/second-member/` | `GET` | `accounts:dashboard_second_member` | Second Member analytics & intake overview |
| `/dashboard/fourth-member/` | `GET` | `accounts:dashboard_fourth_member` | Fourth Member application pipeline & analytics |
| `/dashboard/caretaker/` | `GET` | `accounts:dashboard_caretaker` | Caretaker monitoring task overview |
| `/dashboard/field/` | `GET` | `accounts:dashboard_field` | Field/Ronda verification & case dashboard |

### Module 1 — Intake & Registration

| Endpoint | Method | Route Name | Description |
|---|---|---|---|
| `/intake/staff/<position>/applicants/` | `GET` | `intake:applicants_list` | Applicant management list with modal CRUD |
| `/intake/staff/<position>/archives/` | `GET` | `intake:archive_list` | Archived applicant records (proceeded to Module 2) |
| `/intake/staff/<position>/register/` | `POST` | `intake:walkin_register` | Register a new walk-in applicant (modal POST) |
| `/intake/staff/<position>/duplicate-preview/` | `POST` | `intake:duplicate_preview` | Pre-registration duplicate check (AJAX POST) |
| `/intake/staff/<position>/update-eligibility/` | `POST` | `intake:update_eligibility` | Update applicant eligibility status (AJAX POST) |
| `/intake/staff/<position>/update-applicant/` | `POST` | `intake:update_applicant` | Edit applicant profile fields (AJAX POST) |
| `/intake/staff/<position>/proceed-to-applications/` | `POST` | `intake:proceed_to_applications` | Hand off eligible applicant to Module 2 |
| `/intake/staff/<position>/delete-applicant/` | `POST` | `intake:delete_applicant` | Delete applicant record (AJAX POST) |
| `/intake/staff/<position>/unarchive-applicant/` | `POST` | `intake:unarchive_applicant` | Restore applicant from archive back to registration list |
| `/intake/staff/<position>/upload-scanned-requirement/` | `POST` | `intake:upload_scanned_requirement` | Upload scanned document for an applicant requirement |

### Module 2 — Application & Evaluation

| Endpoint | Method | Route Name | Description |
|---|---|---|---|
| `/applications/staff/<position>/` | `GET` | `applications:applications_list` | Module 2 evaluation queue with modal workflow |
| `/applications/staff/<position>/<uuid>/` | `GET` | `applications:application_detail` | Applicant/application JSON for evaluation modal |
| `/applications/staff/<position>/ready-for-form/` | `GET` | `applications:ready_for_form_queue` | Ready-for-form queue (post-requirements verified) |
| `/applications/staff/<position>/lot-awarding-queue/` | `GET` | `applications:lot_awarding_queue` | Lot awarding queue with position numbers |
| `/applications/staff/<position>/evaluate-precheck/` | `POST` | `applications:evaluate_precheck` | Run eligibility pre-check (AJAX POST) |
| `/applications/staff/<position>/save-eligibility-check-decision/` | `POST` | `applications:save_eligibility_check_decision` | Persist eligibility decision (AJAX POST) |
| `/applications/staff/<position>/generate-form/<uuid>/` | `GET` | `applications:generate_form` | Generate & populate housing application form |
| `/applications/staff/<position>/application-form-pdf/<uuid>/` | `GET` | `applications:application_form_pdf` | Download filled application form as PDF |
| `/applications/staff/<position>/award-lot/` | `POST` | `applications:award_lot` | Award a specific block/lot to an approved applicant |
| `/applications/staff/<position>/notify-ronda/` | `POST` | `applications:notify_ronda_for_situation` | Notify Field/Ronda to verify applicant situation (SMS) |
| `/applications/staff/<position>/lot-awarding-queue/bulk-notify-sms/` | `POST` | `applications:lot_awarding_bulk_notify_sms` | Bulk SMS notify all lot awarding queue members |

### Module 3 — Document Vault

| Endpoint | Method | Route Name | Description |
|---|---|---|---|
| `/documents/<position>/management/` | `GET` | `documents:management` | Document vault management page |
| `/documents/<position>/api/upload/` | `POST` | `documents:upload` | Upload document file/blob (AJAX POST) |
| `/documents/<position>/api/mark-present/` | `POST` | `documents:mark_present` | Mark a requirement as physically present |
| `/documents/<position>/api/applicant-documents/` | `GET` | `documents:get_documents` | Get all documents for an applicant (AJAX GET) |
| `/documents/<position>/blob/<uuid>/` | `GET` | `documents:blob_download` | Download stored document binary file |
| `/documents/<position>/<uuid>/delete/` | `POST` | `documents:delete` | Delete a document record (AJAX POST) |

### Module 4 — Housing Units & Monitoring

| Endpoint | Method | Route Name | Description |
|---|---|---|---|
| `/housing-units/<position>/` | `GET` | `units:housing_units_monitoring` | Interactive housing units monitoring map & list |
| `/housing-units/<position>/gk-masterlist/` | `GET` | `units:gk_masterlist` | GK Cabatangan relocation site masterlist |
| `/housing-units/<position>/site/create/` | `POST` | `units:create_relocation_site` | Create a new relocation site |
| `/housing-units/<position>/unit/create/` | `POST` | `units:create_housing_unit` | Create a new housing unit (block/lot) |
| `/housing-units/<position>/<uuid>/update/` | `POST` | `units:update_housing_unit` | Update housing unit details (AJAX POST) |
| `/housing-units/<position>/<uuid>/details/` | `GET` | `units:get_unit_details` | Get housing unit details JSON (AJAX GET) |
| `/housing-units/<position>/<uuid>/sms/` | `POST` | `units:send_unit_beneficiary_sms` | Send SMS to unit beneficiary |
| `/housing-units/<position>/<uuid>/disqualify-beneficiary/` | `POST` | `units:disqualify_beneficiary_monitoring` | Disqualify occupant from housing unit |
| `/housing-units/<position>/issue-notice/` | `POST` | `units:issue_compliance_notice` | Issue 30-day or 10-day compliance notice |
| `/housing-units/<position>/historical-beneficiaries/import/` | `POST` | `units:historical_beneficiary_import` | Bulk import historical beneficiaries via CSV |
| `/monitoring-dashboard/` | `GET` | `units:caretaker_monitoring_dashboard` | Caretaker monitoring task dashboard |
| `/monitoring-task/<uuid>/notify/` | `POST` | `units:notify_monitoring_task` | Send monitoring task notification |
| `/monitoring-task/<uuid>/assess/` | `POST` | `units:assess_monitoring_report` | Assess submitted monitoring report |
| `/monitoring-report/<uuid>/submit/` | `POST` | `units:submit_monitoring_report` | Submit monitoring inspection report |
| `/blacklists/<position>/` | `GET` | `units:blacklist_management` | Blacklist management page |

### Module 5 — Case Management

| Endpoint | Method | Route Name | Description |
|---|---|---|---|
| `/cases/<position>/` | `GET` | `cases:case_dashboard` | Case management dashboard with desk feed |
| `/cases/<position>/desk-feed/` | `GET` | `cases:desk_feed` | Role-filtered case desk feed (AJAX GET) |
| `/cases/<position>/beneficiary-search/` | `GET` | `cases:beneficiary_search` | Search beneficiaries for case linking (AJAX GET) |
| `/cases/<position>/create/` | `POST` | `cases:create` | Create a new community case record |
| `/cases/<position>/update/` | `POST` | `cases:update` | Update case status or details |
| `/cases/<position>/<uuid>/details/` | `GET` | `cases:get_details` | Get full case detail JSON (AJAX GET) |
| `/cases/<position>/<uuid>/evidence/upload/` | `POST` | `cases:upload_evidence` | Upload evidence file to a case |
| `/cases/<position>/<uuid>/settlement/save/` | `POST` | `cases:save_field_settlement` | Record field settlement for a case |
| `/cases/<position>/settled-log/create/` | `POST` | `cases:create_settled_log` | Create a settled incident log entry |
| `/cases/<position>/settled-log/<uuid>/delete/` | `POST` | `cases:delete_settled_log` | Delete a settled incident log entry |

### Staff Case UI Pages & Admin

| Endpoint | Method | Route Name | Description |
|---|---|---|---|
| `/second-member/cases/` | `GET` | `accounts:second_member_cases` | Second Member case management UI |
| `/fourth-member/cases/` | `GET` | `accounts:fourth_member_cases` | Fourth Member case management UI |
| `/field/cases/` | `GET` | `accounts:field_cases` | Field staff case management UI |
| `/admin/` | `GET/POST` | `admin:index` | Jazzmin Django Admin portal & superuser management |
| `/google/drive-auth/` | `GET` | `accounts:google_drive_auth_start` | Initiate Google Drive OAuth for Document Vault |
| `/google/drive-callback/` | `GET` | `accounts:google_drive_auth_callback` | Google Drive OAuth callback handler |

---

## 🛡️ Configuration & Security

| Setting / Feature | Default | Configuration / Recommendation |
|---|---|---|
| `DEBUG` | `True` | Set to `False` in production; configure `ALLOWED_HOSTS` via env var. |
| `SECRET_KEY` | Environment / Insecure default | Load via `SECRET_KEY` env var. Never commit the real key. |
| `ALLOWED_HOSTS` | `['*']` (DEBUG) / `['localhost']` | Set comma-separated hosts in `ALLOWED_HOSTS` env var for production. |
| `DATABASE_URL` | Local PostgreSQL (`talisay_housing_db`) | Set `DATABASE_URL` env var on Railway for managed PostgreSQL. |
| `CSRF Protection` | Enforced | `CsrfViewMiddleware` active; `CSRF_TRUSTED_ORIGINS` set for dev tunnel + production. |
| `Authentication` | `@login_required` | Session auth enforced on all staff views; public routes explicitly `@login_not_required`. |
| `Session TTL` | 5 hours | `SESSION_COOKIE_AGE = 18000`; expires on browser close. |
| `Google OAuth Domains` | `gmail.com`, `talisayhousing.gov.ph`, `chmsu.edu.ph` | Restrict to your org domain via `GOOGLE_OAUTH_ALLOWED_DOMAINS` env var. |
| `TRUST_PROXY_HEADERS` | `True` (DEBUG) | Enables `USE_X_FORWARDED_HOST` + `SECURE_PROXY_SSL_HEADER` for Railway / dev tunnels. |
| `SMS_SERVICE` | `console` (local) | Set to `semaphore` + `SEMAPHORE_API_KEY` in `.env` for live SMS delivery. |
| `SEMAPHORE_USE_PRIORITY_QUEUE` | `True` | Priority queue (2 credits/SMS) bypasses standard backlog — recommended for staff alerts. |
| `Cache (dev)` | `LocMemCache` | In-process, zero-overhead, no DB round-trips during local development. |
| `Cache (prod)` | `Redis` (if `REDIS_URL` set) | Add Redis to Railway to share cache across workers. Falls back to `DatabaseCache`. |
| `STATICFILES_STORAGE` | WhiteNoise `CompressedManifest` | Gzip-compressed, versioned static files served by WhiteNoise in production. |
| `DATA_UPLOAD_MAX_NUMBER_FIELDS` | `5000` | Increased to support large admin forms (e.g., sites with many housing units). |
| `EXTENSION_30DAY_SKIP_MIDPOINT_BLOCK` | Matches `DEBUG` | Set to `0` in production to enforce caretaker midpoint flow. |
| `PUBLIC_STATUS_BASE_URL` | `https://talisayihms.com` (prod) | Base URL for SMS deep-links in applicant status notifications. |

---

## 📁 Project Structure

> 📄 **ERD Reference:** [`docs/ERD.md`](docs/ERD.md) — Mermaid diagrams for all 38 managed models.

```
📦 capstone-talisay_housing/
├── 📂 accounts/                       🔐 Auth — User model, role routing, dashboards, Google OAuth
│   ├── 🐍 models.py                   # Custom User model with THA position choices
│   ├── 🐍 views.py                    # Login/logout, role dashboards, analytics, Drive OAuth
│   ├── 🐍 urls.py                     # Auth, dashboard, and role-specific URL patterns
│   ├── 🐍 adapters.py                 # django-allauth THA adapters (domain restriction)
│   ├── 🐍 auth_portal.py              # Portal role resolution, cookie, and validation logic
│   ├── 🐍 middleware.py               # LastPortalRoleCookieMiddleware + localization
│   ├── 🐍 staff_activity.py           # Staff action activity logging
│   ├── 🐍 signals.py                  # Post-save signals
│   └── 🐍 tests.py                    # Automated unit tests (auth, dashboard, redirects)
├── 📂 intake/                         📥 Module 1 — Applicant Registration & Eligibility
│   ├── 🐍 models.py                   # SMSLog, Barangay, Applicant, HouseholdMember, Archive
│   ├── 🐍 views.py                    # Registration, eligibility, CDRRMO, archive CRUD views
│   ├── 🐍 urls.py                     # /intake/staff/<position>/* URL patterns
│   ├── 🐍 sms_workflow.py             # Semaphore SMS send logic and retry handling
│   ├── 🐍 utils.py                    # Shared intake helpers
│   └── 🐍 tests.py                    # Automated unit tests (registration, eligibility)
├── 📂 applications/                   📋 Module 2 — Evaluation, Form Generation, Lot Awarding
│   ├── 🐍 models.py                   # Application, CDRRMOCertification, QueueEntry, LotAwarding
│   ├── 🐍 views.py                    # Evaluation pipeline, form generation, lot awarding AJAX
│   ├── 🐍 urls.py                     # /applications/staff/<position>/* URL patterns
│   ├── 🐍 application_form_pdf.py     # PyMuPDF-based application form PDF population engine
│   ├── 🐍 form_pipeline.py            # Form generation pipeline helpers
│   ├── 🐍 staff_pipeline_status.py    # Pipeline status computation for dashboards
│   └── 🐍 tests.py                    # Automated unit tests
├── 📂 documents/                      📁 Module 3 — Document Vault & Requirement Tracking
│   ├── 🐍 models.py                   # Document, DocumentBlob, Requirement, RequirementSubmission
│   ├── 🐍 views.py                    # Upload, download, mark-present, delete AJAX views
│   ├── 🐍 urls.py                     # /documents/<position>/* URL patterns
│   └── 🐍 admin.py                    # Django Admin registration for document models
├── 📂 units/                          🏘️ Module 4 — Housing Units, Monitoring, Blacklist
│   ├── 🐍 models.py                   # RelocationSite, StaticSettlement, HousingUnit, LotAward,
│   │                                  #   ConstructionProgress, Blacklist, MonitoringTask,
│   │                                  #   MonitoringReport, ComplianceNotice
│   ├── 🐍 views.py                    # Housing CRUD, monitoring, caretaker task AJAX views
│   ├── 🐍 urls.py                     # /housing-units/<position>/* and /monitoring-* URL patterns
│   ├── 🐍 monitoring_policy.py        # 30/60/90-day monitoring task policy constants
│   ├── 🐍 housing_unit_status.py      # Status transition helpers
│   ├── 🐍 isf_population.py           # ISF population stats computation
│   ├── 🐍 historical_beneficiary.py   # Historical beneficiary CSV import helpers
│   ├── 🐍 block_lot_sort.py           # Natural sort helper for block/lot display numbers
│   └── 🐍 context_processors.py       # Static settlements context processor
├── 📂 cases/                          ⚖️ Module 5 — Community Case Management
│   ├── 🐍 models.py                   # CaseYearSequence, Case, CaseAction, CaseEvidence, SettledIncidentLog
│   ├── 🐍 views.py                    # Case CRUD, desk feed, evidence upload, settlement AJAX views
│   ├── 🐍 urls.py                     # /cases/<position>/* URL patterns
│   └── 🐍 workflow.py                 # Case status workflow transitions
├── 📂 dashboard/                      🌐 Public Landing Page
│   ├── 🐍 views.py                    # Home page view with 10-minute cached statistics
│   └── 🐍 urls.py                     # / root URL pattern
├── 📂 talisay_housing/                ⚙️ Django project configuration
│   ├── 🐍 settings.py                 # All project settings (DB, cache, SMS, OAuth, Jazzmin)
│   ├── 🐍 urls.py                     # Root URL router — includes all app namespaces
│   ├── 🐍 wsgi.py                     # WSGI entry point (Gunicorn)
│   └── 🐍 asgi.py                     # ASGI entry point
├── 📂 templates/                      🎨 HTML templates (role-segmented)
│   ├── 📂 staff/                      🔐 Staff portal templates (18 HTML files)
│   │   ├── 🌐 staff_base.html         # Shared staff base layout with sidebar nav
│   │   ├── 🌐 _sidebar_nav.html       # Role-aware collapsible sidebar navigation
│   │   ├── 🌐 index.html              # Public landing page
│   │   ├── 🌐 login.html              # Staff authentication portal
│   │   ├── 🌐 dashboard.html          # Role-specific analytics dashboard
│   │   ├── 🌐 applicants.html         # Module 1 applicant list with modal workflow
│   │   ├── 🌐 applications_list.html  # Module 2 evaluation queue
│   │   ├── 🌐 ready_for_form_list.html# Module 2 ready-for-form queue
│   │   ├── 🌐 lot_awarding_queue.html # Module 2 lot awarding queue
│   │   ├── 🌐 management.html         # Module 3 document vault
│   │   ├── 🌐 housing_units_monitoring.html # Module 4 interactive monitoring map
│   │   ├── 🌐 case_management.html    # Module 5 case desk
│   │   ├── 🌐 blacklist_management.html # Blacklist management
│   │   ├── 🌐 archive_list.html       # Intake archive records
│   │   └── 🌐 gk_masterlist.html      # GK Cabatangan relocation masterlist
│   ├── 📂 field/                      🔐 Field/Ronda-specific templates
│   └── 📂 socialaccount/              🔐 django-allauth social account templates
├── 📂 static/                         🎨 Static assets
│   ├── 📂 css/                        🎨 Stylesheets (22 CSS files, ~1.4 MB total)
│   │   ├── 🎨 tha-design-system.css   # Core THA design tokens & shared component styles
│   │   ├── 🎨 tailwind.css            # Compiled Tailwind CSS output
│   │   ├── 🎨 applicants.css          # Module 1 applicant page styles
│   │   ├── 🎨 applications_list.css   # Module 2 evaluation page styles
│   │   ├── 🎨 housing_units_monitoring.css # Module 4 interactive map styles
│   │   ├── 🎨 dashboard.css           # Analytics dashboard styles
│   │   ├── 🎨 case_management.css     # Module 5 case desk styles
│   │   └── 🎨 (15 additional per-page CSS files)
│   └── 📂 js/                         📜 Frontend JavaScript (19 JS files)
│       ├── 📜 applicants.js           # Module 1 registration modals & AJAX handlers
│       ├── 📜 applications_list.js    # Module 2 evaluation workflow JS
│       ├── 📜 housing_units_monitoring.js # Module 4 interactive map & unit AJAX handlers
│       ├── 📜 dashboard.js            # Analytics charts & role-switch handlers
│       ├── 📜 case_management.js      # Module 5 case desk JS
│       ├── 📜 caretaker_monitoring.js # Caretaker monitoring task handlers
│       └── 📜 (13 additional per-page JS files)
├── 📂 docs/                           📐 ERD diagrams & screenshots
│   ├── 🗂️ ERD.drawio                  # Editable Draw.io ERD (38 models, 5 pages)
│   ├── 📄 ERD.md                      # Markdown ERD with Mermaid diagrams
│   └── 📂 screenshots/               📸 UI screenshots per module
│       ├── 📸 01_homepage.png
│       ├── 📸 03_login_page.png
│       ├── 📸 04_dashboard.png
│       └── 📸 10_housing_units.png
├── 📂 notes/                          📝 Internal developer & user documentation
│   ├── 📄 user_guide.md               # Step-by-step staff user guide (full module workflow)
│   └── 📄 dashboard_analytics_explainer.md # Analytics widget explainer for staff
├── 📂 scripts/                        🔧 Deployment shell scripts
│   └── 🔧 start.sh                    # Railway startup: migrate → cache → OAuth sync → Gunicorn
├── 📂 media/                          📂 User-uploaded media (settlement maps, explanation letters)
├── 📂 staticfiles/                    📂 WhiteNoise collectstatic output (auto-generated)
├── 📂 venv/                           🐍 Python virtual environment (local / gitignored)
├── 🗄️ db.sqlite3                      # SQLite fallback (only if DATABASE_URL is unset locally)
├── 🐍 manage.py                       # Django management CLI
├── 🐍 seed_requirements.py            # Seed script for Talisay City barangay reference data
├── ⚙️ requirements.txt                # Python package dependencies
├── 📦 package.json                    # Node.js dependencies (Tailwind CSS 4 CLI)
├── ⚙️ railway.toml                    # Railway deployment config (Nixpacks + Gunicorn)
├── ⚙️ Procfile                        # Process file (web: bash scripts/start.sh)
├── ⚙️ .env                            # Local environment variables (gitignored)
├── ⚙️ .env.example                    # Environment variable reference template
├── ⚙️ .python-version                 # Python version pin (3.12)
├── ⚙️ .gitignore                      # Git ignore rules
├── 📜 CODE_OF_CONDUCT.md             # Contributor Covenant Code of Conduct
└── 📄 README.md                       # This document
```

---

## 🧑‍💻 About

### The Project

The **Integrated Housing Services and Monitoring System (IHSMS)** was developed as a capstone project for the **Talisay City Housing Authority (THA)** — the local government unit responsible for socialized housing programs in Talisay City, Negros Occidental, Philippines.

Before this system, THA staff managed applicants through physical folders, manual eligibility spreadsheets, and handwritten logbooks — a process that made it impossible to audit decisions, track document completeness, or get a real-time view of housing unit availability. IHSMS replaces these manual workflows with a unified, role-gated, auditable digital platform.

### Organization

**Talisay City Housing Authority (THA)**
Talisay City, Negros Occidental, Philippines

This system covers the complete socialized housing lifecycle — from a walk-in applicant at the office window to formal lot award and post-occupancy monitoring at GK Cabatangan and other THA relocation sites.

### Developer

Developed by **John Tyrone Pagunsan Coronel** ([@TheUnshackled1](https://github.com/TheUnshackled1)) as a university capstone project in collaboration with THA staff.

---

*Integrated Housing Services and Monitoring System — Talisay City Housing Authority · Talisay City, Negros Occidental*
