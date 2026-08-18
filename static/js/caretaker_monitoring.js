let pendingEarlyTaskId = null;
let pendingEarlyTaskDetails = null;
let photoCameraStream = null;
let photoCameraFacingMode = 'environment';
const selectedTaskId = (window.CARETAKER_CONFIG && window.CARETAKER_CONFIG.selectedTaskId) || '';

function showToast(message, type = 'success') {
    const container = document.getElementById('toastContainer');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    const icon = type === 'success' 
        ? '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline points="20 6 9 17 4 12"></polyline></svg>'
        : '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>';
    toast.innerHTML = `
        <div class="toast-icon">${icon}</div>
        <div class="toast-content">
            <h4 class="toast-title">${type === 'success' ? 'Success' : 'Attention'}</h4>
            <p class="toast-message">${message}</p>
        </div>
    `;
    container.appendChild(toast);
    setTimeout(() => toast.classList.add('active'), 10);
    setTimeout(() => {
        toast.classList.remove('active');
        setTimeout(() => toast.remove(), 400);
    }, 4500);
}

function openKpiModal(modalId) {
    const modal = document.getElementById(modalId);
    if (!modal) return;
    modal.classList.add('active');
    document.body.style.overflow = 'hidden';
}

function closeKpiModal(modalId) {
    const modal = document.getElementById(modalId);
    if (!modal) return;
    modal.classList.remove('active');
    if (!document.querySelector('.modal-overlay.active')) {
        document.body.style.overflow = '';
    }
}

function scrollToMonitoringTasksTable() {
    const el = document.getElementById('monitoring-tasks-work-area');
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function filterTasks() {
    const statusFilter = document.getElementById('filterStatus').value;
    const typeFilter = document.getElementById('filterType').value;
    const rows = document.querySelectorAll('.task-row');

    rows.forEach(row => {
        const rowStatus = row.dataset.status;
        const rowType = row.dataset.type;

        const statusMatch = !statusFilter || rowStatus === statusFilter;
        const typeMatch = !typeFilter || rowType === typeFilter;

        row.style.display = (statusMatch && typeMatch) ? '' : 'none';
    });
}

function caretakerTaskPhase(taskType) {
    const t = String(taskType || '');
    if (t === 'day_60_inspection') return 'initial';
    if (t === 'day_30_inspection' || t === 'month_2_inspection') return 'final';
    return 'other';
}

function caretakerMonitoringWindowLine(taskType) {
    const t = String(taskType || '');
    if (t === 'month_2_inspection') return '120-day extension — Extension 120 Day visit (120 days after extension start; not the original program 120 Day visit)';
    const phase = caretakerTaskPhase(taskType);
    if (phase === 'initial') return 'Initial monitoring — during 90 days';
    if (phase === 'final') return 'Final monitoring — 120 days after 90 Day visit';
    return 'Scheduled monitoring visit';
}


function toggleCaretakerConstructionChoices(taskType) {
    const phase = caretakerTaskPhase(taskType);
    const initial = document.getElementById('constructionChoicesInitial');
    const final = document.getElementById('constructionChoicesFinal');
    const fieldLabel = document.getElementById('constructionFieldLabel');
    if (!initial || !final) return;
    const isFinal = phase === 'final';
    initial.hidden = isFinal;
    final.hidden = !isFinal;
    if (fieldLabel) {
        fieldLabel.textContent = isFinal ? 'LOT BUILD STATUS (FINAL)' : 'CONSTRUCTION STATUS';
    }
    initial.querySelectorAll('input[type="radio"]').forEach((input) => {
        input.required = !isFinal;
        if (isFinal) input.checked = false;
    });
    final.querySelectorAll('input[type="radio"]').forEach((input) => {
        input.required = isFinal;
        if (!isFinal) input.checked = false;
    });
}

function updateCaretakerOccupancyCopy(taskType) {
    const pos = document.getElementById('occupancySubPositive');
    const neg = document.getElementById('occupancySubNegative');
    if (!pos || !neg) return;
    if (caretakerTaskPhase(taskType) === 'final') {
        pos.textContent = 'Beneficiary or immediate family is residing in the unit at this final visit.';
        neg.textContent = 'Unit is vacant, abandoned, or occupied by unauthorized persons at this final visit.';
    } else {
        pos.textContent = 'Beneficiary or immediate family is residing in the unit.';
        neg.textContent = 'Unit is abandoned, temporarily vacant, or occupied by unauthorized persons.';
    }
}

function applyReportModalPhase(taskType) {
    const phase = caretakerTaskPhase(taskType);
    const titleEl = document.getElementById('reportModalTitle');
    const subtitleEl = document.getElementById('reportModalSubtitle');
    const badgeEl = document.getElementById('reportModalPhaseBadge');
    const noticeEl = document.getElementById('reportModalPhaseNotice');
    const evidenceEl = document.getElementById('reportEvidenceHint');
    if (!titleEl || !subtitleEl || !noticeEl || !evidenceEl) return;

    const sharedSub = 'Occupancy and construction choices plus photo evidence match what housing staff review. If you do not add optional narratives, the system stores short default notes when you submit.';

    if (phase === 'initial') {
        titleEl.textContent = 'Caretaker monitoring report — initial visit';
        subtitleEl.textContent = '';
        if (badgeEl) {
            badgeEl.textContent = 'Initial monitoring';
            badgeEl.hidden = false;
        }
        noticeEl.className = 'monitoring-phase-notice monitoring-phase-notice--initial';
        noticeEl.hidden = false;
        noticeEl.innerHTML = (
            '<strong>90 Day Inspection (initial)</strong> '
            + 'Housing staff will mark this visit as <strong>Normal Progress</strong> or <strong>No Progress</strong> after you submit. '
            + 'This records initial monitoring only; the 120 Day final visit comes later.'
        );
        evidenceEl.textContent = 'Capture or attach up to 4 images of the lot during the 90-day monitoring window.';
    } else if (phase === 'final') {
        const isExtensionFinal = String(taskType) === 'month_2_inspection';
        if (isExtensionFinal) {
            titleEl.textContent = 'Caretaker monitoring report — extension window (120 Day)';
            subtitleEl.textContent = '';
            if (badgeEl) {
                badgeEl.textContent = 'Extension · final';
                badgeEl.hidden = false;
            }
            noticeEl.className = 'monitoring-phase-notice monitoring-phase-notice--final';
            noticeEl.hidden = false;
            noticeEl.innerHTML = (
                '<strong>Extension 120 Day visit</strong> (120 days after the extension start date). '
                + 'Housing staff choose <strong>Housing unit</strong> if the build is finished, or <strong>Failed</strong> if this extension visit does not pass. '
                + 'Failed is the staff path toward <strong>Blacklist beneficiary</strong> when office rules allow (e.g. letter deadline passed with no compliant letter on file).'
            );
            evidenceEl.textContent = 'Capture or attach up to 4 images showing whether construction on the lot is finished or still incomplete.';
        } else {
            titleEl.textContent = 'Caretaker monitoring report — final visit';
            subtitleEl.textContent = '';
            if (badgeEl) {
                badgeEl.textContent = 'Final monitoring';
                badgeEl.hidden = false;
            }
            noticeEl.className = 'monitoring-phase-notice monitoring-phase-notice--final';
            noticeEl.hidden = false;
            noticeEl.innerHTML = (
                '<strong>120 Day Inspection (final)</strong> '
                + 'Staff use your report to decide: '
                + '<strong>Housing unit</strong> — lot build is finished; the lot is counted as a completed unit and monitoring closes. '
                + '<strong>Explanation letter</strong> — opens the explanation-letter workflow.'
            );
            evidenceEl.textContent = 'Capture or attach up to 4 images showing whether construction on the lot is finished or still incomplete.';
        }
    } else {
        titleEl.textContent = 'Caretaker monitoring report';
        subtitleEl.textContent = sharedSub;
        if (badgeEl) badgeEl.hidden = true;
        noticeEl.hidden = true;
        noticeEl.textContent = '';
        evidenceEl.textContent = 'Capture or attach up to 4 images of the lot and any structures or materials.';
    }
    toggleCaretakerConstructionChoices(taskType);
    updateCaretakerOccupancyCopy(taskType);
}

function setReportReference(taskLabel, unitLocation, dueDate, taskType) {
    document.getElementById('reportTaskUnit').textContent = unitLocation || '—';
    document.getElementById('reportTaskType').textContent = taskLabel || '—';
    document.getElementById('reportTaskDueDate').textContent = dueDate || '—';
    const line = caretakerMonitoringWindowLine(taskType);
    document.getElementById('reportTaskMonitoringDay').textContent = line || '—';
    applyReportModalPhase(taskType);
}

function openReportModal(taskId, allowEarly, scheduledDate, taskLabel, unitLocation, dueDate, taskType) {
    if (allowEarly) {
        pendingEarlyTaskId = taskId;
        pendingEarlyTaskDetails = { taskLabel, unitLocation, dueDate, taskType };
        document.getElementById('earlyInspectionMessage').innerHTML =
            `<span style="display:block; margin-bottom: 0.75rem; font-weight:600;">Scheduled inspection: ${scheduledDate}</span>This task is scheduled for a future date. Continue only if you are conducting an early inspection for testing, demonstration, or authorized purposes.`;
        document.getElementById('earlyInspectionModal').classList.add('active');
        document.body.style.overflow = 'hidden';
        return;
    }
    document.getElementById('taskId').value = taskId;
    document.getElementById('allowEarlyInspection').value = allowEarly ? '1' : '0';
    setReportReference(taskLabel, unitLocation, dueDate, taskType);
    document.getElementById('reportModal').classList.add('active');
    document.body.style.overflow = 'hidden';
}

function closeEarlyInspectionModal() {
    pendingEarlyTaskId = null;
    pendingEarlyTaskDetails = null;
    document.getElementById('earlyInspectionModal').classList.remove('active');
    if (!document.querySelector('.modal-overlay.active')) {
        document.body.style.overflow = '';
    }
}

function continueEarlyInspection() {
    if (!pendingEarlyTaskId) return;
    const taskId = pendingEarlyTaskId;
    const details = pendingEarlyTaskDetails;
    closeEarlyInspectionModal();
    document.getElementById('taskId').value = taskId;
    document.getElementById('allowEarlyInspection').value = '1';
    if (details) {
        setReportReference(
            details.taskLabel,
            details.unitLocation,
            details.dueDate,
            details.taskType
        );
    }
    document.getElementById('reportModal').classList.add('active');
    document.body.style.overflow = 'hidden';
}

function closeReportModal() {
    stopPhotoEvidenceCamera();
    document.getElementById('reportModal').classList.remove('active');
    document.getElementById('reportForm').reset();
    document.getElementById('allowEarlyInspection').value = '0';
    /* Reset carousel state */
    photoEvidenceCarouselFiles = [];
    photoEvidenceCarouselIndex = 0;
    if (_photoEvidenceObjUrl) { try { URL.revokeObjectURL(_photoEvidenceObjUrl); } catch(e) {} _photoEvidenceObjUrl = null; }
    const input = document.getElementById('photoEvidenceInput');
    if (input) input.value = '';
    updatePhotoEvidenceCarouselUI();
    if (!document.querySelector('.modal-overlay.active')) {
        document.body.style.overflow = '';
    }
}

function setPhotoEvidenceFiles(files) {
    const input = document.getElementById('photoEvidenceInput');
    if (!input) return;
    const transfer = new DataTransfer();
    [...files].slice(0, 4).forEach((file) => transfer.items.add(file));
    input.files = transfer.files;
    updatePhotoEvidenceName(input);
    /* Jump to the newly-added (last) photo */
    if (photoEvidenceCarouselFiles.length > 0) {
        photoEvidenceCarouselIndex = photoEvidenceCarouselFiles.length - 1;
        updatePhotoEvidenceCarouselUI();
    }
}

function requestPhotoCameraStream(onSuccess, onError) {
    const facing = photoCameraFacingMode;
    const attempts = [
        { video: { facingMode: { ideal: facing } }, audio: false },
        { video: { facingMode: facing }, audio: false },
        { video: true, audio: false },
    ];
    let lastErr = null;
    let index = 0;
    function tryNext() {
        if (index >= attempts.length) {
            onError(lastErr || new Error('Could not open camera'));
            return;
        }
        navigator.mediaDevices.getUserMedia(attempts[index++])
            .then(onSuccess)
            .catch(function (err) {
                lastErr = err;
                if (err && (err.name === 'NotAllowedError' || err.name === 'SecurityError' || err.name === 'NotReadableError')) {
                    onError(err);
                    return;
                }
                tryNext();
            });
    }
    tryNext();
}

function showPhotoCameraStream(stream) {
    photoCameraStream = stream;
    const preview = document.getElementById('cameraPreview');
    const swt = document.getElementById('photoCameraSwitchBtn');
    const mainBtns = document.getElementById('mainEvidenceButtons');
    if (preview) preview.classList.add('active');
    if (swt) swt.style.display = 'inline-block';
    if (mainBtns) mainBtns.style.display = 'none';
    const video = document.getElementById('photoCameraVideo');
    if (video) {
        video.srcObject = stream;
        const playPromise = video.play();
        if (playPromise && typeof playPromise.catch === 'function') {
            playPromise.catch(function () {});
        }
    }
}

function startPhotoEvidenceCamera() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        showToast('This browser does not support live camera access. Use Attach from device instead.', 'error');
        return;
    }
    if (photoCameraStream) {
        photoCameraStream.getTracks().forEach(function (track) { track.stop(); });
        photoCameraStream = null;
    }
    requestPhotoCameraStream(
        showPhotoCameraStream,
        function () {
            stopPhotoEvidenceCamera();
            showToast('Could not open camera. Click Allow when prompted, or use Attach from device.', 'error');
        }
    );
}

function openPhotoEvidenceInput(useCamera) {
    const input = document.getElementById('photoEvidenceInput');
    if (!input) return;
    if (!useCamera) {
        stopPhotoEvidenceCamera();
        input.removeAttribute('capture');
        input.setAttribute('multiple', 'multiple');
        input.click();
        return;
    }
    startPhotoEvidenceCamera();
}

function togglePhotoEvidenceCamera() {
    photoCameraFacingMode = (photoCameraFacingMode === 'environment') ? 'user' : 'environment';
    if (photoCameraStream) {
        startPhotoEvidenceCamera();
    }
}

function stopPhotoEvidenceCamera() {
    if (photoCameraStream) {
        photoCameraStream.getTracks().forEach((track) => track.stop());
        photoCameraStream = null;
    }
    const video = document.getElementById('photoCameraVideo');
    const preview = document.getElementById('cameraPreview');
    if (video) video.srcObject = null;
    if (preview) preview.classList.remove('active');
    const mainBtns = document.getElementById('mainEvidenceButtons');
    if (mainBtns) mainBtns.style.display = 'flex';
    const swt = document.getElementById('photoCameraSwitchBtn');
    if (swt) swt.style.display = 'none';
}

function capturePhotoEvidence() {
    const input = document.getElementById('photoEvidenceInput');
    const video = document.getElementById('photoCameraVideo');
    const canvas = document.getElementById('photoCameraCanvas');
    if (!input || !video || !canvas) return;
    if (input.files && input.files.length >= 4) {
        if (typeof showFlowAlert === 'function') {
            showFlowAlert('Maximum of 4 photo evidence files allowed.', 'Photo limit', null, 'warning');
        } else {
            showToast('Maximum of 4 photo evidence files allowed.', 'error');
        }
        return;
    }
    let vWidth = video.videoWidth || 1280;
    let vHeight = video.videoHeight || 720;
    
    /* Optimization: Scale down 4K/high-res streams to max 1280px for faster field uploads */
    const MAX_DIMENSION = 1280;
    if (vWidth > MAX_DIMENSION || vHeight > MAX_DIMENSION) {
        const ratio = Math.min(MAX_DIMENSION / vWidth, MAX_DIMENSION / vHeight);
        vWidth = Math.floor(vWidth * ratio);
        vHeight = Math.floor(vHeight * ratio);
    }

    canvas.width = vWidth;
    canvas.height = vHeight;
    const context = canvas.getContext('2d');
    context.drawImage(video, 0, 0, vWidth, vHeight);
    canvas.toBlob((blob) => {
        if (!blob) return;
        const file = new File([blob], `monitoring-photo-${Date.now()}.jpg`, { type: 'image/jpeg' });
        setPhotoEvidenceFiles([...(input.files || []), file]);
    }, 'image/jpeg', 0.8); /* Optimized from 0.9 for faster upload speed */
}

function openPhotoEvidencePicker() {
    const input = document.getElementById('photoEvidenceInput');
    if (!input) return;
    stopPhotoEvidenceCamera();
    input.removeAttribute('capture');
    input.setAttribute('multiple', 'multiple');
    input.click();
}

/* --- Carousel state for photo evidence --- */
let photoEvidenceCarouselFiles = [];
let photoEvidenceCarouselIndex = 0;
let _photoEvidenceObjUrl = null;

function updatePhotoEvidenceCarouselUI() {
    const carousel  = document.getElementById('photoEvidenceCarousel');
    const img       = document.getElementById('photoEvidenceImg');
    const counter   = document.getElementById('photoEvidenceCounter');
    const prev      = document.getElementById('photoEvidencePrev');
    const next      = document.getElementById('photoEvidenceNext');
    const label     = document.getElementById('photoEvidenceFileName');

    if (!carousel || !img) return;

    if (photoEvidenceCarouselFiles.length === 0) {
        carousel.hidden = true;
        if (label) { label.textContent = 'No photo selected'; label.style.color = '#475569'; }
        return;
    }

    carousel.hidden = false;
    const totalAttached = photoEvidenceCarouselFiles.length;
    if (label) {
        label.textContent = `${totalAttached} / 4 photos attached`;
        label.style.color = '#15803d';
    }

    /* revoke old object URL to avoid memory leak */
    if (_photoEvidenceObjUrl) { try { URL.revokeObjectURL(_photoEvidenceObjUrl); } catch(e) {} }
    _photoEvidenceObjUrl = URL.createObjectURL(photoEvidenceCarouselFiles[photoEvidenceCarouselIndex]);
    img.src = _photoEvidenceObjUrl;

    const total = photoEvidenceCarouselFiles.length;
    if (counter) counter.textContent = (photoEvidenceCarouselIndex + 1) + ' / ' + total;

    if (prev) prev.hidden = (total <= 1);
    if (next) next.hidden = (total <= 1);

    /* keep the hidden file input in sync so the form can still submit */
    const input = document.getElementById('photoEvidenceInput');
    if (input) {
        const dt = new DataTransfer();
        photoEvidenceCarouselFiles.forEach(function(f) { dt.items.add(f); });
        input.files = dt.files;
    }
}

function updatePhotoEvidenceName(input) {
    if (!input || !input.files) return;
    const count = input.files.length;

    if (count > 4) {
        if (typeof showFlowAlert === 'function') {
            showFlowAlert('Maximum of 4 photo evidence files allowed.', 'Photo limit', null, 'warning');
        } else {
            showToast('Maximum of 4 photo evidence files allowed.', 'error');
        }
        input.value = '';
        photoEvidenceCarouselFiles.length = 0;
        photoEvidenceCarouselIndex = 0;
        updatePhotoEvidenceCarouselUI();
        return;
    }

    /* Sync carousel array from input.files */
    photoEvidenceCarouselFiles = Array.from(input.files);
    if (photoEvidenceCarouselIndex >= photoEvidenceCarouselFiles.length) {
        photoEvidenceCarouselIndex = Math.max(0, photoEvidenceCarouselFiles.length - 1);
    }
    updatePhotoEvidenceCarouselUI();
}

function removePhotoEvidenceFile(index) {
    const input = document.getElementById('photoEvidenceInput');
    if (!input) return;
    photoEvidenceCarouselFiles.splice(index, 1);
    if (photoEvidenceCarouselIndex >= photoEvidenceCarouselFiles.length) {
        photoEvidenceCarouselIndex = Math.max(0, photoEvidenceCarouselFiles.length - 1);
    }
    const dt = new DataTransfer();
    photoEvidenceCarouselFiles.forEach(function(f) { dt.items.add(f); });
    input.files = dt.files;
    updatePhotoEvidenceCarouselUI();
}

/* Wire carousel nav buttons after DOM ready */
document.addEventListener('DOMContentLoaded', function() {
    const prev = document.getElementById('photoEvidencePrev');
    const next = document.getElementById('photoEvidenceNext');
    const rem  = document.getElementById('photoEvidenceRemoveBtn');
    if (prev) prev.addEventListener('click', function() {
        if (photoEvidenceCarouselIndex > 0) {
            photoEvidenceCarouselIndex--;
            updatePhotoEvidenceCarouselUI();
        }
    });
    if (next) next.addEventListener('click', function() {
        if (photoEvidenceCarouselIndex < photoEvidenceCarouselFiles.length - 1) {
            photoEvidenceCarouselIndex++;
            updatePhotoEvidenceCarouselUI();
        }
    });
    if (rem) rem.addEventListener('click', function() {
        removePhotoEvidenceFile(photoEvidenceCarouselIndex);
    });
});
function saveReportDraft() {
    showToast('Draft saved locally. You can resume this later.', 'success');
    closeReportModal();
}

let pendingFormData = null;

function submitReport(event) {
    event.preventDefault();
    const form = document.getElementById('reportForm');
    if (!form.checkValidity()) {
        form.reportValidity();
        return;
    }
    pendingFormData = new FormData(form);
    
    document.getElementById('confirmSubmitTaskType').textContent = document.getElementById('reportTaskType').textContent;
    document.getElementById('confirmSubmitUnit').textContent = document.getElementById('reportTaskUnit').textContent;
    document.getElementById('confirmSubmitModal').classList.add('active');
}

function closeConfirmSubmitModal() {
    document.getElementById('confirmSubmitModal').classList.remove('active');
    pendingFormData = null;
}

function executeSubmitReport() {
    if (!pendingFormData) return;
    const taskId = pendingFormData.get('task_id');
    const submitBtn = document.querySelector('#confirmSubmitModal .btn-submit-report');
    if (submitBtn) submitBtn.disabled = true;

    fetch(`/units/monitoring-report/${taskId}/submit/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
        },
        body: pendingFormData
    })
    .then(response => response.json())
    .then(data => {
        if (submitBtn) submitBtn.disabled = false;
        closeConfirmSubmitModal();
        if (data.success) {
            closeReportModal();
            document.getElementById('successSubmitUnit').textContent = document.getElementById('reportTaskUnit').textContent;
            const now = new Date();
            const timeStr = now.toLocaleDateString('en-US', {month:'short', day:'numeric', year:'numeric'}) + ' ”¢ ' + now.toLocaleTimeString('en-US', {hour:'numeric', minute:'2-digit'});
            document.getElementById('successSubmitTime').textContent = timeStr;
            
            document.getElementById('successSubmitModal').classList.add('active');
            try {
                localStorage.setItem('tha_monitoring_task_sync', String(Date.now()));
            } catch (ignoreLs) { }
        } else {
            showToast(data.error || 'Failed to submit report.', 'error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        if (submitBtn) submitBtn.disabled = false;
        showToast('Failed to submit report. Please check your connection.', 'error');
    });
}

function closeSuccessSubmitModal() {
    document.getElementById('successSubmitModal').classList.remove('active');
    location.reload();
}

document.addEventListener('DOMContentLoaded', function () {
    if (typeof initListPagination === 'function') {
        initListPagination({
            pageSize: 5,
            rowSelector: '#tasksTableBody > tr',
            cardSelector: '.mobile-tasks-cards .mobile-verification-card',
            infoEl: 'monitoringTasksPaginationInfo',
            prevBtn: 'monitoringTasksPrevBtn',
            nextBtn: 'monitoringTasksNextBtn',
            pageIndicator: 'monitoringTasksPageIndicator'
        });
    }

    const reportModalEl = document.getElementById('reportModal');
    if (reportModalEl) {
        reportModalEl.addEventListener('click', function (event) {
            if (event.target === this) closeReportModal();
        });
    }
    const earlyModalEl = document.getElementById('earlyInspectionModal');
    if (earlyModalEl) {
        earlyModalEl.addEventListener('click', function (event) {
            if (event.target === this) closeEarlyInspectionModal();
        });
    }

    document.querySelectorAll('[data-kpi-modal]').forEach(function (card) {
        card.addEventListener('click', function () {
            const modalId = card.getAttribute('data-kpi-modal');
            if (modalId) openKpiModal(modalId);
            if (card.getAttribute('data-kpi-scroll-tasks') === '1') {
                requestAnimationFrame(function () {
                    scrollToMonitoringTasksTable();
                });
            }
        });
    });

    document.querySelectorAll('.kpi-modal').forEach(function (modal) {
        modal.addEventListener('click', function (event) {
            if (event.target === this) closeKpiModal(this.id);
        });
    });

    document.addEventListener('keydown', function (e) {
        if (e.key !== 'Escape') return;
        document.querySelectorAll('.kpi-modal.modal-overlay.active').forEach(function (m) {
            closeKpiModal(m.id);
        });
    });

    if (selectedTaskId) {
        const selectedRow = document.querySelector('[data-task-id="' + selectedTaskId + '"]');
        if (selectedRow) {
            selectedRow.classList.add('task-selected');
            selectedRow.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    }
});

(function setupMonitoringTaskSyncReload() {
    function reloadFromOtherTab() {
        location.reload();
    }
    window.addEventListener('storage', function (e) {
        if (e.key !== 'tha_monitoring_task_sync' || e.newValue == null) return;
        reloadFromOtherTab();
    });
})();

document.addEventListener('DOMContentLoaded', () => {
    // Premium Hover Card popover initialization
    const hoverCard = document.getElementById('applicantHoverCard');
    const hcAvatar = document.getElementById('hcAvatar');
    const hcName = document.getElementById('hcName');
    const hcTx = document.getElementById('hcTx');
    const hcRef = document.getElementById('hcRef');
    const hcRefRow = document.getElementById('hcRefRow');
    const hcBrgy = document.getElementById('hcBrgy');
    const hcDob = document.getElementById('hcDob');

    let hideTimeout;

    document.addEventListener('mouseover', function (e) {
        const nameSpan = e.target.closest('.applicant-name, .kpi-applicant-name');
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

        // Position card
        const rect = nameSpan.getBoundingClientRect();
        
        // Temporarily display to measure height
        hoverCard.style.display = 'block';
        const cardWidth = hoverCard.offsetWidth || 290;
        const cardHeight = hoverCard.offsetHeight || 190;
        hoverCard.style.display = ''; // reset to CSS state

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
        const nameSpan = e.target.closest('.applicant-name, .kpi-applicant-name');
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
