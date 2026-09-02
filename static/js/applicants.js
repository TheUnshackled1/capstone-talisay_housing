/* ===================================================================
   applicants.js
   Extracted from templates/staff/applicants.html
   =================================================================== */

// Auto-hide messages
function getInputValue(id) {
    const el = document.getElementById(id);
    return el ? el.value : '';
}
function setInputValue(id, val) {
    const el = document.getElementById(id);
    if (el) el.value = (val !== undefined && val !== null) ? val : '';
}
function setElementHtml(id, html) {
    const el = document.getElementById(id);
    if (el) el.innerHTML = html;
}
function getCsrfToken() {
    const el = document.querySelector('[name=csrfmiddlewaretoken]');
    return el ? el.value : '';
}
    // Auto-hide messages after 5 seconds
    setTimeout(function () {
        document.querySelectorAll('[style*="position: fixed"][style*="top: 1rem"]').forEach(el => {
            el.style.transition = 'opacity 0.5s';
            el.style.opacity = '0';
            setTimeout(() => el.remove(), 500);
        });
    }, 5000);

// Main Applicants JS
    // Store applicants data in JavaScript
    const applicantsData = JSON.parse(document.getElementById('applicantsDataJson')?.textContent || '[]');
    const archiveReviewData = JSON.parse(document.getElementById('archiveReviewDataJson')?.textContent || '{}');
    let reviewModalArchiveMode = false;

    const FIRST_REVIEW_INDEX = applicantsData.length > 0 ? 0 : -1;
    const canModify = (document.getElementById('canModifyFlag')?.value || 'false') === 'true';
    const duplicatePreviewUrl = window.APPLICANTS_CONFIG.duplicatePreviewUrl;
    const evaluationApplicationsUrl = window.APPLICANTS_CONFIG.evaluationApplicationsUrl;
    const DOC_KEY_TO_APPLICANT_PROP = {
        doc_brgy_residency: 'docBrgyResidency',
        doc_brgy_indigency: 'docBrgyIndigency',
        doc_cedula: 'docCedula',
        doc_police_clearance: 'docPoliceClearance',
        doc_no_property: 'docNoProperty',
        doc_2x2_picture: 'doc2x2Picture',
        doc_sketch_location: 'docSketchLocation',
        doc_voter_cert: 'docVoterCert',
    };
    const DOC_KEY_TO_VAULT_TYPE = {
        doc_brgy_residency: 'barangay_residency',
        doc_brgy_indigency: 'barangay_indigency',
        doc_cedula: 'cedula',
        doc_police_clearance: 'police_clearance',
        doc_no_property: 'no_property',
        doc_2x2_picture: 'photo_2x2',
        doc_sketch_location: 'house_sketch',
        doc_voter_cert: 'voter_certification',
        doc_cdrrmo: 'cdrrmo_cert',
        doc_isf_situational: 'isf_situational_docs',
    };
    const APPLICANT_REQUIREMENT_SCAN_STATUS_URL = window.APPLICANTS_CONFIG.applicantRequirementScanStatusUrl;
    const REMOVE_SCANNED_REQUIREMENT_URL = window.APPLICANTS_CONFIG.removeScannedRequirementUrl;
    const IHSMS_VAULT_SYNC_KEY = 'ihsms_vault_doc_sync';
    const IHSMS_VAULT_SYNC_BC = 'ihsms_vault_doc_sync_bc';
    let DWTObject = null;
    if (window.Dynamsoft?.DWT) {
        Dynamsoft.DWT.RegisterEvent("OnWebTwainReady", function () {
            DWTObject = Dynamsoft.DWT.GetWebTwain("dwtcontrolContainer");
        });
    }

    async function waitForDwtReady(timeoutMs = 5000) {
        const startedAt = Date.now();
        while (!DWTObject && (Date.now() - startedAt) < timeoutMs) {
            await new Promise(function (resolve) { setTimeout(resolve, 100); });
        }
        return DWTObject;
    }

    async function acquireImageWithDwt(opts = {}) {
        const dwt = await waitForDwtReady();
        if (!dwt) throw new Error('Scanner SDK is not ready yet. Refresh the page and try again.');
        const shouldSelectSource = opts.selectSource === true;
        const shouldCloseSourceAfterAcquire = opts.closeSourceAfterAcquire !== false;
        if (shouldSelectSource) {
            await dwt.SelectSourceAsync();
        }
        const beforeCount = Number(dwt.HowManyImagesInBuffer || 0);
        await dwt.AcquireImageAsync({
            IfCloseSourceAfterAcquire: shouldCloseSourceAfterAcquire,
        });
        const afterCount = Number(dwt.HowManyImagesInBuffer || 0);
        if (afterCount <= beforeCount) {
            throw new Error('No image was acquired from the scanner.');
        }
        return true;
    }

    function applyScannedStateToApplicant(docKey) {
        if (!currentApplicant) return;
        const prop = DOC_KEY_TO_APPLICANT_PROP[docKey];
        if (!prop) return;
        currentApplicant[prop] = true;
        currentApplicant.docsCount = [
            currentApplicant.docBrgyResidency,
            currentApplicant.docBrgyIndigency,
            currentApplicant.docCedula,
            currentApplicant.docPoliceClearance,
            currentApplicant.docNoProperty,
            currentApplicant.doc2x2Picture,
            currentApplicant.docSketchLocation,
            currentApplicant.docVoterCert,
        ].filter(Boolean).length;

        const currentId = String(currentApplicant.applicantId || currentApplicant.id || '');
        const match = applicantsData.find(function (a) {
            return String(a.applicantId || a.id || '') === currentId;
        });
        if (match) {
            match[prop] = true;
            match.docsCount = currentApplicant.docsCount;
        }
    }

    function uploadCurrentScannedImageForApplicant(applicantId, referenceNumber, docKey, docCode) {
        return new Promise(async function (resolve, reject) {
            const originalAlert = window.alert;
            const shouldSuppressDwtHttpAlert = function (message) {
                if (typeof message !== 'string') return false;
                const normalized = message.replace(/\s+/g, ' ').trim();
                return /^HTTP process:\s*OK\s*\(200\)\.?$/i.test(normalized) || normalized.toLowerCase().startsWith('http process: ok');
            };
            const restoreAlert = function () {
                window.alert = originalAlert;
            };
            const parseUploadResponse = function (rawResponse) {
                if (!rawResponse) return { ok: true, document_url: '', document_name: '' };
                try {
                    const parsed = typeof rawResponse === 'string' ? JSON.parse(rawResponse) : rawResponse;
                    if (parsed && typeof parsed === 'object') {
                        return {
                            ok: parsed.success !== false,
                            document_url: parsed.document_url || '',
                            document_name: parsed.document_name || '',
                        };
                    }
                } catch (_err) {
                    // keep default fallback
                }
                return { ok: true, document_url: '', document_name: '' };
            };
            window.alert = function (message) {
                if (shouldSuppressDwtHttpAlert(message)) {
                    return;
                }
                return originalAlert.apply(window, arguments);
            };
            try {
                const dwt = await waitForDwtReady();
                if (!dwt) {
                    restoreAlert();
                    reject(new Error('Scanner SDK is not ready.'));
                    return;
                }
                const index = Number(dwt.CurrentImageIndexInBuffer);
                if (index < 0) {
                    restoreAlert();
                    reject(new Error('No scanned image in buffer.'));
                    return;
                }
                const safeApplicantId = encodeURIComponent(applicantId || '');
                const safeDocKey = encodeURIComponent(docKey || '');
                const safeDocCode = encodeURIComponent(docCode || '');
                const uploadUrl = `${window.APPLICANTS_CONFIG.uploadScannedRequirementUrl}?applicant_id=${safeApplicantId}&doc_key=${safeDocKey}&doc_code=${safeDocCode}&capture_method=scan`;
                const fileName = `${(referenceNumber || 'applicant')}_${docCode || 'scan'}.png`;

                dwt.HTTPUpload(
                    uploadUrl,
                    [index],
                    Dynamsoft.DWT.EnumDWT_ImageType.IT_PNG,
                    Dynamsoft.DWT.EnumDWT_UploadDataFormat.Binary,
                    fileName,
                    function (httpResponse) {
                        restoreAlert();
                        resolve(parseUploadResponse(httpResponse));
                    },
                    function (_errorCode, errorString, httpResponse) {
                        restoreAlert();
                        let message = errorString || 'Upload failed.';
                        const normalizedError = String(message || '').replace(/\s+/g, ' ').trim();
                        if (/^HTTP process:\s*OK\s*\(200\)\.?$/i.test(normalizedError) || normalizedError.toLowerCase().startsWith('http process: ok')) {
                            resolve(parseUploadResponse(httpResponse));
                            return;
                        }
                        if (httpResponse) {
                            try {
                                const parsed = JSON.parse(httpResponse);
                                if (parsed && parsed.success) {
                                    resolve(parseUploadResponse(parsed));
                                    return;
                                }
                                if (parsed && parsed.error) message = parsed.error;
                            } catch (_err) {
                                // keep fallback message
                            }
                        }
                        reject(new Error(message));
                    }
                );
            } catch (error) {
                restoreAlert();
                reject(error);
            }
        });
    }

    function uploadCurrentScannedImage(docKey, docCode) {
        if (!currentApplicant) {
            return Promise.reject(new Error('No applicant selected.'));
        }
        return uploadCurrentScannedImageForApplicant(
            currentApplicant.applicantId || currentApplicant.id || '',
            currentApplicant.referenceNumber || '',
            docKey,
            docCode
        );
    }
    // Intake module does not hand off/navigate to Applications automatically.
    // (Applications module is accessed from its own navigation item.)
    let noticePrimaryHandler = null;
    let noticeSecondaryHandler = null;

    function closeNoticeModal() {
        const overlay = document.getElementById('noticeModalOverlay');
        const modal = document.getElementById('noticeModal');
        const bodyEl = document.getElementById('noticeModalBody');
        const refWrap = document.getElementById('noticeModalRefWrap');
        if (overlay) {
            overlay.classList.remove('active');
            overlay.classList.remove('notice-modal-overlay--top');
            overlay.style.zIndex = '';
        }
        if (modal) {
            modal.classList.remove('notice-modal--blacklist-blocked');
            modal.classList.remove('notice-modal--celebration');
        }
        if (bodyEl) bodyEl.classList.remove('notice-modal-body--blacklist-blocked');
        if (refWrap) {
            refWrap.innerHTML = '';
            refWrap.style.display = 'none';
        }
        const progBar = document.getElementById('noticeModalProgressBar');
        if (progBar) {
            progBar.style.display = 'none';
        }
        if (window.noticeModalCountdownTimeout) {
            clearTimeout(window.noticeModalCountdownTimeout);
            window.noticeModalCountdownTimeout = null;
        }
        noticePrimaryHandler = null;
        noticeSecondaryHandler = null;
    }

    function buildProceedArchiveSuccessHtml() {
        return (
            '<p class="notice-success-lead">Moved to <strong>LIST OF APPLICANTS</strong></p>' +
            '<p class="notice-success-detail">This record is archived and will appear in the list below.</p>'
        );
    }

    function buildProceedEvaluationSuccessHtml(fullName) {
        const safeName = (typeof escapeHtml === 'function') ? escapeHtml(fullName || 'Applicant') : String(fullName || 'Applicant');
        return (
            '<p class="notice-success-lead">Moved to <strong>Application &amp; Eligibility</strong></p>' +
            '<div class="notice-modal-name-banner">' + safeName + '</div>'
        );
    }

    function parseRegistrationSuccessMessage(message) {
        const raw = String(message || '').trim();
        const refMatch = raw.match(/Reference:\s*(\S+)/i);
        const nameMatch = raw.match(/Successfully registered:\s*(.+?)\s*\|\s*Reference:/i);
        return {
            fullName: nameMatch ? nameMatch[1].trim() : '',
            referenceNumber: refMatch ? refMatch[1].trim() : '',
        };
    }

    function buildApplicantRegisteredSuccessHtml(fullName) {
        const safeName = (typeof escapeHtml === 'function') ? escapeHtml(fullName || 'Applicant') : String(fullName || 'Applicant');
        return (
            '<p class="notice-success-lead">Successfully registered: <strong>' + safeName + '</strong></p>'
        );
    }

    function showNoticeModal({ title = 'Notice', message = '', messageHtml = '', type = 'info', primaryText = 'OK', secondaryText = '', onPrimary = null, onSecondary = null, allowHtml = false, refPill = '', celebration = false, applicantName = null }) {
        const overlay = document.getElementById('noticeModalOverlay');
        const modal = document.getElementById('noticeModal');
        const titleEl = document.getElementById('noticeModalTitle');
        const bodyEl = document.getElementById('noticeModalBody');
        const refWrap = document.getElementById('noticeModalRefWrap');
        const primaryBtn = document.getElementById('noticePrimaryBtn');
        const secondaryBtn = document.getElementById('noticeSecondaryBtn');
        const subtitleEl = document.getElementById('noticeModalSubtitle');
        const subtitleNameEl = document.getElementById('noticeModalSubtitleName');
        
        if (!overlay || !modal || !titleEl || !bodyEl || !primaryBtn || !secondaryBtn) return;

        // Reset countdown timer if already active
        if (window.noticeModalCountdownTimeout) {
            clearTimeout(window.noticeModalCountdownTimeout);
            window.noticeModalCountdownTimeout = null;
        }
        const progBar = document.getElementById('noticeModalProgressBar');
        if (progBar) {
            progBar.style.display = 'none';
        }

        modal.classList.remove('info', 'success', 'warning', 'error');
        modal.classList.add(type);
        const isCelebration = !!(celebration && type === 'success');
        modal.classList.toggle('notice-modal--celebration', isCelebration);
        if (refWrap) {
            refWrap.innerHTML = '';
            refWrap.style.display = 'none';
            const rp = refPill && String(refPill).trim();
            if (rp && (type === 'success' || type === 'error')) {
                const pill = document.createElement('span');
                pill.className = 'flow-alert-ref-pill';
                pill.style.marginTop = '0';
                pill.textContent = rp;
                refWrap.appendChild(pill);
                refWrap.style.display = 'block';
            }
        }
        titleEl.textContent = title;
        if (allowHtml && messageHtml) {
            bodyEl.innerHTML = messageHtml;
        } else {
            bodyEl.textContent = message;
        }
        
        if (applicantName && subtitleEl && subtitleNameEl) {
            subtitleNameEl.textContent = applicantName;
            subtitleEl.style.display = 'block';
        } else if (subtitleEl) {
            subtitleEl.style.display = 'none';
        }
        
        primaryBtn.textContent = primaryText || 'OK';
        secondaryBtn.textContent = secondaryText || 'Cancel';
        secondaryBtn.style.display = secondaryText ? '' : 'none';

        const normalizedTitle = String(title || '').trim().toLowerCase();
        const normalizedMessage = String(message || '').replace(/\s+/g, ' ').trim();
        const isScannerHttpOkNotice =
            normalizedTitle === 'notice' &&
            /http\s*process.*ok.*\(\s*200\s*\)/i.test(normalizedMessage);

        // Force refresh for scanner HTTP success popups so checklist state updates immediately.
        noticePrimaryHandler = isScannerHttpOkNotice
            ? function () { window.location.replace(window.location.href); }
            : onPrimary;
        noticeSecondaryHandler = onSecondary;
        overlay.classList.add('active');

        // Start countdown for celebration success notice modals (4 seconds)
        if (isCelebration) {
            if (progBar) {
                progBar.style.display = 'block';
                // Trigger reflow to restart CSS animation
                progBar.offsetHeight;
            }
            window.noticeModalCountdownTimeout = setTimeout(function () {
                const handler = noticePrimaryHandler;
                closeNoticeModal();
                if (typeof handler === 'function') {
                    handler();
                }
            }, 4000);
        }
    }

    function applyArchiveRequirementsBlacklistState(payload) {
        const banner = document.getElementById('archiveBlacklistBanner');
        const proceedBtn = document.getElementById('archiveProceedToEvaluationBtn');
        const deleteBtn = document.getElementById('archiveDeleteBlacklistedBtn');
        const blocked = !!(payload && payload.blacklistBlocked);
        if (banner) {
            if (blocked) {
                const reason = (payload.blacklistReason || '').trim();
                const regRef = (payload.blacklistRegistryRef || '').trim();
                const regName = (payload.blacklistRegistryName || '').trim();
                const regLine = regRef && regName ? (regRef + ' — ' + regName) : (regName || regRef || '—');
                banner.innerHTML =
                    '<strong>Cannot proceed — Blacklisted.</strong> '
                    + 'This applicant cannot go to Applicant Evaluation and Eligibility while on the '
                    + '<strong>Blacklisted Beneficiaries</strong> registry'
                    + (regLine !== '—' ? (' (' + regLine + ')') : '')
                    + (reason ? ('. Reason: ' + reason + '.') : '.')
                    + ' Resolve the registry entry in Units monitoring first.';
                banner.hidden = false;
                banner.classList.add('is-visible');
            } else {
                banner.innerHTML = '';
                banner.hidden = true;
                banner.classList.remove('is-visible');
            }
        }
        if (proceedBtn && blocked) {
            proceedBtn.disabled = true;
            proceedBtn.classList.remove('is-ready');
        }
        if (deleteBtn) {
            if (blocked) {
                deleteBtn.style.display = '';
            } else {
                deleteBtn.style.display = 'none';
            }
        }
        return blocked;
    }

    // Delete Blacklisted Applicant from Requirements Modal
    function deleteBlacklistedApplicantFromModal() {
        if (!currentArchiveRequirementsPayload) {
            showFlowAlert('Error: Applicant data not found.');
            return;
        }

        const ref = currentArchiveRequirementsPayload.referenceNumber || '';
        const fullName = currentArchiveRequirementsPayload.fullName || 'This applicant';
        const applicantId = currentArchiveRequirementsPayload.applicantId || '';

        if (!applicantId) {
            showFlowAlert('Error: Applicant ID not found.');
            return;
        }

        showNoticeModal({
            title: 'Delete Blacklisted Applicant?',
            message: `Reference: ${ref}\n\nThis cannot be undone.`,
            type: 'error',
            primaryText: 'Yes, Delete',
            secondaryText: 'Cancel',
            applicantName: fullName,
            onPrimary: () => {
                const deleteBtn = document.getElementById('archiveDeleteBlacklistedBtn');
                if (deleteBtn) {
                    deleteBtn.disabled = true;
                    deleteBtn.textContent = 'Deleting...';
                }

                const formData = new FormData();
                formData.append('csrfmiddlewaretoken', getCsrfToken());
                formData.append('applicant_id', applicantId);

                fetch(window.APPLICANTS_CONFIG.deleteApplicantUrl, {
                    method: 'POST',
                    body: formData
                })
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            showFlowAlert('Blacklisted applicant deleted successfully.', 'Success', null, 'success');
                            closeArchiveRequirementsModal();
                            setTimeout(() => location.reload(), 600);
                        } else {
                            if (deleteBtn) {
                                deleteBtn.disabled = false;
                                deleteBtn.textContent = 'Delete Blacklisted Applicant';
                            }
                            showFlowAlert('Error: ' + (data.error || 'Unable to delete applicant'));
                        }
                    })
                    .catch(error => {
                        if (deleteBtn) {
                            deleteBtn.disabled = false;
                            deleteBtn.textContent = 'Delete Blacklisted Applicant';
                        }
                        showFlowAlert('Error: ' + error.message);
                    });
            }
        });
    }
    window.deleteBlacklistedApplicantFromModal = deleteBlacklistedApplicantFromModal;



    function openArchiveHandoffSummary(buttonEl) {
        if (!buttonEl) return;
        const d = buttonEl.dataset || {};
        const setText = (id, value) => {
            const el = document.getElementById(id);
            if (el) el.textContent = value || 'N/A';
        };

        setText('archiveSummarySubtitle', `${d.reference || 'N/A'} • ${d.name || 'N/A'}`);
        setText('archiveSummaryReference', d.reference || 'N/A');
        setText('archiveSummaryName', d.name || 'N/A');
        setText('archiveSummaryLastName', d.lastName || 'N/A');
        setText('archiveSummaryFirstName', d.firstName || 'N/A');
        setText('archiveSummaryMiddleName', d.middleName || 'N/A');
        setText('archiveSummaryExtensionName', d.extensionName || 'N/A');
        setText('archiveSummaryChannel', d.channel || 'N/A');
        setText('archiveSummarySms', d.sms || 'N/A');
        setText('archiveSummaryDob', d.dob || 'N/A');
        setText('archiveSummaryBarangay', d.barangay || 'N/A');
        setText('archiveSummaryEncodedBy', d.staff || 'Unknown');
        setText('archiveSummaryStaffRole', d.staffPosition || 'N/A');
        setText('archiveSummaryProceededAt', d.proceeded || 'N/A');
        setText('archiveSummaryProceededBy', d.proceededBy || 'Unknown');
        setText('archiveSummaryModule2Summary', d.module2Summary || `${d.reference || 'N/A'} • ${d.name || 'N/A'}`);
        setText('archiveSummaryModule3Summary', d.module3Summary || 'Not yet proceeded to Module 3');
        setText('archiveSummaryModule3At', d.module3At || 'N/A');
        setText('archiveSummaryModule3By', d.module3By || 'N/A');

        const modal = document.getElementById('archiveSummaryModal');
        if (modal) modal.classList.add('active');
    }

    function closeArchiveSummaryModal() {
        const modal = document.getElementById('archiveSummaryModal');
        if (modal) modal.classList.remove('active');
    }

    function closeArchiveRequirementsModal() {
        pendingArchiveUploadContext = null;
        const modal = document.getElementById('archiveRequirementsModal');
        if (modal) modal.classList.remove('active');
    }

    const ARCHIVE_DOC_KEY_BY_CODE = {
        R01: 'doc_brgy_residency',
        R02: 'doc_brgy_indigency',
        R03: 'doc_cedula',
        R04: 'doc_police_clearance',
        R05: 'doc_no_property',
        R06: 'doc_2x2_picture',
        R07: 'doc_sketch_location',
        CDRRMO: 'doc_cdrrmo',
        'ISF-SIT': 'doc_isf_situational',
        RVT: 'doc_voter_cert',
    };

    function isApplicantRequirementOnFile(applicant, code) {
        if (!applicant) return false;
        const rawCode = String(code || '').trim().toUpperCase();
        const docKey = ARCHIVE_DOC_KEY_BY_CODE[rawCode];
        if (!docKey) return false;
        const vaultTypes = Array.isArray(applicant.vaultDocumentTypes) ? applicant.vaultDocumentTypes : [];
        const vaultType = DOC_KEY_TO_VAULT_TYPE[docKey];
        if (vaultType && vaultTypes.indexOf(vaultType) >= 0) return true;
        const prop = DOC_KEY_TO_APPLICANT_PROP[docKey];
        return prop ? !!applicant[prop] : false;
    }

    async function refreshApplicantRequirementScanPayload(payload) {
        if (!payload || !payload.applicantId) return payload;
        try {
            const url = APPLICANT_REQUIREMENT_SCAN_STATUS_URL
                + '?applicant_id=' + encodeURIComponent(String(payload.applicantId));
            const response = await fetch(url, { credentials: 'same-origin', headers: { Accept: 'application/json' } });
            const fresh = await response.json();
            if (!fresh || !fresh.success || !Array.isArray(fresh.rows)) return payload;
            payload.rows = fresh.rows;
            payload.displacementReason = fresh.displacementReason || payload.displacementReason || '';
            payload.blacklistBlocked = !!fresh.blacklistBlocked;
            payload.blacklistReason = fresh.blacklistReason || '';
            payload.blacklistRegistryName = fresh.blacklistRegistryName || '';
            payload.blacklistRegistryRef = fresh.blacklistRegistryRef || '';
            if (fresh.scannedCount != null) payload.scannedCount = fresh.scannedCount;
            if (fresh.trackableTotal != null) payload.trackableTotal = fresh.trackableTotal;
            if (fresh.requiredScannedCount != null) payload.requiredScannedCount = fresh.requiredScannedCount;
            if (fresh.requiredTotal != null) payload.requiredTotal = fresh.requiredTotal;
            if (Array.isArray(fresh.vaultDocumentTypes)) payload.vaultDocumentTypes = fresh.vaultDocumentTypes;
            return payload;
        } catch (_err) {
            return payload;
        }
    }

    function publishVaultDocumentChange(meta) {
        const ts = String(Date.now());
        const envelope = Object.assign({ ts: ts }, meta || {});
        try {
            localStorage.setItem(IHSMS_VAULT_SYNC_KEY, JSON.stringify(envelope));
        } catch (_err) { /* ignore */ }
        try {
            if (typeof BroadcastChannel !== 'undefined') {
                const bc = new BroadcastChannel(IHSMS_VAULT_SYNC_BC);
                bc.postMessage(envelope);
                bc.close();
            }
        } catch (_err) { /* ignore */ }
    }

    function finalizeArchiveVaultSync(refreshedPayload) {
        if (!refreshedPayload) return;
        currentArchiveRequirementsPayload = refreshedPayload;
        const scriptEl = document.getElementById('archive-pages-documents-payload');
        const ref = String(refreshedPayload.referenceNumber || '').trim();
        if (scriptEl && ref) {
            try {
                const payloadMap = JSON.parse(scriptEl.textContent || '{}');
                payloadMap[ref] = refreshedPayload;
                scriptEl.textContent = JSON.stringify(payloadMap);
            } catch (_err) { /* ignore */ }
        }
        renderArchiveRequirementsChecklistTable(refreshedPayload);
        applyArchiveRequirementsBlacklistState(refreshedPayload);
        publishVaultDocumentChange({
            applicantId: refreshedPayload.applicantId || '',
            referenceNumber: ref,
        });
    }

    function isFollowUpRequirement(code) {
        return String(code || '').toUpperCase() === 'ISF-SIT';
    }
    let currentArchiveRequirementsPayload = null;
    let pendingArchiveUploadContext = null;
    let archiveRowUploadBusyButton = null;
    let archiveReplaceDocConfirmResolver = null;
    let archiveReplaceDocPendingRow = null;

    function archiveReqFindRow(code) {
        const safeCode = String(code || '').trim().toUpperCase();
        const payload = currentArchiveRequirementsPayload;
        if (!payload || !Array.isArray(payload.rows)) return null;
        return payload.rows.find(function (r) {
            return String(r.code || '').trim().toUpperCase() === safeCode;
        }) || null;
    }

    function archiveReqRowHasFile(row) {
        if (!row) return false;
        return !!(row.scanned || String(row.latest_file_url || '').trim());
    }

    function archiveCloseReplaceDocOverlay(event) {
        if (event && event.target && event.target.id !== 'archiveReplaceDocOverlay') return;
        archiveResolveReplaceDocConfirm('keep');
    }
    window.archiveCloseReplaceDocOverlay = archiveCloseReplaceDocOverlay;

    function archiveResolveReplaceDocConfirm(action) {
        const overlay = document.getElementById('archiveReplaceDocOverlay');
        if (overlay) {
            overlay.classList.remove('active');
            if (overlay._archiveReplaceEsc) {
                document.removeEventListener('keydown', overlay._archiveReplaceEsc);
                overlay._archiveReplaceEsc = null;
            }
        }
        archiveReplaceDocPendingRow = null;
        if (typeof archiveReplaceDocConfirmResolver === 'function') {
            const resolver = archiveReplaceDocConfirmResolver;
            archiveReplaceDocConfirmResolver = null;
            const normalized = action === 'replace' || action === 'remove' ? action : 'keep';
            resolver(normalized);
        }
    }
    window.archiveResolveReplaceDocConfirm = archiveResolveReplaceDocConfirm;

    function archiveConfirmReplaceExistingDocument(row) {
        if (!archiveReqRowHasFile(row)) return Promise.resolve('replace');
        const overlay = document.getElementById('archiveReplaceDocOverlay');
        const nameEl = document.getElementById('archiveReplaceDocFileName');
        const reqEl = document.getElementById('archiveReplaceDocRequirement');
        if (!overlay || !nameEl) {
            const name = String(row.latest_file_name || row.name || row.code || 'this requirement').trim();
            return Promise.resolve(window.confirm(
                'A file is already on file for ' + name + '.\n\nReplace it with the new upload or scan?'
            ) ? 'replace' : 'keep');
        }
        archiveReplaceDocPendingRow = row;
        const fileName = String(row.latest_file_name || row.name || 'Document on file').trim();
        const reqCode = String(row.code || '').trim();
        const reqName = String(row.name || '').trim();
        nameEl.textContent = fileName;
        if (reqEl) {
            reqEl.textContent = reqCode && reqName ? (reqCode + ' — ' + reqName) : (reqCode || reqName || '—');
        }
        overlay.classList.add('active');
        const escHandler = function (e) {
            if (e.key === 'Escape') archiveResolveReplaceDocConfirm('keep');
        };
        overlay._archiveReplaceEsc = escHandler;
        document.addEventListener('keydown', escHandler);
        return new Promise(function (resolve) {
            archiveReplaceDocConfirmResolver = resolve;
        });
    }

    /** Actions column — Scan only; filed status appears in the Status column. */
    function buildArchiveReqActionsInnerHtml(safeCode, row) {
        const rawCode = String(safeCode || '').trim().toUpperCase();
        if (!ARCHIVE_DOC_KEY_BY_CODE[rawCode]) {
            return '<span style="color:#94a3b8;font-size:0.75rem;width:11.7rem;display:inline-flex;justify-content:center;align-items:center;">—</span>';
        }
        const hasFile = archiveReqRowHasFile(row);
        const docName = escapeHtml(String((row && row.latest_file_name) || (row && row.name) || rawCode).trim() || 'Document on file');
        const hasExistingAttr = hasFile ? '1' : '0';
        const isBlacklisted = !!(currentArchiveRequirementsPayload && currentArchiveRequirementsPayload.blacklistBlocked);
        const disabledAttr = isBlacklisted ? ' disabled' : '';
        const disabledTitle = isBlacklisted ? ' — Resolve blacklist first' : '';

        const scanSvg = '<span class="btn-icon-block"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7V5a2 2 0 0 1 2-2h2"></path><path d="M17 3h2a2 2 0 0 1 2 2v2"></path><path d="M21 17v2a2 2 0 0 1-2 2h-2"></path><path d="M7 21H5a2 2 0 0 1-2-2v-2"></path><line x1="3" y1="12" x2="21" y2="12"></line></svg></span>';

        let removeBtnHtml = '<span style="color:#94a3b8;font-size:0.75rem;width:6.4rem;display:inline-flex;justify-content:center;align-items:center;">—</span>';
        if (hasFile) {
            const trashSvg = '<span class="btn-icon-block"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path><line x1="10" y1="11" x2="10" y2="17"></line><line x1="14" y1="11" x2="14" y2="17"></line></svg></span>';
            removeBtnHtml = '<button type="button" class="btn-modal primary archive-replace-btn-confirm archive-req-remove-btn" data-archive-code="' + safeCode + '" onclick="removeArchiveRequirementByCode(this.getAttribute(\'data-archive-code\'))" title="Remove requirement from file"' + disabledAttr + '>' + trashSvg + '<span>REMOVE</span></button>';
        }

        return '<div class="archive-req-actions-group" style="display:flex; gap:0.4rem; align-items:center; justify-content:center;">'
            + '<button type="button" class="btn-modal secondary archive-req-row-scan-btn" data-archive-scan-code="' + safeCode + '" data-has-existing-doc="' + hasExistingAttr + '" data-existing-doc-name="' + docName + '" onclick="scanArchiveRequirementByCode(this.getAttribute(\'data-archive-scan-code\'))" title="Capture from scanner (TWAIN) — saves to document vault' + disabledTitle + '"' + disabledAttr + '>' + scanSvg + '<span>SCAN</span></button>'
            + removeBtnHtml
            + '</div>';
    }

    /** Status column — Uploaded / Scanned (opens file when URL available). */
    function buildArchiveReqViewInnerHtml(row) {
        const latestFileUrl = String((row && row.latest_file_url) || '').trim();
        const filedLabel = String((row && row.filed_via_label) || '').trim().toUpperCase();
        if (!filedLabel && !latestFileUrl) {
            return '<span style="color:#94a3b8;font-size:0.75rem;display:inline-flex;justify-content:center;width:100%;">—</span>';
        }
        const label = escapeHtml(filedLabel || 'SCANNED');
        const docTitle = escapeHtml(String((row && row.latest_file_name) || filedLabel || 'Document on file').trim());
        const checkSvg = '<span class="btn-icon-block"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg></span>';
        if (latestFileUrl) {
            const safeLatestFileUrl = escapeHtml(latestFileUrl);
            return '<button type="button" class="req-scan req-scan-done archive-req-scan-link" data-archive-view-url="' + safeLatestFileUrl + '" onclick="openArchiveRequirementDocument(this.getAttribute(\'data-archive-view-url\'))" title="Open ' + docTitle + '">' + checkSvg + '<span>' + label + '</span></button>';
        }
        return '<span class="req-scan req-scan-done">' + checkSvg + '<span>' + label + '</span></span>';
    }

    function renderArchiveRequirementsChecklistTable(payload) {
        const tbody = document.getElementById('archiveRequirementsTableBody');
        if (!tbody) return;
        const scannedSummaryEl = document.getElementById('archiveRequirementsScannedSummary');
        const rowSummaryEl = document.getElementById('archiveRequirementsRowSummary');

        if (!payload || !payload.rows || !payload.rows.length) {
            if (scannedSummaryEl) scannedSummaryEl.textContent = '0/0';
            if (rowSummaryEl) rowSummaryEl.textContent = '0';
            tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;padding:1rem;color:#64748b;">No Group A requirements in the catalog. Seed requirements (e.g. R01–R07) to see this checklist.</td></tr>';
            setArchiveScanButtonBusy(false);
            return;
        }

        const rows = payload.rows || [];
        updateArchiveRequirementsSummary(rows, payload);
        tbody.innerHTML = rows.map(function (r) {
            const reqBadge = r.is_required_for_form
                ? '<span class="req-badge req-badge-yes">Required</span>'
                : '<span class="req-badge req-badge-no">Optional</span>';
            const rawCode = String(r.code || '').trim().toUpperCase();
            const code = escapeHtml(rawCode);
            const dispReason = payload && payload.displacementReason ? String(payload.displacementReason).trim() : '';
            let rowLabel = String(r.name || '');
            if (rawCode === 'ISF-SIT' && dispReason) {
                const situLabel = archiveModalIsfSitRowLabel(dispReason);
                if (situLabel) rowLabel = situLabel;
            }
            const tip = String(r.policy_tooltip || '').trim();
            const nameTitleAttr = tip ? ' title="' + escapeHtml(tip) + '"' : '';
            const followUpBadge = code === 'ISF-SIT'
                ? '<span class="req-badge req-badge-no" style="margin-left:0.45rem;">Follow-up</span>'
                : '';
            const rowStyle = code === 'ISF-SIT' ? ' style="background:#f8fafc;"' : '';
            const actionsCell = '<td class="archive-req-table-actions">' + buildArchiveReqActionsInnerHtml(rawCode, r) + '</td>';
            const viewCell = '<td>' + buildArchiveReqViewInnerHtml(r) + '</td>';
            return '<tr data-archive-code="' + code + '"' + rowStyle + '>'
                + '<td class="archive-req-table-name"' + nameTitleAttr + '>' + escapeHtml(rowLabel) + (followUpBadge ? ' ' + followUpBadge : '') + '</td>'
                + '<td>' + reqBadge + '</td>'
                + actionsCell
                + viewCell
                + '</tr>';
        }).join('');
        setArchiveScanButtonBusy(false);
    }

    async function removeArchiveRequirementByCode(codeRaw) {
        const code = String(codeRaw || '').trim().toUpperCase();
        const docKey = ARCHIVE_DOC_KEY_BY_CODE[code];
        const payload = currentArchiveRequirementsPayload;
        const row = archiveReqFindRow(code);
        const label = row && row.code && row.name
            ? (String(row.code).trim() + ' — ' + String(row.name).trim())
            : code;
        if (!docKey || !payload || !payload.applicantId) {
            showFlowAlert('Unable to remove this requirement.');
            return;
        }
        const csrfEl = document.querySelector('[name=csrfmiddlewaretoken]');
        if (!csrfEl) {
            showFlowAlert('Session token missing. Refresh the page and try again.');
            return;
        }
        const formData = new FormData();
        formData.append('csrfmiddlewaretoken', csrfEl.value);
        formData.append('applicant_id', String(payload.applicantId));
        formData.append('doc_key', docKey);

        try {
            const response = await fetch(REMOVE_SCANNED_REQUIREMENT_URL, {
                method: 'POST',
                body: formData,
                credentials: 'same-origin',
            });
            const data = await response.json();
            if (!data.success) {
                throw new Error(data.error || 'Unable to remove requirement.');
            }
            const refreshed = await refreshApplicantRequirementScanPayload(payload);
            finalizeArchiveVaultSync(refreshed);
            showFlowAlert(label + ' removed from file.', 'Success', null, 'success');
        } catch (error) {
            showFlowAlert(error.message || 'Unable to remove requirement.', 'Notice', null, 'warning');
        }
    }
    window.removeArchiveRequirementByCode = removeArchiveRequirementByCode;

    async function triggerArchiveRowDocumentUpload(codeRaw) {
        const code = String(codeRaw || '').trim().toUpperCase();
        const docKey = ARCHIVE_DOC_KEY_BY_CODE[code];
        if (!docKey) {
            showFlowAlert('This row cannot be uploaded from this checklist.');
            return;
        }
        const payload = currentArchiveRequirementsPayload;
        if (!payload || !payload.applicantId) {
            showFlowAlert('No applicant loaded.');
            return;
        }
        const choice = await archiveConfirmReplaceExistingDocument(archiveReqFindRow(code));
        if (choice === 'keep') return;
        if (choice === 'remove') {
            await removeArchiveRequirementByCode(code);
            return;
        }
        pendingArchiveUploadContext = {
            applicantId: String(payload.applicantId),
            referenceNumber: payload.referenceNumber || '',
            code: code,
            docKey: docKey,
        };
        const fileInput = document.getElementById('archiveRequirementFileInput');
        if (!fileInput) return;
        fileInput.value = '';
        fileInput.click();
    }
    window.triggerArchiveRowDocumentUpload = triggerArchiveRowDocumentUpload;

    async function scanArchiveRequirementByCode(codeRaw) {
        const code = String(codeRaw || '').trim().toUpperCase();
        const docKey = ARCHIVE_DOC_KEY_BY_CODE[code];
        const payload = currentArchiveRequirementsPayload;
        const applicantId = payload ? payload.applicantId : '';
        const referenceNumber = payload ? payload.referenceNumber : '';
        if (!docKey || !applicantId) {
            showFlowAlert('Unable to scan this requirement.');
            return;
        }
        const choice = await archiveConfirmReplaceExistingDocument(archiveReqFindRow(code));
        if (choice === 'keep') return;
        if (choice === 'remove') {
            await removeArchiveRequirementByCode(code);
            return;
        }

        const rowScanBtn = document.querySelector(
            '#archiveRequirementsModal button.archive-req-row-scan-btn[data-archive-scan-code="' + code + '"]'
        );
        if (rowScanBtn) {
            rowScanBtn.disabled = true;
            rowScanBtn.textContent = 'Scanning...';
        }
        try {
            const dwt = await waitForDwtReady();
            if (!dwt) throw new Error('Scanner SDK is not ready yet. Refresh the page and try again.');
            await dwt.SelectSourceAsync();
            await acquireImageWithDwt({ selectSource: false, closeSourceAfterAcquire: false });
            const uploadResult = await uploadCurrentScannedImageForApplicant(applicantId, referenceNumber, docKey, code);
            const isSaved = await saveArchiveRequirementDoc(applicantId, docKey, true);
            if (!isSaved) {
            }
            const refreshed = await refreshApplicantRequirementScanPayload(payload);
            finalizeArchiveVaultSync(refreshed);
            if (typeof dwt.CloseSource === 'function') {
                try { dwt.CloseSource(); } catch (_err) { }
            }
        } catch (error) {
            showFlowAlert(error.message || 'Unable to scan this requirement.', 'Notice', null, 'warning');
        } finally {
            if (rowScanBtn) {
                rowScanBtn.disabled = false;
            }
            renderArchiveRowStatusAndActions(code);
        }
    }
    window.scanArchiveRequirementByCode = scanArchiveRequirementByCode;
    function openArchiveRequirementDocument(url) {
        const safeUrl = String(url || '').trim();
        if (!safeUrl) return;
        window.open(safeUrl, '_blank', 'noopener');
    }
    window.openArchiveRequirementDocument = openArchiveRequirementDocument;

    function renderArchiveRowStatusAndActions(code) {
        const safeCode = String(code || '').trim().toUpperCase();
        if (!safeCode) return;
        const payload = currentArchiveRequirementsPayload;
        const row = payload && Array.isArray(payload.rows)
            ? payload.rows.find(function (r) { return String(r.code || '').trim().toUpperCase() === safeCode; })
            : null;
        if (!row) return;
        const rowEl = document.querySelector('#archiveRequirementsTableBody tr[data-archive-code="' + safeCode + '"]');
        if (!rowEl) return;
        const cells = rowEl.querySelectorAll('td');
        if (cells.length < 4) return;
        cells[2].innerHTML = buildArchiveReqActionsInnerHtml(safeCode, row);
        cells[3].innerHTML = buildArchiveReqViewInnerHtml(row);
    }

    function forceArchiveRowScannedDom(code, documentUrl) {
        const safeCode = String(code || '').trim().toUpperCase();
        if (!safeCode) return;
        const payload = currentArchiveRequirementsPayload;
        if (payload && Array.isArray(payload.rows)) {
            payload.rows.forEach(function (row) {
                if (String(row.code || '').trim().toUpperCase() === safeCode) {
                    row.scanned = true;
                    if (documentUrl) row.latest_file_url = documentUrl;
                    row.filed_via = 'scan';
                    row.filed_via_label = 'SCANNED';
                }
            });
        }
        renderArchiveRowStatusAndActions(safeCode);
    }

    function handleArchiveRequirementFileSelected(ev) {
        const input = ev.target;
        const file = input.files && input.files[0];
        const ctx = pendingArchiveUploadContext;
        pendingArchiveUploadContext = null;
        if (!file || !ctx) {
            if (input) input.value = '';
            return;
        }
        const formData = new FormData();
        formData.append('applicant_id', ctx.applicantId);
        formData.append('doc_key', ctx.docKey);
        formData.append('doc_code', ctx.code);
        formData.append('file', file);
        formData.append('capture_method', 'upload');

        const uploadUrl = window.APPLICANTS_CONFIG.uploadScannedRequirementUrl;
        const uploadBtn = document.querySelector(
            '#archiveRequirementsModal button.archive-req-upload-btn[data-archive-upload-code="' + ctx.code + '"]'
        );
        archiveRowUploadBusyButton = uploadBtn || null;
        if (uploadBtn) {
            uploadBtn.disabled = true;
            uploadBtn.textContent = 'Uploading...';
        }

        fetch(uploadUrl, {
            method: 'POST',
            body: formData,
            credentials: 'same-origin',
        })
            .then(function (response) { return response.json(); })
            .then(async function (data) {
                if (!data.success) {
                    throw new Error(data.error || 'Upload failed.');
                }
                const payload = currentArchiveRequirementsPayload;
                const refreshed = await refreshApplicantRequirementScanPayload(payload);
                finalizeArchiveVaultSync(refreshed);
            })
            .catch(function (err) {
                showFlowAlert(err.message || 'Upload failed.', 'Notice', null, 'warning');
            })
            .finally(function () {
                if (input) input.value = '';
                if (archiveRowUploadBusyButton) {
                    archiveRowUploadBusyButton.disabled = false;
                    archiveRowUploadBusyButton = null;
                }
                renderArchiveRowStatusAndActions(ctx.code);
            });
    }

    function setArchiveScanButtonBusy(isBusy) {
        const strictBtn = document.getElementById('archiveScanAllBtn');
        if (strictBtn) {
            strictBtn.disabled = isBusy;
            strictBtn.style.opacity = isBusy ? '0.6' : '1';
            strictBtn.style.cursor = isBusy ? 'wait' : 'pointer';
            strictBtn.textContent = isBusy ? 'Scanning documents...' : 'Scan documents';
        }
        document.querySelectorAll('#archiveRequirementsModal .archive-req-row-scan-btn').forEach(function (btn) {
            btn.disabled = isBusy;
            btn.style.opacity = isBusy ? '0.6' : '1';
            btn.style.cursor = isBusy ? 'wait' : 'pointer';
            if (!isBusy) {
                const code = btn.getAttribute('data-archive-scan-code');
                if (code) {
                    renderArchiveRowStatusAndActions(code);
                }
            }
        });
    }

    function syncArchiveRequirementsButtonSummary(scannedRequired, requiredTotal, scannedAll, totalAll) {
        const payload = currentArchiveRequirementsPayload;
        const ref = payload && payload.referenceNumber ? String(payload.referenceNumber) : '';
        if (!ref) return;
        const btn = document.querySelector('.btn-archive-docs[data-reference="' + ref + '"]');
        if (!btn) return;
        const scannedAllNum = Number(scannedAll) || 0;
        const totalAllNum = Number(totalAll) || 0;
        const scannedReqNum = Number(scannedRequired) || 0;
        const totalReqNum = Number(requiredTotal) || 0;
        let blocks = '';
        for (let i = 1; i <= 15; i++) {
            if (i <= scannedAllNum) blocks += '█';
            else if (i <= totalAllNum) blocks += '░';
        }
        btn.innerHTML = `
            <div style="display: flex; align-items: center; justify-content: center; gap: 0.35rem;">
                <span style="letter-spacing: 1px; font-size: 0.6rem; line-height: 1; opacity: 0.95;">${blocks}</span>
                <span style="font-weight: 700; font-size: 0.6rem; white-space: nowrap;">${scannedAllNum}/${totalAllNum}</span>
            </div>
        `;
        btn.title = 'Applicant requirement scan checklist — ' + scannedAllNum + ' of ' + totalAllNum + ' digitally filed';
        btn.classList.remove('btn-archive-docs--done', 'btn-archive-docs--partial', 'btn-archive-docs--none');
        if (totalReqNum > 0 && scannedReqNum >= totalReqNum) {
            btn.classList.add('btn-archive-docs--done');
        } else if (scannedAllNum > 0) {
            btn.classList.add('btn-archive-docs--partial');
        } else {
            btn.classList.add('btn-archive-docs--none');
        }
    }

    /**
     * LIST OF APPLICANTS — keep Status column in sync with the scan checklist (same X/Y as Documents).
     */
    function syncArchiveRequirementsListRowStatus(scannedRequired, requiredTotal, scannedAll, totalAll) {
        const payload = currentArchiveRequirementsPayload;
        const ref = payload && payload.referenceNumber ? String(payload.referenceNumber) : '';
        if (!ref) return;
        const btn = document.querySelector('.btn-archive-docs[data-reference="' + ref + '"]');
        if (!btn) return;
        const tr = btn.closest('tr');
        if (!tr) return;
        const statusTd = tr.querySelector('td[title*="Applicant requirements"], td[title*="Blacklisted"]');
        const statusPill = statusTd ? statusTd.querySelector('.pastel-status-pill') : null;
        if (!statusPill) return;
        const scannedAllNum = Number(scannedAll) || 0;
        const totalAllNum = Number(totalAll) || 0;
        const scannedReqNum = Number(scannedRequired) || 0;
        const totalReqNum = Number(requiredTotal) || 0;
        var label;
        var tier;
        if (payload && payload.blacklistBlocked) {
            label = 'Cannot proceed';
            tier = 'blocked';
            if (statusTd) {
                statusTd.title =
                    'Blacklisted — cannot proceed to Applicant Evaluation and Eligibility (' +
                    scannedAllNum + '/' + totalAllNum + ' docs on file)';
            }
        } else if (totalReqNum <= 0) {
            label = 'Pending';
            tier = 'pending';
            if (statusTd) {
                statusTd.title =
                    'Applicant requirements (scan checklist): ' +
                    scannedAllNum + '/' + totalAllNum + ' filed — same totals as Documents';
            }
        } else if (scannedReqNum >= totalReqNum) {
            label = 'Complete';
            tier = 'complete';
            if (statusTd) {
                statusTd.title =
                    'Applicant requirements (scan checklist): ' +
                    scannedAllNum + '/' + totalAllNum + ' filed — same totals as Documents';
            }
        } else if (scannedAllNum > 0) {
            label = 'Incomplete';
            tier = 'incomplete';
            if (statusTd) {
                statusTd.title =
                    'Applicant requirements (scan checklist): ' +
                    scannedAllNum + '/' + totalAllNum + ' filed — same totals as Documents';
            }
        } else {
            label = 'Pending';
            tier = 'pending';
            if (statusTd) {
                statusTd.title =
                    'Applicant requirements (scan checklist): ' +
                    scannedAllNum + '/' + totalAllNum + ' filed — same totals as Documents';
            }
        }
        const tierClasses = ['status--complete', 'status--incomplete', 'status--pending', 'status--blocked', 'status--disqualified', 'status--encoded'];
        tierClasses.forEach(function (cls) { statusPill.classList.remove(cls); });
        statusPill.classList.add('status--' + tier);
        const needsPulse = tier === 'pending' || tier === 'incomplete' || tier === 'complete';
        if (needsPulse) {
            statusPill.innerHTML = '<span class="pulse-dot"></span> ' + label;
        } else {
            statusPill.textContent = label;
        }
        var tds = tr.querySelectorAll('td');
        if (tds.length >= 11) {
            var refText = (tds[4].textContent || '').trim().toLowerCase();
            var nameCell = tds[1];
            var nameEl = nameCell.querySelector('.list-archive-full-name') || nameCell;
            var nameText = (nameEl.textContent || '').trim().toLowerCase();
            var barText = (tds[8].textContent || '').trim().toLowerCase();
            var agoText = (tds[3].textContent || '').trim().toLowerCase();
            var stText = label.toLowerCase();
            tr.setAttribute('data-searchable', [nameText, refText, barText, stText, agoText].filter(Boolean).join(' '));
        }
    }

    function updateArchiveRequirementsSummary(rows, payloadCtx) {
        const payload = payloadCtx || currentArchiveRequirementsPayload;
        const scannedSummaryEl = document.getElementById('archiveRequirementsScannedSummary');
        const rowSummaryEl = document.getElementById('archiveRequirementsRowSummary');
        const safeRows = Array.isArray(rows) ? rows : [];
        const requiredRows = safeRows.filter(function (r) { return !!r.is_required_for_form; });
        const scannedRequired = (payload && payload.requiredScannedCount != null)
            ? Number(payload.requiredScannedCount)
            : requiredRows.filter(function (r) { return !!r.scanned; }).length;
        const requiredTotal = (payload && payload.requiredTotal != null)
            ? Number(payload.requiredTotal)
            : requiredRows.length;
        if (scannedSummaryEl) {
            scannedSummaryEl.textContent = String(scannedRequired) + '/' + String(requiredTotal);
            const chip = scannedSummaryEl.closest('.archive-req-chip');
            if (chip) chip.classList.toggle('is-complete', requiredTotal > 0 && scannedRequired >= requiredTotal);
        }
        if (rowSummaryEl) rowSummaryEl.textContent = String(safeRows.length);
        // LIST OF APPLICANTS badge: count every checklist row (incl. optional situational row for Options A/B/C).
        const scannedAll = (payload && payload.scannedCount != null)
            ? Number(payload.scannedCount)
            : safeRows.filter(function (r) { return !!r.scanned; }).length;
        const totalAll = (payload && payload.trackableTotal != null)
            ? Number(payload.trackableTotal)
            : safeRows.length;
        syncArchiveRequirementsButtonSummary(scannedRequired, requiredTotal, scannedAll, totalAll);
        syncArchiveRequirementsListRowStatus(scannedRequired, requiredTotal, scannedAll, totalAll);
        updateArchiveProceedButton(requiredTotal > 0 && scannedRequired >= requiredTotal);
    }

    function updateArchiveProceedButton(canProceed) {
        const proceedBtn = document.getElementById('archiveProceedToEvaluationBtn');
        const hintEl = document.getElementById('archiveProceedHint');
        if (!proceedBtn) return;
        const blacklistBlocked = !!(currentArchiveRequirementsPayload && currentArchiveRequirementsPayload.blacklistBlocked);
        const allowed = !!canProceed && !blacklistBlocked;
        proceedBtn.disabled = !allowed;
        proceedBtn.classList.toggle('is-ready', allowed);
        if (hintEl) {
            if (canProceed) {
                hintEl.textContent = '';
                hintEl.hidden = true;
                hintEl.classList.remove('is-ready');
            } else {
                hintEl.hidden = true;
                hintEl.textContent = '';
                hintEl.classList.remove('is-ready');
            }
        }
    }

    const blacklistRegistryUrl = window.APPLICANTS_CONFIG.blacklistRegistryUrl;

    function showBlacklistProceedBlockedModal(payload, applicantRef) {
        closeArchiveRequirementsModal();
        const data = payload || {};
        const attemptingRef = (applicantRef || data.applicant_reference || data.applicant_reference_number || '').trim();
        const attemptingName = (data.applicant_name || data.applicantName || data.fullName || '').trim();
        const reason = (data.blacklist_reason || data.blacklistReason || '').trim();
        const registryRef = (data.blacklist_registry_ref || data.blacklistRegistryRef || '').trim();
        const registryName = (data.blacklist_registry_name || data.blacklistRegistryName || '').trim();
        const esc = (typeof escapeHtml === 'function') ? escapeHtml : function (s) { return String(s || ''); };

        const attemptBlock = attemptingRef || attemptingName
            ? (
                '<div class="bl-proceed-blocked__attempt">'
                + '<span class="bl-proceed-blocked__attempt-label">Record you tried to promote</span>'
                + (attemptingRef ? ('<span class="bl-proceed-blocked__attempt-ref">' + esc(attemptingRef) + '</span>') : '')
                + (attemptingName ? ('<span class="bl-proceed-blocked__attempt-name">' + esc(attemptingName) + '</span>') : '')
                + '</div>'
            )
            : '';

        const registryLine = registryRef && registryName
            ? ('<code>' + esc(registryRef) + '</code> — ' + esc(registryName))
            : esc(registryName || registryRef || '—');

        showNoticeModal({
            title: 'Cannot proceed — Blacklisted',
            allowHtml: true,
            messageHtml: (
                '<div class="bl-proceed-blocked">'
                + attemptBlock
                + '<p class="bl-proceed-blocked__lead">'
                + 'This applicant cannot move to <strong>Applicant Evaluation and Eligibility</strong> '
                + 'while a matching entry exists on the <strong>Blacklisted Beneficiaries</strong> registry.'
                + '</p>'
                + '<div class="bl-proceed-blocked__registry">'
                + '<span class="bl-proceed-blocked__registry-kicker">Matching registry entry</span>'
                + '<span class="bl-proceed-blocked__registry-line">' + registryLine + '</span>'
                + (reason ? ('<span class="bl-proceed-blocked__reason"><strong>Reason:</strong> ' + esc(reason) + '</span>') : '')
                + '</div>'
                + '<p class="bl-proceed-blocked__note">No proceed SMS was sent. Update or remove the blacklist entry in Units monitoring, then try again.</p>'
                + '<a class="bl-proceed-blocked__link" href="' + esc(blacklistRegistryUrl) + '">Open Blacklisted Beneficiaries registry →</a>'
                + '</div>'
            ),
            type: 'error',
            refPill: '',
            primaryText: 'OK',
        });

        const overlay = document.getElementById('noticeModalOverlay');
        const modal = document.getElementById('noticeModal');
        const bodyEl = document.getElementById('noticeModalBody');
        if (overlay) {
            overlay.classList.add('notice-modal-overlay--top');
            overlay.style.zIndex = '13050';
        }
        if (modal) modal.classList.add('notice-modal--blacklist-blocked');
        if (bodyEl) bodyEl.classList.add('notice-modal-body--blacklist-blocked');
    }

    function logSmsDispatchPlan(flowName, details) {
    }

    function proceedToEvaluationFromArchiveRequirements() {
        const payload = currentArchiveRequirementsPayload;
        if (payload && payload.blacklistBlocked) {
            showBlacklistProceedBlockedModal({
                applicant_name: payload.fullName || '',
                applicant_reference: payload.referenceNumber || '',
                blacklist_reason: payload.blacklistReason || '',
                blacklist_registry_name: payload.blacklistRegistryName || '',
                blacklist_registry_ref: payload.blacklistRegistryRef || '',
                blacklist_blocked: true,
            }, payload.referenceNumber || '');
            return;
        }
        const rows = payload && Array.isArray(payload.rows) ? payload.rows : [];
        const requiredRows = rows.filter(function (r) { return !!r.is_required_for_form; });
        const scannedRequired = requiredRows.filter(function (r) { return !!r.scanned; }).length;
        if (!(requiredRows.length > 0 && scannedRequired === requiredRows.length)) {
            showNoticeModal({
                title: 'Incomplete Requirements',
                message: 'Complete all baseline required documents (R01–R07) before proceeding to Application & Eligibility.',
                type: 'warning',
            });
            return;
        }

        const applicantId = payload && payload.applicantId ? String(payload.applicantId) : '';
        const ref = payload && payload.referenceNumber ? String(payload.referenceNumber) : '';
        if (!applicantId) {
            showNoticeModal({
                title: 'Missing Applicant',
                message: 'Unable to proceed: applicant id is missing in this record.',
                type: 'error',
            });
            return;
        }

        const proceedBtn = document.getElementById('archiveProceedToEvaluationBtn');
        const originalHtml = proceedBtn ? proceedBtn.innerHTML : '';
        if (proceedBtn) {
            proceedBtn.disabled = true;
            proceedBtn.innerHTML = 'Proceeding...';
        }

        const formData = new FormData();
        formData.append('applicant_id', applicantId);
        // This checklist CTA explicitly promotes the archived record into Module 2.
        formData.append('promote_to_module2', '1');
        const csrfEl = document.querySelector('[name=csrfmiddlewaretoken]');
        if (csrfEl) formData.append('csrfmiddlewaretoken', csrfEl.value);
        logSmsDispatchPlan('Proceed to Applicant Evaluation & Eligibility', {
            applicantId: applicantId,
            referenceNumber: ref,
            promoteToModule2: true,
        });

        fetch(window.APPLICANTS_CONFIG.proceedToApplicationsUrl, {
            method: 'POST',
            body: formData
        })
            .then(function (response) {
                return response.json().then(function (data) {
                    return { ok: response.ok, data: data };
                });
            })
            .then(function (result) {
                const data = result.data || {};
                if (!data.success) {
                    if (data.blacklist_blocked || data.blacklistBlocked) {
                        showBlacklistProceedBlockedModal(data, ref);
                        return;
                    }
                    throw new Error(data.error || 'Unable to proceed to Applicant Evaluation & Eligibility.');
                }
                const nextUrl = `${evaluationApplicationsUrl}?applicant_id=${encodeURIComponent(applicantId)}&from=intake_scan_checklist&ref=${encodeURIComponent(ref)}`;
                showNoticeModal({
                    title: 'Proceeded Successfully',
                    messageHtml: buildProceedEvaluationSuccessHtml(payload ? payload.fullName : ''),
                    allowHtml: true,
                    type: 'success',
                    celebration: true,
                    primaryText: 'Continue',
                    onPrimary: function () {
                        window.location.href = nextUrl;
                    },
                });
            })
            .catch(function (error) {
                showNoticeModal({
                    title: 'Proceed Failed',
                    message: error.message || 'Unable to proceed to Applicant Evaluation & Eligibility.',
                    type: 'error',
                });
            })
            .finally(function () {
                if (proceedBtn) {
                    proceedBtn.disabled = false;
                    proceedBtn.innerHTML = originalHtml || 'Proceed to Applicant Evaluation &amp; Eligibility <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"/><path d="m12 5 7 7-7 7"/></svg>';
                }
            });
    }

    function saveArchiveRequirementDoc(applicantId, docKey, isChecked) {
        if (!applicantId || !docKey) return Promise.resolve(false);
        const csrfEl = document.querySelector('[name=csrfmiddlewaretoken]');
        if (!csrfEl) return Promise.resolve(false);

        const formData = new FormData();
        formData.append('csrfmiddlewaretoken', csrfEl.value);
        formData.append('applicant_id', applicantId);
        formData.append('action', 'update_doc');
        formData.append(docKey, isChecked);

        return fetch(window.APPLICANTS_CONFIG.updateApplicantUrl, {
            method: 'POST',
            body: formData
        })
            .then(function (response) { return response.json(); })
            .then(function (data) { return !!data.success; })
            .catch(function (_error) { return false; });
    }

    async function scanAllArchiveRequirementsOneByOne() {
        const payload = currentArchiveRequirementsPayload;
        const rows = payload && Array.isArray(payload.rows) ? payload.rows : [];
        const applicantId = payload ? payload.applicantId : '';
        const referenceNumber = payload ? payload.referenceNumber : '';
        if (!rows.length || !applicantId) {
            showFlowAlert('Unable to scan documents for this applicant.');
            return;
        }

        const pending = rows.filter(function (r) {
            const code = String(r.code || '').toUpperCase();
            return !!r.is_required_for_form && !r.scanned && !!ARCHIVE_DOC_KEY_BY_CODE[code];
        });
        if (!pending.length) {
            updateArchiveRequirementsSummary(rows);
            return;
        }

        setArchiveScanButtonBusy(true);
        try {
            const dwt = await waitForDwtReady();
            if (!dwt) throw new Error('Scanner SDK is not ready yet. Refresh the page and try again.');
            await dwt.SelectSourceAsync();

            for (const row of pending) {
                const code = String(row.code || '').toUpperCase();
                const docKey = ARCHIVE_DOC_KEY_BY_CODE[code];
                await acquireImageWithDwt({ selectSource: false, closeSourceAfterAcquire: false });
                const uploadResult = await uploadCurrentScannedImageForApplicant(applicantId, referenceNumber, docKey, code);

                // Backward-compatible checklist flag sync.
                const isSaved = await saveArchiveRequirementDoc(applicantId, docKey, true);
                if (!isSaved) {
                }

                row.scanned = true;
                if (uploadResult && uploadResult.document_url) row.latest_file_url = uploadResult.document_url;
                if (uploadResult && uploadResult.document_name) row.latest_file_name = uploadResult.document_name;
                row.filed_via = 'scan';
                row.filed_via_label = 'SCANNED';
                renderArchiveRowStatusAndActions(code);
                forceArchiveRowScannedDom(code, uploadResult && uploadResult.document_url ? uploadResult.document_url : '');
                updateArchiveRequirementsSummary(rows);
                await new Promise(function (resolve) { setTimeout(resolve, 120); });
            }
            if (typeof dwt.CloseSource === 'function') {
                try { dwt.CloseSource(); } catch (_err) { }
            }
        } catch (error) {
            showFlowAlert(error.message || 'Unable to scan all documents.', 'Notice', null, 'warning');
        } finally {
            setArchiveScanButtonBusy(false);
        }
    }

    /** Match intake situational-row labels for modal rows (covers stale embedded JSON). */
    function archiveModalIsfSitRowLabel(displacementReason) {
        var dr = String(displacementReason || '').trim();
        if (dr === 'danger_zone') {
            return 'Resident of Danger Zone or Hazard Area Follow-up';
        }
        if (dr === 'ejected') {
            return 'Ejected or Evicted from Prior Residence Follow-up';
        }
        if (dr === 'relocated') {
            return 'Displaced by Government Project or Infrastructure Follow-up';
        }
        return '';
    }

    async function openArchiveRequirementsModal(buttonEl) {
        if (!buttonEl) return;
        let payloadMap = {};
        const scriptEl = document.getElementById('archive-pages-documents-payload');
        if (scriptEl && scriptEl.textContent) {
            try {
                payloadMap = JSON.parse(scriptEl.textContent);
            } catch (_err) {
                payloadMap = {};
            }
        }
        const ref = (buttonEl.dataset && buttonEl.dataset.reference) || '';
        let payload = payloadMap[ref];
        if (payload) {
            payload = await refreshApplicantRequirementScanPayload(payload);
            payloadMap[ref] = payload;
            if (scriptEl) {
                try { scriptEl.textContent = JSON.stringify(payloadMap); } catch (_err) { /* ignore */ }
            }
        }
        currentArchiveRequirementsPayload = payload || null;

        const tbody = document.getElementById('archiveRequirementsTableBody');
        const subtitle = document.getElementById('archiveRequirementsSubtitle');

        if (subtitle) {
            subtitle.textContent = payload && payload.referenceNumber
                ? (payload.referenceNumber + ' • ' + (payload.fullName || ''))
                : ref + ' • —';
        }
        if (!tbody) return;

        renderArchiveRequirementsChecklistTable(payload);
        applyArchiveRequirementsBlacklistState(payload);

        var modalEl = document.getElementById('archiveRequirementsModal');
        if (modalEl) modalEl.classList.add('active');
    }
    window.openArchiveRequirementsModal = openArchiveRequirementsModal;

    document.addEventListener('DOMContentLoaded', function () {
        const archiveReqFileInput = document.getElementById('archiveRequirementFileInput');
        let hasShownVoterRequirementAlert = false;
        let hasShownPropertyRequirementAlert = false;
        if (archiveReqFileInput) {
            archiveReqFileInput.addEventListener('change', handleArchiveRequirementFileSelected);
        }
        const primaryBtn = document.getElementById('noticePrimaryBtn');
        const secondaryBtn = document.getElementById('noticeSecondaryBtn');
        if (primaryBtn) {
            primaryBtn.addEventListener('click', function () {
                const handler = noticePrimaryHandler;
                closeNoticeModal();
                if (typeof handler === 'function') {
                    handler();
                    return;
                }
            });
        }
        if (secondaryBtn) {
            secondaryBtn.addEventListener('click', function () {
                const handler = noticeSecondaryHandler;
                closeNoticeModal();
                if (typeof handler === 'function') handler();
            });
        }
        const displacementSelect = document.querySelector('#addApplicantForm select[name="displacement_reason"]');
        if (displacementSelect) {
            displacementSelect.addEventListener('change', syncRegistrationDisplacementPanels);
        }

        const toggle = document.getElementById('displacementToggle');
        const menu = document.getElementById('displacementMenu');
        const toggleText = document.getElementById('displacementToggleText');
        const items = document.querySelectorAll('.custom-dropdown-item');

        if (toggle && menu && displacementSelect) {
            toggle.addEventListener('click', function (e) {
                e.stopPropagation();
                menu.style.display = menu.style.display === 'none' ? 'flex' : 'none';
            });

            document.addEventListener('click', function (e) {
                if (!menu.contains(e.target) && !toggle.contains(e.target)) {
                    menu.style.display = 'none';
                }
            });

            items.forEach(item => {
                item.addEventListener('click', function () {
                    const val = this.getAttribute('data-value');
                    displacementSelect.value = val;
                    displacementSelect.dispatchEvent(new Event('change'));

                    const titleText = this.querySelector('.tha-layer-title').innerText;
                    toggleText.innerText = titleText;

                    const colors = {
                        'danger_zone': '#b91c1c',
                        'ejected': '#b45309',
                        'relocated': '#047857',
                        'not_abc': '#475569'
                    };
                    toggle.style.borderColor = colors[val] || '#10b981';
                    toggle.style.color = colors[val] || '#064e3b';

                    menu.style.display = 'none';
                });

                item.addEventListener('mouseenter', () => {
                    item.style.backgroundColor = '#f8fafc';
                });
                item.addEventListener('mouseleave', () => {
                    item.style.backgroundColor = 'transparent';
                });
            });
        }
        const voterYes = document.getElementById('voterYes');
        const voterNo = document.getElementById('voterNo');
        if (voterNo) {
            voterNo.addEventListener('change', function () {
                if (!voterNo.checked) return;
                if (!hasShownVoterRequirementAlert) {
                    hasShownVoterRequirementAlert = true;
                    if (typeof window.showFlowAlert === 'function') {
                        window.showFlowAlert(
                            'Applicants must be registered voters in Talisay City before you proceed with registration.',
                            'Office requirement',
                            null,
                            'warning'
                        );
                    } else {
                        window.alert('Office requirement: Applicants must be registered voters in Talisay City before you proceed with registration.');
                    }
                }
                if (voterYes) {
                    voterYes.checked = true;
                    voterYes.dispatchEvent(new Event('change', { bubbles: true }));
                }
            });
        }
        const hasPropertyYes = document.getElementById('hasPropertyYes');
        const hasPropertyNo = document.getElementById('hasPropertyNo');
        const yearsResidingInput = document.getElementById('yearsResiding');
        const monthlyIncomeInput = document.getElementById('monthlyIncome');
        let hasShownResidencyRequirementAlert = false;
        let hasShownIncomeRequirementAlert = false;
        if (hasPropertyYes) {
            hasPropertyYes.addEventListener('change', function () {
                if (!hasPropertyYes.checked) return;
                if (!hasShownPropertyRequirementAlert) {
                    hasShownPropertyRequirementAlert = true;
                    if (typeof window.showFlowAlert === 'function') {
                        window.showFlowAlert(
                            'The office only accepts applicants who do not own property in Talisay City.',
                            'Office requirement',
                            null,
                            'warning'
                        );
                    } else {
                        window.alert('Office requirement: The office only accepts applicants who do not own property in Talisay City.');
                    }
                }
                if (hasPropertyNo) {
                    hasPropertyNo.checked = true;
                    hasPropertyNo.dispatchEvent(new Event('change', { bubbles: true }));
                }
            });
        }
        attachYearsResidingDigitLimit(yearsResidingInput, { minYears: MODULE1_MIN_YEARS_RESIDING });
        const isfEditYearsInput = document.getElementById('isfEditYears');
        attachYearsResidingDigitLimit(isfEditYearsInput, { minYears: 0 });
        if (yearsResidingInput) {
            const enforceResidencyRequirement = function () {
                const raw = String(yearsResidingInput.value || '').trim();
                const years = parseInt(raw, 10);
                const isTooManyDigits = raw !== '' && Number.isFinite(years) && years > MODULE1_MAX_YEARS_RESIDING;
                const isBelowMin = raw !== '' && Number.isFinite(years) && years <= 4;
                if (isTooManyDigits) {
                    yearsResidingInput.setCustomValidity('Years of residence must be at most 2 digits (99).');
                } else if (isBelowMin) {
                    yearsResidingInput.setCustomValidity('Office requirement: Minimum residency is 5 years in Talisay City.');
                    if (!hasShownResidencyRequirementAlert) {
                        hasShownResidencyRequirementAlert = true;
                        if (typeof window.showFlowAlert === 'function') {
                            window.showFlowAlert(
                                'Applicants with 4 years or below residency in Talisay City are not accepted. Minimum is 5 years.',
                                'Office requirement',
                                null,
                                'warning'
                            );
                        } else {
                            window.alert('Office requirement: Applicants with 4 years or below residency in Talisay City are not accepted. Minimum is 5 years.');
                        }
                    }
                } else {
                    yearsResidingInput.setCustomValidity('');
                }
            };
            yearsResidingInput.addEventListener('input', enforceResidencyRequirement);
            yearsResidingInput.addEventListener('change', enforceResidencyRequirement);
        }
        if (monthlyIncomeInput) {
            const enforceIncomeCeilingRequirement = function () {
                const raw = String(monthlyIncomeInput.value || '').replace(/,/g, '').trim();
                const income = parseFloat(raw);
                const isInvalid = raw !== '' && Number.isFinite(income) && income > MODULE1_INCOME_CEILING;
                if (isInvalid) {
                    monthlyIncomeInput.setCustomValidity('Office requirement: Maximum gross monthly household income is PHP 10,000.');
                    if (!hasShownIncomeRequirementAlert) {
                        hasShownIncomeRequirementAlert = true;
                        if (typeof window.showFlowAlert === 'function') {
                            window.showFlowAlert(
                                'Applicants with gross monthly household income above PHP 10,000 are not accepted.',
                                'Office requirement',
                                null,
                                'warning'
                            );
                        } else {
                            window.alert('Office requirement: Applicants with gross monthly household income above PHP 10,000 are not accepted.');
                        }
                    }
                } else {
                    monthlyIncomeInput.setCustomValidity('');
                }
            };
            monthlyIncomeInput.addEventListener('input', enforceIncomeCeilingRequirement);
            monthlyIncomeInput.addEventListener('change', enforceIncomeCeilingRequirement);
        }

        // If an action requested auto-scroll to the Archive section, do it once after reload.
        try {
            if (sessionStorage.getItem('scrollToArchiveSection') === '1') {
                sessionStorage.removeItem('scrollToArchiveSection');
                const target = document.getElementById('archiveSection');
                if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        } catch (_err) {
            // ignore storage errors
        }
    });

    /**
     * Channel B (hazard pathway): the Yes/No answer is stored on dangerZoneType and drives CDRRMO handling.
     * `formatHazardZoneTypeLabel` must stay aligned with `reviewDangerType` option values.
     */
    function formatHazardZoneTypeLabel(raw) {
        if (raw == null || !String(raw).trim()) return '';
        const code = String(raw).trim().toLowerCase().replace(/-/g, '_');
        const map = {
            riverside: 'Riverside / Riverbank',
            flood_prone: 'Flood-Prone Area',
            landslide: 'Landslide-Prone Area',
            storm_surge: 'Storm Surge Zone',
            river_bank: 'River / Creek Bank',
            cliff_edge: 'Cliff Edge',
            coastal: 'Coastal Erosion',
            railroad: 'Near Railroad Tracks',
            road_right_of_way: 'Road Right-of-Way',
            other: 'Other Hazard',
        };
        if (map[code]) return map[code];
        return String(raw).replace(/_/g, ' ').replace(/\b\w/g, function (c) { return c.toUpperCase(); });
    }

    function channelBDisplayLabel(applicant) {
        if (!applicant) return 'Channel B — Hazard pathway (classification pending)';
        const ch = applicant.channel;
        if (ch !== 'B' && ch !== 'danger_zone') return 'Channel B — Hazard pathway (classification pending)';
        const dz = applicant.dangerZoneType || applicant.danger_zone_type;
        const declared = !!(dz && String(dz).trim());
        return declared
            ? 'Channel B — Hazard declaration: affirmative'
            : 'Channel B — Hazard declaration: negative';
    }

    /** Module 1 income rule — must match `Applicant.is_income_eligible` / `update_eligibility` in intake/views.py */
    const MODULE1_INCOME_CEILING = 10000;
    /** Mirror `MODULE1_MIN_YEARS_RESIDING_TALISAY` / `MODULE1_MAX_YEARS_RESIDING_TALISAY` in intake/views.py */
    const MODULE1_MIN_YEARS_RESIDING = 5;
    const MODULE1_MAX_YEARS_RESIDING = 99;

    function attachYearsResidingDigitLimit(inputEl, { minYears = 0 } = {}) {
        if (!inputEl || inputEl.dataset.yearsDigitLimit === '1') return;
        inputEl.dataset.yearsDigitLimit = '1';
        inputEl.setAttribute('inputmode', 'numeric');
        inputEl.setAttribute('maxlength', '2');
        if (minYears > 0) {
            inputEl.setAttribute('min', String(minYears));
        }
        const clampDigits = function () {
            let digits = String(inputEl.value || '').replace(/\D/g, '').slice(0, 2);
            if (digits !== '') {
                let n = parseInt(digits, 10);
                if (n > MODULE1_MAX_YEARS_RESIDING) {
                    n = MODULE1_MAX_YEARS_RESIDING;
                    digits = String(n);
                }
            }
            if (inputEl.value !== digits) {
                inputEl.value = digits;
            }
        };
        inputEl.addEventListener('input', clampDigits);
        inputEl.addEventListener('paste', function (e) {
            e.preventDefault();
            const paste = (e.clipboardData || window.clipboardData).getData('text');
            inputEl.value = String(paste || '').replace(/\D/g, '').slice(0, 2);
            clampDigits();
        });
    }

    function clearLayer2ViolationClasses(scopeRoot) {
        if (!scopeRoot) return;
        scopeRoot.querySelectorAll('.tha-layer2-violation').forEach(function (el) {
            el.classList.remove('tha-layer2-violation');
        });
    }

    function parseMonthlyIncomeLayer2(raw) {
        if (raw == null || raw === '') return NaN;
        if (typeof raw === 'number' && Number.isFinite(raw)) return raw;
        const n = parseFloat(String(raw).replace(/,/g, '').trim());
        return Number.isFinite(n) ? n : NaN;
    }

    function getLayer2ViolationFlags(applicant) {
        if (!applicant) {
            return { income: false, residency: false, voter: false, property: false, any: false };
        }
        const incomeNum = parseMonthlyIncomeLayer2(applicant.monthlyIncome);
        const ceiling = Number(applicant.incomeCeilingPeso) > 0 ? Number(applicant.incomeCeilingPeso) : MODULE1_INCOME_CEILING;
        const incomeViolates = Number.isFinite(incomeNum) && incomeNum > ceiling;

        const years = parseInt(applicant.yearsResiding, 10);
        const yearsNum = Number.isFinite(years) ? years : 0;
        const residencyViolates = yearsNum < MODULE1_MIN_YEARS_RESIDING;

        const voterViolates = !applicant.isRegisteredVoterTalisay;

        const hp = applicant.hasPropertyInTalisay;
        const propertyViolates = hp === true || hp === 'true' || hp === 1;

        const any = !!(incomeViolates || residencyViolates || voterViolates || propertyViolates);
        return {
            income: incomeViolates,
            residency: residencyViolates,
            voter: voterViolates,
            property: propertyViolates,
            any: any,
        };
    }

    function getApplicantSnapshotForLayer2FromDangerZoneForm(baseApplicant) {
        const a = Object.assign({}, baseApplicant || {});
        const incEl = document.getElementById('reviewIncomeB');
        const yrEl = document.getElementById('reviewYearsB');
        const voterEl = document.getElementById('reviewVoterB');
        const propEl = document.getElementById('reviewPropertyB');
        if (incEl && incEl.value !== undefined) {
            const raw = String(incEl.value || '').replace(/,/g, '');
            const n = parseFloat(raw);
            if (Number.isFinite(n)) a.monthlyIncome = n;
        }
        if (yrEl && yrEl.value !== undefined && yrEl.value !== '') {
            const n = parseInt(yrEl.value, 10);
            if (Number.isFinite(n)) a.yearsResiding = n;
        }
        if (voterEl && voterEl.value !== undefined) {
            const v = String(voterEl.value || '').trim().toLowerCase();
            a.isRegisteredVoterTalisay = v === 'yes' || v === 'true' || v === '1';
        }
        if (propEl && propEl.value !== undefined) {
            const v = String(propEl.value || '').trim().toLowerCase();
            a.hasPropertyInTalisay = v === 'yes' || v === 'true' || v === '1';
        }
        return a;
    }

    function applyLayer2ViolationHighlights(applicant, scopeRoot) {
        clearLayer2ViolationClasses(scopeRoot);
        if (!applicant || !scopeRoot) return;
        const flags = getLayer2ViolationFlags(applicant);
        function mark(inputId, violated) {
            const input = document.getElementById(inputId);
            const wrap = input && input.closest('.form-group');
            if (wrap && violated) wrap.classList.add('tha-layer2-violation');
        }
        mark('reviewIncomeB', flags.income);
        mark('reviewVoterB', flags.voter);
        mark('reviewYearsB', flags.residency);
        mark('reviewPropertyB', flags.property);
    }

    function updateReviewModalPolicyAlert(applicant) {
        const shell = document.querySelector('#reviewModal .modal-content.tha-review-modal');
        if (!shell) return;
        const flags = getLayer2ViolationFlags(applicant);
        shell.classList.toggle('tha-review-modal--policy-alert', flags.any);
    }

    /** Recompute red violation boxes from current Channel B form values (live while editing). */
    function refreshLayer2ViolationsFromDangerZoneForm() {
        const dzRoot = document.getElementById('dangerZoneReviewSection');
        if (!dzRoot || !currentApplicant || currentApplicant.channel !== 'B') return;
        const snap = getApplicantSnapshotForLayer2FromDangerZoneForm(currentApplicant);
        applyLayer2ViolationHighlights(snap, dzRoot);
        updateReviewModalPolicyAlert(snap);
    }

    (function bindDangerZoneLayer2LiveListeners() {
        const root = document.getElementById('dangerZoneReviewSection');
        if (!root || root.dataset.thaLayer2LiveBound === '1') return;
        root.dataset.thaLayer2LiveBound = '1';
        const watched = { reviewIncomeB: 1, reviewYearsB: 1, reviewVoterB: 1, reviewPropertyB: 1 };
        function onLayer2Field(ev) {
            const id = ev.target && ev.target.id;
            if (!id || !watched[id]) return;
            refreshLayer2ViolationsFromDangerZoneForm();
        }
        root.addEventListener('input', onLayer2Field);
        root.addEventListener('change', onLayer2Field);
    })();

    function incomeCheckState(applicant) {
        const income = Number(applicant.monthlyIncome) || 0;
        const ceiling = Number(applicant.incomeCeilingPeso) > 0 ? Number(applicant.incomeCeilingPeso) : MODULE1_INCOME_CEILING;
        const pass = typeof applicant.incomeEligible === 'boolean'
            ? applicant.incomeEligible
            : income <= ceiling;
        return { income, ceiling, pass };
    }

    function incomeExceedsCeilingNoticeHtml(pass, income, ceiling) {
        if (pass) return '';
        const amt = '₱' + Number(income).toLocaleString('en-PH', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        const cap = '₱' + Number(ceiling).toLocaleString('en-PH', { minimumFractionDigits: 0, maximumFractionDigits: 0 });
        return `<div style="margin-top:0.5rem;padding:0.625rem 0.75rem;background:#fef2f2;border:1px solid #fecaca;border-radius:0.375rem;font-size:0.8125rem;color:#991b1b;line-height:1.45;">
            <strong>Advisory — income above Module 1 ceiling:</strong> Declared household income is <strong>${amt}</strong>, which exceeds the applicable ceiling of <strong>${cap}</strong>. Eligibility may not be recorded until the declared income is amended on file or the applicant is formally disqualified on stated grounds.
        </div>`;
    }

    function formatIncomeInputValue(rawValue) {
        const numeric = Number.parseFloat(String(rawValue ?? '').replace(/,/g, ''));
        if (Number.isNaN(numeric)) return '';
        return numeric.toLocaleString('en-PH', {
            minimumFractionDigits: 0,
            maximumFractionDigits: 2
        });
    }

    // Format income field with thousands separator on blur (text inputs only)
    function attachIncomeFormatter(input) {
        input.addEventListener('blur', function () {
            if (this.value === '' || this.value === '0') return;

            const numValue = parseFloat(this.value.replace(/,/g, ''));
            if (!isNaN(numValue) && numValue > 0) {
                // Keep number inputs unformatted to avoid browser parse errors (e.g. "7,500")
                if (this.type === 'number') {
                    this.value = String(numValue);
                    return;
                }
                this.value = numValue.toLocaleString('en-PH', {
                    minimumFractionDigits: 0,
                    maximumFractionDigits: 2
                });
            }
        });
    }

    // Format monthly income inline as user types (e.g., 1500 -> 1,500).
    function attachNumberIncomeSanitizer(input) {
        const format = function (rawValue) {
            const cleaned = String(rawValue || '')
                .replace(/[^0-9.]/g, '')
                .replace(/(\..*)\./g, '$1');
            if (!cleaned) return '';

            const parts = cleaned.split('.');
            const whole = parts[0] || '0';
            const decimal = parts[1] !== undefined ? parts[1].slice(0, 2) : '';
            const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
            return decimal !== '' ? `${grouped}.${decimal}` : grouped;
        };

        const sanitize = function () {
            if (typeof this.value !== 'string') return;
            this.value = format(this.value);
        };
        input.addEventListener('input', sanitize);
        input.addEventListener('blur', sanitize);
        if (input.form) {
            input.form.addEventListener('submit', function () {
                input.value = input.value.replace(/,/g, '');
            });
        }
        sanitize.call(input);
    }

    // Toggle collapsible fieldsets
    function toggleFieldset(header) {
        const fieldset = header.closest('.form-fieldset');
        if (fieldset.classList.contains('always-open')) return; // Don't toggle if always-open

        const content = fieldset.querySelector('.form-fieldset-content');
        header.classList.toggle('collapsed');
        content.classList.toggle('collapsed');
    }

    // Initialize income formatters on page load
    const APPLICANTS_TABLE_PAGE_SIZE = 5;
    const ARCHIVE_TABLE_PAGE_SIZE = 10;
    let applicantsCurrentPage = 1;
    let archiveCurrentPage = 1;

    window.addEventListener('DOMContentLoaded', function () {
        /* Flatpickr for #dateOfBirth / #registrationEjectionDate: init in openAddModal only. */
        // Attach only to text-like income fields. Number inputs must stay plain numeric.
        document.querySelectorAll('.form-input[name*="income"]:not([type="number"]), input[id*="Income"]:not([type="number"])').forEach(attachIncomeFormatter);
        document.querySelectorAll('.js-open-review').forEach(btn => {
            btn.addEventListener('click', function () {
                const idx = Number(this.dataset.applicantIndex);
                if (!Number.isNaN(idx)) openReviewModal(idx);
            });
        });
        document.querySelectorAll('.js-open-archive-review').forEach(btn => {
            btn.addEventListener('click', function () {
                openArchiveReviewModal(this);
            });
        });
        initializeTablePagination();
        const params = new URLSearchParams(window.location.search);
        if (params.get('q') && document.getElementById('searchInput')) {
    const searchInput = document.getElementById('searchInput');
    if (searchInput) searchInput.value = params.get('q') || '';
        }
        if (params.get('archive_q') && document.getElementById('archiveSearchInput')) {
    const archiveSearchInput = document.getElementById('archiveSearchInput');
    if (archiveSearchInput) archiveSearchInput.value = params.get('archive_q') || '';
        }
        filterTable(true);
    });

    document.getElementById('activeApplicantsSearchForm')?.addEventListener('submit', function () {
        const pageInput = this.querySelector('input[name="page"]');
        if (pageInput) pageInput.remove();
    });
    document.getElementById('archiveListSearchForm')?.addEventListener('submit', function () {
        const pageInput = this.querySelector('input[name="page"]');
        if (pageInput) pageInput.remove();
    });

    function initializeTablePagination() {
        const applicantsPrevBtn = document.getElementById('applicantsPrevBtn');
        const applicantsNextBtn = document.getElementById('applicantsNextBtn');
        const archivePrevBtn = document.getElementById('archivePrevBtn');
        const archiveNextBtn = document.getElementById('archiveNextBtn');

        if (applicantsPrevBtn) {
            applicantsPrevBtn.addEventListener('click', function () {
                if (applicantsCurrentPage > 1) {
                    applicantsCurrentPage -= 1;
                    filterTable(false);
                }
            });
        }

        if (applicantsNextBtn) {
            applicantsNextBtn.addEventListener('click', function () {
                const rows = getFilteredApplicantRows();
                const totalPages = Math.max(1, Math.ceil(rows.length / APPLICANTS_TABLE_PAGE_SIZE));
                if (applicantsCurrentPage < totalPages) {
                    applicantsCurrentPage += 1;
                    filterTable(false);
                }
            });
        }

        if (archivePrevBtn) {
            archivePrevBtn.addEventListener('click', function () {
                if (archiveCurrentPage > 1) {
                    archiveCurrentPage -= 1;
                    filterArchiveTable(false);
                }
            });
        }

        if (archiveNextBtn) {
            archiveNextBtn.addEventListener('click', function () {
                const filteredRows = getFilteredArchiveRows();
                const totalPages = Math.max(1, Math.ceil(filteredRows.length / ARCHIVE_TABLE_PAGE_SIZE));
                if (archiveCurrentPage < totalPages) {
                    archiveCurrentPage += 1;
                    filterArchiveTable(false);
                }
            });
        }

        filterArchiveTable(true);
    }

    function getFilteredApplicantRows() {
        const searchInputEl = document.getElementById('searchInput');
        const channelFilterEl = document.getElementById('filterChannel');
        const barangayFilterEl = document.getElementById('filterBarangay');

        const searchValue = searchInputEl ? searchInputEl.value.toLowerCase() : '';
        const channelFilter = channelFilterEl ? channelFilterEl.value : 'all';
        const barangayFilter = barangayFilterEl ? barangayFilterEl.value : 'all';
        const rows = Array.from(document.querySelectorAll('#applicantsTableBody tr'));

        return rows.filter(row => {
            const channel = row.dataset.channel;
            const barangay = row.dataset.barangay;
            const searchable = row.dataset.searchable;

            const matchSearch = searchValue === '' || (searchable && searchable.includes(searchValue));
            const matchChannel = channelFilter === 'all' || channel === channelFilter;
            const matchBarangay = barangayFilter === 'all' || barangay === barangayFilter;
            return matchSearch && matchChannel && matchBarangay;
        });
    }

    function getFilteredArchiveRows() {
        const searchInputEl = document.getElementById('archiveSearchInput');
        const channelFilterEl = document.getElementById('archiveFilterChannel');
        const barangayFilterEl = document.getElementById('archiveFilterBarangay');

        const searchValue = searchInputEl ? searchInputEl.value.toLowerCase() : '';
        const channelFilter = channelFilterEl ? channelFilterEl.value : 'all';
        const barangayFilter = barangayFilterEl ? barangayFilterEl.value : 'all';
        const rows = Array.from(document.querySelectorAll('#archiveTableBody tr[data-archive-row="true"]'));

        return rows.filter(row => {
            const channel = row.dataset.channel;
            const barangay = row.dataset.barangay;
            const searchable = row.dataset.searchable;

            const matchSearch = searchValue === '' || (searchable && searchable.includes(searchValue));
            const matchChannel = channelFilter === 'all' || channel === channelFilter;
            const matchBarangay = barangayFilter === 'all' || barangay === barangayFilter;
            return matchSearch && matchChannel && matchBarangay;
        });
    }

    function updatePaginationUI(prefix, totalRows, currentPage, totalPages, start, end) {
        const infoEl = document.getElementById(`${prefix}PaginationInfo`);
        const indicatorEl = document.getElementById(`${prefix}PageIndicator`);
        const prevBtn = document.getElementById(`${prefix}PrevBtn`);
        const nextBtn = document.getElementById(`${prefix}NextBtn`);

        if (infoEl) {
            infoEl.textContent = totalRows === 0
                ? 'Showing 0-0 of 0'
                : `Showing ${start}-${end} of ${totalRows}`;
        }
        if (indicatorEl) indicatorEl.textContent = `Page ${currentPage} of ${totalPages}`;
        if (prevBtn) prevBtn.disabled = currentPage <= 1 || totalRows === 0;
        if (nextBtn) nextBtn.disabled = currentPage >= totalPages || totalRows === 0;
    }

    // Table filtering + pagination
    function filterTable(resetPage = true) {
        if (resetPage) applicantsCurrentPage = 1;

        const allRows = Array.from(document.querySelectorAll('#applicantsTableBody tr'));
        const filteredRows = getFilteredApplicantRows();
        const totalRows = filteredRows.length;
        const totalPages = Math.max(1, Math.ceil(totalRows / APPLICANTS_TABLE_PAGE_SIZE));
        applicantsCurrentPage = Math.min(applicantsCurrentPage, totalPages);

        const startIndex = (applicantsCurrentPage - 1) * APPLICANTS_TABLE_PAGE_SIZE;
        const endIndex = startIndex + APPLICANTS_TABLE_PAGE_SIZE;
        const rowsOnPage = filteredRows.slice(startIndex, endIndex);

        allRows.forEach(row => {
            if (rowsOnPage.includes(row)) {
                row.style.display = '';
            } else {
                row.style.display = 'none';
            }
        });

        rowsOnPage.forEach((row, index) => {
            const firstTd = row.querySelector('td:first-child');
            if (firstTd) firstTd.textContent = startIndex + index + 1;
        });

        const displayStart = totalRows === 0 ? 0 : startIndex + 1;
        const displayEnd = totalRows === 0 ? 0 : Math.min(endIndex, totalRows);
        updatePaginationUI('applicants', totalRows, applicantsCurrentPage, totalPages, displayStart, displayEnd);
    }

    function filterArchiveTable(resetPage = true) {
        if (resetPage) archiveCurrentPage = 1;
        const archiveRows = Array.from(document.querySelectorAll('#archiveTableBody tr[data-archive-row="true"]'));
        const filteredRows = getFilteredArchiveRows();
        renderArchiveTablePage(archiveRows, filteredRows);
    }

    function renderArchiveTablePage(allArchiveRows, filteredArchiveRows) {
        const archiveRows = allArchiveRows || Array.from(document.querySelectorAll('#archiveTableBody tr[data-archive-row="true"]'));
        const filteredRows = filteredArchiveRows || getFilteredArchiveRows();
        const archiveEmptyRow = document.getElementById('archiveEmptyRow');
        const archiveTotalCountEl = document.getElementById('archiveTotalCount');
        const totalRows = filteredRows.length;
        const totalPages = Math.max(1, Math.ceil(totalRows / ARCHIVE_TABLE_PAGE_SIZE));
        archiveCurrentPage = Math.min(archiveCurrentPage, totalPages);

        const startIndex = (archiveCurrentPage - 1) * ARCHIVE_TABLE_PAGE_SIZE;
        const endIndex = startIndex + ARCHIVE_TABLE_PAGE_SIZE;
        const rowsOnPage = filteredRows.slice(startIndex, endIndex);

        archiveRows.forEach(row => {
            if (rowsOnPage.includes(row)) {
                row.style.display = '';
            } else {
                row.style.display = 'none';
            }
        });

        rowsOnPage.forEach((row, index) => {
            const firstTd = row.querySelector('td:first-child');
            if (firstTd) firstTd.textContent = startIndex + index + 1;
        });

        if (archiveEmptyRow) {
            archiveEmptyRow.style.display = totalRows === 0 ? '' : 'none';
        }
        if (archiveTotalCountEl) {
            archiveTotalCountEl.textContent = String(totalRows);
        }
        const displayStart = totalRows === 0 ? 0 : startIndex + 1;
        const displayEnd = totalRows === 0 ? 0 : Math.min(endIndex, totalRows);
        updatePaginationUI('archive', totalRows, archiveCurrentPage, totalPages, displayStart, displayEnd);
    }

    // ====== REVIEW MODAL ======
    let currentApplicant = null;
    let isEditMode = false;

    function canReviewApplicantIndex(index) {
        if (FIRST_REVIEW_INDEX < 0) return false;
        return Number(index) === FIRST_REVIEW_INDEX;
    }

    function populateReviewModalFromApplicant(applicant) {
        if (!applicant) {
            showFlowAlert('Error: No applicant data found.');
            return;
        }
        currentApplicant = applicant;

        const modal = document.getElementById('reviewModal');
        if (!modal) {
            showFlowAlert('Error: Modal not found in page.');
            return;
        }

        // Set header info (with null checks)
        const reviewNameEl = document.getElementById('reviewName');
        const reviewRefEl = document.getElementById('reviewReference');
        const reviewApplicantIdEl = document.getElementById('reviewApplicantId');
        const reviewChannelEl = document.getElementById('reviewChannel');

        if (reviewNameEl) reviewNameEl.textContent = currentApplicant.fullName;
        if (reviewRefEl) {
            const regLabel = currentApplicant.isArchived ? 'Proceeded' : 'Reg.';
            reviewRefEl.textContent = `${currentApplicant.referenceNumber} · ${regLabel} ${currentApplicant.dateRegistered}`;
        }
        if (reviewApplicantIdEl) reviewApplicantIdEl.value = currentApplicant.applicantId || currentApplicant.id;
        if (reviewChannelEl) reviewChannelEl.value = currentApplicant.channel;

        // Channel labels with differentiation for Channel A
        function getChannelLabel(applicant) {
            if (applicant.channel === 'A') {
                return applicant.channelSource === 'staff_entry'
                    ? 'Channel A — Staff Entry'
                    : 'Channel A — Landowner Portal';
            } else if (applicant.channel === 'B') {
                return channelBDisplayLabel(applicant);
            } else if (applicant.channel === 'C') {
                return 'Channel C — Walk-in';
            }
            return 'Unknown Channel';
        }

        // Hide all sections first (with null checks)
        const dangerZoneSection = document.getElementById('dangerZoneReviewSection');
        const walkinSection = document.getElementById('walkinReviewSection');

        if (dangerZoneSection) dangerZoneSection.style.display = 'none';
        if (walkinSection) walkinSection.style.display = 'none';

        // Show appropriate section based on channel
        if (currentApplicant.channel === 'C') {
            // Channel C: Regular Walk-in
            if (walkinSection) walkinSection.style.display = 'block';

            const eligBadge = document.getElementById('reviewEligibilityBadge');
            if (eligBadge) {
                eligBadge.textContent = currentApplicant.eligibilityStatus;
                const eligClass = currentApplicant.eligibilityStatus === 'Eligible' ? 'success' :
                    currentApplicant.eligibilityStatus === 'Disqualified' ? 'danger' : 'warning';
                eligBadge.className = 'status-badge status-' + eligClass;
            }

            const queueBadge = document.getElementById('reviewQueueBadge');
            if (queueBadge) {
                if (currentApplicant.queueType && currentApplicant.queueType !== 'None') {
                    queueBadge.style.display = 'inline-flex';
                    queueBadge.textContent = currentApplicant.queueType + (currentApplicant.queuePosition ? ' #' + currentApplicant.queuePosition : '');
                    queueBadge.className = 'status-badge status-info';
                } else {
                    queueBadge.style.display = 'none';
                }
            }

            // Populate Channel C form fields (with null checks)
            const sexEl = document.getElementById('reviewSex');
            const civilStatusEl = document.getElementById('reviewCivilStatus');
            const ageEl = document.getElementById('reviewAge');
            const dobEl = document.getElementById('reviewDateOfBirth');
            const barangayEl = document.getElementById('reviewBarangay');
            const incomeEl = document.getElementById('reviewIncome');
            const householdEl = document.getElementById('reviewHousehold');
            const yearsEl = document.getElementById('reviewYears');
            const phoneEl = document.getElementById('reviewPhone');
            const addressEl = document.getElementById('reviewAddress');
            const dangerZoneStatusEl = document.getElementById('reviewDangerZoneStatus');
            const occupationEl = document.getElementById('reviewOccupation');
            const employmentStatusEl = document.getElementById('reviewEmploymentStatus');

            // Parse fullName into Last, First, Middle
            const lastNameEl = document.getElementById('reviewLastName');
            const firstNameEl = document.getElementById('reviewFirstName');
            const middleNameEl = document.getElementById('reviewMiddleName');
            const extensionNameEl = document.getElementById('reviewExtensionName');

            if (lastNameEl || firstNameEl || middleNameEl || extensionNameEl) {
                if (lastNameEl) lastNameEl.value = currentApplicant.lastName || '';
                if (firstNameEl) firstNameEl.value = currentApplicant.firstName || '';
                if (middleNameEl) middleNameEl.value = currentApplicant.middleName || '';
                if (extensionNameEl) extensionNameEl.value = currentApplicant.extensionName || '';
            }

            // Populate all fields
            if (sexEl) sexEl.value = currentApplicant.sex === 'M' ? 'Male' : currentApplicant.sex === 'F' ? 'Female' : (currentApplicant.sex || '');
            if (civilStatusEl) civilStatusEl.value = currentApplicant.civilStatus || '';
            if (ageEl) ageEl.value = currentApplicant.age ?? '';
            if (dobEl) dobEl.value = currentApplicant.dateOfBirth || '';
            if (barangayEl) barangayEl.value = currentApplicant.barangay || '';
            const barangayDisplayEl = document.getElementById('reviewBarangayDisplay');
            if (barangayDisplayEl) barangayDisplayEl.textContent = currentApplicant.barangay || '—';
            if (incomeEl) incomeEl.value = formatIncomeInputValue(currentApplicant.monthlyIncome);
            if (householdEl) householdEl.value = currentApplicant.householdSize || '';
            if (yearsEl) yearsEl.value = currentApplicant.yearsResiding || '';
            if (phoneEl) phoneEl.value = currentApplicant.phoneNumber || '';
            if (addressEl) addressEl.value = currentApplicant.currentAddress || '';
            if (occupationEl) occupationEl.value = currentApplicant.occupation || '';
            if (employmentStatusEl) employmentStatusEl.value = currentApplicant.employmentStatus || '';

            // Populate danger zone status
            if (dangerZoneStatusEl) {
                dangerZoneStatusEl.textContent = currentApplicant.isInDangerZone ? '✓ Yes — In Danger Zone' : '✓ No — Not in Danger Zone';
                dangerZoneStatusEl.style.color = currentApplicant.isInDangerZone ? '#dc2626' : '#10b981';
            }

            // Populate household members list
            const householdListEl = document.getElementById('reviewHouseholdList');
            if (householdListEl && currentApplicant.householdMembers && currentApplicant.householdMembers.length > 0) {
                let membersHTML = '<div style="display: grid; gap: 0.75rem;">';
                currentApplicant.householdMembers.forEach((member, idx) => {
                    membersHTML += `
                            <div style="padding: 0.75rem; background: #f9fafb; border-left: 3px solid #3b82f6; border-radius: 0.375rem;">
                                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.5rem; font-size: 0.875rem;">
                                    <div><strong>Name:</strong> ${member.name || '-'}</div>
                                    <div><strong>Relationship:</strong> ${member.relationship || '-'}</div>
                                    <div><strong>Age:</strong> ${member.age || '-'}</div>
                                    <div><strong>Civil Status:</strong> ${member.civilStatus || '-'}</div>
                                </div>
                            </div>
                        `;
                });
                membersHTML += '</div>';
                householdListEl.innerHTML = membersHTML;
            }

            // Populate eligibility checks
            populateEligibilityChecks(currentApplicant);

            // Lot assignment
            const lotSection = document.getElementById('lotAssignmentSection');
            const lotDetails = document.getElementById('lotDetails');
            if (lotSection && lotDetails) {
                if (currentApplicant.lotAssignment) {
                    lotSection.style.display = 'block';
                    lotDetails.innerHTML = `
                            <strong>Block ${currentApplicant.lotAssignment.block}, Lot ${currentApplicant.lotAssignment.lot}</strong> — ${currentApplicant.lotAssignment.site}<br>
                            Awarded: ${currentApplicant.lotAssignment.dateAwarded}
                        `;
                } else {
                    lotSection.style.display = 'none';
                }
            }
        } else if (currentApplicant.channel === 'B') {
            // Channel B: Danger Zone
            if (dangerZoneSection) dangerZoneSection.style.display = 'block';
            if (walkinSection) walkinSection.style.display = 'none';

            // Set eligibility badge based on danger zone status
            const eligBadgeB = document.getElementById('reviewEligibilityBadgeB');
            if (eligBadgeB) {
                if (currentApplicant.isInDangerZone) {
                    eligBadgeB.className = 'status-badge status-warning';
                    eligBadgeB.textContent = 'Awaiting CDRRMO field certification';
                } else {
                    eligBadgeB.className = 'status-badge status-success';
                    eligBadgeB.textContent = 'No CDRRMO certification required';
                }
            }

            const channelBadgeB = document.getElementById('reviewChannelBadge');
            if (channelBadgeB) {
                channelBadgeB.className = 'status-badge status-info';
                const declared = !!(currentApplicant.dangerZoneType && String(currentApplicant.dangerZoneType).trim());
                channelBadgeB.style.background = declared ? '#fef3c7' : '#e0f2fe';
                channelBadgeB.style.color = declared ? '#92400e' : '#0369a1';
                channelBadgeB.style.border = declared ? '1px solid #fcd34d' : '1px solid #0ea5e9';
                channelBadgeB.textContent = channelBDisplayLabel(currentApplicant);
            }

            const queueBadgeB = document.getElementById('reviewQueueBadgeB');
            if (queueBadgeB) {
                if (currentApplicant.queueType && currentApplicant.queueType !== 'None') {
                    queueBadgeB.style.display = 'inline-flex';
                    queueBadgeB.textContent = currentApplicant.queueType + (currentApplicant.queuePosition ? ' #' + currentApplicant.queuePosition : '');
                    queueBadgeB.className = 'status-badge status-info';
                } else {
                    queueBadgeB.style.display = 'inline-flex';
                    queueBadgeB.className = 'status-badge';
                    queueBadgeB.style.background = '#f1f5f9';
                    queueBadgeB.style.color = '#64748b';
                    queueBadgeB.style.border = '1px solid #e2e8f0';
                    queueBadgeB.textContent = 'No queue assignment';
                }
            }

            // Populate Channel B form fields (with null checks)
            const fullNameBEl = document.getElementById('reviewFullNameB');
            const barangayBEl = document.getElementById('reviewBarangayB');
            const incomeBEl = document.getElementById('reviewIncomeB');
            const householdBEl = document.getElementById('reviewHouseholdB');
            const yearsBEl = document.getElementById('reviewYearsB');
            const phoneBEl = document.getElementById('reviewPhoneB');
            const addressBEl = document.getElementById('reviewAddressB');
            const dangerTypeEl = document.getElementById('reviewDangerType');
            const dangerLocEl = document.getElementById('reviewDangerLocation');

            if (fullNameBEl) fullNameBEl.value = currentApplicant.fullName || '';
            if (barangayBEl) barangayBEl.value = currentApplicant.barangay || '';
            const barangayBDisplayEl = document.getElementById('reviewBarangayBDisplay');
            if (barangayBDisplayEl) barangayBDisplayEl.textContent = currentApplicant.barangay || '—';
            if (incomeBEl) incomeBEl.value = formatIncomeInputValue(currentApplicant.monthlyIncome);
            if (householdBEl) householdBEl.value = currentApplicant.householdSize || '';
            if (yearsBEl) yearsBEl.value = currentApplicant.yearsResiding || '';
            if (phoneBEl) phoneBEl.value = currentApplicant.phoneNumber || '';
            if (addressBEl) addressBEl.value = currentApplicant.currentAddress || '';
            if (dangerTypeEl) dangerTypeEl.value = currentApplicant.dangerZoneType || '';
            if (dangerLocEl) dangerLocEl.value = currentApplicant.dangerZoneLocation || '';

            // Mirror Registration Sheet identity / household / income fields (read-only)
            populateChannelBRegistrationMirror(currentApplicant);
            applyLayer2ViolationHighlights(currentApplicant, dangerZoneSection);
            updateReviewModalPolicyAlert(currentApplicant);

            // CDRRMO summary strip — only while disposition is still pending (final UI from populateCdrrmoSection)
            const cdrrmoBox = document.getElementById('cdrrmoStatusBox');
            const cdrrmoText = document.getElementById('cdrrmoStatusText');
            if (cdrrmoBox && cdrrmoText && currentApplicant.cdrrmo_status === 'pending') {
                const daysPending = currentApplicant.cdrrmoDaysPending || 0;
                const isOverdue = currentApplicant.isCdrrmoFlagged;
                if (isOverdue) {
                    cdrrmoBox.style.background = '#fef2f2';
                    cdrrmoBox.style.borderColor = '#fca5a5';
                    cdrrmoText.style.color = '#dc2626';
                    cdrrmoText.innerHTML = `<strong>Follow-up required: certification overdue</strong><br>CDRRMO disposition has remained pending for <strong>${daysPending}</strong> calendar days (exceeds the fourteen-day monitoring reference). Coordinate with CDRRMO or intake as appropriate.`;
                } else {
                    cdrrmoBox.style.background = '#fef3c7';
                    cdrrmoBox.style.borderColor = '#fcd34d';
                    cdrrmoText.style.color = '#92400e';
                    cdrrmoText.innerHTML = `<strong>Awaiting CDRRMO disposition</strong> (${daysPending} day(s) on record)<br>A field inspection report or official CDRRMO paperwork filed at intake is still required.`;
                }
            }

            // Populate eligibility checks for Channel B
            const isInDangerZoneB = currentApplicant.dangerZoneType ? true : false;
            populateEligibilityChecksB(currentApplicant, isInDangerZoneB);

            // Populate Applicant Situation (D. section)
            const situationCard = document.getElementById('reviewApplicantSituationCard');
            const situationIcon = document.getElementById('situationIcon');
            const situationLabel = document.getElementById('reviewSituationLabel');
            const situationDesc = document.getElementById('reviewSituationDescription');
            const displacementReason = currentApplicant.displacementReason || '';

            if (situationLabel && situationDesc) {
                if (displacementReason === 'danger_zone') {
                    situationLabel.textContent = 'Option A: Resident of Danger Zone or Hazard Area';
                    situationDesc.textContent = 'Applicant resides in a flood-prone, landslide, storm-surge, riverbank, cliff-edge, or coastal hazard area requiring relocation for safety.';
                } else if (displacementReason === 'ejected') {
                    situationLabel.textContent = 'Option B: Ejected or Evicted from Prior Residence';
                    situationDesc.textContent = 'Applicant has been evicted or displaced through private land eviction, court order, landowner recovery, or analogous proceedings.';
                } else if (displacementReason === 'relocated') {
                    situationLabel.textContent = 'Option C: Displaced by Government Project or Infrastructure';
                    situationDesc.textContent = 'Applicant is required to relocate due to a road-widening, drainage, infrastructure, or other government-initiated project.';
                } else if (displacementReason === 'not_abc') {
                    situationLabel.textContent = 'Option D';
                    situationDesc.textContent = 'The situation does not fall under a hazard area, ejection, or a government project.';
                } else {
                    situationLabel.textContent = '—';
                    situationDesc.textContent = 'Applicant situation not recorded.';
                }
            }

            // Color-code Applicant Situation card by selected option (A/B/C/D)
            const situationTheme = {
                danger_zone: {
                    cardBg: 'linear-gradient(135deg, #fef2f2 0%, #fff7ed 100%)',
                    cardBorder: '#fecaca',
                    iconBg: '#fee2e2',
                    labelColor: '#b91c1c',
                    descColor: '#7f1d1d',
                },
                ejected: {
                    cardBg: 'linear-gradient(135deg, #fff7ed 0%, #fffbeb 100%)',
                    cardBorder: '#fdba74',
                    iconBg: '#ffedd5',
                    labelColor: '#b45309',
                    descColor: '#9a3412',
                },
                relocated: {
                    cardBg: 'linear-gradient(135deg, #f0fdf4 0%, #ecfeff 100%)',
                    cardBorder: '#86efac',
                    iconBg: '#dcfce7',
                    labelColor: '#047857',
                    descColor: '#065f46',
                },
                not_abc: {
                    cardBg: 'linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%)',
                    cardBorder: '#cbd5e1',
                    iconBg: '#e2e8f0',
                    labelColor: '#475569',
                    descColor: '#334155',
                },
                default: {
                    cardBg: 'linear-gradient(135deg, #f0f9ff 0%, #f1f5f9 100%)',
                    cardBorder: '#cbd5e1',
                    iconBg: '#e0f2fe',
                    labelColor: '#1e293b',
                    descColor: '#475569',
                },
            };

            const appliedTheme = situationTheme[displacementReason] || situationTheme.default;
            if (situationCard) {
                situationCard.style.background = appliedTheme.cardBg;
                situationCard.style.borderColor = appliedTheme.cardBorder;
            }
            if (situationIcon) {
                situationIcon.style.background = appliedTheme.iconBg;
            }
            if (situationLabel) {
                situationLabel.style.color = appliedTheme.labelColor;
            }
            if (situationDesc) {
                situationDesc.style.color = appliedTheme.descColor;
            }

            // Show/hide danger zone sections based on displacement reason
            const dangerZoneInfoSection = document.querySelector('.danger-zone-info');
            const ejectionInfoSection = document.querySelector('.ejection-info');
            const projectInfoSection = document.querySelector('.project-info');

            // Hide all sections first
            if (dangerZoneInfoSection) dangerZoneInfoSection.style.display = 'none';
            if (ejectionInfoSection) ejectionInfoSection.style.display = 'none';
            if (projectInfoSection) projectInfoSection.style.display = 'none';

            // Show/hide danger zone sections based on displacement reason
            if (displacementReason === 'danger_zone') {
                if (dangerZoneInfoSection) dangerZoneInfoSection.style.display = 'block';
                // Populate danger zone fields
                const dangerTypeEl = document.getElementById('reviewDangerType');
                const dangerLocEl = document.getElementById('reviewDangerLocation');
                if (dangerTypeEl) dangerTypeEl.value = currentApplicant.dangerZoneType || '';
                if (dangerLocEl) dangerLocEl.value = currentApplicant.dangerZoneLocation || '';
            } else if (displacementReason === 'ejected') {
                if (ejectionInfoSection) ejectionInfoSection.style.display = 'block';
                // Populate ejection fields
                const ejectionTypeEl = document.getElementById('reviewEjectionType');
                const ejectionDateEl = document.getElementById('reviewEjectionDate');
                if (ejectionTypeEl) ejectionTypeEl.value = currentApplicant.ejectionType || '';
                if (ejectionDateEl) ejectionDateEl.value = currentApplicant.ejectionDate || '';
            } else if (displacementReason === 'relocated') {
                if (projectInfoSection) projectInfoSection.style.display = 'block';
                // Populate project fields
                const projectNameEl = document.getElementById('reviewProjectName');
                if (projectNameEl) projectNameEl.value = currentApplicant.projectName || '';
            }
            // For Option D (not_abc): no additional sections shown

        } else {
            // Unknown channel - show Channel C section as fallback with error message
            if (walkinSection) walkinSection.style.display = 'block';
        }

        // Show/hide action buttons based on status
        updateActionButtons(currentApplicant);

        // Reset edit mode
        isEditMode = false;
        updateEditModeUI();

        modal.classList.add('active');
    }

    function openReviewModal(index) {
        try {
            if (!canReviewApplicantIndex(index)) {
                showNoticeModal({
                    title: 'FIFO Review Order',
                    message: 'Please review and proceed applicant #1 first. The next applicant unlocks automatically after the first is completed.',
                    type: 'warning',
                    primaryText: 'Understood',
                });
                return;
            }
            reviewModalArchiveMode = false;
            populateReviewModalFromApplicant(applicantsData[index]);
        } catch (error) {
            showFlowAlert('Error opening modal: ' + error.message + '\n\nCheck browser console (F12) for details.');
        }
    }

    function openArchiveReviewModal(buttonEl) {
        try {
            const ref = String(buttonEl?.dataset?.reference || '').trim();
            const applicant = ref ? archiveReviewData[ref] : null;
            if (!applicant) {
                showNoticeModal({
                    title: 'Record Unavailable',
                    message: 'Unable to load this applicant for review.',
                    type: 'warning',
                });
                return;
            }
            reviewModalArchiveMode = true;
            populateReviewModalFromApplicant(applicant);
        } catch (error) {
            showFlowAlert('Error opening modal: ' + error.message);
        }
    }
    window.openArchiveReviewModal = openArchiveReviewModal;

    function populateISFList(applicant) {
        const container = document.getElementById('isfListContainer');
        const isfId = applicant.id || applicant.applicantId;
        const statusClass = applicant.eligibilityStatus === 'Eligible' ? 'success' :
            applicant.eligibilityStatus === 'Disqualified' ? 'danger' : 'warning';
        const { income, pass: incomePass } = incomeCheckState(applicant);

        // Compact ISF card
        container.innerHTML = `
            <div class="isf-review-card" data-isf-id="${isfId}" style="background: white; border: 1px solid #e2e8f0; border-radius: 0.5rem; overflow: hidden;">
                <!-- Header -->
                <div style="background: #f1f5f9; padding: 0.375rem 0.75rem; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #e2e8f0;">
                    <span style="font-size: 0.75rem; color: #64748b;">${applicant.referenceNumber}</span>
                    <span class="status-badge status-${statusClass}" style="font-size: 0.625rem; padding: 0.125rem 0.5rem;">${applicant.eligibilityStatus}</span>
                </div>
                
                <!-- Compact Fields -->
                <div style="padding: 0.5rem 0.75rem; display: grid; grid-template-columns: 1fr 1fr; gap: 0.375rem; font-size: 0.75rem;">
                    <div style="grid-column: span 2;">
                        <label style="color: #64748b; font-size: 0.625rem; text-transform: uppercase;">Name</label>
                        <input type="text" class="form-input isf-field" name="isf_name_${isfId}" value="${applicant.fullName || ''}" ${isEditMode ? '' : 'readonly'} style="padding: 0.25rem 0.5rem; font-size: 0.75rem;">
                    </div>
                    <div>
                        <label style="color: #64748b; font-size: 0.625rem; text-transform: uppercase;">Income (₱)</label>
                        <input type="number" class="form-input isf-field" name="isf_income_${isfId}" value="${income}" min="0" ${isEditMode ? '' : 'readonly'} style="padding: 0.25rem 0.5rem; font-size: 0.75rem;">
                    </div>
                    <div>
                        <label style="color: #64748b; font-size: 0.625rem; text-transform: uppercase;">Household</label>
                        <input type="number" class="form-input isf-field" name="isf_household_${isfId}" value="${applicant.householdSize || 1}" min="1" ${isEditMode ? '' : 'readonly'} style="padding: 0.25rem 0.5rem; font-size: 0.75rem;">
                    </div>
                    <div>
                        <label style="color: #64748b; font-size: 0.625rem; text-transform: uppercase;">Years</label>
                        <input type="number" class="form-input isf-field" name="isf_years_${isfId}" value="${applicant.yearsResiding || 0}" min="0" ${isEditMode ? '' : 'readonly'} style="padding: 0.25rem 0.5rem; font-size: 0.75rem;">
                    </div>
                    <div>
                        <label style="color: #64748b; font-size: 0.625rem; text-transform: uppercase;">Barangay</label>
                        <input type="text" class="form-input isf-field" name="isf_barangay_${isfId}" value="${applicant.barangay || ''}" ${isEditMode ? '' : 'readonly'} style="padding: 0.25rem 0.5rem; font-size: 0.75rem;">
                    </div>
                </div>
                
                <!-- Compact Footer: Eligibility + Actions -->
                <div style="background: #f8fafc; padding: 0.375rem 0.75rem; border-top: 1px solid #e2e8f0; display: flex; justify-content: space-between; align-items: center;">
                    <div style="display: flex; gap: 0.5rem; font-size: 0.625rem;">
                        <span style="color: ${incomePass ? '#16a34a' : '#dc2626'};">${incomePass ? '✓' : '✗'} ≤₱10k</span>
                        <span style="color: #16a34a;">✓ No property</span>
                        <span style="color: #16a34a;">✓ Not blacklisted</span>
                    </div>
                    ${(applicant.eligibilityStatus === 'Pending' || applicant.eligibilityStatus === 'Pending eligibility check') ? `
                        <div style="display: flex; gap: 0.25rem;">
                            <button type="button" onclick="markISFEligible('${isfId}')" style="background: #10b981; color: white; border: none; padding: 0.25rem 0.5rem; border-radius: 0.25rem; font-size: 0.625rem; cursor: pointer;">✓ Eligible</button>
                            <button type="button" onclick="showDisqualifyReason()" style="background: #ef4444; color: white; border: none; padding: 0.25rem 0.5rem; border-radius: 0.25rem; font-size: 0.625rem; cursor: pointer;">✗ Disqualify</button>
                        </div>
                    ` : `
                        <span style="font-size: 0.625rem; color: #64748b;">${applicant.eligibilityStatus === 'Eligible' ? '→ Priority Queue' : 'Disqualified'}</span>
                    `}
                </div>
            </div>
        `;
    }

    function generateEligibilityCheckHTML(applicant) {
        const { income, ceiling, pass: incomePass } = incomeCheckState(applicant);
        const incomeWarn = incomePass ? '' : `<div style="font-size: 0.65rem; color: #991b1b; margin-top: 0.125rem; max-width: 14rem;">Exceeds ₱${ceiling.toLocaleString('en-PH')} ceiling — cannot mark eligible.</div>`;

        return `
            <div style="display: flex; flex-direction: column;">
            <div style="display: flex; align-items: center; gap: 0.375rem; font-size: 0.75rem;">
                <svg style="width: 0.875rem; height: 0.875rem; color: ${incomePass ? '#16a34a' : '#dc2626'};" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    ${incomePass ? '<polyline points="20 6 9 17 4 12"></polyline>' : '<line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line>'}
                </svg>
                <span>Household income ≤ ₱${ceiling.toLocaleString('en-PH')} (declared: ₱${income.toLocaleString('en-PH', { minimumFractionDigits: 2, maximumFractionDigits: 2 })})</span>
            </div>
            ${incomeWarn}
            </div>
            <div style="display: flex; align-items: center; gap: 0.375rem; font-size: 0.75rem;">
                <svg style="width: 0.875rem; height: 0.875rem; color: #16a34a;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="20 6 9 17 4 12"></polyline>
                </svg>
                <span>No property ownership</span>
            </div>
            <div style="display: flex; align-items: center; gap: 0.375rem; font-size: 0.75rem;">
                <svg style="width: 0.875rem; height: 0.875rem; color: #16a34a;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="20 6 9 17 4 12"></polyline>
                </svg>
                <span>Not blacklisted</span>
            </div>
        `;
    }

    function markISFEligible(isfId) {
        // Use the same endpoint as walkin
        const formData = new FormData();
        formData.append('csrfmiddlewaretoken', getCsrfToken());
        formData.append('applicant_id', isfId);
        formData.append('action', 'mark_eligible');
        formData.append('channel', 'A');

        fetch(window.APPLICANTS_CONFIG.updateEligibilityUrl, {
            method: 'POST',
            body: formData
        })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showFlowAlert('ISF marked as eligible and added to Priority Queue.', 'Success', null, 'success');
                    location.reload();
                } else {
                    showFlowAlert('Error: ' + (data.error || 'Unknown error'));
                }
            })
            .catch(error => {
                showFlowAlert('Error: ' + error.message);
            });
    }

    function isCdrrmoCertified(status) {
        return Boolean(status) && status.toLowerCase().startsWith('certified');
    }

    function populateEligibilityChecks(applicant) {
        const container = document.getElementById('eligibilityChecks');
        if (!container) return;

        const { income, ceiling, pass: incomePass } = incomeCheckState(applicant);
        const cdrrmoPass = isCdrrmoCertified(applicant.cdrrmoStatus);
        const incomeNote = incomeExceedsCeilingNoticeHtml(incomePass, income, ceiling);

        container.innerHTML = `
            <div style="display: flex; flex-direction: column;">
            <div style="display: flex; align-items: center; gap: 0.5rem; padding: 0.5rem; background: ${incomePass ? '#dcfce7' : '#fee2e2'}; border-radius: 0.375rem;">
                <svg style="width: 1rem; height: 1rem; color: ${incomePass ? '#16a34a' : '#dc2626'};" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    ${incomePass ? '<polyline points="20 6 9 17 4 12"></polyline>' : '<line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line>'}
                </svg>
                <span style="font-size: 0.8125rem;">Monthly household income ≤ ₱${ceiling.toLocaleString('en-PH')} <strong>(declared: ₱${income.toLocaleString('en-PH', { minimumFractionDigits: 2, maximumFractionDigits: 2 })})</strong></span>
            </div>
            ${incomeNote}
            </div>
            <div style="display: flex; align-items: center; gap: 0.5rem; padding: 0.5rem; background: #dcfce7; border-radius: 0.375rem;">
                <svg style="width: 1rem; height: 1rem; color: #16a34a;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="20 6 9 17 4 12"></polyline>
                </svg>
                <span style="font-size: 0.8125rem;">No property ownership in Talisay City</span>
            </div>
            <div style="display: flex; align-items: center; gap: 0.5rem; padding: 0.5rem; background: #dcfce7; border-radius: 0.375rem;">
                <svg style="width: 1rem; height: 1rem; color: #16a34a;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="20 6 9 17 4 12"></polyline>
                </svg>
                <span style="font-size: 0.8125rem;">Not on blacklist</span>
            </div>
            ${applicant.channel === 'B' ? `
            <div style="display: flex; align-items: center; gap: 0.5rem; padding: 0.5rem; background: ${cdrrmoPass ? '#dcfce7' : '#fef3c7'}; border-radius: 0.375rem;">
                <svg style="width: 1rem; height: 1rem; color: ${cdrrmoPass ? '#16a34a' : '#d97706'};" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    ${cdrrmoPass ? '<polyline points="20 6 9 17 4 12"></polyline>' : '<circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line>'}
                </svg>
                <span style="font-size: 0.8125rem;">CDRRMO Certification: <strong>${applicant.cdrrmoStatus || 'Pending'}</strong></span>
            </div>
            ` : ''}
        `;
    }

    // Toggle document checkbox and auto-save
    function toggleAndSaveDoc(label, docKey) {
        const checkbox = label.querySelector('input[type="checkbox"]');
        if (!checkbox) return;

        // Toggle checkbox
        checkbox.checked = !checkbox.checked;
        label.classList.toggle('complete', checkbox.checked);
        label.classList.toggle('incomplete', !checkbox.checked);

        // Update icon
        const svg = label.querySelector('svg');
        if (checkbox.checked) {
            svg.innerHTML = '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline>';
        } else {
            svg.innerHTML = '<circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line>';
        }

        // Auto-save to database
        saveDocumentStatus(docKey, checkbox.checked);
    }

    // Save single document status to database
    function saveDocumentStatus(docKey, isChecked) {
        if (!currentApplicant) return Promise.resolve(false);

        const formData = new FormData();
        formData.append('csrfmiddlewaretoken', getCsrfToken());
        formData.append('applicant_id', currentApplicant.applicantId || currentApplicant.id);
        formData.append('channel', currentApplicant.channel);
        formData.append('action', 'update_doc');
        formData.append(docKey, isChecked);

        if (currentApplicant.channel === 'A') {
            formData.append('submission_id', currentApplicant.submissionId);
        }

        return fetch(window.APPLICANTS_CONFIG.updateApplicantUrl, {
            method: 'POST',
            body: formData
        })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Update local data
                    const keyMap = {
                        'doc_brgy_residency': 'docBrgyResidency',
                        'doc_brgy_indigency': 'docBrgyIndigency',
                        'doc_cedula': 'docCedula',
                        'doc_police_clearance': 'docPoliceClearance',
                        'doc_no_property': 'docNoProperty',
                        'doc_2x2_picture': 'doc2x2Picture',
                        'doc_sketch_location': 'docSketchLocation',
                        'doc_voter_cert': 'docVoterCert',
                    };
                    if (keyMap[docKey]) {
                        currentApplicant[keyMap[docKey]] = isChecked;
                        // Recalculate docs count
                        currentApplicant.docsCount = [
                            currentApplicant.docBrgyResidency,
                            currentApplicant.docBrgyIndigency,
                            currentApplicant.docCedula,
                            currentApplicant.docPoliceClearance,
                            currentApplicant.docNoProperty,
                            currentApplicant.doc2x2Picture,
                            currentApplicant.docSketchLocation,
                            currentApplicant.docVoterCert,
                        ].filter(Boolean).length;
                    }
                    return true;
                } else {
                    return false;
                }
            })
            .catch(error => {
                return false;
            });
    }

    // Mirror Registration Sheet fields (Section A/B/C) into the Channel B review modal.
    // Read-only display only — driven from applicant JSON, never from form input.
    function populateChannelBRegistrationMirror(applicant) {
        if (!applicant) return;
        const setValue = (id, value) => {
            const el = document.getElementById(id);
            if (el) el.value = value == null ? '' : value;
        };
        setValue('reviewLastNameB', applicant.lastName);
        setValue('reviewFirstNameB', applicant.firstName);
        setValue('reviewMiddleNameB', applicant.middleName);
        setValue('reviewExtensionNameB', applicant.extensionName);
        const sexDisplay = applicant.sex === 'M' ? 'Male' : applicant.sex === 'F' ? 'Female' : (applicant.sex || '');
        setValue('reviewSexB', sexDisplay);
        setValue('reviewCivilStatusB', applicant.civilStatus || '');
        setValue('reviewAgeB', applicant.age ?? '');
        setValue('reviewDateOfBirthB', applicant.dateOfBirth);
        const voterEl = document.getElementById('reviewVoterB');
        if (voterEl) voterEl.value = applicant.isRegisteredVoterTalisay ? 'yes' : 'no';
        const voterDisplayEl = document.getElementById('reviewVoterBDisplay');
        if (voterDisplayEl) voterDisplayEl.textContent = applicant.isRegisteredVoterTalisay ? 'Yes' : 'No';
        const propEl = document.getElementById('reviewPropertyB');
        if (propEl) {
            const hp = applicant.hasPropertyInTalisay;
            propEl.value = (hp === true || hp === 'true' || hp === 1) ? 'yes' : 'no';
        }
        const propDisplayEl = document.getElementById('reviewPropertyBDisplay');
        if (propDisplayEl) {
            const hp = applicant.hasPropertyInTalisay;
            propDisplayEl.textContent = (hp === true || hp === 'true' || hp === 1) ? 'Yes' : 'No';
        }
        setValue('reviewOccupationB', applicant.occupation);
        setValue('reviewEmploymentStatusB', applicant.employmentStatus);

        const listEl = document.getElementById('reviewHouseholdListB');
        if (listEl) {
            const members = Array.isArray(applicant.householdMembers) ? applicant.householdMembers : [];
            if (members.length === 0) {
                listEl.innerHTML = '';
            } else {
                let html = '<div style="display: grid; gap: 0.75rem;">';
                members.forEach(member => {
                    html += `
                        <div style="padding: 0.75rem; background: #f9fafb; border-left: 3px solid #3b82f6; border-radius: 0.375rem;">
                            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.5rem; font-size: 0.875rem;">
                                <div><strong>Name:</strong> ${member.name || '-'}</div>
                                <div><strong>Relationship:</strong> ${member.relationship || '-'}</div>
                                <div><strong>Age:</strong> ${member.age || '-'}</div>
                                <div><strong>Civil status:</strong> ${member.civilStatus || '-'}</div>
                            </div>
                        </div>
                    `;
                });
                html += '</div>';
                listEl.innerHTML = html;
            }
        }
    }

    // Channel B specific eligibility checks (includes CDRRMO only if in danger zone)
    function populateEligibilityChecksB(applicant, isInDangerZone) {
        const container = document.getElementById('eligibilityChecksB');
        if (!container) return;

        let html = '';

        container.innerHTML = html;
    }

    // Channel A specific eligibility checks
    function populateEligibilityChecksA(applicant) {
        const container = document.getElementById('eligibilityChecksA');
        if (!container) return;

        const { income, ceiling, pass: incomePass } = incomeCheckState(applicant);
        const incomeNote = incomeExceedsCeilingNoticeHtml(incomePass, income, ceiling);

        container.innerHTML = `
            <div style="display: flex; flex-direction: column;">
            <div style="display: flex; align-items: center; gap: 0.5rem; padding: 0.5rem; background: ${incomePass ? '#dcfce7' : '#fee2e2'}; border-radius: 0.375rem;">
                <svg style="width: 1rem; height: 1rem; color: ${incomePass ? '#16a34a' : '#dc2626'};" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    ${incomePass ? '<polyline points="20 6 9 17 4 12"></polyline>' : '<line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line>'}
                </svg>
                <span style="font-size: 0.8125rem;">Monthly household income ≤ ₱${ceiling.toLocaleString('en-PH')} <strong>(declared: ₱${income.toLocaleString('en-PH', { minimumFractionDigits: 2, maximumFractionDigits: 2 })})</strong></span>
            </div>
            ${incomeNote}
            </div>
            <div style="display: flex; align-items: center; gap: 0.5rem; padding: 0.5rem; background: #dcfce7; border-radius: 0.375rem;">
                <svg style="width: 1rem; height: 1rem; color: #16a34a;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="20 6 9 17 4 12"></polyline>
                </svg>
                <span style="font-size: 0.8125rem;">No property ownership in Talisay City</span>
            </div>
            <div style="display: flex; align-items: center; gap: 0.5rem; padding: 0.5rem; background: #dcfce7; border-radius: 0.375rem;">
                <svg style="width: 1rem; height: 1rem; color: #16a34a;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="20 6 9 17 4 12"></polyline>
                </svg>
                <span style="font-size: 0.8125rem;">Not on blacklist</span>
            </div>
            <div style="display: flex; align-items: center; gap: 0.5rem; padding: 0.5rem; background: #dbeafe; border-radius: 0.375rem;">
                <svg style="width: 1rem; height: 1rem; color: #2563eb;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="20 6 9 17 4 12"></polyline>
                </svg>
                <span style="font-size: 0.8125rem;">Landowner Endorsed — Priority Queue</span>
            </div>
        `;
    }

    // Channel A specific document checklist
    function populateDocumentChecklistA(applicant) {
        const container = document.getElementById('documentChecklistA');
        if (!container) return;

        const docs = [
            { key: 'docBrgyResidency', dbKey: 'doc_brgy_residency', label: 'Brgy. Certificate of Residency' },
            { key: 'docBrgyIndigency', dbKey: 'doc_brgy_indigency', label: 'Brgy. Certificate of Indigency' },
            { key: 'docCedula', dbKey: 'doc_cedula', label: 'Cedula' },
            { key: 'docPoliceClearance', dbKey: 'doc_police_clearance', label: 'Police Clearance' },
            { key: 'docNoProperty', dbKey: 'doc_no_property', label: 'Certificate of No Property' },
            { key: 'doc2x2Picture', dbKey: 'doc_2x2_picture', label: '2x2 Picture' },
            { key: 'docSketchLocation', dbKey: 'doc_sketch_location', label: 'Sketch of House Location' }
        ];

        let html = '';
        docs.forEach(doc => {
            const checked = applicant[doc.key] || false;
            html += `
                <label class="document-item ${checked ? 'complete' : 'incomplete'}" style="cursor: ${isEditMode ? 'pointer' : 'default'};" ${isEditMode ? `onclick="toggleAndSaveDoc(this, '${doc.dbKey}')"` : ''}>
                    <input type="checkbox" name="${doc.dbKey}" ${checked ? 'checked' : ''} ${isEditMode ? '' : 'disabled'} style="display: none;">
                    <svg class="document-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        ${checked
                    ? '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline>'
                    : '<circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line>'}
                    </svg>
                    ${doc.label}
                </label>
            `;
        });
        container.innerHTML = html;
    }

    function hasPendingFieldDisposition(applicant) {
        return !!(
            applicant &&
            applicant.channel === 'B' &&
            applicant.cdrrmo_disposition_source === 'field_unit' &&
            (applicant.cdrrmo_status === 'certified' || applicant.cdrrmo_status === 'not_certified') &&
            applicant.applicantStatus === 'pending_cdrrmo'
        );
    }

    function shouldShowGenericEligibilityActions(applicant) {
        if (!applicant) return false;
        const st = String(applicant.applicantStatus || '').toLowerCase();
        if (!(st === 'pending' || st === 'pending_cdrrmo')) return false;
        if (hasPendingFieldDisposition(applicant)) return false;
        return true;
    }

    function updateActionButtons(applicant) {
        const btnMarkEligible = document.getElementById('btnMarkEligible');
        const btnDisqualify = document.getElementById('btnDisqualify');
        const btnProceedModule2 = document.getElementById('btnProceedModule2');
        const reviewActions = document.getElementById('reviewActions');

        // Return early if elements don't exist (read-only users)
        if (!reviewActions) return;

        // Proceed from modal → Intake Archives only (no Applicant.module2_handoff_*)
        if (btnProceedModule2) {
            const appStatus = String(applicant?.applicantStatus || '').toLowerCase();
            const hideProceed = appStatus === 'disqualified' || !!applicant?.isArchived;
            btnProceedModule2.style.display = hideProceed ? 'none' : 'inline-flex';
        }

        // Show generic Mark Eligible / Disqualify only when this is not a pending field report case.
        if (shouldShowGenericEligibilityActions(applicant)) {
            reviewActions.style.display = 'flex';

            // For Channel B pending CDRRMO, disable mark eligible
            if (btnMarkEligible) {
                if (String(applicant.applicantStatus || '').toLowerCase() === 'pending_cdrrmo' && !isCdrrmoCertified(applicant.cdrrmoStatus)) {
                    btnMarkEligible.disabled = true;
                    btnMarkEligible.title = 'Awaiting CDRRMO verification of hazard claim';
                } else {
                    btnMarkEligible.disabled = false;
                    btnMarkEligible.title = '';
                }
            }
        } else {
            reviewActions.style.display = 'none';
        }
    }

    // Archive-only proceed (same endpoint as modal “Proceed to LIST OF APPLICATIONS”)
    let archiveProceedInFlight = false;

    function proceedToArchive(applicant = null) {
        const target = applicant || currentApplicant;
        if (archiveProceedInFlight) return;
        if (!target || !(target.applicantId || target.id)) {
            showNoticeModal({
                title: 'No Record Selected',
                message: 'Please open an applicant record before proceeding to LIST OF APPLICATIONS.',
                type: 'warning',
            });
            return;
        }

        const formData = new FormData();
        formData.append('applicant_id', target.applicantId || target.id);
        formData.append('csrfmiddlewaretoken', getCsrfToken());
        logSmsDispatchPlan('Proceed to LIST OF APPLICANTS', {
            applicantId: target.applicantId || target.id,
            referenceNumber: target.referenceNumber || '',
            promoteToModule2: false,
            smsTrigger: 'proceed_applicant_list',
        });

        archiveProceedInFlight = true;

        fetch(window.APPLICANTS_CONFIG.proceedToApplicationsUrl, {
            method: 'POST',
            body: formData
        })
            .then(response => response.json())
            .then(data => {
                if (!data.success) {
                    showNoticeModal({
                        title: 'Proceed Failed',
                        message: data.error || 'Unable to proceed to LIST OF APPLICATIONS.',
                        type: 'error',
                    });
                    return;
                }
                showNoticeModal({
                    title: 'Success!',
                    messageHtml: buildProceedArchiveSuccessHtml(),
                    allowHtml: true,
                    type: 'success',
                    celebration: true,
                    refPill: target.referenceNumber || '',
                    onPrimary: () => {
                        try { sessionStorage.setItem('scrollToArchiveSection', '1'); } catch (_err) { }
                        closeReviewModal();
                        location.reload();
                    },
                });
            })
            .catch(error => {
                showNoticeModal({
                    title: 'Network Error',
                    message: error.message,
                    type: 'error',
                });
            })
            .finally(() => {
                archiveProceedInFlight = false;
            });
    }

    function openDocumentScanModal(applicant) {
        if (!applicant) return;

        const modal = document.getElementById('documentScanModal');
        if (!modal) {
            return;
        }

        // Set applicant reference
        const refEl = document.getElementById('documentScanApplicantRef');
        if (refEl) {
            refEl.textContent = `${applicant.referenceNumber} • ${applicant.fullName}`;
        }

        // Fallback CTA injection: ensure scan action is visible even if older modal markup is cached.
        ensureDocumentScanActionButtons();

        const requirements = [
            {
                code: 'R01',
                name: 'Brgy. Certificate of Residency',
                group: 'Applicant Requirements',
                dbKey: 'doc_brgy_residency',
                isRequired: true,
                isActive: true,
                scanned: isApplicantRequirementOnFile(applicant, 'R01'),
            },
            {
                code: 'R02',
                name: 'Brgy. Certificate of Indigency',
                group: 'Applicant Requirements',
                dbKey: 'doc_brgy_indigency',
                isRequired: true,
                isActive: true,
                scanned: isApplicantRequirementOnFile(applicant, 'R02'),
            },
            {
                code: 'R03',
                name: 'Cedula',
                group: 'Applicant Requirements',
                dbKey: 'doc_cedula',
                isRequired: true,
                isActive: true,
                scanned: isApplicantRequirementOnFile(applicant, 'R03'),
            },
            {
                code: 'R04',
                name: 'Police Clearance',
                group: 'Applicant Requirements',
                dbKey: 'doc_police_clearance',
                isRequired: true,
                isActive: true,
                scanned: isApplicantRequirementOnFile(applicant, 'R04'),
            },
            {
                code: 'R05',
                name: 'Certificate of No Property',
                group: 'Applicant Requirements',
                dbKey: 'doc_no_property',
                isRequired: true,
                isActive: true,
                scanned: isApplicantRequirementOnFile(applicant, 'R05'),
            },
            {
                code: 'R06',
                name: '2x2 Picture',
                group: 'Applicant Requirements',
                dbKey: 'doc_2x2_picture',
                isRequired: true,
                isActive: true,
                scanned: isApplicantRequirementOnFile(applicant, 'R06'),
            },
            {
                code: 'R07',
                name: 'Sketch of House Location',
                group: 'Applicant Requirements',
                dbKey: 'doc_sketch_location',
                isRequired: true,
                isActive: true,
                scanned: isApplicantRequirementOnFile(applicant, 'R07'),
            },
        ];
        requirements.push({
            code: 'RVT',
            name: 'Voter Certification',
            group: 'Applicant Requirements',
            dbKey: 'doc_voter_cert',
            isRequired: false,
            isActive: true,
            scanned: isApplicantRequirementOnFile(applicant, 'RVT'),
        });
        if (['danger_zone', 'ejected', 'relocated'].includes(applicant.displacementReason)) {
            var situCode = String(applicant.displacementReason || '').trim() === 'danger_zone' ? 'CDRRMO' : 'ISF-SIT';
            var situDbKey = String(applicant.displacementReason || '').trim() === 'danger_zone' ? 'doc_cdrrmo' : 'doc_isf_situational';
            requirements.push({
                code: situCode,
                name: (function () {
                    var dr = String(applicant.displacementReason || '').trim();
                    if (dr === 'danger_zone') {
                        return 'Resident of Danger Zone or Hazard Area Follow-up';
                    }
                    if (dr === 'ejected') {
                        return 'Ejected or Evicted from Prior Residence Follow-up';
                    }
                    if (dr === 'relocated') {
                        return 'Displaced by Government Project or Infrastructure Follow-up';
                    }
                    return 'ISF situational documentation Follow-up';
                })(),
                group: 'Applicant Requirements',
                dbKey: situDbKey,
                isRequired: false,
                isActive: true,
                scanned: isApplicantRequirementOnFile(applicant, situCode),
            });
        }

        populateDocumentScanTable(requirements, applicant);

        modal.style.display = 'flex';
    }

    function ensureDocumentScanActionButtons() {
        const modal = document.getElementById('documentScanModal');
        if (!modal) return;

        if (!document.getElementById('scanAllDocumentsHeaderBtn')) {
            const headline = modal.querySelector('.docscan-headline');
            if (headline) {
                const headerBtn = document.createElement('button');
                headerBtn.type = 'button';
                headerBtn.id = 'scanAllDocumentsHeaderBtn';
                headerBtn.className = 'btn-modal secondary';
                headerBtn.textContent = 'Scan documents';
                headerBtn.style.marginTop = '0.45rem';
                headerBtn.style.alignSelf = 'flex-start';
                headerBtn.onclick = scanAllDocumentsOneByOne;
                headline.appendChild(headerBtn);
            }
        }
    }

    function closeDocumentScanModal() {
        const modal = document.getElementById('documentScanModal');
        if (modal) modal.style.display = 'none';
    }

    function populateDocumentScanTable(requirements, applicant) {
        const tbody = document.getElementById('documentScanTableBody');
        if (!tbody) return;

        tbody.innerHTML = requirements.map(req => `
            <tr style="border-bottom: 1px solid #e2e8f0; ${isFollowUpRequirement(req.code) ? 'background:#f8fafc;' : ''}" data-docscan-code="${escapeHtml(req.code)}">
                <td style="text-align: center;">
                    <input
                        type="checkbox"
                        class="doc-scan-checkbox docscan-check"
                        data-code="${req.code}"
                        data-doc-key="${req.dbKey || ''}"
                        data-required="${req.isRequired}"
                        ${req.scanned ? 'checked' : ''}
                        disabled
                    >
                </td>
                <td class="docscan-table-name">
                    ${escapeHtml(req.name)}
                    ${isFollowUpRequirement(req.code) ? '<span class="req-badge req-badge-no" style="margin-left:0.45rem;">Follow-up</span>' : ''}
                </td>
                <td>
                    <span class="${req.isRequired ? 'req-badge req-badge-yes' : 'req-badge req-badge-no'}">
                        ${req.isRequired ? 'Required' : 'Optional'}
                    </span>
                </td>
                <td>
                    <span class="${req.scanned ? 'docscan-status docscan-status-done' : 'docscan-status docscan-status-pending'}">
                        ${req.scanned ? 'On file' : 'Missing'}
                    </span>
                </td>
                <td>
                    ${req.dbKey
                ? `<button type="button" class="btn-modal secondary docscan-row-scan-btn" data-code="${escapeHtml(req.code)}" data-doc-key="${escapeHtml(req.dbKey)}" data-doc-name="${escapeHtml(req.name)}" onclick="scanSingleRequirementFromRow(this)" ${canModify ? '' : 'disabled'}>${canModify ? 'Scan' : 'View only'}</button>`
                : '<span style="color:#64748b;font-size:0.75rem;">N/A</span>'}
                </td>
            </tr>
        `).join('');

        const rowsEl = document.getElementById('documentScanRows');
        if (rowsEl) rowsEl.textContent = String(requirements.length);
        updateDocumentScanProgress();
    }

    async function scanSingleRequirementFromRow(buttonEl) {
        if (!buttonEl || !currentApplicant) return;
        const docKey = buttonEl.dataset.docKey || '';
        const code = buttonEl.dataset.code || 'document';
        const name = buttonEl.dataset.docName || code;
        if (!docKey) return;

        buttonEl.disabled = true;
        const oldText = buttonEl.textContent;
        buttonEl.textContent = 'Scanning...';
        try {
            await acquireImageWithDwt({ selectSource: true });
            await uploadCurrentScannedImage(docKey, code);
            applyScannedStateToApplicant(docKey);
            const isSaved = await saveDocumentStatus(docKey, true);
            if (!isSaved) {
            }

            const row = buttonEl.closest('tr');
            const checkbox = row?.querySelector('.doc-scan-checkbox');
            const statusEl = row?.querySelector('.docscan-status');
            if (checkbox) checkbox.checked = true;
            if (statusEl) {
                statusEl.className = 'docscan-status docscan-status-done';
                statusEl.textContent = 'View';
            }
            updateDocumentScanProgress();
            buttonEl.textContent = 'Scan';
        } catch (error) {
            showFlowAlert('Unable to scan ' + name + ': ' + (error.message || 'unknown error'), 'Notice', null, 'warning');
            buttonEl.textContent = oldText;
            buttonEl.disabled = false;
            return;
        }
        buttonEl.disabled = true;
    }

    function updateDocumentScanProgress() {
        const requiredCheckboxes = document.querySelectorAll('.doc-scan-checkbox[data-required="true"]:checked');
        const totalRequired = document.querySelectorAll('.doc-scan-checkbox[data-required="true"]');

        const scannedCount = requiredCheckboxes.length;
        const requiredCount = totalRequired.length;

        const progressEl = document.getElementById('documentScanProgress');
        if (progressEl) progressEl.textContent = `${scannedCount}/${requiredCount}`;
        const readinessEl = document.getElementById('documentScanReadiness');
        const isComplete = scannedCount === requiredCount && requiredCount > 0;
        if (readinessEl) readinessEl.textContent = isComplete ? 'Ready' : 'Review';

        const submitBtn = document.getElementById('submitToApplicationsBtn');
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.style.opacity = '1';
            submitBtn.style.cursor = 'pointer';
        }
    }

    function setDocumentScanButtonsBusy(isBusy) {
        const headerScanBtn = document.getElementById('scanAllDocumentsHeaderBtn');
        const scanBtn = document.getElementById('scanAllDocumentsBtn');
        const topScanBtn = document.getElementById('scanAllDocumentsTopBtn');
        const submitBtn = document.getElementById('submitToApplicationsBtn');
        if (headerScanBtn) {
            headerScanBtn.disabled = isBusy;
            headerScanBtn.style.opacity = isBusy ? '0.6' : '1';
            headerScanBtn.style.cursor = isBusy ? 'wait' : 'pointer';
            headerScanBtn.textContent = isBusy ? 'Scanning documents...' : 'Scan documents';
        }
        if (scanBtn) {
            scanBtn.disabled = isBusy;
            scanBtn.style.opacity = isBusy ? '0.6' : '1';
            scanBtn.style.cursor = isBusy ? 'wait' : 'pointer';
            scanBtn.textContent = isBusy ? 'Scanning documents...' : 'Scan documents';
        }
        if (topScanBtn) {
            topScanBtn.disabled = isBusy;
            topScanBtn.style.opacity = isBusy ? '0.6' : '1';
            topScanBtn.style.cursor = isBusy ? 'wait' : 'pointer';
            topScanBtn.textContent = isBusy ? 'Scanning documents...' : 'Scan documents';
        }
        if (submitBtn) {
            submitBtn.disabled = isBusy;
            submitBtn.style.opacity = isBusy ? '0.6' : '1';
            submitBtn.style.cursor = isBusy ? 'wait' : 'pointer';
        }
    }

    async function scanAllDocumentsOneByOne() {
        if (!currentApplicant) return;

        const checkboxes = Array.from(document.querySelectorAll('.doc-scan-checkbox[data-required="true"]'));
        const pending = checkboxes.filter((checkbox) => !checkbox.checked && checkbox.dataset.docKey);
        if (pending.length === 0) {
            updateDocumentScanProgress();
            return;
        }

        setDocumentScanButtonsBusy(true);
        try {
            const dwt = await waitForDwtReady();
            if (!dwt) throw new Error('Scanner SDK is not ready yet. Refresh the page and try again.');
            await dwt.SelectSourceAsync();
            for (const checkbox of pending) {
                await acquireImageWithDwt({ selectSource: false, closeSourceAfterAcquire: false });
                await uploadCurrentScannedImage(checkbox.dataset.docKey, checkbox.dataset.code || 'document');
                applyScannedStateToApplicant(checkbox.dataset.docKey);
                const isSaved = await saveDocumentStatus(checkbox.dataset.docKey, true);
                if (!isSaved) {
                }

                checkbox.checked = true;
                const statusEl = checkbox.closest('tr')?.querySelector('.docscan-status');
                if (statusEl) {
                    statusEl.className = 'docscan-status docscan-status-done';
                    statusEl.textContent = 'View';
                }
                const rowBtn = checkbox.closest('tr')?.querySelector('.docscan-row-scan-btn');
                if (rowBtn) {
                    rowBtn.disabled = true;
                    rowBtn.textContent = 'Scan';
                }
                updateDocumentScanProgress();
                await new Promise((resolve) => setTimeout(resolve, 120));
            }
            if (typeof dwt.CloseSource === 'function') {
                try { dwt.CloseSource(); } catch (_err) { }
            }
        } catch (error) {
            showFlowAlert(error.message || 'Unable to scan all documents. Please try again.', 'Notice', null, 'warning');
        } finally {
            setDocumentScanButtonsBusy(false);
        }
    }

    function submitToApplications() {
        if (!currentApplicant) return;

        // Close the document scan modal
        closeDocumentScanModal();

        // Now call the actual proceed_to_applications endpoint
        proceedToArchive(currentApplicant);
    }

    // NOTE: `proceedToApplicationsAPI` removed — use `proceedToArchive` only.

    function closeReviewModal() {
        const modal = document.getElementById('reviewModal');
        if (modal) modal.classList.remove('active');
        const shell = document.querySelector('#reviewModal .modal-content.tha-review-modal');
        if (shell) shell.classList.remove('tha-review-modal--policy-alert');
        const dzRoot = document.getElementById('dangerZoneReviewSection');
        if (dzRoot) clearLayer2ViolationClasses(dzRoot);
        currentApplicant = null;
        isEditMode = false;
        reviewModalArchiveMode = false;
    }

    function toggleEditMode() {
        isEditMode = !isEditMode;
        updateEditModeUI();
    }

    function updateEditModeUI() {
        const modal = document.getElementById('reviewModal');
        if (modal) modal.classList.toggle('tha-edit-mode', isEditMode);

        // Channel C fields
        const walkinFields = ['reviewFullName', 'reviewIncome', 'reviewHousehold', 'reviewYears', 'reviewPhone', 'reviewAddress'];
        const selectFieldsC = ['reviewBarangay'];

        // Channel B (Danger Zone) fields
        const dangerZoneFields = ['reviewFullNameB', 'reviewIncomeB', 'reviewHouseholdB', 'reviewYearsB', 'reviewPhoneB', 'reviewAddressB', 'reviewDangerLocation'];
        const selectFieldsB = ['reviewBarangayB', 'reviewDangerType', 'reviewVoterB', 'reviewPropertyB'];

        // Channel A landowner fields
        const landownerFields = ['reviewLandownerName', 'reviewLandownerPhone', 'reviewPropertyAddress', 'reviewSubmissionBarangay'];

        // Channel A ISF fields (redesigned modal)
        const channelAFields = ['reviewFullNameA', 'reviewIncomeA', 'reviewHouseholdA', 'reviewYearsA', 'reviewPhoneA', 'reviewAddressA'];
        const selectFieldsA = ['reviewBarangayA'];

        // Update Channel C fields
        walkinFields.forEach(id => {
            const el = document.getElementById(id);
            if (el) el.readOnly = !isEditMode;
        });

        // Toggle: use CSS classes show-in-view-mode and show-in-edit-mode
        selectFieldsC.forEach(id => {
            const el = document.getElementById(id);
            if (el) el.disabled = !isEditMode;
        });

        // Update Channel B fields
        dangerZoneFields.forEach(id => {
            const el = document.getElementById(id);
            if (el) el.readOnly = !isEditMode;
        });

        // Channel B selects: toggle disabled state
        selectFieldsB.forEach(id => {
            const el = document.getElementById(id);
            if (el) el.disabled = !isEditMode;
        });

        // Update Channel A landowner fields
        landownerFields.forEach(id => {
            const el = document.getElementById(id);
            if (el) el.readOnly = !isEditMode;
        });

        // Update Channel A ISF fields
        channelAFields.forEach(id => {
            const el = document.getElementById(id);
            if (el) el.readOnly = !isEditMode;
        });

        selectFieldsA.forEach(id => {
            const el = document.getElementById(id);
            if (el) el.disabled = !isEditMode;
        });

        // These elements only exist for users with can_modify permission
        const editToggleText = document.getElementById('editToggleText');
        const editActions = document.getElementById('editActions');
        const reviewActions = document.getElementById('reviewActions');

        if (editToggleText) editToggleText.textContent = isEditMode ? 'Cancel Edit' : 'EDIT record';
        if (editActions) editActions.style.display = isEditMode ? 'flex' : 'none';

        // When leaving edit mode, re-apply role/path-based button gating.
        if (reviewActions) {
            if (isEditMode) {
                reviewActions.style.display = 'none';
            } else if (currentApplicant) {
                updateActionButtons(currentApplicant);
            }
        }

        // Update document checklists based on channel
        if (currentApplicant) {
            if (currentApplicant.channel === 'A') {
                // Channel A uses static form fields - just update document checklist
                populateDocumentChecklistA(currentApplicant);
            }
            if (currentApplicant.channel === 'B') {
                const dzRoot = document.getElementById('dangerZoneReviewSection');
                const snap = getApplicantSnapshotForLayer2FromDangerZoneForm(currentApplicant);
                applyLayer2ViolationHighlights(snap, dzRoot);
                updateReviewModalPolicyAlert(snap);
            }
        }
    }

    // Update CDRRMO certification status (Channel B only)
    function updateCdrrmoStatus(newStatus) {
        if (!currentApplicant || currentApplicant.channel !== 'B') {
            showFlowAlert('CDRRMO certification only applies to Channel B applicants.');
            return;
        }

        const statusText = newStatus === 'certified' ? 'CERTIFIED' : 'NOT CERTIFIED';
        showNoticeModal({
            title: `Mark as ${statusText}?`,
            message: `Are you sure you want to mark this applicant as ${statusText}?\n\nThis will update their CDRRMO certification status.`,
            type: 'warning',
            primaryText: 'Yes, Confirm',
            secondaryText: 'Cancel',
            applicantName: currentApplicant.fullName,
            onPrimary: () => {
                const cdrrmoNotes = document.getElementById('cdrrmoNotes')?.value || '';

                // Send AJAX request to update CDRRMO status
                const formData = new FormData();
                formData.append('applicant_id', currentApplicant.applicantId);
                formData.append('channel', 'B');
                formData.append('cdrrmo_status', newStatus);
                formData.append('cdrrmo_notes', cdrrmoNotes);
                formData.append('csrfmiddlewaretoken', getCsrfToken());

                fetch(window.APPLICANTS_CONFIG.updateApplicantUrl, {
                    method: 'POST',
                    body: formData
                })
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            // Update local data
                            currentApplicant.cdrrmoStatus = newStatus === 'certified' ? 'Certified' : 'Not Certified';
                            currentApplicant.isCdrrmoFlagged = false;
                            currentApplicant.cdrrmoDaysPending = 0;

                            if (newStatus === 'certified') {
                                currentApplicant.eligibilityStatus = 'Pending eligibility check';
                            } else {
                                currentApplicant.eligibilityStatus = 'Pending eligibility check';
                                currentApplicant.channel = 'C';  // Downgraded to walk-in
                            }

                            // Update UI
                            const cdrrmoBox = document.getElementById('cdrrmoStatusBox');
                            const cdrrmoText = document.getElementById('cdrrmoStatusText');
                            const cdrrmoActionsBox = document.getElementById('cdrrmoActionsBox');

                            if (cdrrmoBox && cdrrmoText) {
                                if (newStatus === 'certified') {
                                    cdrrmoBox.style.background = '#dcfce7';
                                    cdrrmoBox.style.borderColor = '#86efac';
                                    cdrrmoText.style.color = '#166534';
                                    cdrrmoText.innerHTML = `<strong>CDRRMO certification on file</strong><br>The declared hazard-area representation has been certified pursuant to CDRRMO field verification.`;
                                } else {
                                    cdrrmoBox.style.background = '#fee2e2';
                                    cdrrmoBox.style.borderColor = '#fca5a5';
                                    cdrrmoText.style.color = '#991b1b';
                                    cdrrmoText.innerHTML = `<strong>CDRRMO certification not granted</strong><br>The declared location was not certified as a qualifying hazard area. The record will be reclassified for walk-in processing, as applicable.`;
                                }
                            }

                            // Hide action buttons
                            if (cdrrmoActionsBox) cdrrmoActionsBox.style.display = 'none';

                            showFlowAlert(`CDRRMO status updated to ${statusText}. Page will reload to reflect changes.`);
                            location.reload();
                        } else {
                            showFlowAlert('Error: ' + (data.error || 'Unknown error'));
                        }
                    })
                    .catch(error => {
                        showFlowAlert('Network error. Please try again.');
                    });
            }
        });
    }

    function cancelEdit() {
        isEditMode = false;
        updateEditModeUI();
        // Reset form values based on channel (with null checks)
        if (currentApplicant) {
            if (currentApplicant.channel === 'A') {
                // Reset landowner fields
                const landownerNameEl = document.getElementById('reviewLandownerName');
                const landownerPhoneEl = document.getElementById('reviewLandownerPhone');
                const propertyAddressEl = document.getElementById('reviewPropertyAddress');
                const submissionBarangayEl = document.getElementById('reviewSubmissionBarangay');

                if (landownerNameEl) landownerNameEl.value = currentApplicant.landownerName || '';
                if (landownerPhoneEl) landownerPhoneEl.value = currentApplicant.landownerPhone || '';
                if (propertyAddressEl) propertyAddressEl.value = currentApplicant.propertyAddress || '';
                if (submissionBarangayEl) submissionBarangayEl.value = currentApplicant.submissionBarangay || currentApplicant.barangay || '';

                // Reset ISF fields (redesigned modal)
                const fullNameAEl = document.getElementById('reviewFullNameA');
                const barangayAEl = document.getElementById('reviewBarangayA');
                const incomeAEl = document.getElementById('reviewIncomeA');
                const householdAEl = document.getElementById('reviewHouseholdA');
                const yearsAEl = document.getElementById('reviewYearsA');
                const phoneAEl = document.getElementById('reviewPhoneA');
                const addressAEl = document.getElementById('reviewAddressA');

                if (fullNameAEl) fullNameAEl.value = currentApplicant.fullName || '';
                if (barangayAEl) barangayAEl.value = currentApplicant.barangay || '';
                if (incomeAEl) incomeAEl.value = String(currentApplicant.monthlyIncome || '').replace(/,/g, '');
                if (householdAEl) householdAEl.value = currentApplicant.householdSize || '';
                if (yearsAEl) yearsAEl.value = currentApplicant.yearsResiding || '';
                if (phoneAEl) phoneAEl.value = currentApplicant.phoneNumber || '';
                if (addressAEl) addressAEl.value = currentApplicant.propertyAddress || '';
            } else if (currentApplicant.channel === 'B') {
                const fullNameBEl = document.getElementById('reviewFullNameB');
                const barangayBEl = document.getElementById('reviewBarangayB');
                const incomeBEl = document.getElementById('reviewIncomeB');
                const householdBEl = document.getElementById('reviewHouseholdB');
                const yearsBEl = document.getElementById('reviewYearsB');
                const phoneBEl = document.getElementById('reviewPhoneB');
                const addressBEl = document.getElementById('reviewAddressB');
                const dangerTypeEl = document.getElementById('reviewDangerType');
                const dangerLocEl = document.getElementById('reviewDangerLocation');

                if (fullNameBEl) fullNameBEl.value = currentApplicant.fullName || '';
                if (barangayBEl) barangayBEl.value = currentApplicant.barangay || '';
                if (incomeBEl) incomeBEl.value = formatIncomeInputValue(currentApplicant.monthlyIncome);
                if (householdBEl) householdBEl.value = currentApplicant.householdSize || '';
                if (yearsBEl) yearsBEl.value = currentApplicant.yearsResiding || '';
                if (phoneBEl) phoneBEl.value = currentApplicant.phoneNumber || '';
                if (addressBEl) addressBEl.value = currentApplicant.currentAddress || '';
                if (dangerTypeEl) dangerTypeEl.value = currentApplicant.dangerZoneType || '';
                if (dangerLocEl) dangerLocEl.value = currentApplicant.dangerZoneLocation || '';
                populateChannelBRegistrationMirror(currentApplicant);
                const dzRoot = document.getElementById('dangerZoneReviewSection');
                applyLayer2ViolationHighlights(currentApplicant, dzRoot);
                updateReviewModalPolicyAlert(currentApplicant);
            } else {
                const fullNameEl = document.getElementById('reviewFullName');
                const barangayEl = document.getElementById('reviewBarangay');
                const incomeEl = document.getElementById('reviewIncome');
                const householdEl = document.getElementById('reviewHousehold');
                const yearsEl = document.getElementById('reviewYears');
                const phoneEl = document.getElementById('reviewPhone');
                const addressEl = document.getElementById('reviewAddress');

                if (fullNameEl) fullNameEl.value = currentApplicant.fullName || '';
                if (barangayEl) barangayEl.value = currentApplicant.barangay || '';
                if (incomeEl) incomeEl.value = formatIncomeInputValue(currentApplicant.monthlyIncome);
                if (householdEl) householdEl.value = currentApplicant.householdSize || '';
                if (yearsEl) yearsEl.value = currentApplicant.yearsResiding || '';
                if (phoneEl) phoneEl.value = currentApplicant.phoneNumber || '';
                if (addressEl) addressEl.value = currentApplicant.currentAddress || '';
            }
        }
    }

    function closeDeadlineModal() {
    const deadlineModal = document.getElementById('deadlineModal');
    if (deadlineModal) deadlineModal.style.display = 'none';
    }

    function setDocumentDeadline() {
        if (!currentApplicant) return;

        const deadlineDate = getInputValue('deadlineDate');
        const deadlineTime = getInputValue('deadlineTime');

        if (!deadlineDate || !deadlineTime) {
            showFlowAlert('Please select both date and time');
            return;
        }

        // Combine date and time
        const deadlineDateTime = `${deadlineDate}T${deadlineTime}`;

        // Send to backend
        const formData = new FormData();
        formData.append('csrfmiddlewaretoken', getCsrfToken());
        formData.append('applicant_id', currentApplicant.applicantId || currentApplicant.id);
        formData.append('action', 'set_doc_deadline');
        formData.append('document_deadline', deadlineDateTime);

        fetch(window.APPLICANTS_CONFIG.updateEligibilityUrl, {
            method: 'POST',
            body: formData
        })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    closeDeadlineModal();
                    showFlowAlert('Document deadline set. Applicant status changed to "Submitting Requirements" and will be notified via SMS.', 'Success', null, 'success');
                    location.reload();
                } else {
                    showFlowAlert('Error: ' + (data.error || 'Unknown error'));
                }
            })
            .catch(error => {
                showFlowAlert('Error: ' + error.message);
            });
    }

    function markEligible() {
        if (!currentApplicant) return;

        // For Channel A: Open ISF Review Modal
        if (currentApplicant.channel === 'A') {
            currentISFData = currentApplicant;
            populateISFModal(currentApplicant);
    const isfReviewModal = document.getElementById('isfReviewModal');
    if (isfReviewModal) isfReviewModal.classList.add('active');
            return;
        }

        // For Channel B/C: Use AJAX to mark eligible
        const formData = new FormData();
        formData.append('csrfmiddlewaretoken', getCsrfToken());
        formData.append('applicant_id', currentApplicant.applicantId || currentApplicant.id);
        formData.append('action', 'mark_eligible');

        fetch(window.APPLICANTS_CONFIG.updateEligibilityUrl, {
            method: 'POST',
            body: formData
        })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showFlowAlert('Applicant marked as eligible and added to queue.', 'Success', null, 'success');
                    location.reload();
                } else {
                    showFlowAlert('Error: ' + (data.error || 'Unknown error'));
                }
            })
            .catch(error => {
                showFlowAlert('Error: ' + error.message);
            });
    }

    function showDisqualifyReason() {
        showFlowAlert(
            'Disqualification is handled in Module 2 blacklist policy. Open Application & Eligibility and run Evaluation Precheck.'
        );
    }

    function closeDisqualifyModal() {
        const modal = document.getElementById('disqualifyModal');
        if (modal) modal.classList.remove('active');
    }

    function confirmDisqualify() {
        showFlowAlert(
            'Disqualification is handled in Module 2 blacklist policy. Open Application & Eligibility and run Evaluation Precheck.'
        );
    }

    // Save Changes for Review Modal
    function saveReviewChanges(event) {
        event.preventDefault();

        if (!currentApplicant) return;

        const formData = new FormData();
        formData.append('csrfmiddlewaretoken', getCsrfToken());
        formData.append('applicant_id', currentApplicant.applicantId || currentApplicant.id);
        formData.append('channel', currentApplicant.channel);
        formData.append('action', 'update');

        if (currentApplicant.channel === 'A') {
            // Channel A: Include landowner + ISF data
            formData.append('submission_id', getInputValue('reviewSubmissionId'));
            formData.append('landowner_name', getInputValue('reviewLandownerName'));
            formData.append('landowner_phone', getInputValue('reviewLandownerPhone'));
            formData.append('property_address', getInputValue('reviewPropertyAddress'));
            formData.append('submission_barangay', getInputValue('reviewSubmissionBarangay'));

            // Get ISF field data from redesigned modal
            formData.append('isf_name', getInputValue('reviewFullNameA'));
            formData.append('isf_income', getInputValue('reviewIncomeA'));
            formData.append('isf_household', getInputValue('reviewHouseholdA'));
            formData.append('isf_years', getInputValue('reviewYearsA'));
            formData.append('isf_barangay', getInputValue('reviewBarangayA'));

            // Include Channel A document checklist
            document.querySelectorAll('#documentChecklistA input[type="checkbox"]').forEach(cb => {
                formData.append(cb.name, cb.checked);
            });

        } else if (currentApplicant.channel === 'B') {
            // Channel B: Danger Zone applicant data
            formData.append('full_name', getInputValue('reviewFullNameB'));
            formData.append('barangay', getInputValue('reviewBarangayB'));
            formData.append('monthly_income', getInputValue('reviewIncomeB').replace(/,/g, ''));
            formData.append('household_size', getInputValue('reviewHouseholdB'));
            formData.append('years_residing', getInputValue('reviewYearsB'));
            formData.append('phone_number', getInputValue('reviewPhoneB'));
            formData.append('current_address', getInputValue('reviewAddressB'));
            const dzTypeEl = document.getElementById('reviewDangerType');
            const dzLocEl = document.getElementById('reviewDangerLocation');
            formData.append('danger_zone_type', dzTypeEl ? dzTypeEl.value : '');
            formData.append('danger_zone_location', dzLocEl ? dzLocEl.value : '');
            const voterB = document.getElementById('reviewVoterB');
            const propB = document.getElementById('reviewPropertyB');
            if (voterB) formData.append('is_registered_voter_talisay', voterB.value);
            if (propB) formData.append('has_property_in_talisay', propB.value);

        } else {
            // Channel C: Regular walk-in applicant data
            formData.append('full_name', getInputValue('reviewFullName'));
            formData.append('barangay', getInputValue('reviewBarangay'));
            formData.append('monthly_income', getInputValue('reviewIncome').replace(/,/g, ''));
            formData.append('household_size', getInputValue('reviewHousehold'));
            formData.append('years_residing', getInputValue('reviewYears'));
            formData.append('phone_number', getInputValue('reviewPhone'));
            formData.append('current_address', getInputValue('reviewAddress'));

        }

        fetch(window.APPLICANTS_CONFIG.updateApplicantUrl, {
            method: 'POST',
            body: formData
        })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showFlowAlert('Changes saved successfully.', 'Success', function () {
                        location.reload();
                    }, 'success');
                } else {
                    showFlowAlert('Error: ' + (data.error || 'Unknown error'));
                }
            })
            .catch(error => {
                showFlowAlert('Error: ' + error.message);
            });
    }

    // Attach form submit handler
    document.getElementById('reviewForm').addEventListener('submit', saveReviewChanges);

    // Archive Applicant (replaces Delete)
    function confirmDelete() {
        if (!currentApplicant) return;

        const name = currentApplicant.fullName;
        const ref = currentApplicant.referenceNumber;

        showNoticeModal({
            title: 'Archive this applicant record?',
            message: `Reference: ${ref}\n\nThe applicant will be moved to the Archives list and will NOT be deleted.`,
            type: 'warning',
            primaryText: 'OK',
            secondaryText: 'Cancel',
            applicantName: name,
            onPrimary: () => {
                const formData = new FormData();
                formData.append('csrfmiddlewaretoken', getCsrfToken());
                formData.append('applicant_id', currentApplicant.applicantId || currentApplicant.id);
                formData.append('channel', currentApplicant.channel);
                formData.append('formally_archive', 'true');  // signals the view to set formally_archived=True

                fetch(window.APPLICANTS_CONFIG.proceedToApplicationsUrl, {
                    method: 'POST',
                    body: formData
                })
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            showFlowAlert('Applicant archived successfully. Redirecting to Archives...', 'Success', null, 'success');
                            closeReviewModal();
                            setTimeout(function () {
                                window.location.href = window.APPLICANTS_CONFIG.archiveListUrl;
                            }, 1200);
                        } else {
                            showFlowAlert('Error: ' + (data.error || 'Unknown error'));
                        }
                    })
                    .catch(error => {
                        showFlowAlert('Error: ' + error.message);
                    });
            }
        });
    }


    let dateOfBirthPicker = null;
    let ejectionDatePicker = null;

    function syncRegistrationDisplacementPanels() {
        const selectEl = document.querySelector('#addApplicantForm select[name="displacement_reason"]');
        const v = selectEl ? selectEl.value : '';
        const danger = document.getElementById('registrationDispDanger');
        const ejected = document.getElementById('registrationDispEjected');
        const relocated = document.getElementById('registrationDispRelocated');
        if (danger) danger.hidden = v !== 'danger_zone';
        if (ejected) ejected.hidden = v !== 'ejected';
        if (relocated) relocated.hidden = v !== 'relocated';
    }

    function openAddModal() {
        const modal = document.getElementById('addModal');
        if (modal) {
            modal.classList.add('active');
            // Keep sidebar accessible — offset modal by current sidebar width
            // Only apply on large screens (sidebar is transformed off-screen on mobile)
            const sidebar = document.querySelector('.sidebar');
            if (sidebar && window.innerWidth >= 1024) {
                const sidebarWidth = sidebar.getBoundingClientRect().width;
                modal.style.left = sidebarWidth + 'px';
            } else {
                modal.style.left = '';
            }
        }
        /* Init Flatpickr after modal is painted (hidden-modal init breaks layout/positioning). */
        requestAnimationFrame(function () {
            requestAnimationFrame(function () {
                syncDateOfBirthMaxToToday();
            });
        });
        // Initialize household members
        householdMemberCount = 1;
        renderHouseholdMembers();
        queueDuplicatePreviewCheck();
        syncRegistrationDisplacementPanels();
    }

    function closeAddModal() {
        const modal = document.getElementById('addModal');
        const form = document.getElementById('addApplicantForm');
        if (dateOfBirthPicker) {
            try {
                dateOfBirthPicker.destroy();
            } catch (_e) { /* noop */ }
            dateOfBirthPicker = null;
        }
        if (ejectionDatePicker) {
            try {
                ejectionDatePicker.destroy();
            } catch (_e) { /* noop */ }
            ejectionDatePicker = null;
        }
        if (modal) modal.classList.remove('active');
        if (form) form.reset();
        hideDuplicatePreview();
        syncRegistrationDisplacementPanels();
    }

    let duplicatePreviewTimer = null;
    let duplicatePreviewInFlight = 0;
    let duplicatePreviewCurrent = null;

    function hideDuplicatePreview() {
        const box = document.getElementById('duplicatePreview');
        const text = document.getElementById('duplicatePreviewText');
        const openBtn = document.getElementById('duplicateOpenBtn');
        if (box) box.style.display = 'none';
        if (text) text.textContent = '';
        if (openBtn) openBtn.style.display = 'none';
        duplicatePreviewCurrent = null;
    }

    function renderDuplicatePreview(data) {
        const box = document.getElementById('duplicatePreview');
        const text = document.getElementById('duplicatePreviewText');
        if (!box || !text) return;
        if (!data || !data.duplicate) {
            hideDuplicatePreview();
            return;
        }
        duplicatePreviewCurrent = data;
        text.textContent = `Record: ${data.reference_number} (${data.full_name}). Current location: ${data.location}. Status: ${data.status}. Last handled by: ${data.handled_by}.`;
        const openBtn = document.getElementById('duplicateOpenBtn');
        if (openBtn) openBtn.style.display = 'inline-flex';
        box.style.display = 'block';
    }

    function openDuplicatePreviewRecord() {
        if (!duplicatePreviewCurrent || !duplicatePreviewCurrent.record_id) return;

        const targetId = String(duplicatePreviewCurrent.record_id);
        const idx = applicantsData.findIndex(app => {
            const appId = String(app.applicantId || app.id || '');
            return appId === targetId;
        });

        if (idx >= 0) {
            closeAddModal();
            setTimeout(() => openReviewModal(idx), 50);
            return;
        }

        if (duplicatePreviewCurrent.can_open_in_intake) {
            showNoticeModal({
                title: 'Record Not Visible',
                message: 'Matching record is in Intake, but it is not visible in the current list. Refresh the page, then try again.',
                type: 'warning',
            });
            return;
        }

        showNoticeModal({
            title: 'Record Not Available in Intake',
            message: 'This record has already moved to another module and cannot be opened in Intake review.',
            type: 'warning',
        });
    }

    function queueDuplicatePreviewCheck() {
        if (duplicatePreviewTimer) clearTimeout(duplicatePreviewTimer);
        duplicatePreviewTimer = setTimeout(runDuplicatePreviewCheck, 300);
    }

    function runDuplicatePreviewCheck() {
        const lastName = (document.getElementById('lastName')?.value || '').trim();
        const firstName = (document.getElementById('firstName')?.value || '').trim();
        const dateOfBirth = (document.getElementById('dateOfBirth')?.value || '').trim();
        const barangay = (document.getElementById('barangay')?.value || '').trim();

        if (!lastName || !firstName || !dateOfBirth || !barangay) {
            hideDuplicatePreview();
            return;
        }

        const requestId = ++duplicatePreviewInFlight;
        const params = new URLSearchParams({
            last_name: lastName,
            first_name: firstName,
            date_of_birth: dateOfBirth,
            barangay: barangay,
        });

        fetch(`${duplicatePreviewUrl}?${params.toString()}`, {
            method: 'GET',
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
        })
            .then(response => response.json())
            .then(data => {
                if (requestId !== duplicatePreviewInFlight) return;
                if (!data.success) {
                    hideDuplicatePreview();
                    return;
                }
                renderDuplicatePreview(data);
            })
            .catch(() => {
                if (requestId !== duplicatePreviewInFlight) return;
                hideDuplicatePreview();
            });
    }

    let householdMemberCount = 0;

    function updateHouseholdSize() {
        // Count filled household members (at least one field has data)
        let filledCount = 0;
        for (let i = 1; i <= householdMemberCount; i++) {
            const nameInput = document.querySelector(`input[name="hh_member_${i}_name"]`);
            if (nameInput && nameInput.value.trim()) {
                filledCount++;
            }
        }
        // Total = applicant (1) + filled members
        const totalSize = 1 + filledCount;
    const householdSizeInput = document.getElementById('householdSize');
    if (householdSizeInput) householdSizeInput.value = totalSize;
    }

    function renderHouseholdMembers() {
        const container = document.getElementById('householdMembersContainer');
        container.innerHTML = '';

        for (let i = 1; i <= householdMemberCount; i++) {
            const memberDiv = document.createElement('div');
            memberDiv.id = `hhMember${i}`;
            memberDiv.className = 'hh-member-row';
            memberDiv.innerHTML = `
                <div class="form-group hh-member-name-span">
                    <label class="form-label">Full name</label>
                    <input type="text" class="form-input hh-member-field" placeholder="Surname, given name, extension" name="hh_member_${i}_name" maxlength="30" minlength="2" onchange="updateHouseholdSize()" autocomplete="name">
                </div>
                <div class="form-group">
                    <label class="form-label">Relationship</label>
                    <select class="form-select hh-member-field" name="hh_member_${i}_relationship" onchange="updateHouseholdSize()">
                        <option value="">— Select —</option>
                        <option value="spouse">Spouse</option>
                        <option value="son">Son</option>
                        <option value="daughter">Daughter</option>
                        <option value="mother">Mother</option>
                        <option value="father">Father</option>
                        <option value="uncle">Uncle</option>
                        <option value="aunt">Aunt</option>
                        <option value="grandfather">Grandfather</option>
                        <option value="grandmother">Grandmother</option>
                        <option value="grandchild">Grandchild</option>
                        <option value="live_in_partner">Live-in Partner</option>
                        <option value="other">Other relative</option>
                    </select>
                </div>
                <div class="form-group">
                    <label class="form-label">Age</label>
                    <input type="number" class="form-input hh-member-field" placeholder="Years" name="hh_member_${i}_age" min="0" max="120" onchange="updateHouseholdSize()">
                </div>
                <div class="form-group">
                    <label class="form-label">Sex</label>
                    <div class="hh-sex-group">
                        <label><input type="radio" name="hh_member_${i}_sex" value="male"> Male</label>
                        <label><input type="radio" name="hh_member_${i}_sex" value="female"> Female</label>
                    </div>
                </div>
                <div class="form-group">
                    <label class="form-label">Civil Status</label>
                    <select class="form-select hh-member-field" name="hh_member_${i}_status" onchange="updateHouseholdSize()">
                        <option value="">— Select —</option>
                        <option value="single">Single</option>
                        <option value="married">Married</option>
                        <option value="widowed">Widowed</option>
                        <option value="divorced">Divorced</option>
                        <option value="separated">Separated</option>
                        <option value="common_law">Common-law</option>
                    </select>
                </div>
                <div class="form-group">
                    <label class="form-label">Contact (Opt)</label>
                    <input type="tel" class="form-input hh-member-field ph-phone" placeholder="09XXXXXXXXXX" maxlength="11" inputmode="numeric" autocomplete="tel-national" name="hh_member_${i}_contact">
                    <span class="hh-member-help">11 digits only</span>
                </div>
                <div class="form-group hh-member-remove-cell">
                    <label class="form-label">&nbsp;</label>
                    <button type="button" onclick="deleteHouseholdMember(${i})" class="tha-reg-remove-member" title="Remove this member">
                        <span class="btn-icon-block">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                                <polyline points="3 6 5 6 21 6"></polyline>
                                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                            </svg>
                        </span>
                        <span>Remove</span>
                    </button>
                </div>
            `;
            container.appendChild(memberDiv);
        }
        initializePhoneInputs();
        container.querySelectorAll('input[name^="hh_member_"][name$="_name"]').forEach((el) => {
            attachUppercaseField(el);
        });
        updateHouseholdSize();
    }

    function addHouseholdMember() {
        householdMemberCount++;
        renderHouseholdMembers();
    }

    function deleteHouseholdMember(index) {
        if (householdMemberCount <= 1) {
            showFlowAlert('The last household member row cannot be removed. Clear the fields on that row if it is not used.');
            return;
        }
        householdMemberCount--;
        renderHouseholdMembers();
    }


    /** Date inputs: material-style Flatpickr with native fallback. */
    function syncDateOfBirthMaxToToday() {
        const today = new Date();
        const dobEl = document.getElementById('dateOfBirth');
        const ejectEl = document.getElementById('registrationEjectionDate');

        if (window.flatpickr) {
            if (dobEl) {
                if (!dateOfBirthPicker) {
                    dateOfBirthPicker = flatpickr(dobEl, {
                        appendTo: document.body,
                        dateFormat: 'Y-m-d',
                        altInput: true,
                        altFormat: 'd/m/Y',
                        altInputClass: 'form-input',
                        allowInput: true,
                        disableMobile: true,
                        closeOnSelect: true,
                        maxDate: today,
                        onReady: function (_selected, _dateStr, fp) {
                            if (fp.altInput) {
                                fp.altInput.placeholder = 'dd/mm/yyyy';
                                fp.altInput.setAttribute('aria-label', 'Date of birth');
                            }
                        },
                        onChange: function (_selected, _dateStr, fp) {
                            calculateAge();
                        },
                    });
                } else {
                    dateOfBirthPicker.set('maxDate', today);
                }
            }

            if (ejectEl) {
                if (!ejectionDatePicker) {
                    ejectionDatePicker = flatpickr(ejectEl, {
                        appendTo: document.body,
                        dateFormat: 'Y-m-d',
                        altInput: true,
                        altFormat: 'd/m/Y',
                        altInputClass: 'form-input',
                        allowInput: true,
                        disableMobile: true,
                        closeOnSelect: true,
                        maxDate: today,
                        onReady: function (_selected, _dateStr, fp) {
                            if (fp.altInput) {
                                fp.altInput.placeholder = 'dd/mm/yyyy';
                                fp.altInput.setAttribute('aria-label', 'Date of notice or ejection');
                            }
                        },
                    });
                } else {
                    ejectionDatePicker.set('maxDate', today);
                }
            }
            return;
        }

        const y = today.getFullYear();
        const m = String(today.getMonth() + 1).padStart(2, '0');
        const day = String(today.getDate()).padStart(2, '0');
        const maxValue = y + '-' + m + '-' + day;

        if (dobEl) {
            dobEl.setAttribute('type', 'date');
            dobEl.max = maxValue;
            dobEl.setAttribute('aria-label', 'Date of birth');
        }
        if (ejectEl) {
            ejectEl.setAttribute('type', 'date');
            ejectEl.max = maxValue;
            ejectEl.setAttribute('aria-label', 'Date of notice or ejection');
        }
    }

    // Auto-calculate age from date of birth (optional; no eligibility gates).
    function calculateAge() {
        const dobInput = document.getElementById('dateOfBirth');
        const ageInput = document.getElementById('age');
        if (!dobInput || !ageInput) return null;

        if (!dobInput.value) {
            ageInput.value = '';
            return null;
        }

        const dob = new Date(dobInput.value);
        if (Number.isNaN(dob.getTime())) {
            ageInput.value = '';
            return null;
        }

        const today = new Date();
        let age = today.getFullYear() - dob.getFullYear();
        const monthDiff = today.getMonth() - dob.getMonth();
        if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < dob.getDate())) {
            age--;
        }

        if (age < 0) {
            ageInput.value = '';
            return null;
        }

        ageInput.value = age;
        return age;
    }

    /** First letter uppercase only; keeps pasted casing for the rest. */
    function leadingCapital(str) {
        const s = String(str ?? '').trim();
        if (!s) return '';
        return s.charAt(0).toUpperCase() + s.slice(1);
    }

    /** Applicant identity names: entire field uppercase while typing or on paste. */
    function attachUppercaseField(el) {
        if (!el) return;
        const toUpperLive = () => {
            const v = el.value;
            if (!v) return;
            const fixed = v.toUpperCase();
            if (fixed === v) return;
            const pos = el.selectionStart;
            const end = el.selectionEnd;
            el.value = fixed;
            try {
                el.setSelectionRange(pos, end);
            } catch (err) { /* ignore */ }
        };
        const normalizeBlur = () => {
            const next = String(el.value || '').trim().toUpperCase();
            if (el.value !== next) el.value = next;
        };
        el.addEventListener('input', toUpperLive);
        el.addEventListener('blur', normalizeBlur);
        el.addEventListener('paste', () => requestAnimationFrame(toUpperLive));
    }

    function attachLeadingCapitalField(el) {
        if (!el) return;
        /** While typing or after paste: uppercase first character only; keep caret stable. */
        const capitalizeFirstLive = () => {
            const v = el.value;
            if (!v.length) return;
            const c0 = v.charAt(0);
            const up = c0.toUpperCase();
            if (up === c0) return;
            const fixed = up + v.slice(1);
            const pos = el.selectionStart;
            const end = el.selectionEnd;
            el.value = fixed;
            try {
                el.setSelectionRange(pos, end);
            } catch (err) { /* ignore */ }
        };
        /** On blur: trim edges then capitalize first visible character (paste + leadingCapital). */
        const normalizeBlur = () => {
            const next = leadingCapital(el.value);
            if (el.value !== next) el.value = next;
        };
        el.addEventListener('input', capitalizeFirstLive);
        el.addEventListener('blur', normalizeBlur);
        el.addEventListener('paste', () => requestAnimationFrame(capitalizeFirstLive));
    }

    function submitAddApplicant(event) {
        event.preventDefault();
        const form = document.getElementById('addApplicantForm');
        const channel = getInputValue('channelInput');

        const sentenceCase = (str) => {
            if (!str) return str;
            const s = String(str).trim();
            if (!s) return '';
            return s.charAt(0).toUpperCase() + s.slice(1).toLowerCase();
        };

        const uppercaseName = (str) => String(str ?? '').trim().toUpperCase();

        const lnEl = document.getElementById('lastName');
        const fnEl = document.getElementById('firstName');
        const mnEl = document.getElementById('middleName');
        const exEl = document.getElementById('extensionName');
        const lastName = uppercaseName(lnEl ? lnEl.value : '');
        const firstName = uppercaseName(fnEl ? fnEl.value : '');
        const middleName = uppercaseName(mnEl ? mnEl.value : '');
        const extensionName = uppercaseName(exEl ? exEl.value : '');
        if (lnEl) lnEl.value = lastName;
        if (fnEl) fnEl.value = firstName;
        if (mnEl) mnEl.value = middleName;
        if (exEl) exEl.value = extensionName;

        const addrEl = document.getElementById('presentAddress');
        const pobEl = document.getElementById('placeOfBirth');
        const spouseEl = document.getElementById('spouseName');
        if (addrEl) addrEl.value = uppercaseName(addrEl.value);
        if (pobEl) pobEl.value = uppercaseName(pobEl.value);
        if (spouseEl) spouseEl.value = uppercaseName(spouseEl.value);

        const occEl = document.getElementById('occupation');
        if (occEl) occEl.value = uppercaseName(occEl.value);

        const hzLocEl = document.getElementById('registrationDangerZoneLocation');
        const projNameEl = document.getElementById('registrationProjectName');
        if (hzLocEl) hzLocEl.value = uppercaseName(hzLocEl.value);
        if (projNameEl) projNameEl.value = uppercaseName(projNameEl.value);

        for (let i = 1; i <= householdMemberCount; i++) {
            const hn = document.querySelector(`input[name="hh_member_${i}_name"]`);
            if (hn) hn.value = uppercaseName(hn.value);
        }

        let fullName = `${lastName}, ${firstName}${middleName ? ' ' + middleName : ''}`;
        if (extensionName) {
            fullName = `${fullName}, ${extensionName}`;
        }

        // Remove commas from income fields before creating FormData
        const incomeFields = form.querySelectorAll('input[name*="income"]');
        incomeFields.forEach(field => {
            field.value = field.value.replace(/,/g, '');
        });

        const formData = new FormData(form);

        // Add combined full_name (stored display field capped at model max_length)
        formData.set('full_name', fullName.slice(0, 30));

        if (formData.has('current_address')) {
            formData.set('current_address', uppercaseName(formData.get('current_address')));
        }
        if (formData.has('place_of_birth')) {
            formData.set('place_of_birth', uppercaseName(formData.get('place_of_birth')));
        }
        if (formData.has('spouse_name')) {
            formData.set('spouse_name', uppercaseName(formData.get('spouse_name')));
        }

        // Validate phone number
        const phoneNumber = document.getElementById('phoneNumber');
        if (phoneNumber && phoneNumber.value) {
            const phoneClean = phoneNumber.value.replace(/\D/g, '');
            if (phoneClean.length !== 11 || !phoneClean.startsWith('09')) {
                showNoticeModal({
                    title: 'Invalid Applicant Mobile Number',
                    message: 'Required format: 09XXXXXXXXXX (11 digits).',
                    type: 'warning',
                });
                return;
            }
        }

        // Validate years residing in Talisay (2 digits max; office minimum 5 years)
        const yearsResiding = document.getElementById('yearsResiding');
        const yearsResidingRaw = yearsResiding ? String(yearsResiding.value || '').trim() : '';
        const yearsResidingValue = yearsResiding ? parseInt(yearsResidingRaw, 10) : NaN;
        if (!yearsResiding || !/^\d{1,2}$/.test(yearsResidingRaw) || !Number.isFinite(yearsResidingValue)) {
            showNoticeModal({
                title: 'Residency Requirement',
                message: 'Enter years of residence as a whole number (2 digits only, 5–99).',
                type: 'warning',
            });
            if (yearsResiding) {
                yearsResiding.setCustomValidity('Enter 1–2 digits (5–99 years).');
                yearsResiding.reportValidity();
            }
            return;
        }
        if (yearsResidingValue > MODULE1_MAX_YEARS_RESIDING) {
            showNoticeModal({
                title: 'Residency Requirement',
                message: 'Years of residence must be at most 2 digits (99).',
                type: 'warning',
            });
            if (yearsResiding) {
                yearsResiding.setCustomValidity('Maximum 99 years (2 digits).');
                yearsResiding.reportValidity();
            }
            return;
        }
        if (yearsResidingValue <= 4) {
            showNoticeModal({
                title: 'Residency Requirement',
                message: 'Applicants with 4 years or below residency in Talisay City are not accepted. Minimum is 5 years.',
                type: 'warning',
            });
            if (yearsResiding) {
                yearsResiding.setCustomValidity('Office requirement: Minimum residency is 5 years in Talisay City.');
                yearsResiding.reportValidity();
            }
            return;
        }
        yearsResiding.setCustomValidity('');

        // Office requirement: applicant must be a registered voter in Talisay City.
        const voterSelection = String(formData.get('is_registered_voter_talisay') || '').trim().toLowerCase();
        if (voterSelection !== 'true') {
            showNoticeModal({
                title: 'Voter Requirement',
                message: 'Applicants must be registered voters in Talisay City before you proceed with registration.',
                type: 'warning',
            });
            return;
        }

        // Office requirement: maximum gross monthly household income is PHP 10,000.
        const monthlyIncomeRaw = String(formData.get('monthly_income') || '').replace(/,/g, '').trim();
        const monthlyIncomeValue = parseFloat(monthlyIncomeRaw);
        if (!Number.isFinite(monthlyIncomeValue) || monthlyIncomeValue > MODULE1_INCOME_CEILING) {
            showNoticeModal({
                title: 'Income Requirement',
                message: 'Applicants with gross monthly household income above PHP 10,000 are not accepted.',
                type: 'warning',
            });
            const monthlyIncome = document.getElementById('monthlyIncome');
            if (monthlyIncome) {
                monthlyIncome.setCustomValidity('Office requirement: Maximum gross monthly household income is PHP 10,000.');
                monthlyIncome.reportValidity();
            }
            return;
        }
        const monthlyIncome = document.getElementById('monthlyIncome');
        if (monthlyIncome) monthlyIncome.setCustomValidity('');

        // Property ownership declaration is required for Module 2.2.
        const propertyOwnershipSelected = formData.get('has_property_in_talisay');
        if (!propertyOwnershipSelected || !['yes', 'no'].includes(String(propertyOwnershipSelected).toLowerCase())) {
            showNoticeModal({
                title: 'Property Ownership Required',
                message: 'Please select Yes or No for property ownership in Talisay City.',
                type: 'warning',
            });
            return;
        }

        const civilStatusSelected = String(formData.get('civil_status') || '').trim();
        if (!civilStatusSelected) {
            showNoticeModal({
                title: 'Civil Status Required',
                message: 'Please select the applicant\'s civil status.',
                type: 'warning',
            });
            const civilStatusEl = document.getElementById('civilStatus');
            if (civilStatusEl) {
                civilStatusEl.setCustomValidity('Civil status is required.');
                civilStatusEl.reportValidity();
            }
            return;
        }
        const civilStatusEl = document.getElementById('civilStatus');
        if (civilStatusEl) civilStatusEl.setCustomValidity('');

        calculateAge();

        // Validate household members - if any field is filled, all must be filled
        for (let i = 1; i <= householdMemberCount; i++) {
            const nameField = document.querySelector(`input[name="hh_member_${i}_name"]`);
            const relationshipField = document.querySelector(`select[name="hh_member_${i}_relationship"]`);
            const ageField = document.querySelector(`input[name="hh_member_${i}_age"]`);
            const statusField = document.querySelector(`select[name="hh_member_${i}_status"]`);
            const contactField = document.querySelector(`input[name="hh_member_${i}_contact"]`);

            const hasName = nameField && nameField.value.trim();
            const hasRelationship = relationshipField && relationshipField.value.trim();
            const hasAge = ageField && ageField.value.trim();
            const hasStatus = statusField && statusField.value.trim();

            const fieldsWithData = [hasName, hasRelationship, hasAge, hasStatus].filter(v => v).length;

            // If any field has data, all must be filled
            if (fieldsWithData > 0 && fieldsWithData < 4) {
                showNoticeModal({
                    title: `Household Member ${i}`,
                    message: 'Either fill all fields or delete this member row.',
                    type: 'warning',
                });
                return;
            }

            if (contactField && contactField.value.trim()) {
                const contactClean = contactField.value.replace(/\D/g, '');
                if (contactClean.length !== 11 || !contactClean.startsWith('09')) {
                    showNoticeModal({
                        title: `Household Member ${i}`,
                        message: 'Contact number must be 11 digits and start with 09.',
                        type: 'warning',
                    });
                    return;
                }
            }
        }

        const displacementReason = (formData.get('displacement_reason') || '').trim();
        if (!displacementReason) {
            showNoticeModal({
                title: 'Applicant Situation',
                message: 'Please select Option A, B, C, or D under Applicant Situation.',
                type: 'warning',
            });
            return;
        }
        if (displacementReason === 'danger_zone') {
            const hz = (document.getElementById('registrationDangerZoneType')?.value || '').trim();
            const loc = (document.getElementById('registrationDangerZoneLocation')?.value || '').trim().replace(/\s+/g, ' ');
            if (!hz) {
                showNoticeModal({ title: 'Hazard classification', message: 'Select a hazard type for Option A.', type: 'warning' });
                return;
            }
            if (!loc || loc.length < 12) {
                showNoticeModal({
                    title: 'Hazard location',
                    message: 'Enter a specific hazard location (at least 12 characters), e.g. sitio, landmark, river segment.',
                    type: 'warning',
                });
                return;
            }
        } else if (displacementReason === 'ejected') {
            const ej = (document.getElementById('registrationEjectionType')?.value || '').trim();
            if (!ej) {
                showNoticeModal({ title: 'Ejection classification', message: 'Select an ejection type for Option B.', type: 'warning' });
                return;
            }
        } else if (displacementReason === 'relocated') {
            const pn = (document.getElementById('registrationProjectName')?.value || '').trim();
            if (!pn) {
                showNoticeModal({ title: 'Project designation', message: 'Enter the government project or infrastructure designation for Option C.', type: 'warning' });
                return;
            }
        }

        // Store globally for the confirm submission modal
        pendingRegistrationFormData = formData;

        // Populate confirm modal fields

        // --- Identity ---
        const confirmLastName = document.getElementById('confirmRegLastName');
        if (confirmLastName) confirmLastName.textContent = formData.get('last_name') || 'N/A';
        const confirmFirstName = document.getElementById('confirmRegFirstName');
        if (confirmFirstName) confirmFirstName.textContent = formData.get('first_name') || 'N/A';
        const confirmMiddleName = document.getElementById('confirmRegMiddleName');
        if (confirmMiddleName) confirmMiddleName.textContent = formData.get('middle_name') || 'N/A';
        const confirmExtName = document.getElementById('confirmRegExtName');
        if (confirmExtName) confirmExtName.textContent = formData.get('extension_name') || 'N/A';

        const confirmSex = document.getElementById('confirmRegSex');
        if (confirmSex) {
            const sexRadios = document.getElementsByName('sex');
            let selectedSex = formData.get('sex') === 'M' ? 'Male' : 'Female';
            for (const radio of sexRadios) {
                if (radio.checked && radio.nextElementSibling) {
                    selectedSex = radio.nextElementSibling.textContent.trim();
                    break;
                }
            }
            confirmSex.textContent = selectedSex || 'N/A';
        }

        const confirmCivil = document.getElementById('confirmRegCivil');
        const civilSelect = document.getElementById('civilStatus');
        if (confirmCivil) {
            confirmCivil.textContent = civilSelect && civilSelect.selectedIndex > 0 ? civilSelect.options[civilSelect.selectedIndex].text : 'N/A';
        }

        const confirmVoter = document.getElementById('confirmRegVoter');
        if (confirmVoter) confirmVoter.textContent = formData.get('is_registered_voter_talisay') === 'true' ? 'Yes' : (formData.get('is_registered_voter_talisay') === 'false' ? 'No' : 'N/A');

        const confirmProperty = document.getElementById('confirmRegProperty');
        if (confirmProperty) confirmProperty.textContent = formData.get('has_property_in_talisay') === 'yes' ? 'Yes' : (formData.get('has_property_in_talisay') === 'no' ? 'No' : 'N/A');

        const confirmYears = document.getElementById('confirmRegYears');
        if (confirmYears) confirmYears.textContent = formData.get('years_residing') || 'N/A';

        const confirmContact = document.getElementById('confirmRegContact');
        if (confirmContact) confirmContact.textContent = formData.get('phone_number') || 'N/A';

        const confirmDob = document.getElementById('confirmRegDob');
        if (confirmDob) confirmDob.textContent = formData.get('date_of_birth') || 'N/A';

        const confirmAge = document.getElementById('confirmRegAge');
        if (confirmAge) confirmAge.textContent = formData.get('age') || 'N/A';

        const confirmAddress = document.getElementById('confirmRegAddress');
        if (confirmAddress) confirmAddress.textContent = formData.get('current_address') || 'N/A';

        const confirmBrgy = document.getElementById('confirmRegBrgy');
        if (confirmBrgy) confirmBrgy.textContent = formData.get('barangay') || 'N/A';

        const confirmPob = document.getElementById('confirmRegPob');
        if (confirmPob) confirmPob.textContent = formData.get('place_of_birth') || 'N/A';

        const confirmSpouse = document.getElementById('confirmRegSpouse');
        if (confirmSpouse) confirmSpouse.textContent = formData.get('spouse_name') || 'N/A';

        const confirmSpousePhone = document.getElementById('confirmRegSpousePhone');
        if (confirmSpousePhone) confirmSpousePhone.textContent = formData.get('spouse_phone') || 'N/A';

        // --- Household Members ---
        const confirmHousehold = document.getElementById('confirmRegHousehold');
        if (confirmHousehold) confirmHousehold.textContent = formData.get('household_size') || '1';

        const confirmMembersList = document.getElementById('confirmRegMembersList');
        if (confirmMembersList) {
            confirmMembersList.innerHTML = ''; // clear previous
            let memberItems = [];
            for (let i = 1; i <= householdMemberCount; i++) {
                const nameF = document.querySelector(`input[name="hh_member_${i}_name"]`);
                const relF = document.querySelector(`select[name="hh_member_${i}_relationship"]`);
                const ageF = document.querySelector(`input[name="hh_member_${i}_age"]`);
                const sexF = document.querySelector(`select[name="hh_member_${i}_sex"]`) || document.querySelector(`input[name="hh_member_${i}_sex"]:checked`);
                const statF = document.querySelector(`select[name="hh_member_${i}_status"]`);
                const contF = document.querySelector(`input[name="hh_member_${i}_contact"]`);

                if (nameF && nameF.value.trim()) {
                    let sexText = '';
                    if (sexF && sexF.options) {
                        sexText = sexF.selectedIndex > 0 ? sexF.options[sexF.selectedIndex].text : '';
                    } else if (sexF) {
                        sexText = sexF.value === 'M' ? 'Male' : (sexF.value === 'F' ? 'Female' : '');
                    }

                    let itemText = `<strong>${nameF.value}</strong>`;
                    let details = [];
                    if (relF && relF.selectedIndex > 0) details.push(relF.options[relF.selectedIndex].text);
                    if (ageF && ageF.value) details.push(ageF.value + ' yrs');
                    if (sexText) details.push(sexText);
                    if (statF && statF.selectedIndex > 0) details.push(statF.options[statF.selectedIndex].text);
                    if (contF && contF.value) details.push(contF.value);

                    if (details.length > 0) itemText += ` &mdash; <span style="color: #475569;">${details.join(', ')}</span>`;
                    memberItems.push(`<div class="rcm-member-row">${itemText}</div>`);
                }
            }
            if (memberItems.length > 0) {
                confirmMembersList.innerHTML = memberItems.join('');
            } else {
                confirmMembersList.innerHTML = '<div class="rcm-field" style="border-style: dashed;"><span style="color: #94a3b8; font-style: italic; font-size: 0.8rem;">No household members added.</span></div>';
            }
        }

        // --- Income ---
        const confirmOcc = document.getElementById('confirmRegOcc');
        if (confirmOcc) confirmOcc.textContent = formData.get('occupation') || 'N/A';

        const confirmEmpStatus = document.getElementById('confirmRegEmpStatus');
        const empSelect = document.getElementById('employmentStatus');
        if (confirmEmpStatus) {
            confirmEmpStatus.textContent = empSelect && empSelect.selectedIndex > 0 ? empSelect.options[empSelect.selectedIndex].text : 'N/A';
        }

        const confirmIncome = document.getElementById('confirmRegIncome');
        if (confirmIncome) {
            const income = formData.get('monthly_income') || '0';
            confirmIncome.textContent = '₱' + Number(income).toLocaleString();
        }

        // --- Situation ---
        const confirmSituation = document.getElementById('confirmRegSituation');
        if (confirmSituation) {
            const situation = formData.get('displacement_reason') || '';
            if (situation === 'danger_zone') {
                const hz = document.getElementById('registrationDangerZoneType');
                const hzText = hz && hz.selectedIndex > 0 ? hz.options[hz.selectedIndex].text : 'N/A';
                const loc = formData.get('danger_zone_location') || 'N/A';
                confirmSituation.innerHTML = `<strong>Option A: Danger Zone</strong><br><span style="color: #475569;">Hazard Type: ${hzText}<br>Location: ${loc}</span>`;
            } else if (situation === 'ejected') {
                const ej = document.getElementById('registrationEjectionType');
                const ejText = ej && ej.selectedIndex > 0 ? ej.options[ej.selectedIndex].text : 'N/A';
                confirmSituation.innerHTML = `<strong>Option B: Ejected/Evicted</strong><br><span style="color: #475569;">Ejection Type: ${ejText}</span>`;
            } else if (situation === 'relocated') {
                const pn = formData.get('project_name') || 'N/A';
                confirmSituation.innerHTML = `<strong>Option C: Relocated by Gov't</strong><br><span style="color: #475569;">Project Name: ${pn}</span>`;
            } else if (situation === 'not_abc') {
                confirmSituation.innerHTML = `<strong>Option D: None of A, B, or C</strong><br><span style="color: #475569;">Situation does not fall under danger zone, ejection, or government project.</span>`;
            }
        }

        const confirmModal = document.getElementById('registrationConfirmModal');
        if (confirmModal) confirmModal.style.display = 'flex';
    }

    let pendingRegistrationFormData = null;

    function closeRegistrationConfirmModal() {
        const modal = document.getElementById('registrationConfirmModal');
        if (modal) modal.style.display = 'none';
    }

    function executeRegistrationSubmit() {
        if (!pendingRegistrationFormData) return;

        // Close the confirm modal immediately
        closeRegistrationConfirmModal();

        let endpoint = window.APPLICANTS_CONFIG.walkinRegisterUrl;
        const csrfToken = getCsrfToken();

        fetch(endpoint, {
            method: 'POST',
            body: pendingRegistrationFormData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': csrfToken
            }
        })
            .then(response => {
                const contentType = response.headers.get('content-type');
                if (!contentType || !contentType.includes('application/json')) {
                    return response.text().then(text => {
                        throw new Error('Server returned HTML instead of JSON. Check console for details.');
                    });
                }
                return response.json();
            })
            .then(data => {
                if (data.success) {
                    closeAddModal();
                    const successLine = data.message || 'Applicant registered successfully.';
                    const registered = parseRegistrationSuccessMessage(successLine);
                    showNoticeModal({
                        title: 'Applicant Registered',
                        messageHtml: buildApplicantRegisteredSuccessHtml(registered.fullName),
                        allowHtml: true,
                        type: 'success',
                        celebration: true,
                        refPill: registered.referenceNumber || '',
                        onPrimary: () => { location.reload(); },
                    });
                } else {
                    const errorMsg = data.error || 'Unknown error occurred';
                    showNoticeModal({
                        title: 'Registration Error',
                        message: errorMsg,
                        type: 'error',
                    });
                }
            })
            .catch(error => {
                showNoticeModal({
                    title: 'Request Failed',
                    message: error.message,
                    type: 'error',
                });
            });
    }

    function populateAndOpenReviewModal(applicant) {
        /**
         * Populate the review modal with newly registered applicant data and open it.
         * Shows danger zone info only if applicant selected "Yes" for danger zone.
         */
        // Set header info
        document.getElementById('reviewName').textContent = applicant.fullName;
        document.getElementById('reviewReference').textContent = applicant.referenceNumber + ' · Reg. ' + applicant.dateRegistered;
        setInputValue('reviewApplicantId', applicant.id);
        setInputValue('reviewChannel', applicant.channel);

        // Channel B (walk-in hazard pathway) — API may use 'B' or 'danger_zone'
        if (applicant.channel === 'danger_zone' || applicant.channel === 'B') {
    const dangerZoneReviewSection = document.getElementById('dangerZoneReviewSection');
    if (dangerZoneReviewSection) dangerZoneReviewSection.style.display = 'block';

            // Basic info
            setInputValue('reviewFullNameB', applicant.fullName);
            setInputValue('reviewBarangayB', applicant.barangay);
            setInputValue('reviewIncomeB', formatIncomeInputValue(applicant.monthlyIncome));
            setInputValue('reviewHouseholdB', applicant.householdSize);
            setInputValue('reviewYearsB', applicant.yearsResiding);
            setInputValue('reviewPhoneB', applicant.phoneNumber);
            setInputValue('reviewAddressB', applicant.currentAddress);
            populateChannelBRegistrationMirror(applicant);

            // Update channel badge from hazard Yes/No (dangerZoneType set when Yes)
            const dangerZoneBadge = document.getElementById('reviewDangerZoneBadge');
            const channelBadge = document.getElementById('reviewChannelBadge');
            const eligibilityBadgeB = document.getElementById('reviewEligibilityBadgeB');

            if (channelBadge) {
                channelBadge.className = 'status-badge status-info';
                const declared = !!(applicant.dangerZoneType || applicant.danger_zone_type);
                channelBadge.style.background = declared ? '#fef3c7' : '#e0f2fe';
                channelBadge.style.color = declared ? '#92400e' : '#0369a1';
                channelBadge.style.border = declared ? '1px solid #fcd34d' : '1px solid #0ea5e9';
                channelBadge.textContent = channelBDisplayLabel(applicant);
            }

            // Eligibility badge based on Yes/No selection
            if (eligibilityBadgeB) {
                if (applicant.isInDangerZone) {
                    eligibilityBadgeB.className = 'status-badge status-warning';
                    eligibilityBadgeB.textContent = 'Pending CDRRMO verification';
                } else {
                    eligibilityBadgeB.className = 'status-badge status-info';
                    eligibilityBadgeB.textContent = 'Pending eligibility check';
                }
            }

            // CONDITIONALLY show danger zone info section
            const dangerZoneInfoSection = document.querySelector('.danger-zone-info');

            if (applicant.isInDangerZone) {
                // User selected "Yes" - show danger zone details
                if (dangerZoneInfoSection) dangerZoneInfoSection.style.display = 'block';

                setInputValue('reviewDangerType', applicant.dangerZoneType || '');

                // Set location field
                const locationInput = document.querySelector('input[name="danger_zone_location"]');
                if (locationInput) locationInput.value = applicant.dangerZoneLocation || '';

                // Set status badge
                const statusBadge = document.getElementById('reviewEligibilityBadgeB');
                if (statusBadge) {
                    statusBadge.className = 'status-badge status-warning';
                    statusBadge.textContent = 'Pending CDRRMO verification';
                }

                // Show CDRRMO Certification section when "Yes" is selected
                const cdrrmoSection = document.querySelector('.cdrrmo-certification-section');
                if (cdrrmoSection) cdrrmoSection.style.display = 'block';
            } else {
                // User selected "No" - hide danger zone details
                if (dangerZoneInfoSection) dangerZoneInfoSection.style.display = 'none';

                // Set status badge
                const statusBadge = document.getElementById('reviewEligibilityBadgeB');
                if (statusBadge) {
                    statusBadge.className = 'status-badge status-info';
                    statusBadge.textContent = 'Pending eligibility check';
                }

                // Hide CDRRMO Certification section when "No" is selected
                const cdrrmoSection = document.querySelector('.cdrrmo-certification-section');
                if (cdrrmoSection) cdrrmoSection.style.display = 'none';
            }

            // Populate Eligibility Checks (pass isInDangerZone flag)
            populateEligibilityChecksB(applicant, applicant.isInDangerZone);
        }

        // Show the modal
        const modal = document.getElementById('reviewModal');
        if (modal) {
            modal.style.display = 'flex';
        }

    }

    function selectChannel(channel) {
        // Update button states
        document.querySelectorAll('.channel-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.channel === channel);
        });

        // Update hidden input
        const channelInput = document.getElementById('channelInput');
        if (channelInput) channelInput.value = channel;

        // Get danger zone section
        const dangerZoneGroup = document.getElementById('dangerZoneGroup');
        const dangerZoneType = document.getElementById('dangerZoneType');
        const dangerZoneLocation = document.getElementById('dangerZoneLocation');
        const regularNote = document.getElementById('regularNote');
        const cdrrmoNote = document.getElementById('cdrrmoNote');

        if (channel === 'danger_zone') {
            // Show danger zone fields
            if (dangerZoneGroup) dangerZoneGroup.style.display = 'block';
            if (dangerZoneType) dangerZoneType.required = true;
            if (dangerZoneLocation) dangerZoneLocation.required = true;
            if (regularNote) regularNote.style.display = 'none';
            if (cdrrmoNote) cdrrmoNote.style.display = 'block';
        } else {
            // Hide danger zone fields
            if (dangerZoneGroup) dangerZoneGroup.style.display = 'none';
            if (dangerZoneType) dangerZoneType.required = false;
            if (dangerZoneLocation) dangerZoneLocation.required = false;
            if (regularNote) regularNote.style.display = 'block';
            if (cdrrmoNote) cdrrmoNote.style.display = 'none';
        }
    }

    // Document checkbox styling
    document.addEventListener('DOMContentLoaded', function () {
        document.querySelectorAll('.document-item input').forEach(checkbox => {
            checkbox.addEventListener('change', function () {
                this.parentElement.classList.toggle('checked', this.checked);
            });
        });

        // Ensure number income field never contains comma-separated values.
        const incomeInput = document.getElementById('monthlyIncome');
        if (incomeInput) {
            attachNumberIncomeSanitizer(incomeInput);
        }

        ['lastName', 'firstName', 'dateOfBirth', 'barangay'].forEach(id => {
            const el = document.getElementById(id);
            if (!el) return;
            const eventName = (id === 'barangay' || id === 'dateOfBirth') ? 'change' : 'input';
            el.addEventListener(eventName, queueDuplicatePreviewCheck);
            el.addEventListener('blur', queueDuplicatePreviewCheck);
        });

        [
            'lastName', 'firstName', 'middleName', 'extensionName',
            'presentAddress', 'placeOfBirth', 'spouseName', 'occupation',
            'registrationDangerZoneLocation', 'registrationProjectName',
        ].forEach(id => {
            attachUppercaseField(document.getElementById(id));
        });
    });

    // Add another ISF record entry for Channel A
    let isfCount = 1;
    function addISFRecord() {
        isfCount++;
        const container = document.getElementById('isfRecordsContainer');
        const newEntry = document.createElement('div');
        newEntry.className = 'isf-record-entry';
        newEntry.dataset.isfIndex = isfCount;
        newEntry.style.cssText = 'background: #f8fafc; border: 1px solid #e2e8f0; padding: 1rem; border-radius: 0.5rem; margin-bottom: 0.75rem;';
        newEntry.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
                <span style="font-weight: 600; color: #1e293b; font-size: 0.875rem;">ISF #${isfCount}</span>
                <button type="button" onclick="removeISFRecord(this)" style="background: none; border: none; cursor: pointer; color: #ef4444; font-size: 0.75rem; display: flex; align-items: center; gap: 0.25rem;">
                    <svg style="width: 0.875rem; height: 0.875rem;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <line x1="18" y1="6" x2="6" y2="18"></line>
                        <line x1="6" y1="6" x2="18" y2="18"></line>
                    </svg>
                    Remove
                </button>
            </div>
            <div class="form-grid">
                <div class="form-group" style="grid-column: span 2;">
                    <label class="form-label">Full Name *</label>
                    <input type="text" class="form-input" placeholder="Juan Dela Cruz" name="isf_name[]" required>
                </div>
                <div class="form-group">
                    <label class="form-label">Household Members *</label>
                    <input type="number" class="form-input" placeholder="5" name="isf_household[]" min="1" value="1" required>
                </div>
                <div class="form-group">
                    <label class="form-label">Monthly Income (₱) *</label>
                    <input type="text" class="form-input" inputmode="decimal" pattern="[0-9,]*" placeholder="8000" name="isf_income[]" required>
                </div>
                <div class="form-group" style="grid-column: span 2;">
                    <label class="form-label">Years Residing *</label>
                    <input type="number" class="form-input" placeholder="3" name="isf_years[]" min="0" required>
                </div>
                <div class="form-group" style="grid-column: span 2;">
                    <label class="form-label">Contact Number</label>
                    <input type="tel" class="form-input ph-phone" placeholder="09XXXXXXXXXX" pattern="09[0-9]{9}" name="isf_phone[]">
                    <div class="form-help" style="font-size: 0.75rem; color: #64748b; margin-top: 0.25rem;">11 digits: 09XXXXXXXXXX (optional)</div>
                </div>
            </div>
        `;
        container.appendChild(newEntry);
    }

    function removeISFRecord(button) {
        const entry = button.closest('.isf-record-entry');
        const container = document.getElementById('isfRecordsContainer');

        // Don't remove if it's the only one
        if (container.querySelectorAll('.isf-record-entry').length > 1) {
            entry.remove();
            // Renumber remaining entries
            const entries = container.querySelectorAll('.isf-record-entry');
            entries.forEach((e, index) => {
                e.dataset.isfIndex = index + 1;
                e.querySelector('span').textContent = `ISF #${index + 1}`;
            });
            isfCount = entries.length;
        } else {
            showFlowAlert('At least one ISF record is required.');
        }
    }

    // Pass applicant data as JSON for onclick handler
    function escapeHtml(text) {
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };
        return text.replace(/[&<>"']/g, m => map[m]);
    }

    // Export to CSV
    function exportToCSV() {
        const channelFilterEl = document.getElementById('filterChannel');
        const barangayFilterEl = document.getElementById('filterBarangay');

        const channelFilter = channelFilterEl ? channelFilterEl.value : 'all';
        const barangayFilter = barangayFilterEl ? barangayFilterEl.value : 'all';

        // Filter applicants based on current filters
        let filteredData = applicantsData.filter(app => {
            const matchChannel = channelFilter === 'all' || app.channel === channelFilter;
            const matchBarangay = barangayFilter === 'all' || app.barangay === barangayFilter;
            return matchChannel && matchBarangay;
        });

        if (filteredData.length === 0) {
            showFlowAlert('No data to export with current filters.');
            return;
        }

        // CSV header
        const headers = [
            'Reference #',
            'Full Name',
            'Channel',
            'Barangay',
            'Monthly Income',
            'Household Size',
            'Years Residing',
            'Phone Number',
            'Current Address',
            'Eligibility Status',
            'Queue Type',
            'Queue Position',
            'Documents Submitted',
            'Registration Date',
            'Handled By'
        ];

        // CSV rows
        const rows = filteredData.map(app => [
            app.referenceNumber || '',
            app.fullName || '',
            app.channel === 'A' ? 'Channel A - Landowner' :
                (app.channel === 'B' || app.channel === 'danger_zone') ? channelBDisplayLabel(app) : 'Channel C - Walk-in',
            app.barangay || '',
            app.monthlyIncome || '',
            app.householdSize || '',
            app.yearsResiding || '',
            app.phoneNumber || '',
            (app.currentAddress || '').replace(/,/g, ';'),
            app.eligibilityStatus || '',
            app.queueType || 'N/A',
            app.queuePosition || '',
            `${app.docsCount || 0}/${app.docsTotal || 7}`,
            app.dateRegistered || '',
            app.handledBy || ''
        ]);

        // Build CSV content
        let csvContent = headers.join(',') + '\n';
        rows.forEach(row => {
            csvContent += row.map(cell => `"${String(cell).replace(/"/g, '""')}"`).join(',') + '\n';
        });

        // Download
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        const url = URL.createObjectURL(blob);
        link.setAttribute('href', url);
        link.setAttribute('download', `ISF_Applicants_${new Date().toISOString().split('T')[0]}.csv`);
        link.style.visibility = 'hidden';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }

    // ============================================================================
    // ISF REVIEW MODAL FUNCTIONS
    // ============================================================================

    let currentISFData = null;

    function loadISFData(applicantData) {
        // Load ISF data into the modal (direct data loading, no AJAX needed)
        if (!applicantData) {
            showFlowAlert('Error: No applicant data available');
            return;
        }
        currentISFData = applicantData;
        populateISFModal(applicantData);
    const isfReviewModal = document.getElementById('isfReviewModal');
    if (isfReviewModal) isfReviewModal.classList.add('active');
    }

    function populateISFModal(data) {
        // Populate ISF modal fields with data
        setInputValue('isfId', data.applicantId || data.id);
        document.getElementById('isfRefNumber').textContent = (data.referenceNumber || '') + ' · Reg. ' + (data.dateRegistered || '');
        document.getElementById('isfFullName').textContent = data.fullName || '';
        document.getElementById('isfHousehold').textContent = (data.householdSize || 0) + ' members';
        document.getElementById('isfIncome').textContent = '₱' + (parseFloat(data.monthlyIncome || 0).toLocaleString('en-PH', { minimumFractionDigits: 2, maximumFractionDigits: 2 }));
        document.getElementById('isfYears').textContent = (data.yearsResiding || 0) + ' years';
        setInputValue('isfPhoneNumber', data.phoneNumber || '');
        setInputValue('isfBarangay', data.barangay || '');
        setInputValue('isfPropertyOwnership', '');

        // Show income warning if exceeds limit
        const incomeWarning = document.getElementById('isfIncomeWarning');
        if (parseFloat(data.monthlyIncome || 0) > 10000) {
            incomeWarning.style.display = 'flex';
        } else {
            incomeWarning.style.display = 'none';
        }

        // Reset disqualify section
    const isfDisqualifyGroup = document.getElementById('isfDisqualifyGroup');
    if (isfDisqualifyGroup) isfDisqualifyGroup.style.display = 'none';
        setInputValue('isfDisqualifyReason', '');
        document.getElementById('isfApproveBtn').textContent = '✓ Mark as Eligible';
        document.getElementById('isfDisqualifyBtn').textContent = '✕ Mark as Disqualified';

        // Show Edit button only if ISF is still pending (not yet decided)
        const editBtn = document.getElementById('isfEditBtn');
        if (data.status === 'pending' || data.status === 'Pending Review') {
            editBtn.style.display = 'inline-block';
        } else {
            editBtn.style.display = 'none';
        }

        // Check eligibility and update button state
        checkISFEligibility(data);

        // Add listener to property ownership dropdown to re-check on change
        document.getElementById('isfPropertyOwnership').onchange = function () {
            checkISFEligibility(data);
        };
    }

    function checkISFEligibility(data) {
        // Check all eligibility criteria
        const eligibilityChecks = {
            income: parseFloat(data.monthlyIncome || 0) <= 10000,
            property: getInputValue('isfPropertyOwnership') === 'no',
            propertySelected: getInputValue('isfPropertyOwnership') !== ''
        };

        // Determine if Mark as Eligible button should be enabled
        const canMarkEligible = eligibilityChecks.income && eligibilityChecks.propertySelected;

        // Update button state
        const approveBtn = document.getElementById('isfApproveBtn');
        if (canMarkEligible && eligibilityChecks.property) {
            approveBtn.disabled = false;
            approveBtn.style.opacity = '1';
            approveBtn.style.cursor = 'pointer';
            approveBtn.title = 'All criteria passed - Click to mark as eligible';
        } else {
            approveBtn.disabled = true;
            approveBtn.style.opacity = '0.5';
            approveBtn.style.cursor = 'not-allowed';

            // Set tooltip message
            let reasons = [];
            if (!eligibilityChecks.income) {
                reasons.push('Income exceeds ₱10,000 limit');
            }
            if (!eligibilityChecks.property && eligibilityChecks.propertySelected) {
                reasons.push('Owns property in Talisay City');
            }
            if (!eligibilityChecks.propertySelected) {
                reasons.push('Please verify property ownership');
            }
            approveBtn.title = 'Cannot mark eligible: ' + reasons.join(', ');
        }
    }

    function closeISFModal() {
    const isfReviewModal = document.getElementById('isfReviewModal');
    if (isfReviewModal) isfReviewModal.classList.remove('active');
        // Reset edit mode
        const editSection = document.getElementById('isfEditSection');
        if (editSection) {
            editSection.style.display = 'none';
        }
        const editBtn = document.getElementById('isfEditBtn');
        if (editBtn) {
            editBtn.textContent = '✎ Edit Information';
        }
        currentISFData = null;
    }

    function toggleISFDisqualify() {
        showFlowAlert(
            'Intake disqualification controls are disabled. Disqualification is now enforced by Module 2 blacklist checks.'
        );
    }

    function submitISFReview(action) {
        const isfId = getInputValue('isfId');
        const phoneNumber = getInputValue('isfPhoneNumber');
        const barangay = getInputValue('isfBarangay');
        const propertyOwnership = getInputValue('isfPropertyOwnership');

        // Prevent submission if Mark as Eligible button is disabled
        if (action === 'eligible' && document.getElementById('isfApproveBtn').disabled) {
            showFlowAlert('This applicant does not meet eligibility criteria. Update records first, then continue in Module 2 Evaluation Precheck.');
            return;
        }

        // Validation
        if (!phoneNumber) {
            showFlowAlert('Contact number is required');
            return;
        }

        // Validate Philippine phone format (11 digits, starts with 09)
        const phoneClean = phoneNumber.replace(/\D/g, '');
        if (phoneClean.length !== 11 || !phoneClean.startsWith('09')) {
            showFlowAlert('Invalid phone format. Required: 09XXXXXXXXXX (11 digits)');
            return;
        }

        if (!barangay) {
            showFlowAlert('Barangay is required');
            return;
        }
        if (!propertyOwnership) {
            showFlowAlert('Property ownership verification is required');
            return;
        }

        // Submit form via AJAX
        const formData = new FormData();
        formData.append('csrfmiddlewaretoken', getCsrfToken());
        formData.append('phone_number', phoneClean); // Send digits only
        formData.append('barangay', barangay);
        formData.append('has_property_in_talisay', propertyOwnership);
        formData.append('action', 'submit');
        formData.append('status', 'eligible');

        fetch(`/intake/staff/isf/${isfId}/review/`, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showFlowAlert(data.message || 'ISF processed successfully');
                    closeISFModal();
                    location.reload();
                } else {
                    showFlowAlert('Error: ' + (data.error || 'Unknown error'));
                }
            })
            .catch(error => {
                showFlowAlert('Error submitting form: ' + error.message);
            });
    }

    function toggleISFEditMode() {
        const editSection = document.getElementById('isfEditSection');
        const editBtn = document.getElementById('isfEditBtn');
        const approveBtn = document.getElementById('isfApproveBtn');
        const disqualifyBtn = document.getElementById('isfDisqualifyBtn');

        if (editSection.style.display === 'none') {
            // Entering edit mode
            editSection.style.display = 'block';
            editBtn.textContent = '✕ Cancel Edit';
            approveBtn.style.display = 'none';
            disqualifyBtn.style.display = 'none';

            // Pre-fill with current values
            if (currentISFData) {
                setInputValue('isfEditIncome', currentISFData.monthly_income || '');
                setInputValue('isfEditHousehold', currentISFData.household_members || '');
                setInputValue('isfEditYears', currentISFData.years_residing || '');
                setInputValue('isfEditReason', '');
            }
        } else {
            // Exiting edit mode
            editSection.style.display = 'none';
            editBtn.textContent = '✎ Edit Information';
            approveBtn.style.display = 'block';
            disqualifyBtn.style.display = 'block';
            // Clear edit fields
            setInputValue('isfEditIncome', '');
            setInputValue('isfEditHousehold', '');
            setInputValue('isfEditYears', '');
            setInputValue('isfEditReason', '');
        }
    }

    function submitISFEdit() {
        const isfId = getInputValue('isfId');
        const income = getInputValue('isfEditIncome');
        const household = getInputValue('isfEditHousehold');
        const years = getInputValue('isfEditYears');
        const reason = getInputValue('isfEditReason');

        // Validation
        if (!reason.trim()) {
            showFlowAlert('Reason for edit is required');
            return;
        }

        // For now, we'll submit income edit (could be extended for other fields)
        if (income && income !== currentISFData.monthly_income) {
            submitFieldEdit('monthly_income', income, reason);
        } else if (household && household !== currentISFData.household_members) {
            submitFieldEdit('household_members', household, reason);
        } else if (years && String(years) !== String(currentISFData.years_residing)) {
            const yearsDigits = String(years).replace(/\D/g, '').slice(0, 2);
            const yearsNum = parseInt(yearsDigits, 10);
            if (!/^\d{1,2}$/.test(yearsDigits) || !Number.isFinite(yearsNum) || yearsNum > MODULE1_MAX_YEARS_RESIDING) {
                showFlowAlert('Years of residence must be 2 digits only (0–99).');
                return;
            }
            submitFieldEdit('years_residing', String(yearsNum), reason);
        } else {
            showFlowAlert('No changes detected');
            return;
        }
    }

    function submitFieldEdit(fieldName, newValue, editReason) {
        const isfId = getInputValue('isfId');

        // Remove commas from income before sending
        if (fieldName === 'monthly_income') {
            newValue = newValue.replace(/,/g, '');
        }

        const formData = new FormData();
        formData.append('csrfmiddlewaretoken', getCsrfToken());
        formData.append('field_name', fieldName);
        formData.append('new_value', newValue);
        formData.append('edit_reason', editReason);

        fetch(`/intake/staff/isf/${isfId}/edit/`, {
            method: 'POST',
            body: formData
        })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showFlowAlert(data.message || 'Data updated successfully');
                    // Update currentISFData
                    currentISFData[fieldName] = newValue;
                    // Re-check eligibility after edit
                    checkISFEligibility(currentISFData);
                    // Exit edit mode
                    toggleISFEditMode();
                } else {
                    showFlowAlert('Error: ' + (data.error || 'Failed to update'));
                }
            })
            .catch(error => {
                showFlowAlert('Error updating data: ' + error.message);
            });
    }

    // Philippine phone validation - limit to 11 digits, silently
    function initializePhoneInputs() {
        document.querySelectorAll('input.ph-phone, input[name="isf_phone[]"]').forEach(input => {
            if (input.dataset.phoneInit === 'true') return;
            input.dataset.phoneInit = 'true';
            input.addEventListener('input', function () {
                this.value = this.value.replace(/\D/g, '').slice(0, 11);
            });
        });
    }

    // Initialize on page load
    document.addEventListener('DOMContentLoaded', function () {
        initializePhoneInputs();
    });

    // Re-initialize phone inputs when new ISF records are added
    const originalAddISFRecord = addISFRecord;
    window.addISFRecord = function () {
        originalAddISFRecord();
        // Reinitialize after adding new record
        setTimeout(initializePhoneInputs, 100);
    };

    // ===== CDRRMO VERIFICATION FUNCTIONS =====
    function approveCdrrmo() {
        const staffNotes = getInputValue('staffCdrrmoNotes');
        const applicantId = getInputValue('reviewApplicantId');

        if (!applicantId) {
            showFlowAlert('Error: No applicant selected');
            return;
        }

        const formData = new FormData();
        formData.append('applicant_id', applicantId);
        formData.append('decision', 'approved');
        formData.append('staff_notes', staffNotes);

        fetch(window.APPLICANTS_CONFIG.updateCdrrmoStatusUrl, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken()
            },
            body: formData
        })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showFlowAlert('CDRRMO disposition recorded as accepted.\n\nThe applicant record will be updated and the page will reload.');
                    closeReviewModal();
                    setTimeout(() => location.reload(), 1000);
                } else {
                    showFlowAlert('Error: ' + data.error);
                }
            })
            .catch(error => {
                showFlowAlert('Error: ' + error.message);
            });
    }

    function rejectCdrrmo() {
        const staffNotes = getInputValue('staffCdrrmoNotes');
        const applicantId = getInputValue('reviewApplicantId');

        if (!applicantId) {
            showFlowAlert('Error: No applicant selected');
            return;
        }

        showNoticeModal({
            title: 'Reject CDRRMO Report?',
            message: 'Reject this CDRRMO field report?\n\nThe applicant will be treated as not within a certified hazard area and reclassified for walk-in processing, where applicable.',
            type: 'warning',
            primaryText: 'Yes, Reject',
            secondaryText: 'Cancel',
            applicantName: currentApplicant ? currentApplicant.fullName : null,
            onPrimary: () => {
                const formData = new FormData();
                formData.append('applicant_id', applicantId);
                formData.append('decision', 'rejected');
                formData.append('staff_notes', staffNotes);

                fetch(window.APPLICANTS_CONFIG.updateCdrrmoStatusUrl, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': getCsrfToken()
                    },
                    body: formData
                })
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            showFlowAlert('CDRRMO disposition recorded as rejected.\n\nThe applicant record will be updated for walk-in processing and the page will reload.');
                            closeReviewModal();
                            setTimeout(() => location.reload(), 1000);
                        } else {
                            showFlowAlert('Error: ' + data.error);
                        }
                    })
                    .catch(error => {
                        showFlowAlert('Error: ' + error.message);
                    });
            }
        });
    }

    function renderCdrrmoWorkflowTimeline(applicantData) {
        const host = document.getElementById('cdrrmoWorkflowTimelineBody');
        if (!host) return;

        const status = applicantData.cdrrmo_status || 'pending';
        const source = applicantData.cdrrmo_disposition_source || 'pending';
        const appStatus = applicantData.applicantStatus || '';
        const registeredAt = applicantData.dateRegistered || '—';
        const dispositionAt = applicantData.certified_at ? new Date(applicantData.certified_at).toLocaleDateString() : null;
        const finalized = appStatus !== 'pending_cdrrmo';
        const sentToModule2 = appStatus === 'eligible' || appStatus === 'requirements' || appStatus === 'application' || appStatus === 'standby' || appStatus === 'awarded';

        function dot(done, pending) {
            if (done) return '<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#16a34a;margin-right:0.45rem;vertical-align:middle;"></span>';
            if (pending) return '<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#eab308;margin-right:0.45rem;vertical-align:middle;"></span>';
            return '<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#cbd5e1;margin-right:0.45rem;vertical-align:middle;"></span>';
        }

        let step2Text = 'Awaiting disposition (office intake filing or field unit report)';
        if (source === 'office_intake') {
            step2Text = 'Official CDRRMO paperwork filed at THA intake' + (dispositionAt ? ` (${dispositionAt})` : '');
        } else if (source === 'field_unit') {
            step2Text = 'Field unit report submitted' + (dispositionAt ? ` (${dispositionAt})` : '');
        }

        let step3Text = 'Awaiting staff finalization';
        if (source === 'office_intake' && status !== 'pending') {
            step3Text = 'No separate field-finalization step required (office disposition is final)';
        } else if (finalized) {
            if (appStatus === 'eligible') step3Text = 'Staff finalized as eligible';
            else if (appStatus === 'disqualified') step3Text = 'Staff finalized as disqualified';
            else step3Text = `Staff finalized (status: ${appStatus})`;
        }

        const lines = [
            `${dot(true, false)}<strong>Step 1:</strong> Intake record encoded (${registeredAt})`,
            `${dot(status !== 'pending', status === 'pending')}<strong>Step 2:</strong> ${step2Text}`,
            `${dot(finalized || (source === 'office_intake' && status !== 'pending'), status !== 'pending' && !(finalized || source === 'office_intake'))}<strong>Step 3:</strong> ${step3Text}`,
            `${dot(sentToModule2, finalized && !sentToModule2)}<strong>Step 4:</strong> ${sentToModule2 ? 'Ready in Module 2 — Application & Eligibility' : 'Not yet in Module 2 handoff list'}`,
        ];
        host.innerHTML = lines.map(function (line) { return `<div style="margin-bottom:0.25rem;">${line}</div>`; }).join('');
    }

    // Function to populate CDRRMO section in modal
    function populateCdrrmoSection(applicantId, applicantData) {
        const cdrrmoSection = document.querySelector('.cdrrmo-certification-section');
        if (!cdrrmoSection) return;

        // Check if applicant has danger zone info
        if (!applicantData.dangerZoneType) {
            const opHide = document.getElementById('officeCdrrmoReceiptPanel');
            if (opHide) opHide.style.display = 'none';
            cdrrmoSection.style.display = 'none';
            return;
        }

        cdrrmoSection.style.display = 'block';

        // Set declared info
        const dzType = applicantData.dangerZoneType || applicantData.danger_zone_type;
        const dzLabel = formatHazardZoneTypeLabel(dzType);
        document.getElementById('cdrrmoDeclarationType').textContent = dzLabel || dzType || 'Not specified';
        document.getElementById('cdrrmoDecLocation').textContent = applicantData.dangerZoneLocation || applicantData.danger_zone_location || 'Not specified';
        renderCdrrmoWorkflowTimeline(applicantData);

        // Check CDRRMO certification status
        const cdrrmoStatus = applicantData.cdrrmo_status; // 'pending', 'certified', 'not_certified'
        const dispositionSource = applicantData.cdrrmo_disposition_source || 'field_unit';
        const rondaTeamResultBox = document.getElementById('rondaTeamResultBox');
        const staffApprovalBox = document.getElementById('staffApprovalBox');
        const cdrrmoActionsBox = document.getElementById('cdrrmoActionsBox');
        const cdrrmoStatusBox = document.getElementById('cdrrmoStatusBox');
        const officeIntakeResultBox = document.getElementById('officeIntakeResultBox');
        const rondaEvidenceSection = document.getElementById('rondaEvidencePhotosSection');
        const rondaEvidenceStrip = document.getElementById('rondaEvidencePhotosStrip');
        const rondaEvidenceEmpty = document.getElementById('rondaEvidencePhotosEmpty');

        function resetRondaEvidencePhotos() {
            if (rondaEvidenceStrip) rondaEvidenceStrip.innerHTML = '';
            if (rondaEvidenceSection) rondaEvidenceSection.style.display = 'none';
            if (rondaEvidenceEmpty) rondaEvidenceEmpty.style.display = 'none';
        }

        // Intake modal policy: keep CDRRMO/Ronda detailed verification display out of this modal.
        // Full verification details are viewed from Module 2 (Application & Eligibility) View modal.
        if (rondaTeamResultBox) rondaTeamResultBox.style.display = 'none';
        if (staffApprovalBox) staffApprovalBox.style.display = 'none';
        if (cdrrmoActionsBox) cdrrmoActionsBox.style.display = 'none';

        if (cdrrmoStatus === 'pending') {
            resetRondaEvidencePhotos();
            cdrrmoStatusBox.style.display = 'block';
            if (rondaTeamResultBox) rondaTeamResultBox.style.display = 'none';
            if (staffApprovalBox) staffApprovalBox.style.display = 'none';
            if (cdrrmoActionsBox) cdrrmoActionsBox.style.display = 'none';
            if (officeIntakeResultBox) officeIntakeResultBox.style.display = 'none';
            setElementHtml('cdrrmoStatusText', `
                <strong>Awaiting CDRRMO disposition</strong><br>
                <span style="font-size: 0.75rem;">Either the field unit will submit an on-site verification report (with optional photographs), or intake will file official CDRRMO certification received at the THA office.${canModify ? ' Use <strong>Official CDRRMO certification — office receipt</strong> below when paperwork is on file.' : ''}</span>
            `);
        } else if (cdrrmoStatus === 'certified' || cdrrmoStatus === 'not_certified') {
            cdrrmoStatusBox.style.display = 'none';

            if (dispositionSource === 'office_intake') {
                if (officeIntakeResultBox) officeIntakeResultBox.style.display = 'block';
                if (rondaTeamResultBox) rondaTeamResultBox.style.display = 'none';
                if (staffApprovalBox) staffApprovalBox.style.display = 'none';
                if (cdrrmoActionsBox) cdrrmoActionsBox.style.display = 'none';
                resetRondaEvidencePhotos();

                const oiBy = document.getElementById('officeIntakeRecordedBy');
                const oiDt = document.getElementById('officeIntakeFiledDate');
                const oiNotes = document.getElementById('officeIntakeNotesDisplay');
                if (oiBy) oiBy.textContent = applicantData.result_recorded_by_name || '—';
                if (oiDt) oiDt.textContent = applicantData.certified_at ? new Date(applicantData.certified_at).toLocaleDateString() : '—';
                if (oiNotes) oiNotes.textContent = applicantData.office_intake_notes || '—';

                const ocb = document.getElementById('officeIntakeCertifiedBadge');
                const onb = document.getElementById('officeIntakeNotCertifiedBadge');
                if (cdrrmoStatus === 'certified') {
                    if (ocb) ocb.style.display = 'inline-block';
                    if (onb) onb.style.display = 'none';
                } else {
                    if (ocb) ocb.style.display = 'none';
                    if (onb) onb.style.display = 'inline-block';
                }
            } else {
                if (officeIntakeResultBox) officeIntakeResultBox.style.display = 'none';
                if (rondaTeamResultBox) rondaTeamResultBox.style.display = 'none';
                if (staffApprovalBox) staffApprovalBox.style.display = 'none';
                if (cdrrmoActionsBox) cdrrmoActionsBox.style.display = 'none';
                resetRondaEvidencePhotos();
            }
        } else {
            resetRondaEvidencePhotos();
            if (cdrrmoActionsBox) cdrrmoActionsBox.style.display = 'none';
            if (officeIntakeResultBox) officeIntakeResultBox.style.display = 'none';
        }

        const officePanel = document.getElementById('officeCdrrmoReceiptPanel');
        if (officePanel) {
            const dz = applicantData.dangerZoneType || applicantData.danger_zone_type;
            const showOffice = canModify && applicantData.cdrrmo_status === 'pending' && !!dz;
            officePanel.style.display = showOffice ? 'block' : 'none';
        }
    }

    /** Intake: official CDRRMO paperwork received at THA while cert is still system-pending (uses `update_cdrrmo_certification`). */
    function recordOfficeCdrrmoCertified() {
        if (!canModify) return;
        const applicantId = document.getElementById('reviewApplicantId')?.value;
        if (!applicantId || !currentApplicant || currentApplicant.channel !== 'B') {
            showFlowAlert('Unable to record certification: no applicant is selected or this record is not a Channel B hazard pathway file.');
            return;
        }
        if (currentApplicant.cdrrmo_status !== 'pending') {
            showFlowAlert('Office receipt is only available while the CDRRMO certification record is still pending in the system (before a certified or not-certified disposition is filed).');
            return;
        }
        showNoticeModal({
            title: 'Record CDRRMO Certification?',
            message: 'Record official CDRRMO certification as received at the THA intake office?\n\nThe applicant will be marked hazard-area certified, assigned a priority queue position where applicable, and notified by SMS if a mobile number is on file.',
            type: 'warning',
            primaryText: 'Yes, Proceed',
            secondaryText: 'Cancel',
            applicantName: currentApplicant ? currentApplicant.fullName : null,
            onPrimary: () => {
                const extra = document.getElementById('officeCdrrmoReceiptNotes')?.value?.trim() || '';
                const prefix = '[Official CDRRMO certification received at THA intake — ' + new Date().toISOString().slice(0, 10) + '] ';
                const notes = extra ? (prefix + extra) : prefix;
                const formData = new FormData();
                formData.append('applicant_id', applicantId);
                formData.append('decision', 'certified');
                formData.append('notes', notes);
                formData.append('office_receipt', '1');
                formData.append('csrfmiddlewaretoken', getCsrfToken());

                fetch(window.APPLICANTS_CONFIG.updateCdrrmoCertificationUrl, {
                    method: 'POST',
                    body: formData,
                })
                    .then(function (response) { return response.json(); })
                    .then(function (data) {
                        if (data.success) {
                            showFlowAlert(data.message || 'CDRRMO certification recorded.');
                            closeReviewModal();
                            setTimeout(function () { location.reload(); }, 400);
                        } else {
                            showFlowAlert(data.error || 'Unable to record certification.');
                        }
                    })
                    .catch(function (err) {
                        showFlowAlert('Error: ' + err.message);
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

