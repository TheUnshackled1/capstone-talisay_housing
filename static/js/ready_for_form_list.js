/* ===================================================================
   ready_for_form_list.js
   Extracted from templates/staff/ready_for_form_list.html
   Django template vars injected via #rfqBridge script in HTML.
   =================================================================== */


    let RfqDWTObject = null;
    let rfqReplaceDocConfirmResolver = null;
    if (window.Dynamsoft && window.Dynamsoft.DWT) {
        Dynamsoft.DWT.RegisterEvent('OnWebTwainReady', function () {
            RfqDWTObject = Dynamsoft.DWT.GetWebTwain('dwtcontrolContainer');
        });
    }

    async function rfqWaitForDwt(timeoutMs) {
        const t = timeoutMs || 12000;
        const startedAt = Date.now();
        while (!RfqDWTObject && (Date.now() - startedAt) < t) {
            await new Promise(function (resolve) { setTimeout(resolve, 100); });
        }
        return RfqDWTObject;
    }

    function rfqCloseReplaceDocOverlay(event) {
        if (event && event.target && event.target.id !== 'rfqReplaceDocOverlay') return;
        rfqResolveReplaceDocConfirm(false);
    }

    function rfqResolveReplaceDocConfirm(approved) {
        const overlay = document.getElementById('rfqReplaceDocOverlay');
        if (overlay) {
            overlay.classList.remove('active');
            if (overlay._rfqReplaceEsc) {
                document.removeEventListener('keydown', overlay._rfqReplaceEsc);
                overlay._rfqReplaceEsc = null;
            }
        }
        if (typeof rfqReplaceDocConfirmResolver === 'function') {
            const resolver = rfqReplaceDocConfirmResolver;
            rfqReplaceDocConfirmResolver = null;
            resolver(!!approved);
        }
    }

    function rfqConfirmReplaceExistingDocument(docName) {
        const overlay = document.getElementById('rfqReplaceDocOverlay');
        const nameEl = document.getElementById('rfqReplaceDocFileName');
        if (!overlay || !nameEl) {
            return Promise.resolve(window.confirm(
                'A signed application is already on file. Replace it?'
            ));
        }
        nameEl.textContent = docName || 'Signed application';
        overlay.classList.add('active');
        const esc = function (e) {
            if (e.key === 'Escape') rfqResolveReplaceDocConfirm(false);
        };
        overlay._rfqReplaceEsc = esc;
        document.addEventListener('keydown', esc);
        return new Promise(function (resolve) {
            rfqReplaceDocConfirmResolver = resolve;
        });
    }

    async function rfqScanSignedApplication(btn) {
        if (!btn) return;
        const oldHtml = btn.innerHTML;
        const scanSvg = btn.querySelector('svg') ? btn.querySelector('svg').outerHTML : '';
        const applicantId = String(btn.dataset.applicantId || '').trim();
        if (!applicantId) {
            rfqShowAlert('Missing applicant.', 'Scan', 'default');
            return;
        }
        const hasExistingDoc = String(btn.dataset.hasExistingDoc || '0') === '1';
        const existingDocName = String(btn.dataset.existingDocName || '').trim() || 'Signed application';
        if (hasExistingDoc) {
            const ok = await rfqConfirmReplaceExistingDocument(existingDocName);
            if (!ok) return;
        }
        const refRaw = String(btn.dataset.refLabel || '').trim();
        const safeRef = refRaw ? refRaw.replace(/\s+/g, '_').replace(/[^a-zA-Z0-9._-]/g, '').slice(0, 80) : ('app_' + applicantId.replace(/-/g, '').slice(0, 12));
        const reviewUrl = String(btn.dataset.reviewUrl || '').trim();
        const applicationId = String(btn.dataset.applicationId || '').trim();
        const referenceNumber = String(btn.dataset.referenceNumber || '').trim();
        btn.disabled = true;
        btn.innerHTML = scanSvg + ' Starting scanner…';
        try {
            const dwt = await rfqWaitForDwt();
            if (!dwt) throw new Error('Scanner SDK not ready. Refresh the page and try again.');
            btn.innerHTML = scanSvg + ' Select source…';
            await dwt.SelectSourceAsync();
            const beforeCount = Number(dwt.HowManyImagesInBuffer || 0);
            await dwt.AcquireImageAsync({ IfCloseSourceAfterAcquire: true });
            const afterCount = Number(dwt.HowManyImagesInBuffer || 0);
            if (afterCount <= beforeCount) throw new Error('No image was acquired.');
            const index = Number(dwt.CurrentImageIndexInBuffer);
            const uploadUrl = `${RFQ_INTAKE_DWT_URL}?applicant_id=${encodeURIComponent(applicantId)}&doc_key=doc_signed_application&doc_code=SIGNED`;
            const fileName = `${safeRef}_signed_application.png`;
            btn.innerHTML = scanSvg + ' Uploading…';
            await new Promise(function (resolve, reject) {
                dwt.HTTPUpload(
                    uploadUrl,
                    [index],
                    Dynamsoft.DWT.EnumDWT_ImageType.IT_PNG,
                    Dynamsoft.DWT.EnumDWT_UploadDataFormat.Binary,
                    fileName,
                    function (httpResponse) { resolve(httpResponse); },
                    function (_errorCode, errorString, httpResponse) {
                        let message = errorString || 'Upload failed.';
                        const normalized = String(message || '').replace(/\s+/g, ' ').trim();
                        if (/^HTTP process:\s*OK\s*\(200\)/i.test(normalized) || normalized.toLowerCase().startsWith('http process: ok')) {
                            resolve(httpResponse);
                            return;
                        }
                        if (httpResponse) {
                            try {
                                const parsed = JSON.parse(httpResponse);
                                if (parsed && parsed.success) {
                                    resolve(httpResponse);
                                    return;
                                }
                                if (parsed && parsed.error) message = parsed.error;
                            } catch (_err) { }
                        }
                        reject(new Error(message));
                    }
                );
            });
            rfqPromptSignedDocReview(
                reviewUrl,
                'Signed application scan saved to the vault.',
                applicationId,
                referenceNumber,
                applicantId
            );
        } catch (err) {
            rfqShowAlert((err && err.message) ? err.message : 'Scan was cancelled or failed.', 'Scan', 'default');
            btn.disabled = false;
            btn.innerHTML = oldHtml;
        }
    }

    let rfqFileUploadApplicantId = null;
    let rfqFileUploadButtonEl = null;

    function rfqGetCsrfToken() {
        const inp = document.querySelector('[name=csrfmiddlewaretoken]');
        if (inp && inp.value) return inp.value;
        const m = document.cookie.match(/csrftoken=([^;]+)/);
        return m ? decodeURIComponent(m[1].trim()) : '';
    }

    /** Signed application upload: PDF, Word, or plain text only — not images. */
    function rfqSignedApplicationFileAllowed(file) {
        if (!file || !file.name) return false;
        const ct = (file.type || '').toLowerCase();
        if (ct.startsWith('image/')) return false;
        const ext = (file.name.lastIndexOf('.') >= 0
            ? file.name.slice(file.name.lastIndexOf('.')).toLowerCase()
            : '');
        const okExt = ['.pdf', '.doc', '.docx', '.txt'].indexOf(ext) >= 0;
        if (okExt) return true;
        return (
            ct === 'application/pdf'
            || ct === 'application/msword'
            || ct === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            || ct === 'text/plain'
        );
    }

    // rfqPickSignedApplicationFile removed — dead code (upload handled via rfqScanSignedApplication)


    // ---- Custom confirmation modal helpers ----
    function rfqShowConfirm(message, onOk, options) {
        const overlay = document.getElementById('rfqConfirmOverlay');
        const titleEl = document.getElementById('rfqConfirmTitle');
        const messageEl = document.getElementById('rfqConfirmMessage');
        const okBtn = document.getElementById('rfqConfirmOk');
        const cancelBtn = document.getElementById('rfqConfirmCancel');
        if (!overlay || !messageEl || !okBtn || !cancelBtn) {
            if (window.confirm(message)) onOk && onOk();
            return;
        }
        const opts = options || {};
        if (titleEl) titleEl.textContent = opts.title || 'Generate application form?';
        if (message) messageEl.textContent = message;
        const okLabel = opts.okText || 'Generate Form';
        const cancelLabel = opts.cancelText || 'Cancel';
        const isProceed = okLabel.toLowerCase().includes('proceed');
        const okSvg = isProceed
            ? '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>'
            : '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="12" y1="18" x2="12" y2="12"></line><line x1="9" y1="15" x2="15" y2="15"></line></svg>';
        const cancelSvg = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>';

        okBtn.className = 'tha-btn tha-btn-success';
        okBtn.innerHTML = `<span class="btn-icon-block">${okSvg}</span><span>${okLabel}</span>`;

        cancelBtn.className = 'tha-btn tha-btn-danger';
        cancelBtn.innerHTML = `<span class="btn-icon-block">${cancelSvg}</span><span>${cancelLabel}</span>`;
        overlay.classList.add('active');

        const cleanup = () => {
            overlay.classList.remove('active');
            okBtn.removeEventListener('click', handleOk);
            cancelBtn.removeEventListener('click', handleCancel);
            overlay.removeEventListener('click', handleBackdrop);
            document.removeEventListener('keydown', handleEsc);
        };
        const handleOk = () => { cleanup(); onOk && onOk(); };
        const handleCancel = () => {
            cleanup();
            if (typeof opts.onCancel === 'function') opts.onCancel();
        };
        const handleBackdrop = (e) => {
            if (e.target === overlay) {
                cleanup();
                if (typeof opts.onCancel === 'function') opts.onCancel();
            }
        };
        const handleEsc = (e) => {
            if (e.key === 'Escape') {
                cleanup();
                if (typeof opts.onCancel === 'function') opts.onCancel();
            }
        };
        okBtn.addEventListener('click', handleOk);
        cancelBtn.addEventListener('click', handleCancel);
        overlay.addEventListener('click', handleBackdrop);
        document.addEventListener('keydown', handleEsc);
    }

    function rfqShowAlert(message, title, variant) {
        showFlowAlert(message, title, null, variant);
    }


    function rfqQueueUrlWithoutRetrySign() {
        try {
            const u = new URL(window.location.href);
            u.searchParams.delete('retry_sign');
            return u.pathname + (u.searchParams.toString() ? ('?' + u.searchParams.toString()) : '');
        } catch (_e) {
            return queueUrl;
        }
    }

    function rfqPromptSignedDocReview(reviewUrl, successMsg, applicationId, referenceNumber, applicantId) {
        showFlowAlert(
            successMsg || 'Signed application scan saved to the vault.',
            'Application Form',
            function () {
                window.location.href = rfqQueueUrlWithoutRetrySign();
            },
            'success'
        );
    }

    async function generateFormFromQueue(applicantId) {
        rfqShowConfirm(
            'The form will be generated for this applicant and an application number assigned.',
            async () => {
                const pdfHold = window.open('about:blank', '_blank');
                try {
                    const response = await fetch(`/applications/staff/${position}/generate-form/${applicantId}/`);
                    const data = await response.json();
                    if (data.success) {
                        if (data.pdf_url && pdfHold) {
                            pdfHold.location.href = data.pdf_url;
                        } else if (pdfHold) {
                            pdfHold.close();
                        }
                        showFlowAlert(
                            'Application #' + data.application_number + ' generated. Returning to this queue...',
                            'Form generated',
                            function () {
                                window.location.href = queueUrl;
                            },
                            'success'
                        );
                    } else {
                        if (pdfHold) pdfHold.close();
                        rfqShowAlert(data.error || 'Failed to generate form', 'Generation failed', 'default');
                    }
                } catch (error) {
                    if (pdfHold) pdfHold.close();
                    rfqShowAlert('Error: ' + error.message, 'Network error', 'default');
                }
            },
            {
                title: 'Generate application form?',
                okText: 'Generate Form',
                cancelText: 'Cancel',
            }
        );
    }

    async function proceedToLotAwardingQueue(applicationId) {
        if (!applicationId) {
            rfqShowAlert('Missing application record.', 'Lot awarding queue', 'default');
            return;
        }
        rfqShowConfirm(
            'This will move the signed application from Ready for Form to the Lot Awarding queue for housing lot assignment.',
            async () => {
                const csrf = rfqGetCsrfToken();
                const fd = new FormData();
                fd.append('application_id', applicationId);
                try {
                    const response = await fetch(proceedLotQueueUrl, {
                        method: 'POST',
                        body: fd,
                        headers: csrf ? { 'X-CSRFToken': csrf } : {},
                    });
                    const data = await response.json();
                    if (!response.ok || !data.success) {
                        throw new Error(data.error || 'Unable to proceed to lot-awarding queue.');
                    }
                    const alertMsg = data.message || 'Application routed to lot-awarding queue (Standby position #2).';
                    showFlowAlert(
                        alertMsg,
                        'Lot awarding queue',
                        function () {
                            window.location.href = lotAwardingQueueUrl;
                        },
                        'success'
                    );
                } catch (error) {
                    rfqShowAlert(
                        (error && error.message) ? error.message : 'Unable to proceed to lot-awarding queue.',
                        'Lot awarding queue',
                        'default'
                    );
                }
            },
            {
                title: 'Proceed to lot awarding?',
                okText: 'Proceed',
                cancelText: 'Cancel',
            }
        );
    }

    document.addEventListener('DOMContentLoaded', function () {
        const finput = document.getElementById('rfqSignedApplicationFile');
        if (finput) {
            finput.addEventListener('change', async function () {
                const file = finput.files && finput.files[0];
                const applicantId = rfqFileUploadApplicantId;
                const triggerBtn = rfqFileUploadButtonEl;
                const reviewUrl = triggerBtn ? String(triggerBtn.dataset.reviewUrl || '').trim() : '';
                const applicationId = triggerBtn ? String(triggerBtn.dataset.applicationId || '').trim() : '';
                const referenceNumber = triggerBtn ? String(triggerBtn.dataset.referenceNumber || '').trim() : '';
                rfqFileUploadApplicantId = null;
                rfqFileUploadButtonEl = null;
                if (!file || !applicantId) return;
                const oldHtml = triggerBtn ? triggerBtn.innerHTML : '';
                if (!rfqSignedApplicationFileAllowed(file)) {
                    rfqShowAlert(
                        'Please upload a PDF, Word document (.doc or .docx), or plain text (.txt). Photos and other images are not accepted here.',
                        'Upload document',
                        'default'
                    );
                    finput.value = '';
                    if (triggerBtn) {
                        triggerBtn.disabled = false;
                        triggerBtn.innerHTML = oldHtml;
                    }
                    return;
                }
                if (triggerBtn) {
                    triggerBtn.disabled = true;
                    const uploadSvg = triggerBtn.querySelector('svg') ? triggerBtn.querySelector('svg').outerHTML : '';
                    triggerBtn.innerHTML = uploadSvg + ' Uploading…';
                }
                const csrf = rfqGetCsrfToken();
                const fd = new FormData();
                fd.append('applicant_id', applicantId);
                fd.append('doc_type', 'signed_application');
                fd.append('file', file);
                try {
                    const response = await fetch(`/documents/${position}/api/upload/`, {
                        method: 'POST',
                        body: fd,
                        headers: csrf ? { 'X-CSRFToken': csrf } : {},
                    });
                    const data = await response.json();
                    if (data.success) {
                        const msg = data.pipeline_note || data.message || 'Document uploaded.';
                        rfqPromptSignedDocReview(reviewUrl, msg, applicationId, referenceNumber, applicantId);
                    } else {
                        rfqShowAlert(data.error || 'Upload failed.', 'Upload', 'default');
                        if (triggerBtn) {
                            triggerBtn.disabled = false;
                            triggerBtn.innerHTML = oldHtml;
                        }
                    }
                } catch (err) {
                    rfqShowAlert((err && err.message) ? err.message : 'Upload failed.', 'Upload', 'default');
                    if (triggerBtn) {
                        triggerBtn.disabled = false;
                        triggerBtn.innerHTML = oldHtml;
                    }
                }
            });
        }

        // Premium Hover Card popover initialization
        const hoverCard = document.getElementById('applicantHoverCard');
        const hcAvatar = document.getElementById('hcAvatar');
        const hcName = document.getElementById('hcName');
        const hcTx = document.getElementById('hcTx');
        const hcRef = document.getElementById('hcRef');
        const hcRefRow = document.getElementById('hcRefRow');
        const hcBrgy = document.getElementById('hcBrgy');
        const hcDob = document.getElementById('hcDob');
        const hcDispRow = document.getElementById('hcDispRow');
        const hcDispBadge = document.getElementById('hcDispBadge');

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

            const dispReason = nameSpan.dataset.dispReason || '';
            if (dispReason && hcDispRow && hcDispBadge) {
                let badgeClass = '';
                let badgeText = '';
                if (dispReason === 'danger_zone') {
                    badgeClass = 'priority-hsl-badge option-a';
                    badgeText = 'Danger Zone';
                } else if (dispReason === 'ejected') {
                    badgeClass = 'priority-hsl-badge option-b';
                    badgeText = 'Ejected';
                } else if (dispReason === 'relocated') {
                    badgeClass = 'priority-hsl-badge option-c';
                    badgeText = 'Relocated';
                } else if (dispReason === 'not_abc') {
                    badgeClass = 'priority-hsl-badge option-d';
                    badgeText = 'Other';
                }

                if (badgeText) {
                    hcDispBadge.className = badgeClass;
                    hcDispBadge.textContent = badgeText;
                    hcDispRow.style.display = 'flex';
                } else {
                    hcDispRow.style.display = 'none';
                }
            } else if (hcDispRow) {
                hcDispRow.style.display = 'none';
            }

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

        if (!selectedApplicantId) return;
        const targetRow = document.querySelector(`tr[data-applicant-id="${selectedApplicantId}"]`);
        if (!targetRow) return;
        targetRow.classList.add('rfq-selected-row');
        targetRow.scrollIntoView({ behavior: 'smooth', block: 'center' });
    });
