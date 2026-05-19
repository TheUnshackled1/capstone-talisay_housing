from pathlib import Path

p = Path(__file__).resolve().parents[1] / "templates/cases/case_management.html"
text = p.read_text(encoding="utf-8")

start = text.find("<!-- JavaScript -->")
end = text.find("{% endblock %}", start)
if start == -1 or end == -1:
    raise SystemExit("markers not found")

new_script = r'''<!-- JavaScript -->
<script>
const CASE_POSITION = '{{ request.user.position }}';
let currentCaseId = null;
let complainantSearchTimer = null;

function csrfToken() {
    return document.querySelector('[name=csrfmiddlewaretoken]').value;
}

function resetCaseModalSections() {
    ['subjectSection', 'investigationSection', 'referralSection', 'resolutionSection',
     'notesSection', 'priorCasesSection', 'updateFormSection'].forEach((id) => {
        const el = document.getElementById(id);
        if (el) el.style.display = 'none';
    });
    const evidenceList = document.getElementById('evidenceList');
    if (evidenceList) evidenceList.innerHTML = '';
    const updateNote = document.getElementById('updateNote');
    const newStatus = document.getElementById('newStatus');
    if (updateNote) updateNote.value = '';
    if (newStatus) newStatus.value = '';
}

function openCaseModal(caseId) {
    currentCaseId = caseId;
    resetCaseModalSections();
    fetch(`/cases/${CASE_POSITION}/${caseId}/details/`)
        .then((r) => r.json())
        .then((d) => {
            if (d.success) populateCaseModal(d.case);
            else alert('Error: ' + d.error);
        });
}

function populateCaseModal(c) {
    document.getElementById('modalCaseNumber').textContent = c.case_number;
    document.getElementById('modalCaseDate').textContent =
        `Filed: ${new Date(c.received_at).toLocaleDateString()} · Received by: ${c.received_by}`;
    document.getElementById('modalComplainantName').textContent = c.complainant_name;
    document.getElementById('modalComplainantPhone').textContent = c.complainant_phone || 'No phone';
    document.getElementById('modalComplainantRef').textContent = c.complainant_reference
        ? `Ref: ${c.complainant_reference}` : '';
    document.getElementById('modalComplainantUnit').textContent = c.complainant_unit_label || '';
    document.getElementById('modalDescription').textContent = c.initial_description;
    document.getElementById('modalComplaintType').textContent = c.case_type_display;

    if (c.subject_name) {
        document.getElementById('subjectSection').style.display = 'block';
        document.getElementById('modalSubjectName').textContent = c.subject_name +
            (c.subject_reference ? ` (${c.subject_reference})` : '');
    }

    if (c.investigation_notes) {
        document.getElementById('investigationSection').style.display = 'block';
        document.getElementById('modalInvestigationNotes').textContent = c.investigation_notes;
        document.getElementById('modalInvestigatedBy').textContent = `Investigated by: ${c.investigated_by}`;
    }

    if (c.referred_to) {
        document.getElementById('referralSection').style.display = 'block';
        document.getElementById('modalReferredTo').textContent = `Referred to: ${c.referred_to}`;
        document.getElementById('modalReferralNotes').textContent = c.referral_notes || '';
        document.getElementById('modalReferralDate').textContent = c.referred_at
            ? `Referred: ${new Date(c.referred_at).toLocaleDateString()}` : '';
    }

    if (c.resolution_notes) {
        document.getElementById('resolutionSection').style.display = 'block';
        document.getElementById('modalResolutionNotes').textContent = c.resolution_notes;
        document.getElementById('modalResolvedDate').textContent = c.resolved_at
            ? `Resolved: ${new Date(c.resolved_at).toLocaleDateString()}` : '';
    }

    if (c.prior_cases && c.prior_cases.length) {
        document.getElementById('priorCasesSection').style.display = 'block';
        document.getElementById('priorCasesList').innerHTML = c.prior_cases.map((pc) => `
            <motion style="font-size: 0.8rem; padding: 0.5rem; background: #f8fafc; border-radius: 6px;">
                <strong>${pc.case_number}</strong> — ${pc.case_type_display} (${pc.status_display})
            </div>`).join('');
    }

    const evidenceSection = document.getElementById('evidenceSection');
    evidenceSection.style.display = 'block';
    const evidenceList = document.getElementById('evidenceList');
    if (c.evidence && c.evidence.length) {
        evidenceList.innerHTML = c.evidence.map((ev) => `
            <div style="font-size: 0.8rem; padding: 0.5rem; background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 6px;">
                <a href="${ev.url}" target="_blank" rel="noopener">${ev.caption || 'View file'}</a>
                <div style="color: #64748b; margin-top: 0.2rem;">${ev.uploaded_by} · ${new Date(ev.uploaded_at).toLocaleString()}</div>
            </div>`).join('');
    } else {
        evidenceList.innerHTML = '<p style="font-size: 0.8rem; color: #64748b; margin: 0;">No evidence uploaded yet.</p>';
    }
    document.getElementById('evidenceUploadForm').style.display =
        ['resolved', 'closed'].includes(c.status) ? 'none' : 'flex';

    if (c.notes && c.notes.length > 0) {
        document.getElementById('notesSection').style.display = 'block';
        document.getElementById('notesList').innerHTML = c.notes.map((n) => `
            <div style="background: var(--gray-50); border: 1px solid var(--gray-200); border-radius: 8px; padding: 0.75rem;">
                <p style="margin: 0 0 0.25rem; color: var(--gray-900); font-weight: 500; font-size: 0.85rem;">${n.created_by}</p>
                <p style="margin: 0 0 0.25rem; color: var(--gray-900); font-size: 0.85rem; line-height: 1.4;">${n.note}</p>
                <p style="margin: 0; font-size: 0.75rem; color: var(--gray-600);">${new Date(n.created_at).toLocaleString()}</p>
            </div>`).join('');
    }

    if (!['resolved', 'closed'].includes(c.status)) {
        document.getElementById('updateFormSection').style.display = 'flex';
    }

    document.getElementById('caseModal').style.display = 'flex';
}

function closeCaseModal(e) {
    if (e && e.target.id !== 'caseModal') return;
    document.getElementById('caseModal').style.display = 'none';
}

function openNewCaseModal() {
    document.getElementById('newCaseModal').style.display = 'flex';
}

function closeNewCaseModal(e) {
    if (e && e.target.id !== 'newCaseModal') return;
    document.getElementById('newCaseModal').style.display = 'none';
}

function applyBeneficiarySelection(row) {
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
}

function runComplainantSearch(q) {
    const box = document.getElementById('complainantSearchResults');
    if (!q || q.length < 2) {
        box.style.display = 'none';
        box.innerHTML = '';
        return;
    }
    fetch(`/cases/${CASE_POSITION}/beneficiary-search/?q=${encodeURIComponent(q)}`)
        .then((r) => r.json())
        .then((d) => {
            if (!d.success || !d.results.length) {
                box.innerHTML = '<p style="padding: 0.5rem; font-size: 0.8rem; color: #64748b; margin: 0;">No matches.</p>';
                box.style.display = 'block';
                return;
            }
            box.innerHTML = d.results.map((row, i) => `
                <button type="button" data-index="${i}" style="display: block; width: 100%; text-align: left; padding: 0.5rem 0.65rem; border: none; border-bottom: 1px solid #f1f5f9; background: #fff; cursor: pointer; font-size: 0.8rem;">
                    <strong>${row.full_name}</strong><br>
                    <span style="color: #64748b;">${row.reference_number || ''}${row.unit_label ? ' · ' + row.unit_label : ''}</span>
                </button>`).join('');
            box.style.display = 'block';
            box.querySelectorAll('button').forEach((btn) => {
                const idx = parseInt(btn.dataset.index, 10);
                btn.onclick = () => applyBeneficiarySelection(d.results[idx]);
            });
        });
}

function createNewCase() {
    const data = {
        complainant_name: document.getElementById('newComplainantName').value.trim(),
        complainant_phone: document.getElementById('newComplainantPhone').value.trim(),
        case_type: document.getElementById('newCaseType').value,
        received_at_location: document.getElementById('newReceivedAt').value,
        initial_description: document.getElementById('newDescription').value.trim(),
        subject_name: document.getElementById('newSubjectName').value.trim(),
        complainant_applicant_id: document.getElementById('complainantApplicantId').value,
        related_unit_id: document.getElementById('relatedUnitId').value,
    };
    if (!data.complainant_name || !data.case_type || !data.initial_description) {
        alert('Fill required fields');
        return;
    }
    fetch(`/cases/${CASE_POSITION}/create/`, {
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
}

async function postCaseUpdate(payload) {
    const res = await fetch(`/cases/${CASE_POSITION}/update/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() },
        body: JSON.stringify(payload),
    });
    return res.json();
}

async function saveUpdate() {
    const note = document.getElementById('updateNote').value.trim();
    const newStatus = document.getElementById('newStatus').value.trim();
    if (!note && !newStatus) {
        alert('Add a note and/or choose a new status.');
        return;
    }
    try {
        if (newStatus) {
            const statusData = await postCaseUpdate({
                case_id: currentCaseId,
                action: 'change_status',
                new_status: newStatus,
            });
            if (!statusData.success) throw new Error(statusData.error || 'Status update failed');
        }
        if (note) {
            const noteData = await postCaseUpdate({
                case_id: currentCaseId,
                action: 'add_note',
                note,
            });
            if (!noteData.success) throw new Error(noteData.error || 'Note failed');
        }
        alert('Case updated.');
        closeCaseModal();
        location.reload();
    } catch (err) {
        alert(err.message || 'Update failed');
    }
}

function uploadCaseEvidence() {
    const fileInput = document.getElementById('evidenceFile');
    if (!fileInput.files || !fileInput.files[0]) {
        alert('Choose a file to upload.');
        return;
    }
    const fd = new FormData();
    fd.append('file', fileInput.files[0]);
    fd.append('caption', document.getElementById('evidenceCaption').value.trim());
    fetch(`/cases/${CASE_POSITION}/${currentCaseId}/evidence/upload/`, {
        method: 'POST',
        headers: { 'X-CSRFToken': csrfToken() },
        body: fd,
    })
        .then((r) => r.json())
        .then((d) => {
            if (d.success) {
                alert(d.message);
                openCaseModal(currentCaseId);
            } else alert(d.error || 'Upload failed');
        });
}

function applyCaseFilters() {
    const url = new URL(window.location.href);
    const q = document.getElementById('searchInput').value.trim();
    const t = document.getElementById('typeFilter').value;
    if (q) url.searchParams.set('q', q);
    else url.searchParams.delete('q');
    if (t && t !== 'all') url.searchParams.set('type', t);
    else url.searchParams.delete('type');
    window.location.href = url.toString();
}

function printCaseRecord() {
    window.print();
}

document.getElementById('searchInput')?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') applyCaseFilters();
});
document.getElementById('typeFilter')?.addEventListener('change', applyCaseFilters);
document.getElementById('complainantSearchInput')?.addEventListener('input', (e) => {
    clearTimeout(complainantSearchTimer);
    const q = e.target.value.trim();
    complainantSearchTimer = setTimeout(() => runComplainantSearch(q), 300);
});

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeCaseModal();
        closeNewCaseModal();
    }
});

{% if open_new_case %}
openNewCaseModal();
{% endif %}
</script>

'''

# Fix accidental motion tags in template string
new_script = new_script.replace('<motion style=', '<div style=').replace('</motion>', '</div>')

p.write_text(text[:start] + new_script + text[end:], encoding="utf-8")
print("OK", p)
