function exportArchiveCSV() {
    const table = document.querySelector('.applicants-table');
    if (!table) return;
    const headers = Array.from(table.querySelectorAll('thead th')).map(th => th.textContent.trim());
    const rows = Array.from(table.querySelectorAll('tbody tr'))
        .filter(tr => tr.querySelectorAll('td').length > 1)
        .map(tr => Array.from(tr.querySelectorAll('td')).map(td => (td.textContent || '').replace(/\s+/g, ' ').trim()));

    if (rows.length === 0) {
        showFlowAlert('No archive rows to export.');
        return;
    }
    let csv = headers.map(h => `"${String(h).replace(/"/g, '""')}"`).join(',') + '\n';
    rows.forEach(row => {
        csv += row.map(cell => `"${String(cell).replace(/"/g, '""')}"`).join(',') + '\n';
    });
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.href = url;
    link.download = `Archive_Records_${new Date().toISOString().split('T')[0]}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

function openArchiveHandoffSummary(buttonEl) {
    if (!buttonEl) return;
    const d = buttonEl.dataset || {};
    window.currentArchiveId = d.id;
    window.currentArchiveName = d.name || '';
    
    const setText = (id, value, fallback = 'N/A') => {
        const el = document.getElementById(id);
        if (el) el.textContent = (value !== undefined && value !== null && String(value).trim() !== '') ? String(value) : fallback;
    };

    const displayTx = (d.id && String(d.id).trim())
        ? `#${d.id.slice(0, 8)}`
        : '';
    setText('archiveSummaryReference', d.reference || '');
    setText('archiveSummaryName', d.name || '');
    setText('archiveSummaryLastName', d.lastName || '');
    setText('archiveSummaryFirstName', d.firstName || '');
    setText('archiveSummaryMiddleName', d.middleName || '');
    setText('archiveSummaryExtensionName', d.extensionName || '');
    setText('archiveSummaryDob', d.dob || '');
    setText('archiveSummaryBarangay', d.barangay || '');
    setText('archiveSummaryEncodedBy', d.staff || '', 'Unknown');
    setText('archiveSummaryStaffRole', d.staffPosition || '');
    setText('archiveSummarySms', d.sms || '');

    const docsLink = document.getElementById('archiveSummaryDocumentsLink');
    const vaultUrl = (d.documentsVaultUrl || '').trim();
    if (docsLink) {
        if (vaultUrl) {
            docsLink.href = vaultUrl;
            docsLink.classList.remove('btn-archive-action--disabled');
            docsLink.title = 'Open applicant document checklist in Document Management';
        } else {
            docsLink.href = '#';
            docsLink.classList.add('btn-archive-action--disabled');
            docsLink.title = 'Document vault link unavailable';
        }
    }

    const modal = document.getElementById('archiveSummaryModal');
    if (modal) modal.classList.add('active');
}

function closeArchiveSummaryModal() {
    const modal = document.getElementById('archiveSummaryModal');
    if (modal) modal.classList.remove('active');
}

function closeNoticeModal() {
    const overlay = document.getElementById('noticeModalOverlay');
    if (overlay) overlay.style.display = 'none';
}

function showNoticeModal({ title = 'Notice', message = '', primaryText = 'OK', secondaryText = 'Cancel', applicantName = null, onPrimary = null, onSecondary = null }) {
    const overlay = document.getElementById('noticeModalOverlay');
    const titleEl = document.getElementById('noticeModalTitle');
    const bodyEl = document.getElementById('noticeModalBody');
    const primaryBtn = document.getElementById('noticePrimaryBtn');
    const secondaryBtn = document.getElementById('noticeSecondaryBtn');
    const subtitleEl = document.getElementById('noticeModalSubtitle');
    const subtitleNameEl = document.getElementById('noticeModalSubtitleName');
    
    if (!overlay || !titleEl || !bodyEl || !primaryBtn || !secondaryBtn) return;

    titleEl.textContent = title;
    bodyEl.textContent = message;
    
    if (applicantName && subtitleEl && subtitleNameEl) {
        subtitleNameEl.textContent = applicantName;
        subtitleEl.style.display = 'block';
    } else if (subtitleEl) {
        subtitleEl.style.display = 'none';
    }
    
    primaryBtn.textContent = primaryText;
    secondaryBtn.textContent = secondaryText;
    secondaryBtn.style.display = secondaryText ? '' : 'none';

    primaryBtn.onclick = () => {
        if (onPrimary) onPrimary();
        closeNoticeModal();
    };

    secondaryBtn.onclick = () => {
        if (onSecondary) onSecondary();
        closeNoticeModal();
    };

    overlay.style.display = 'flex';
}

function unarchiveApplicant() {
    if (!window.currentArchiveId) return;
    
    showNoticeModal({
        title: 'Unarchive / Restore Record?',
        message: 'This will restore the applicant to the active Registration list.',
        primaryText: 'Yes, Restore',
        secondaryText: 'Cancel',
        applicantName: window.currentArchiveName || 'This Applicant',
        onPrimary: () => {
            if (!window.ARCHIVE_CONFIG || !window.ARCHIVE_CONFIG.unarchiveUrl) {
                showFlowAlert('Configuration error: Unarchive URL not found.', 'Error', null, 'error');
                return;
            }

            const formData = new FormData();
            formData.append('archive_id', window.currentArchiveId);
            if (window.ARCHIVE_CONFIG.csrfToken) {
                formData.append('csrfmiddlewaretoken', window.ARCHIVE_CONFIG.csrfToken);
            }

            fetch(window.ARCHIVE_CONFIG.unarchiveUrl, {
                method: 'POST',
                body: formData
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    showFlowAlert(data.message || 'Applicant restored successfully.', 'Success', null, 'success');
                    closeArchiveSummaryModal();
                    setTimeout(() => {
                        window.location.reload();
                    }, 1000);
                } else {
                    showFlowAlert(data.error || 'Failed to unarchive applicant.', 'Error', null, 'error');
                }
            })
            .catch(err => {
                showFlowAlert('Network error occurred.', 'Error', null, 'error');
                console.error(err);
            });
        }
    });
}

// Premium Hover Card popover initialization for tables
document.addEventListener('DOMContentLoaded', () => {
    const hoverCard = document.getElementById('applicantHoverCard');
    if (!hoverCard) return;
    const hcAvatar = document.getElementById('hcAvatar');
    const hcName = document.getElementById('hcName');
    const hcTx = document.getElementById('hcTx');
    const hcRef = document.getElementById('hcRef');
    const hcRefRow = document.getElementById('hcRefRow');
    const hcBrgy = document.getElementById('hcBrgy');
    const hcDob = document.getElementById('hcDob');

    let hideTimeout;

    document.addEventListener('mouseover', function (e) {
        const nameSpan = e.target.closest('.complainant-name.applicant-name');
        const isHoverCard = e.target.closest('#applicantHoverCard');

        if (!nameSpan) {
            if (isHoverCard) {
                clearTimeout(hideTimeout);
            }
            return;
        }

        clearTimeout(hideTimeout);

        const fullName = nameSpan.dataset.fullName || nameSpan.textContent.trim();
        const txId = nameSpan.dataset.txId || '';
        const refCode = nameSpan.dataset.refCode || '';
        const barangay = nameSpan.dataset.barangay || 'Not specified';
        const dob = nameSpan.dataset.dob || 'Not specified';

        // Populate card
        hcName.textContent = fullName;
        hcAvatar.textContent = fullName.slice(0, 2).toUpperCase();
        
        // Client-side slicing safety for UUIDs and long transaction IDs
        let displayTx = txId;
        if (displayTx.startsWith('APP-')) {
            const rawId = displayTx.substring(4).replace(/[^a-fA-F0-9\-]/g, '');
            const cleanId = rawId.replace(/-/g, '');
            displayTx = 'APP-' + cleanId.slice(0, 8) + '...';
        } else if (displayTx.startsWith('TX-')) {
            const rawId = displayTx.substring(3).replace(/[^a-fA-F0-9\-]/g, '');
            const cleanId = rawId.replace(/-/g, '');
            displayTx = 'TX-' + cleanId.slice(0, 8) + '...';
        } else if (displayTx.length > 15) {
            displayTx = displayTx.slice(0, 12) + '...';
        }
        hcTx.textContent = displayTx;

        if (refCode) {
            hcRef.textContent = refCode;
            hcRefRow.style.display = 'flex';
        } else {
            hcRefRow.style.display = 'none';
        }
        hcBrgy.textContent = barangay;
        hcDob.textContent = dob;

        // Position card — card is always display:block (visibility controls show/hide)
        const rect = nameSpan.getBoundingClientRect();
        const cardWidth = hoverCard.offsetWidth || 290;
        const cardHeight = hoverCard.offsetHeight || 190;

        const scrollX = window.pageXOffset || document.documentElement.scrollLeft;
        const scrollY = window.pageYOffset || document.documentElement.scrollTop;

        // Position directly above, centered
        let targetLeft = rect.left + scrollX + (rect.width / 2) - (cardWidth / 2);
        let targetTop = rect.top + scrollY - cardHeight - 12; // 12px gap

        // Boundaries checks
        if (targetLeft < 10) targetLeft = 10;
        if (targetLeft + cardWidth > window.innerWidth - 10) {
            targetLeft = window.innerWidth - cardWidth - 10;
        }

        if (rect.top - cardHeight - 12 < 10) {
            // Flip below
            targetTop = rect.bottom + scrollY + 12;
            hoverCard.classList.add('position-below');
        } else {
            hoverCard.classList.remove('position-below');
        }

        hoverCard.style.left = targetLeft + 'px';
        hoverCard.style.top = targetTop + 'px';
        hoverCard.classList.add('active');
    });

    document.addEventListener('mouseout', function (e) {
        const nameSpan = e.target.closest('.complainant-name.applicant-name');
        const isHoverCard = e.target.closest('#applicantHoverCard');

        if (nameSpan || isHoverCard) {
            hideTimeout = setTimeout(function () {
                hoverCard.classList.remove('active');
            }, 250);
        }
    });

    hoverCard.addEventListener('mouseenter', function () {
        clearTimeout(hideTimeout);
    });

    hoverCard.addEventListener('mouseleave', function () {
        hideTimeout = setTimeout(function () {
            hoverCard.classList.remove('active');
        }, 250);
    });
});
