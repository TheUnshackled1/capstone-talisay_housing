/* ===================================================================
   applications_list.js
   Extracted from templates/staff/applications_list.html
   Django template vars injected via #appsBridge script in HTML.
   =================================================================== */

    let flowAlertOnConfirm = null;
    let flowAlertOnNext = null;
    let lastPrecheckApplicantName = '';
    let lastPrecheckApplicantId = '';
    let lastPrecheckMessage = 'No blacklist record found. The applicant may proceed to the Eligibility Evaluation Checklist.';
    let currentEligibilityApplicantId = '';
    let lastEligibilitySnapshot = null;
    const eligibilityManualDecisions = {};
    let pendingFailedCheckKey = '';
    let pendingM2RequirementUploadContext = null;
    let m2ReplaceDocConfirmResolver = null;

    const M2_VIEW_ICON_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>';
    const M2_PASS_ICON_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>';
    const M2_MISSING_ICON_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>';
    const M2_PHOTO_ICON_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><circle cx="8.5" cy="8.5" r="1.5"></circle><polyline points="21 15 16 10 5 21"></polyline></svg>';

    /** Maps eligibility card keys → intake `upload_scanned_requirement` doc_key / barangay requirement code (same as intake staff checklist). */
    const M2_ELIGIBILITY_CHECK_TO_INTAKE_DOC = {
        property: { doc_key: 'doc_no_property', doc_code: 'R05' },
        age_residency: { doc_key: 'doc_brgy_residency', doc_code: 'R01' },
        income: { doc_key: 'doc_brgy_indigency', doc_code: 'R02' },
        household: { doc_key: 'doc_cedula', doc_code: 'R03' },
        voter: { doc_key: 'doc_voter_cert', doc_code: 'RVT' },
    };
    const M2_DOC_MISSING_LABEL = 'Missing — scan or upload';
    const M2_VAULT_DOCUMENT_TYPE_TO_INTAKE_DOC = {
        cdrrmo_cert: { doc_key: 'doc_cdrrmo', doc_code: 'CDRRMO' },
        isf_situational_docs: { doc_key: 'doc_isf_situational', doc_code: 'ISF-SIT' },
    };

    let M2DWTObject = null;
    if (window.Dynamsoft?.DWT) {
        Dynamsoft.DWT.RegisterEvent('OnWebTwainReady', function () {
            M2DWTObject = Dynamsoft.DWT.GetWebTwain('dwtcontrolContainer');
        });
    }

    async function m2WaitForDwtReady(timeoutMs = 8000) {
        const startedAt = Date.now();
        while (!M2DWTObject && (Date.now() - startedAt) < timeoutMs) {
            await new Promise(function (resolve) { setTimeout(resolve, 100); });
        }
        return M2DWTObject;
    }

    async function m2AcquireImageWithDwt(opts = {}) {
        const dwt = await m2WaitForDwtReady();
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

    function m2UploadCurrentScannedImageForApplicant(applicantId, referenceNumber, docKey, docCode) {
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
                    /* ignore */
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
                const dwt = await m2WaitForDwtReady();
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
                const uploadUrl = `${MODULE2_INTAKE_UPLOAD_SCAN_URL}?applicant_id=${safeApplicantId}&doc_key=${safeDocKey}&doc_code=${safeDocCode}&capture_method=scan`;
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
                                /* ignore */
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

    async function m2EligibilityChecklistDwtScan(buttonEl) {
        if (!buttonEl || !MODULE2_CAN_DWT_SCAN) return;
        const checkKey = String(buttonEl.dataset.checkKey || '').trim();
        const mapping = M2_ELIGIBILITY_CHECK_TO_INTAKE_DOC[checkKey];
        const applicantId = currentEligibilityApplicantId;
        if (!mapping || !applicantId) return;
        const refRaw = lastEligibilitySnapshot && lastEligibilitySnapshot.reference_number != null
            ? String(lastEligibilitySnapshot.reference_number).trim()
            : '';
        const referenceNumber = refRaw || applicantId;
        const hasExistingDoc = String(buttonEl.dataset.hasExistingDoc || '0') === '1';
        const existingDocName = String(buttonEl.dataset.existingDocName || '').trim() || 'Scanned document';
        if (hasExistingDoc) {
            const ok = await m2ConfirmReplaceExistingDocument(existingDocName);
            if (!ok) return;
        }

        const scanSvg = buttonEl.querySelector('svg') ? buttonEl.querySelector('svg').outerHTML : '';
        const oldHtml = buttonEl.innerHTML;
        buttonEl.disabled = true;
        buttonEl.innerHTML = scanSvg + ' Scanning…';
        try {
            await m2AcquireImageWithDwt({ selectSource: true });
            await m2UploadCurrentScannedImageForApplicant(applicantId, referenceNumber, mapping.doc_key, mapping.doc_code);
            await fetchEligibilitySnapshot(applicantId);
            showFlowAlert('Scan saved to the document vault.', 'Scan complete', null, 'success');
        } catch (error) {
            showFlowAlert((error && error.message) ? error.message : 'Unable to complete scan.');
            buttonEl.innerHTML = oldHtml;
        } finally {
            buttonEl.disabled = false;
            buttonEl.innerHTML = oldHtml;
        }
    }

    async function m2SituationCertificationDwtScan(buttonEl) {
        if (!buttonEl || !MODULE2_CAN_DWT_SCAN) return;
        const docKey = String(buttonEl.dataset.intakeDocKey || '').trim();
        const docCode = String(buttonEl.dataset.intakeDocCode || '').trim() || 'document';
        const applicantId = currentEligibilityApplicantId;
        if (!docKey || !applicantId) return;
        const refRaw = lastEligibilitySnapshot && lastEligibilitySnapshot.reference_number != null
            ? String(lastEligibilitySnapshot.reference_number).trim()
            : '';
        const referenceNumber = refRaw || applicantId;
        const hasExistingDoc = String(buttonEl.dataset.hasExistingDoc || '0') === '1';
        const existingDocName = String(buttonEl.dataset.existingDocName || '').trim() || 'Scanned document';
        if (hasExistingDoc) {
            const ok = await m2ConfirmReplaceExistingDocument(existingDocName);
            if (!ok) return;
        }

        const scanSvg = buttonEl.querySelector('svg') ? buttonEl.querySelector('svg').outerHTML : '';
        const oldHtml = buttonEl.innerHTML;
        buttonEl.disabled = true;
        buttonEl.innerHTML = scanSvg + ' Scanning…';
        try {
            await m2AcquireImageWithDwt({ selectSource: true });
            await m2UploadCurrentScannedImageForApplicant(applicantId, referenceNumber, docKey, docCode);
            await fetchEligibilitySnapshot(applicantId);
            showFlowAlert('Scan saved to the document vault.', 'Scan complete', null, 'success');
        } catch (error) {
            showFlowAlert((error && error.message) ? error.message : 'Unable to complete scan.');
            buttonEl.innerHTML = oldHtml;
        } finally {
            buttonEl.disabled = false;
            buttonEl.innerHTML = oldHtml;
        }
    }

    async function m2TriggerEligibilityChecklistFileUpload(buttonEl) {
        if (!buttonEl || !MODULE2_CAN_DWT_SCAN) return;
        const checkKey = String(buttonEl.dataset.m2UploadCheckKey || '').trim();
        const mapping = M2_ELIGIBILITY_CHECK_TO_INTAKE_DOC[checkKey];
        const applicantId = currentEligibilityApplicantId;
        if (!mapping || !applicantId) return;
        const hasExistingDoc = String(buttonEl.dataset.hasExistingDoc || '0') === '1';
        const existingDocName = String(buttonEl.dataset.existingDocName || '').trim() || 'Scanned document';
        if (hasExistingDoc) {
            const ok = await m2ConfirmReplaceExistingDocument(existingDocName);
            if (!ok) return;
        }
        pendingM2RequirementUploadContext = {
            mode: 'eligibility',
            applicantId,
            docKey: mapping.doc_key,
            docCode: mapping.doc_code,
            checkKey,
        };
        const inp = document.getElementById('m2RequirementFileInput');
        if (!inp) return;
        inp.value = '';
        inp.click();
    }

    async function m2SituationCertificationFileUpload(buttonEl) {
        if (!buttonEl || !MODULE2_CAN_DWT_SCAN) return;
        const docKey = String(buttonEl.dataset.intakeDocKey || '').trim();
        const docCode = String(buttonEl.dataset.intakeDocCode || '').trim() || 'document';
        const applicantId = currentEligibilityApplicantId;
        if (!docKey || !applicantId) return;
        const hasExistingDoc = String(buttonEl.dataset.hasExistingDoc || '0') === '1';
        const existingDocName = String(buttonEl.dataset.existingDocName || '').trim() || 'Scanned document';
        if (hasExistingDoc) {
            const ok = await m2ConfirmReplaceExistingDocument(existingDocName);
            if (!ok) return;
        }
        pendingM2RequirementUploadContext = {
            mode: 'situation',
            applicantId,
            docKey,
            docCode,
        };
        const inp = document.getElementById('m2RequirementFileInput');
        if (!inp) return;
        inp.value = '';
        inp.click();
    }

    async function handleM2RequirementFileSelected(ev) {
        const input = ev.target;
        const file = input.files && input.files[0];
        const ctx = pendingM2RequirementUploadContext;
        pendingM2RequirementUploadContext = null;
        if (!file || !ctx) {
            if (input) input.value = '';
            return;
        }
        const formData = new FormData();
        formData.append('applicant_id', ctx.applicantId);
        formData.append('doc_key', ctx.docKey);
        formData.append('doc_code', String(ctx.docCode || '').toUpperCase());
        formData.append('file', file);
        formData.append('capture_method', 'upload');

        let busyBtn = null;
        if (ctx.mode === 'eligibility' && ctx.checkKey) {
            busyBtn = document.querySelector(
                '#eligibilityNextModal button.m2-elig-intake-upload-btn[data-m2-upload-check-key="' + ctx.checkKey.replace(/"/g, '') + '"]'
            );
        } else if (ctx.mode === 'situation' && ctx.docKey) {
            busyBtn = document.querySelector(
                '#eligibilityNextModal button.m2-elig-intake-upload-btn[data-intake-doc-key="' + ctx.docKey.replace(/"/g, '') + '"]'
            );
        }
        let oldHtml = '';
        if (busyBtn) {
            oldHtml = busyBtn.innerHTML;
            const uploadSvg = busyBtn.querySelector('svg') ? busyBtn.querySelector('svg').outerHTML : '';
            busyBtn.disabled = true;
            busyBtn.innerHTML = uploadSvg + ' Uploading…';
        }
        try {
            const response = await fetch(MODULE2_INTAKE_UPLOAD_SCAN_URL, {
                method: 'POST',
                body: formData,
                credentials: 'same-origin',
            });
            const ct = (response.headers.get('content-type') || '').toLowerCase();
            const data = ct.includes('application/json') ? await response.json() : null;
            if (!data || !data.success) {
                throw new Error((data && data.error) ? data.error : 'Upload failed.');
            }
            await fetchEligibilitySnapshot(ctx.applicantId);
            showFlowAlert('File saved to the document vault.', 'Upload complete', null, 'success');
        } catch (err) {
            showFlowAlert(err.message || 'Upload failed.');
            if (busyBtn && busyBtn.isConnected) {
                busyBtn.disabled = false;
                busyBtn.innerHTML = oldHtml;
            }
        } finally {
            if (input) input.value = '';
        }
    }

    function escapeHtml(text) {
        const s = text == null ? '' : String(text);
        const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
        return s.replace(/[&<>"']/g, (m) => map[m]);
    }

    function m2EscapeAttrJson(jsonStr) {
        return String(jsonStr).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');
    }

    let m2FieldPhotoGalleryUrls = [];
    let m2FieldPhotoGalleryIndex = 0;

    function m2OpenSituationFieldPhotoGalleryFromBtn(btn) {
        const raw = btn && btn.getAttribute('data-m2-field-photos');
        if (!raw) return;
        let urls;
        try {
            urls = JSON.parse(raw);
        } catch (e1) {
            return;
        }
        if (!Array.isArray(urls) || !urls.length) return;
        m2OpenSituationFieldPhotoGallery(urls);
    }

    function m2FieldPhotoGalleryRefresh() {
        const urls = m2FieldPhotoGalleryUrls;
        const idx = m2FieldPhotoGalleryIndex;
        const img = document.getElementById('m2FieldPhotoGalleryImg');
        const prev = document.getElementById('m2FieldPhotoGalleryPrev');
        const next = document.getElementById('m2FieldPhotoGalleryNext');
        const counter = document.getElementById('m2FieldPhotoGalleryCounter');
        if (!img || !urls.length) return;
        img.src = urls[idx] || '';
        img.alt = 'Site photograph ' + String(idx + 1) + ' of ' + String(urls.length);
        if (counter) {
            counter.textContent = urls.length > 1 ? String(idx + 1) + ' / ' + String(urls.length) : '';
        }
        if (prev) prev.hidden = urls.length <= 1;
        if (next) next.hidden = urls.length <= 1;
    }

    function m2FieldPhotoGalleryStep(delta) {
        const n = m2FieldPhotoGalleryUrls.length;
        if (n <= 1) return;
        m2FieldPhotoGalleryIndex = (m2FieldPhotoGalleryIndex + delta + n) % n;
        m2FieldPhotoGalleryRefresh();
    }

    function m2FieldPhotoGalleryOnKeydown(e) {
        if (e.key === 'Escape') {
            m2CloseSituationFieldPhotoGallery();
            return;
        }
        if (m2FieldPhotoGalleryUrls.length <= 1) return;
        if (e.key === 'ArrowLeft') {
            e.preventDefault();
            m2FieldPhotoGalleryStep(-1);
        }
        if (e.key === 'ArrowRight') {
            e.preventDefault();
            m2FieldPhotoGalleryStep(1);
        }
    }

    function m2OpenSituationFieldPhotoGallery(urls) {
        const overlay = document.getElementById('m2FieldPhotoGalleryModal');
        const titleEl = document.getElementById('m2FieldPhotoGalleryTitle');
        const subEl = document.getElementById('m2FieldPhotoGallerySubtitle');
        if (!overlay) return;
        const list = urls.slice();
        const n = list.length;
        if (!n) return;
        m2FieldPhotoGalleryUrls = list;
        m2FieldPhotoGalleryIndex = 0;
        if (titleEl) titleEl.textContent = n === 1 ? 'Site photograph' : 'Site photographs';
        if (subEl) {
            subEl.textContent = n === 1 ? '1 image on file.' : String(n) + ' images on file.';
        }
        m2FieldPhotoGalleryRefresh();
        overlay.classList.add('active');
        overlay.setAttribute('aria-hidden', 'false');
        document.addEventListener('keydown', m2FieldPhotoGalleryOnKeydown);
    }

    function m2CloseSituationFieldPhotoGallery(event) {
        if (event && event.target && event.target.id !== 'm2FieldPhotoGalleryModal') return;
        const overlay = document.getElementById('m2FieldPhotoGalleryModal');
        const img = document.getElementById('m2FieldPhotoGalleryImg');
        if (!overlay) return;
        overlay.classList.remove('active');
        overlay.setAttribute('aria-hidden', 'true');
        if (img) img.src = '';
        m2FieldPhotoGalleryUrls = [];
        document.removeEventListener('keydown', m2FieldPhotoGalleryOnKeydown);
    }

    function formatM2EvidenceHtml(lines) {
        const arr = (Array.isArray(lines) ? lines : []).map((e) => String(e || '').trim()).filter(Boolean);
        if (!arr.length) return '';

        // Decorate status value with an icon badge
        function statusBadge(val) {
            const v = val.trim();
            const vl = v.toLowerCase();
            if (vl === 'scanned') {
                return `<span class="m2-ev-status m2-ev-status--ok">&#x2714; Scanned</span>`;
            }
            if (vl === 'uploaded') {
                return `<span class="m2-ev-status m2-ev-status--ok">&#x2714; Uploaded</span>`;
            }
            if (vl.startsWith('missing')) {
                return `<span class="m2-ev-status m2-ev-status--miss">&#x26A0; Missing</span>`;
            }
            // Numeric values — bold, no badge
            if (/^\d[\d,.\s]*$/.test(v) || /^₱/.test(v)) {
                return `<span class="m2-ev-status m2-ev-status--num">${escapeHtml(v)}</span>`;
            }
            return `<span class="m2-ev-status m2-ev-status--neutral">${escapeHtml(v)}</span>`;
        }

        const rows = arr.map((line) => {
            const colonIdx = line.indexOf(':');
            if (colonIdx > 0 && colonIdx < line.length - 1) {
                const label = line.slice(0, colonIdx).trim();
                const val = line.slice(colonIdx + 1).trim();
                return `<tr class="m2-ev-tr"><td class="m2-ev-td-label">${escapeHtml(label)}</td><td class="m2-ev-td-status">${statusBadge(val)}</td></tr>`;
            }
            return `<tr class="m2-ev-tr"><td class="m2-ev-td-full" colspan="2">${escapeHtml(line)}</td></tr>`;
        }).join('');

        return `<div class="m2-elig-evidence-box">
            <table class="m2-ev-table">
                <thead><tr><th class="m2-ev-th">Evidence</th><th class="m2-ev-th m2-ev-th--status">Status</th></tr></thead>
                <tbody>${rows}</tbody>
            </table>
        </div>`;
    }


    function splitSituationDetailForEvidence(detail) {
        const s = String(detail || '').trim();
        if (!s) return [];
        return s.split(/\.\s+/).map((x) => x.trim()).filter(Boolean).map((p) => (p.endsWith('.') ? p : `${p}.`));
    }

    function situationCertReasonForCheck(checks, sc, idx, done, suppressBlockingInCards) {
        if (done) return 'Requirement satisfied.';
        if (suppressBlockingInCards) return '';
        const block = String(sc.blocking_summary || '').trim();
        if (!block) return '';
        const firstMiss = checks.findIndex((ch) => !ch.done);
        if (checks.length <= 1 || idx === firstMiss) return block;
        return '';
    }

    function buildM2SituationCertCardHtml(c, idx, checks, sc, suppressReasonDup) {
        const ok = !!c.done;
        const vaultUploadUrl = typeof c.vault_upload_url === 'string' ? c.vault_upload_url.trim() : '';
        const vaultScanUrl = typeof c.vault_scan_url === 'string' ? c.vault_scan_url.trim() : '';
        const docUrl = (c.view_document && c.view_document.url) ? String(c.view_document.url).trim() : '';
        const docName = (c.view_document && c.view_document.name) ? String(c.view_document.name) : 'Document';
        const safeDocHref = docUrl ? docUrl.replace(/"/g, '&quot;') : '';
        const safeVaultUploadHref = vaultUploadUrl ? vaultUploadUrl.replace(/"/g, '&quot;') : '';
        const safeVaultScanHref = vaultScanUrl ? vaultScanUrl.replace(/"/g, '&quot;') : '';
        const vaultDt = String(c.vault_document_type || '').trim();
        const sitDwtMapping = M2_VAULT_DOCUMENT_TYPE_TO_INTAKE_DOC[vaultDt];
        const hasExistingDocAttr = docUrl ? '1' : '0';
        const safeExistingDocNameAttr = escapeHtml(docName || 'Document');
        const sitScanControlHtml = '';
        const sitUploadHtml = '';
        const isFieldSitePhotosRow = String(c.key || '').trim() === 'field_site_photos';
        const fieldPhotoUrls = Array.isArray(c.field_photo_urls) ? c.field_photo_urls.filter(function (u) { return u && String(u).trim(); }) : [];
        const fieldPhotosAttr = fieldPhotoUrls.length ? m2EscapeAttrJson(JSON.stringify(fieldPhotoUrls)) : '';
        const viewFieldPhotosHtml = (isFieldSitePhotosRow && fieldPhotoUrls.length && fieldPhotosAttr)
            ? `<button type="button" class="eligibility-view-doc-btn m2-sit-action-view-photos" data-m2-field-photos="${fieldPhotosAttr}" onclick="m2OpenSituationFieldPhotoGalleryFromBtn(this)" title="View ${fieldPhotoUrls.length} photograph(s) in the viewer"><span class="btn-icon-block">${M2_PHOTO_ICON_SVG}</span><span>Photos</span></button>`
            : '';
        const evidenceHtml = formatM2EvidenceHtml(splitSituationDetailForEvidence(c.detail));
        let cardClass = 'm2-elig-card m2-elig-card--compact';
        if (ok) cardClass += ' m2-elig-card--pass';
        else cardClass += ' m2-elig-card--fail';
        const chipClass = ok ? 'passed' : 'failed';
        const chipLabel = ok ? 'Done' : 'Missing';
        const reasonLine = situationCertReasonForCheck(checks, sc, idx, ok, suppressReasonDup);
        const markPassedTitle = ok
            ? 'Requirement satisfied on record. When every row shows Done, click Mark Situation Certified below.'
            : 'Upload or scan the required document in the vault until this row shows Done.';
        const markPassedButtonsHtml = isFieldSitePhotosRow
            ? ''
            : (ok
                ? `<button type="button" class="eligibility-decision-btn m2-sit-mark-passed active-pass" title="${escapeHtml(markPassedTitle)}"
                 onclick="showFlowAlert('This requirement is satisfied on record. When every row shows Done, click Mark Situation Certified below.', 'Situation Certification', null, 'success')"><span class="btn-icon-block">${M2_PASS_ICON_SVG}</span><span>Mark</span></button>`
                : `<button type="button" class="eligibility-decision-btn m2-sit-mark-passed" disabled title="${escapeHtml(markPassedTitle)}"><span class="btn-icon-block">${M2_PASS_ICON_SVG}</span><span>Mark</span></button>`);
        const viewSitDocBtnHtml = docUrl ? `<a class="eligibility-view-doc-btn m2-sit-action-view" href="${safeDocHref}" target="_blank" rel="noopener noreferrer" title="${escapeHtml(docName)}"><span class="btn-icon-block">${M2_VIEW_ICON_SVG}</span><span>View</span></a>` : '';
        const actionsRow = (viewSitDocBtnHtml || viewFieldPhotosHtml || markPassedButtonsHtml)
            ? `<div class="m2-elig-actions m2-sit-actions">
                <div class="m2-elig-decision-actions">
                    ${viewSitDocBtnHtml}
                    ${viewFieldPhotosHtml}
                    ${markPassedButtonsHtml}
                </div>
            </div>`
            : '';
        return `
            <div class="${cardClass}">
                <div class="m2-elig-card-head">
                    <h4 class="m2-elig-card-title">${escapeHtml(String(c.label || 'Requirement'))}</h4>
                    <span class="eligibility-check-chip ${chipClass}">${chipLabel}</span>
                </div>
                ${reasonLine ? `<div class="m2-elig-card-reason">${ok ? '' : '&#x26A0; '}${escapeHtml(reasonLine)}</div>` : ''}
                ${evidenceHtml}
                ${actionsRow}
            </div>`;
    }

    function showFlowAlert(message, title = 'Notice', onConfirm = null, tone = 'default', onNext = null) {
        const modal = document.getElementById('flowAlertModal');
        const card = document.getElementById('flowAlertCard');
        const titleEl = document.getElementById('flowAlertTitle');
        const messageEl = document.getElementById('flowAlertMessage');
        const iconEl = document.getElementById('flowAlertIcon');
        const nextBtn = document.getElementById('flowAlertNextBtn');
        const actionsEl = document.getElementById('flowAlertActions');
        const celIcon = document.getElementById('flowAlertCelebrationIcon');
        const progBar = document.getElementById('flowAlertProgressBar');

        if (!modal || !titleEl || !messageEl) {
            alert(message);
            if (typeof onConfirm === 'function') onConfirm();
            return;
        }

        // Reset countdown timer if active
        if (window.flowAlertCountdownTimeout) {
            clearTimeout(window.flowAlertCountdownTimeout);
            window.flowAlertCountdownTimeout = null;
        }

        titleEl.textContent = title;
        messageEl.textContent = message || '';

        const isCelebration = !!(tone === 'success' || tone === 'proceed_success');

        const isPrecheckNextStep = tone === 'success' && (title === 'Evaluation Pre-check' || title === 'Evaluation Precheck') && typeof onNext === 'function';

        if (card) {
            card.classList.remove('success', 'proceed-success', 'flow-alert-card--celebration', 'flow-alert-card--precheck-next');
            if (tone === 'success') card.classList.add('success');
            if (tone === 'proceed_success') card.classList.add('proceed-success');
            if (isCelebration) {
                card.classList.add('flow-alert-card--celebration');
            }
            if (isPrecheckNextStep) {
                card.classList.add('flow-alert-card--precheck-next');
            }
        }

        if (celIcon) {
            celIcon.style.display = isCelebration ? 'flex' : 'none';
        }
        if (progBar) {
            progBar.style.display = 'none';
        }

        if (iconEl) {
            iconEl.style.display = isCelebration ? 'none' : ((tone !== 'default') ? 'inline-flex' : 'none');
        }
        if (nextBtn) {
            nextBtn.style.display = isPrecheckNextStep ? 'inline-flex' : 'none';
        }
        const okBtn = document.querySelector('#flowAlertModal .flow-alert-ok');
        if (okBtn) {
            okBtn.style.display = isPrecheckNextStep ? 'none' : 'inline-flex';
        }
        if (actionsEl) {
            actionsEl.style.justifyContent = 'center';
        }

        flowAlertOnConfirm = onConfirm;
        flowAlertOnNext = onNext;
        modal.classList.add('active');

    }

    function closeFlowAlert(event) {
        if (event && event.target && event.target.id !== 'flowAlertModal') return;
        const modal = document.getElementById('flowAlertModal');
        if (modal) modal.classList.remove('active');
        if (window.flowAlertCountdownTimeout) {
            clearTimeout(window.flowAlertCountdownTimeout);
            window.flowAlertCountdownTimeout = null;
        }
    }

    function confirmFlowAlert() {
        const onConfirm = flowAlertOnConfirm;
        flowAlertOnConfirm = null;
        flowAlertOnNext = null;
        if (window.flowAlertCountdownTimeout) {
            clearTimeout(window.flowAlertCountdownTimeout);
            window.flowAlertCountdownTimeout = null;
        }
        closeFlowAlert();
        if (typeof onConfirm === 'function') onConfirm();
    }

    function m2ConfirmReplaceExistingDocument(docName) {
        if (typeof showFlowConfirmReplaceDocument === 'function') {
            return showFlowConfirmReplaceDocument(docName || 'Scanned document');
        }
        return Promise.resolve(window.confirm('A document is already attached. Do you want to replace it?'));
    }

    async function m2HandleReplaceAwareVaultLinkClick(event) {
        const link = event.target && event.target.closest
            ? event.target.closest('a.m2-replace-aware-link')
            : null;
        if (!link) return;
        const hasExistingDoc = String(link.dataset.hasExistingDoc || '0') === '1';
        if (!hasExistingDoc) return;
        event.preventDefault();
        const existingDocName = String(link.dataset.existingDocName || '').trim() || 'Scanned document';
        const approved = await m2ConfirmReplaceExistingDocument(existingDocName);
        if (!approved) return;
        const href = link.getAttribute('href');
        if (!href) return;
        window.open(href, link.getAttribute('target') || '_self', 'noopener');
    }

    function confirmFlowAlertNext() {
        const onNext = flowAlertOnNext;
        flowAlertOnConfirm = null;
        flowAlertOnNext = null;
        closeFlowAlert();
        if (typeof onNext === 'function') onNext();
    }

    function normalizeEligibilityStatus(status) {
        const normalized = String(status || '').toLowerCase();
        if (['passed', 'failed', 'pending', 'not_required'].includes(normalized)) return normalized;
        return 'pending';
    }

    function getEligibilityDecisionKey(checkKey) {
        if (!currentEligibilityApplicantId || !checkKey) return '';
        return `${currentEligibilityApplicantId}:${checkKey}`;
    }

    async function setEligibilityDecision(checkKey, status) {
        const key = getEligibilityDecisionKey(checkKey);
        if (!key) return;
        const normalized = normalizeEligibilityStatus(status);
        if (normalized !== 'passed' && normalized !== 'failed') return;
        if (normalized === 'failed') {
            openEligibilityFailReasonModal(checkKey);
            return;
        }
        await saveEligibilityDecision(checkKey, 'passed', '');
    }

    function getManualDecision(checkKey) {
        const key = getEligibilityDecisionKey(checkKey);
        if (!key) return null;
        const raw = eligibilityManualDecisions[key];
        if (!raw || typeof raw !== 'object') return null;
        if (!['passed', 'failed'].includes(String(raw.status || '').toLowerCase())) return null;
        return raw;
    }

    function getEligibilityStatusUi(overall) {
        const data = overall || {};
        if (data.blacklist_blocked) return { label: 'Blocked - Blacklisted', cls: 'blocked', title: '' };
        if (data.has_application) {
            const label = String(data.application_stage_label || 'Form Released').trim() || 'Form Released';
            const st = String(data.application_status || '').trim();
            let cls = 'ready';
            if (st === 'draft') cls = 'pending';
            else if (st === 'awarded') cls = 'followup';
            return { label, cls, title: '' };
        }
        if (!data.required_docs_complete) return { label: 'Docs Incomplete', cls: 'pending', title: '' };
        if (data.situation_docs_ready === false) return { label: 'Needs Situation Docs', cls: 'pending', title: '' };
        if (String(data.certification_status || '') === 'pending') return { label: 'Pending Certification', cls: 'pending', title: '' };
        if (String(data.field_evidence_status || '') === 'missing') return { label: 'Needs Field Evidence', cls: 'pending', title: '' };
        if (data.has_failed_checks) {
            return {
                label: 'Pending Follow-up',
                cls: 'followup',
                title: 'One or more eligibility checks marked Missing — reviewer follow-up required.',
            };
        }
        if (data.form_generation_ready) return { label: 'Ready for Form', cls: 'ready', title: '' };
        return { label: 'Under Review', cls: 'pending', title: '' };
    }

    function updateApplicantRowEligibilityStatus(applicantId, overall) {
        const id = String(applicantId || '').trim();
        if (!id) return;
        const row = document.querySelector(`tr[data-applicant-id="${id}"]`);
        if (!row) return;
        const container = row.querySelector('.col-eligibility .col-status-wrap');
        if (!container) return;
        const status = getEligibilityStatusUi(overall || {});
        let hint = String((overall && overall.readiness_hint) || '').trim();
        if (overall && overall.has_application) {
            hint = String((overall.application_number || '')).trim();
        }
        container.innerHTML = `
            <span class="m2-readiness-chip ${status.cls}"${status.title ? ` title="${escapeHtml(status.title)}"` : ''}>${escapeHtml(status.label)}</span>
            ${hint ? `<div class="m2-readiness-hint">${escapeHtml(hint)}</div>` : ''}
        `;
        syncApplicantRowGenerateFormAction(id, overall || {});
    }

    function syncApplicantRowGenerateFormAction(applicantId, overall) {
        const id = String(applicantId || '').trim();
        if (!id) return;
        const row = document.querySelector(`tr[data-applicant-id="${id}"]`);
        if (!row) return;
        const actionsWrap = row.querySelector('.col-actions > div');
        if (!actionsWrap) return;
        const existingBtn = actionsWrap.querySelector(`button[onclick*="proceedToFormQueue('${id}')"]`);
        if (existingBtn) existingBtn.remove();
    }

    // markApplicantRowFormGenerated removed — dead code (row refreshed via window.location.reload)
    async function saveEligibilityDecision(checkKey, status, failureReason, opts = {}) {
        const applicantId = currentEligibilityApplicantId;
        if (!applicantId || !checkKey) return null;
        const formData = new FormData();
        formData.append('applicant_id', applicantId);
        formData.append('check_key', checkKey);
        formData.append('status', status);
        formData.append('failure_reason', failureReason || '');
        if (status === 'failed') {
            formData.append('notify_applicant_sms', opts.notifyApplicantSms ? '1' : '0');
        }
        formData.append('csrfmiddlewaretoken', MODULE2_CSRF_TOKEN);
        try {
            const response = await fetch(MODULE2_SAVE_ELIGIBILITY_URL, {
                method: 'POST',
                body: formData,
            });
            const data = await response.json();
            if (!data.success) {
                showFlowAlert(data.error || 'Unable to save checklist decision.');
                return null;
            }
            const decisionKey = getEligibilityDecisionKey(checkKey);
            if (decisionKey) {
                eligibilityManualDecisions[decisionKey] = {
                    status: data.decision.status,
                    failure_reason: data.decision.failure_reason || '',
                };
            }
            // Fast local update: keep modal stable (no full content clear/flicker).
            if (lastEligibilitySnapshot) {
                renderEligibilityChecklist(lastEligibilitySnapshot);
            }
            // Silent sync: refresh backend snapshot without wiping/repainting modal content.
            const freshSnapshot = await fetchEligibilitySnapshot(applicantId, {
                preserveContent: true,
                renderChecklist: false,
            });
            if (freshSnapshot && freshSnapshot.overall) {
                updateApplicantRowEligibilityStatus(applicantId, freshSnapshot.overall);
            }
            return data;
        } catch (error) {
            showFlowAlert(error.message || 'Unable to save checklist decision.');
            return null;
        }
    }

    function openEligibilityFailReasonModal(checkKey) {
        pendingFailedCheckKey = String(checkKey || '');
        const inputEl = document.getElementById('eligibilityFailReasonInput');
        const errorEl = document.getElementById('eligibilityFailReasonError');
        const existing = getManualDecision(checkKey);
        if (inputEl) inputEl.value = existing && existing.status === 'failed' ? (existing.failure_reason || '') : '';
        if (errorEl) {
            errorEl.style.display = 'none';
            errorEl.textContent = '';
        }
        const smsCb = document.getElementById('eligibilityFailNotifySms');
        if (smsCb) smsCb.checked = true;
        const modal = document.getElementById('eligibilityFailReasonModal');
        if (modal) modal.classList.add('active');
    }

    function closeEligibilityFailReasonModal(event) {
        if (event && event.target && event.target.id !== 'eligibilityFailReasonModal') return;
        pendingFailedCheckKey = '';
        const modal = document.getElementById('eligibilityFailReasonModal');
        if (modal) modal.classList.remove('active');
    }

    async function submitEligibilityFailedReason() {
        const checkKey = pendingFailedCheckKey;
        const inputEl = document.getElementById('eligibilityFailReasonInput');
        const errorEl = document.getElementById('eligibilityFailReasonError');
        const reason = String(inputEl ? inputEl.value : '').trim();
        if (reason.length < 5) {
            if (errorEl) {
                errorEl.textContent = 'Please enter a clear reason (at least 5 characters).';
                errorEl.style.display = 'block';
            }
            return;
        }
        const smsCb = document.getElementById('eligibilityFailNotifySms');
        const notifySms = smsCb ? smsCb.checked : false;
        const data = await saveEligibilityDecision(checkKey, 'failed', reason, { notifyApplicantSms: notifySms });
        if (!data) return;
        closeEligibilityFailReasonModal();
        let msg = 'Missing decision saved.';
        if (notifySms) {
            if (data.sms_sent) {
                msg += ' ' + (data.sms_detail || 'SMS sent to applicant.');
            } else {
                msg += ' ' + (data.sms_detail || 'SMS was not sent.');
            }
        }
        const alertTone = (!notifySms || data.sms_sent) ? 'success' : 'default';
        showFlowAlert(msg, 'Eligibility', null, alertTone);
    }

    let m2SitCarouselIndex = 0;

    function m2SitCarouselSync() {
        const track = document.getElementById('m2SitCarouselTrack');
        const slides = track ? track.querySelectorAll('.m2-elig-carousel-slide') : [];
        const total = slides.length;
        if (!total) return;
        if (m2SitCarouselIndex < 0) m2SitCarouselIndex = 0;
        if (m2SitCarouselIndex >= total) m2SitCarouselIndex = total - 1;
        track.style.transform = 'translateX(-' + (m2SitCarouselIndex * 100) + '%)';
        const counter = document.getElementById('m2SitCarouselCounter');
        if (counter) counter.textContent = (m2SitCarouselIndex + 1) + ' / ' + total;
        document.querySelectorAll('#m2SitCarouselDots .m2-elig-carousel-dot').forEach(function (dot, i) {
            dot.classList.toggle('is-active', i === m2SitCarouselIndex);
            dot.setAttribute('aria-current', i === m2SitCarouselIndex ? 'true' : 'false');
        });
        const prev = document.getElementById('m2SitCarouselPrev');
        const next = document.getElementById('m2SitCarouselNext');
        if (prev) prev.disabled = m2SitCarouselIndex <= 0;
        if (next) next.disabled = m2SitCarouselIndex >= total - 1;
    }

    function m2SitCarouselStep(delta) {
        m2SitCarouselIndex += delta;
        m2SitCarouselSync();
    }

    function m2SitCarouselGoTo(index) {
        m2SitCarouselIndex = index;
        m2SitCarouselSync();
    }

    function renderEligibilityChecklist(snapshot) {
        const listEl = document.getElementById('eligibilityNextChecklist');
        const docEvidenceEl = document.getElementById('eligibilityNextDocEvidence');
        if (!listEl || !docEvidenceEl) return;
        lastEligibilitySnapshot = snapshot || null;

        const subtitle = document.getElementById('eligibilityNextSubtitle');
        const chipsRow = document.getElementById('eligibilityNextInfoChips');
        const applicantName = snapshot?.applicant?.full_name || lastPrecheckApplicantName || '';
        const situation = snapshot?.situation || {};
        const sc = snapshot?.situation_certification || {};
        if (subtitle) {
            const sitTitle = (situation.title || '').trim();
            subtitle.textContent = applicantName
                ? `Applicant: ${applicantName}${sitTitle ? ' (' + sitTitle + ')' : ''}`
                : 'Applicant: —';
        }
        if (chipsRow) {
            const ap = snapshot?.applicant || {};
            const ref = (snapshot?.reference_number || '').trim();
            const barangay = (ap.barangay || '').trim();
            const dateReg = (ap.registered_at || '').trim();
            const sitLabel = (situation.option || '').trim();
            const staff = (ap.staff_name || '').trim();
            const chip = (text) => text
                ? `<span class="m2-info-chip">${escapeHtml(text)}</span>`
                : '';
            chipsRow.innerHTML = [
                chip(ref ? `Ref #${ref}` : ''),
                chip(barangay),
                chip(dateReg),
                chip(sitLabel),
                chip(staff ? `Staff: ${staff}` : ''),
            ].filter(Boolean).join('');
            chipsRow.style.display = chipsRow.innerHTML ? 'flex' : 'none';
        }


        const checks = snapshot?.checks || {};
        const gates = snapshot?.gates || {};
        const entries = [
            { key: 'property', is_reviewable: true, ...(checks.property || {}) },
            { key: 'age_residency', is_reviewable: true, ...(checks.age_residency || {}) },
            { key: 'income', is_reviewable: true, ...(checks.income || {}) },
            { key: 'household', is_reviewable: true, ...(checks.household || {}) },
            { key: 'voter', is_reviewable: true, ...(checks.voter || {}) },
        ].filter(Boolean);

        const failedChecks = entries.filter((entry) => {
            const d = getManualDecision(entry.key);
            return d && d.status === 'failed';
        });
        const undecidedChecks = entries.filter((entry) => {
            const d = getManualDecision(entry.key);
            if (d && (d.status === 'passed' || d.status === 'failed')) return false; // manually decided
            if (entry.key === 'voter' && entry.status === 'passed') return false;
            return true;
        });

        const sitChecks = Array.isArray(sc.checks) ? sc.checks : [];
        const isWalkInInfo = !!sc.walk_in_informational;
        const sitMissingCount = isWalkInInfo ? 0 : sitChecks.filter(ch => !ch.done).length;


        const passedChecks = entries.filter((entry) => {
            const d = getManualDecision(entry.key);
            if (d && d.status === 'passed') return true;
            if (entry.key === 'voter' && entry.status === 'passed' && !(d && d.status === 'failed')) return true;
            return false;
        });
        const missingEvidenceChecks = entries.filter((entry) => {
            const d = getManualDecision(entry.key);
            const isAutoPassed = entry.key === 'voter' && entry.status === 'passed' && !(d && d.status === 'failed');
            if (isAutoPassed) return false;
            const hasDoc = !!(entry && entry.view_document && entry.view_document.url);
            const hasVault = !!(entry && entry.vault_upload_url);
            return !hasDoc && !hasVault;
        });

        const totalPendingCount = undecidedChecks.length + sitMissingCount;

        // Short inline status label — absorbed into the chips bar
        const pendingLabel = totalPendingCount > 0
            ? `<span class="m2-summary-status-label m2-summary-status-label--pending">${totalPendingCount} requirement${totalPendingCount === 1 ? '' : 's'} pending</span>`
            : (failedChecks.length
                ? `<span class="m2-summary-status-label m2-summary-status-label--fail">${failedChecks.length} missing &mdash; blocks Ready for Form</span>`
                : `<span class="m2-summary-status-label m2-summary-status-label--ok">All requirements complete</span>`);

        const proceedFormBtn = document.getElementById('eligibilityProceedFormModalBtn');
        const overall = snapshot?.overall || {};
        const isFormReady = !!(overall.form_generation_ready || (totalPendingCount === 0 && failedChecks.length === 0));

        // Progress label: X / Y Requirements Completed
        const progressLabel = document.getElementById('eligibilityProgressLabel');
        const totalChecks = entries.length + (isWalkInInfo ? 0 : sitChecks.length);
        const completedChecks = passedChecks.length + (isWalkInInfo ? sitChecks.length : sitChecks.filter(ch => !!ch.done).length);
        if (progressLabel) {
            const allDone = totalPendingCount === 0 && failedChecks.length === 0;
            progressLabel.textContent = allDone
                ? `\u2714 All ${totalChecks} Requirements Completed`
                : `${completedChecks} / ${totalChecks} Requirements Completed`;
            progressLabel.classList.toggle('m2-progress-label--done', allDone);
        }

        if (proceedFormBtn) {
            const canProceed = isFormReady && !overall.has_application;
            proceedFormBtn.style.display = 'inline-flex';
            const wasReady = proceedFormBtn.classList.contains('m2-proceed--ready');
            if (canProceed) {
                proceedFormBtn.removeAttribute('disabled');
                proceedFormBtn.disabled = false;
                proceedFormBtn.title = 'Proceed to Form Generation and send reminder SMS';
                proceedFormBtn.onclick = function() {
                    handleProceedFromModal();
                };
                if (!wasReady) {
                    // Trigger animation only on transition to ready
                    proceedFormBtn.classList.remove('m2-proceed--ready');
                    void proceedFormBtn.offsetWidth; // reflow to restart animation
                    proceedFormBtn.classList.add('m2-proceed--ready');
                }
            } else {
                proceedFormBtn.setAttribute('disabled', 'disabled');
                proceedFormBtn.disabled = true;
                proceedFormBtn.onclick = null;
                proceedFormBtn.classList.remove('m2-proceed--ready');
                if (failedChecks.length > 0) {
                    proceedFormBtn.title = `Resolve missing requirements first (${failedChecks.length} missing)`;
                } else if (totalPendingCount > 0) {
                    proceedFormBtn.title = `Complete all requirements first (${totalPendingCount} remaining)`;
                } else {
                    proceedFormBtn.title = 'Application form already generated or requirements incomplete.';
                }
            }
        }


        if (totalPendingCount === 0 && failedChecks.length === 0) {
            const applicantId = snapshot?.applicant?.id || currentEligibilityApplicantId;
            if (String(overall.certification_status || '') === 'pending' && !window._autoCertifyingMap?.[applicantId]) {
                if (!window._autoCertifyingMap) window._autoCertifyingMap = {};
                window._autoCertifyingMap[applicantId] = true;
                markSituationCertifiedFromModal().finally(() => {
                    if (window._autoCertifyingMap) delete window._autoCertifyingMap[applicantId];
                });
            } else if (applicantId && window._lastCertifiedAlertApplicantId !== applicantId) {
                window._lastCertifiedAlertApplicantId = applicantId;
                showFlowAlert(
                    'Situation certification completed successfully. You may now proceed with Application Form Generation.',
                    'Situation Certification',
                    null,
                    'success'
                );
            }
        }

        const buildCheckCardHtml = (entry) => {
            const manualDecision = getManualDecision(entry.key);
            const manualStatus = manualDecision ? manualDecision.status : '';
            const title = entry.title || 'Check';
            const reason = entry.reason || '';
            const failedReason = manualDecision && manualDecision.status === 'failed'
                ? (manualDecision.failure_reason || '')
                : '';
            const docUrl = entry?.view_document?.url || '';
            const docName = entry?.view_document?.name || 'Scanned document';
            const vaultUploadUrl = typeof entry.vault_upload_url === 'string' ? entry.vault_upload_url.trim() : '';
            const vaultScanUrl = typeof entry.vault_scan_url === 'string' ? entry.vault_scan_url.trim() : '';
            const hasManualStatus = manualStatus === 'passed' || manualStatus === 'failed';
            const manualLabel = manualStatus === 'passed' ? 'Passed' : (manualStatus === 'failed' ? 'Missing' : '');
            const evidenceHtml = formatM2EvidenceHtml(entry.evidence);
            const isVoterAutoPassed = entry.key === 'voter' && entry.status === 'passed' && !hasManualStatus;
            const chipHtml = hasManualStatus
                ? `<span class="eligibility-check-chip ${manualStatus}">${manualLabel}</span>`
                : (isVoterAutoPassed
                    ? `<span class="eligibility-check-chip auto-passed" title="Auto-passed: voter certification is optional and profile confirms registered voter">Auto-passed</span>`
                    : '');
            let cardToneClass = 'm2-elig-card m2-elig-card--compact';
            if (manualStatus === 'failed') cardToneClass += ' m2-elig-card--fail';
            else if (manualStatus === 'passed') cardToneClass += ' m2-elig-card--pass';
            else if (isVoterAutoPassed) cardToneClass += ' m2-elig-card--pass';
            else cardToneClass += ' m2-elig-card--pending';
            const safeDocHref = docUrl ? String(docUrl).replace(/"/g, '&quot;') : '';
            const safeVaultUploadHref = vaultUploadUrl ? vaultUploadUrl.replace(/"/g, '&quot;') : '';
            const safeVaultScanHref = vaultScanUrl ? vaultScanUrl.replace(/"/g, '&quot;') : '';
            const eligDwtMapping = M2_ELIGIBILITY_CHECK_TO_INTAKE_DOC[entry.key];
            const hasExistingDocAttr = docUrl ? '1' : '0';
            const viewDocBtnHtml = docUrl
                ? `<a class="eligibility-view-doc-btn" href="${safeDocHref}" target="_blank" rel="noopener noreferrer" title="${escapeHtml(docName)}"><span class="btn-icon-block">${M2_VIEW_ICON_SVG}</span><span>View</span></a>`
                : '';
            const decisionButtonsHtml = (entry.is_reviewable && !isVoterAutoPassed)
                ? `<button type="button" class="eligibility-decision-btn ${manualStatus === 'passed' ? 'active-pass' : ''}" onclick="setEligibilityDecision('${entry.key}', 'passed')"><span class="btn-icon-block">${M2_PASS_ICON_SVG}</span><span>Pass</span></button>
                    <button type="button" class="eligibility-decision-btn ${manualStatus === 'failed' ? 'active-fail' : ''}" onclick="setEligibilityDecision('${entry.key}', 'failed')"><span class="btn-icon-block">${M2_MISSING_ICON_SVG}</span><span>Missing</span></button>`
                : '';
            const actionsRow = (viewDocBtnHtml || decisionButtonsHtml)
                ? `<div class="m2-elig-actions">
                    <div class="m2-elig-decision-actions">
                        ${viewDocBtnHtml}
                        ${decisionButtonsHtml}
                    </div>
                   </div>`
                : '';

            return `
                <div class="${cardToneClass}">
                    <div class="m2-elig-card-head">
                        <h4 class="m2-elig-card-title">${escapeHtml(title)}</h4>
                        ${chipHtml}
                    </div>
                    ${reason ? `<div class="m2-elig-card-reason">${escapeHtml(reason)}</div>` : ''}
                    ${failedReason ? `<div class="m2-elig-fail-msg">${escapeHtml(failedReason)}</div>` : ''}
                    ${evidenceHtml}
                    ${actionsRow}
                </div>
            `;
        };

        let situationCardsHtml = '';
        if (isWalkInInfo) {
            // Option D requires no situation-specific uploads; 5 core cards rendered.
            situationCardsHtml = '';
        } else if (sitChecks.length > 0) {
            situationCardsHtml = sitChecks.map((c, idx) => {
                return buildM2SituationCertCardHtml(c, idx, sitChecks, sc, false);
            }).join('');
        }

        const totalSituationCards = isWalkInInfo ? 0 : sitChecks.length;
        const totalCards = entries.length + totalSituationCards;

        // Option A (7 cards): 4 in Row 1, 3 in Row 2.
        // Options B & C (6 cards): 3 in Row 1, 3 in Row 2.
        // Option D (5 cards): 3 in Row 1, 2 centered in Row 2.
        const firstRowCount = (totalCards === 5 || totalCards === 6) ? 3 : 4;
        const firstRowEntries = entries.slice(0, firstRowCount);
        const secondRowCoreEntries = entries.slice(firstRowCount);

        const firstRowCards = firstRowEntries.map((entry) => buildCheckCardHtml(entry)).join('');
        const secondRowCoreCards = secondRowCoreEntries.map((entry) => buildCheckCardHtml(entry)).join('');
        const secondRowCards = `${secondRowCoreCards}${situationCardsHtml}`;

        const row1GridClass = (totalCards === 5 || totalCards === 6) ? 'm2-elig-grid-row1 m2-elig-grid-3col' : 'm2-elig-grid-row1';
        const row2GridClass = (totalCards === 5) ? 'm2-elig-grid-row2 m2-elig-grid-2col-centered' : 'm2-elig-grid-row2 m2-elig-grid-3col';

        // Inject summary chips styles once
        if (!document.getElementById('m2-summary-chips-style')) {
            const s = document.createElement('style');
            s.id = 'm2-summary-chips-style';
            s.textContent = [
                '.m2-summary-chips{display:flex;align-items:center;gap:0.45rem;flex-wrap:wrap;margin-bottom:0.6rem;}',
                '.m2-summary-chip{display:inline-flex;align-items:center;gap:0.32rem;padding:0.2rem 0.6rem;border-radius:9999px;font-size:0.62rem;font-weight:700;letter-spacing:0.02em;border:1px solid;}',
                '.m2-summary-chip__count{font-size:0.82rem;font-weight:800;line-height:1;}',
                '.m2-summary-chip--passed{background:#dcfce7;border-color:#86efac;color:#166534;}',
                '.m2-summary-chip--pending{background:#fef3c7;border-color:#fde68a;color:#92400e;}',
                '.m2-summary-chip--failed{background:#fee2e2;border-color:#fca5a5;color:#991b1b;}',
                '.m2-summary-chip--missing{background:#dbeafe;border-color:#93c5fd;color:#1e40af;}',
                '.m2-summary-status-label{margin-left:auto;font-size:0.62rem;font-weight:600;padding:0.18rem 0.5rem;border-radius:0.35rem;}',
                '.m2-summary-status-label--pending{color:#92400e;background:#fef3c7;border:1px solid #fde68a;}',
                '.m2-summary-status-label--fail{color:#991b1b;background:#fee2e2;border:1px solid #fca5a5;}',
                '.m2-summary-status-label--ok{color:#166534;background:#dcfce7;border:1px solid #86efac;}'
            ].join('');
            document.head.appendChild(s);
        }


        const summaryChipsHtml = `<div class="m2-summary-chips">
            <span class="m2-summary-chip m2-summary-chip--passed">&#x2714; Passed <span class="m2-summary-chip__count">${passedChecks.length}</span></span>
            <span class="m2-summary-chip m2-summary-chip--pending">&#x23F3; Pending <span class="m2-summary-chip__count">${undecidedChecks.length}</span></span>
            <span class="m2-summary-chip m2-summary-chip--failed">&#x26A0; Missing <span class="m2-summary-chip__count">${failedChecks.length}</span></span>
            ${pendingLabel}
        </div>`;

        docEvidenceEl.innerHTML = '';
        listEl.innerHTML = `
            <div class="m2-elig-outer-card" style="padding: 0.75rem;">
                ${summaryChipsHtml}
                <div class="${row1GridClass}">
                    ${firstRowCards}
                </div>
                <div class="${row2GridClass}">
                    ${secondRowCards}
                </div>
            </div>
        `;
    }


    async function fetchEligibilitySnapshot(applicantId, opts = {}) {
        const preserveContent = !!opts.preserveContent;
        const renderChecklist = opts.renderChecklist !== false;
        const listEl = document.getElementById('eligibilityNextChecklist');
        const docEvidenceEl = document.getElementById('eligibilityNextDocEvidence');
        if (!preserveContent && listEl && !listEl.children.length) {
            listEl.innerHTML = '<div class="m2-elig-outer-card" style="padding:1rem;text-align:center;color:#64748b;font-size:0.8rem;">Loading evaluation checklist…</div>';
            if (docEvidenceEl) docEvidenceEl.innerHTML = '';
        }
        if (!applicantId) {
            if (listEl) listEl.innerHTML = '<div class="eligibility-next-item"><span class="line-title">No applicant selected.</span></div>';
            return null;
        }
        const formData = new FormData();
        formData.append('applicant_id', applicantId);
        formData.append('csrfmiddlewaretoken', MODULE2_CSRF_TOKEN);
        try {
            const response = await fetch(MODULE2_ELIGIBILITY_SNAPSHOT_URL, {
                method: 'POST',
                body: formData,
            });
            const contentType = (response.headers.get('content-type') || '').toLowerCase();
            if (response.redirected || !contentType.includes('application/json')) {
                if (listEl) listEl.innerHTML = '<div class="eligibility-next-item"><span class="line-title">Your session may have expired. Please log in again, then retry.</span></div>';
                return;
            }
            const data = await response.json();
            if (!data.success) {
                if (listEl) listEl.innerHTML = `<div class="eligibility-next-item"><span class="line-title">${data.error || 'Unable to load eligibility snapshot.'}</span></div>`;
                return null;
            }
            Object.keys(eligibilityManualDecisions).forEach((key) => {
                if (key.startsWith(`${currentEligibilityApplicantId}:`)) delete eligibilityManualDecisions[key];
            });
            const savedDecisions = data.saved_decisions || {};
            Object.keys(savedDecisions).forEach((checkKey) => {
                const decisionKey = getEligibilityDecisionKey(checkKey);
                if (!decisionKey) return;
                const d = savedDecisions[checkKey] || {};
                const normalized = normalizeEligibilityStatus(d.status);
                if (normalized === 'passed' || normalized === 'failed') {
                    eligibilityManualDecisions[decisionKey] = {
                        status: normalized,
                        failure_reason: String(d.failure_reason || ''),
                    };
                }
            });
            if (renderChecklist) renderEligibilityChecklist(data);
            else lastEligibilitySnapshot = data || null;
            return data;
        } catch (error) {
            if (!preserveContent && listEl) {
                listEl.innerHTML = `<div class="eligibility-next-item"><span class="line-title">Error loading checklist: ${error.message}</span></div>`;
            }
            return null;
        }
    }

    function openEligibilityNextModal(applicantName, applicantId) {
        currentEligibilityApplicantId = applicantId || '';
        window._lastCertifiedAlertApplicantId = null;
        const subtitle = document.getElementById('eligibilityNextSubtitle');
        if (subtitle) {
            subtitle.textContent = applicantName
                ? `Applicant: ${applicantName}`
                : 'Applicant: —';
        }
        const modal = document.getElementById('eligibilityNextModal');
        if (modal) modal.classList.add('active');
        fetchEligibilitySnapshot(applicantId);
    }

    function backToEligibilityChecklistModal() {
        closeSituationCertificationModal();
        const modal = document.getElementById('eligibilityNextModal');
        if (modal) modal.classList.add('active');
    }

    async function openSituationCertificationModal(opts) {
        opts = opts || {};
        const skipFetch = !!opts.skipFetch;
        if (!skipFetch) m2SitCarouselIndex = 0;
        if (!currentEligibilityApplicantId) {
            showFlowAlert('Load the eligibility checklist first before proceeding.');
            return;
        }
        if (!skipFetch) {
            await fetchEligibilitySnapshot(currentEligibilityApplicantId);
        }
        const snap = lastEligibilitySnapshot;
        if (!snap) {
            showFlowAlert('Unable to load eligibility data for situation certification.');
            return;
        }
        const modal = document.getElementById('situationCertificationModal');
        const content = document.getElementById('situationCertificationContent');
        const subtitle = document.getElementById('situationCertificationSubtitle');
        const situation = snap.situation || {};
        const sc = snap.situation_certification || {};
        const option = situation.option || 'Not set';
        const code = situation.code || '';
        const title = situation.title || 'Applicant Situation is not yet declared';
        const desc = situation.description || 'No situation details are available.';
        if (subtitle) subtitle.textContent = `${option} · ${title}`;
        const walkInInformational = !!sc.walk_in_informational;
        const checks = Array.isArray(sc.checks) ? sc.checks : [];

        if (content) {
            if (walkInInformational) {
                content.innerHTML = `
                    <div class="m2-elig-outer-card">
                        <div class="m2-elig-card m2-elig-card--pass">
                            <div class="m2-elig-card-head">
                                <h4 class="m2-elig-card-title">Applicant Situation</h4>
                                <span class="eligibility-check-chip passed">Ready</span>
                            </div>
                            <div class="m2-elig-card-reason">No situation-specific uploads required for Option&nbsp;D. Press Continue when ready.</div>
                        </div>
                    </div>`;
            } else {
                const missingCount = checks.filter((ch) => !ch.done).length;
                const multiMissing = missingCount > 1;
                const blockText = String(sc.blocking_summary || '').trim();
                const bannerHtml = (!sc.ready && multiMissing && blockText)
                    ? `<div class="m2-elig-banner m2-elig-banner--fail">${escapeHtml(blockText)}</div>`
                    : '';
                const suppressReasonDup = !!bannerHtml;
                if (m2SitCarouselIndex >= checks.length) {
                    m2SitCarouselIndex = Math.max(0, checks.length - 1);
                }
                const carouselDotsHtml = checks.map(function (c, idx) {
                    let dotClass = 'm2-elig-carousel-dot';
                    if (idx === m2SitCarouselIndex) dotClass += ' is-active';
                    if (c.done) dotClass += ' is-pass';
                    else dotClass += ' is-fail';
                    return `<button type="button" class="${dotClass}" aria-label="Go to requirement ${idx + 1}: ${escapeHtml(String(c.label || 'Requirement'))}" onclick="m2SitCarouselGoTo(${idx})"></button>`;
                }).join('');
                const checkSlides = checks.map(function (c, idx) {
                    const cardHtml = buildM2SituationCertCardHtml(c, idx, checks, sc, suppressReasonDup);
                    return `<div class="m2-elig-carousel-slide" role="group" aria-roledescription="slide" aria-label="Requirement ${idx + 1} of ${checks.length}">${cardHtml}</div>`;
                }).join('');
                content.innerHTML = `
                    <div class="m2-elig-outer-card">
                        ${bannerHtml}
                        <div class="m2-elig-carousel" id="m2SitCarousel">
                            <div class="m2-elig-carousel-toolbar">
                                <span class="m2-elig-carousel-counter" id="m2SitCarouselCounter">1 / ${checks.length}</span>
                                <div class="m2-elig-carousel-dots" id="m2SitCarouselDots">${carouselDotsHtml}</div>
                            </div>
                            <div class="m2-elig-carousel-viewport">
                                <button type="button" class="m2-elig-carousel-nav" id="m2SitCarouselPrev" aria-label="Previous requirement" onclick="m2SitCarouselStep(-1)">‹</button>
                                <div class="m2-elig-carousel-track-wrap">
                                    <div class="m2-elig-carousel-track" id="m2SitCarouselTrack">${checkSlides}</div>
                                </div>
                                <button type="button" class="m2-elig-carousel-nav" id="m2SitCarouselNext" aria-label="Next requirement" onclick="m2SitCarouselStep(1)">›</button>
                            </div>
                        </div>
                    </div>`;
                m2SitCarouselSync();
            }
        }
        const certifyBtn = document.getElementById('markSituationCertifiedBtn');
        if (certifyBtn) {
            if (walkInInformational) {
                certifyBtn.textContent = 'Continue';
                certifyBtn.disabled = false;
                certifyBtn.style.opacity = '1';
                certifyBtn.style.cursor = 'pointer';
                certifyBtn.title = 'Complete Applicant Situation step and record eligibility';
            } else {
                certifyBtn.textContent = 'Mark Situation Certified';
                certifyBtn.disabled = !sc.ready;
                certifyBtn.style.opacity = certifyBtn.disabled ? '0.55' : '1';
                certifyBtn.style.cursor = certifyBtn.disabled ? 'not-allowed' : 'pointer';
                certifyBtn.title = sc.ready ? '' : String(sc.blocking_summary || 'Complete situation certification requirements');
            }
        }
        const eligibilityModal = document.getElementById('eligibilityNextModal');
        if (eligibilityModal) eligibilityModal.classList.remove('active');
        if (modal) modal.classList.add('active');
    }

    /** Cross-tab + same-machine sync: field desk submits photos → Module 2 situation modal refreshes without manual reload. */
    const M2_FIELD_CERT_SYNC_KEY = 'tha_field_cert_sync';
    /** BroadcastChannel notifies all same-origin contexts immediately (localStorage `storage` skips the writer tab). */
    const M2_FIELD_CERT_BC_NAME = 'tha_field_cert_sync_bc';
    let m2FieldCertBc = null;
    try {
        if (typeof BroadcastChannel !== 'undefined') {
            m2FieldCertBc = new BroadcastChannel(M2_FIELD_CERT_BC_NAME);
            m2FieldCertBc.onmessage = function () {
                scheduleM2EligibilityOpenViewsRefresh();
            };
        }
    } catch (ignoreBc) {
        m2FieldCertBc = null;
    }
    let m2EligibilitySyncTimer = null;
    function scheduleM2EligibilityOpenViewsRefresh() {
        if (m2EligibilitySyncTimer) clearTimeout(m2EligibilitySyncTimer);
        m2EligibilitySyncTimer = setTimeout(function () {
            m2EligibilitySyncTimer = null;
            refreshM2EligibilityOpenViews();
        }, 250);
    }
    async function refreshM2EligibilityOpenViews() {
        const id = currentEligibilityApplicantId;
        if (!id) return;
        const sit = document.getElementById('situationCertificationModal');
        const elig = document.getElementById('eligibilityNextModal');
        const sitOpen = sit && sit.classList.contains('active');
        const eligOpen = elig && elig.classList.contains('active');
        if (!sitOpen && !eligOpen) return;
        const fetchOpts = { preserveContent: true };
        const data = await fetchEligibilitySnapshot(id, fetchOpts);
        if (!data) return;
        if (sitOpen) {
            await openSituationCertificationModal({ skipFetch: true });
        }
    }
    window.addEventListener('storage', function (e) {
        if (e.key !== M2_FIELD_CERT_SYNC_KEY || e.newValue == null) return;
        scheduleM2EligibilityOpenViewsRefresh();
    });
    document.addEventListener('visibilitychange', function () {
        if (document.visibilityState !== 'visible') return;
        scheduleM2EligibilityOpenViewsRefresh();
    });
    window.addEventListener('pageshow', function (ev) {
        if (ev.persisted) scheduleM2EligibilityOpenViewsRefresh();
    });

    // markSituationCertifiedFromModal removed — dead code (handled by handleProceedFromModal)

    function closeSituationCertificationModal(event) {
        if (event && event.target && event.target.id !== 'situationCertificationModal') return;
        const modal = document.getElementById('situationCertificationModal');
        if (modal) modal.classList.remove('active');
    }

    function closeEligibilityNextModal(event) {
        if (event && event.target && event.target.id !== 'eligibilityNextModal') return;
        const modal = document.getElementById('eligibilityNextModal');
        if (modal) modal.classList.remove('active');
        closeEligibilityFailReasonModal();
        closeSituationCertificationModal();
    }

    function backToPrecheckAlert() {
        closeEligibilityNextModal();
        showFlowAlert(
            lastPrecheckMessage,
            'Evaluation Pre-check',
            null,
            'success',
            () => openEligibilityNextModal(lastPrecheckApplicantName, lastPrecheckApplicantId)
        );
    }

    // Filter functions
    function filterByStage(stage) {
        const search = document.getElementById('searchInput')?.value || '';
        window.location.href = `?stage=${stage}&search=${encodeURIComponent(search)}&page=1`;
    }

    document.getElementById('evaluationsSearchForm')?.addEventListener('submit', function () {
        const pageInput = this.querySelector('input[name="page"]');
        if (pageInput) pageInput.remove();
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            // Only close awardModal when it is actually open
            if (document.getElementById('awardModal')?.classList.contains('active')) {
                closeAwardModal();
            }
        }
    });

    async function runEvaluatePrecheck(applicantId, applicantName) {
        if (!applicantId) return;
        const formData = new FormData();
        formData.append('applicant_id', applicantId);
        formData.append('csrfmiddlewaretoken', MODULE2_CSRF_TOKEN);

        try {
            const response = await fetch(MODULE2_EVALUATE_PRECHECK_URL, {
                method: 'POST',
                body: formData,
            });
            const contentType = (response.headers.get('content-type') || '').toLowerCase();
            if (response.redirected || !contentType.includes('application/json')) {
                showFlowAlert(
                    'Session expired or access changed. Please log in again, then retry Evaluation Pre-check.',
                    'Evaluation Pre-check'
                );
                return;
            }
            const data = await response.json();
            if (!data.success) {
                showFlowAlert(
                    data.error || `Precheck failed for ${applicantName || 'this applicant'}.`,
                    'Evaluation Pre-check'
                );
                // If blacklisted auto-disqualification happened, refresh the list.
                if (String(data.error || '').toLowerCase().includes('blacklist')) {
                    setTimeout(() => window.location.reload(), 900);
                }
                return;
            }
            lastPrecheckApplicantName = applicantName || '';
            lastPrecheckApplicantId = applicantId || '';
            lastPrecheckMessage = data.message || `Precheck passed for ${applicantName || 'this applicant'}.`;
            showFlowAlert(
                lastPrecheckMessage,
                'Evaluation Pre-check',
                null,
                'success',
                () => openEligibilityNextModal(applicantName, applicantId)
            );
        } catch (error) {
            showFlowAlert('Precheck request failed: ' + error.message, 'Evaluation Pre-check');
        }
    }

    async function handleProceedFromModal() {
        if (!currentEligibilityApplicantId) return;
        const snap = lastEligibilitySnapshot;
        const overall = snap?.overall || {};
        const isCertified = !!overall.form_generation_ready;
        if (!isCertified) {
            try {
                const formData = new FormData();
                formData.append('applicant_id', currentEligibilityApplicantId);
                formData.append('notes', '');
                formData.append('csrfmiddlewaretoken', MODULE2_CSRF_TOKEN);
                const response = await fetch(MODULE2_MARK_SITUATION_URL, {
                    method: 'POST',
                    body: formData,
                    headers: { 'X-Requested-With': 'XMLHttpRequest' },
                });
                const contentType = (response.headers.get('content-type') || '').toLowerCase();
                if (response.redirected || !contentType.includes('application/json')) {
                    showFlowAlert('Session expired or access changed. Please log in again and retry.', 'ERROR');
                    return;
                }
                const data = await response.json();
                if (!data.success) throw new Error(data.error || 'Unable to complete situation certification.');
            } catch (error) {
                showFlowAlert(error.message || 'Unable to mark situation certified.', 'ERROR');
                return;
            }
        }
        showApplicationFormConfirmModal(currentEligibilityApplicantId);
    }

    function showApplicationFormConfirmModal(applicantId) {
        const overlay = document.getElementById('appFormConfirmOverlay');
        const proceedBtn = document.getElementById('appFormConfirmProceedBtn');
        if (!overlay) {
            if (confirm('Proceed to Form Generation?\nThis will generate an application form and move the applicant to the Ready for Form queue.')) {
                proceedToFormQueue(applicantId);
            }
            return;
        }
        if (proceedBtn) {
            proceedBtn.onclick = function() {
                closeAppFormConfirmModal();
                proceedToFormQueue(applicantId);
            };
        }
        overlay.classList.add('active');
    }

    function closeAppFormConfirmModal() {
        const overlay = document.getElementById('appFormConfirmOverlay');
        if (overlay) overlay.classList.remove('active');
    }

    function closeAppFormConfirmOverlay(event) {
        if (event && event.target && event.target.id === 'appFormConfirmOverlay') {
            closeAppFormConfirmModal();
        }
    }

    async function proceedToFormQueue(applicantId) {
        if (!applicantId) return;
        const formData = new FormData();
        formData.append('applicant_id', applicantId);
        formData.append('csrfmiddlewaretoken', MODULE2_CSRF_TOKEN);
        try {
            const response = await fetch(MODULE2_PROCEED_TO_FORM_QUEUE_URL, {
                method: 'POST',
                body: formData,
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
            });
            const contentType = (response.headers.get('content-type') || '').toLowerCase();
            if (response.redirected || !contentType.includes('application/json')) {
                showFlowAlert(
                    'Your session may have expired or access changed. Please log in again, then retry.',
                    'ERROR'
                );
                return;
            }
            const data = await response.json();
            if (!data.success) {
                throw new Error(data.error || 'Unable to proceed applicant to Ready for Form queue.');
            }
            const smsPlan = data.sms_plan || {};
            showFlowAlert(
                'Applicant moved to FORM GENERATION',
                'SUCCESS',
                () => {
                    closeEligibilityNextModal();
                    window.location.reload();
                },
                'proceed_success'
            );
        } catch (error) {
            showFlowAlert(error.message || 'Unable to proceed to Form Generation.', 'ERROR');
        }
    }

    // Lot Awarding Modal
    function openAwardModal(applicationId, applicantName) {
        const awardAppIdInput = document.getElementById('awardApplicationId');
        if (awardAppIdInput) awardAppIdInput.value = applicationId;
        document.getElementById('awardModalName').textContent = applicantName;
        const awardModalEl = document.getElementById('awardModal');
        if (awardModalEl) awardModalEl.classList.add('active');
        window.setTimeout(function () {
            var sel = document.getElementById('awardHousingUnit');
            if (sel && !sel.disabled) sel.focus();
        }, 30);
    }

    function closeAwardModal() {
        const awardModalEl = document.getElementById('awardModal');
        if (awardModalEl) awardModalEl.classList.remove('active');
        document.getElementById('awardForm').reset();
    }

    document.getElementById('awardModal')?.addEventListener('click', (e) => {
        if (e.target === e.currentTarget) closeAwardModal();
    });

    document.getElementById('awardForm')?.addEventListener('submit', async (e) => {
        e.preventDefault();

        const formData = new FormData(e.target);
        formData.append('csrfmiddlewaretoken', MODULE2_CSRF_TOKEN);

        try {
            const response = await fetch(MODULE2_AWARD_LOT_URL, {
                method: 'POST',
                body: formData
            });
            const data = await response.json();

            if (data.success) {
                showFlowAlert('Lot awarded successfully! SMS notification sent to beneficiary.', 'Award Lot', () => {
                    location.reload();
                }, 'success');
            } else {
                showFlowAlert(data.error || 'Failed to award lot', 'Award Lot');
            }
        } catch (error) {
            showFlowAlert('Error: ' + error.message, 'Award Lot');
        }
    });

    document.getElementById('m2RequirementFileInput')?.addEventListener('change', handleM2RequirementFileSelected);
    document.addEventListener('click', function (event) {
        m2HandleReplaceAwareVaultLinkClick(event);
    });

    // Initialize page
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
    });
