"""
Module 5 — complaint handling per THA office spec.

Phases: Recording → Type ID → Review → Action/Decision → Monitoring → Closure
"""

from accounts.models import FIELD_DESK_POSITIONS

# --- Phases (desk guide) ---
PHASES = [
    {'key': 'recording', 'label': 'Case recording', 'hint': 'Add Case · beneficiary search · Pending Review'},
    {'key': 'type', 'label': 'Case type identification', 'hint': 'Type controls which action buttons appear'},
    {'key': 'review', 'label': 'Case review', 'hint': 'Staff reviews evidence & history — system does not judge'},
    {'key': 'action', 'label': 'Action & decision', 'hint': 'Warnings, mediation, referrals recorded'},
    {'key': 'monitoring', 'label': 'Case monitoring', 'hint': 'Follow-ups · repeat complaints · unresolved cases'},
    {'key': 'closure', 'label': 'Resolution & closure', 'hint': 'Resolved → Closed · full history archived'},
]

WORKFLOW_STEPS = [
    {'num': 1, 'key': 'report', 'label': 'Report', 'hint': 'Complaint at THA Office or on-site'},
    {'num': 2, 'key': 'record', 'label': 'Record', 'hint': 'Case ID · Pending Review'},
    {'num': 3, 'key': 'type', 'label': 'Type', 'hint': 'Complaint type → available buttons'},
    {'num': 4, 'key': 'review', 'label': 'Review', 'hint': 'Valid? Escalation? Office discretion'},
    {'num': 5, 'key': 'act', 'label': 'Act', 'hint': 'Official actions & decisions'},
    {'num': 6, 'key': 'monitor', 'label': 'Monitor', 'hint': 'Mediation · awaiting response · engineering'},
    {'num': 7, 'key': 'close', 'label': 'Close', 'hint': 'Resolved → Closed'},
]

# Status codes
STATUS_PENDING_REVIEW = 'pending_review'
STATUS_UNDER_REVIEW = 'under_review'
STATUS_MEDIATION = 'mediation_monitoring'
STATUS_AWAITING_RESPONSE = 'awaiting_response'
STATUS_REFERRED_ENGINEERING = 'referred_engineering'
STATUS_RESOLVED = 'resolved'
STATUS_CLOSED = 'closed'

TERMINAL_STATUSES = frozenset({STATUS_RESOLVED, STATUS_CLOSED})
ACTIVE_STATUSES = frozenset({
    STATUS_PENDING_REVIEW,
    STATUS_UNDER_REVIEW,
    STATUS_MEDIATION,
    STATUS_AWAITING_RESPONSE,
    STATUS_REFERRED_ENGINEERING,
})

LEGACY_STATUS_MAP = {
    'open': STATUS_PENDING_REVIEW,
    'investigation': STATUS_UNDER_REVIEW,
    'referred': STATUS_REFERRED_ENGINEERING,
    'pending_decision': STATUS_MEDIATION,
    'resolved': STATUS_RESOLVED,
    'closed': STATUS_CLOSED,
}

# Legacy case_type codes → spec types
LEGACY_TYPE_MAP = {
    'boundary': 'lot_boundary',
    'interpersonal': 'community_quarrel',
    'illegal_transfer': 'illegal_occupant',
    'unauthorized': 'illegal_occupant',
    'structural': 'occupancy_dispute',
    'damage': 'other',
}

STATUS_COLORS = {
    STATUS_PENDING_REVIEW: '#f59e0b',
    STATUS_UNDER_REVIEW: '#3b82f6',
    STATUS_MEDIATION: '#ea580c',
    STATUS_AWAITING_RESPONSE: '#0d9488',
    STATUS_REFERRED_ENGINEERING: '#a855f7',
    STATUS_RESOLVED: '#22c55e',
    STATUS_CLOSED: '#6b7280',
}

# --- Action codes (Step 5 buttons) ---
ACTION_REFER_ENGINEERING = 'refer_engineering'
ACTION_ISSUE_WARNING = 'issue_warning'
ACTION_SCHEDULE_MEDIATION = 'schedule_mediation'
ACTION_MONITOR_COMPLAINT = 'monitor_complaint'
ACTION_RECORD_INCIDENT = 'record_incident'
ACTION_RECORD_RESOLUTION = 'record_resolution'
ACTION_REVIEW_OCCUPANCY = 'review_occupancy'
ACTION_REQUEST_CLARIFICATION = 'request_clarification'
ACTION_MONITOR_CASE = 'monitor_case'
ACTION_ISSUE_REMINDER = 'issue_reminder'
ACTION_MONITOR_COMPLIANCE = 'monitor_compliance'
ACTION_SCHEDULE_INSPECTION = 'schedule_inspection'
# Legacy (still accepted if stored)
ACTION_VERBAL_WARNING = 'verbal_warning'
ACTION_WRITTEN_WARNING = 'written_warning'
ACTION_MEDIATION_HELD = 'mediation_held'
ACTION_NOTICE_ISSUED = 'notice_issued'
ACTION_FOLLOW_UP = 'follow_up'
ACTION_OTHER = 'other'

ACTION_LABELS = {
    ACTION_REFER_ENGINEERING: 'Refer to City Engineering',
    ACTION_ISSUE_WARNING: 'Issue warning',
    ACTION_SCHEDULE_MEDIATION: 'Schedule mediation',
    ACTION_MONITOR_COMPLAINT: 'Monitor complaint',
    ACTION_RECORD_INCIDENT: 'Record incident',
    ACTION_RECORD_RESOLUTION: 'Record resolution',
    ACTION_REVIEW_OCCUPANCY: 'Review occupancy',
    ACTION_REQUEST_CLARIFICATION: 'Request clarification',
    ACTION_MONITOR_CASE: 'Monitor case',
    ACTION_ISSUE_REMINDER: 'Issue reminder',
    ACTION_MONITOR_COMPLIANCE: 'Monitor compliance',
    ACTION_SCHEDULE_INSPECTION: 'Schedule lot survey',
    ACTION_VERBAL_WARNING: 'Verbal warning issued',
    ACTION_WRITTEN_WARNING: 'Written warning issued',
    ACTION_MEDIATION_HELD: 'Mediation conducted',
    ACTION_NOTICE_ISSUED: 'Notice issued',
    ACTION_FOLLOW_UP: 'Follow-up logged',
    ACTION_OTHER: 'Other action recorded',
}

# Spec complaint types → type-specific action buttons (desk guide)
CASE_TYPE_ACTIONS = {
    'lot_boundary': [ACTION_REFER_ENGINEERING],
    'noise': [ACTION_ISSUE_WARNING, ACTION_SCHEDULE_MEDIATION],
    'drunk_disturbance': [ACTION_ISSUE_WARNING, ACTION_SCHEDULE_MEDIATION],
    'community_quarrel': [ACTION_SCHEDULE_MEDIATION, ACTION_RECORD_RESOLUTION],
    'illegal_occupant': [ACTION_REVIEW_OCCUPANCY, ACTION_REQUEST_CLARIFICATION],
    'occupancy_dispute': [ACTION_REVIEW_OCCUPANCY, ACTION_REQUEST_CLARIFICATION],
    'sanitation': [ACTION_ISSUE_REMINDER, ACTION_MONITOR_COMPLIANCE],
    'other': [],
}

TYPE_ACTION_GUIDE = {
    'lot_boundary': 'Lot boundary → Refer to City Engineering',
    'noise': 'Noise → Issue warning · Schedule mediation',
    'drunk_disturbance': 'Drunk disturbance → Issue warning · Schedule mediation',
    'community_quarrel': 'Community quarrel → Schedule mediation · Record resolution',
    'illegal_occupant': 'Illegal occupant → Review occupancy · Request clarification',
    'occupancy_dispute': 'Occupancy dispute → Review occupancy · Request clarification',
    'sanitation': 'Sanitation → Issue reminder · Monitor compliance',
    'other': 'Other — record remarks under review notes; resolve when ready.',
}

# Which action sets status after record
ACTION_STATUS_MAP = {
    ACTION_REFER_ENGINEERING: STATUS_REFERRED_ENGINEERING,
    ACTION_ISSUE_WARNING: STATUS_MEDIATION,
    ACTION_SCHEDULE_MEDIATION: STATUS_MEDIATION,
    ACTION_MONITOR_COMPLAINT: STATUS_MEDIATION,
    ACTION_RECORD_INCIDENT: STATUS_UNDER_REVIEW,
    ACTION_RECORD_RESOLUTION: STATUS_RESOLVED,
    ACTION_REVIEW_OCCUPANCY: STATUS_UNDER_REVIEW,
    ACTION_REQUEST_CLARIFICATION: STATUS_AWAITING_RESPONSE,
    ACTION_MONITOR_CASE: STATUS_MEDIATION,
    ACTION_ISSUE_REMINDER: STATUS_MEDIATION,
    ACTION_MONITOR_COMPLIANCE: STATUS_MEDIATION,
    ACTION_SCHEDULE_INSPECTION: STATUS_UNDER_REVIEW,
}

WORKFLOW_TRANSITIONS = {
    'start_review': {
        'from': {STATUS_PENDING_REVIEW},
        'to': STATUS_UNDER_REVIEW,
        'label': 'Mark under review',
    },
    'enter_monitoring': {
        'from': {STATUS_UNDER_REVIEW, STATUS_REFERRED_ENGINEERING, STATUS_AWAITING_RESPONSE},
        'to': STATUS_MEDIATION,
        'label': 'Under mediation / monitoring',
    },
}


def normalize_case_type(case_type: str) -> str:
    return LEGACY_TYPE_MAP.get(case_type, case_type or 'other')


def normalize_status(status: str) -> str:
    return LEGACY_STATUS_MAP.get(status, status)


def user_can_manage_workflow(user) -> bool:
    return getattr(user, 'position', None) not in FIELD_DESK_POSITIONS


def user_can_record_case(user) -> bool:
    return user.is_authenticated


def workflow_step_for_case(case) -> int:
    status = normalize_status(case.status)
    if status == STATUS_CLOSED:
        return 7
    if status == STATUS_RESOLVED:
        return 7
    if status in (STATUS_MEDIATION, STATUS_REFERRED_ENGINEERING, STATUS_AWAITING_RESPONSE):
        return 6
    if case.actions.exists():
        return max(6, 5)
    if status == STATUS_UNDER_REVIEW:
        return 4 if not (case.investigation_notes or '').strip() else 5
    if status == STATUS_PENDING_REVIEW:
        return 3 if case.case_type else 2
    return 2


def step_states_for_case(case) -> list:
    current = workflow_step_for_case(case)
    return [
        {**step, 'state': 'done' if step['num'] < current else ('active' if step['num'] == current else 'pending')}
        for step in WORKFLOW_STEPS
    ]


def current_phase_for_case(case) -> dict:
    """Desk phase banner for modal."""
    status = normalize_status(case.status)
    if status == STATUS_CLOSED:
        return PHASES[5]
    if status == STATUS_RESOLVED:
        return PHASES[5]
    if status in (STATUS_MEDIATION, STATUS_AWAITING_RESPONSE, STATUS_REFERRED_ENGINEERING):
        return PHASES[4]
    if status == STATUS_UNDER_REVIEW:
        return PHASES[2] if not (case.investigation_notes or '').strip() else PHASES[3]
    if status == STATUS_PENDING_REVIEW:
        return PHASES[1]
    return PHASES[0]


def allowed_type_actions(case_type: str) -> list:
    ct = normalize_case_type(case_type)
    codes = CASE_TYPE_ACTIONS.get(ct, [])
    return [{'code': c, 'label': ACTION_LABELS[c]} for c in codes]


def allowed_workflow_buttons(case, user) -> list:
    if not user_can_manage_workflow(user):
        return []
    status = normalize_status(case.status)
    buttons = []
    if status == STATUS_PENDING_REVIEW:
        buttons.append({
            'transition': 'start_review',
            'label': WORKFLOW_TRANSITIONS['start_review']['label'],
            'style': 'primary',
        })
    if status in WORKFLOW_TRANSITIONS['enter_monitoring']['from']:
        buttons.append({
            'transition': 'enter_monitoring',
            'label': WORKFLOW_TRANSITIONS['enter_monitoring']['label'],
            'style': 'secondary',
        })
    return buttons


def can_transition(case, transition_key: str) -> bool:
    status = normalize_status(case.status)
    spec = WORKFLOW_TRANSITIONS.get(transition_key)
    return bool(spec and status in spec['from'])


def apply_transition(case, transition_key: str):
    case.status = WORKFLOW_TRANSITIONS[transition_key]['to']


def refer_engineering_allowed(case) -> bool:
    return (
        normalize_case_type(case.case_type) == 'lot_boundary'
        and normalize_status(case.status) in {
            STATUS_UNDER_REVIEW,
            STATUS_MEDIATION,
            STATUS_REFERRED_ENGINEERING,
            STATUS_AWAITING_RESPONSE,
        }
    )


def type_action_guide(case_type: str) -> str:
    return TYPE_ACTION_GUIDE.get(normalize_case_type(case_type), TYPE_ACTION_GUIDE['other'])


def apply_action_status(case, action_type: str):
    """Set case status from type-specific button (spec system actions)."""
    ct = normalize_case_type(case.case_type)
    if action_type == ACTION_REFER_ENGINEERING:
        if ct != 'lot_boundary':
            raise ValueError('City Engineering referral is only for lot boundary issues.')
        case.status = STATUS_REFERRED_ENGINEERING
        case.referred_to = 'City Engineering'
        from django.utils import timezone
        case.referred_at = timezone.now()
        return
    new_status = ACTION_STATUS_MAP.get(action_type)
    if new_status:
        case.status = new_status
    elif normalize_status(case.status) == STATUS_PENDING_REVIEW:
        case.status = STATUS_UNDER_REVIEW


def monitoring_alerts(case, prior_count: int) -> list:
    alerts = []
    status = normalize_status(case.status)
    if status in TERMINAL_STATUSES:
        return alerts
    if case.is_stale:
        alerts.append({
            'level': 'warning',
            'text': f'Unresolved {case.days_open} days — office follow-up required.',
        })
    if prior_count >= 2:
        alerts.append({
            'level': 'warning',
            'text': f'Repeated complaints: {prior_count} prior case(s) for this beneficiary.',
        })
    if case.follow_up_at:
        from django.utils import timezone
        if case.follow_up_at <= timezone.localdate():
            alerts.append({'level': 'info', 'text': 'Follow-up date is due or overdue.'})
    if status == STATUS_REFERRED_ENGINEERING:
        alerts.append({
            'level': 'info',
            'text': 'Awaiting Engineering findings — THA staff controls referral (system does not contact engineering).',
        })
    if status == STATUS_AWAITING_RESPONSE:
        alerts.append({'level': 'info', 'text': 'Awaiting response — monitor until clarified.'})
    return alerts
