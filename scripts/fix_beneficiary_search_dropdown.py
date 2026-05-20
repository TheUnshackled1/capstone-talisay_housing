from pathlib import Path

p = Path(__file__).resolve().parents[1] / "templates/cases/case_management.html"
t = p.read_text(encoding="utf-8")

old_c = """                <input type="text" id="complainantSearchInput" autocomplete="off" style="padding: 0.625rem; border: 1px solid #d1d5db; border-radius: 8px; font-size: 0.875rem; width: 100%; box-sizing: border-box;" placeholder="e.g. Juan Dela Cruz">
                <motion id="complainantSearchResults" style="display: none; border: 1px solid #e5e7eb; border-radius: 8px; max-height: 10rem; overflow-y: auto; background: #fff; margin-top: 0.35rem;"></motion>
                <div id="complainantAutoFill" class="case-autofill-grid" style="display:grid;">
                    <div class="full"><label>Reference no</label><input type="text" id="complainantAutoRef" readonly placeholder="—"></div>
                    <motion><label>Block &amp; lot</label><input type="text" id="complainantAutoUnit" readonly placeholder="—"></div>
                    <div class="full"><label>Contact number</label><input type="text" id="complainantAutoPhone" readonly placeholder="—"></div>
                    <input type="hidden" id="complainantAutoName">
                </div>"""

# fix accidental motion in old_c read from file exactly
old_c = """                <input type="text" id="complainantSearchInput" autocomplete="off" style="padding: 0.625rem; border: 1px solid #d1d5db; border-radius: 8px; font-size: 0.875rem; width: 100%; box-sizing: border-box;" placeholder="e.g. Juan Dela Cruz">
                <div id="complainantSearchResults" style="display: none; border: 1px solid #e5e7eb; border-radius: 8px; max-height: 10rem; overflow-y: auto; background: #fff; margin-top: 0.35rem;"></motion>
                <div id="complainantAutoFill" class="case-autofill-grid" style="display:grid;">
                    <div class="full"><label>Reference no</label><input type="text" id="complainantAutoRef" readonly placeholder="—"></div>
                    <div><label>Block &amp; lot</label><input type="text" id="complainantAutoUnit" readonly placeholder="—"></div>
                    <div class="full"><label>Contact number</label><input type="text" id="complainantAutoPhone" readonly placeholder="—"></div>
                    <input type="hidden" id="complainantAutoName">
                </div>"""
old_c = old_c.replace("</motion>", "</motion>").replace("</motion>", "</div>")

new_c = """                <motion class="case-beneficiary-search-wrap">
                    <input type="text" id="complainantSearchInput" autocomplete="off" style="padding: 0.625rem; border: 1px solid #d1d5db; border-radius: 8px; font-size: 0.875rem; width: 100%; box-sizing: border-box;" placeholder="e.g. Juan Dela Cruz, APP ref, or 1-1">
                    <div id="complainantSearchResults" class="case-search-results" style="display: none;"></div>
                </motion>
                <p style="font-size: 0.7rem; color: #94a3b8; margin: 0.35rem 0 0;">Type 2+ characters — pick an occupant from the list.</p>
                <div id="complainantAutoFill" class="case-autofill-grid" style="display:grid;">
                    <div class="full"><label>Complainant name</label><input type="text" id="complainantAutoName" readonly placeholder="—"></div>
                    <div><label>Reference no</label><input type="text" id="complainantAutoRef" readonly placeholder="—"></div>
                    <div><label>Block &amp; lot</label><input type="text" id="complainantAutoUnit" readonly placeholder="—"></div>
                    <div class="full"><label>Contact number</label><input type="text" id="complainantAutoPhone" readonly placeholder="—"></div>
                </div>"""
new_c = new_c.replace("<motion class", "<div class").replace("</motion>", "</div>")

if old_c not in t:
    raise SystemExit("complainant block not found")
t = t.replace(old_c, new_c, 1)

old_s = """                <input type="text" id="subjectSearchInput" autocomplete="off" style="padding: 0.625rem; border: 1px solid #d1d5db; border-radius: 8px; font-size: 0.875rem; width: 100%; box-sizing: border-box;" placeholder="Search beneficiary (optional)">
                <div id="subjectSearchResults" style="display: none; border: 1px solid #e5e7eb; border-radius: 8px; max-height: 8rem; overflow-y: auto; margin-top: 0.35rem;"></div>
                <div id="subjectAutoFill" class="case-autofill-grid" style="display:grid;">
                    <div class="full"><label>Reference no</label><input type="text" id="subjectAutoRef" readonly placeholder="—"></div>
                    <div><label>Block &amp; lot</label><input type="text" id="subjectAutoUnit" readonly placeholder="—"></div>
                    <input type="hidden" id="subjectAutoName">
                </div>"""

new_s = """                <div class="case-beneficiary-search-wrap">
                    <input type="text" id="subjectSearchInput" autocomplete="off" style="padding: 0.625rem; border: 1px solid #d1d5db; border-radius: 8px; font-size: 0.875rem; width: 100%; box-sizing: border-box;" placeholder="e.g. name, APP ref, or lot">
                    <div id="subjectSearchResults" class="case-search-results" style="display: none;"></div>
                </div>
                <div id="subjectAutoFill" class="case-autofill-grid" style="display:grid;">
                    <div class="full"><label>Respondent name</label><input type="text" id="subjectAutoName" readonly placeholder="—"></div>
                    <div><label>Reference no</label><input type="text" id="subjectAutoRef" readonly placeholder="—"></div>
                    <div><label>Block &amp; lot</label><input type="text" id="subjectAutoUnit" readonly placeholder="—"></div>
                </div>"""

if old_s not in t:
    raise SystemExit("subject block not found")
t = t.replace(old_s, new_s, 1)

# JS
if "function runBeneficiarySearch" not in t:
    t = t.replace(
        "function runComplainantSearch(q) {\n    const box = document.getElementById('complainantSearchResults');",
        """function runBeneficiarySearch(q, box, onSelect) {
    if (!box) return;
    if (!q || q.length < 2) {
        box.style.display = 'none';
        box.innerHTML = '';
        return;
    }
    box.innerHTML = '<p style="padding:0.5rem;font-size:0.8rem;color:#64748b;margin:0;">Searching…</p>';
    box.style.display = 'block';
    fetch(`/cases/${CASE_POSITION}/beneficiary-search/?q=${encodeURIComponent(q)}`)
        .then((r) => r.json())
        .then((d) => {
            if (!d.success || !d.results.length) {
                box.innerHTML = '<p style="padding: 0.5rem; font-size: 0.8rem; color: #64748b; margin: 0;">No matches. Try name, APP ref, or lot (1-1).</p>';
                box.style.display = 'block';
                return;
            }
            bindBeneficiarySearchResults(box, d.results, onSelect);
        })
        .catch(() => {
            box.innerHTML = '<p style="padding:0.5rem;font-size:0.8rem;color:#b91c1c;margin:0;">Search failed.</p>';
            box.style.display = 'block';
        });
}

function runComplainantSearch(q) {
    runBeneficiarySearch(q, document.getElementById('complainantSearchResults'), applyBeneficiarySelection);
}

function _runComplainantSearchOld(q) {
    const box = document.getElementById('complainantSearchResults');""",
    )
    end = t.find("function runSubjectSearch(q) {")
    start = t.find("function _runComplainantSearchOld(q) {")
    if start > 0 and end > start:
        t = t[:start] + t[end:]

t = t.replace(
    """function runSubjectSearch(q) {
    const box = document.getElementById('subjectSearchResults');
    if (!q || q.length < 2) { box.style.display = 'none'; box.innerHTML = ''; return; }
    fetch(`/cases/${CASE_POSITION}/beneficiary-search/?q=${encodeURIComponent(q)}`)
        .then((r) => r.json())
        .then((d) => {
            if (!d.success || !d.results.length) {
                box.innerHTML = '<p style="padding:0.5rem;font-size:0.8rem;color:#64748b;margin:0;">No occupied unit matches.</p>';
                box.style.display = 'block';
                return;
            }
            bindBeneficiarySearchResults(box, d.results, applySubjectSelection);
        });
}""",
    "function runSubjectSearch(q) {\n    runBeneficiarySearch(q, document.getElementById('subjectSearchResults'), applySubjectSelection);\n}",
)

for a, b in [
    ("setReadonlyField('complainantAutoRef', row.reference_number);", "setReadonlyField('complainantAutoName', row.full_name);\n    setReadonlyField('complainantAutoRef', row.reference_number);"),
    ("['complainantAutoRef', 'complainantAutoUnit', 'complainantAutoPhone']", "['complainantAutoName', 'complainantAutoRef', 'complainantAutoUnit', 'complainantAutoPhone']"),
    ("['subjectAutoRef', 'subjectAutoUnit']", "['subjectAutoName', 'subjectAutoRef', 'subjectAutoUnit']"),
    ("setReadonlyField('subjectAutoRef', row.reference_number);", "setReadonlyField('subjectAutoName', row.full_name);\n    setReadonlyField('subjectAutoRef', row.reference_number);"),
]:
    t = t.replace(a, b, 1)

p.write_text(t, encoding="utf-8")
print("OK")
