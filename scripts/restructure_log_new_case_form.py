from pathlib import Path

p = Path(__file__).resolve().parents[1] / "templates/cases/case_management.html"
t = p.read_text(encoding="utf-8")

start = '            <div style="background: #ecfdf5; border: 1px solid #a7f3d0; border-radius: 8px; padding: 0.75rem;">\n                <p style="font-size: 0.7rem; font-weight: 800; color: #047857; margin: 0 0 0.35rem; letter-spacing: 0.12em; text-transform: uppercase;">Case recording</p>'
end = '            <motion style="display: flex; flex-direction: column; gap: 0.5rem;">\n                <label style="font-size: 0.75rem; font-weight: 600; color: #1f2937; text-transform: uppercase; letter-spacing: 0.05em;">Complaint Type *</label>'
end = end.replace("<motion", "<motion").replace("<motion", "<div")
end = '            <motion style="display: flex; flex-direction: column; gap: 0.5rem;">\n                <label style="font-size: 0.75rem; font-weight: 600; color: #1f2937; text-transform: uppercase; letter-spacing: 0.05em;">Complaint Type *</label>'
end = """            <div style="display: flex; flex-direction: column; gap: 0.5rem;">
                <label style="font-size: 0.75rem; font-weight: 600; color: #1f2937; text-transform: uppercase; letter-spacing: 0.05em;">Complaint Type *</label>"""

i = t.find(start)
j = t.find(end)
if i < 0 or j < 0 or j <= i:
    raise SystemExit(f"markers not found i={i} j={j}")

new_middle = """            <div style="background: #ecfdf5; border: 1px solid #a7f3d0; border-radius: 8px; padding: 0.75rem;">
                <p style="font-size: 0.7rem; font-weight: 800; color: #047857; margin: 0 0 0.35rem; letter-spacing: 0.12em; text-transform: uppercase;">Add case — centralized recording</p>
                <p style="font-size: 0.8rem; color: #065f46; margin: 0; line-height: 1.45;">Search beneficiaries (do not type names manually). System auto-fills profile data. After save: Case ID + status <strong>Pending Review</strong>.</p>
            </div>

            <section class="case-record-section">
                <h3>Complainant</h3>
                <label style="font-size: 0.75rem; font-weight: 600; color: #1f2937; text-transform: uppercase; letter-spacing: 0.05em;">Search beneficiary</label>
                <input type="text" id="complainantSearchInput" autocomplete="off" style="padding: 0.625rem; border: 1px solid #d1d5db; border-radius: 8px; font-size: 0.875rem; color: #111827; width: 100%; box-sizing: border-box;" placeholder="e.g. Juan Dela Cruz or APP-2026-001">
                <div id="complainantSearchResults" style="display: none; border: 1px solid #e5e7eb; border-radius: 8px; max-height: 10rem; overflow-y: auto; background: #fff; margin-top: 0.35rem;"></div>
                <input type="hidden" id="complainantApplicantId">
                <input type="hidden" id="relatedUnitId">
                <input type="hidden" id="newComplainantName">
                <input type="hidden" id="newComplainantPhone">
                <div id="complainantAutoFill" class="case-autofill-grid">
                    <p class="case-autofill-hint full" id="complainantAutoHint">Pick a name from search results — fields below fill automatically.</p>
                    <div class="full">
                        <label>Complainant name</label>
                        <input type="text" id="complainantAutoName" readonly placeholder="—">
                    </div>
                    <div>
                        <label>Reference no</label>
                        <input type="text" id="complainantAutoRef" readonly placeholder="—">
                    </div>
                    <div>
                        <label>Block &amp; lot</label>
                        <input type="text" id="complainantAutoUnit" readonly placeholder="—">
                    </div>
                    <div class="full">
                        <label>Contact number</label>
                        <input type="text" id="complainantAutoPhone" readonly placeholder="—">
                    </div>
                </div>
                <label class="case-walkin-toggle">
                    <input type="checkbox" id="complainantWalkinToggle" onchange="toggleComplainantWalkin()">
                    Walk-in / not in system (type name manually)
                </label>
                <div id="complainantWalkinFields" class="case-walkin-fields">
                    <div>
                        <label style="font-size: 0.75rem; font-weight: 600; color: #1f2937;">Complainant name *</label>
                        <input type="text" id="complainantWalkinName" style="padding: 0.625rem; border: 1px solid #d1d5db; border-radius: 8px; font-size: 0.875rem; width: 100%; box-sizing: border-box;" placeholder="Full name">
                    </div>
                    <div>
                        <label style="font-size: 0.75rem; font-weight: 600; color: #1f2937;">Phone (optional)</label>
                        <input type="tel" id="complainantWalkinPhone" style="padding: 0.625rem; border: 1px solid #d1d5db; border-radius: 8px; font-size: 0.875rem; width: 100%; box-sizing: border-box;" placeholder="Contact number">
                    </div>
                </div>
            </section>

            """

t = t[:i] + new_middle + t[j:]

# Respondent section
old_resp_start = """            <div style="display: flex; flex-direction: column; gap: 0.5rem;">
                <label style="font-size: 0.75rem; font-weight: 600; color: #1f2937; text-transform: uppercase; letter-spacing: 0.05em;">Respondent / against whom (search)</label>"""
old_resp_end = """            <div style="display: flex; flex-direction: column; gap: 0.5rem;">
                <label style="font-size: 0.75rem; font-weight: 600; color: #1f2937; text-transform: uppercase; letter-spacing: 0.05em;">Description *</label>"""

ri = t.find(old_resp_start)
rj = t.find(old_resp_end)
if ri < 0 or rj < 0:
    raise SystemExit("respondent markers not found")

new_resp = """            <section class="case-record-section">
                <h3>Respondent / against whom</h3>
                <label style="font-size: 0.75rem; font-weight: 600; color: #1f2937; text-transform: uppercase; letter-spacing: 0.05em;">Search beneficiary</label>
                <input type="text" id="subjectSearchInput" autocomplete="off" style="padding: 0.625rem; border: 1px solid #d1d5db; border-radius: 8px; font-size: 0.875rem; width: 100%; box-sizing: border-box;" placeholder="Name or APP reference...">
                <div id="subjectSearchResults" style="display: none; border: 1px solid #e5e7eb; border-radius: 8px; max-height: 8rem; overflow-y: auto; margin-top: 0.35rem;"></div>
                <input type="hidden" id="subjectApplicantId">
                <input type="hidden" id="newSubjectName">
                <motion id="subjectAutoFill" class="case-autofill-grid">
                    <p class="case-autofill-hint full" id="subjectAutoHint">Optional — search to link respondent profile.</p>
                    <div class="full">
                        <label>Respondent name</label>
                        <input type="text" id="subjectAutoName" readonly placeholder="—">
                    </div>
                    <div>
                        <label>Reference no</label>
                        <input type="text" id="subjectAutoRef" readonly placeholder="—">
                    </div>
                    <div>
                        <label>Block &amp; lot</label>
                        <input type="text" id="subjectAutoUnit" readonly placeholder="—">
                    </div>
                </motion>
                <label class="case-walkin-toggle">
                    <input type="checkbox" id="subjectWalkinToggle" onchange="toggleSubjectWalkin()">
                    Respondent not in system (type name manually)
                </label>
                <div id="subjectWalkinFields" class="case-walkin-fields">
                    <div>
                        <label style="font-size: 0.75rem; font-weight: 600; color: #1f2937;">Respondent name</label>
                        <input type="text" id="subjectWalkinName" style="padding: 0.625rem; border: 1px solid #d1d5db; border-radius: 8px; font-size: 0.875rem; width: 100%; box-sizing: border-box;" placeholder="Person against complaint">
                    </div>
                </div>
            </section>

            """
new_resp = new_resp.replace("<motion id", "<div id").replace("</motion>", "</div>")

t = t[:ri] + new_resp + t[rj:]

# Rename description label
t = t.replace(
    'letter-spacing: 0.05em;">Description *</label>',
    'letter-spacing: 0.05em;">Incident description *</label>',
    1,
)

# JS updates
old_apply = """function applyBeneficiarySelection(row) {
    document.getElementById('complainantApplicantId').value = row.id || '';
    document.getElementById('relatedUnitId').value = row.unit_id || '';
    document.getElementById('newComplainantName').value = row.full_name || '';
    document.getElementById('newComplainantPhone').value = row.phone_number || '';
    document.getElementById('complainantAutoRef').textContent = row.reference_number || '—';
    document.getElementById('complainantAutoUnit').textContent = row.unit_label || '—';
    document.getElementById('complainantAutoPhone').textContent = row.phone_number || '—';
    const panel = document.getElementById('complainantAutoFill');
    panel.style.display = row.id ? 'grid' : 'none';
    document.getElementById('complainantSearchResults').style.display = 'none';
    document.getElementById('complainantSearchInput').value = row.full_name || '';
}"""

new_apply = """function setReadonlyField(id, value) {
    const el = document.getElementById(id);
    if (el) el.value = value || '';
}

function clearComplainantAutoFill() {
    ['complainantAutoName', 'complainantAutoRef', 'complainantAutoUnit', 'complainantAutoPhone'].forEach((id) => setReadonlyField(id, ''));
    document.getElementById('complainantAutoFill')?.classList.remove('is-linked');
    const hint = document.getElementById('complainantAutoHint');
    if (hint) hint.style.display = 'block';
}

function applyBeneficiarySelection(row) {
    document.getElementById('complainantApplicantId').value = row.id || '';
    document.getElementById('relatedUnitId').value = row.unit_id || '';
    document.getElementById('newComplainantName').value = row.full_name || '';
    document.getElementById('newComplainantPhone').value = row.phone_number || '';
    setReadonlyField('complainantAutoName', row.full_name);
    setReadonlyField('complainantAutoRef', row.reference_number);
    setReadonlyField('complainantAutoUnit', row.unit_label);
    setReadonlyField('complainantAutoPhone', row.phone_number);
    const panel = document.getElementById('complainantAutoFill');
    if (panel) panel.classList.add('is-linked');
    const hint = document.getElementById('complainantAutoHint');
    if (hint) hint.style.display = 'none';
    document.getElementById('complainantSearchResults').style.display = 'none';
    document.getElementById('complainantSearchInput').value = row.full_name || '';
    const walkin = document.getElementById('complainantWalkinToggle');
    if (walkin?.checked) { walkin.checked = false; toggleComplainantWalkin(); }
}"""

if old_apply not in t:
    raise SystemExit("applyBeneficiarySelection not found")
t = t.replace(old_apply, new_apply, 1)

old_subj = """function applySubjectSelection(row) {
    document.getElementById('subjectApplicantId').value = row.id || '';
    document.getElementById('newSubjectName').value = row.full_name || '';
    document.getElementById('subjectAutoRef').textContent = row.reference_number || '—';
    document.getElementById('subjectAutoUnit').textContent = row.unit_label || '—';
    const panel = document.getElementById('subjectAutoFill');
    panel.style.display = row.id ? 'grid' : 'none';
    document.getElementById('subjectSearchResults').style.display = 'none';
    document.getElementById('subjectSearchInput').value = row.full_name || '';
}"""

new_subj = """function clearSubjectAutoFill() {
    ['subjectAutoName', 'subjectAutoRef', 'subjectAutoUnit'].forEach((id) => setReadonlyField(id, ''));
    document.getElementById('subjectAutoFill')?.classList.remove('is-linked');
    const hint = document.getElementById('subjectAutoHint');
    if (hint) hint.style.display = 'block';
}

function applySubjectSelection(row) {
    document.getElementById('subjectApplicantId').value = row.id || '';
    document.getElementById('newSubjectName').value = row.full_name || '';
    setReadonlyField('subjectAutoName', row.full_name);
    setReadonlyField('subjectAutoRef', row.reference_number);
    setReadonlyField('subjectAutoUnit', row.unit_label);
    document.getElementById('subjectAutoFill')?.classList.add('is-linked');
    const hint = document.getElementById('subjectAutoHint');
    if (hint) hint.style.display = 'none';
    document.getElementById('subjectSearchResults').style.display = 'none';
    document.getElementById('subjectSearchInput').value = row.full_name || '';
    const walkin = document.getElementById('subjectWalkinToggle');
    if (walkin?.checked) { walkin.checked = false; toggleSubjectWalkin(); }
}

function toggleComplainantWalkin() {
    const on = document.getElementById('complainantWalkinToggle')?.checked;
    const fields = document.getElementById('complainantWalkinFields');
    if (fields) fields.classList.toggle('is-open', !!on);
    if (on) {
        document.getElementById('complainantApplicantId').value = '';
        document.getElementById('relatedUnitId').value = '';
        clearComplainantAutoFill();
        document.getElementById('complainantSearchInput').value = '';
    }
}

function toggleSubjectWalkin() {
    const on = document.getElementById('subjectWalkinToggle')?.checked;
    const fields = document.getElementById('subjectWalkinFields');
    if (fields) fields.classList.toggle('is-open', !!on);
    if (on) {
        document.getElementById('subjectApplicantId').value = '';
        clearSubjectAutoFill();
        document.getElementById('subjectSearchInput').value = '';
    }
}"""

if old_subj not in t:
    raise SystemExit("applySubjectSelection not found")
t = t.replace(old_subj, new_subj, 1)

old_reset = """function resetNewCaseForm() {
    ['complainantSearchInput', 'newComplainantName', 'newComplainantPhone', 'newSubjectName',
     'newDescription', 'subjectSearchInput'].forEach((id) => {
        const el = document.getElementById(id);
        if (el) el.value = '';
    });
    ['complainantApplicantId', 'relatedUnitId', 'subjectApplicantId'].forEach((id) => {
        const el = document.getElementById(id);
        if (el) el.value = '';
    });
    const typeEl = document.getElementById('newCaseType');
    if (typeEl) typeEl.value = '';
    ['complainantSearchResults', 'subjectSearchResults'].forEach((id) => {
        const el = document.getElementById(id);
        if (el) { el.style.display = 'none'; el.innerHTML = ''; }
    });
    ['complainantAutoFill', 'subjectAutoFill'].forEach((id) => {
        const el = document.getElementById(id);
        if (el) el.style.display = 'none';
    });
    const files = document.getElementById('newCaseEvidenceFiles');
    if (files) files.value = '';
}"""

new_reset = """function resetNewCaseForm() {
    ['complainantSearchInput', 'newDescription', 'subjectSearchInput',
     'complainantWalkinName', 'complainantWalkinPhone', 'subjectWalkinName'].forEach((id) => {
        const el = document.getElementById(id);
        if (el) el.value = '';
    });
    ['complainantApplicantId', 'relatedUnitId', 'subjectApplicantId', 'newComplainantName', 'newComplainantPhone', 'newSubjectName'].forEach((id) => {
        const el = document.getElementById(id);
        if (el) el.value = '';
    });
    const typeEl = document.getElementById('newCaseType');
    if (typeEl) typeEl.value = '';
    ['complainantSearchResults', 'subjectSearchResults'].forEach((id) => {
        const el = document.getElementById(id);
        if (el) { el.style.display = 'none'; el.innerHTML = ''; }
    });
    clearComplainantAutoFill();
    clearSubjectAutoFill();
    ['complainantWalkinToggle', 'subjectWalkinToggle'].forEach((id) => {
        const el = document.getElementById(id);
        if (el) el.checked = false;
    });
    document.getElementById('complainantWalkinFields')?.classList.remove('is-open');
    document.getElementById('subjectWalkinFields')?.classList.remove('is-open');
    const files = document.getElementById('newCaseEvidenceFiles');
    if (files) files.value = '';
}"""

if old_reset not in t:
    raise SystemExit("resetNewCaseForm not found")
t = t.replace(old_reset, new_reset, 1)

old_create = """function createNewCase() {
    const data = {
        complainant_name: document.getElementById('newComplainantName').value.trim(),
        complainant_phone: document.getElementById('newComplainantPhone').value.trim(),"""

new_create = """function syncComplainantPayload() {
    const walkin = document.getElementById('complainantWalkinToggle')?.checked;
    if (walkin) {
        document.getElementById('newComplainantName').value = document.getElementById('complainantWalkinName')?.value.trim() || '';
        document.getElementById('newComplainantPhone').value = document.getElementById('complainantWalkinPhone')?.value.trim() || '';
    }
}

function syncSubjectPayload() {
    const walkin = document.getElementById('subjectWalkinToggle')?.checked;
    if (walkin) {
        document.getElementById('newSubjectName').value = document.getElementById('subjectWalkinName')?.value.trim() || '';
    }
}

function createNewCase() {
    syncComplainantPayload();
    syncSubjectPayload();
    const data = {
        complainant_name: document.getElementById('newComplainantName').value.trim(),
        complainant_phone: document.getElementById('newComplainantPhone').value.trim(),"""

if old_create not in t:
    raise SystemExit("createNewCase not found")
t = t.replace(old_create, new_create, 1)

old_val = """    if (!data.complainant_name || !data.case_type || !data.initial_description) {
        alert('Fill required fields');
        return;
    }"""

new_val = """    const walkin = document.getElementById('complainantWalkinToggle')?.checked;
    const linked = document.getElementById('complainantApplicantId')?.value;
    if (!walkin && !linked) {
        alert('Search and select a complainant beneficiary, or check walk-in / not in system.');
        return;
    }
    if (!data.complainant_name || !data.case_type || !data.initial_description) {
        alert('Fill required fields: complainant, complaint type, and incident description.');
        return;
    }"""

if old_val not in t:
    raise SystemExit("validation not found")
t = t.replace(old_val, new_val, 1)

p.write_text(t, encoding="utf-8")
print("Restructured Log New Case form")
