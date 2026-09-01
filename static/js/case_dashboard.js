/**
 * case_dashboard.js
 * Field Inspector — Dashboard Logic
 * Extracted from templates/field/dashboard.html
 *
 * URL bridge pattern: the CDRRMO API URL is resolved by Django and injected
 * via a data-attribute so this file stays a true static asset:
 *   <span id="case-dashboard-data"
 *         data-cdrrmo-url="{% url 'accounts:field_applicant_cdrrmo_meta' applicant_id='00000000-0000-4000-8000-000000000001' %}"
 *         hidden></span>
 */

'use strict';

/* ===== Module-level constants ===== */

/** Hazard type lookup — built once, reused on every modal open. */
const HAZARD_LABELS = Object.freeze({
    riverside:          'Riverside / Riverbank',
    flood_prone:        'Flood-Prone Area',
    landslide:          'Landslide-Prone Area',
    storm_surge:        'Storm Surge Zone',
    river_bank:         'River / Creek Bank',
    cliff_edge:         'Cliff Edge',
    coastal:            'Coastal Erosion',
    railroad:           'Near Railroad Tracks',
    road_right_of_way:  'Road Right-of-Way',
    other:              'Other Hazard',
});

/** CDRRMO metadata pre-loaded from the inline JSON script tag. */
const FIELD_PENDING_CDRRMO_META = (function () {
    const el = document.getElementById('field-pending-cdrrmo-meta');
    if (!el || !el.textContent) return {};
    try { return JSON.parse(el.textContent); } catch (e) { return {}; }
})();

/* ===== Camera / Evidence state ===== */
let fieldCameraStream       = null;
let fieldCameraFacingMode   = 'environment';
const fieldEvidenceFiles    = [];
let fieldEvidenceCarouselIndex = 0;
let _fieldEvidenceObjUrl    = null;  // current object URL shown in carousel

/* ===== Auto-refresh every 5 minutes ===== */
setTimeout(() => location.reload(), 5 * 60 * 1000);

/* =========================================================
   INIT
   ========================================================= */
document.addEventListener('DOMContentLoaded', function () {
    initScrollAnimations();
    initFieldKpiCards();

    if (typeof initListPagination === 'function') {
        initListPagination({
            pageSize:      5,
            rowSelector:   '#fieldPendingTableBody > tr',
            cardSelector:  '#fieldPendingMobileCards .mobile-verification-card',
            infoEl:        'fieldPendingPaginationInfo',
            prevBtn:       'fieldPendingPrevBtn',
            nextBtn:       'fieldPendingNextBtn',
            pageIndicator: 'fieldPendingPageIndicator',
        });
    }

    /* Camera buttons */
    _bindClick('fieldCameraStartBtn',    startFieldCamera);
    _bindClick('fieldCameraCaptureBtn',  captureFieldPhoto);
    _bindClick('fieldCameraSwitchBtn',   toggleFieldCamera);
    _bindClick('fieldCameraStopBtn',     stopFieldCamera);

    const pickBtn   = document.getElementById('fieldEvidenceFilePickBtn');
    const fileInput = document.getElementById('fieldEvidenceFileInput');
    if (pickBtn && fileInput) {
        pickBtn.addEventListener('click',  () => fileInput.click());
        fileInput.addEventListener('change', onFieldEvidenceFilesSelected);
    }

    /* Carousel nav */
    const fePrev = document.getElementById('fieldEvidencePrev');
    const feNext = document.getElementById('fieldEvidenceNext');
    const feRem  = document.getElementById('fieldEvidenceRemoveBtn');
    if (fePrev) fePrev.addEventListener('click', () => {
        if (fieldEvidenceCarouselIndex > 0) { fieldEvidenceCarouselIndex--; refreshFieldEvidenceCarousel(); }
    });
    if (feNext) feNext.addEventListener('click', () => {
        if (fieldEvidenceCarouselIndex < fieldEvidenceFiles.length - 1) { fieldEvidenceCarouselIndex++; refreshFieldEvidenceCarousel(); }
    });
    if (feRem) feRem.addEventListener('click', () => removeFieldEvidenceAt(fieldEvidenceCarouselIndex));

    /* Modal backdrop clicks */
    _bindModalBackdrop('certifiedApplicantsModal', closeCertifiedApplicantsModal);
    _bindModalBackdrop('todaySummaryModal',         closeTodaySummaryModal);
    _bindModalBackdrop('verificationModal',         closeVerificationModal);

    /* Global Escape key */
    document.addEventListener('keydown', function (e) {
        if (e.key !== 'Escape') return;
        if (_isVisible('verificationModal'))         { closeVerificationModal();         return; }
        if (_isVisible('certifiedApplicantsModal'))  { closeCertifiedApplicantsModal();  return; }
        if (_isVisible('todaySummaryModal'))         { closeTodaySummaryModal(); }
    });

    initApplicantHoverCard();
});

/* =========================================================
   PRIVATE HELPERS
   ========================================================= */

function _bindClick(id, fn) {
    const el = document.getElementById(id);
    if (el) el.addEventListener('click', fn);
}

function _bindModalBackdrop(id, closeFn) {
    const el = document.getElementById(id);
    if (el) el.addEventListener('click', (e) => { if (e.target === el) closeFn(); });
}

function _isVisible(id) {
    const el = document.getElementById(id);
    return el && el.style.display === 'flex';
}

function _openModal(el) {
    if (!el) return;
    el.style.display = 'flex';
    document.body.style.overflow = 'hidden';
}

function _closeModal(el) {
    if (!el) return;
    el.style.display = 'none';
    document.body.style.overflow = '';
}

/* =========================================================
   SCROLL ANIMATIONS
   ========================================================= */
function initScrollAnimations() {
    const selector =
        '.scroll-animate, .scroll-animate-left, .scroll-animate-right, ' +
        '.scroll-animate-scale, .scroll-animate-fade, .scroll-animate-bounce, ' +
        '.scroll-animate-rotate, .scroll-animate-blur, .scroll-animate-card';

    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        document.querySelectorAll(selector).forEach(el => el.classList.add('animate-in'));
        return;
    }

    const observer = new IntersectionObserver((entries, obs) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('animate-in');
                obs.unobserve(entry.target);
            }
        });
    }, { root: null, rootMargin: '0px 0px -50px 0px', threshold: 0.1 });

    document.querySelectorAll(selector).forEach(el => observer.observe(el));
}

/* =========================================================
   KPI CARDS
   ========================================================= */
function initFieldKpiCards() {
    document.querySelectorAll('.field-kpi-card--interactive').forEach(card => {
        card.addEventListener('click', () => {
            const action = card.getAttribute('data-kpi-action');
            if      (action === 'pending')    scrollToFieldPendingQueue();
            else if (action === 'certified')  openCertifiedApplicantsModal();
            else if (action === 'today')      showMyVerifications();
        });
        card.addEventListener('keydown', e => {
            if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); card.click(); }
        });
    });
}

function scrollToFieldPendingQueue() {
    const el = document.getElementById('field-pending-queue');
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

/* =========================================================
   MODALS — Certified / Today Summary
   ========================================================= */
function openCertifiedApplicantsModal()  { _openModal(document.getElementById('certifiedApplicantsModal')); }
function closeCertifiedApplicantsModal() { _closeModal(document.getElementById('certifiedApplicantsModal')); }
function showMyVerifications()           { _openModal(document.getElementById('todaySummaryModal')); }
function closeTodaySummaryModal()        { _closeModal(document.getElementById('todaySummaryModal')); }

/* =========================================================
   NOTIFICATIONS
   ========================================================= */
function fieldNotify(message, title, variant) {
    if (typeof window.showFlowAlert === 'function') {
        window.showFlowAlert(message, title || 'Notice', null, variant || 'default');
    } else {
        alert(message);
    }
}

/* =========================================================
   CAMERA
   ========================================================= */
function startFieldCamera() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        fieldNotify(
            'This browser does not support in-page camera access. Please use "Attach from device" to upload photographs.',
            'Camera unavailable'
        );
        return;
    }
    // Stop any existing stream before requesting a new one
    stopFieldCamera();
    _requestCameraStream(showFieldCameraUi, function (err) {
        stopFieldCamera();
        const detail = err && err.message ? err.message : 'permission denied';
        fieldNotify(
            'Could not open camera: ' + detail + '. Click Allow when prompted, or use Attach from device.',
            'Camera blocked'
        );
    });
}

function toggleFieldCamera() {
    fieldCameraFacingMode = fieldCameraFacingMode === 'environment' ? 'user' : 'environment';
    if (fieldCameraStream) startFieldCamera();
}

function stopFieldCamera() {
    if (fieldCameraStream) {
        fieldCameraStream.getTracks().forEach(t => t.stop());
        fieldCameraStream = null;
    }
    const v = document.getElementById('fieldCameraVideo');
    if (v) { v.srcObject = null; v.style.display = 'none'; }
    _setCameraButtons(true);
}

function captureFieldPhoto() {
    const v = document.getElementById('fieldCameraVideo');
    const c = document.getElementById('fieldCameraCanvas');
    if (!v || !c || !v.videoWidth) {
        fieldNotify('Wait for the camera preview to appear, then capture again.', 'Camera not ready');
        return;
    }
    if (fieldEvidenceFiles.length >= 4) {
        fieldNotify('Maximum 4 evidence photos.', 'Photo limit reached', 'warning');
        return;
    }
    c.width  = v.videoWidth;
    c.height = v.videoHeight;
    c.getContext('2d').drawImage(v, 0, 0);
    c.toBlob(blob => {
        if (!blob) return;
        addFieldEvidenceFile(new File([blob], 'site-evidence-' + Date.now() + '.jpg', { type: 'image/jpeg' }));
    }, 'image/jpeg', 0.88);
}

/** Tries camera constraints in order of preference, falling back gracefully. */
function _requestCameraStream(onSuccess, onError) {
    const facing   = fieldCameraFacingMode;
    const attempts = [
        { video: { facingMode: { ideal: facing } }, audio: false },
        { video: { facingMode: facing },             audio: false },
        { video: true,                               audio: false },
    ];
    let lastErr = null;
    let i = 0;
    function tryNext() {
        if (i >= attempts.length) { onError(lastErr || new Error('Could not open camera')); return; }
        navigator.mediaDevices.getUserMedia(attempts[i++])
            .then(onSuccess)
            .catch(err => {
                lastErr = err;
                if (err && (err.name === 'NotAllowedError' || err.name === 'SecurityError' || err.name === 'NotReadableError')) {
                    onError(err); return;
                }
                tryNext();
            });
    }
    tryNext();
}

function showFieldCameraUi(stream) {
    fieldCameraStream = stream;
    _setCameraButtons(false);
    const v = document.getElementById('fieldCameraVideo');
    if (v) {
        v.style.display = 'block';
        v.srcObject = stream;
        const p = v.play();
        if (p && typeof p.catch === 'function') p.catch(() => {});
    }
}

/** Toggles the Start / Capture / Switch / Stop button visibility. */
function _setCameraButtons(showStart) {
    const start = document.getElementById('fieldCameraStartBtn');
    const cap   = document.getElementById('fieldCameraCaptureBtn');
    const swt   = document.getElementById('fieldCameraSwitchBtn');
    const stp   = document.getElementById('fieldCameraStopBtn');
    if (start) start.style.display = showStart ? 'inline-block' : 'none';
    if (cap)   cap.style.display   = showStart ? 'none' : 'inline-block';
    if (swt)   swt.style.display   = showStart ? 'none' : 'inline-block';
    if (stp)   stp.style.display   = showStart ? 'none' : 'inline-block';
}

/* =========================================================
   EVIDENCE FILES
   ========================================================= */
function addFieldEvidenceFile(file) {
    if (fieldEvidenceFiles.length >= 4) {
        fieldNotify('Maximum 4 evidence photos.', 'Photo limit reached', 'warning');
        return;
    }
    if (file.size > 6 * 1024 * 1024) {
        fieldNotify('Each photo must be 6 MB or smaller: ' + (file.name || 'file'), 'Photo too large');
        return;
    }
    fieldEvidenceFiles.push(file);
    fieldEvidenceCarouselIndex = fieldEvidenceFiles.length - 1;
    refreshFieldEvidenceCarousel();
}

function removeFieldEvidenceAt(index) {
    if (index < 0 || index >= fieldEvidenceFiles.length) return;
    fieldEvidenceFiles.splice(index, 1);
    fieldEvidenceCarouselIndex = Math.min(fieldEvidenceCarouselIndex, Math.max(0, fieldEvidenceFiles.length - 1));
    refreshFieldEvidenceCarousel();
}

function onFieldEvidenceFilesSelected(ev) {
    Array.from(ev.target.files || []).forEach(file => {
        if (fieldEvidenceFiles.length < 4) addFieldEvidenceFile(file);
    });
    ev.target.value = '';
}

function clearFieldEvidenceUI() {
    if (_fieldEvidenceObjUrl) {
        try { URL.revokeObjectURL(_fieldEvidenceObjUrl); } catch (_) {}
        _fieldEvidenceObjUrl = null;
    }
    fieldEvidenceFiles.length   = 0;
    fieldEvidenceCarouselIndex  = 0;
    const fi = document.getElementById('fieldEvidenceFileInput');
    if (fi) fi.value = '';
    refreshFieldEvidenceCarousel();
}

function refreshFieldEvidenceCarousel() {
    const carousel = document.getElementById('fieldEvidenceCarousel');
    const img      = document.getElementById('fieldEvidenceImg');
    const counter  = document.getElementById('fieldEvidenceCounter');
    const prev     = document.getElementById('fieldEvidencePrev');
    const next     = document.getElementById('fieldEvidenceNext');
    const label    = document.getElementById('fieldEvidenceNoPhotoLabel');
    if (!carousel || !img) return;

    if (!fieldEvidenceFiles.length) {
        carousel.hidden = true;
        if (label) { label.style.display = 'block'; label.textContent = 'No photo selected'; }
        return;
    }

    carousel.hidden = false;
    if (label) label.style.display = 'none';

    if (_fieldEvidenceObjUrl) { try { URL.revokeObjectURL(_fieldEvidenceObjUrl); } catch (_) {} }
    _fieldEvidenceObjUrl = URL.createObjectURL(fieldEvidenceFiles[fieldEvidenceCarouselIndex]);
    img.src = _fieldEvidenceObjUrl;

    const total = fieldEvidenceFiles.length;
    if (counter) counter.textContent = (fieldEvidenceCarouselIndex + 1) + ' / ' + total;
    if (prev) prev.hidden = total <= 1;
    if (next) next.hidden = total <= 1;
}

/* =========================================================
   HAZARD CLASSIFICATION
   ========================================================= */
function formatHazardClassification(code) {
    if (!code || !String(code).trim()) return '—';
    const key = String(code).trim().toLowerCase().replace(/-/g, '_');
    return HAZARD_LABELS[key] || String(code).replace(/_/g, ' ');
}

/* =========================================================
   CDRRMO META
   ========================================================= */
function _getCdrrmoUrlTemplate() {
    const el = document.getElementById('case-dashboard-data');
    return el ? (el.dataset.cdrrmoUrl || '') : '';
}

function _formatCdrrmoDateTime(iso) {
    if (!iso) return '—';
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return '—';
    return d.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })
         + ' ' + d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
}

function applyFieldCdrrmoMeta(meta) {
    const statusEl = document.getElementById('cdrrmoStatusText');
    const dateEl   = document.getElementById('cdrrmoDateText');
    if (!statusEl || !dateEl) return;

    if (!meta) { statusEl.textContent = '—'; dateEl.textContent = '—'; return; }

    const CDRRMO_STATUS = {
        certified:     { text: 'Certified — danger zone (government record)', color: '#166534' },
        not_certified: { text: 'Not certified — hazard claim not verified',   color: '#991b1b' },
    };

    if (CDRRMO_STATUS[meta.status]) {
        statusEl.textContent = CDRRMO_STATUS[meta.status].text;
        statusEl.style.color = CDRRMO_STATUS[meta.status].color;
    } else if (meta.document_at) {
        statusEl.textContent = 'CDRRMO certification on file — awaiting field verification report';
        statusEl.style.color = '#1d4ed8';
    } else {
        statusEl.textContent = 'Pending — awaiting field verification report';
        statusEl.style.color = '#78350f';
    }
    dateEl.textContent = _formatCdrrmoDateTime(meta.certified_at || meta.document_at || null);
}

async function refreshFieldCdrrmoMeta(applicantId) {
    // Show embedded snapshot immediately (zero latency)
    applyFieldCdrrmoMeta(FIELD_PENDING_CDRRMO_META[String(applicantId)] || {});

    const template = _getCdrrmoUrlTemplate();
    if (!template) return;

    const url = template.replace('00000000-0000-4000-8000-000000000001', encodeURIComponent(applicantId));
    try {
        const resp = await fetch(url, { headers: { Accept: 'application/json' }, credentials: 'same-origin' });
        if (!resp.ok || !(resp.headers.get('content-type') || '').includes('application/json')) return;
        const data = await resp.json();
        if (data.success && data.meta) {
            applyFieldCdrrmoMeta(data.meta);
            FIELD_PENDING_CDRRMO_META[String(applicantId)] = data.meta;  // update cache
        }
    } catch (_) { /* keep embedded snapshot on network error */ }
}

/* =========================================================
   VERIFICATION MODAL
   ========================================================= */
async function openVerificationModal(applicantId, applicantName, address, dangerZoneType, dangerZoneLocation, referenceNumber) {
    clearFieldEvidenceUI();
    stopFieldCamera();

    const setField = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
    const setVal   = (id, val) => { const el = document.getElementById(id); if (el) el.value = val; };

    setVal('verificationModalApplicantId', applicantId);
    setField('verificationModalName',      applicantName);
    setField('verificationModalAddress',   address);
    setField('verificationModalDangerZone', formatHazardClassification(dangerZoneType));
    setField('verificationModalLocation',  (dangerZoneLocation && dangerZoneLocation.trim()) ? dangerZoneLocation.trim() : '—');
    setField('cdrrmoRefText',              (referenceNumber && referenceNumber.trim())        ? referenceNumber.trim()   : '—');

    const cdrrmoStatusBox = document.getElementById('cdrrmoStatusBox');
    if (cdrrmoStatusBox) {
        cdrrmoStatusBox.style.display = dangerZoneType ? 'block' : 'none';
    }
    if (dangerZoneType) {
        void refreshFieldCdrrmoMeta(applicantId);
    } else {
        applyFieldCdrrmoMeta(null);
    }

    _openModal(document.getElementById('verificationModal'));
}

function closeVerificationModal() {
    stopFieldCamera();
    clearFieldEvidenceUI();
    _closeModal(document.getElementById('verificationModal'));
    const form = document.getElementById('verificationForm');
    if (form) form.reset();
}

function submitVerification(event) {
    event.preventDefault();

    const applicantId       = document.getElementById('verificationModalApplicantId').value;
    const notesEl           = document.getElementById('verificationNotes');
    const verificationNotes = notesEl ? notesEl.value.trim() : '';

    if (!fieldEvidenceFiles.length) {
        fieldNotify(
            'Attach at least one site photograph (capture from camera or pick from device) before submitting. ' +
            'Photos are required so Module 2 can verify the field record.',
            'Site photo required'
        );
        return;
    }

    const formData = new FormData();
    formData.append('applicant_id',          applicantId);
    formData.append('verification_decision', 'certified');
    formData.append('verification_notes',    verificationNotes);
    fieldEvidenceFiles.forEach(file => formData.append('evidence_photos', file, file.name));

    const dash = document.querySelector('.dashboard-container');
    const pos  = (dash && dash.dataset.userPosition) ? dash.dataset.userPosition : 'field';

    fetch(`/applications/staff/${pos}/field-verify-cdrrmo/`, {
        method: 'POST',
        headers: { 'X-CSRFToken': _getCsrfToken() },
        body: formData,
    })
    .then(r => r.json())
    .then(data => {
        if (!data.success) {
            fieldNotify('Submission could not be completed: ' + data.error, 'Submission failed');
            return;
        }

        const photoMsg = (data.photos_saved > 0)
            ? `\n\nAttached ${data.photos_saved} site photograph(s) to this certification.` : '';
        let smsMsg = '';
        if (Object.prototype.hasOwnProperty.call(data, 'sms_dispatched')) {
            smsMsg = data.sms_dispatched
                ? "\n\nA status SMS was queued for the applicant's contact number."
                : '\n\nNo SMS was queued (missing or invalid mobile number, or gateway error).';
        }

        // Broadcast sync signal to other open tabs
        try {
            const ts = String(Date.now());
            localStorage.setItem('tha_field_cert_sync', ts);
            if (typeof BroadcastChannel !== 'undefined') {
                const bc = new BroadcastChannel('tha_field_cert_sync_bc');
                bc.postMessage({ t: ts });
                bc.close();
            }
        } catch (_) { /* private mode / storage quota */ }

        const msg   = data.message + photoMsg + smsMsg +
            '\n\nThe field certification has been recorded and is now available in Module 2 for staff review.';
        const onAck = () => { closeVerificationModal(); setTimeout(() => location.reload(), 200); };
        if (typeof window.showFlowAlert === 'function') {
            window.showFlowAlert(msg, 'Verification recorded', onAck, 'success');
        } else {
            alert(msg); onAck();
        }
    })
    .catch(err => {
        console.error('Fetch error:', err);
        fieldNotify('Network or server error: ' + err, 'Network error');
    });
}

function _getCsrfToken() {
    return document.querySelector('[name=csrfmiddlewaretoken]')?.value
        || document.querySelector('input[name="_token"]')?.value
        || _getCookieValue('csrftoken');
}

function _getCookieValue(name) {
    const match = document.cookie.split(';')
        .map(c => c.trim())
        .find(c => c.startsWith(name + '='));
    return match ? decodeURIComponent(match.slice(name.length + 1)) : null;
}

/* =========================================================
   HOVER CARD POPOVER
   ========================================================= */
function initApplicantHoverCard() {
    const hoverCard = document.getElementById('applicantHoverCard');
    if (!hoverCard) return;

    const hcAvatar = document.getElementById('hcAvatar');
    const hcName   = document.getElementById('hcName');
    const hcTx     = document.getElementById('hcTx');
    const hcRef    = document.getElementById('hcRef');
    const hcRefRow = document.getElementById('hcRefRow');
    const hcBrgy   = document.getElementById('hcBrgy');
    const hcDob    = document.getElementById('hcDob');
    let hideTimeout;

    document.addEventListener('mouseover', e => {
        const nameSpan = e.target.closest('.applicant-name');
        if (!nameSpan) {
            if (e.target.closest('#applicantHoverCard')) clearTimeout(hideTimeout);
            return;
        }
        clearTimeout(hideTimeout);

        const fullName = nameSpan.dataset.fullName || nameSpan.textContent.trim();
        if (hcName)   hcName.textContent   = fullName;
        if (hcAvatar) hcAvatar.textContent = fullName.slice(0, 2).toUpperCase();
        if (hcTx)     hcTx.textContent     = _formatTxId(nameSpan.dataset.txId || '');

        const refCode = nameSpan.dataset.refCode || '';
        if (hcRefRow) hcRefRow.style.display = refCode ? 'flex' : 'none';
        if (hcRef && refCode) hcRef.textContent = refCode;
        if (hcBrgy) hcBrgy.textContent = nameSpan.dataset.barangay || 'Not specified';
        if (hcDob)  hcDob.textContent  = nameSpan.dataset.dob      || 'Not specified';

        _positionHoverCard(hoverCard, nameSpan);
        hoverCard.classList.add('active');
    });

    document.addEventListener('mouseout', e => {
        if (e.target.closest('.applicant-name') || e.target.closest('#applicantHoverCard')) {
            hideTimeout = setTimeout(() => hoverCard.classList.remove('active'), 250);
        }
    });

    hoverCard.addEventListener('mouseenter', () => clearTimeout(hideTimeout));
    hoverCard.addEventListener('mouseleave', () => {
        hideTimeout = setTimeout(() => hoverCard.classList.remove('active'), 250);
    });
}

function _formatTxId(txId) {
    if (!txId) return '';
    const prefixes = ['APP-', 'TX-'];
    for (const prefix of prefixes) {
        if (txId.startsWith(prefix)) {
            const clean = txId.slice(prefix.length).replace(/[^a-fA-F0-9]/g, '');
            return prefix + clean.slice(0, 8) + '...';
        }
    }
    return txId.length > 15 ? txId.slice(0, 12) + '...' : txId;
}

function _positionHoverCard(card, anchor) {
    // Measure in hidden state, then restore
    card.style.visibility = 'hidden';
    card.style.display    = 'block';
    const cardW = card.offsetWidth  || 290;
    const cardH = card.offsetHeight || 190;
    card.style.display    = '';
    card.style.visibility = '';

    const rect    = anchor.getBoundingClientRect();
    const scrollX = window.scrollX;
    const scrollY = window.scrollY;

    let left = rect.left + scrollX + rect.width / 2 - cardW / 2;
    let top  = rect.top  + scrollY - cardH - 12;

    // Clamp horizontally
    left = Math.max(10, Math.min(left, window.innerWidth - cardW - 10));

    // Flip below if not enough space above
    if (rect.top - cardH - 12 < 10) {
        top = rect.bottom + scrollY + 12;
        card.classList.add('position-below');
    } else {
        card.classList.remove('position-below');
    }

    card.style.left = left + 'px';
    card.style.top  = top  + 'px';
}
