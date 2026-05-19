from pathlib import Path

p = Path(__file__).resolve().parents[1] / "templates/cases/case_management.html"
t = p.read_text(encoding="utf-8")

start = '        <motion style="display: flex; justify-content: space-between; align-items: center; padding: 1.5rem; border-bottom: 1px solid #e5e7eb;">'
start = '        <div style="display: flex; justify-content: space-between; align-items: center; padding: 1.5rem; border-bottom: 1px solid #e5e7eb;">'
end = '        <div style="padding: 1rem 1.5rem; border-top: 1px solid #e5e7eb; background: #f9fafb; display: flex; gap: 0.75rem;">'

i = t.find(start)
j = t.find(end, i)
if i < 0 or j < 0:
    raise SystemExit(f"markers not found i={i} j={j}")

new_block = """        <motion style="display: flex; justify-content: flex-end; padding: 0.75rem 1rem 0;">
            <button type="button" onclick="closeNewCaseModal()" style="padding: 0.25rem; background: transparent; border: none; color: #9ca3af; font-size: 1.5rem; cursor: pointer; width: 32px; height: 32px; display: flex; align-items: center; justify-content: center;" title="Close">✕</button>
        </motion>

        <div style="flex: 1; padding: 0 1.5rem 1.5rem; display: flex; flex-direction: column; gap: 1rem; overflow-y: auto;">
            <h2 style="margin: 0; font-size: 1.25rem; font-weight: 600; color: #111827;">Add Case</h2>

            <div style="display: flex; flex-direction: column; gap: 0.5rem;">
                <label style="font-size: 0.75rem; font-weight: 600; color: #1f2937; text-transform: uppercase; letter-spacing: 0.05em;">Beneficiary search *</label>
                <input type="text" id="complainantSearchInput" autocomplete="off" style="padding: 0.625rem; border: 1px solid #d1d5db; border-radius: 8px; font-size: 0.875rem; color: #111827; width: 100%; box-sizing: border-box;" placeholder="Name, APP reference, or lot (e.g. 1-1)">
                <div id="complainantSearchResults" style="display: none; border: 1px solid #e5e7eb; border-radius: 8px; max-height: 10rem; overflow-y: auto; background: #fff;"></div>
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
                    </motion>
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
                <motion id="subjectSearchResults" style="display: none;"></motion>
                <input type="text" id="subjectSearchInput" style="display: none;" tabindex="-1" aria-hidden="true">
                <div id="subjectAutoFill" style="display: none;"><input id="subjectAutoName"><input id="subjectAutoRef"><input id="subjectAutoUnit"></div>
                <p id="complainantAutoHint" style="display: none;"></p>
                <p id="subjectAutoHint" style="display: none;"></p>
            </div>

            <div style="display: flex; flex-direction: column; gap: 0.5rem;">
                <label style="font-size: 0.75rem; font-weight: 600; color: #1f2937; text-transform: uppercase; letter-spacing: 0.05em;">Complaint type *</label>
                <select id="newCaseType" style="padding: 0.625rem; border: 1px solid #d1d5db; border-radius: 8px; font-size: 0.875rem; color: #111827;">
                    <option value="">— Select —</option>
                    {% for code, label in case_type_choices %}
                    <option value="{{ code }}">{{ label }}</option>
                    {% endfor %}
                </select>
            </div>

            <div style="display: flex; flex-direction: column; gap: 0.5rem;">
                <label style="font-size: 0.75rem; font-weight: 600; color: #1f2937; text-transform: uppercase; letter-spacing: 0.05em;">Incident description *</label>
                <textarea id="newDescription" style="padding: 0.625rem; border: 1px solid #d1d5db; border-radius: 8px; font-size: 0.875rem; resize: vertical; min-height: 100px; color: #111827;" placeholder="Describe the complaint..."></textarea>
            </div>

            <div style="display: flex; flex-direction: column; gap: 0.5rem;">
                <label style="font-size: 0.75rem; font-weight: 600; color: #1f2937; text-transform: uppercase; letter-spacing: 0.05em;">Uploaded evidence</label>
                <input type="file" id="newCaseEvidenceFiles" accept="image/jpeg,image/png,image/webp,application/pdf" multiple style="font-size: 0.8rem;">
            </div>
        </div>

        """
new_block = new_block.replace("<motion", "<div").replace("</motion>", "</motion>")
new_block = new_block.replace("</motion>\n                </div>", "</motion>\n                </div>")
new_block = new_block.replace(
    '<input type="text" id="complainantAutoPhone" readonly placeholder="—">\n                    </motion>',
    '<input type="text" id="complainantAutoPhone" readonly placeholder="—">\n                    </div>',
)
new_block = new_block.replace('<motion id="subjectSearchResults"', '<div id="subjectSearchResults"')

t = t[:i] + new_block + t[j:]

t = t.replace('>Log Case</button>', '>Add Case</button>', 1)

# createNewCase: read hidden received at
old_recv = "received_at_location: document.getElementById('newReceivedAt').value,"
if old_recv in t:
    pass  # still works with hidden input

# applyBeneficiarySelection - show grid
old_panel = """    const panel = document.getElementById('complainantAutoFill');
    if (panel) panel.classList.add('is-linked');
    const hint = document.getElementById('complainantAutoHint');
    if (hint) hint.style.display = 'none';"""
new_panel = """    const panel = document.getElementById('complainantAutoFill');
    if (panel) {
        panel.classList.add('is-linked');
        panel.style.display = 'grid';
    }"""
if old_panel in t:
    t = t.replace(old_panel, new_panel, 1)

old_clear = """function clearComplainantAutoFill() {
    ['complainantAutoName', 'complainantAutoRef', 'complainantAutoUnit', 'complainantAutoPhone'].forEach((id) => setReadonlyField(id, ''));
    document.getElementById('complainantAutoFill')?.classList.remove('is-linked');
    const hint = document.getElementById('complainantAutoHint');
    if (hint) hint.style.display = 'block';
}"""
new_clear = """function clearComplainantAutoFill() {
    ['complainantAutoName', 'complainantAutoRef', 'complainantAutoUnit', 'complainantAutoPhone'].forEach((id) => setReadonlyField(id, ''));
    const panel = document.getElementById('complainantAutoFill');
    if (panel) {
        panel.classList.remove('is-linked');
        panel.style.display = 'none';
    }
}"""
if old_clear in t:
    t = t.replace(old_clear, new_clear, 1)

p.write_text(t, encoding="utf-8")
print("Simplified Add Case modal")
