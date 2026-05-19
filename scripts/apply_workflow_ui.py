from pathlib import Path

p = Path(__file__).resolve().parents[1] / "templates/cases/case_management.html"
t = p.read_text(encoding="utf-8")

m = '            <motion id="evidenceSection">'.replace("<motion", "<motion")
m = '            <div id="evidenceSection">'
if "case_workflow_ui.html" not in t:
    t = t.replace(m, '            {% include "cases/partials/case_workflow_ui.html" %}\n\n' + m)

s = "            <!-- Update Form (for open cases) -->"
e = "        <!-- Modal Footer -->"
if s in t:
    i0, i1 = t.find(s), t.find(e, t.find(s))
    if i1 > i0:
        t = t[:i0] + t[i1:]

old = (
    "style=\"background: white; border-left: 4px solid "
    "{% if case.status == 'open' %}#f59e0b"
    "{% elif case.status == 'investigation' %}#3b82f6"
    "{% elif case.status == 'referred' %}#a855f7"
    "{% elif case.status == 'pending_decision' %}#ea580c"
    "{% elif case.status == 'resolved' %}#22c55e"
    "{% else %}#6b7280{% endif %};"
)
new = (
    "style=\"background: white; border-left: 4px solid "
    "{% if case.status == 'pending_review' %}#f59e0b"
    "{% elif case.status == 'under_review' %}#3b82f6"
    "{% elif case.status == 'mediation_monitoring' %}#ea580c"
    "{% elif case.status == 'referred_engineering' %}#a855f7"
    "{% elif case.status == 'resolved' %}#22c55e"
    "{% elif case.status == 'closed' %}#6b7280"
    "{% else %}#9ca3af{% endif %};"
)
t = t.replace(old, new)

for a, b in [
    ("case.status == 'open'", "case.status == 'pending_review'"),
    ("case.status == 'investigation'", "case.status == 'under_review'"),
    ("case.status == 'referred'", "case.status == 'referred_engineering'"),
    ("case.status == 'pending_decision'", "case.status == 'mediation_monitoring'"),
]:
    t = t.replace(a, b)

t = t.replace(
    "const CASE_POSITION = '{{ request.user.position }}';",
    "const CASE_POSITION = '{{ request.user.position }}';\n"
    "const CAN_MANAGE_WORKFLOW = {{ can_manage_workflow|yesno:'true,false' }};",
    1,
)

t = t.replace(
    "'notesSection', 'priorCasesSection', 'updateFormSection']",
    "'notesSection', 'priorCasesSection', 'workflowPanelSection', 'actionsHistorySection',\n"
    "     'workflowStepper', 'monitoringAlertsBox', 'rondaReadOnlyNotice']",
)

t = t.replace(
    "            if (d.success) populateCaseModal(d.case);",
    "            if (d.success) { window._caseCanManage = d.can_manage_workflow; populateCaseModal(d.case); }",
)

old_end = """    if (!['resolved', 'closed'].includes(c.status)) {
        document.getElementById('updateFormSection').style.display = 'flex';
    }

    document.getElementById('caseModal').style.display = 'flex';
}"""

new_end = """    renderWorkflowUI(c, window._caseCanManage);

    document.getElementById('caseModal').style.display = 'flex';
}"""

t = t.replace(old_end, new_end)

wf_js_path = Path(__file__).resolve().parent / "workflow_modal_js.txt"
if "function renderWorkflowUI" not in t and wf_js_path.exists():
    wf_js = wf_js_path.read_text(encoding="utf-8")
    marker = "{% if open_new_case %}"
    t = t.replace(marker, wf_js + "\n" + marker)

p.write_text(t, encoding="utf-8")
print("Patched", p)
