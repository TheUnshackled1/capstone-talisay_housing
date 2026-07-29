function lawqShowAlert(message, title, onConfirm, variant) {
        showFlowAlert(message, title, onConfirm, variant);
    }

    var LAWQ_SMS_DEFAULT = (
        'Congratulations! Pirmanado na ang imo forms. Ikaw ang assignan na sang lot. '
        + 'Maghulat sang schedule para sa inyo orientasyon. Salamat!'
    );

    function lawqFormatOrientationLabel(isoLocal) {
        if (!isoLocal) return '';
        var d = new Date(isoLocal);
        if (isNaN(d.getTime())) return '';
        return d.toLocaleString('en-US', {
            month: 'long',
            day: 'numeric',
            year: 'numeric',
            hour: 'numeric',
            minute: '2-digit',
        });
    }

    function lawqSmsBodyForOrientation(isoLocal) {
        var whenLabel = lawqFormatOrientationLabel(isoLocal);
        if (!whenLabel) return LAWQ_SMS_DEFAULT;
        return (
            'Congratulations! Pirmanado na ang imo forms. Ikaw ang assignan na sang lot. '
            + 'Ang inyo orientasyon sa ' + whenLabel + '. Salamat!'
        );
    }

    function openLawqSmsModal() {
        var modal = document.getElementById('lawqSmsModal');
        var listEl = document.getElementById('lawqSmsRecipientList');
        var summaryEl = document.getElementById('lawqSmsRecipientSummary');
        var ta = document.getElementById('lawqSmsMessageText');
        var orient = document.getElementById('lawqSmsOrientationAt');
        var selected = Array.from(document.querySelectorAll('.lawq-app-check')).filter(function (cb) { return cb.checked; });
        if (!selected.length || !modal || !listEl || !summaryEl || !ta) return;

        listEl.innerHTML = '';
        selected.forEach(function (cb) {
            var li = document.createElement('li');
            li.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" style="width:0.75rem;height:0.75rem;flex-shrink:0;" aria-hidden="true"><path d="M20 6L9 17l-5-5"></path></svg>' + (cb.getAttribute('data-applicant-name') || ('Application ' + cb.value));
            listEl.appendChild(li);
        });
        summaryEl.textContent = selected.length + ' recipient' + (selected.length !== 1 ? 's' : '');
        if (orient) orient.value = '';
        ta.value = LAWQ_SMS_DEFAULT;
        modal.classList.add('active');
        if (orient) orient.focus();
    }

    function closeLawqSmsModal() {
        var modal = document.getElementById('lawqSmsModal');
        if (modal) modal.classList.remove('active');
    }

    (function () {
        var selectAll = document.getElementById('lawqSelectAll');
        var checks = function () { return Array.from(document.querySelectorAll('.lawq-app-check')); };
        var bulkBtn = document.getElementById('lawqBulkSmsBtn');
        var bulkCount = document.getElementById('lawqBulkCount');
        var smsModal = document.getElementById('lawqSmsModal');
        var confirmBtn = document.getElementById('lawqSmsConfirmBtn');
        var orientInput = document.getElementById('lawqSmsOrientationAt');
        var messageInput = document.getElementById('lawqSmsMessageText');

        function updateBulkUi() {
            var c = checks();
            var n = c.filter(function (x) { return x.checked; }).length;
            if (bulkCount) bulkCount.textContent = n + ' selected';
            if (bulkBtn) bulkBtn.disabled = n === 0;
            if (selectAll && c.length) {
                selectAll.indeterminate = n > 0 && n < c.length;
                selectAll.checked = n === c.length;
            }
        }

        if (selectAll) {
            selectAll.addEventListener('change', function () {
                checks().forEach(function (cb) { cb.checked = selectAll.checked; });
                updateBulkUi();
            });
        }
        checks().forEach(function (cb) {
            cb.addEventListener('change', updateBulkUi);
        });
        updateBulkUi();

        if (orientInput && messageInput) {
            orientInput.addEventListener('change', function () {
                messageInput.value = lawqSmsBodyForOrientation(orientInput.value);
            });
        }

        if (bulkBtn) {
            bulkBtn.addEventListener('click', function () {
                if (!checks().filter(function (cb) { return cb.checked; }).length) return;
                openLawqSmsModal();
            });
        }

        if (smsModal) {
            smsModal.addEventListener('click', function (e) {
                if (e.target === smsModal) closeLawqSmsModal();
            });
        }

        if (confirmBtn) {
            confirmBtn.addEventListener('click', async function () {
                var ids = checks().filter(function (cb) { return cb.checked; }).map(function (cb) { return cb.value; });
                var ta = document.getElementById('lawqSmsMessageText');
                var orient = document.getElementById('lawqSmsOrientationAt');
                var msg = (ta && ta.value) ? ta.value.trim() : '';
                var orientationAt = (orient && orient.value) ? orient.value.trim() : '';
                if (!ids.length) {
                    closeLawqSmsModal();
                    return;
                }
                if (!orientationAt) {
                    lawqShowAlert('Orientation date and time are required.', 'Send SMS', null, 'default');
                    return;
                }
                if (msg.length < 10) {
                    lawqShowAlert('Please enter a message of at least 10 characters.', 'Send SMS', null, 'default');
                    return;
                }
                var body = new URLSearchParams();
                body.append('csrfmiddlewaretoken', LAWQ_CONFIG.csrfToken);
                body.append('message', msg);
                body.append('orientation_at', orientationAt);
                ids.forEach(function (id) { body.append('application_ids', id); });
                try {
                    confirmBtn.disabled = true;
                    var btnSpan = confirmBtn.querySelector('span');
                    if (btnSpan) btnSpan.textContent = 'Sending…';
                    var res = await fetch(LAWQ_CONFIG.urls.bulkNotifySms, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                        body: body.toString()
                    });
                    var data = await res.json();
                    if (data.success) {
                        closeLawqSmsModal();
                        var summary = 'SMS sent: ' + (data.sent || 0);
                        if (data.skipped_no_phone > 0) {
                            summary += '\nSkipped (no phone): ' + data.skipped_no_phone;
                        }
                        if (data.failed > 0) {
                            summary += '\nFailed: ' + data.failed;
                        }
                        lawqShowAlert(summary, 'Send SMS', function () { location.reload(); }, 'success');
                        checks().forEach(function (cb) { cb.checked = false; });
                        if (selectAll) selectAll.checked = false;
                        updateBulkUi();
                    } else {
                        lawqShowAlert(data.error || 'Send SMS failed.', 'Send SMS', null, 'default');
                    }
                } catch (e) {
                    lawqShowAlert('Error: ' + (e.message || e), 'Send SMS', null, 'default');
                } finally {
                    confirmBtn.disabled = false;
                    var btnSpan = confirmBtn.querySelector('span');
                    if (btnSpan) btnSpan.textContent = 'Send SMS';
                }
            });
        }
    })();

    function openAwardModal(applicationId, applicantName) {
        document.getElementById('awardApplicationId').value = applicationId;
        document.getElementById('awardModalName').textContent = applicantName;
        
        // Strictly force the confirm step to hide (overriding any CSS !important)
        hideAwardConfirm();
        
        var overlay = document.getElementById('awardModal');
        overlay.classList.add('active');
        window.setTimeout(function () {
            var sel = document.getElementById('awardHousingUnit');
            if (sel && !sel.disabled) sel.focus();
        }, 30);
    }

    function showAwardConfirm() {
        const unitSelect = document.getElementById('awardHousingUnit');
        if (!unitSelect.value) {
            lawqShowAlert('Please select a vacant unit first.', 'Notice', null, 'warning');
            return;
        }
        
        const applicantName = document.getElementById('awardModalName').textContent;
        const selectedUnitText = unitSelect.options[unitSelect.selectedIndex].text;
        
        document.getElementById('confirmApplicantName').textContent = applicantName;
        document.getElementById('confirmUnitName').textContent = selectedUnitText;
        
        document.getElementById('awardFormBody').style.display = 'none';
        document.getElementById('awardFormFooter').style.setProperty('display', 'none', 'important');
        
        document.getElementById('awardConfirmBody').style.display = 'block';
        document.getElementById('awardConfirmFooter').style.setProperty('display', 'flex', 'important');
    }

    function hideAwardConfirm() {
        document.getElementById('awardConfirmBody').style.display = 'none';
        document.getElementById('awardConfirmFooter').style.setProperty('display', 'none', 'important');
        
        document.getElementById('awardFormBody').style.display = 'block';
        document.getElementById('awardFormFooter').style.setProperty('display', 'flex', 'important');
    }

    function closeAwardModal() {
        document.getElementById('awardModal').classList.remove('active');
        document.getElementById('awardForm').reset();
        hideAwardConfirm();
    }

    document.getElementById('awardModal').addEventListener('click', function (e) {
        if (e.target === e.currentTarget) closeAwardModal();
    });

    document.getElementById('awardForm').addEventListener('submit', async (e) => {
        e.preventDefault();

        const formData = new FormData(e.target);
        formData.append('csrfmiddlewaretoken', LAWQ_CONFIG.csrfToken);
        try {
            const response = await fetch(LAWQ_CONFIG.urls.awardLot, {
                method: 'POST',
                body: formData
            });
            const data = await response.json();
            if (data.success) {
                lawqShowAlert(data.message || 'Lot awarded successfully.', 'Award Lot', function () {
                    window.location.href = LAWQ_CONFIG.urls.housingUnitsMonitoring;
                }, 'success');
            } else {
                lawqShowAlert(data.error || 'Failed to award lot.', 'Award Lot', null, 'default');
            }
        } catch (error) {
            lawqShowAlert('Error: ' + error.message, 'Award Lot', null, 'default');
        }
    });

    // Auto-sync queue list without requiring manual refresh.
    // If server-side queue contents changed, reload this page while preserving query params.
    (function () {
        const SYNC_INTERVAL_MS = 12000;

        function currentQueueSignature(rootDoc) {
            const rowIds = Array.from(
                rootDoc.querySelectorAll('tbody tr[data-application-id]')
            ).map((tr) => tr.getAttribute('data-application-id') || '').join('|');
            const pagerSummary = (rootDoc.querySelector('.rfq-pagination span')?.textContent || '').trim();
            return rowIds + '||' + pagerSummary;
        }

        function shouldPauseAutoSync() {
            if (document.hidden) return true;
            if (document.getElementById('awardModal')?.classList.contains('active')) return true;
            if (document.getElementById('lawqSmsModal')?.classList.contains('active')) return true;
            const searchInput = document.querySelector('input[name="search"]');
            if (searchInput && document.activeElement === searchInput) return true;
            return false;
        }

        let baselineSignature = currentQueueSignature(document);

        window.setInterval(async function () {
            if (shouldPauseAutoSync()) return;
            try {
                const url = new URL(window.location.href);
                url.searchParams.set('_sync', String(Date.now()));
                const resp = await fetch(url.toString(), {
                    method: 'GET',
                    cache: 'no-store',
                    headers: { 'X-Requested-With': 'XMLHttpRequest' },
                });
                if (!resp.ok) return;
                const html = await resp.text();
                const remoteDoc = new DOMParser().parseFromString(html, 'text/html');
                const remoteSignature = currentQueueSignature(remoteDoc);
                if (remoteSignature && remoteSignature !== baselineSignature) {
                    window.location.reload();
                    return;
                }
                baselineSignature = remoteSignature || baselineSignature;
            } catch (err) {
                // Quiet fail: do not interrupt staff workflow on transient network issues.
            }
        }, SYNC_INTERVAL_MS);
    })();

    // Premium Hover Card popover initialization
    document.addEventListener('DOMContentLoaded', () => {
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