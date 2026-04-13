# HEAD-SPECIFIC VIEWS IMPLEMENTATION PLAN
**Author**: Claude
**Date**: 2026-04-13
**Target**: 4 new HEAD (Arthur Maramba) dashboard pages
**Status**: PLANNING

---

## OVERVIEW

Four new HEAD-specific views replacing broken #href navigation links:
1. **Applicants Overview** - Executive intake summary
2. **Pending Signature** - Applications awaiting HEAD final approval
3. **Analytics Dashboard** - System-wide performance metrics
4. **Monthly Reports** - Compliance and historical reporting

**Key Pattern**: All views are read-only (HEAD oversight role), use `@login_required`, verify `position='head'`, and follow existing dashboard patterns.

---

## 1. APPLICANTS OVERVIEW

### URL
```
/head/applicants/
```

### View Function: `head_applicants_overview(request)`
**File**: `accounts/views.py`

**Responsibilities**:
- Executive-level applicant intake summary
- No editing capabilities (read-only)
- Focus on channel breakdown, eligibility metrics, queue status, alerts

**Database Queries Required**:

```python
# Channel Breakdown (3 queries)
total_applicants = Applicant.objects.count()
channel_landowner = Applicant.objects.filter(channel='landowner').count()
channel_danger = Applicant.objects.filter(channel='danger_zone').count()
channel_walkin = Applicant.objects.filter(channel='walk_in').count()

# Eligibility Status Breakdown (4 queries)
pending_eligibility = Applicant.objects.filter(status='pending').count()
eligible = Applicant.objects.filter(status='eligible').count()
disqualified = Applicant.objects.filter(status='disqualified').count()
pending_cdrrmo = Applicant.objects.filter(status='pending_cdrrmo').count()

# Queue Status (2 queries with select_related)
priority_queue = QueueEntry.objects.filter(
    queue_type='priority',
    status='active'
).select_related('applicant').count()

walkin_queue = QueueEntry.objects.filter(
    queue_type='walk_in',
    status='active'
).select_related('applicant').count()

# Critical Alerts (4 separate alert queries)
# 1. CDRRMO Overdue (>14 days pending)
from django.utils import timezone
from datetime import timedelta
overdue_threshold = timezone.now() - timedelta(days=14)
overdue_cdrrmo = CDRRMOCertification.objects.filter(
    status='pending',
    requested_at__lt=overdue_threshold
).count()

# List the actual overdue CDRRMO records (top 5)
overdue_cdrrmo_list = CDRRMOCertification.objects.filter(
    status='pending',
    requested_at__lt=overdue_threshold
).select_related('applicant').order_by('requested_at')[:5]

# 2. Blacklist Alert Count
blacklist_count = Blacklist.objects.count()

# 3. SMS Failures (last 7 days)
seven_days_ago = timezone.now() - timedelta(days=7)
failed_sms_count = SMSLog.objects.filter(
    status='failed',
    sent_at__gte=seven_days_ago
).count()

# Get sample failed SMS records
failed_sms_list = SMSLog.objects.filter(
    status='failed',
    sent_at__gte=seven_days_ago
).order_by('-sent_at')[:10]

# 4. Requirements Pending Verification
pending_requirements = RequirementSubmission.objects.filter(
    status='submitted'
).select_related('applicant', 'requirement').count()

# Detailed breakdown by status
requirements_by_status = {
    'pending': RequirementSubmission.objects.filter(status='pending').count(),
    'submitted': RequirementSubmission.objects.filter(status='submitted').count(),
    'verified': RequirementSubmission.objects.filter(status='verified').count(),
    'rejected': RequirementSubmission.objects.filter(status='rejected').count(),
}
```

**Context Data Structure**:
```python
context = {
    'page_title': 'Applicants Overview',

    # Channel Breakdown
    'total_applicants': int,
    'channel_breakdown': {
        'landowner': int,      # Channel A
        'danger_zone': int,    # Channel B
        'walk_in': int,        # Channel C
    },

    # Eligibility Metrics
    'eligibility_breakdown': {
        'pending': int,
        'eligible': int,
        'disqualified': int,
        'pending_cdrrmo': int,
    },
    'eligibility_pass_rate': int (percent),
    'requirement_breakdown': {
        'pending': int,
        'submitted': int,
        'verified': int,
        'rejected': int,
    },

    # Queue Status
    'queue_status': {
        'priority': int,
        'walk_in': int,
        'total_in_queue': int,
    },

    # Critical Alerts
    'alerts': {
        'overdue_cdrrmo': {
            'count': int,
            'threshold_days': 14,
            'details': [
                {
                    'applicant_name': str,
                    'reference': str,
                    'days_pending': int,
                    'location': str,
                },
                ...
            ]
        },
        'blacklist': {
            'count': int,
            'severity': 'high' | 'medium' | 'low',
        },
        'sms_failures': {
            'count': int,
            'period_days': 7,
            'details': [
                {
                    'phone': str,
                    'message': str,
                    'trigger_event': str,
                    'error': str,
                    'timestamp': datetime,
                },
                ...
            ]
        },
        'pending_requirements': {
            'count': int,
            'details': [...]
        }
    }
}
```

---

## 2. PENDING SIGNATURE

### URL
```
/head/applications/pending/
```

### View Function: `head_pending_signature(request)`
**File**: `accounts/views.py`

**Responsibilities**:
- List all applications awaiting HEAD's final signature
- Show application details: name, number, dates, status, days pending
- Action buttons: Review, Sign, Defer
- Sortable by days pending (oldest first by default)
- Read-only list (actual signing happens in separate workflow)

**Database Queries Required**:

```python
# Applications awaiting HEAD signature
# Status: 'routing' with last step 'forwarded_head'
pending_applications = Application.objects.filter(
    status='routing'
).select_related(
    'applicant'
).prefetch_related(
    'routing_steps'
)

# Enrich with routing metadata
pending_with_metadata = []
for app in pending_applications:
    # Get the "forwarded_head" routing step (most recent)
    forwarded_step = app.routing_steps.filter(
        step='forwarded_head'
    ).order_by('-action_at').first()

    if forwarded_step:
        days_waiting = forwarded_step.days_since_action
        is_delayed = forwarded_step.is_delayed  # >3 days

        pending_with_metadata.append({
            'id': app.id,
            'application_number': app.application_number,
            'applicant_name': app.applicant.full_name,
            'applicant_reference': app.applicant.reference_number,
            'received_date': forwarded_step.action_at,
            'days_pending': days_waiting,
            'is_delayed': is_delayed,
            'status': app.status,
            'applicant_channel': app.applicant.channel,
        })

# Sort by days pending (oldest first)
pending_with_metadata.sort(
    key=lambda x: x['days_pending'],
    reverse=True
)

# Calculate summary stats
pending_count = len(pending_with_metadata)
delayed_count = sum(1 for x in pending_with_metadata if x['is_delayed'])
average_days_pending = (
    sum(x['days_pending'] for x in pending_with_metadata) / pending_count
    if pending_count > 0 else 0
)

# Get oldest application (longest waiting)
oldest_app = pending_with_metadata[0] if pending_with_metadata else None
```

**Context Data Structure**:
```python
context = {
    'page_title': 'Applications Pending Signature',

    'summary': {
        'total_pending': int,
        'delayed_count': int,           # >3 days
        'average_days_pending': float,
        'oldest_days': int,
    },

    'applications': [
        {
            'id': UUID,
            'application_number': str,
            'applicant_name': str,
            'applicant_reference': str,
            'received_date': datetime,
            'days_pending': int,
            'is_delayed': bool,
            'status': str,
            'applicant_channel': str,
            'action_url': str,  # /applications/{id}/review/
        },
        ...
    ],

    'filter_options': {
        'sort_by': 'days_pending',  # or 'received_date', 'applicant_name'
    }
}
```

---

## 3. ANALYTICS DASHBOARD

### URL
```
/head/analytics/
```

### View Function: `head_analytics(request)`
**File**: `accounts/views.py`

**Responsibilities**:
- System-wide performance metrics
- Application processing statistics
- Timeline and trend analysis
- Visual charts/metrics for management oversight

**Database Queries Required**:

```python
from django.db.models import Count, Q
from datetime import timedelta, date
from django.utils import timezone

# ===== APPLICATION PIPELINE METRICS =====
# Total applications processed
total_applications = Application.objects.count()

# Applications by status
applications_by_status = {
    'draft': Application.objects.filter(status='draft').count(),
    'completed': Application.objects.filter(status='completed').count(),
    'routing': Application.objects.filter(status='routing').count(),
    'oic_signed': Application.objects.filter(status='oic_signed').count(),
    'head_signed': Application.objects.filter(status='head_signed').count(),
    'standby': Application.objects.filter(status='standby').count(),
    'awarded': Application.objects.filter(status='awarded').count(),
}

# Approval metrics
awarded_applications = Application.objects.filter(status='awarded').count()
disqualified_count = Applicant.objects.filter(status='disqualified').count()

# Calculate approval rate
if total_applications > 0:
    approval_rate = (awarded_applications / total_applications) * 100
    rejection_rate = (disqualified_count / total_applications) * 100
else:
    approval_rate = 0
    rejection_rate = 0

# ===== PROCESSING TIME METRICS =====
# Average time from application generation to award
awarded_apps_with_times = Application.objects.filter(
    status='awarded'
).select_related('applicant')

processing_times = []
for app in awarded_apps_with_times:
    if app.form_generated_at and app.fully_approved_at:
        days = (app.fully_approved_at - app.form_generated_at).days
        processing_times.append(days)

average_processing_time = (
    sum(processing_times) / len(processing_times)
    if processing_times else 0
)

# Processing stage breakdown
# Time from application completion to OIC signature
oic_signed_apps = Application.objects.filter(
    status__in=['oic_signed', 'head_signed', 'standby', 'awarded']
).select_related('applicant')

oic_signature_times = []
for app in oic_signed_apps:
    # Find the OIC signature timestamp
    oic_routing = app.routing_steps.filter(step='signed_oic').first()
    if oic_routing and app.form_generated_at:
        days = (oic_routing.action_at - app.form_generated_at).days
        oic_signature_times.append(days)

average_oic_time = (
    sum(oic_signature_times) / len(oic_signature_times)
    if oic_signature_times else 0
)

# Time from OIC signature to HEAD signature
head_signature_times = []
oic_and_head_apps = Application.objects.filter(
    status__in=['head_signed', 'standby', 'awarded']
).select_related('applicant').prefetch_related('routing_steps')

for app in oic_and_head_apps:
    oic_step = app.routing_steps.filter(step='signed_oic').first()
    head_step = app.routing_steps.filter(step='signed_head').first()
    if oic_step and head_step:
        days = (head_step.action_at - oic_step.action_at).days
        head_signature_times.append(days)

average_head_time = (
    sum(head_signature_times) / len(head_signature_times)
    if head_signature_times else 0
)

# ===== MONTHLY TRENDS (LAST 6 MONTHS) =====
monthly_stats = []
today = timezone.now()

for month_offset in range(6):
    # Calculate month start and end
    first_day = (today - timedelta(days=today.day + (30 * month_offset))).replace(day=1)
    next_month = (first_day + timedelta(days=32)).replace(day=1)

    month_received = Application.objects.filter(
        form_generated_at__gte=first_day,
        form_generated_at__lt=next_month
    ).count()

    month_approved = Application.objects.filter(
        fully_approved_at__gte=first_day,
        fully_approved_at__lt=next_month
    ).count()

    month_awarded = Application.objects.filter(
        status='awarded',
        updated_at__gte=first_day,
        updated_at__lt=next_month
    ).count()

    month_disqualified = Applicant.objects.filter(
        status='disqualified',
        updated_at__gte=first_day,
        updated_at__lt=next_month
    ).count()

    monthly_stats.append({
        'month': first_day.strftime('%B %Y'),
        'received': month_received,
        'approved': month_approved,
        'awarded': month_awarded,
        'disqualified': month_disqualified,
    })

# Reverse to show most recent last
monthly_stats.reverse()

# ===== QUEUE METRICS =====
priority_queue = QueueEntry.objects.filter(
    queue_type='priority',
    status='active'
).count()

walkin_queue = QueueEntry.objects.filter(
    queue_type='walk_in',
    status='active'
).count()

# ===== FACILITATED SERVICES METRICS =====
notarial_services = FacilitatedService.objects.filter(
    service_type='notarial'
)
notarial_completed = notarial_services.filter(status='completed').count()
notarial_pending = notarial_services.filter(status__in=['pending', 'in_progress']).count()

engineering_services = FacilitatedService.objects.filter(
    service_type='engineering'
)
engineering_completed = engineering_services.filter(status='completed').count()
engineering_pending = engineering_services.filter(status__in=['pending', 'in_progress']).count()

# ===== HOUSING UNITS METRICS =====
total_units = HousingUnit.objects.count()
occupied_units = HousingUnit.objects.filter(status='Occupied').count()
vacant_units = HousingUnit.objects.filter(status='Vacant — available').count()
under_notice_units = HousingUnit.objects.filter(
    status__in=['Under notice (30-day)', 'Final notice (10-day)']
).count()
repossessed_units = HousingUnit.objects.filter(status='Repossessed').count()

occupancy_rate = (occupied_units / total_units * 100) if total_units > 0 else 0
```

**Context Data Structure**:
```python
context = {
    'page_title': 'System Analytics Dashboard',

    # Pipeline Overview
    'pipeline': {
        'total': int,
        'by_status': {
            'draft': int,
            'completed': int,
            'routing': int,
            'oic_signed': int,
            'head_signed': int,
            'standby': int,
            'awarded': int,
        }
    },

    # Approval Metrics
    'approval_metrics': {
        'approved_count': int,
        'approval_rate': float (percent),
        'rejection_rate': float (percent),
        'disqualified_count': int,
    },

    # Processing Time (in days)
    'processing_times': {
        'average_total': float,
        'average_to_oic_signature': float,
        'average_oic_to_head': float,
    },

    # Monthly Trends (last 6 months)
    'monthly_trends': [
        {
            'month': str,           # "April 2026"
            'received': int,
            'approved': int,
            'awarded': int,
            'disqualified': int,
        },
        ...
    ],

    # Queue Status
    'queue': {
        'priority': int,
        'walk_in': int,
        'total': int,
    },

    # Facilitated Services
    'services': {
        'notarial': {
            'completed': int,
            'pending': int,
            'total': int,
        },
        'engineering': {
            'completed': int,
            'pending': int,
            'total': int,
        }
    },

    # Housing Units
    'housing': {
        'total_units': int,
        'occupied': int,
        'vacant': int,
        'under_notice': int,
        'repossessed': int,
        'occupancy_rate': float (percent),
    }
}
```

---

## 4. MONTHLY REPORTS

### URL
```
/head/reports/
```

### View Function: `head_monthly_reports(request)`
**File**: `accounts/views.py`

**Responsibilities**:
- Compliance and performance reports organized by month
- Month selector dropdown for historical viewing
- System-wide summary for selected month
- Printable/downloadable format
- Show application stats, queue status, housing units status, case management summary

**Database Queries Required**:

```python
from django.utils import timezone
from datetime import timedelta, date

# Get month from request parameter (default to current month)
requested_month = request.GET.get('month', timezone.now().strftime('%Y-%m'))

# Parse month YYYY-MM format
month_year = timezone.datetime.strptime(requested_month, '%Y-%m').date()
month_start = month_year.replace(day=1)
# First day of next month
next_month = (month_start + timedelta(days=32)).replace(day=1)

# ===== APPLICATIONS REPORT FOR MONTH =====
month_applications = Application.objects.filter(
    form_generated_at__gte=timezone.make_aware(timezone.datetime.combine(month_start, timezone.datetime.min.time())),
    form_generated_at__lt=timezone.make_aware(timezone.datetime.combine(next_month, timezone.datetime.min.time()))
).select_related('applicant').prefetch_related('routing_steps')

applications_received = month_applications.count()

applications_approved = Application.objects.filter(
    fully_approved_at__gte=timezone.make_aware(timezone.datetime.combine(month_start, timezone.datetime.min.time())),
    fully_approved_at__lt=timezone.make_aware(timezone.datetime.combine(next_month, timezone.datetime.min.time()))
).count()

applications_awarded = Application.objects.filter(
    status='awarded',
    updated_at__gte=timezone.make_aware(timezone.datetime.combine(month_start, timezone.datetime.min.time())),
    updated_at__lt=timezone.make_aware(timezone.datetime.combine(next_month, timezone.datetime.min.time()))
).count()

applications_rejected = Applicant.objects.filter(
    status='disqualified',
    eligibility_checked_at__gte=timezone.make_aware(timezone.datetime.combine(month_start, timezone.datetime.min.time())),
    eligibility_checked_at__lt=timezone.make_aware(timezone.datetime.combine(next_month, timezone.datetime.min.time()))
).count()

# ===== QUEUE STATUS FOR MONTH =====
# Count active queue positions on the first day of month
priority_queue = QueueEntry.objects.filter(
    queue_type='priority',
    status='active',
    entered_at__lte=next_month
).exclude(
    completed_at__lte=month_start
).count()

walkin_queue = QueueEntry.objects.filter(
    queue_type='walk_in',
    status='active',
    entered_at__lte=next_month
).exclude(
    completed_at__lte=month_start
).count()

# ===== HOUSING UNITS REPORT =====
units_occupied = HousingUnit.objects.filter(status='Occupied').count()
units_vacant = HousingUnit.objects.filter(status='Vacant — available').count()
units_under_notice = HousingUnit.objects.filter(
    status__in=['Under notice (30-day)', 'Final notice (10-day)']
).count()
units_repossessed = HousingUnit.objects.filter(status='Repossessed').count()
total_units = HousingUnit.objects.count()

occupancy_rate = (units_occupied / total_units * 100) if total_units > 0 else 0

# Units with compliance notices issued in month
compliance_notices_month = ComplianceNotice.objects.filter(
    issued_at__gte=timezone.make_aware(timezone.datetime.combine(month_start, timezone.datetime.min.time())),
    issued_at__lt=timezone.make_aware(timezone.datetime.combine(next_month, timezone.datetime.min.time()))
).count()

# ===== CASE MANAGEMENT REPORT =====
# Cases received in month
cases_received = Case.objects.filter(
    received_at__gte=timezone.make_aware(timezone.datetime.combine(month_start, timezone.datetime.min.time())),
    received_at__lt=timezone.make_aware(timezone.datetime.combine(next_month, timezone.datetime.min.time()))
).count()

# Active cases (open, under investigation, etc.)
active_cases = Case.objects.filter(
    status__in=['open', 'investigation', 'referred', 'pending_decision']
).count()

# Resolved cases in month
resolved_cases = Case.objects.filter(
    status__in=['resolved', 'closed'],
    updated_at__gte=timezone.make_aware(timezone.datetime.combine(month_start, timezone.datetime.min.time())),
    updated_at__lt=timezone.make_aware(timezone.datetime.combine(next_month, timezone.datetime.min.time()))
).count()

# Cases by type
cases_by_type = {}
for case in Case.objects.filter(
    received_at__gte=timezone.make_aware(timezone.datetime.combine(month_start, timezone.datetime.min.time())),
    received_at__lt=timezone.make_aware(timezone.datetime.combine(next_month, timezone.datetime.min.time()))
):
    case_type = case.get_case_type_display()
    cases_by_type[case_type] = cases_by_type.get(case_type, 0) + 1

# ===== ELECTRICITY CONNECTIONS REPORT =====
electricity_completed = ElectricityConnection.objects.filter(
    status='completed',
    completed_at__gte=timezone.make_aware(timezone.datetime.combine(month_start, timezone.datetime.min.time())),
    completed_at__lt=timezone.make_aware(timezone.datetime.combine(next_month, timezone.datetime.min.time()))
).count()

electricity_pending = ElectricityConnection.objects.filter(
    status__in=['pending', 'docs_submitted', 'coordinating', 'approved']
).count()

# ===== AVAILABLE MONTHS (for dropdown) =====
# Get first and last application dates to bound the range
first_app = Application.objects.order_by('form_generated_at').first()
last_app = Application.objects.order_by('-form_generated_at').first()

available_months = []
if first_app:
    start_month = first_app.form_generated_at.replace(day=1)
    end_month = timezone.now().replace(day=1)
    current = start_month

    while current <= end_month:
        available_months.append({
            'value': current.strftime('%Y-%m'),
            'display': current.strftime('%B %Y'),
        })
        # Move to next month
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)

available_months.reverse()  # Most recent first
```

**Context Data Structure**:
```python
context = {
    'page_title': 'Monthly Reports',

    'current_month': str,  # 'April 2026'
    'selected_month': str,  # '2026-04'

    'available_months': [
        {'value': '2026-04', 'display': 'April 2026'},
        ...
    ],

    # Applications Report
    'applications': {
        'received': int,
        'approved': int,
        'awarded': int,
        'rejected': int,
        'approval_rate': float,
    },

    # Queue Status
    'queue': {
        'priority': int,
        'walk_in': int,
        'total': int,
    },

    # Housing Units Status
    'housing': {
        'occupied': int,
        'vacant': int,
        'under_notice': int,
        'repossessed': int,
        'total': int,
        'occupancy_rate': float,
        'compliance_notices_issued': int,
    },

    # Case Management
    'cases': {
        'received': int,
        'active': int,
        'resolved': int,
        'by_type': {
            'Boundary Dispute': int,
            'Structural Issue': int,
            'Interpersonal Conflict': int,
            'Illegal Transfer': int,
            'Unauthorized Occupant': int,
            'Property Damage': int,
            'Noise/Disturbance': int,
            'Other': int,
        }
    },

    # Electricity Connections
    'electricity': {
        'completed': int,
        'pending': int,
    }
}
```

---

## 5. STYLING PATTERNS

### CSS Classes & Design System

All templates extend the existing `dashboard.css` system with THA brand colors:

```css
/* Primary Colors */
--primary-600: #2563eb    /* Main THA blue */
--primary-700: #1e4d8c    /* Darker blue for accents */
--primary-900: #0f2447    /* Darkest for text */

/* Status Colors */
--green-500: #22c55e      /* Success/Approved */
--amber-500: #f59e0b      /* Warning/Pending */
--red-500: #ef4444        /* Critical/Rejected */
--blue-600: #2563eb       /* Info/Primary */

/* Cards with hover effect */
.card {
    background: white;
    border-radius: 12px;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
    border: 1px solid #e5e7eb;
}

.card:hover {
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
    transform: translateY(-2px);
    transition: all 150ms ease;
}

/* Status badges */
.badge {
    display: inline-block;
    padding: 0.25rem 0.75rem;
    border-radius: 9999px;
    font-size: 0.75rem;
    font-weight: 600;
}

.badge-blue { background: #dbeafe; color: #0369a1; }
.badge-green { background: #dcfce7; color: #065f46; }
.badge-amber { background: #fef3c7; color: #92400e; }
.badge-red { background: #fee2e2; color: #991b1b; }

/* Alert boxes */
.alert-critical {
    background: #fee2e2;
    border: 1px solid #fecaca;
    border-left: 4px solid #dc2626;
    padding: 1rem;
    border-radius: 8px;
}

.alert-warning {
    background: #fef3c7;
    border: 1px solid #fde68a;
    border-left: 4px solid #f59e0b;
    padding: 1rem;
    border-radius: 8px;
}

.alert-info {
    background: #dbeafe;
    border: 1px solid #bfdbfe;
    border-left: 4px solid #2563eb;
    padding: 1rem;
    border-radius: 8px;
}

/* Grid layouts */
.grid-metric {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 1rem;
}

@media (max-width: 768px) {
    .grid-metric {
        grid-template-columns: repeat(2, 1fr);
    }
}

@media (max-width: 480px) {
    .grid-metric {
        grid-template-columns: 1fr;
    }
}
```

### Component Templates (HTML Patterns)

**Metric Card**:
```html
<div class="card">
    <div class="card-header">
        <h3 class="card-title">{{ title }}</h3>
        <span class="badge badge-blue">{{ subtitle }}</span>
    </div>
    <div class="card-body">
        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem;">
            <div style="text-align: center;">
                <div style="font-size: 2rem; font-weight: bold; color: #2563eb;">{{ value }}</div>
                <div style="font-size: 0.875rem; color: #6b7280; margin-top: 0.5rem;">{{ label }}</div>
            </div>
            <!-- Additional metric cards -->
        </div>
    </div>
</card>
```

**List Item**:
```html
<div style="border-bottom: 1px solid #e5e7eb; padding: 1rem; display: flex; justify-content: space-between; align-items: center;">
    <div>
        <div style="font-weight: 600; color: #1f2937;">{{ item.name }}</div>
        <div style="font-size: 0.875rem; color: #6b7280; margin-top: 0.25rem;">{{ item.reference }}</div>
    </div>
    <div style="text-align: right;">
        <span class="badge badge-amber">{{ item.days_pending }} days</span>
        <a href="{{ item.action_url }}" class="btn btn-sm btn-primary">View</a>
    </div>
</div>
```

**Alert Box**:
```html
<div class="alert-critical">
    <div style="display: flex; justify-content: space-between; align-items: center;">
        <div>
            <div style="font-weight: 600; color: #991b1b; font-size: 0.875rem;">⚠️ Alert Title</div>
            <div style="font-size: 1.5rem; font-weight: bold; color: #dc2626; margin-top: 0.5rem;">{{ count }}</div>
            <div style="font-size: 0.75rem; color: #991b1b; margin-top: 0.25rem;">Description</div>
        </div>
        <a href="{{ detail_url }}" class="btn btn-sm btn-danger">Review</a>
    </div>
</div>
```

---

## 6. URL ROUTING STRUCTURE

### Primary Route File: `accounts/urls.py`

```python
urlpatterns = [
    # ... existing paths ...

    # HEAD-SPECIFIC VIEWS
    path('head/applicants/', views.head_applicants_overview, name='head_applicants'),
    path('head/applications/pending/', views.head_pending_signature, name='head_pending_sig'),
    path('head/analytics/', views.head_analytics, name='head_analytics'),
    path('head/reports/', views.head_monthly_reports, name='head_reports'),
]
```

### URL Patterns Required:
- `/accounts/head/applicants/` → `head_applicants_overview`
- `/accounts/head/applications/pending/` → `head_pending_signature`
- `/accounts/head/analytics/` → `head_analytics`
- `/accounts/head/reports/` → `head_monthly_reports`

---

## 7. NAVIGATION INTEGRATION

### Update: `templates/accounts/head/dashboard.html`

Replace broken #href links with actual URLs:

```html
<!-- OLD: <a href="#" class="nav-link">Applicants Overview</a> -->
<!-- NEW: -->
<a href="{% url 'accounts:head_applicants' %}" class="nav-link {% if request.resolver_match.url_name == 'head_applicants' %}active{% endif %}">
    <svg><!-- icon --></svg>
    Applicants Overview
</a>

<a href="{% url 'accounts:head_pending_sig' %}" class="nav-link {% if request.resolver_match.url_name == 'head_pending_sig' %}active{% endif %}">
    <svg><!-- icon --></svg>
    Pending Signature
</a>

<a href="{% url 'accounts:head_analytics' %}" class="nav-link {% if request.resolver_match.url_name == 'head_analytics' %}active{% endif %}">
    <svg><!-- icon --></svg>
    Analytics
</a>

<a href="{% url 'accounts:head_reports' %}" class="nav-link {% if request.resolver_match.url_name == 'head_reports' %}active{% endif %}">
    <svg><!-- icon --></svg>
    Monthly Reports
</a>
```

### Navigation Item Styling

```css
.nav-link {
    display: flex;
    align-items: center;
    padding: 0.75rem 1rem;
    color: #6b7280;
    text-decoration: none;
    border-left: 4px solid transparent;
    transition: all 150ms ease;
}

.nav-link:hover {
    background-color: #f3f4f6;
    color: #2563eb;
    border-left-color: #2563eb;
}

.nav-link.active {
    background-color: #f3f4f6;
    color: #2563eb;
    border-left-color: #2563eb;
    font-weight: 600;
}

.nav-link svg {
    width: 20px;
    height: 20px;
    margin-right: 0.75rem;
}
```

---

## 8. IMPLEMENTATION CHECKLIST

### Files to Create/Modify:

- [ ] **`accounts/views.py`**
  - [ ] Add `head_applicants_overview(request)` function
  - [ ] Add `head_pending_signature(request)` function
  - [ ] Add `head_analytics(request)` function
  - [ ] Add `head_monthly_reports(request)` function
  - [ ] Add necessary imports (QuerySet methods, timezone, timedelta)

- [ ] **`accounts/urls.py`**
  - [ ] Add 4 URL patterns for HEAD views
  - [ ] Verify URL names match template references

- [ ] **Create templates/accounts/head/applicants_overview.html**
  - [ ] Channel breakdown widget (3-column grid)
  - [ ] Eligibility metrics card
  - [ ] Queue status widget
  - [ ] Critical alerts section (CDRRMO, Blacklist, SMS failures)
  - [ ] Responsive layout for mobile

- [ ] **Create templates/accounts/head/pending_signature.html**
  - [ ] Summary stats (total, delayed count, average days)
  - [ ] Sortable application list
  - [ ] Action buttons per application
  - [ ] Empty state message
  - [ ] Filter/sort controls

- [ ] **Create templates/accounts/head/analytics_dashboard.html**
  - [ ] Pipeline overview (status breakdown)
  - [ ] Approval metrics (rate, volume)
  - [ ] Processing time metrics (3 stages)
  - [ ] Monthly trend chart (6 months)
  - [ ] Queue status
  - [ ] Facilitated services summary
  - [ ] Housing units summary

- [ ] **Create templates/accounts/head/monthly_reports.html**
  - [ ] Month selector dropdown
  - [ ] Applications report section
  - [ ] Queue status section
  - [ ] Housing units section
  - [ ] Case management section
  - [ ] Electricity connections section
  - [ ] Print button

- [ ] **Update templates/accounts/head/dashboard.html**
  - [ ] Replace #href links with actual {% url %} tags
  - [ ] Add active state highlighting

### Testing Checklist:

- [ ] All views require @login_required
- [ ] All views verify position='head'
- [ ] No editing/POST endpoints (read-only)
- [ ] Database queries use select_related/prefetch_related for optimization
- [ ] Templates render without errors
- [ ] Responsive design works on mobile (480px, 768px, 1024px)
- [ ] Links in navigation point to correct views
- [ ] Active state highlighting works
- [ ] Empty states handled (no data available)
- [ ] Date formatting consistent throughout

### Performance Optimization:

- [ ] Use `select_related()` for ForeignKey relationships
- [ ] Use `prefetch_related()` for reverse relations
- [ ] Calculate aggregates in view, not template
- [ ] Cache month list for reports view
- [ ] Limit list queries with `.first()` or `[:10]`
- [ ] Use `only()` / `defer()` for large querysets if needed

---

## 9. DATA NORMALIZATION & EDGE CASES

### Applicants Overview Edge Cases:
- No applicants in system → Show "0" with appropriate messaging
- CDRRMO list is empty → Hide alert section
- SMS failures threshold (>5) → Show critical styling

### Pending Signature Edge Cases:
- No applications pending → Show "No applications awaiting signature"
- All applications delayed → Highlight critical
- Sort maintains state across page reloads (via URL param)

### Analytics Edge Cases:
- No applications approved → Show 0% approval rate
- Division by zero → Handle with ternary (count > 0 ? calc : 0)
- Future dates → Filter to today and past only

### Monthly Reports Edge Cases:
- Month with no data → Show all zeros
- No applications ever → Don't show month in dropdown
- Current vs. historical months → Same query logic
- Print view → Consider layout for PDF

---

## 10. SECURITY & VALIDATION

### Access Control:
```python
# All views must start with:
@login_required
def head_view(request):
    if request.user.position != 'head':
        messages.error(request, 'Access denied.')
        return redirect('accounts:dashboard')
```

### Input Validation (Reports):
```python
# Validate month format
requested_month = request.GET.get('month', timezone.now().strftime('%Y-%m'))
try:
    month_dt = timezone.datetime.strptime(requested_month, '%Y-%m')
except ValueError:
    month_dt = timezone.now()
    messages.warning(request, 'Invalid month format. Showing current month.')
```

### No Editing Allowed:
- All views are GET only (no POST endpoints)
- No forms with CSRF tokens required
- No bulk actions or data modifications
- Links to external edit pages only for context switching

---

## 11. SUMMARY

| View | Lines | Queries | Context Keys | Purpose |
|------|-------|---------|--------------|---------|
| Applicants Overview | ~100 | 15 | 12 | Intake summary & alerts |
| Pending Signature | ~80 | 8 | 8 | Applications awaiting approval |
| Analytics | ~120 | 20 | 10 | System-wide performance metrics |
| Monthly Reports | ~110 | 18 | 9 | Historical compliance reporting |

**Total Implementation**:
- 4 new view functions (~410 lines)
- 4 new templates (~800 lines HTML)
- URL routing updates (~4 lines)
- Navigation integration updates (~20 lines)
- CSS patterns (reuse existing, ~50 new lines)

**Database Optimization**:
- Use prefetch_related for routing_steps
- Use select_related for applicant foreign keys
- Cache availability month list
- Limit deep querysets with .first() / [:N]

---

## 12. REFERENCE: EXISTING PATTERNS

### View Pattern (from dashboard_head):
```python
@login_required
def dashboard_head(request):
    if request.user.position != 'head':
        messages.error(request, 'Access denied.')
        return redirect('accounts:dashboard')

    # Calculations
    total = Model.objects.count()

    context = {'total': total, ...}
    return render(request, 'accounts/head/dashboard.html', context)
```

### Template Pattern (dashboard.html):
```html
{% extends "accounts/base.html" %}
{% load static %}

{% block title %}Page Title{% endblock %}
{% block content %}
<div class="card">
    <div class="card-header">
        <h3 class="card-title">Widget Title</h3>
    </div>
    <div class="card-body">
        <!-- Content -->
    </div>
</div>
{% endblock %}
```

---

**Document Version**: 1.0
**Last Updated**: 2026-04-13
**Next Steps**: Begin view implementation in accounts/views.py
