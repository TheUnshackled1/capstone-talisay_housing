import calendar
import csv
import json
import secrets
import urllib.request as _drive_urlreq

from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_GET
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Count, F, Q, Prefetch
from django.urls import reverse
from django.contrib.sessions.models import Session
from django.contrib.auth import get_user_model
from django.utils.http import url_has_allowed_host_and_scheme
from django.core.cache import cache
from datetime import date, datetime, timedelta
from urllib.parse import urlencode

from allauth.account.internal.decorators import login_not_required
from allauth.socialaccount.adapter import get_adapter
from allauth.socialaccount.providers.base.constants import AuthProcess

from .auth_oauth import google_oauth_configured
from .forms import LoginForm
from .models import FIELD_INSPECTOR_POSITIONS
from .auth_portal import (
    PORTAL_ROLE_SESSION_KEY,
    is_valid_portal_role,
    normalize_portal_role,
    portal_role_display,
    portal_role_for_position,
    remember_portal_role_cookie,
    resolve_login_portal_role,
    user_allowed_for_portal,
)
from intake.models import Applicant, Archive, SMSLog
from applications.models import CDRRMOCertification, FieldVerificationPhoto
from applications.views import module2_ready_for_form_queue_rows
from units.models import Blacklist as UnitsBlacklist
from applications.models import QueueEntry, Application
from documents.models import Document, RequirementSubmission
from units.models import HousingUnit, LotAward, ConstructionProgress, RelocationSite
from units.isf_population import isf_population_stats, resolve_isf_population_site
from cases.models import Case


def _redirect_login_preserving_role(request, role: str | None = None):
    """Return to login; keep ?role= so the portal badge and rules stay in sync after a failed check."""
    resolved = normalize_portal_role(role or request.GET.get('role', '') or resolve_login_portal_role(request))
    if resolved:
        return redirect(f"{reverse('accounts:login')}?{urlencode({'role': resolved})}")
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

    role = resolve_login_portal_role(request)
    role_display = portal_role_display(role)

    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']

            user = authenticate(request, username=username, password=password)

            if user is not None:
                allowed, err = user_allowed_for_portal(user, role)
                if not allowed:
                    messages.error(request, err)
                    return _redirect_login_preserving_role(request, role=role)

                login(request, user)
                if role:
                    request._ihsms_save_portal_role = role
                messages.success(request, f'Welcome back, {user.first_name or user.username}!')
                next_url = request.GET.get('next')
                if next_url and url_has_allowed_host_and_scheme(
                    next_url,
                    allowed_hosts={request.get_host()},
                    require_https=request.is_secure(),
                ):
                    response = redirect(next_url)
                else:
                    response = redirect('accounts:dashboard')
                if role:
                    remember_portal_role_cookie(response, role)
                return response
            else:
                messages.error(request, 'Invalid username or password.')
        else:
            messages.error(request, 'Please enter both username and password.')
    else:
        form = LoginForm()

    response = render(request, 'staff/login.html', {
        'form': form,
        'role': role,
        'role_display': role_display,
    })
    if role:
        remember_portal_role_cookie(response, role)
    return response


@login_not_required
def google_login_start(request):
    """Validate portal role and start Google OAuth in a single hop.

    Previously two views with a redirect between them; merged to cut one
    full HTTP round-trip before Google sees the request.
    """
    role = normalize_portal_role(request.GET.get('role', '') or request.GET.get('portal_role', ''))
    if not is_valid_portal_role(role):
        messages.error(request, 'Select your staff portal before signing in with Google.')
        return redirect('accounts:login')

    # Cache the SocialApp existence check — it almost never changes at runtime.
    # TTL: 1 hour — SocialApp rows only change via admin commands, not at runtime.
    _oauth_ok = cache.get('google_oauth_configured')
    if _oauth_ok is None:
        _oauth_ok = google_oauth_configured()
        cache.set('google_oauth_configured', _oauth_ok, 3600)  # 1-hour TTL
    if not _oauth_ok:
        messages.error(
            request,
            'Google sign-in is not set up. Ask an administrator to run: '
            'python manage.py setup_google_oauth',
        )
        return redirect(f"{reverse('accounts:login')}?{urlencode({'role': role})}")

    provider = get_adapter().get_provider(request, 'google')
    return provider.redirect(request, process=AuthProcess.LOGIN, portal_role=role)


@login_not_required
def tha_google_oauth_login(request):
    """Legacy entry point kept for backward-compat with allauth URL wiring.

    Delegates to google_login_start so the single-hop optimisation applies
    whether allauth or our own URL triggers this flow.
    """
    return google_login_start(request)


def logout_view(request):
    """Log out and return to the portal login page."""
    role = ''
    if request.user.is_authenticated:
        role = portal_role_for_position(request.user.position)
    logout(request)
    messages.info(request, 'You have been logged out.')
    params = {}
    if role:
        params['role'] = role
    login_url = reverse('accounts:login')
    if params:
        login_url = f'{login_url}?{urlencode(params)}'
    return redirect(login_url)


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
        'second_member': 'accounts:dashboard_second_member',
        'fourth_member': 'accounts:dashboard_fourth_member',
        'ronda': 'accounts:dashboard_field',
        'field': 'accounts:dashboard_field',
    }
    
    # Get URL for user's position, default to field dashboard
    url_name = position_urls.get(position, 'accounts:dashboard_field')
    return redirect(url_name)


@login_required
def dashboard_second_member(request):
    """
    Dashboard for Second Member (Lourynie Joie V. Tingson)
    Responsibilities: M2 (notices), M3 (docs), M4 (compliance), M6 (reports)
    """
    if request.user.position != 'second_member':
        messages.error(request, 'Access denied. This dashboard is for the Second Member position only.')
        return redirect('accounts:dashboard')

    _force_refresh = request.GET.get('refresh') == '1'

    # Analytics payload — cached for 10 minutes (shared across Railway dynos via
    # DatabaseCache). Previously caused a ~14s cold hit per worker; now computed once.
    _cache_key = (
        f"dashboard_analytics_second_member"
        f"_{request.GET.get('year', 'all')}"
        f"_{request.GET.get('month', 'all')}"
        f"_{request.GET.get('site_id', '')}"
    )
    analytics_data = None if _force_refresh else cache.get(_cache_key)
    if analytics_data is None:
        analytics_data = _staff_reports_analytics_payload(request)
        cache.set(_cache_key, analytics_data, 600)  # 10-minute TTL (shared via DatabaseCache)

    # CSV export — works via ?export=csv on the dashboard URL
    if request.GET.get('export') == 'csv':
        return _staff_reports_analytics_csv_response(
            analytics_data, 'Second Member', 'second_member_report'
        )

    # Pull counts from the already-computed analytics payload — no extra DB queries.
    incomplete_docs_count = analytics_data.get('incomplete_docs', 0)
    total_applicants = analytics_data.get('total_applications', 0)
    awaiting_signature_count = analytics_data.get('pending_final_signature_count', 0)
    total_housing_units = analytics_data.get('housing_units_total', 0)
    approved_this_month = analytics_data.get('approved_this_month', 0)
    cases_total = analytics_data.get('cases_total', 0)

    # ===== MODULE 3: DOCUMENT OVERSIGHT — cached 2 min to avoid per-load DB hit =====
    _alerts_cache_key = 'dashboard_second_member_doc_alerts'
    doc_completeness_alerts = None if _force_refresh else cache.get(_alerts_cache_key)
    if doc_completeness_alerts is None:
        incomplete_module1_qs = (
            Applicant.objects.filter(_applicant_missing_intake_doc_q())
            .only(
                'full_name', 'reference_number',
                'doc_brgy_residency', 'doc_brgy_indigency', 'doc_cedula',
                'doc_police_clearance', 'doc_no_property', 'doc_2x2_picture',
                'doc_sketch_location',
            )
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
        cache.set(_alerts_cache_key, doc_completeness_alerts, 120)  # 2-minute TTL

    # ==================== MODULE 6: UPCOMING REPORTS (Reports for Full Disclosure Portal) ====================
    reports_to_generate = []
    today = date.today()
    if today.day == 1:  # 1st of the month — Monthly Compliance Summary is due today
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

    context = {
        'page_title': 'Second Member Dashboard',
        'user_position': 'second_member',
        'cases_total': cases_total,
        'incomplete_docs': incomplete_docs_count,
        'doc_completeness_alerts': doc_completeness_alerts[:10],
        'reports_to_generate': reports_to_generate,
        'total_applicants': total_applicants,
        'awaiting_signature': awaiting_signature_count,
        'housing_units': total_housing_units,
        'approved_this_month': approved_this_month,
        **analytics_data,
    }

    return render(request, 'staff/dashboard.html', context)


def _report_month_bounds(year: int, month: int):
    """First and last instant of calendar month in the active timezone."""
    tz = timezone.get_current_timezone()
    start = datetime(year, month, 1, 0, 0, 0, tzinfo=tz)
    last_day = calendar.monthrange(year, month)[1]
    end = datetime(year, month, last_day, 23, 59, 59, 999999, tzinfo=tz)
    return start, end


def _report_year_bounds(year: int):
    """First and last instant of calendar year in the active timezone."""
    tz = timezone.get_current_timezone()
    start = datetime(year, 1, 1, 0, 0, 0, tzinfo=tz)
    end = datetime(year, 12, 31, 23, 59, 59, 999999, tzinfo=tz)
    return start, end


def _parse_analytics_period(request, now=None):
    """
    Resolve dashboard ?year=&month= filter.

    - no params / year=all → all-time
    - year=Y & month=all (or missing month) → full calendar year Y
    - year=Y & month=M → that calendar month
    """
    if now is None:
        now = timezone.localtime(timezone.now())

    year_param = (request.GET.get('year') or '').strip()
    month_param = (request.GET.get('month') or '').strip()

    # Default / All Year
    if not year_param or year_param == 'all':
        period_start = now.replace(year=2000, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        return {
            'report_year': 'all',
            'report_month': 'all',
            'period_start': period_start,
            'period_end': now,
            'period_label': 'All Year',
            'filter_active': False,
        }

    try:
        report_year = int(year_param)
    except (TypeError, ValueError):
        report_year = now.year
    report_year = max(2000, min(report_year, 2100))

    # Full year when month is omitted or explicitly "all"
    if not month_param or month_param == 'all':
        period_start, period_end = _report_year_bounds(report_year)
        if report_year == now.year:
            period_end = min(period_end, now)
        return {
            'report_year': report_year,
            'report_month': 'all',
            'period_start': period_start,
            'period_end': period_end,
            'period_label': str(report_year),
            'filter_active': True,
        }

    try:
        report_month = int(month_param)
    except (TypeError, ValueError):
        report_month = now.month
    report_month = max(1, min(report_month, 12))
    period_start, period_end = _report_month_bounds(report_year, report_month)
    return {
        'report_year': report_year,
        'report_month': report_month,
        'period_start': period_start,
        'period_end': period_end,
        'period_label': f'{calendar.month_name[report_month]} {report_year}',
        'filter_active': True,
    }


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


def _staff_analytics_module2_counts(user):
    """
    Returns (evaluation_count, ready_for_form_count, evaluation_ids, ready_for_form_ids)
    using pure SQL aggregates — no Python iteration over rows.

    Previously a Python for-loop with full prefetches (documents, household_members,
    eligibility_check_decisions, cdrrmo_certification__field_photos) caused ~14s on Railway.

    SQL translation of _module2_on_ready_for_form_queue_track:
      RFQ = form_queue_routed_at IS NOT NULL
            AND (application IS NULL OR application.status IN ('draft', 'completed'))
    SQL translation of the eval exclusion:
      EXCLUDED = form_queue_routed_at IS NOT NULL AND application.status IN ('standby', 'awarded')
    """
    from applications.views import _module2_evaluations_applicants_queryset

    _MODULE2_FORM_PIPELINE_STATUSES = frozenset({'draft', 'completed'})
    _ROUTED_REMOVED_STATUSES = frozenset({'standby', 'awarded'})

    # Lean base queryset — clear ALL prefetches and reset select_related to only
    # the application join. The base queryset carries barangay/cdrrmo/registered_by
    # joins that are useless here and add unnecessary SQL LEFT JOINs.
    base_qs = (
        _module2_evaluations_applicants_queryset()
        .prefetch_related(None)
        .select_related(None)
        .select_related('application')
    )

    # Fetch just PKs and the two fields we need — one DB round-trip, no model instances
    rows = list(base_qs.values('id', 'form_queue_routed_at', 'application__status'))

    rfq_ids = []
    eval_ids = []
    for row in rows:
        routed = row['form_queue_routed_at']
        app_status = (row['application__status'] or '').strip()
        if routed:
            if not app_status or app_status in _MODULE2_FORM_PIPELINE_STATUSES:
                rfq_ids.append(row['id'])
                continue  # mirrors applications_list.html: rfq removed from list
            if app_status in _ROUTED_REMOVED_STATUSES:
                continue  # mirrors applications_list.html: awarded/standby routed removed
        eval_ids.append(row['id'])

    return len(eval_ids), len(rfq_ids), eval_ids, rfq_ids



def _staff_analytics_ready_for_form_count(user):
    """Kept for backward compatibility — returns only the ready-for-form count."""
    res = _staff_analytics_module2_counts(user)
    return res[1]


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
    case_aging_bands=None,
    funnel_stages=None,
    isf_population_data=None,
    voter_registration_counts=None,
    blacklist_by_reason=None,
    construction_stages=None,
):
    """
    Build a JSON-serializable dict for Chart.js (staff analytics page).
    Keeps labels readable and aligned with the same queries as the tables.
    """

    def pair_labels_counts(rows, label_key='label', count_key='count'):
        labels = [_chart_label(r.get(label_key)) for r in rows]
        values = [int(r.get(count_key) or 0) for r in rows]
        res = {'labels': labels, 'values': values}
        if any('breakdown' in r for r in rows):
            res['breakdowns'] = [r.get('breakdown') or {} for r in rows]
        return res

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
    if case_aging_bands:
        data['caseAging'] = {
            'labels': list(case_aging_bands.keys()),
            'values': list(case_aging_bands.values()),
        }
    if funnel_stages:
        data['workflowFunnel'] = pair_labels_counts(funnel_stages)

    # ISF Population data
    if isf_population_data:
        data['isfPopulation'] = {
            'labels': ['Male', 'Female'],
            'values': [
                int(isf_population_data.get('male_household', 0)),
                int(isf_population_data.get('female_household', 0))
            ]
        }
        # ISF Overall - comprehensive breakdown
        data['isfOverall'] = {
            'labels': [
                'Total Beneficiaries',
                'Total Population',
            ],
            'values': [
                int(isf_population_data.get('total_isf', 0)),
                int(isf_population_data.get('total_population', 0))
            ]
        }

    # Voter registration status breakdown
    if voter_registration_counts:
        data['voterRegistration'] = {
            'labels': ['Registered Voter', 'Not Registered'],
            'values': [
                int(voter_registration_counts.get('registered', 0)),
                int(voter_registration_counts.get('not_registered', 0)),
            ]
        }

    # Blacklist breakdown by reason (real DB data)
    if blacklist_by_reason is not None:
        data['blacklistByReason'] = pair_labels_counts(blacklist_by_reason)

    # Construction progress stages
    if construction_stages:
        data['constructionProgress'] = {
            'labels': ['Not Started', 'In Progress', 'Completed', 'Delayed'],
            'values': [
                int(construction_stages.get('not_started', 0)),
                int(construction_stages.get('in_progress', 0)),
                int(construction_stages.get('completed', 0)),
                int(construction_stages.get('delayed', 0)),
            ]
        }

    return data


def _calculate_analytics_enhancements(data):
    """
    Enhance analytics data with:
    - Efficiency metrics (conversion rates, completion %)
    - Trend indicators (↑ ↓ for improvement/decline)
    - Status colors for visual alerts
    """
    enhancements = {}

    # 1. Pipeline completion rates
    total_applicants = data.get('total_applications', 0)
    awarded_applicants = sum([row.get('count', 0) for row in data.get('applicants_by_channel', []) if row.get('status') == 'awarded'])

    if total_applicants > 0:
        enhancements['pipeline_completion_pct'] = int((awarded_applicants / total_applicants) * 100)
    else:
        enhancements['pipeline_completion_pct'] = 0

    # 2. Document upload rate
    housing_apps = data.get('housing_application_records', 0)
    docs_uploaded = data.get('docs_filed', 0)
    if housing_apps > 0:
        enhancements['doc_upload_rate_pct'] = min(100, int((docs_uploaded / housing_apps / 10) * 100))  # Assuming ~10 docs per app
    else:
        enhancements['doc_upload_rate_pct'] = 0

    # 3. Requirement verification rate
    req_verified = data.get('requirements_verified_period', 0)
    req_submitted = data.get('requirement_submissions_submitted_period', 0)
    if req_submitted > 0:
        enhancements['requirement_fulfilment_pct'] = int((req_verified / req_submitted) * 100)
    else:
        enhancements['requirement_fulfilment_pct'] = 0

    # 4. Housing occupancy health
    occupancy_rate = data.get('housing_occupancy_rate', 0)
    if occupancy_rate >= 80:
        enhancements['occupancy_status'] = 'excellent'
        enhancements['occupancy_status_color'] = '#10b981'
    elif occupancy_rate >= 60:
        enhancements['occupancy_status'] = 'good'
        enhancements['occupancy_status_color'] = '#0ea5e9'
    elif occupancy_rate >= 40:
        enhancements['occupancy_status'] = 'fair'
        enhancements['occupancy_status_color'] = '#f59e0b'
    else:
        enhancements['occupancy_status'] = 'low'
        enhancements['occupancy_status_color'] = '#ef4444'

    # 5. Bottleneck identification
    incomplete_docs = data.get('incomplete_docs', 0)
    pending_final_signature = data.get('pending_final_signature_count', 0)
    stale_cases = data.get('stale_cases_count', 0)

    bottlenecks = []
    if incomplete_docs > 5:
        bottlenecks.append({'issue': 'incomplete_docs', 'count': incomplete_docs, 'severity': 'high'})
    if pending_final_signature > 10:
        bottlenecks.append({'issue': 'pending_final_signature', 'count': pending_final_signature, 'severity': 'high'})
    if stale_cases > 3:
        bottlenecks.append({'issue': 'stale_cases', 'count': stale_cases, 'severity': 'medium'})

    enhancements['bottlenecks'] = bottlenecks
    enhancements['has_critical_issues'] = len([b for b in bottlenecks if b['severity'] == 'high']) > 0

    # 6. Case resolution efficiency
    opened_period = data.get('cases_opened_period', 0)
    closed_period = data.get('cases_closed_period', 0)
    if opened_period > 0:
        enhancements['case_resolution_rate'] = int((closed_period / opened_period) * 100) if opened_period > 0 else 0
    else:
        enhancements['case_resolution_rate'] = 0

    # 7. Staff workload metrics
    req_verification_rate = data.get('req_verification_rate', 0)
    lot_awards = data.get('awarded_transition_period', 0)

    enhancements['verification_status'] = 'on_track' if req_verification_rate >= 80 else 'behind'
    enhancements['lot_award_momentum'] = 'positive' if lot_awards > 2 else 'needs_attention'

    return enhancements


def _get_session_monitoring_data():
    """
    Lightweight session stats for dashboard context keys.

    The previous implementation ran 24+ hourly ``Session`` counts and decoded
    session rows on every Second/Fourth Member dashboard load. With a restored
    ``django_session`` table that aborted gunicorn (WORKER TIMEOUT) on Railway.
    Templates do not render these fields today — keep cheap placeholders + a
    few aggregate counts only.
    """
    now = timezone.now()
    active_count = Session.objects.filter(expire_date__gte=now).count()
    total_sessions = Session.objects.count()
    return {
        'total_sessions': total_sessions,
        'active_sessions': active_count,
        'expired_sessions': max(total_sessions - active_count, 0),
        'sessions_24h': Session.objects.filter(expire_date__gte=now - timedelta(hours=24)).count(),
        'sessions_7d': Session.objects.filter(expire_date__gte=now - timedelta(days=7)).count(),
        'active_user_sessions': [],
        'login_trend': [],
        'expiring_soon': 0,
        'peak_hour': 'N/A',
        'peak_count': 0,
    }


def _staff_reports_analytics_payload(request):
    """
    Shared datasets for Second / Fourth Member reporting (same analytics scope).

    Returns a dict suitable for ``staff_reports_analytics.html`` and CSV export.
    """
    now = timezone.localtime(timezone.now())
    period = _parse_analytics_period(request, now=now)
    report_year = period['report_year']
    report_month = period['report_month']
    period_start = period['period_start']
    period_end = period['period_end']
    period_label = period['period_label']
    filter_active = period['filter_active']

    doc_type_labels = dict(Document.DOCUMENT_TYPE_CHOICES)
    applicant_status_labels = dict(Applicant.STATUS_CHOICES)
    application_status_labels = dict(Application.STATUS_CHOICES)
    incomplete_docs_count = Applicant.objects.filter(_applicant_missing_intake_doc_q()).count()
    total_applicants = Applicant.objects.count()
    housing_application_records = Application.objects.count()

    # ── Smart dropdown: distinct (year, month) pairs that have real remaining data ──
    from django.db.models import Exists, OuterRef, Q
    from django.db.models.functions import ExtractYear, ExtractMonth
    from units.historical_beneficiary import HISTORICAL_BACKFILL_NOTE

    # Historical GK backfill rows with no lot award left are orphans — do not
    # keep their created_at year in the filter after the unit/beneficiary is removed.
    _has_lot_award = LotAward.objects.filter(application__applicant_id=OuterRef('pk'))
    _ap_for_periods = Applicant.objects.exclude(
        Q(application__notes__icontains=HISTORICAL_BACKFILL_NOTE) & ~Exists(_has_lot_award)
    )
    _ap_periods = (
        _ap_for_periods
        .annotate(yr=ExtractYear('created_at'), mo=ExtractMonth('created_at'))
        .values('yr', 'mo')
        .distinct()
        .order_by('yr', 'mo')
    )
    _case_periods = (
        Case.objects
        .filter(received_at__isnull=False)
        .annotate(yr=ExtractYear('received_at'), mo=ExtractMonth('received_at'))
        .values('yr', 'mo')
        .distinct()
        .order_by('yr', 'mo')
    )
    _award_periods = (
        LotAward.objects
        .annotate(yr=ExtractYear('awarded_at'), mo=ExtractMonth('awarded_at'))
        .values('yr', 'mo')
        .distinct()
        .order_by('yr', 'mo')
    )
    # Merge and deduplicate (skip null extracts from bad/empty timestamps)
    _all_periods_set = set()
    for _row in _ap_periods:
        if _row['yr'] and _row['mo']:
            _all_periods_set.add((int(_row['yr']), int(_row['mo'])))
    for _row in _case_periods:
        if _row['yr'] and _row['mo']:
            _all_periods_set.add((int(_row['yr']), int(_row['mo'])))
    for _row in _award_periods:
        if _row['yr'] and _row['mo']:
            _all_periods_set.add((int(_row['yr']), int(_row['mo'])))
    # Do NOT inject the currently selected year/month — if that data was deleted
    # (e.g. GK 2002 removed), the year must disappear from the dropdown.
    available_periods = sorted(_all_periods_set)  # list of (year, month) tuples
    available_years = sorted(set(y for y, m in available_periods))
    # Map year → list of (month_num, month_name) for that year
    available_months_by_year = {}
    for y, m in available_periods:
        available_months_by_year.setdefault(y, []).append((m, calendar.month_name[m]))
    for y in available_months_by_year:
        available_months_by_year[y] = sorted(set(available_months_by_year[y]), key=lambda t: t[0])
    # Build JSON-safe structure for JS
    available_periods_json = {
        str(y): [{'num': m, 'name': calendar.month_name[m]} for m, _ in available_months_by_year[y]]
        for y in available_years
    }

    # Raw status breakdown — kept for CSV export only
    applicant_status_raw = sorted(
        (
            Applicant.objects.values('status')
            .annotate(count=Count('id'))
            .order_by('-count')
        ),
        key=lambda x: (-x['count'], x['status'] or ''),
    )
    status_display_overrides = {
        'pending': 'Pending Eligibility',
        'application': 'Pending Application',
    }
    for row in applicant_status_raw:
        st = row.get('status') or ''
        row['label'] = status_display_overrides.get(
            st,
            applicant_status_labels.get(st, st or '—')
        )
    # applicant_by_status will be rebuilt as a pipeline list below (after ready_for_form_queue_count)
    applicant_by_status = applicant_status_raw

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
    trend_end_y = report_year if report_year != 'all' else now.year
    trend_end_m = report_month if report_month != 'all' else now.month
    # Collapse 6 sequential count() calls → 1 aggregate query with conditional counts
    _upload_six_months = _six_month_sequence_end(trend_end_y, trend_end_m)
    _upload_month_bounds = [(y, m, lbl, *_report_month_bounds(y, m)) for y, m, lbl in _upload_six_months]
    _upload_agg = Document.objects.aggregate(**{
        f'c_{y}_{m}': Count('pk', filter=Q(uploaded_at__gte=ms, uploaded_at__lte=me))
        for y, m, lbl, ms, me in _upload_month_bounds
    })
    for y, m, lbl, ms, me in _upload_month_bounds:
        c = _upload_agg.get(f'c_{y}_{m}') or 0
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

    applicants_top_barangays = list(
        Applicant.objects.exclude(barangay_id__isnull=True)
        .filter(created_at__gte=period_start, created_at__lte=period_end)
        .values(place_name=F('barangay__name'))
        .annotate(count=Count('id'))
        .order_by('-count')[:12]
    )
    for row in applicants_top_barangays:
        row['place_name'] = row.get('place_name') or '—'
    _analytics_rows_bar_pct(applicants_top_barangays)

    # ISF population — lot-awarded beneficiaries (Module 4 / GK Masterlist source)
    # When a year/month filter is active, only count awards in that period.
    isf_site, isf_site_id = resolve_isf_population_site(request.GET.get('site_id'))
    if filter_active:
        isf_population_data = isf_population_stats(
            isf_site, period_start=period_start, period_end=period_end
        )
        # Edge case: awarded applicants created in the period with no LotAward row yet
        # (e.g. legacy 2002 record) — include them so Status/ISF stay consistent.
        _awarded_in_period = list(
            Applicant.objects.filter(
                status='awarded',
                created_at__gte=period_start,
                created_at__lte=period_end,
            ).prefetch_related('household_members')
        )
        if isf_population_data.get('total_isf', 0) == 0 and _awarded_in_period:
            for ap in _awarded_in_period:
                isf_population_data['total_isf'] = int(isf_population_data.get('total_isf') or 0) + 1
                isf_population_data['awarded_units'] = int(isf_population_data.get('awarded_units') or 0) + 1
                isf_population_data['total_population'] = int(isf_population_data.get('total_population') or 0) + 1
                if ap.sex == 'M':
                    isf_population_data['male_household'] = int(isf_population_data.get('male_household') or 0) + 1
                    isf_population_data['male_count'] = int(isf_population_data.get('male_count') or 0) + 1
                elif ap.sex == 'F':
                    isf_population_data['female_household'] = int(isf_population_data.get('female_household') or 0) + 1
                    isf_population_data['female_count'] = int(isf_population_data.get('female_count') or 0) + 1
                for member in ap.household_members.all():
                    isf_population_data['total_population'] = int(isf_population_data.get('total_population') or 0) + 1
                    if member.sex == 'M':
                        isf_population_data['male_household'] = int(isf_population_data.get('male_household') or 0) + 1
                        isf_population_data['male_count'] = int(isf_population_data.get('male_count') or 0) + 1
                    elif member.sex == 'F':
                        isf_population_data['female_household'] = int(isf_population_data.get('female_household') or 0) + 1
                        isf_population_data['female_count'] = int(isf_population_data.get('female_count') or 0) + 1
    else:
        isf_population_data = isf_population_stats(isf_site)
    relocation_sites = list(
        RelocationSite.objects.filter(is_active=True).order_by('name').values('id', 'name')
    )

    intake_registration_trend = []
    reg_max = 1
    trend_end_y = report_year if report_year != 'all' else now.year
    trend_end_m = report_month if report_month != 'all' else now.month
    # Collapse 6 sequential count() calls → 1 aggregate query with conditional counts
    _reg_six_months = _six_month_sequence_end(trend_end_y, trend_end_m)
    _reg_month_bounds = [(y, m, lbl, *_report_month_bounds(y, m)) for y, m, lbl in _reg_six_months]
    _reg_agg = Applicant.objects.aggregate(**{
        f'c_{y}_{m}': Count('pk', filter=Q(created_at__gte=ms, created_at__lte=me))
        for y, m, lbl, ms, me in _reg_month_bounds
    })
    for y, m, lbl, ms, me in _reg_month_bounds:
        c = _reg_agg.get(f'c_{y}_{m}') or 0
        reg_max = max(reg_max, c)
        intake_registration_trend.append({'label': lbl, 'year': y, 'month': m, 'count': c})
    for row in intake_registration_trend:
        row['bar_pct'] = min(100, int(round(100 * row['count'] / reg_max))) if reg_max else 0

    module2_handoff_count = Applicant.objects.filter(module2_handoff_at__isnull=False).count()
    # Single pass: get both evaluation_count (matches applications_list.html Total List)
    # and ready_for_form_queue_count (matches ready_for_form_list.html) together, along with IDs.
    _evaluation_count, ready_for_form_queue_count, _eval_ids, _rfq_ids = _staff_analytics_module2_counts(request.user)
    pending_final_signature_count = Application.objects.filter(status='completed').count()

    # Pipeline-stage applicant counts — uses the EXACT same queries as each module page
    # so the dashboard numbers always match what staff see when they navigate to each section.
    from units.historical_beneficiary import intake_registration_exclude_q

    # Registered = what applicants.html (REGISTERED APPLICANTS table) shows
    _registered_ids = list(
        Archive.objects
        .filter(formally_archived=False)
        .exclude(intake_registration_exclude_q(prefix='applicant__'))
        .exclude(applicant__application__isnull=False)
        .values_list('applicant_id', flat=True)
    )
    _awarded_ids = list(Applicant.objects.filter(status='awarded').values_list('id', flat=True))

    # When a year/month filter is active, scope Status & Situation to applicants
    # created in that period so Apply Filter visibly changes the charts.
    if filter_active:
        _period_id_set = set(
            Applicant.objects.filter(
                created_at__gte=period_start,
                created_at__lte=period_end,
            ).values_list('id', flat=True)
        )
        _registered_ids = [i for i in _registered_ids if i in _period_id_set]
        _eval_ids = [i for i in _eval_ids if i in _period_id_set]
        _rfq_ids = [i for i in _rfq_ids if i in _period_id_set]
        _awarded_ids = [i for i in _awarded_ids if i in _period_id_set]
        _evaluation_count = len(_eval_ids)
        ready_for_form_queue_count = len(_rfq_ids)

    _registered_count = len(_registered_ids)
    _awarded_count = len(_awarded_ids)

    # Applicants by Status — all-time by default; period-scoped when filter is active
    applicant_by_status = [
        {'status': 'registered',   'label': 'Registered',               'count': _registered_count},
        {'status': 'evaluation',   'label': 'Evaluation & Eligibility', 'count': _evaluation_count},
        {'status': 'form',         'label': 'Form',                     'count': ready_for_form_queue_count},
        {'status': 'awarded',      'label': 'Lot Awarded',              'count': _awarded_count},
    ]

    # Applicant Situation — active pipeline (CDRRMO / Ejected / Displaced / None)
    active_pipeline_ids = (
        set(_registered_ids)
        | set(_eval_ids)
        | set(_rfq_ids)
        | set(_awarded_ids)
    )

    applicant_stage_map = {}
    for aid in _registered_ids:
        applicant_stage_map[aid] = 'Registered'
    for aid in _eval_ids:
        applicant_stage_map[aid] = 'Evaluation & Eligibility'
    for aid in _rfq_ids:
        applicant_stage_map[aid] = 'Form'
    for aid in _awarded_ids:
        applicant_stage_map[aid] = 'Lot Awarded'

    situation_breakdowns = {
        'danger_zone': {'Registered': 0, 'Evaluation & Eligibility': 0, 'Form': 0, 'Lot Awarded': 0},
        'ejected':     {'Registered': 0, 'Evaluation & Eligibility': 0, 'Form': 0, 'Lot Awarded': 0},
        'relocated':   {'Registered': 0, 'Evaluation & Eligibility': 0, 'Form': 0, 'Lot Awarded': 0},
        'not_abc':     {'Registered': 0, 'Evaluation & Eligibility': 0, 'Form': 0, 'Lot Awarded': 0},
    }

    situation_counts_map = {'danger_zone': 0, 'ejected': 0, 'relocated': 0, 'not_abc': 0}
    active_applicants_qs = Applicant.objects.filter(id__in=active_pipeline_ids).values('id', 'displacement_reason')
    for app_row in active_applicants_qs:
        reason = (app_row.get('displacement_reason') or '').strip()
        if reason in situation_counts_map:
            situation_counts_map[reason] += 1
            st = applicant_stage_map.get(app_row['id'])
            if st and reason in situation_breakdowns and st in situation_breakdowns[reason]:
                situation_breakdowns[reason][st] += 1

    situation_total = sum(situation_counts_map.values())

    applicants_by_channel = [
        {
            'channel': 'danger_zone',
            'label': 'CDRRMO',
            'count': situation_counts_map.get('danger_zone', 0),
            'breakdown': situation_breakdowns.get('danger_zone', {}),
        },
        {
            'channel': 'ejected',
            'label': 'Ejected',
            'count': situation_counts_map.get('ejected', 0),
            'breakdown': situation_breakdowns.get('ejected', {}),
        },
        {
            'channel': 'relocated',
            'label': 'Displaced',
            'count': situation_counts_map.get('relocated', 0),
            'breakdown': situation_breakdowns.get('relocated', {}),
        },
        {
            'channel': 'not_abc',
            'label': 'None',
            'count': situation_counts_map.get('not_abc', 0),
            'breakdown': situation_breakdowns.get('not_abc', {}),
        },
    ]
    _analytics_rows_bar_pct(applicants_by_channel)

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
    if filter_active:
        # Period view: only units awarded in this window (not full current inventory)
        _period_unit_ids = list(
            LotAward.objects.filter(
                awarded_at__gte=period_start,
                awarded_at__lte=period_end,
            ).values_list('unit_id', flat=True)
        )
        _housing_qs = HousingUnit.objects.filter(id__in=_period_unit_ids)
        housing_units_by_status = sorted(
            _housing_qs.values('status').annotate(count=Count('id')),
            key=lambda x: (-x['count'], x['status'] or ''),
        )
        housing_units_total = len(set(_period_unit_ids))
    else:
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
    # Filter cases by the selected period (cases received/opened in that month)
    _period_cases_qs = Case.objects.filter(
        received_at__gte=period_start,
        received_at__lte=period_end,
    )
    cases_by_status = sorted(
        _period_cases_qs.values('status').annotate(count=Count('id')),
        key=lambda x: (-x['count'], x['status'] or ''),
    )
    for row in cases_by_status:
        row['label'] = case_status_labels.get(row['status'], row['status'] or '—')
    _analytics_rows_bar_pct(cases_by_status)

    cases_by_type = sorted(
        _period_cases_qs.values('case_type').annotate(count=Count('id')),
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
    # Replaced Python for-loop (full table scan) with a single SQL aggregate
    _3d_ago  = now - timedelta(days=3)
    _7d_ago  = now - timedelta(days=7)
    _14d_ago = now - timedelta(days=14)
    _30d_ago = now - timedelta(days=30)
    _open_cases_agg = Case.objects.exclude(status__in=['resolved', 'closed']).aggregate(
        total=Count('pk'),
        # received_at=None → treated as 0 days (matches original logic)
        band_0_3=Count('pk', filter=Q(received_at__gte=_3d_ago) | Q(received_at__isnull=True)),
        band_4_7=Count('pk', filter=Q(received_at__gte=_7d_ago, received_at__lt=_3d_ago)),
        band_8_14=Count('pk', filter=Q(received_at__gte=_14d_ago, received_at__lt=_7d_ago)),
        band_15_30=Count('pk', filter=Q(received_at__gte=_30d_ago, received_at__lt=_14d_ago)),
        band_30plus=Count('pk', filter=Q(received_at__lt=_30d_ago)),
        stale=Count('pk', filter=Q(received_at__lt=_14d_ago)),
    )
    open_cases_count = _open_cases_agg['total']
    stale_cases_count = _open_cases_agg['stale']
    case_aging_bands = {
        '0-3 days':   _open_cases_agg['band_0_3'],
        '4-7 days':   _open_cases_agg['band_4_7'],
        '8-14 days':  _open_cases_agg['band_8_14'],
        '15-30 days': _open_cases_agg['band_15_30'],
        '30+ days':   _open_cases_agg['band_30plus'],
    }

    # Applicant workflow funnel — collapse 5 count() calls → 1 aggregate
    _funnel_agg = Applicant.objects.aggregate(
        eligible=Count('pk', filter=Q(status='eligible')),
        requirements=Count('pk', filter=Q(status='requirements')),
        application=Count('pk', filter=Q(status='application')),
        standby=Count('pk', filter=Q(status='standby')),
        awarded=Count('pk', filter=Q(status='awarded')),
    )
    funnel_stages = [
        {'label': 'Registered (all time)',        'count': total_applicants},
        {'label': 'Eligible / in queue',          'count': _funnel_agg['eligible']},
        {'label': 'Submitting requirements',      'count': _funnel_agg['requirements']},
        {'label': 'Application in progress',      'count': _funnel_agg['application']},
        {'label': 'Fully approved (standby)',     'count': _funnel_agg['standby']},
        {'label': 'Lot awarded',                  'count': _funnel_agg['awarded']},
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
    housing_units_total_for_rate = housing_units_total  # alias for occupancy rate calc
    housing_occupancy_rate = (
        int(round(100 * occupied_units / housing_units_total))
        if housing_units_total > 0 else 0
    )

    # Approved this month (for dashboard stat card)
    _this_month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    approved_this_month = Application.objects.filter(
        status='awarded', updated_at__gte=_this_month_start
    ).count()
    pending_final_signature_count = Application.objects.filter(status='completed').count()

    # Units under notice
    units_under_notice = HousingUnit.objects.filter(
        status__in=['Under notice (30-day)', 'Final notice (10-day)']
    ).count()
    repossessed_units = HousingUnit.objects.filter(status='Repossessed').count()

    # Construction progress summary — collapse 5 count() calls → 1 aggregate
    _cp_agg = ConstructionProgress.objects.aggregate(
        total=Count('pk'),
        completed=Count('pk', filter=Q(stage='completed')),
        not_started=Count('pk', filter=Q(stage='not_started')),
        delayed=Count('pk', filter=Q(is_delayed=True)),
    )
    construction_total = _cp_agg['total']
    construction_stages = {
        'not_started': _cp_agg['not_started'],
        # in_progress = all stages that are neither 'not_started' nor 'completed'
        'in_progress': _cp_agg['total'] - _cp_agg['not_started'] - _cp_agg['completed'],
        'completed':   _cp_agg['completed'],
        'delayed':     _cp_agg['delayed'],
    }
    construction_completed    = construction_stages['completed']
    construction_in_progress  = construction_stages['in_progress']
    construction_delayed      = construction_stages['delayed']
    construction_not_started  = construction_stages['not_started']

    # Blacklist breakdown by reason — period-scoped when filter is active
    blacklist_reason_labels = dict(UnitsBlacklist.REASON_CHOICES)
    _blacklist_qs = UnitsBlacklist.objects.all()
    if filter_active:
        _blacklist_qs = _blacklist_qs.filter(
            blacklisted_at__gte=period_start,
            blacklisted_at__lte=period_end,
        )
    blacklist_by_reason = sorted(
        _blacklist_qs.values('reason').annotate(count=Count('id')),
        key=lambda x: -int(x.get('count') or 0),
    )
    for row in blacklist_by_reason:
        row['label'] = blacklist_reason_labels.get(row['reason'], row['reason'] or '—')
    blacklist_count = sum(int(r.get('count') or 0) for r in blacklist_by_reason)

    # Active lot awards
    if filter_active:
        active_lot_awards = LotAward.objects.filter(
            status='active',
            awarded_at__gte=period_start,
            awarded_at__lte=period_end,
        ).count()
    else:
        active_lot_awards = LotAward.objects.filter(status='active').count()

    # ===== VOTER REGISTRATION STATUS (Descriptive Analytics) =====
    # Count beneficiaries (awarded applicants) by voter registration status
    _voter_qs = Applicant.objects.filter(status='awarded')
    if filter_active:
        _voter_qs = _voter_qs.filter(
            created_at__gte=period_start,
            created_at__lte=period_end,
        )
    voter_reg_data = (
        _voter_qs
        .values('is_registered_voter_talisay')
        .annotate(count=Count('id'))
    )
    voter_registered_count = 0
    voter_not_registered_count = 0
    for row in voter_reg_data:
        if row['is_registered_voter_talisay']:
            voter_registered_count = int(row['count'])
        else:
            voter_not_registered_count = int(row['count'])
    voter_total = voter_registered_count + voter_not_registered_count

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
        case_aging_bands=case_aging_bands,
        funnel_stages=funnel_stages,
        isf_population_data=isf_population_data,
        voter_registration_counts={
            'registered': voter_registered_count,
            'not_registered': voter_not_registered_count,
        },
        blacklist_by_reason=blacklist_by_reason,
        construction_stages=construction_stages,
    )

    # Smart dropdowns: only years/months with real data (fallback to standard range if none)
    year_options = available_years if available_years else list(range(now.year - 5, now.year + 2))
    month_options = list(range(1, 13))
    if report_year == 'all':
        months_for_select = [('all', 'All Months')]
    else:
        _year_months = available_months_by_year.get(
            report_year,
            [(i, calendar.month_name[i]) for i in range(1, 13)],
        )
        # Prepend All Months so staff can filter by year only
        months_for_select = [('all', 'All Months')] + list(_year_months)

    analytics_data = {
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
        'filter_active': filter_active,
        'year_options': year_options,
        'month_options': month_options,
        'months_for_select': months_for_select,
        'applicant_by_status': applicant_status_raw,  # CSV export uses raw status breakdown
        'application_by_status': application_by_status,
        'documents_by_type': documents_by_type,
        # ISF Population Statistics
        'isf_population_data': isf_population_data,
        'isf_site_id': isf_site_id,
        'isf_site_name': isf_population_data.get('site_name', 'All relocation sites'),
        'relocation_sites': relocation_sites,
        'monthly_upload_trend': monthly_upload_trend,
        'applicants_registered_period': applicants_registered_period,
        'housing_apps_created_period': housing_apps_created_period,
        'awarded_transition_period': awarded_transition_period,
        'requirements_verified_period': requirements_verified_period,
        'queue_active_rows': queue_active_rows,
        'vacant_units_count': vacant_units_count,
        'pending_cdrrmo_count': pending_cdrrmo_count,
        'situation_total': situation_total,
        'applicants_by_channel': applicants_by_channel,
        'applicants_top_barangays': applicants_top_barangays,
        'intake_registration_trend': intake_registration_trend,
        'module2_handoff_count': module2_handoff_count,
        'ready_for_form_queue_count': ready_for_form_queue_count,
        'pending_final_signature_count': pending_final_signature_count,
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
        'construction_not_started': construction_not_started,
        'blacklist_count': blacklist_count,
        'blacklist_by_reason': blacklist_by_reason,
        'active_lot_awards': active_lot_awards,
        # Voter registration analytics
        'voter_registered_count': voter_registered_count,
        'voter_not_registered_count': voter_not_registered_count,
        'voter_total': voter_total,
        # SVG gauge ring offsets — circumference = 2πr ≈ 97.4; offset = circ × (1 − pct/100)
        'housing_occupancy_offset': round(97.4 * (1 - housing_occupancy_rate / 100), 1),
        'req_verification_offset': round(97.4 * (1 - req_verification_rate / 100), 1),
        'stale_cases_offset': round(97.4 * (1 - min(100, (stale_cases_count * 10 if cases_total else 0)) / 100), 1),
        'construction_progress_offset': round(
            97.4 * (1 - min(100, int(100 * construction_in_progress / max(construction_total, 1))) / 100), 1
        ),
        # Session monitoring removed from request path — previously caused Railway
        # WORKER TIMEOUT (24 hourly Session scans). Context keys kept as cheap stubs
        # so any leftover template references do not KeyError.
        'total_sessions': 0,
        'active_sessions': 0,
        'expired_sessions': 0,
        'sessions_24h': 0,
        'sessions_7d': 0,
        'active_user_sessions': [],
        'login_trend': [],
        'expiring_soon': 0,
        'peak_hour': 'N/A',
        'peak_count': 0,
        # Dashboard stat card keys — included so dashboard_second_member can pull them from
        # the 2-minute cache instead of firing separate COUNT queries per page load.
        'cases_total': cases_total,
        'housing_units_total': housing_units_total,
        'approved_this_month': approved_this_month,
        'pending_final_signature_count': pending_final_signature_count,
        # Smart filter dropdown data
        'available_periods_json': available_periods_json,
    }

    # Add efficiency enhancements
    analytics_data.update(_calculate_analytics_enhancements(analytics_data))
    return analytics_data


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
    if report_year == 'all':
        filename = f"{filename_prefix}_all_time.csv"
    elif report_month == 'all':
        filename = f"{filename_prefix}_{report_year}.csv"
    else:
        filename = f"{filename_prefix}_{report_year}_{report_month:02d}.csv"
    
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
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
    isf = data.get('isf_population_data') or {}
    writer.writerow(['ISF population (lot-awarded — housing units / GK Masterlist)'])
    writer.writerow(['Relocation site scope', data.get('isf_site_name', 'All relocation sites')])
    writer.writerow(['Metric', 'Value'])
    writer.writerow(['Lot-awarded families (beneficiary heads)', isf.get('total_isf', 0)])
    writer.writerow(['Total on-site population (heads + household members)', isf.get('total_population', 0)])
    writer.writerow(['Male individuals', isf.get('male_count', 0)])
    writer.writerow(['Female individuals', isf.get('female_count', 0)])
    writer.writerow(['Units with active lot award', isf.get('awarded_units', 0)])
    writer.writerow(['Housing units in scope', isf.get('total_housing_units', 0)])
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
        'Pending final signature (applications)',
        data.get('pending_final_signature_count'),
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
    cases_total = Case.objects.count()

    standby_count = len(standby_queue)
    available_count = len(available_lots)
    ready_to_award = min(standby_count, available_count)

    # Analytics payload (handles ?month, ?year, ?site_id GET params)
    analytics_data = _staff_reports_analytics_payload(request)

    # CSV export — works via ?export=csv on the dashboard URL
    if request.GET.get('export') == 'csv':
        return _staff_reports_analytics_csv_response(
            analytics_data, 'Fourth Member', 'fourth_member_report'
        )

    context = {
        'page_title': 'Fourth Member Dashboard',
        'user_position': 'fourth_member',
        'total_applicants': total_applicants,
        'awaiting_signature': awaiting_signature_count,
        'housing_units': total_housing_units,
        'approved_this_month': approved_this_month,
        'cases_total': cases_total,
        'incomplete_docs': incomplete_requirements,
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
        # ========== ANALYTICS PANEL ==========
        **analytics_data,
    }

    return render(request, 'staff/dashboard.html', context)


@login_required
def dashboard_caretaker(request):
    """Legacy URL name; field desk (ronda / field) redirects to the field dashboard."""
    if request.user.position not in FIELD_INSPECTOR_POSITIONS:
        messages.error(request, 'Access denied.')
        return redirect('accounts:dashboard')
    return redirect('accounts:dashboard_field')


def _cdrrmo_meta_for_applicant(applicant):
    """Vault CDRRMO upload date + government certification record for field desk UI."""
    doc = (
        Document.objects.filter(applicant_id=applicant.pk, document_type='cdrrmo_cert')
        .order_by('-uploaded_at')
        .first()
    )
    cert = getattr(applicant, 'cdrrmo_certification', None)
    return {
        'status': cert.status if cert else 'pending',
        'certified_at': cert.certified_at.isoformat() if cert and cert.certified_at else None,
        'document_at': doc.uploaded_at.isoformat() if doc and doc.uploaded_at else None,
    }


def _module1_staff_handled_user(applicant):
    """Staff who proceeded from Module 1; falls back to encoder."""
    return getattr(applicant, 'module2_handoff_by', None) or applicant.registered_by


def _staff_handled_row(user):
    """Avatar initials + labels for Staff Handled columns (intake / field desk)."""
    if not user:
        return {
            'staff_handled': '—',
            'staff_position': '—',
            'staff_initials': '—',
            'staff_position_key': '',
        }
    first = (user.first_name or '')[:1]
    last = (user.last_name or '')[:1]
    initials = (first + last).upper() or '??'
    position_key = getattr(user, 'position', '') or ''
    if hasattr(user, 'get_position_display_short'):
        position_label = user.get_position_display_short()
    else:
        position_label = user.get_position_display() if position_key else '—'
    return {
        'staff_handled': user.get_full_name(),
        'staff_position': position_label,
        'staff_initials': initials,
        'staff_position_key': position_key,
    }


@login_required
@require_GET
def field_applicant_cdrrmo_meta(request, applicant_id):
    """Fresh CDRRMO vault / certification dates for the field verification modal (GET)."""
    if request.user.position not in FIELD_INSPECTOR_POSITIONS:
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)
    try:
        applicant = Applicant.objects.get(pk=applicant_id)
    except Applicant.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Applicant not found.'}, status=404)
    return JsonResponse({'success': True, 'meta': _cdrrmo_meta_for_applicant(applicant)})


@login_required
def dashboard_field(request):
    """
    Unified field desk: Ronda (includes on-site / caretaker duties) and Field personnel.
    Channel B danger-zone field verification (CDRRMO) after Module 2 handoff.
    """
    if request.user.position not in FIELD_INSPECTOR_POSITIONS:
        messages.error(
            request,
            'Access denied. This dashboard is for field inspectors only.',
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
        'applicant',
        'applicant__registered_by',
        'applicant__module2_handoff_by',
        'applicant__barangay',
    ).order_by('requested_at')

    pending_cert_list = list(pending_certifications)
    total_pending_certs = len(pending_cert_list)

    pending_cdrrmo_meta = {
        str(cert.applicant_id): _cdrrmo_meta_for_applicant(cert.applicant)
        for cert in pending_cert_list
    }

    # Oldest certification request first — table row order matches field visit order before QueueEntry exists
    visit_order_by_applicant_id = {
        c.applicant_id: order
        for order, c in enumerate(pending_cert_list, start=1)
    }

    pending_verifications = []
    for row_num, cert in enumerate(pending_cert_list, start=1):
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

        staff_user = _module1_staff_handled_user(cert.applicant)
        staff_row = _staff_handled_row(staff_user)
        pending_verifications.append({
            'index': row_num,
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
            'staff_user': staff_user,
            **staff_row,
            'sms_status': '✓ Sent' if cert.applicant.registration_sms_sent else '✗ Not Sent',
            'created_at': cert.requested_at,
            'days_pending': days_pending,
            'dob': cert.applicant.date_of_birth.strftime('%b %d, %Y') if cert.applicant.date_of_birth else 'Not specified',
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

    not_certified_applicants = []
    for cert in CDRRMOCertification.objects.filter(
        status='not_certified'
    ).select_related('applicant', 'result_recorded_by').order_by('-certified_at')[:100]:
        not_certified_applicants.append({
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
        'pending_cdrrmo_meta': pending_cdrrmo_meta,

        # ========== VERIFICATION SUMMARY ==========
        'verified_percentage': verified_percentage,
        'certified_applicants': certified_applicants,
        'not_certified_applicants': not_certified_applicants,
        'today_summary': today_summary,
        'today_summary_counts': today_summary_counts,
    }
    return render(request, 'field/dashboard.html', context)





# Legacy view for backward compatibility - now just redirects
@login_required
def dashboard_view(request):
    """Legacy dashboard view - redirects to position-specific dashboard."""
    return dashboard_redirect(request)


# ==================== CASE MANAGEMENT (Module 5) ====================


@login_required
def second_member_case_management(request):
    if request.user.position != 'second_member':
        messages.error(request, 'Access denied. This page is for the Second Member only.')
        return redirect('accounts:dashboard')
    from cases.views import case_management_dashboard
    return case_management_dashboard(request, 'second_member')


@login_required
def fourth_member_case_management(request):
    if request.user.position != 'fourth_member':
        messages.error(request, 'Access denied. This page is for the Fourth Member only.')
        return redirect('accounts:dashboard')
    from cases.views import case_management_dashboard
    return case_management_dashboard(request, 'fourth_member')


@login_required
def field_case_management(request):
    if request.user.position not in FIELD_INSPECTOR_POSITIONS:
        messages.error(request, 'Access denied. This page is for field inspectors only.')
        return redirect('accounts:dashboard')
    from cases.views import case_management_dashboard
    return case_management_dashboard(request, request.user.position)


# =============================================================================
# Google Drive OAuth popup — used by the Document Vault "Upload" button
# to get a drive.readonly access token server-side via authorization code flow.
# =============================================================================

@login_required
def google_drive_auth_start(request):
    """
    Opens as a popup from management.js.
    Redirects the popup to Google's OAuth consent page requesting
    drive.readonly scope.  On completion Google redirects back to
    google_drive_auth_callback.
    """
    from django.conf import settings as django_settings

    state = secrets.token_urlsafe(16)
    request.session['gdrive_oauth_state'] = state

    callback_uri = request.build_absolute_uri('/google/drive-callback/')

    params = urlencode({
        'client_id':     django_settings.GOOGLE_OAUTH_CLIENT_ID,
        'redirect_uri':  callback_uri,
        'response_type': 'code',
        'scope':         'https://www.googleapis.com/auth/drive.readonly',
        'access_type':   'online',
        'state':         state,
        'prompt':        'select_account',
    })
    return redirect(f'https://accounts.google.com/o/oauth2/v2/auth?{params}')


def google_drive_auth_callback(request):
    """
    OAuth callback — Google redirects here with ?code=... after the user
    grants Drive access.  We exchange the code for an access token and send
    it back to the parent window via BroadcastChannel + postMessage, then close.
    No @login_required — Google redirects here without session cookies in
    some browser configs; CSRF is handled by the state parameter.
    """
    from django.conf import settings as django_settings

    error = request.GET.get('error', '')
    code  = request.GET.get('code', '')

    def _close_with(payload):
        """
        Deliver the token (or error) back to the parent window and close.
        Uses BroadcastChannel as primary (works even when window.opener is
        cleared after cross-origin navigation) and postMessage as fallback.
        Shows a human-readable error if something went wrong.
        """
        payload_js = json.dumps(payload)

        if payload.get('error'):
            error_msg = payload['error']
            body_html = (
                f'<h3 style="color:#c0392b;font-family:sans-serif">Drive auth failed: {error_msg}</h3>'
                f'<p style="font-family:sans-serif">This window will close shortly.</p>'
            )
        else:
            body_html = '<p style="font-family:sans-serif">Authorised &#10003; &mdash; closing&hellip;</p>'

        html = (
            f'<!DOCTYPE html><html><body>{body_html}<script>'
            # BroadcastChannel — works even without window.opener
            f'(function(){{try{{var bc=new BroadcastChannel("gdrive_auth");bc.postMessage({payload_js});bc.close();}}catch(e){{}}}}());'
            # postMessage fallback
            f'try{{window.opener&&window.opener.postMessage({payload_js},window.location.origin);}}catch(e){{}}'
            # Close after a short delay so the user can read any error
            f'setTimeout(function(){{window.close();}},800);'
            f'</script></body></html>'
        )
        return HttpResponse(html, content_type='text/html')

    # ── CSRF check: state must match what we stored in the session ──────────────
    state_received = request.GET.get('state', '')
    state_expected = request.session.pop('gdrive_oauth_state', '')
    if not state_received or not state_expected or not secrets.compare_digest(state_received, state_expected):
        return _close_with({'type': 'google_drive_token', 'error': 'state_mismatch — possible CSRF attempt'})

    if error or not code:
        return _close_with({'type': 'google_drive_token', 'error': error or 'no_code'})

    # Exchange authorization code for access token
    callback_uri = request.build_absolute_uri('/google/drive-callback/')
    post_data = urlencode({
        'code':          code,
        'client_id':     django_settings.GOOGLE_OAUTH_CLIENT_ID,
        'client_secret': django_settings.GOOGLE_OAUTH_CLIENT_SECRET,
        'redirect_uri':  callback_uri,
        'grant_type':    'authorization_code',
    }).encode()

    try:
        req = _drive_urlreq.Request(
            'https://oauth2.googleapis.com/token',
            data=post_data,
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            method='POST',
        )
        with _drive_urlreq.urlopen(req, timeout=10) as resp:
            token_data = json.loads(resp.read())
    except Exception as exc:
        return _close_with({'type': 'google_drive_token', 'error': f'token_exchange_failed: {exc}'})

    access_token = token_data.get('access_token', '')
    if not access_token:
        google_error = token_data.get('error', 'no_access_token')
        google_desc  = token_data.get('error_description', '')
        return _close_with({'type': 'google_drive_token', 'error': f'{google_error}: {google_desc}'})

    # Return token + server-reported expiry so the JS side can schedule cache
    # invalidation to the exact second instead of guessing 55 minutes.
    expires_in = int(token_data.get('expires_in', 3600))
    return _close_with({
        'type':         'google_drive_token',
        'access_token': access_token,
        'expires_in':   expires_in,
    })
