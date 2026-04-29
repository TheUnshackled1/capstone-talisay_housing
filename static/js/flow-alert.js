/**
 * Global THA flow alert (#flowAlertModal). Loaded from staff_base.html.
 */
(function (global) {
    var flowAlertOnConfirm = null;

    function resetFlowAlertVariant() {
        var card = document.getElementById('flowAlertCard');
        var refWrap = document.getElementById('flowAlertRefWrap');
        if (card) card.classList.remove('flow-alert-card--success');
        if (refWrap) {
            refWrap.innerHTML = '';
            refWrap.style.display = 'none';
        }
    }

    function closeFlowAlert(event) {
        if (event && event.target && event.target.id !== 'flowAlertModal') return;
        var modal = document.getElementById('flowAlertModal');
        if (modal) modal.classList.remove('active');
        resetFlowAlertVariant();
    }

    function confirmFlowAlert() {
        var onConfirm = flowAlertOnConfirm;
        flowAlertOnConfirm = null;
        closeFlowAlert();
        if (typeof onConfirm === 'function') onConfirm();
    }

    function showFlowAlert(message, title, onConfirm, variant) {
        if (title === undefined) title = 'Notice';
        if (variant === undefined) variant = 'default';
        var modal = document.getElementById('flowAlertModal');
        var titleEl = document.getElementById('flowAlertTitle');
        var messageEl = document.getElementById('flowAlertMessage');
        var card = document.getElementById('flowAlertCard');
        var refWrap = document.getElementById('flowAlertRefWrap');
        if (!modal || !titleEl || !messageEl) {
            global.alert(message);
            if (typeof onConfirm === 'function') onConfirm();
            return;
        }
        if (card) {
            card.classList.toggle('flow-alert-card--success', variant === 'success');
        }
        if (refWrap) {
            refWrap.innerHTML = '';
            refWrap.style.display = 'none';
        }
        titleEl.textContent = title;
        messageEl.textContent = message || '';
        flowAlertOnConfirm = onConfirm || null;
        modal.classList.add('active');
    }

    function showHandoffSuccessAlert(refText, onConfirm) {
        var modal = document.getElementById('flowAlertModal');
        var titleEl = document.getElementById('flowAlertTitle');
        var messageEl = document.getElementById('flowAlertMessage');
        var card = document.getElementById('flowAlertCard');
        var refWrap = document.getElementById('flowAlertRefWrap');
        if (!modal || !titleEl || !messageEl || !card) {
            var fallback = 'Handoff successful. This applicant was proceeded from Module 1 and is now available here for Application & Eligibility'
                + (refText ? ' (ref ' + refText + ').' : '.');
            global.alert(fallback);
            if (typeof onConfirm === 'function') onConfirm();
            return;
        }
        card.classList.add('flow-alert-card--success');
        titleEl.textContent = 'Handoff successful';
        messageEl.textContent = 'This applicant was proceeded from Module 1 and is now available here for Application & Eligibility.';
        if (refWrap) {
            refWrap.innerHTML = '';
            refWrap.style.display = 'none';
            var trimmed = refText && String(refText).trim();
            if (trimmed) {
                var pill = document.createElement('span');
                pill.className = 'flow-alert-ref-pill';
                pill.textContent = trimmed;
                refWrap.appendChild(pill);
                refWrap.style.display = 'block';
            }
        }
        flowAlertOnConfirm = onConfirm || null;
        modal.classList.add('active');
    }

    global.showFlowAlert = showFlowAlert;
    global.showHandoffSuccessAlert = showHandoffSuccessAlert;
    global.resetFlowAlertVariant = resetFlowAlertVariant;
    global.closeFlowAlert = closeFlowAlert;
    global.confirmFlowAlert = confirmFlowAlert;
})(typeof window !== 'undefined' ? window : this);
