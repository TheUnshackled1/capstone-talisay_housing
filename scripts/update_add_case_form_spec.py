from pathlib import Path

p = Path(__file__).resolve().parents[1] / "templates/cases/case_management.html"
t = p.read_text(encoding="utf-8")

old_form = """            <div style="display: flex; flex-direction: column; gap: 0.5rem;">
                <label style="font-size: 0.75rem; font-weight: 600; color: #1f2937; text-transform: uppercase; letter-spacing: 0.05em;">Beneficiary search *</label>
                <input type="text" id="complainantSearchInput" autocomplete="off" style="padding: 0.625rem; border: 1px solid #d1d5db; border-radius: 8px; font-size: 0.875rem; color: #111827; width: 100%; box-sizing: border-box;" placeholder="Name, APP reference, or lot (e.g. 1-1)">
                <motion id="complainantSearchResults" style="display: none; border: 1px solid #e5e7eb; border-radius: 8px; max-height: 10rem; overflow-y: auto; background: #fff;"></motion>
                <input type="hidden" id="complainantApplicantId">
                <input type="hidden" id="relatedUnitId">
                <input type="hidden" id="newComplainantName">
                <input type="hidden" id="newComplainantPhone">
                <input type="hidden" id="newReceivedAt" value="{% if is_field_desk %}onsite{% else %}office{% endif %}">
                <input type="hidden" id="subjectApplicantId" value="">
                <input type="hidden" id="newSubjectName" value="">
                <div id="complainantAutoFill" class="case-autofill-grid" style="display: none;">
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
                <label class="case-walkin-toggle" style="margin-top: 0.25rem;">
                    <input type="checkbox" id="complainantWalkinToggle" onchange="toggleComplainantWalkin()">
                    Not in system
                </label>
                <div id="complainantWalkinFields" class="case-walkin-fields">
                    <input type="text" id="complainantWalkinName" style="padding: 0.625rem; border: 1px solid #d1d5db; border-radius: 8px; font-size: 0.875rem; width: 100%; box-sizing: border-box;" placeholder="Full name">
                    <input type="tel" id="complainantWalkinPhone" style="padding: 0.625rem; border: 1px solid #d1d5db; border-radius: 8px; font-size: 0.875rem; width: 100%; box-sizing: border-box;" placeholder="Phone (optional)">
                </div>
                <input type="checkbox" id="subjectWalkinToggle" style="display: none;">
                <div id="subjectWalkinFields" style="display: none;"><input type="text" id="subjectWalkinName"></div>
                <div id="subjectSearchResults" style="display: none;"></motion>
                <input type="text" id="subjectSearchInput" style="display: none;" tabindex="-1" aria-hidden="true">
                <div id="subjectAutoFill" style="display: none;"><input id="subjectAutoName"><input id="subjectAutoRef"><input id="subjectAutoUnit"></div>
                <p id="complainantAutoHint" style="display: none;"></p>
                <p id="subjectAutoHint" style="display: none;"></p>
            </div>"""

old_form = old_form.replace("<motion id", "<motion id").replace("</motion>", "</motion>")
old_form = old_form.replace("<motion id=\"complainantSearchResults\"", "<div id=\"complainantSearchResults\"")
old_form = old_form.replace("<motion id=\"complainantSearchResults\"", "<motion id=\"complainantSearchResults\"")
old_form = old_form.replace('id="complainantSearchResults" style="display: none;', 'id="complainantSearchResults" style="display: none;')
# read actual file chunk
start = '            <div style="display: flex; flex-direction: column; gap: 0.5rem;">\n                <label style="font-size: 0.75rem; font-weight: 600; color: #1f2937; text-transform: uppercase; letter-spacing: 0.05em;">Beneficiary search *</label>'
end = '            <div style="display: flex; flex-direction: column; gap: 0.5rem;">\n                <label style="font-size: 0.75rem; font-weight: 600; color: #1f2937; text-transform: uppercase; letter-spacing: 0.05em;">Complaint type *</label>'

i = t.find(start)
j = t.find(end)
if i < 0 or j < 0:
    raise SystemExit(f"form markers not found i={i} j={j}")

new_form = """            <input type="hidden" id="newReceivedAt" value="{% if is_field_desk %}onsite{% else %}office{% endif %}">
            <input type="hidden" id="complainantApplicantId">
            <input type="hidden" id="relatedUnitId">
            <input type="hidden" id="newComplainantName">
            <input type="hidden" id="newComplainantPhone">
            <input type="hidden" id="subjectApplicantId">
            <input type="hidden" id="newSubjectName">

            <div class="case-record-section">
                <label style="font-size: 0.75rem; font-weight: 600; color: #1f2937; text-transform: uppercase; letter-spacing: 0.05em;">Search beneficiary (complainant) *</label>
                <input type="text" id="complainantSearchInput" autocomplete="off" style="padding: 0.625rem; border: 1px solid #d1d5db; border-radius: 8px; font-size: 0.875rem; width: 100%; box-sizing: border-box;" placeholder="e.g. Juan Dela Cruz">
                <div id="complainantSearchResults" style="display: none; border: 1px solid #e5e7eb; border-radius: 8px; max-height: 10rem; overflow-y: auto; background: #fff; margin-top: 0.35rem;"></div>
                <motion id="complainantAutoFill" class="case-autofill-grid">
                    <div class="full"><label>Reference no</label><input type="text" id="complainantAutoRef" readonly placeholder="—"></div>
                    <div><label>Block &amp; lot</label><input type="text" id="complainantAutoUnit" readonly placeholder="—"></motion>
                    <div class="full"><label>Contact number</label><input type="text" id="complainantAutoPhone" readonly placeholder="—"></div>
                    <input type="hidden" id="complainantAutoName">
                </motion>
                <label class="case-walkin-toggle"><input type="checkbox" id="complainantWalkinToggle" onchange="toggleComplainantWalkin()"> Not in system</label>
                <div id="complainantWalkinFields" class="case-walkin-fields">
                    <input type="text" id="complainantWalkinName" placeholder="Full name" style="padding:0.625rem;border:1px solid #d1d5db;border-radius:8px;width:100%;box-sizing:border-box;">
                    <input type="tel" id="complainantWalkinPhone" placeholder="Phone (optional)" style="padding:0.625rem;border:1px solid #d1d5db;border-radius:8px;width:100%;box-sizing:border-box;">
                </div>
            </div>

            <div class="case-record-section">
                <label style="font-size: 0.75rem; font-weight: 600; color: #1f2937; text-transform: uppercase; letter-spacing: 0.05em;">Respondent / against whom</label>
                <input type="text" id="subjectSearchInput" autocomplete="off" style="padding: 0.625rem; border: 1px solid #d1d5db; border-radius: 8px; font-size: 0.875rem; width: 100%; box-sizing: border-box;" placeholder="Search beneficiary (optional)">
                <div id="subjectSearchResults" style="display: none; border: 1px solid #e5e7eb; border-radius: 8px; max-height: 8rem; overflow-y: auto; margin-top: 0.35rem;"></div>
                <div id="subjectAutoFill" class="case-autofill-grid">
                    <motion class="full"><label>Reference no</label><input type="text" id="subjectAutoRef" readonly placeholder="—"></div>
                    <div><label>Block &amp; lot</label><input type="text" id="subjectAutoUnit" readonly placeholder="—"></div>
                    <input type="hidden" id="subjectAutoName">
                </div>
                <label class="case-walkin-toggle"><input type="checkbox" id="subjectWalkinToggle" onchange="toggleSubjectWalkin()"> Respondent not in system</label>
                <div id="subjectWalkinFields" class="case-walkin-fields">
                    <input type="text" id="subjectWalkinName" placeholder="Person against complaint" style="padding:0.625rem;border:1px solid #d1d5db;border-radius:8px;width:100%;box-sizing:border-box;">
                </div>
            </div>

            """
new_form = new_form.replace("<motion", "<div").replace("</motion>", "</motion>")
new_form = new_form.replace("</motion>", "</div>")
new_form = new_form.replace('<div id="complainantAutoFill" class="case-autofill-grid">', '<motion id="complainantAutoFill" class="case-autofill-grid" style="display:grid;">')
new_form = new_form.replace('<motion id="complainantAutoFill"', '<div id="complainantAutoFill"')
new_form = new_form.replace('<div id="subjectAutoFill" class="case-autofill-grid">', '<div id="subjectAutoFill" class="case-autofill-grid" style="display:grid;">')

t = t[:i] + new_form + t[j:]

# incident description maxlength
t = t.replace(
    '<textarea id="newDescription" style="padding: 0.625rem; border: 1px solid #d1d5db; border-radius: 8px; font-size: 0.875rem; resize: vertical; min-height: 100px; color: #111827;" placeholder="Describe the complaint..."></textarea>',
    '<input type="text" id="newDescription" maxlength="100" style="padding: 0.625rem; border: 1px solid #d1d5db; border-radius: 8px; font-size: 0.875rem; width: 100%; box-sizing: border-box;" placeholder="Brief incident summary (max 100 characters)" oninput="updateDescCount()">\n                <span id="newDescriptionCount" style="font-size: 0.7rem; color: #64748b;">0 / 100</span>',
)

# evidence label for ronda
t = t.replace(
    '<label style="font-size: 0.75rem; font-weight: 600; color: #1f2937; text-transform: uppercase; letter-spacing: 0.05em;">Uploaded evidence</label>',
    """<label style="font-size: 0.75rem; font-weight: 600; color: #1f2937; text-transform: uppercase; letter-spacing: 0.05em;">{% if is_ronda %}Uploaded evidence (caretaker){% else %}Uploaded evidence{% endif %}</label>
                {% if is_ronda %}<p style="font-size:0.72rem;color:#64748b;margin:0;">Photo or PDF from on-site report (max 6 MB each).</p>{% endif %}""",
)

# case list type badges - replace old block
old_badges = """                    <span style="display: inline-flex; padding: 0.25rem 0.6rem; border-radius: 4px; font-size: 0.75rem; font-weight: 600;
                        {% if case.case_type == 'boundary' %}background: rgba(168, 85, 247, 0.15); color: #6b21a8;{% endif %}
                        {% if case.case_type == 'structural' %}background: rgba(239, 68, 68, 0.15); color: #991b1b;{% endif %}
                        {% if case.case_type == 'interpersonal' %}background: rgba(234, 88, 12, 0.15); color: #92400e;{% endif %}
                        {% if case.case_type == 'illegal_transfer' %}background: rgba(59, 130, 246, 0.15); color: #1e40af;{% endif %}
                        {% if case.case_type == 'unauthorized' %}background: rgba(168, 85, 247, 0.15); color: #6b21a8;{% endif %}
                        {% if case.case_type == 'damage' %}background: rgba(239, 68, 68, 0.15); color: #991b1b;{% endif %}
                        {% if case.case_type == 'noise' %}background: rgba(234, 88, 12, 0.15); color: #92400e;{% endif %}
                        {% if case.case_type == 'other' %}background: rgba(75, 85, 99, 0.15); color: #374151;{% endif %}
                    ">"""

new_badges = """                    <span style="display: inline-flex; padding: 0.25rem 0.6rem; border-radius: 4px; font-size: 0.75rem; font-weight: 600; background: rgba(59, 130, 246, 0.12); color: #1e40af;">"""

if old_badges in t:
    t = t.replace(old_badges, new_badges, 1)

# JS updates
t = t.replace(
    """    setReadonlyField('complainantAutoName', row.full_name);
    setReadonlyField('complainantAutoRef', row.reference_number);
    setReadonlyField('complainantAutoUnit', row.unit_label);
    setReadonlyField('complainantAutoPhone', row.phone_number);
    const panel = document.getElementById('complainantAutoFill');
    if (panel) {
        panel.classList.add('is-linked');
        panel.style.display = 'grid';
    }""",
    """    document.getElementById('newComplainantName').value = row.full_name || '';
    setReadonlyField('complainantAutoRef', row.reference_number);
    setReadonlyField('complainantAutoUnit', row.unit_label);
    setReadonlyField('complainantAutoPhone', row.phone_number);
    const panel = document.getElementById('complainantAutoFill');
    if (panel) panel.classList.add('is-linked');""",
)

t = t.replace(
    """function clearComplainantAutoFill() {
    ['complainantAutoName', 'complainantAutoRef', 'complainantAutoUnit', 'complainantAutoPhone'].forEach((id) => setReadonlyField(id, ''));
    const panel = document.getElementById('complainantAutoFill');
    if (panel) {
        panel.classList.remove('is-linked');
        panel.style.display = 'none';
    }
}""",
    """function clearComplainantAutoFill() {
    ['complainantAutoRef', 'complainantAutoUnit', 'complainantAutoPhone'].forEach((id) => setReadonlyField(id, ''));
    document.getElementById('complainantAutoFill')?.classList.remove('is-linked');
}""",
)

t = t.replace(
    """function clearSubjectAutoFill() {
    ['subjectAutoName', 'subjectAutoRef', 'subjectAutoUnit'].forEach((id) => setReadonlyField(id, ''));
    document.getElementById('subjectAutoFill')?.classList.remove('is-linked');
    const hint = document.getElementById('subjectAutoHint');
    if (hint) hint.style.display = 'block';
}""",
    """function clearSubjectAutoFill() {
    ['subjectAutoRef', 'subjectAutoUnit'].forEach((id) => setReadonlyField(id, ''));
    document.getElementById('subjectAutoFill')?.classList.remove('is-linked');
}""",
)

t = t.replace(
    """function applySubjectSelection(row) {
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
}""",
    """function applySubjectSelection(row) {
    document.getElementById('subjectApplicantId').value = row.id || '';
    document.getElementById('newSubjectName').value = row.full_name || '';
    setReadonlyField('subjectAutoRef', row.reference_number);
    setReadonlyField('subjectAutoUnit', row.unit_label);
    document.getElementById('subjectAutoFill')?.classList.add('is-linked');
    document.getElementById('subjectSearchResults').style.display = 'none';
    document.getElementById('subjectSearchInput').value = row.full_name || '';
    const walkin = document.getElementById('subjectWalkinToggle');
    if (walkin?.checked) { walkin.checked = false; toggleSubjectWalkin(); }
}""",
)

# add updateDescCount and validation
if 'function updateDescCount' not in t:
    t = t.replace(
        'function syncComplainantPayload() {',
        """function updateDescCount() {
    const el = document.getElementById('newDescription');
    const c = document.getElementById('newDescriptionCount');
    if (el && c) c.textContent = `${(el.value || '').length} / 100`;
}

function syncComplainantPayload() {""",
    )

t = t.replace(
    """    if (!data.complainant_name || !data.case_type || !data.initial_description) {
        alert('Fill required fields: complainant, complaint type, and incident description.');
        return;
    }""",
    """    if (!data.complainant_name || !data.case_type || !data.initial_description) {
        alert('Fill required fields: complainant, complaint type, and incident description.');
        return;
    }
    if (data.initial_description.length > 100) {
        alert('Incident description must be 100 characters or less.');
        return;
    }""",
)

t = t.replace(
    "    const files = document.getElementById('newCaseEvidenceFiles');\n    if (files) files.value = '';\n}",
    "    const files = document.getElementById('newCaseEvidenceFiles');\n    if (files) files.value = '';\n    updateDescCount();\n}",
)

p.write_text(t, encoding="utf-8")
print("Updated Add Case form spec")
