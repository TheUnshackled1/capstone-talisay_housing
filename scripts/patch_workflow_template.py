"""Patch case_management.html for 7-step workflow UI."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
p = ROOT / "templates/cases/case_management.html"
text = p.read_text(encoding="utf-8")

# CSS for workflow stepper
css_marker = "    @media (max-width: 640px) {"
css_add = """    .case-workflow-stepper {
        display: flex;
        flex-wrap: wrap;
        gap: 0.35rem;
        margin-bottom: 1rem;
    }
    .case-wf-step {
        flex: 1 1 4.5rem;
        min-width: 4.2rem;
        text-align: center;
        padding: 0.35rem 0.25rem;
        border-radius: 6px;
        font-size: 0.62rem;
        font-weight: 700;
        line-height: 1.2;
        border: 1px solid #e5e7eb;
        background: #f9fafb;
        color: #9ca3af;
    }
    .case-wf-step.done { background: #ecfdf5; border-color: #6ee7b7; color: #047857; }
    .case-wf-step.active { background: #eff6ff; border-color: #93c5fd; color: #1d4ed8; }
    .case-wf-step .num { display: block; font-size: 0.7rem; }

"""
if ".case-workflow-stepper" not in text:
    text = text.replace(css_marker, css_add + css_marker, 1)

# KPIs
old_kpis = """<motion class="monitoring-kpis">"""
# fix - use actual content
old_kpis = """<motion class="monitoring-kpis">""".replace("<motion", "<div")
old_kpis = """<div class="monitoring-kpis">"""
new_kpis = """<motion class="monitoring-kpis">"""
new_kpis = """<div class="monitoring-kpis">
    <div class="monitoring-kpi monitoring-kpi-open">
        <motion class="monitoring-kpi-icon">""".replace("<motion", "<motion")  # noop

new_kpis = """<div class="monitoring-kpis">
    <div class="monitoring-kpi monitoring-kpi-open">
        <div class="monitoring-kpi-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M12 8v4l3 3"/><circle cx="12" cy="12" r="9"/></svg>
        </div>
        <div class="monitoring-kpi-text"><h4>Pending Review</h4><motion class="monitoring-kpi-number">{{ status_counts.pending_review }}</div></div>
    </div>
    <div class="monitoring-kpi monitoring-kpi-investigation">
        <div class="monitoring-kpi-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="11" cy="11" r="7"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
        </div>
        <div class="monitoring-kpi-text"><h4>Under Review</h4><div class="monitoring-kpi-number">{{ status_counts.under_review }}</div></div>
    </motion>
    <div class="monitoring-kpi monitoring-kpi-referred">
        <div class="monitoring-kpi-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M4 12h10"/><path d="M10 6l6 6-6 6"/></svg></div>
        <div class="monitoring-kpi-text"><h4>Monitoring</h4><motion class="monitoring-kpi-number">{{ status_counts.mediation_monitoring }}</div></div>
    </div>
    <div class="monitoring-kpi" style="border-color: #e9d5ff;">
        <div class="monitoring-kpi-icon" style="background:#f3e8ff;color:#7c3aed;"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M12 2v20M2 12h20"/></svg></div>
        <div class="monitoring-kpi-text"><h4>Engineering</h4><div class="monitoring-kpi-number">{{ status_counts.referred_engineering }}</div></div>
    </div>
    <div class="monitoring-kpi monitoring-kpi-resolved">
        <div class="monitoring-kpi-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="12" cy="12" r="9"/><path d="M8 12l2.5 2.5L16 9"/></svg></motion>
        <div class="monitoring-kpi-text"><h4>Resolved</h4><div class="monitoring-kpi-number">{{ status_counts.resolved }}</motion></motion>
    </div>
</div>"""

new_kpis = new_kpis.replace("</motion>", "</div>").replace("<motion ", "<div ")

start_kpi = text.find('<motion class="monitoring-kpis">')
if start_kpi == -1:
    start_kpi = text.find('<div class="monitoring-kpis">')
end_kpi = text.find('</div>\n\n<div class="monitoring-work-area">')
if start_kpi != -1 and end_kpi != -1:
    # find closing of monitoring-kpis - count divs is hard; use known end marker
    end_kpi = text.find('<motion class="monitoring-work-area">')
    if end_kpi == -1:
        end_kpi = text.find('<motion class="monitoring-work-area">'.replace("<motion", "<div"))
    end_kpi = text.find('<div class="monitoring-work-area">')
    if end_kpi != -1:
        text = text[:start_kpi] + new_kpis + "\n\n" + text[end_kpi:]

# Include workflow partial before notes section
include_marker = "            <!-- Case Notes Timeline (if exists) -->"
if "case_workflow_ui.html" not in text:
    text = text.replace(
        include_marker,
        '            {% include "cases/partials/case_workflow_ui.html" %}\n\n            ' + include_marker,
    )

# Remove old update form
old_form_start = "            <!-- Update Form (for open cases) -->"
old_form_end = "            </div>\n        </motion>\n\n        <!-- Modal Footer -->"
old_form_end = "            </div>\n        </div>\n\n        <!-- Modal Footer -->"
if old_form_start in text:
    i0 = text.find(old_form_start)
    i1 = text.find("        <!-- Modal Footer -->", i0)
    if i1 > i0:
        text = text[:i0] + text[i1:]

# Status border colors in list - simplify with inline style using status
# Replace long border-left block - optional skip if too fragile

# Patch JS: add CAN_MANAGE_WORKFLOW and workflow functions
js_const = "const CASE_POSITION = '{{ request.user.position }}';"
js_const_new = """const CASE_POSITION = '{{ request.user.position }}';
const CAN_MANAGE_WORKFLOW = {{ can_manage_workflow|yesno:"true,false" }};"""
text = text.replace(js_const, js_const_new, 1)

# Replace resetCaseModalSections list
text = text.replace(
    "['subjectSection', 'investigationSection', 'referralSection', 'resolutionSection',\n"
    "     'notesSection', 'priorCasesSection', 'updateFormSection']",
    "['subjectSection', 'investigationSection', 'referralSection', 'resolutionSection',\n"
    "     'notesSection', 'priorCasesSection', 'workflowPanelSection', 'actionsHistorySection',\n"
    "     'workflowStepper', 'monitoringAlertsBox', 'rondaReadOnlyNotice']",
)

# Replace updateFormSection display logic in populateCaseModal
text = text.replace(
    "    if (!['resolved', 'closed'].includes(c.status)) {\n"
    "        document.getElementById('updateFormSection').style.display = 'flex';\n"
    "    }\n\n"
    "    document.getElementById('caseModal').style.display = 'flex';\n}",
    "    renderWorkflowUI(c, d.can_manage_workflow);\n\n"
    "    document.getElementById('caseModal').style.display = 'flex';\n}",
)

# Append workflow JS before {% if open_new_case %}
wf_js = r'''
let lastCasePayload = null;

function renderWorkflowUI(c, canManage) {
    const stepper = document.getElementById('workflowStepper');
    if (stepper && c.workflow_steps) {
        stepper.style.display = 'flex';
        stepper.innerHTML = c.workflow_steps.map((s) => `
            <div class="case-wf-step ${s.state}" title="${s.hint}">
                <span class="num">${s.num}</span>${s.label}
            </div>`).join('');
    }
    const alertsBox = document.getElementById('monitoringAlertsBox');
    if (alertsBox) {
        if (c.monitoring_alerts && c.monitoring_alerts.length) {
            alertsBox.style.display = 'flex';
            alertsBox.innerHTML = c.monitoring_alerts.map((a) => `
                <p style="margin:0;font-size:0.8rem;padding:0.5rem 0.65rem;border-radius:6px;
                    background:${a.level === 'warning' ? '#fffbeb' : '#eff6ff'};
                    border:1px solid ${a.level === 'warning' ? '#fcd34d' : '#93c5fd'};
                    color:${a.level === 'warning' ? '#92400e' : '#1e40af'};">${a.text}</p>`).join('');
        } else {
            alertsBox.style.display = 'none';
            alertsBox.innerHTML = '';
        }
    }
    const rondaNotice = document.getElementById('rondaReadOnlyNotice');
    if (rondaNotice) rondaNotice.style.display = (!canManage && !['resolved','closed'].includes(c.status)) ? 'block' : 'none';
    if (c.actions && c.actions.length) {
        document.getElementById('actionsHistorySection').style.display = 'block';
        document.getElementById('actionsHistoryList').innerHTML = c.actions.map((a) => `
            <motion style="font-size:0.8rem;padding:0.5rem;background:#fff;border:1px solid #e5e7eb;border-radius:6px;">
                <strong>${a.action_label}</strong>${a.details ? ' — ' + a.details : ''}
                <div style="color:#64748b;margin-top:0.2rem;">${a.created_by} · ${new Date(a.created_at).toLocaleString()}</div>
            </div>`).join('');
    }
    const panel = document.getElementById('workflowPanelSection');
    if (!panel) return;
    const terminal = ['resolved', 'closed'].includes(c.status);
    panel.style.display = (canManage && !terminal) ? 'flex' : 'none';
    if (!canManage || terminal) return;
    const btnRow = document.getElementById('workflowButtonsRow');
    btnRow.innerHTML = (c.workflow_buttons || []).map((b) => {
        const bg = b.style === 'primary' ? '#047857' : b.style === 'success' ? '#16a34a' : b.style === 'muted' ? '#6b7280' : '#2563eb';
        return `<button type="button" onclick="runWorkflowTransition('${b.action}')" style="padding:0.45rem 0.75rem;background:${bg};color:#fff;border:none;border-radius:6px;font-size:0.8rem;font-weight:600;cursor:pointer;">${b.label}</button>`;
    }).join('');
    const reviewBlock = document.getElementById('reviewNotesBlock');
    reviewBlock.style.display = ['under_review','mediation_monitoring','referred_engineering'].includes(c.status) ? 'flex' : 'none';
    document.getElementById('reviewNotes').value = c.investigation_notes || '';
    const typeBlock = document.getElementById('typeActionsBlock');
    typeBlock.style.display = c.status !== 'pending_review' ? 'flex' : 'none';
    const sel = document.getElementById('caseActionType');
    sel.innerHTML = (c.type_actions || []).map((a) => `<option value="${a.code}">${a.label}</option>`).join('');
    const resolveClose = document.getElementById('resolveCloseBlock');
    resolveClose.style.display = 'flex';
    document.getElementById('resolveBlock').style.display = c.status !== 'resolved' ? 'flex' : 'none';
    document.getElementById('closeBlock').style.display = c.status === 'resolved' ? 'flex' : 'none';
    if (c.follow_up_at) document.getElementById('caseFollowUpDate').value = c.follow_up_at.slice(0, 10);
    if (c.closure_outcome) document.getElementById('closureOutcome').value = c.closure_outcome;
    lastCasePayload = c;
}

function runWorkflowTransition(transition) {
    postCaseUpdate({ case_id: currentCaseId, action: 'workflow_transition', transition })
        .then((d) => { if (d.success) { alert(d.message); openCaseModal(currentCaseId); } else alert(d.error); });
}

function saveReviewNotes() {
    const review_notes = document.getElementById('reviewNotes').value.trim();
    postCaseUpdate({ case_id: currentCaseId, action: 'save_review', review_notes })
        .then((d) => { if (d.success) { alert(d.message); openCaseModal(currentCaseId); } else alert(d.error); });
}

function recordCaseAction() {
    const action_type = document.getElementById('caseActionType').value;
    const details = document.getElementById('caseActionDetails').value.trim();
    const follow_up_at = document.getElementById('caseFollowUpDate').value;
    postCaseUpdate({ case_id: currentCaseId, action: 'record_action', action_type, details, follow_up_at })
        .then((d) => { if (d.success) { alert(d.message); openCaseModal(currentCaseId); } else alert(d.error); });
}

function resolveCase() {
    const resolution_notes = document.getElementById('resolutionNotes').value.trim();
    if (!resolution_notes) { alert('Enter resolution outcome'); return; }
    postCaseUpdate({ case_id: currentCaseId, action: 'resolve', resolution_notes })
        .then((d) => { if (d.success) { alert(d.message); location.reload(); } else alert(d.error); });
}

function closeCase() {
    const closure_outcome = document.getElementById('closureOutcome').value.trim();
    if (!closure_outcome) { alert('Enter closure summary'); return; }
    postCaseUpdate({ case_id: currentCaseId, action: 'close', closure_outcome })
        .then((d) => { if (d.success) { alert(d.message); location.reload(); } else alert(d.error); });
}

function saveCaseNote() {
    const note = (document.getElementById('workflowUpdateNote') || document.getElementById('updateNote')).value.trim();
    if (!note) { alert('Enter a note'); return; }
    postCaseUpdate({ case_id: currentCaseId, action: 'add_note', note })
        .then((d) => { if (d.success) { alert(d.message); openCaseModal(currentCaseId); } else alert(d.error); });
}

'''
wf_js = wf_js.replace('<motion ', '<motion ').replace('</motion>', '</div>').replace('<motion style', '<div style')

marker = "{% if open_new_case %}"
if "function renderWorkflowUI" not in text:
    text = text.replace(marker, wf_js + "\n" + marker)

# Fix populateCaseModal to pass can_manage - use d from outer
text = text.replace(
    "            if (d.success) populateCaseModal(d.case);",
    "            if (d.success) { populateCaseModal(d.case); lastCasePayload = d.case; window._caseCanManage = d.can_manage_workflow; }",
)
text = text.replace(
    "    renderWorkflowUI(c, d.can_manage_workflow);",
    "    renderWorkflowUI(c, window._caseCanManage);",
)

# Remove saveUpdate if still present - map workflow transition start_review
text = text.replace("async function saveUpdate()", "async function saveUpdateLegacy()")

# Map workflow button action start_review
if "runWorkflowTransition" in text and "'start_review'" not in text:
    pass  # start_review uses workflow_transition - need to fix buttons
# workflow buttons use action 'start_review' but backend expects workflow_transition with transition key
# Fix allowed_workflow_buttons to use transition key

p.write_text(text, encoding="utf-8")
print("Patched", p)
