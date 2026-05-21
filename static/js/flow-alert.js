/**
 * Global THA flow alert (#flowAlertModal). Loaded from staff_base.html.
 */
(function (global) {
    var flowAlertOnConfirm = null;

    function resetFlowAlertVariant() {
        var card = document.getElementById('flowAlertCard');
        var refWrap = document.getElementById('flowAlertRefWrap');
        var celIcon = document.getElementById('flowAlertCelebrationIcon');
        var progBar = document.getElementById('flowAlertProgressBar');
        var defaultBadge = document.getElementById('flowAlertSuccessBadge');
        if (card) {
            card.classList.remove('flow-alert-card--success', 'flow-alert-card--celebration');
        }
        if (refWrap) {
            refWrap.innerHTML = '';
            refWrap.style.display = 'none';
        }
        if (celIcon) celIcon.style.display = 'none';
        if (progBar) progBar.style.display = 'none';
        if (defaultBadge) defaultBadge.style.display = 'none';
        if (global.flowAlertCountdownTimeout) {
            clearTimeout(global.flowAlertCountdownTimeout);
            global.flowAlertCountdownTimeout = null;
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
        var celIcon = document.getElementById('flowAlertCelebrationIcon');
        var progBar = document.getElementById('flowAlertProgressBar');
        var defaultBadge = document.getElementById('flowAlertSuccessBadge');

        if (!modal || !titleEl || !messageEl) {
            global.alert(message);
            if (typeof onConfirm === 'function') onConfirm();
            return;
        }

        // Reset countdown timer if active
        if (global.flowAlertCountdownTimeout) {
            clearTimeout(global.flowAlertCountdownTimeout);
            global.flowAlertCountdownTimeout = null;
        }

        if (card) {
            card.classList.remove('flow-alert-card--success', 'flow-alert-card--celebration');
        }

        var isCelebration = (variant === 'success' || variant === 'proceed_success');

        if (isCelebration) {
            if (card) {
                card.classList.add('flow-alert-card--success');
                card.classList.add('flow-alert-card--celebration');
            }
            if (celIcon) celIcon.style.display = 'flex';
            if (defaultBadge) defaultBadge.style.display = 'none';
        } else {
            if (variant === 'success' && card) {
                card.classList.add('flow-alert-card--success');
            }
            if (defaultBadge) {
                defaultBadge.style.display = (variant === 'success') ? 'flex' : 'none';
            }
            if (celIcon) celIcon.style.display = 'none';
        }

        if (refWrap) {
            refWrap.innerHTML = '';
            refWrap.style.display = 'none';
        }

        titleEl.textContent = title;
        messageEl.textContent = message || '';
        flowAlertOnConfirm = onConfirm || null;
        modal.classList.add('active');

        // Start 4-second countdown if celebration is true
        if (isCelebration) {
            if (progBar) {
                progBar.style.display = 'block';
                // Trigger reflow to restart CSS animation
                progBar.offsetHeight;
            }
            global.flowAlertCountdownTimeout = setTimeout(function() {
                confirmFlowAlert();
            }, 4000);
        }
    }

    function showHandoffSuccessAlert(refText, onConfirm) {
        showFlowAlert(
            'This applicant was proceeded from Module 1 and is now available here for Application & Eligibility.',
            'Handoff successful',
            onConfirm,
            'success'
        );
        var refWrap = document.getElementById('flowAlertRefWrap');
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
    }

    var flowReplaceDocResolver = null;

    function closeFlowReplaceDocConfirm(event) {
        if (event && event.target && event.target.id !== 'flowReplaceDocModal') return;
        resolveFlowReplaceDocConfirm(false);
    }

    function resolveFlowReplaceDocConfirm(approved) {
        var modal = document.getElementById('flowReplaceDocModal');
        if (modal) {
            modal.classList.remove('active');
            modal.setAttribute('aria-hidden', 'true');
        }
        if (typeof flowReplaceDocResolver === 'function') {
            var resolver = flowReplaceDocResolver;
            flowReplaceDocResolver = null;
            resolver(!!approved);
        }
    }

    function showFlowConfirmReplaceDocument(docName) {
        var modal = document.getElementById('flowReplaceDocModal');
        var nameEl = document.getElementById('flowReplaceDocName');
        var label = docName && String(docName).trim() ? String(docName).trim() : 'Document';
        if (!modal || !nameEl) {
            return Promise.resolve(global.confirm(
                'Replace the file already on record?\n\n' + label + '\n\nProceed?'
            ));
        }
        nameEl.textContent = label;
        modal.classList.add('active');
        modal.setAttribute('aria-hidden', 'false');
        var proceedBtn = document.getElementById('flowReplaceDocProceedBtn');
        if (proceedBtn) proceedBtn.focus();
        return new Promise(function (resolve) {
            flowReplaceDocResolver = resolve;
        });
    }

    global.showFlowAlert = showFlowAlert;
    global.showHandoffSuccessAlert = showHandoffSuccessAlert;
    global.resetFlowAlertVariant = resetFlowAlertVariant;
    global.closeFlowAlert = closeFlowAlert;
    global.confirmFlowAlert = confirmFlowAlert;
    global.showFlowConfirmReplaceDocument = showFlowConfirmReplaceDocument;
    global.closeFlowReplaceDocConfirm = closeFlowReplaceDocConfirm;
    global.resolveFlowReplaceDocConfirm = resolveFlowReplaceDocConfirm;
})(typeof window !== 'undefined' ? window : this);
