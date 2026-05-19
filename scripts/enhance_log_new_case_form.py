"""Align Log New Case modal with CASE RECORDING spec."""
from pathlib import Path

p = Path(__file__).resolve().parents[1] / "templates/cases/case_management.html"
t = p.read_text(encoding="utf-8")

old_block = """            <div style="display: flex; flex-direction: column; gap: 0.5rem;">
                <label style="font-size: 0.75rem; font-weight: 600; color: #1f2937; text-transform: uppercase; letter-spacing: 0.05em;">Search beneficiary (auto-fill)</label>
                <input type="text" id="complainantSearchInput" autocomplete="off" style="padding: 0.625rem; border: 1px solid #d1d5db; border-radius: 8px; font-size: 0.875rem; color: #111827;" placeholder="Name or APP reference...">
                <motion id="complainantSearchResults" style="display: none; border: 1px solid #e5e7eb; border-radius: 8px; max-height: 10rem; overflow-y: auto; background: #fff;"></motion>
                <p id="complainantLinkedSummary" style="display: none; font-size: 0.75rem; color: #047857; margin: 0; font-weight: 600;"></p>
                <input type="hidden" id="complainantApplicantId">
                <input type="hidden" id="relatedUnitId">
            </div>"""
old_block = old_block.replace("<motion id", "<div id").replace("</motion>", "</div>")

new_block = """            <div style="background: #ecfdf5; border: 1px solid #a7f3d0; border-radius: 8px; padding: 0.75rem;">
                <p style="font-size: 0.7rem; font-weight: 800; color: #047857; margin: 0 0 0.35rem; letter-spacing: 0.12em; text-transform: uppercase;">Case recording</p>
                <p style="font-size: 0.8rem; color: #065f46; margin: 0; line-height: 1.45;">Search beneficiaries to auto-fill — avoids spelling errors and wrong linkage. After save: Case ID generated, status <strong>Pending Review</strong>.</p>
            </div>

            <div style="display: flex; flex-direction: column; gap: 0.5rem;">
                <label style="font-size: 0.75rem; font-weight: 600; color: #1f2937; text-transform: uppercase; letter-spacing: 0.05em;">Search beneficiary (complainant)</label>
                <input type="text" id="complainantSearchInput" autocomplete="off" style="padding: 0.625rem; border: 1px solid #d1d5db; border-radius: 8px; font-size: 0.875rem; color: #111827;" placeholder="Name or APP reference...">
                <div id="complainantSearchResults" style="display: none; border: 1px solid #e5e7eb; border-radius: 8px; max-height: 10rem; overflow-y: auto; background: #fff;"></div>
                <input type="hidden" id="complainantApplicantId">
                <input type="hidden" id="relatedUnitId">
                <div id="complainantAutoFill" style="display: none; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 0.75rem; grid-template-columns: 1fr 1fr; gap: 0.5rem 1rem;">
                    <motion style="grid-column: 1 / -1;">
                        <span style="font-size: 0.65rem; font-weight: 700; color: #64748b; text-transform: uppercase;">Auto-filled from profile</span>
                    </div>
                    <div>
                        <span style="font-size: 0.65rem; color: #64748b;">Reference No</span>
                        <p id="complainantAutoRef" style="margin: 0.15rem 0 0; font-size: 0.85rem; font-weight: 600; color: #0f172a;">—</p>
                    </div>
                    <div>
                        <span style="font-size: 0.65rem; color: #64748b;">Block &amp; Lot</span>
                        <p id="complainantAutoUnit" style="margin: 0.15rem 0 0; font-size: 0.85rem; font-weight: 600; color: #0f172a;">—</p>
                    </div>
                    <div style="grid-column: 1 / -1;">
                        <span style="font-size: 0.65rem; color: #64748b;">Contact number</span>
                        <p id="complainantAutoPhone" style="margin: 0.15rem 0 0; font-size: 0.85rem; font-weight: 600; color: #0f172a;">—</p>
                    </div>
                </div>
            </div>"""
new_block = new_block.replace("<motion style", "<div style")

if old_block not in t:
    raise SystemExit("complainant block not found")
t = t.replace(old_block, new_block, 1)

old_subject = """            <div style="display: flex; flex-direction: column; gap: 0.5rem;">
                <label style="font-size: 0.75rem; font-weight: 600; color: #1f2937; text-transform: uppercase; letter-spacing: 0.05em;">Respondent / against whom (search)</label>
                <input type="text" id="subjectSearchInput" autocomplete="off" style="padding: 0.625rem; border: 1px solid #d1d5db; border-radius: 8px; font-size: 0.875rem;" placeholder="Name or APP reference...">
                <div id="subjectSearchResults" style="display: none; border: 1px solid #e5e7eb; border-radius: 8px; max-height: 8rem; overflow-y: auto;"></div>
                <input type="hidden" id="subjectApplicantId">
            </motion>"""
old_subject = old_subject.replace("</motion>", "</div>")

new_subject = """            <div style="display: flex; flex-direction: column; gap: 0.5rem;">
                <label style="font-size: 0.75rem; font-weight: 600; color: #1f2937; text-transform: uppercase; letter-spacing: 0.05em;">Respondent / against whom (search)</label>
                <input type="text" id="subjectSearchInput" autocomplete="off" style="padding: 0.625rem; border: 1px solid #d1d5db; border-radius: 8px; font-size: 0.875rem;" placeholder="Name or APP reference...">
                <div id="subjectSearchResults" style="display: none; border: 1px solid #e5e7eb; border-radius: 8px; max-height: 8rem; overflow-y: auto;"></div>
                <input type="hidden" id="subjectApplicantId">
                <div id="subjectAutoFill" style="display: none; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 0.75rem; grid-template-columns: 1fr 1fr; gap: 0.5rem 1rem;">
                    <div style="grid-column: 1 / -1;">
                        <span style="font-size: 0.65rem; font-weight: 700; color: #64748b; text-transform: uppercase;">Auto-filled (respondent)</span>
                    </div>
                    <div>
                        <span style="font-size: 0.65rem; color: #64748b;">Reference No</span>
                        <p id="subjectAutoRef" style="margin: 0.15rem 0 0; font-size: 0.85rem; font-weight: 600; color: #0f172a;">—</p>
                    </div>
                    <div>
                        <span style="font-size: 0.65rem; color: #64748b;">Block &amp; Lot</span>
                        <p id="subjectAutoUnit" style="margin: 0.15rem 0 0; font-size: 0.85rem; font-weight: 600; color: #0f172a;">—</p>
                    </div>
                </div>
            </div>"""

if old_subject not in t:
    raise SystemExit("subject block not found")
t = t.replace(old_subject, new_subject, 1)

old_desc_hint = """            <div style="background: #dbeafe; border: 1px solid #93c5fd; border-radius: 8px; padding: 0.75rem;">
                <p style="font-size: 0.75rem; color: #1d4ed8; margin: 0; line-height: 1.4;">Steps 1–2: Report and record. Case ID is assigned with status <strong>Pending Review</strong> for THA desk follow-up.</p>
            </div>"""

evidence_block = """            <div style="display: flex; flex-direction: column; gap: 0.5rem;">
                <label style="font-size: 0.75rem; font-weight: 600; color: #1f2937; text-transform: uppercase; letter-spacing: 0.05em;">Evidence (optional)</label>
                <input type="file" id="newCaseEvidenceFiles" accept="image/jpeg,image/png,image/webp,application/pdf" multiple style="font-size: 0.8rem;">
                <p style="font-size: 0.7rem; color: #64748b; margin: 0;">Photos or PDF (max 6 MB each). Attached when case is saved.</p>
            </div>

            <div style="background: #dbeafe; border: 1px solid #93c5fd; border-radius: 8px; padding: 0.75rem;">
                <p style="font-size: 0.75rem; color: #1d4ed8; margin: 0; line-height: 1.4;">Steps 1–2: Report and record. Case ID is assigned with status <strong>Pending Review</strong> for THA desk follow-up.</p>
            </div>"""

if old_desc_hint not in t:
    raise SystemExit("hint block not found")
t = t.replace(old_desc_hint, evidence_block, 1)

old_apply = """function applyBeneficiarySelection(row) {
    document.getElementById('complainantApplicantId').value = row.id || '';
    document.getElementById('relatedUnitId').value = row.unit_id || '';
    document.getElementById('newComplainantName').value = row.full_name || '';
    document.getElementById('newComplainantPhone').value = row.phone_number || '';
    const parts = [row.reference_number, row.unit_label, row.site_name].filter(Boolean);
    const summary = document.getElementById('complainantLinkedSummary');
    summary.textContent = parts.length ? 'Linked: ' + parts.join(' · ') : '';
    summary.style.display = parts.length ? 'block' : 'none';
    document.getElementById('complainantSearchResults').style.display = 'none';
    document.getElementById('complainantSearchInput').value = row.full_name || '';
}"""

new_apply = """function applyBeneficiarySelection(row) {
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
}

function applySubjectSelection(row) {
    document.getElementById('subjectApplicantId').value = row.id || '';
    document.getElementById('newSubjectName').value = row.full_name || '';
    document.getElementById('subjectAutoRef').textContent = row.reference_number || '—';
    document.getElementById('subjectAutoUnit').textContent = row.unit_label || '—';
    const panel = document.getElementById('subjectAutoFill');
    panel.style.display = row.id ? 'grid' : 'none';
    document.getElementById('subjectSearchResults').style.display = 'none';
    document.getElementById('subjectSearchInput').value = row.full_name || '';
}

function resetNewCaseForm() {
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

if old_apply not in t:
    raise SystemExit("applyBeneficiarySelection not found")
t = t.replace(old_apply, new_apply, 1)

t = t.replace(
    """function openNewCaseModal() {
    const caseModal = document.getElementById('caseModal');
    if (caseModal) caseModal.style.display = 'none';
    document.body.style.overflow = 'hidden';
    document.getElementById('newCaseModal').style.display = 'flex';
}""",
    """function openNewCaseModal() {
    const caseModal = document.getElementById('caseModal');
    if (caseModal) caseModal.style.display = 'none';
    resetNewCaseForm();
    document.body.style.overflow = 'hidden';
    document.getElementById('newCaseModal').style.display = 'flex';
}""",
)

t = t.replace(
    """                btn.onclick = () => {
                    document.getElementById('subjectApplicantId').value = d.results[idx].id || '';
                    document.getElementById('newSubjectName').value = d.results[idx].full_name || '';
                    box.style.display = 'none';
                };""",
    """                btn.onclick = () => applySubjectSelection(d.results[idx]);""",
)

old_create = """    fetch(`/cases/${CASE_POSITION}/create/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() },
        body: JSON.stringify(data),
    })
        .then((r) => r.json())
        .then((d) => {
            if (d.success) {
                alert(d.message);
                closeNewCaseModal();
                location.reload();
            } else alert('Error: ' + d.error);
        });
}"""

new_create = """    fetch(`/cases/${CASE_POSITION}/create/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() },
        body: JSON.stringify(data),
    })
        .then((r) => r.json())
        .then(async (d) => {
            if (!d.success) {
                alert('Error: ' + d.error);
                return;
            }
            const fileInput = document.getElementById('newCaseEvidenceFiles');
            const files = fileInput?.files ? Array.from(fileInput.files) : [];
            if (files.length && d.case?.id) {
                for (const file of files) {
                    const fd = new FormData();
                    fd.append('file', file);
                    fd.append('caption', 'Initial intake evidence');
                    await fetch(`/cases/${CASE_POSITION}/${d.case.id}/evidence/upload/`, {
                        method: 'POST',
                        headers: { 'X-CSRFToken': csrfToken() },
                        body: fd,
                    });
                }
            }
            alert(d.message);
            closeNewCaseModal();
            location.reload();
        });
}"""

if old_create not in t:
    raise SystemExit("createNewCase fetch block not found")
t = t.replace(old_create, new_create, 1)

p.write_text(t, encoding="utf-8")
print("Enhanced Log New Case form")
