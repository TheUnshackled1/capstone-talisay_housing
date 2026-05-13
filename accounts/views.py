import calendar
import csv
import json

from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Count, F, Q, Prefetch
from django.urls import reverse
from datetime import date, datetime, timedelta
from urllib.parse import urlencode
from .forms import LoginForm
from .models import FIELD_DESK_POSITIONS
from intake.models import Applicant, SMSLog
from applications.models import CDRRMOCertification, FieldVerificationPhoto
from units.models import Blacklist as UnitsBlacklist
from applications.models import QueueEntry, Application
from documents.models import Document, RequirementSubmission
from units.models import HousingUnit, LotAward, ConstructionProgress
from cases.models import Case


def _redirect_login_preserving_role(request):
    """Return to login; keep ?role= so the portal badge and rules stay in sync after a failed check."""
    role = request.GET.get('role', '')
    if role:
        return redirect(f"{reverse('accounts:login')}?{urlencode({'role': role})}")
    return redirect('accounts:login')


def _applicant_missing_intake_doc_q():
    """Any of the seven Module 1 intake checklist documents not yet marked received."""
    return (
        Q(doc_brgy_residency=False)
        | Q(doc_brgy_indigency=False)
        | Q(doc_cedula=False)
        | Q(doc_police_clearance=False)
        | Q(doc_no_property=False)
        | Q(doc_2x2_picture=False)
        | Q(doc_sketch_location=False)
    )


def _applicant_intake_docs_done_count(applicant):
    keys = (
        'doc_brgy_residency',
        'doc_brgy_indigency',
        'doc_cedula',
        'doc_police_clearance',
        'doc_no_property',
        'doc_2x2_picture',
        'doc_sketch_location',
    )
    return sum(1 for k in keys if getattr(applicant, k, False))


def login_view(request):
    """Staff login page."""
    if request.user.is_authenticated:
        return redirect('accounts:dashboard')
    
    # Get the requested role from URL parameter
    role = request.GET.get('role', '')
    # Legacy ?role=caretaker merged into ronda — treat as unified field desk
    if role == 'caretaker':
        role = 'field_desk'
    role_display = None

    # Map role codes to display names
    role_map = {
        'oic': 'OIC-THA',
        'second_member': 'Second Member',
        'fourth_member': 'Fourth Member',
        'ronda': 'Ronda / Field Personnel',
        'field': 'Field Personnel',
        'field_desk': 'Field verification desk',
    }
    role_display = role_map.get(role, None)
    
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            
            user = authenticate(request, username=username, password=password)
            
            if user is not None:
                # ENFORCE: Portal must match the user's position (or unified field desk).
                if role:
                    if role == 'field_desk':
                        if user.position not in FIELD_DESK_POSITIONS:
                            messages.error(
                                request,
                                'Access denied: this portal is only for field desk staff (Ronda or Field).',
                            )
                            return _redirect_login_preserving_role(request)
                    elif user.position != role:
                        messages.error(
                            request,
                            f'Access Denied: Your account is registered as {user.get_position_display()}, '
                            f'not {role_display}. Please use the correct login portal for your position.',
                        )
                        return _redirect_login_preserving_role(request)
                
                login(request, user)
                messages.success(request, f'Welcome back, {user.first_name or user.username}!')
                next_url = request.GET.get('next', 'accounts:dashboard')
                return redirect(next_url)
            else:
                messages.error(request, 'Invalid username or password.')
        else:
            messages.error(request, 'Please enter both username and password.')
    else:
        form = LoginForm()
    
    return render(request, 'accounts/login.html', {
        'form': form,
        'role': role,
        'role_display': role_display,
    })


def logout_view(request):
    """Log out and redirect to home."""
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('home')


@login_required
def dashboard_redirect(request):
    """
    Redirect to the appropriate position-specific dashboard.
    This ensures users always land on their designated dashboard.
    """
    user = request.user
    position = user.position
    
    # Map position to URL name
    position_urls = {
        'oic': 'accounts:dashboard_oic',
        'second_member': 'accounts:dashboard_second_member',
        'fourth_member': 'accounts:dashboard_fourth_member',
        'ronda': 'accounts:dashboard_field',
        'field': 'accounts:dashboard_field',
    }
    
    # Get URL for user's position, default to field dashboard
    url_name = position_urls.get(position, 'accounts:dashboard_field')
    return redirect(url_name)


@login_required
def dashboard_oic(request):
    """
    OIC dashboard focused on read-only analytics, with emphasis on housing-unit data.
    """
    if request.user.position != 'oic':
        messages.error(request, 'Access denied. This dashboard is for the OIC position only.')
        return redirect('accounts:dashboard')

    total_housing_units = HousingUnit.objects.count()
    occupied_units = HousingUnit.objects.filter(status='Occupied').count()
    vacant_units = HousingUnit.objects.filter(status='Vacant — available').count()
    under_notice_units = HousingUnit.objects.filter(status__in=['Under notice (30-day)', 'Final notice (10-day)']).count()
    repossessed_units = HousingUnit.objects.filter(status='Repossessed').count()

    total_applications = Application.objects.count()
    awarded_applications = Application.objects.filter(status='awarded').count()
    standby_applications = Application.objects.filter(status='standby').count()
    completed_applications = Application.objects.filter(status='completed').count()
    draft_applications = Application.objects.filter(status='draft').count()

    occupancy_rate_pct = int(round((occupied_units / total_housing_units) * 100)) if total_housing_units else 0
    vacancy_rate_pct = int(round((vacant_units / total_housing_units) * 100)) if total_housing_units else 0
    awarded_rate_pct = int(round((awarded_applications / total_applications) * 100)) if total_applications else 0
    ready_for_award_pct = int(round((standby_applications / total_applications) * 100)) if total_applications else 0

    apps_for_modal = list(
        Application.objects.select_related('applicant').order_by('-updated_at')[:300]
    )
    units_for_modal = list(
        HousingUnit.objects.select_related('site').order_by('block_number', 'lot_number')[:300]
    )
    oic_modal_lists = {
        'total_applications': [
            {
                'primary': app.application_number,
                'secondary': app.applicant.full_name,
                'meta': app.get_status_display(),
            }
            for app in apps_for_modal
        ],
        'completed_applications': [
            {
                'primary': app.application_number,
                'secondary': app.applicant.full_name,
                'meta': app.get_status_display(),
            }
            for app in apps_for_modal
            if app.status == 'completed'
        ],
        'awarded_applications': [
            {
                'primary': app.application_number,
                'secondary': app.applicant.full_name,
                'meta': app.get_status_display(),
            }
            for app in apps_for_modal
            if app.status == 'awarded'
        ],
        'housing_units': [
            {
                'primary': f'Block {unit.block_number}, Lot {unit.lot_number}',
                'secondary': getattr(unit, 'occupant_name', '') or 'No assigned occupant',
                'meta': unit.status,
            }
            for unit in units_for_modal
        ],
    }

    context = {
        'page_title': 'OIC Dashboard',
        'user_position': 'oic',
        'total_housing_units': total_housing_units,
        'occupied_units': occupied_units,
        'vacant_units': vacant_units,
        'under_notice_units': under_notice_units,
        'repossessed_units': repossessed_units,
        'total_applications': total_applications,
        'awarded_applications': awarded_applications,
        'standby_applications': standby_applications,
        'completed_applications': completed_applications,
        'draft_applications': draft_applications,
        'occupancy_rate_pct': occupancy_rate_pct,
        'vacancy_rate_pct': vacancy_rate_pct,
        'awarded_rate_pct': awarded_rate_pct,
        'ready_for_award_pct': ready_for_award_pct,
        'oic_analytics_updated_at': timezone.now(),
        'oic_modal_data_json': json.dumps(oic_modal_lists),
    }
    return render(request, 'accounts/dashboard.html', context)


@login_required
def dashboard_second_member(request):
    """
    Dashboard for Second Member (Lourynie Joie V. Tingson)
    Responsibilities: M2 (notices), M3 (docs), M4 (compliance), M6 (reports)
    """
    if request.user.position != 'second_member':
        messages.error(request, 'Access denied. This dashboard is for the Second Member position only.')
        return redirect('accounts:dashboard')

    # ==================== MODULE 4: legacy compliance notices list removed ====================
    pending_notices_count = 0
    urgent_notices_count = 0
    notices_to_prepare = []

    # ==================== MODULE 3: DOCUMENT OVERSIGHT (M3) — Module 1 seven-document checklist ====================
    incomplete_module1_qs = (
        Applicant.objects.filter(_applicant_missing_intake_doc_q())
        .order_by('-updated_at')[:15]
    )
    doc_completeness_alerts = []
    for app in incomplete_module1_qs:
        done = _applicant_intake_docs_done_count(app)
        doc_completeness_alerts.append({
            'applicant_name': app.full_name,
            'reference': app.reference_number,
            'missing_docs': f'{7 - done}/7 intake documents still pending',
        })
    incomplete_docs_count = Applicant.objects.filter(_applicant_missing_intake_doc_q()).count()

    # ==================== MODULE 6: UPCOMING REPORTS (Reports for Full Disclosure Portal) ====================
    # Track reports due this month
    reports_to_generate = []
    # Standard monthly reports due: 1st (Compliance Summary), 15th (Mid-month Status), 28th (Monthly Closing)
    today = date.today()

    if today.day < 1:
        reports_to_generate.append({
            'title': 'Monthly Compliance Summary',
            'due_date': today.replace(day=1),
            'status': 'DUE TODAY',
        })
    if today.day < 15:
        reports_to_generate.append({
            'title': 'Mid-Month Status Report',
            'due_date': today.replace(day=15),
            'status': 'UPCOMING',
        })
    reports_to_generate.append({
        'title': 'Monthly Closing Report',
        'due_date': today.replace(day=28),
        'status': 'UPCOMING' if today.day < 28 else 'DUE TODAY',
    })

    # ==================== SYSTEM TOTALS ====================
    total_applicants = Applicant.objects.count()

    # Shared stat card data (for dashboard headers)
    # Applications fully approved by OIC (final signature)
    awaiting_signature_count = Application.objects.filter(
        status='standby'
    ).count()

    # Total housing units
    total_housing_units = HousingUnit.objects.count()

    # Approved this month
    this_month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    approved_this_month = Application.objects.filter(
        status='awarded',
        updated_at__gte=this_month_start
    ).count()

    intake_incomplete_module1 = Applicant.objects.filter(_applicant_missing_intake_doc_q()).count()
    pending_cdrrmo_count = CDRRMOCertification.objects.filter(status='pending').count()
    requirements_verified_month = RequirementSubmission.objects.filter(
        status='verified',
        verified_at__gte=this_month_start,
    ).count()
    vacant_units_award = HousingUnit.objects.filter(status='Vacant — available').count()

    context = {
        'page_title': 'Second Member Dashboard',
        'user_position': 'second_member',

        # ========== MODULE 4: COMPLIANCE NOTICES (M4) ==========
        'pending_notices': pending_notices_count,
        'urgent_notices': urgent_notices_count,
        'notices_to_prepare': notices_to_prepare,

        # ========== MODULE 3: DOCUMENT OVERSIGHT (M3) ==========
        'incomplete_docs': incomplete_docs_count,
        'doc_completeness_alerts': doc_completeness_alerts[:10],  # Limit to 10

        # ========== MODULE 6: REPORTS (M6) ==========
        'reports_to_generate': reports_to_generate,

        # ========== SYSTEM OVERVIEW ==========
        'total_applicants': total_applicants,
        'awaiting_signature': awaiting_signature_count,  # Shared stat card
        'housing_units': total_housing_units,  # Shared stat card
        'approved_this_month': approved_this_month,  # Shared stat card
        # Second-row stat cards (aligned to Joie’s intake + oversight role)
        'intake_incomplete_module1': intake_incomplete_module1,
        'pending_cdrrmo_count': pending_cdrrmo_count,
        'requirements_verified_month': requirements_verified_month,
        'vacant_units_award': vacant_units_award,
    }

    return render(request, 'accounts/dashboard.html', context)


def _report_month_bounds(year: int, month: int):
    """First and last instant of calendar month in the active timezone."""
    tz = timezone.get_current_timezone()
    start = datetime(year, month, 1, 0, 0, 0, tzinfo=tz)
    last_day = calendar.monthrange(year, month)[1]
    end = datetime(year, month, last_day, 23, 59, 59, 999999, tzinfo=tz)
    return start, end


def _six_month_sequence_end(year: int, month: int):
    """Six (year, month, label) tuples, chronological order, ending at year/month."""
    pairs = []
    y, m = year, month
    for _ in range(6):
        pairs.append((y, m, f'{calendar.month_abbr[m]} {y}'))
        m -= 1
        if m < 1:
            m = 12
            y -= 1
    pairs.reverse()
    return pairs


def _staff_analytics_ready_for_form_count(user):
    """
    Cardinality of the Ready for Form queue — same routing rules as ``ready_for_form_queue``.
    Uses lazy imports to avoid tight coupling at module load time.
    """
    from documents.models import Requirement
    from applications.views import (
        _module2_evaluations_applicants_queryset,
        _module2_applicant_row_payload,
        _module2_on_ready_for_form_queue_track,
        get_module2_permissions,
    )

    permissions = get_module2_permissions(user)
    required_total = Requirement.objects.filter(
        group='A',
        is_active=True,
        is_required_for_form=True,
    ).count()
    n = 0
    for applicant in _module2_evaluations_applicants_queryset().iterator(chunk_size=200):
        row = _module2_applicant_row_payload(applicant, permissions, required_total, user)
        if row is None:
            continue
        if _module2_on_ready_for_form_queue_track(applicant, row['application']):
            n += 1
    return n


def _analytics_rows_bar_pct(rows, count_key='count'):
    """Attach ``bar_pct`` 0–100 per row vs max count for horizontal bar charts."""
    if not rows:
        return rows
    top = max(r[count_key] for r in rows)
    top = max(top, 1)
    for r in rows:
        r['bar_pct'] = min(100, int(round(100 * r[count_key] / top)))
    return rows


def _chart_label(s, max_len=44):
    if s is None:
        return '—'
    s = str(s).strip()
    if len(s) <= max_len:
        return s
    return s[: max_len - 1] + '…'


def _build_analytics_charts_data(
    intake_registration_trend,
    monthly_upload_trend,
    applicant_by_status,
    application_by_status,
    housing_units_by_status,
    cases_by_status,
    cases_by_type,
    applicants_top_barangays,
    applicants_by_channel,
    requirement_by_status,
    queue_active_rows,
    ready_for_form_queue_count,
    module2_handoff_count,
    housing_application_records,
    applicants_registered_period,
    *,
    queue_by_status=None,
    case_aging_bands=None,
    funnel_stages=None,
):
    """
    Build a JSON-serializable dict for Chart.js (staff analytics page).
    Keeps labels readable and aligned with the same queries as the tables.
    """

    def pair_labels_counts(rows, label_key='label', count_key='count'):
        labels = [_chart_label(r.get(label_key)) for r in rows]
        values = [int(r.get(count_key) or 0) for r in rows]
        return {'labels': labels, 'values': values}

    queue_chart_rows = [
        {
            'label': _chart_label(
                (r.get('queue_type') or '—').replace('_', ' ').strip().title()
            ),
            'count': r.get('count') or 0,
        }
        for r in (queue_active_rows or [])
    ]

    data = {
        'trend': {
            'labels': [r['label'] for r in intake_registration_trend],
            'registrations': [int(r['count']) for r in intake_registration_trend],
            'vaultUploads': [int(r['count']) for r in monthly_upload_trend],
        },
        'applicantsByStatus': pair_labels_counts(applicant_by_status),
        'applicationsByStatus': pair_labels_counts(application_by_status),
        'housingByStatus': pair_labels_counts(housing_units_by_status),
        'casesByStatus': pair_labels_counts(cases_by_status),
        'casesByType': pair_labels_counts(cases_by_type),
        'topBarangays': pair_labels_counts(applicants_top_barangays, label_key='place_name'),
        'channels': pair_labels_counts(applicants_by_channel),
        'requirementsByStatus': pair_labels_counts(requirement_by_status),
        'activeQueues': pair_labels_counts(queue_chart_rows),
        'pipelineSnapshot': {
            'labels': [
                'Ready for Form',
                'Module 2 handoff',
                'Housing app records',
                'New applicants (period)',
            ],
            'values': [
                int(ready_for_form_queue_count),
                int(module2_handoff_count),
                int(housing_application_records),
                int(applicants_registered_period),
            ],
        },
    }

    # Enriched operational charts
    if queue_by_status:
        data['queueByStatus'] = pair_labels_counts(queue_by_status)
    if case_aging_bands:
        data['caseAging'] = {
            'labels': list(case_aging_bands.keys()),
            'values': list(case_aging_bands.values()),
        }
    if funnel_stages:
        data['workflowFunnel'] = pair_labels_counts(funnel_stages)

    return data


def _staff_reports_analytics_payload(request):
    """
    Shared datasets for Second / Fourth Member reporting (same analytics scope).

    Returns a dict suitable for ``staff_reports_analytics.html`` and CSV export.
    """
    now = timezone.localtime(timezone.now())
    try:
        report_year = int(request.GET.get('year', now.year))
        report_month = int(request.GET.get('month', now.month))
    except (TypeError, ValueError):
        report_year, report_month = now.year, now.month
    report_year = max(2000, min(report_year, 2100))
    report_month = max(1, min(report_month, 12))

    period_start, period_end = _report_month_bounds(report_year, report_month)
    period_label = f'{calendar.month_name[report_month]} {report_year}'

    doc_type_labels = dict(Document.DOCUMENT_TYPE_CHOICES)
    applicant_status_labels = dict(Applicant.STATUS_CHOICES)
    application_status_labels = dict(Application.STATUS_CHOICES)
    incomplete_docs_count = Applicant.objects.filter(_applicant_missing_intake_doc_q()).count()
    total_applicants = Applicant.objects.count()
    housing_application_records = Application.objects.count()

    applicant_by_status = sorted(
        (
            Applicant.objects.values('status')
            .annotate(count=Count('id'))
            .order_by('-count')
        ),
        key=lambda x: (-x['count'], x['status'] or ''),
    )
    for row in applicant_by_status:
        row['label'] = applicant_status_labels.get(row['status'], row['status'] or '—')

    application_by_status = sorted(
        (
            Application.objects.values('status')
            .annotate(count=Count('id'))
            .order_by('-count')
        ),
        key=lambda x: (-x['count'], x['status'] or ''),
    )
    for row in application_by_status:
        row['label'] = application_status_labels.get(row['status'], row['status'] or '—')

    docs_filed_period = Document.objects.filter(
        uploaded_at__gte=period_start,
        uploaded_at__lte=period_end,
    ).count()

    documents_by_type = sorted(
        (
            Document.objects.filter(uploaded_at__gte=period_start, uploaded_at__lte=period_end)
            .values('document_type')
            .annotate(count=Count('id'))
            .order_by('-count')[:24]
        ),
        key=lambda x: (-x['count'], x['document_type'] or ''),
    )
    max_doc_type_count = documents_by_type[0]['count'] if documents_by_type else 1
    for row in documents_by_type:
        row['label'] = doc_type_labels.get(row['document_type'], row['document_type'] or '—')
        row['bar_pct'] = min(100, int(round(100 * row['count'] / max_doc_type_count)))

    monthly_upload_trend = []
    trend_max = 1
    for y, m, lbl in _six_month_sequence_end(report_year, report_month):
        ms, me = _report_month_bounds(y, m)
        c = Document.objects.filter(uploaded_at__gte=ms, uploaded_at__lte=me).count()
        trend_max = max(trend_max, c)
        monthly_upload_trend.append({'label': lbl, 'year': y, 'month': m, 'count': c})
    for row in monthly_upload_trend:
        row['bar_pct'] = min(100, int(round(100 * row['count'] / trend_max))) if trend_max else 0

    applicants_registered_period = Applicant.objects.filter(
        created_at__gte=period_start,
        created_at__lte=period_end,
    ).count()
    housing_apps_created_period = Application.objects.filter(
        created_at__gte=period_start,
        created_at__lte=period_end,
    ).count()
    awarded_transition_period = Application.objects.filter(
        status='awarded',
        updated_at__gte=period_start,
        updated_at__lte=period_end,
    ).count()
    requirements_verified_period = RequirementSubmission.objects.filter(
        status='verified',
        verified_at__gte=period_start,
        verified_at__lte=period_end,
    ).count()

    queue_active_rows = sorted(
        QueueEntry.objects.filter(status='active')
        .values('queue_type')
        .annotate(count=Count('id')),
        key=lambda x: (-x['count'], x['queue_type'] or ''),
    )

    vacant_units_count = HousingUnit.objects.filter(status='Vacant — available').count()
    pending_cdrrmo_count = CDRRMOCertification.objects.filter(status='pending').count()

    situation_counts_map = {
        (row.get('displacement_reason') or '').strip(): int(row.get('count') or 0)
        for row in Applicant.objects.values('displacement_reason').annotate(count=Count('id'))
    }
    applicants_by_channel = [
        {
            'channel': 'danger_zone',
            'label': 'Option A — Resident of Danger Zone or Hazard Area',
            'count': situation_counts_map.get('danger_zone', 0),
        },
        {
            'channel': 'ejected',
            'label': 'Option B — Ejected or Evicted from Prior Residence',
            'count': situation_counts_map.get('ejected', 0),
        },
        {
            'channel': 'relocated',
            'label': 'Option C — Displaced by Government Project or Infrastructure',
            'count': situation_counts_map.get('relocated', 0),
        },
        {
            'channel': 'not_abc',
            'label': 'Option D — None of A, B, or C (Other / not listed)',
            'count': situation_counts_map.get('not_abc', 0),
        },
    ]
    _analytics_rows_bar_pct(applicants_by_channel)

    applicants_top_barangays = list(
        Applicant.objects.exclude(barangay_id__isnull=True)
        .values(place_name=F('barangay__name'))
        .annotate(count=Count('id'))
        .order_by('-count')[:12]
    )
    for row in applicants_top_barangays:
        row['place_name'] = row.get('place_name') or '—'
    _analytics_rows_bar_pct(applicants_top_barangays)

    intake_registration_trend = []
    reg_max = 1
    for y, m, lbl in _six_month_sequence_end(report_year, report_month):
        ms, me = _report_month_bounds(y, m)
        c = Applicant.objects.filter(created_at__gte=ms, created_at__lte=me).count()
        reg_max = max(reg_max, c)
        intake_registration_trend.append({'label': lbl, 'year': y, 'month': m, 'count': c})
    for row in intake_registration_trend:
        row['bar_pct'] = min(100, int(round(100 * row['count'] / reg_max))) if reg_max else 0

    module2_handoff_count = Applicant.objects.filter(module2_handoff_at__isnull=False).count()
    ready_for_form_queue_count = _staff_analytics_ready_for_form_count(request.user)
    pending_oic_signature_count = Application.objects.filter(status='completed').count()

    requirement_submission_labels = dict(RequirementSubmission.STATUS_CHOICES)
    requirement_by_status = sorted(
        RequirementSubmission.objects.values('status').annotate(count=Count('id')),
        key=lambda x: (-x['count'], x['status'] or ''),
    )
    for row in requirement_by_status:
        row['label'] = requirement_submission_labels.get(row['status'], row['status'] or '—')
    _analytics_rows_bar_pct(requirement_by_status)

    requirement_submissions_submitted_period = RequirementSubmission.objects.filter(
        submitted_at__gte=period_start,
        submitted_at__lte=period_end,
    ).count()

    documents_total_count = Document.objects.count()

    housing_units_total = HousingUnit.objects.count()
    housing_status_labels = dict(HousingUnit.STATUS_CHOICES)
    housing_units_by_status = sorted(
        HousingUnit.objects.values('status').annotate(count=Count('id')),
        key=lambda x: (-x['count'], x['status'] or ''),
    )
    for row in housing_units_by_status:
        row['label'] = housing_status_labels.get(row['status'], row['status'] or '—')
    _analytics_rows_bar_pct(housing_units_by_status)

    cases_total = Case.objects.count()
    case_status_labels = dict(Case.STATUS_CHOICES)
    case_type_labels = dict(Case.CASE_TYPE_CHOICES)
    cases_by_status = sorted(
        Case.objects.values('status').annotate(count=Count('id')),
        key=lambda x: (-x['count'], x['status'] or ''),
    )
    for row in cases_by_status:
        row['label'] = case_status_labels.get(row['status'], row['status'] or '—')
    _analytics_rows_bar_pct(cases_by_status)

    cases_by_type = sorted(
        Case.objects.values('case_type').annotate(count=Count('id')),
        key=lambda x: (-x['count'], x['case_type'] or ''),
    )
    for row in cases_by_type:
        row['label'] = case_type_labels.get(row['case_type'], row['case_type'] or '—')
    _analytics_rows_bar_pct(cases_by_type)

    cases_opened_period = Case.objects.filter(
        received_at__gte=period_start,
        received_at__lte=period_end,
    ).count()
    cases_closed_period = Case.objects.filter(
        status__in=['resolved', 'closed'],
        resolved_at__gte=period_start,
        resolved_at__lte=period_end,
    ).count()

    # ===== ENRICHED OPERATIONAL ANALYTICS =====

    # Queue entries by status (full lifecycle)
    queue_status_labels = dict(QueueEntry.STATUS_CHOICES)
    queue_by_status = sorted(
        QueueEntry.objects.values('status').annotate(count=Count('id')),
        key=lambda x: (-x['count'], x['status'] or ''),
    )
    for row in queue_by_status:
        row['label'] = queue_status_labels.get(row['status'], row['status'] or '—')
    _analytics_rows_bar_pct(queue_by_status)

    # Queue entries by type (priority vs walk-in)
    queue_type_labels = dict(QueueEntry.QUEUE_TYPE_CHOICES)
    queue_by_type = sorted(
        QueueEntry.objects.values('queue_type').annotate(count=Count('id')),
        key=lambda x: (-x['count'], x['queue_type'] or ''),
    )
    for row in queue_by_type:
        row['label'] = queue_type_labels.get(row['queue_type'], row['queue_type'] or '—')
    _analytics_rows_bar_pct(queue_by_type)

    # Case aging bands (open cases only)
    open_cases = Case.objects.exclude(status__in=['resolved', 'closed'])
    stale_cases_count = 0
    case_aging_bands = {'0-3 days': 0, '4-7 days': 0, '8-14 days': 0, '15-30 days': 0, '30+ days': 0}
    for c in open_cases:
        days = (now - c.received_at).days if c.received_at else 0
        if days > 14:
            stale_cases_count += 1
        if days <= 3:
            case_aging_bands['0-3 days'] += 1
        elif days <= 7:
            case_aging_bands['4-7 days'] += 1
        elif days <= 14:
            case_aging_bands['8-14 days'] += 1
        elif days <= 30:
            case_aging_bands['15-30 days'] += 1
        else:
            case_aging_bands['30+ days'] += 1
    open_cases_count = open_cases.count()

    # Applicant workflow funnel — count per pipeline stage
    funnel_stages = [
        {'label': 'Registered (all time)', 'count': total_applicants},
        {'label': 'Eligible / in queue', 'count': Applicant.objects.filter(status='eligible').count()},
        {'label': 'Submitting requirements', 'count': Applicant.objects.filter(status='requirements').count()},
        {'label': 'Application in progress', 'count': Applicant.objects.filter(status='application').count()},
        {'label': 'Fully approved (standby)', 'count': Applicant.objects.filter(status='standby').count()},
        {'label': 'Lot awarded', 'count': Applicant.objects.filter(status='awarded').count()},
    ]
    _analytics_rows_bar_pct(funnel_stages)

    # Requirement verification velocity (verified in period / total submitted in period)
    req_submitted_period = RequirementSubmission.objects.filter(
        submitted_at__gte=period_start, submitted_at__lte=period_end,
    ).count()
    req_verified_period = requirements_verified_period
    req_verification_rate = (
        int(round(100 * req_verified_period / req_submitted_period))
        if req_submitted_period > 0 else 0
    )

    # Housing occupancy rate
    occupied_units = HousingUnit.objects.filter(status='Occupied').count()
    housing_occupancy_rate = (
        int(round(100 * occupied_units / housing_units_total))
        if housing_units_total > 0 else 0
    )

    # Units under notice
    units_under_notice = HousingUnit.objects.filter(
        status__in=['Under notice (30-day)', 'Final notice (10-day)']
    ).count()
    repossessed_units = HousingUnit.objects.filter(status='Repossessed').count()

    # Construction progress summary
    construction_total = ConstructionProgress.objects.count()
    construction_completed = ConstructionProgress.objects.filter(stage='completed').count()
    construction_in_progress = ConstructionProgress.objects.exclude(
        stage__in=['not_started', 'completed']
    ).count()
    construction_delayed = ConstructionProgress.objects.filter(is_delayed=True).count()

    # Blacklist count
    blacklist_count = UnitsBlacklist.objects.count()

    # Active lot awards
    active_lot_awards = LotAward.objects.filter(status='active').count()

    analytics_charts_data = _build_analytics_charts_data(
        intake_registration_trend,
        monthly_upload_trend,
        applicant_by_status,
        application_by_status,
        housing_units_by_status,
        cases_by_status,
        cases_by_type,
        applicants_top_barangays,
        applicants_by_channel,
        requirement_by_status,
        queue_active_rows,
        ready_for_form_queue_count,
        module2_handoff_count,
        housing_application_records,
        applicants_registered_period,
        queue_by_status=queue_by_status,
        case_aging_bands=case_aging_bands,
        funnel_stages=funnel_stages,
    )

    year_options = list(range(now.year - 5, now.year + 2))
    month_options = list(range(1, 13))
    months_for_select = [(i, calendar.month_name[i]) for i in range(1, 13)]

    return {
        'pending_notices': 0,
        'incomplete_docs': incomplete_docs_count,
        'total_applications': total_applicants,
        'housing_application_records': housing_application_records,
        'notices_issued': 0,
        'docs_filed': docs_filed_period,
        'timestamp': timezone.now(),
        'period_label': period_label,
        'report_year': report_year,
        'report_month': report_month,
        'year_options': year_options,
        'month_options': month_options,
        'months_for_select': months_for_select,
        'applicant_by_status': applicant_by_status,
        'application_by_status': application_by_status,
        'documents_by_type': documents_by_type,
        'monthly_upload_trend': monthly_upload_trend,
        'applicants_registered_period': applicants_registered_period,
        'housing_apps_created_period': housing_apps_created_period,
        'awarded_transition_period': awarded_transition_period,
        'requirements_verified_period': requirements_verified_period,
        'queue_active_rows': queue_active_rows,
        'vacant_units_count': vacant_units_count,
        'pending_cdrrmo_count': pending_cdrrmo_count,
        'applicants_by_channel': applicants_by_channel,
        'applicants_top_barangays': applicants_top_barangays,
        'intake_registration_trend': intake_registration_trend,
        'module2_handoff_count': module2_handoff_count,
        'ready_for_form_queue_count': ready_for_form_queue_count,
        'pending_oic_signature_count': pending_oic_signature_count,
        'requirement_by_status': requirement_by_status,
        'requirement_submissions_submitted_period': requirement_submissions_submitted_period,
        'documents_total_count': documents_total_count,
        'housing_units_total': housing_units_total,
        'housing_units_by_status': housing_units_by_status,
        'cases_total': cases_total,
        'cases_by_status': cases_by_status,
        'cases_by_type': cases_by_type,
        'cases_opened_period': cases_opened_period,
        'cases_closed_period': cases_closed_period,
        'analytics_charts_data': analytics_charts_data,
        # Enriched operational analytics
        'queue_by_status': queue_by_status,
        'queue_by_type': queue_by_type,
        'case_aging_bands': case_aging_bands,
        'stale_cases_count': stale_cases_count,
        'open_cases_count': open_cases_count,
        'funnel_stages': funnel_stages,
        'req_submitted_period': req_submitted_period,
        'req_verification_rate': req_verification_rate,
        'housing_occupancy_rate': housing_occupancy_rate,
        'occupied_units': occupied_units,
        'units_under_notice': units_under_notice,
        'repossessed_units': repossessed_units,
        'construction_total': construction_total,
        'construction_completed': construction_completed,
        'construction_in_progress': construction_in_progress,
        'construction_delayed': construction_delayed,
        'blacklist_count': blacklist_count,
        'active_lot_awards': active_lot_awards,
        # SVG gauge ring offsets — circumference = 2πr ≈ 97.4; offset = circ × (1 − pct/100)
        'housing_occupancy_offset': round(97.4 * (1 - housing_occupancy_rate / 100), 1),
        'req_verification_offset': round(97.4 * (1 - req_verification_rate / 100), 1),
        'stale_cases_offset': round(97.4 * (1 - min(100, (stale_cases_count * 10 if cases_total else 0)) / 100), 1),
        'construction_progress_offset': round(
            97.4 * (1 - min(100, int(100 * construction_in_progress / max(construction_total, 1))) / 100), 1
        ),
    }


def _staff_reports_analytics_csv_response(data, export_role_title, filename_prefix):
    """Build CSV download for shared staff report payload."""
    report_year = data['report_year']
    report_month = data['report_month']
    period_label = data['period_label']
    applicant_by_status = data['applicant_by_status']
    application_by_status = data['application_by_status']
    documents_by_type = data['documents_by_type']
    monthly_upload_trend = data['monthly_upload_trend']

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = (
        f'attachment; filename="{filename_prefix}_{report_year}_{report_month:02d}.csv"'
    )
    response.write('\ufeff')
    writer = csv.writer(response)
    writer.writerow([f'THA {export_role_title} — data export (shared intake & operations metrics)'])
    writer.writerow(['Reporting period', period_label])
    writer.writerow(['Generated', timezone.localtime(timezone.now()).isoformat()])
    writer.writerow([])
    writer.writerow(['Applicant counts by status (snapshot)'])
    writer.writerow(['Status code', 'Label', 'Count'])
    for row in applicant_by_status:
        writer.writerow([row['status'], row['label'], row['count']])
    writer.writerow([])
    writer.writerow(['Housing Application records by status (snapshot)'])
    writer.writerow(['Status code', 'Label', 'Count'])
    for row in application_by_status:
        writer.writerow([row['status'], row['label'], row['count']])
    writer.writerow([])
    writer.writerow(['Vault uploads in period by document type'])
    writer.writerow(['Type code', 'Label', 'Count'])
    for row in documents_by_type:
        writer.writerow([row['document_type'], row['label'], row['count']])
    writer.writerow([])
    writer.writerow(['Document uploads — trailing six months'])
    writer.writerow(['Month', 'Count'])
    for row in monthly_upload_trend:
        writer.writerow([row['label'], row['count']])
    writer.writerow([])
    writer.writerow(['Period activity'])
    writer.writerow(['Metric', 'Value'])
    writer.writerow(['New applicants registered (created in period)', data['applicants_registered_period']])
    writer.writerow(['New housing Application records created in period', data['housing_apps_created_period']])
    writer.writerow(['Applications marked awarded (updated in period)', data['awarded_transition_period']])
    writer.writerow(['Requirements verified (in period)', data['requirements_verified_period']])
    writer.writerow(['Vault document uploads (in period)', data['docs_filed']])
    writer.writerow([])
    writer.writerow(['Module summaries'])
    writer.writerow(['Applicants by applicant situation (Options A-D)', '', ''])
    writer.writerow(['Situation code', 'Label', 'Count'])
    for row in data.get('applicants_by_channel', []):
        writer.writerow([row.get('channel'), row.get('label'), row.get('count')])
    writer.writerow(['Top barangays (masterlist)', '', ''])
    writer.writerow(['Barangay', 'Count'])
    for row in data.get('applicants_top_barangays', []):
        writer.writerow([row.get('place_name'), row.get('count')])
    writer.writerow(['New registrations — trailing six months', '', ''])
    writer.writerow(['Month', 'Count'])
    for row in data.get('intake_registration_trend', []):
        writer.writerow([row.get('label'), row.get('count')])
    writer.writerow([])
    writer.writerow([
        'Ready for Form queue (current)',
        data.get('ready_for_form_queue_count'),
    ])
    writer.writerow([
        'Module 2 handoff reached (applicants)',
        data.get('module2_handoff_count'),
    ])
    writer.writerow([
        'Pending OIC signature (applications)',
        data.get('pending_oic_signature_count'),
    ])
    writer.writerow([])
    writer.writerow(['Requirement submissions by status'])
    writer.writerow(['Status', 'Label', 'Count'])
    for row in data.get('requirement_by_status', []):
        writer.writerow([row.get('status'), row.get('label'), row.get('count')])
    writer.writerow([])
    writer.writerow([
        'Requirement rows submitted (timestamp in period)',
        data.get('requirement_submissions_submitted_period'),
    ])
    writer.writerow(['Documents in vault (total)', data.get('documents_total_count')])
    writer.writerow([])
    writer.writerow(['Housing units by status'])
    writer.writerow(['Status code', 'Label', 'Count'])
    for row in data.get('housing_units_by_status', []):
        writer.writerow([row.get('status'), row.get('label'), row.get('count')])
    writer.writerow([])
    writer.writerow(['Cases by status'])
    writer.writerow(['Status', 'Label', 'Count'])
    for row in data.get('cases_by_status', []):
        writer.writerow([row.get('status'), row.get('label'), row.get('count')])
    writer.writerow(['Cases by type'])
    writer.writerow(['Type', 'Label', 'Count'])
    for row in data.get('cases_by_type', []):
        writer.writerow([row.get('case_type'), row.get('label'), row.get('count')])
    writer.writerow([
        'Cases opened (received in period)',
        data.get('cases_opened_period'),
    ])
    writer.writerow([
        'Cases closed (resolved_at in period)',
        data.get('cases_closed_period'),
    ])
    return response


@login_required
def second_member_analytics(request):
    """Second Member — same operational analytics dataset as Fourth Member (reports hub)."""
    if request.user.position != 'second_member':
        messages.error(request, 'Access denied. Analytics is for the Second Member position only.')
        return redirect('accounts:dashboard')

    data = _staff_reports_analytics_payload(request)
    if request.GET.get('export') == 'csv':
        return _staff_reports_analytics_csv_response(data, 'Second Member', 'second_member_report')

    context = {
        **data,
        'page_title': 'Reports & analytics',
        'report_meta_title': 'Reports & analytics — Second Member | THA',
        'report_role_heading': 'Second Member oversight',
        'report_role_officer': 'Lourynie Joie V. Tingson',
        'report_role_modules': 'M2, M3, M4, M6',
        'dashboard_url': reverse('accounts:dashboard_second_member'),
    }
    return render(request, 'accounts/staff_reports_analytics.html', context)


@login_required
def fourth_member_analytics(request):
    """Fourth Member — same analytics datasets as Second Member (shared pipeline visibility)."""
    if request.user.position != 'fourth_member':
        messages.error(request, 'Access denied. Analytics is for the Fourth Member position only.')
        return redirect('accounts:dashboard')

    data = _staff_reports_analytics_payload(request)
    if request.GET.get('export') == 'csv':
        return _staff_reports_analytics_csv_response(data, 'Fourth Member', 'fourth_member_report')

    context = {
        **data,
        'page_title': 'Reports & analytics',
        'report_meta_title': 'Reports & analytics — Fourth Member | THA',
        'report_role_heading': 'Fourth Member oversight',
        'report_role_officer': 'Jocel O. Cuaysing',
        'report_role_modules': 'M1, M2, M3, M4',
        'dashboard_url': reverse('accounts:dashboard_fourth_member'),
    }
    return render(request, 'accounts/staff_reports_analytics.html', context)


@login_required
def dashboard_fourth_member(request):
    """
    Dashboard for Fourth Member (Jocel O. Cuaysing)
    Responsibilities: M1 (masterlist, eligibility, queue), M2 (requirements, lot awarding), M3 (docs), M4 (property custodian)
    """
    if request.user.position != 'fourth_member':
        messages.error(request, 'Access denied. This dashboard is for the Fourth Member position only.')
        return redirect('accounts:dashboard')

    total_applicants = Applicant.objects.count()
    awaiting_signature_count = Application.objects.filter(status='standby').count()
    total_housing_units = HousingUnit.objects.count()
    this_month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    approved_this_month = Application.objects.filter(
        status='awarded',
        updated_at__gte=this_month_start,
    ).count()

    today = timezone.localdate()
    active_queue_today = QueueEntry.objects.filter(status='active', entered_at__date=today).count()
    active_queue_total = QueueEntry.objects.filter(status='active').count()
    queue_today = active_queue_today if active_queue_today else active_queue_total

    incomplete_requirements = Applicant.objects.filter(_applicant_missing_intake_doc_q()).count()
    pending_cdrrmo_count = CDRRMOCertification.objects.filter(status='pending').count()
    vacant_units = HousingUnit.objects.filter(status='Vacant — available').select_related('site').order_by(
        'site__code', 'block_number', 'lot_number'
    )[:40]
    available_lots = [
        {
            'block': u.block_number,
            'lot': u.lot_number,
            'site': u.site.code,
            'label': str(u),
        }
        for u in vacant_units
    ]
    lots_for_awarding = len(available_lots)

    priority_queue = list(
        QueueEntry.objects.filter(status='active', queue_type='priority')
        .select_related('applicant')
        .order_by('position')[:25]
    )
    # Only `priority` exists in QUEUE_TYPE_CHOICES today; keep empty until walk-in queue is modeled.
    walkin_queue = []

    pending_cdrrmo = list(
        CDRRMOCertification.objects.filter(status='pending')
        .select_related('applicant')
        .order_by('-requested_at')[:20]
    )

    requirements_checklist = []
    for app in (
        Applicant.objects.filter(_applicant_missing_intake_doc_q())
        .order_by('-created_at')[:20]
    ):
        dc = _applicant_intake_docs_done_count(app)
        requirements_checklist.append(
            {
                'full_name': app.full_name,
                'reference_number': app.reference_number,
                'docs_count': dc,
                'completion_percent': int(round((dc / 7) * 100)),
            }
        )

    standby_queue = list(
        Application.objects.filter(status='standby').select_related('applicant').order_by('updated_at')[:40]
    )

    blacklist_count = UnitsBlacklist.objects.count()
    repossessed_count = HousingUnit.objects.filter(status='Repossessed').count()
    awaiting_reaward = Application.objects.filter(status='standby').count()

    standby_count = len(standby_queue)
    available_count = len(available_lots)
    ready_to_award = min(standby_count, available_count)

    context = {
        'page_title': 'Fourth Member Dashboard',
        'user_position': 'fourth_member',
        'total_applicants': total_applicants,
        'awaiting_signature': awaiting_signature_count,
        'housing_units': total_housing_units,
        'approved_this_month': approved_this_month,
        'queue_today': queue_today,
        'incomplete_requirements': incomplete_requirements,
        'pending_cdrrmo_stat': pending_cdrrmo_count,
        'lots_for_awarding': lots_for_awarding,
        'priority_queue': priority_queue,
        'walkin_queue': walkin_queue,
        'pending_cdrrmo': pending_cdrrmo,
        'requirements_checklist': requirements_checklist,
        'standby_queue': standby_queue,
        'available_lots': available_lots,
        'blacklist_count': blacklist_count,
        'repossessed_count': repossessed_count,
        'awaiting_reaward': awaiting_reaward,
        'ready_to_award': ready_to_award,
    }

    return render(request, 'accounts/dashboard.html', context)


@login_required
def dashboard_caretaker(request):
    """Legacy URL name; field desk (ronda / field) redirects to the field dashboard."""
    if request.user.position not in FIELD_DESK_POSITIONS:
        messages.error(request, 'Access denied.')
        return redirect('accounts:dashboard')
    return redirect('accounts:dashboard_field')


@login_required
def dashboard_field(request):
    """
    Unified field desk: Ronda (includes on-site / caretaker duties) and Field personnel.
    Channel B danger-zone field verification (CDRRMO) after Module 2 handoff.
    """
    if request.user.position not in FIELD_DESK_POSITIONS:
        messages.error(
            request,
            'Access denied. This dashboard is for field desk staff (Ronda or Field) only.',
        )
        return redirect('accounts:dashboard')

    # ==================== CHANNEL B FIELD VERIFICATION ====================
    # Pending danger zone verifications after intake staff proceeded the record to Archives.
    # Filter:
    # 1. CDRRMOCertification status='pending' (needs field verification)
    # 2. Applicant claimed danger zone (danger_zone_type is not empty)
    # 3. Applicant is income eligible (monthly_income <= 10,000)
    # 4. Applicant has an Intake Archive row (Proceed → LIST OF APPLICATIONS)
    # 5. Applicant is in pending_cdrrmo stage
    pending_certifications = CDRRMOCertification.objects.filter(
        status='pending',
        applicant__danger_zone_type__isnull=False,  # Claimed danger zone
        applicant__monthly_income__lte=10000,  # Income eligible
        applicant__module2_handoff_at__isnull=False,  # Staff clicked Proceed to Module 2
        applicant__status='pending_cdrrmo',
    ).exclude(
        applicant__danger_zone_type=''  # Empty string means not claimed
    ).distinct().select_related(
        'applicant', 'applicant__registered_by', 'applicant__barangay'
    ).order_by('-requested_at')

    pending_cert_list = list(pending_certifications)
    total_pending_certs = len(pending_cert_list)
    # Oldest certification request first — useful field visit order before a QueueEntry exists
    visit_order_by_applicant_id = {}
    for order, c in enumerate(
        sorted(pending_cert_list, key=lambda x: x.requested_at),
        start=1,
    ):
        visit_order_by_applicant_id[c.applicant_id] = order

    pending_verifications = []
    for cert in pending_cert_list:
        days_pending = (timezone.now() - cert.requested_at).days

        # Priority QueueEntry is only created after eligibility / CDRRMO staff steps — not at registration.
        # Show assigned priority number when present; otherwise show FIFO field-visit order among pending cases.
        queue_entry = cert.applicant.queue_entries.filter(status='active').first()
        if queue_entry:
            queue_position = f'Priority no. {queue_entry.position}'
        else:
            visit_n = visit_order_by_applicant_id.get(cert.applicant_id, 0)
            queue_position = (
                f'Pre-assignment · field visit order {visit_n} of {total_pending_certs}'
                if total_pending_certs
                else 'Pre-assignment'
            )

        pending_verifications.append({
            'index': pending_certifications.filter(requested_at__gte=cert.requested_at).count(),
            'id': cert.applicant.id,
            'transaction_id': cert.id,
            'reference_number': cert.applicant.reference_number,
            'applicant_name': cert.applicant.full_name,
            'address': cert.applicant.current_address,
            'barangay': cert.applicant.barangay,
            'phone': cert.applicant.phone_number,
            'household_members': cert.applicant.household_member_count,
            'monthly_income': cert.applicant.monthly_income,
            'danger_zone_type': cert.applicant.danger_zone_type,
            'danger_zone_location': cert.applicant.danger_zone_location,
            'channel': 'Channel B — Danger Zone',
            'eligibility': 'Eligible to Proceed',  # All showing in this view are eligible
            'queue_position': queue_position,
            'staff_handled': cert.applicant.registered_by.get_full_name() if cert.applicant.registered_by else '—',
            'staff_position': cert.applicant.registered_by.get_position_display() if cert.applicant.registered_by else '—',
            'sms_status': '✓ Sent' if cert.applicant.registration_sms_sent else '✗ Not Sent',
            'created_at': cert.requested_at,
            'days_pending': days_pending,
        })

    total_pending = len(pending_verifications)

    # Breakdown by staff who registered them
    staff_workload = {}
    for cert in pending_verifications:
        staff_name = cert['staff_handled']
        if staff_name not in staff_workload:
            staff_workload[staff_name] = 0
        staff_workload[staff_name] += 1

    # Certified vs Not Certified tallies
    certified_count = CDRRMOCertification.objects.filter(
        status='certified'
    ).count()

    not_certified_count = CDRRMOCertification.objects.filter(
        status='not_certified'
    ).count()

    # Aging verifications (pending > 7 days)
    seven_days_ago = timezone.now() - timedelta(days=7)
    aging_certifications = CDRRMOCertification.objects.filter(
        status='pending',
        requested_at__lt=seven_days_ago
    ).select_related('applicant').order_by('-requested_at')

    aging_verifications = []
    for cert in aging_certifications:
        aging_verifications.append({
            'applicant': cert.applicant,
            'days_pending': (timezone.now() - cert.requested_at).days,
        })

    aging_count = len(aging_verifications)

    # Team workload (field desk roles; ronda subsumes former caretaker)
    FIELD_TEAM_SIZE = 3
    avg_per_member = int(total_pending / FIELD_TEAM_SIZE) if total_pending > 0 else 0

    # Completed today (verifications completed today)
    today = timezone.now().date()
    completed_today = CDRRMOCertification.objects.filter(
        status__in=['certified', 'not_certified'],
        certified_at__date=today
    ).count()

    team_workload = {
        'pending': total_pending,
        'avg_per_member': avg_per_member,
        'completed_today': completed_today,
    }

    # Success rate (verified as danger zone / total processed)
    total_processed = certified_count + not_certified_count
    if total_processed > 0:
        verified_percentage = int((certified_count / total_processed) * 100)
    else:
        verified_percentage = 0

    # Certified applicants log (for clickable Success Rate drilldown)
    certified_applicants = []
    for cert in CDRRMOCertification.objects.filter(
        status='certified'
    ).select_related('applicant', 'result_recorded_by').order_by('-certified_at')[:100]:
        certified_applicants.append({
            'full_name': cert.applicant.full_name,
            'address': cert.applicant.current_address,
            'danger_zone_type': cert.applicant.danger_zone_type,
            'certified_at': cert.certified_at,
            'recorded_by': cert.result_recorded_by.get_full_name() if cert.result_recorded_by else '—',
        })

    # Today's summary: certifications recorded today + photos uploaded today
    today_certs_qs = CDRRMOCertification.objects.filter(
        status__in=['certified', 'not_certified'],
        certified_at__date=today,
    ).select_related('applicant', 'result_recorded_by').order_by('-certified_at')

    today_photo_uploads_qs = FieldVerificationPhoto.objects.filter(
        uploaded_at__date=today,
    ).select_related('certification__applicant', 'uploaded_by')

    photo_counts_today = {}
    for ph in today_photo_uploads_qs:
        ap_id = ph.certification.applicant_id
        photo_counts_today[ap_id] = photo_counts_today.get(ap_id, 0) + 1

    today_summary = []
    seen_applicants = set()
    for cert in today_certs_qs:
        seen_applicants.add(cert.applicant_id)
        today_summary.append({
            'full_name': cert.applicant.full_name,
            'address': cert.applicant.current_address,
            'status': cert.status,
            'status_label': cert.get_status_display(),
            'certified_at': cert.certified_at,
            'recorded_by': cert.result_recorded_by.get_full_name() if cert.result_recorded_by else '—',
            'photos_today': photo_counts_today.get(cert.applicant_id, 0),
        })

    # Include applicants who only had photos uploaded today (no certification recorded yet)
    for ph in today_photo_uploads_qs:
        ap_id = ph.certification.applicant_id
        if ap_id in seen_applicants:
            continue
        seen_applicants.add(ap_id)
        today_summary.append({
            'full_name': ph.certification.applicant.full_name,
            'address': ph.certification.applicant.current_address,
            'status': ph.certification.status,
            'status_label': ph.certification.get_status_display(),
            'certified_at': None,
            'recorded_by': ph.uploaded_by.get_full_name() if ph.uploaded_by else '—',
            'photos_today': photo_counts_today.get(ap_id, 0),
        })

    today_summary_counts = {
        'recorded': len([r for r in today_summary if r['certified_at']]),
        'photo_only': len([r for r in today_summary if not r['certified_at']]),
        'photos': sum(photo_counts_today.values()),
    }

    context = {
        'page_title': 'Field Operations Dashboard',
        'user_position': request.user.position,

        # ========== MODULE 1: VERIFICATION METRICS ==========
        'total_pending': total_pending,
        'certified_count': certified_count,
        'not_certified_count': not_certified_count,

        # ========== TEAM WORKLOAD ==========
        'team_workload': team_workload,
        'staff_workload': staff_workload,

        # ========== AGING VERIFICATIONS ==========
        'aging_verifications': aging_verifications,
        'aging_count': aging_count,

        # ========== PENDING VERIFICATIONS LIST ==========
        'pending_verifications': pending_verifications,

        # ========== VERIFICATION SUMMARY ==========
        'verified_percentage': verified_percentage,
        'certified_applicants': certified_applicants,
        'today_summary': today_summary,
        'today_summary_counts': today_summary_counts,
    }
    return render(request, 'accounts/field/dashboard.html', context)





# Legacy view for backward compatibility - now just redirects
@login_required
def dashboard_view(request):
    """Legacy dashboard view - redirects to position-specific dashboard."""
    return dashboard_redirect(request)


@login_required
def applicants_list(request):
    """
    Module 1: ISF Registration - Applicant Intake
    Accessible to: Second Member (Joie), Fourth Member (Jocel)
    """
    allowed_positions = ['second_member', 'fourth_member']
    if request.user.position not in allowed_positions:
        messages.error(request, 'Access denied. This module is for Second and Fourth Members only.')
        return redirect('accounts:dashboard')
    
    # Mock data - matching the React mockApplicants structure
    mock_applicants = [
        {
            'id': 1,
            'fullName': 'Dela Cruz, Maria Santos',
            'referenceNumber': 'THA-2024-00123',
            'dateRegistered': '2024-01-15',
            'channel': 'A',
            'barangay': 'Poblacion',
            'monthlyIncome': 8500,
            'householdSize': 5,
            'yearsResiding': 12,
            'eligibilityStatus': 'Eligible',
            'queueType': 'Priority',
            'queuePosition': 3,
            'applicationStage': 'Requirements Submission',
            'cdrrmoStatus': None,
            'dangerZoneType': None,
            'isCdrrmoFlagged': False,
            'signatoryRoutingDelayed': False,
            'disqualificationReason': None,
            'documents': {
                'barangayCertResidency': True,
                'barangayCertIndigency': True,
                'cedula': True,
                'policeClearance': False,
                'certNoProperty': True,
                'picture2x2': True,
                'sketchHouseLocation': False
            },
            'lotAssignment': None,
        },
        {
            'id': 2,
            'fullName': 'Santos, Juan Pedro',
            'referenceNumber': 'THA-2024-00045',
            'dateRegistered': '2023-11-20',
            'channel': 'B',
            'barangay': 'Cabatangan',
            'monthlyIncome': 7200,
            'householdSize': 4,
            'yearsResiding': 8,
            'eligibilityStatus': 'Pending CDRRMO',
            'queueType': 'None',
            'queuePosition': None,
            'applicationStage': 'Awaiting Certification',
            'cdrrmoStatus': 'Pending',
            'dangerZoneType': 'Riverside',
            'isCdrrmoFlagged': True,
            'signatoryRoutingDelayed': False,
            'disqualificationReason': None,
            'documents': {
                'barangayCertResidency': True,
                'barangayCertIndigency': True,
                'cedula': True,
                'policeClearance': True,
                'certNoProperty': True,
                'picture2x2': True,
                'sketchHouseLocation': True
            },
            'lotAssignment': None,
        },
        {
            'id': 3,
            'fullName': 'Reyes, Ana Marie',
            'referenceNumber': 'THA-2024-00087',
            'dateRegistered': '2024-02-01',
            'channel': 'C',
            'barangay': 'Tabunoc',
            'monthlyIncome': 9200,
            'householdSize': 3,
            'yearsResiding': 5,
            'eligibilityStatus': 'Eligible',
            'queueType': 'Walk-in',
            'queuePosition': 12,
            'applicationStage': 'Queue',
            'cdrrmoStatus': None,
            'dangerZoneType': None,
            'isCdrrmoFlagged': False,
            'signatoryRoutingDelayed': False,
            'disqualificationReason': None,
            'documents': {
                'barangayCertResidency': True,
                'barangayCertIndigency': True,
                'cedula': True,
                'policeClearance': True,
                'certNoProperty': True,
                'picture2x2': True,
                'sketchHouseLocation': True
            },
            'lotAssignment': None,
        },
        {
            'id': 4,
            'fullName': 'Garcia, Roberto Luis',
            'referenceNumber': 'THA-2024-00198',
            'dateRegistered': '2024-01-05',
            'channel': 'A',
            'barangay': 'Dumlog',
            'monthlyIncome': 15000,
            'householdSize': 6,
            'yearsResiding': 15,
            'eligibilityStatus': 'Disqualified',
            'queueType': 'None',
            'queuePosition': None,
            'applicationStage': 'Eligibility Check',
            'cdrrmoStatus': None,
            'dangerZoneType': None,
            'isCdrrmoFlagged': False,
            'signatoryRoutingDelayed': False,
            'disqualificationReason': 'Monthly income exceeds ₱10,000 limit',
            'documents': {
                'barangayCertResidency': False,
                'barangayCertIndigency': False,
                'cedula': False,
                'policeClearance': False,
                'certNoProperty': False,
                'picture2x2': False,
                'sketchHouseLocation': False
            },
            'lotAssignment': None,
        },
        {
            'id': 5,
            'fullName': 'Mendoza, Elena Cruz',
            'referenceNumber': 'THA-2023-00234',
            'dateRegistered': '2023-09-12',
            'channel': 'A',
            'barangay': 'Poblacion',
            'monthlyIncome': 6800,
            'householdSize': 4,
            'yearsResiding': 20,
            'eligibilityStatus': 'Eligible',
            'queueType': 'Priority',
            'queuePosition': 1,
            'applicationStage': 'Lot Awarding',
            'cdrrmoStatus': None,
            'dangerZoneType': None,
            'isCdrrmoFlagged': False,
            'signatoryRoutingDelayed': False,
            'disqualificationReason': None,
            'documents': {
                'barangayCertResidency': True,
                'barangayCertIndigency': True,
                'cedula': True,
                'policeClearance': True,
                'certNoProperty': True,
                'picture2x2': True,
                'sketchHouseLocation': True
            },
            'lotAssignment': {
                'block': 'A',
                'lot': '5',
                'site': 'GK Cabatangan',
                'dateAwarded': '2024-02-15'
            },
        },
        {
            'id': 6,
            'fullName': 'Torres, Miguel Angel',
            'referenceNumber': 'THA-2024-00067',
            'dateRegistered': '2024-01-22',
            'channel': 'B',
            'barangay': 'Biasong',
            'monthlyIncome': 7500,
            'householdSize': 7,
            'yearsResiding': 10,
            'eligibilityStatus': 'Eligible',
            'queueType': 'Priority',
            'queuePosition': 5,
            'applicationStage': 'Signatory Routing',
            'cdrrmoStatus': 'Certified',
            'dangerZoneType': 'Flood-prone area',
            'isCdrrmoFlagged': False,
            'signatoryRoutingDelayed': True,
            'signatoryRoutingDelayedAt': 'OIC Signature',
            'disqualificationReason': None,
            'documents': {
                'barangayCertResidency': True,
                'barangayCertIndigency': True,
                'cedula': True,
                'policeClearance': True,
                'certNoProperty': True,
                'picture2x2': True,
                'sketchHouseLocation': True
            },
            'lotAssignment': None,
        }
    ]
    
    # Barangays list
    barangays = [
        'Biasong', 'Bulawan', 'Cabatangan', 'Cadulawan', 'Camp IV', 'Cansojong',
        'Dumlog', 'Jaclupan', 'Lagtang', 'Lawaan I', 'Lawaan II', 'Lawaan III',
        'Linao', 'Maghaway', 'Manipis', 'Mohon', 'Poblacion', 'Pooc', 'San Isidro',
        'San Roque', 'Tabunoc', 'Tanke', 'Tapul', 'Tigbao', 'Talisay City',
        'Zone 1', 'Zone 2'
    ]
    
    # Calculate stats
    total_applicants = len(mock_applicants)
    priority_count = len([a for a in mock_applicants if a['queueType'] == 'Priority'])
    walkin_count = len([a for a in mock_applicants if a['queueType'] == 'Walk-in'])
    pending_cdrrmo = len([a for a in mock_applicants if a.get('cdrrmoStatus') == 'Pending'])
    
    context = {
        'page_title': 'ISF Registration',
        'user_position': request.user.position,
        'applicants': mock_applicants,
        'applicants_json': json.dumps(mock_applicants),
        'barangays': barangays,
        'stats': {
            'total': total_applicants,
            'priority': priority_count,
            'walkin': walkin_count,
            'pending_cdrrmo': pending_cdrrmo
        }
    }
    
    return render(request, 'accounts/applicants.html', context)


# ==================== OIC-SPECIFIC VIEWS ====================

