const VAULT_MGMT_INTAKE_DWT_URL = window.MANAGEMENT_CONFIG.intakeDwtUrl;
const VAULT_DRAWER_CAN_INTAKE_SCAN = window.MANAGEMENT_CONFIG.canIntakeScan;

let VaultMgmtDWTObject = null;
let vaultDrawerPendingUploadContext = null;
    if (window.Dynamsoft && window.Dynamsoft.DWT) {
        Dynamsoft.DWT.RegisterEvent('OnWebTwainReady', function () {
            VaultMgmtDWTObject = Dynamsoft.DWT.GetWebTwain('dwtcontrolContainer');
        });
    }

    async function vaultMgmtWaitForDwt(timeoutMs) {
        const t = timeoutMs || 10000;
        const startedAt = Date.now();
        while (!VaultMgmtDWTObject && (Date.now() - startedAt) < t) {
            await new Promise(function (resolve) { setTimeout(resolve, 100); });
        }
        return VaultMgmtDWTObject;
    }

    function vaultMgmtNotify(message, title, variant) {
        if (typeof window.showFlowAlert === 'function') {
            window.showFlowAlert(message, title || 'Notice', null, variant || 'default');
        } else {
            window.alert(message);
        }
    }

    async function vaultMgmtRunSignedApplicationDwtScan() {
        const applicantId = String(document.getElementById('applicantSelect')?.value || '').trim();
        const docType = String(document.getElementById('uploadDocumentTypeSelect')?.value || '').trim();
        if (!applicantId) {
            vaultMgmtNotify('Select an applicant first.');
            return;
        }
        if (docType !== 'signed_application') {
            vaultMgmtNotify('Choose document type “Physically signed application (scan)” before scanning.');
            return;
        }
        const btn = document.getElementById('vaultMgmtDwtScanBtn');
        const labelEl = btn ? btn.querySelector('.dm-action-btn-label') : null;
        const oldText = labelEl ? labelEl.textContent : '';
        if (btn) {
            btn.disabled = true;
            if (labelEl) labelEl.textContent = 'Scanning…';
        }
        try {
            const dwt = await vaultMgmtWaitForDwt();
            if (!dwt) throw new Error('Scanner SDK is not ready. Refresh the page and try again.');
            await dwt.SelectSourceAsync();
            const beforeCount = Number(dwt.HowManyImagesInBuffer || 0);
            await dwt.AcquireImageAsync({ IfCloseSourceAfterAcquire: true });
            const afterCount = Number(dwt.HowManyImagesInBuffer || 0);
            if (afterCount <= beforeCount) throw new Error('No image was acquired from the scanner.');
            const index = Number(dwt.CurrentImageIndexInBuffer);
            const uploadUrl = `${VAULT_MGMT_INTAKE_DWT_URL}?applicant_id=${encodeURIComponent(applicantId)}&doc_key=doc_signed_application&doc_code=SIGNED`;
            const refOpt = document.getElementById('applicantSelect').selectedOptions[0];
            const refLabel = refOpt ? String(refOpt.textContent || '').trim().replace(/\s+/g, '_').slice(0, 80) : 'applicant';
            const fileName = `${refLabel}_signed_application.png`;

            await new Promise(function (resolve, reject) {
                dwt.HTTPUpload(
                    uploadUrl,
                    [index],
                    Dynamsoft.DWT.EnumDWT_ImageType.IT_PNG,
                    Dynamsoft.DWT.EnumDWT_UploadDataFormat.Binary,
                    fileName,
                    function (httpResponse) {
                        resolve(httpResponse);
                    },
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
                            } catch (_err) {}
                        }
                        reject(new Error(message));
                    }
                );
            });
            vaultMgmtNotify('Scan saved to the document vault.', 'Scan complete', 'success');
            closeUploadModal();
            location.reload();
        } catch (error) {
            vaultMgmtNotify((error && error.message) ? error.message : 'Unable to complete scan.');
            if (labelEl) labelEl.textContent = oldText || 'Scan document';
        } finally {
            if (btn) {
                btn.disabled = false;
                if (labelEl && labelEl.textContent === 'Scanning…') {
                    labelEl.textContent = oldText || 'Scan document';
                }
            }
        }
    }

function vaultDrawerEscapeHtml(text) {
    const d = document.createElement('div');
    d.textContent = text == null ? '' : String(text);
    return d.innerHTML;
}

let VAULT_DRAWER_MAP = {};
let vaultDrawerApplicantId = null;
let vaultDrawerApplicantName = '';

function loadVaultDrawerMapFromDom() {
    const el = document.getElementById('vault-drawer-data');
    if (!el || el.textContent == null) {
        return false;
    }
    const raw = el.textContent.trim();
    if (!raw) {
        VAULT_DRAWER_MAP = {};
        return false;
    }
    try {
        VAULT_DRAWER_MAP = JSON.parse(raw);
        return true;
    } catch (err) {
        console.error('vault-drawer-data JSON parse failed', err);
        VAULT_DRAWER_MAP = {};
        return false;
    }
}

function vaultLookupApplicantData(applicantId) {
    const key = String(applicantId || '').trim().toLowerCase();
    if (!key) return null;
    if (VAULT_DRAWER_MAP[key]) {
        return VAULT_DRAWER_MAP[key];
    }
    for (const k of Object.keys(VAULT_DRAWER_MAP)) {
        if (k === key || String(k).toLowerCase() === key) {
            return VAULT_DRAWER_MAP[k];
        }
        const a = String(k).replace(/-/g, '');
        const b = key.replace(/-/g, '');
        if (a && a === b) {
            return VAULT_DRAWER_MAP[k];
        }
    }
    return null;
}

function vaultOpenUploadForMissingDoc(docTypeKey) {
    if (!vaultDrawerApplicantId || !docTypeKey) return;
    closeVaultDrawer();
    openUploadModalForApplicant(vaultDrawerApplicantId, vaultDrawerApplicantName, docTypeKey);
}

function vaultOpenScanForMissingDoc(docTypeKey) {
    if (!vaultDrawerApplicantId || !docTypeKey) return;
    closeVaultDrawer();
    openUploadModalForApplicant(vaultDrawerApplicantId, vaultDrawerApplicantName, docTypeKey, 'scan');
}

async function vaultDrawerConfirmReplace(docName) {
    if (typeof showFlowConfirmReplaceDocument === 'function') {
        return showFlowConfirmReplaceDocument(docName || 'Document');
    }
    const label = docName || 'Document';
    return window.confirm('Replace the file already on record?\n\n' + label + '\n\nProceed?');
}

async function vaultDrawerTriggerUpload(buttonEl) {
    if (!buttonEl || !VAULT_DRAWER_CAN_INTAKE_SCAN) {
        const tk = buttonEl && buttonEl.dataset.vaultTypeKey;
        if (tk) vaultOpenUploadForMissingDoc(tk);
        return;
    }
    const docKey = String(buttonEl.dataset.intakeDocKey || '').trim();
    const docCode = String(buttonEl.dataset.intakeDocCode || '').trim();
    if (!docKey || !vaultDrawerApplicantId) return;
    if (String(buttonEl.dataset.hasExistingDoc || '0') === '1') {
        const ok = await vaultDrawerConfirmReplace(buttonEl.dataset.existingDocName || 'Document');
        if (!ok) return;
    }
    vaultDrawerPendingUploadContext = {
        docKey: docKey,
        docCode: docCode,
        triggerBtn: buttonEl,
    };
    const inp = document.getElementById('vaultDrawerFileInput');
    if (!inp) return;
    inp.value = '';
    inp.click();
}

async function vaultDrawerTriggerScan(buttonEl) {
    if (!buttonEl || !VAULT_DRAWER_CAN_INTAKE_SCAN) {
        const tk = buttonEl && buttonEl.dataset.vaultTypeKey;
        if (tk) vaultOpenScanForMissingDoc(tk);
        return;
    }
    const docKey = String(buttonEl.dataset.intakeDocKey || '').trim();
    const docCode = String(buttonEl.dataset.intakeDocCode || '').trim();
    if (!docKey || !vaultDrawerApplicantId) return;
    if (String(buttonEl.dataset.hasExistingDoc || '0') === '1') {
        const ok = await vaultDrawerConfirmReplace(buttonEl.dataset.existingDocName || 'Document');
        if (!ok) return;
    }
    const oldHtml = buttonEl.innerHTML;
    buttonEl.disabled = true;
    buttonEl.textContent = 'Scanning…';
    try {
        const dwt = await vaultMgmtWaitForDwt();
        if (!dwt) throw new Error('Scanner SDK is not ready. Refresh the page and try again.');
        await dwt.SelectSourceAsync();
        const beforeCount = Number(dwt.HowManyImagesInBuffer || 0);
        await dwt.AcquireImageAsync({ IfCloseSourceAfterAcquire: true });
        if (Number(dwt.HowManyImagesInBuffer || 0) <= beforeCount) {
            throw new Error('No image was acquired from the scanner.');
        }
        const index = Number(dwt.CurrentImageIndexInBuffer);
        const uploadUrl = VAULT_MGMT_INTAKE_DWT_URL
            + '?applicant_id=' + encodeURIComponent(vaultDrawerApplicantId)
            + '&doc_key=' + encodeURIComponent(docKey)
            + '&doc_code=' + encodeURIComponent(docCode)
            + '&capture_method=scan';
        const refLabel = (vaultDrawerApplicantName || 'applicant').replace(/\s+/g, '_').slice(0, 80);
        const fileName = refLabel + '_' + (docCode || 'scan') + '.png';
        await new Promise(function (resolve, reject) {
            dwt.HTTPUpload(
                uploadUrl,
                [index],
                Dynamsoft.DWT.EnumDWT_ImageType.IT_PNG,
                Dynamsoft.DWT.EnumDWT_UploadDataFormat.Binary,
                fileName,
                function (httpResponse) { resolve(httpResponse); },
                function (_code, errorString, httpResponse) {
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
                        } catch (_err) {}
                    }
                    reject(new Error(message));
                }
            );
        });
        vaultMgmtNotify('Scan saved to the document vault.', 'Scan complete', 'success');
        location.reload();
    } catch (error) {
        vaultMgmtNotify((error && error.message) ? error.message : 'Unable to complete scan.');
        buttonEl.innerHTML = oldHtml;
    } finally {
        buttonEl.disabled = false;
        if (buttonEl.textContent === 'Scanning…') {
            buttonEl.innerHTML = oldHtml;
        }
    }
}

async function vaultDrawerHandleFileSelected(ev) {
    const input = ev.target;
    const file = input.files && input.files[0];
    const ctx = vaultDrawerPendingUploadContext;
    vaultDrawerPendingUploadContext = null;
    if (!file || !ctx || !vaultDrawerApplicantId) {
        if (input) input.value = '';
        return;
    }
    const formData = new FormData();
    formData.append('applicant_id', vaultDrawerApplicantId);
    formData.append('doc_key', ctx.docKey);
    formData.append('doc_code', String(ctx.docCode || '').toUpperCase());
    formData.append('file', file);
    formData.append('capture_method', 'upload');
    const busyBtn = ctx.triggerBtn;
    const oldHtml = busyBtn ? busyBtn.innerHTML : '';
    if (busyBtn) {
        busyBtn.disabled = true;
        busyBtn.textContent = 'Uploading…';
    }
    try {
        const response = await fetch(VAULT_MGMT_INTAKE_DWT_URL, {
            method: 'POST',
            body: formData,
            credentials: 'same-origin',
        });
        const ct = (response.headers.get('content-type') || '').toLowerCase();
        const data = ct.includes('application/json') ? await response.json() : null;
        if (!data || !data.success) {
            throw new Error((data && data.error) ? data.error : 'Upload failed.');
        }
        vaultMgmtNotify('File saved to the document vault.', 'Upload complete', 'success');
        location.reload();
    } catch (err) {
        vaultMgmtNotify(err.message || 'Upload failed.');
        if (busyBtn) {
            busyBtn.disabled = false;
            busyBtn.innerHTML = oldHtml || 'Upload';
        }
    } finally {
        if (input) input.value = '';
    }
}

function vaultBuildServicesMenu(actionsEl, item, overrideGalleryUrls, overrideGalleryTitle) {
    if (!actionsEl) return;

    const typeKey     = item ? item.type_key : null;
    const hideActions = item ? item.hide_add_file : true;
    const docKey      = item ? item.intake_doc_key : null;
    const docCode     = item ? item.intake_doc_code : null;
    const onFile      = item ? !!item.on_file : false;
    const viewUrl     = item ? item.view_url : null;
    const viewUrls    = overrideGalleryUrls || (item ? item.view_urls : null);
    const galleryTitle = overrideGalleryTitle || (item ? item.label : null);
    const canInline   = VAULT_DRAWER_CAN_INTAKE_SCAN && docKey && docCode && !hideActions;

    // Determine which actions are available
    const hasView    = (onFile && viewUrl) || (viewUrls && viewUrls.length);
    const hasUpload  = !hideActions && (canInline ? true : !!typeKey);
    const hasScan    = !hideActions && (canInline ? true : !!typeKey);
    const hasReplace = onFile && hasUpload;

    if (!hasView && !hasUpload && !hasScan) return;

    // --- Services ▼ button ---
    const wrap = document.createElement('div');
    wrap.className = 'vault-svc-wrap';
    wrap.style.position = 'relative';
    wrap.style.display  = 'inline-block';

    const trigger = document.createElement('button');
    trigger.type      = 'button';
    trigger.className = 'vault-svc-btn';
    trigger.innerHTML = 'Services <span style="font-size:0.65rem;">&#9660;</span>';
    trigger.setAttribute('aria-haspopup', 'true');
    trigger.setAttribute('aria-expanded', 'false');
    trigger.addEventListener('click', function (e) {
        e.stopPropagation();
        closeAllVaultSvcMenus();
        const m = wrap._vaultSvcMenu;
        if (m) {
            // Use fixed positioning to escape overflow:hidden/auto scroll containers
            const rect = trigger.getBoundingClientRect();
            m.style.position = 'fixed';
            m.style.top  = (rect.bottom + 4) + 'px';
            m.style.right = (window.innerWidth - rect.right) + 'px';
            m.style.left  = 'auto';
            m.style.display = 'block';
            trigger.setAttribute('aria-expanded', 'true');
        }
    });
    wrap.appendChild(trigger);

    // --- Dropdown menu (appended to body so it escapes overflow clips) ---
    const menu = document.createElement('div');
    menu.className    = 'vault-svc-menu';
    menu.style.display = 'none';

    function addItem(icon, label, onClick) {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'vault-svc-item';
        btn.innerHTML = icon + label;
        btn.addEventListener('click', function (e) {
            e.stopPropagation();
            closeAllVaultSvcMenus();
            onClick();
        });
        menu.appendChild(btn);
    }

    const eyeSvg   = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>';
    const upSvg    = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>';
    const scanSvg  = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 7V5a2 2 0 0 1 2-2h2"/><path d="M17 3h2a2 2 0 0 1 2 2v2"/><path d="M21 17v2a2 2 0 0 1-2 2h-2"/><path d="M7 21H5a2 2 0 0 1-2-2v-2"/><line x1="3" y1="12" x2="21" y2="12"/></svg>';
    const repSvg   = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>';

    if (hasView) {
        addItem(eyeSvg, '\u00a0View', function () {
            if (viewUrls && viewUrls.length) {
                openVaultImageGallery(viewUrls, galleryTitle || 'Photos');
            } else if (viewUrl) {
                window.open(viewUrl, '_blank', 'noopener');
            }
        });
    }

    if (hasUpload) {
        // Build a fake button element so we can reuse vaultDrawerTriggerUpload
        const fakeBtn = document.createElement('button');
        fakeBtn.dataset.vaultTypeKey    = typeKey || '';
        fakeBtn.dataset.intakeDocKey    = docKey || '';
        fakeBtn.dataset.intakeDocCode   = docCode || '';
        fakeBtn.dataset.hasExistingDoc  = onFile ? '1' : '0';
        fakeBtn.dataset.existingDocName = (item && item.label) || 'Document';
        addItem(upSvg, '\u00a0Upload', function () {
            if (canInline) {
                vaultDrawerTriggerUpload(fakeBtn);
            } else if (typeKey) {
                vaultOpenUploadForMissingDoc(typeKey);
            }
        });
    }

    if (hasScan) {
        const fakeScanBtn = document.createElement('button');
        fakeScanBtn.dataset.vaultTypeKey    = typeKey || '';
        fakeScanBtn.dataset.intakeDocKey    = docKey || '';
        fakeScanBtn.dataset.intakeDocCode   = docCode || '';
        fakeScanBtn.dataset.hasExistingDoc  = onFile ? '1' : '0';
        fakeScanBtn.dataset.existingDocName = (item && item.label) || 'Document';
        addItem(scanSvg, '\u00a0Scan', function () {
            if (canInline) {
                vaultDrawerTriggerScan(fakeScanBtn);
            } else if (typeKey) {
                vaultOpenScanForMissingDoc(typeKey);
            }
        });
    }

    if (hasReplace) {
        const fakeRepBtn = document.createElement('button');
        fakeRepBtn.dataset.vaultTypeKey    = typeKey || '';
        fakeRepBtn.dataset.intakeDocKey    = docKey || '';
        fakeRepBtn.dataset.intakeDocCode   = docCode || '';
        fakeRepBtn.dataset.hasExistingDoc  = '1';
        fakeRepBtn.dataset.existingDocName = (item && item.label) || 'Document';
        const repItem = document.createElement('button');
        repItem.type = 'button';
        repItem.className = 'vault-svc-item vault-svc-item--replace';
        repItem.innerHTML = repSvg + '\u00a0Replace';
        repItem.addEventListener('click', function (e) {
            e.stopPropagation();
            closeAllVaultSvcMenus();
            if (canInline) {
                vaultDrawerTriggerUpload(fakeRepBtn);
            } else if (typeKey) {
                vaultOpenUploadForMissingDoc(typeKey);
            }
        });
        menu.appendChild(repItem);
    }

    // Append menu to body so it escapes vault-drawer-scroll overflow:auto
    document.body.appendChild(menu);
    // Store reference for the click-outside closer
    wrap._vaultSvcMenu = menu;
    actionsEl.appendChild(wrap);
}

function vaultAppendDrawerDocActions(actionsEl, item) {
    if (!actionsEl || !item || item.is_monitoring_report) return;
    vaultBuildServicesMenu(actionsEl, item);
}

function vaultAppendViewButton(actionsEl, viewUrl, label) {
    if (!actionsEl || !viewUrl) return;
    // Wrap a simple view-only item in the Services menu
    vaultBuildServicesMenu(actionsEl, {
        on_file: true,
        view_url: viewUrl,
        label: label || 'View',
        hide_add_file: true,
        intake_doc_key: null,
        intake_doc_code: null,
        type_key: null,
    });
}

function closeAllVaultSvcMenus() {
    document.querySelectorAll('.vault-svc-menu').forEach(function (m) { m.style.display = 'none'; });
    document.querySelectorAll('.vault-svc-btn').forEach(function (b) { b.setAttribute('aria-expanded', 'false'); });
}

var vaultImageGalleryUrls = [];
var vaultImageGalleryIndex = 0;

function vaultImageGalleryRefresh() {
    var urls = vaultImageGalleryUrls;
    var idx = vaultImageGalleryIndex;
    var img = document.getElementById('vaultImageGalleryImg');
    var prev = document.getElementById('vaultImageGalleryPrev');
    var next = document.getElementById('vaultImageGalleryNext');
    var counter = document.getElementById('vaultImageGalleryCounter');
    if (!img || !urls.length) return;
    img.src = urls[idx] || '';
    img.alt = 'Photo ' + String(idx + 1) + ' of ' + String(urls.length);
    if (counter) {
        counter.textContent = urls.length > 1 ? String(idx + 1) + ' / ' + String(urls.length) : '';
    }
    if (prev) {
        prev.hidden = urls.length <= 1;
    }
    if (next) {
        next.hidden = urls.length <= 1;
    }
}

function vaultImageGalleryStep(delta) {
    var n = vaultImageGalleryUrls.length;
    if (n <= 1) return;
    vaultImageGalleryIndex = (vaultImageGalleryIndex + delta + n) % n;
    vaultImageGalleryRefresh();
}

function vaultImageGalleryOnKeydown(e) {
    if (e.key === 'Escape') {
        closeVaultImageGallery();
        return;
    }
    if (vaultImageGalleryUrls.length <= 1) return;
    if (e.key === 'ArrowLeft') {
        e.preventDefault();
        vaultImageGalleryStep(-1);
    }
    if (e.key === 'ArrowRight') {
        e.preventDefault();
        vaultImageGalleryStep(1);
    }
}

function openVaultImageGallery(urls, title) {
    if (!urls || !urls.length) return;
    var modal = document.getElementById('vaultImageGalleryModal');
    var titleEl = document.getElementById('vaultImageGalleryTitle');
    if (!modal) return;
    vaultImageGalleryUrls = urls.slice();
    vaultImageGalleryIndex = 0;
    if (titleEl && title) {
        titleEl.textContent = title;
    }
    vaultImageGalleryRefresh();
    modal.classList.add('is-open');
    modal.style.display = 'flex';
    document.addEventListener('keydown', vaultImageGalleryOnKeydown);
}

function closeVaultImageGallery() {
    var modal = document.getElementById('vaultImageGalleryModal');
    var img = document.getElementById('vaultImageGalleryImg');
    if (modal) {
        modal.classList.remove('is-open');
        modal.style.display = 'none';
    }
    if (img) {
        img.src = '';
    }
    vaultImageGalleryUrls = [];
    document.removeEventListener('keydown', vaultImageGalleryOnKeydown);
}

function vaultAppendGalleryViewButton(actionsEl, urls, title) {
    if (!actionsEl || !urls || !urls.length) return;
    vaultBuildServicesMenu(actionsEl, {
        on_file: true,
        view_url: null,
        label: title || 'Photos',
        hide_add_file: true,
        intake_doc_key: null,
        intake_doc_code: null,
        type_key: null,
    }, urls, title);
}

function setMonitoringReportText(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value || '—';
}

function openMonitoringReportDocument(report) {
    if (!report) return;
    setMonitoringReportText('monitoringReportDocumentTitle', report.title || 'Monitoring report');
    setMonitoringReportText('monitoringReportDocumentSubtitle', 'Post-award field verification document');
    setMonitoringReportText('monitoringReportDocUnit', report.unit);
    setMonitoringReportText('monitoringReportDocDay', report.monitoring_day ? ('Day ' + report.monitoring_day) : '—');
    setMonitoringReportText('monitoringReportDocDue', report.due_date);
    setMonitoringReportText('monitoringReportDocSubmitted', report.submitted_at + ' by ' + (report.submitted_by || '—'));
    setMonitoringReportText(
        'monitoringReportDocConstruction',
        (report.construction_status || '—') + (report.percent_complete ? ' (' + report.percent_complete + ')' : '')
    );
    setMonitoringReportText(
        'monitoringReportDocAssessment',
        report.assessment + (report.assessed_by && report.assessed_by !== '—' ? ' by ' + report.assessed_by : '')
    );
    setMonitoringReportText('monitoringReportDocOccupancy', report.occupancy_notes);
    setMonitoringReportText('monitoringReportDocProgress', report.progress_notes);
    setMonitoringReportText('monitoringReportDocRemarks', report.general_remarks);

    const photosBtn = document.getElementById('monitoringReportDocPhotosBtn');
    const photos = report.photo_urls || [];
    if (photosBtn) {
        if (photos.length) {
            photosBtn.style.display = 'inline-flex';
            photosBtn.onclick = function () {
                openVaultImageGallery(photos, report.title || 'Monitoring report photos');
            };
        } else {
            photosBtn.style.display = 'none';
            photosBtn.onclick = null;
        }
    }

    const modal = document.getElementById('monitoringReportDocumentModal');
    if (modal) {
        modal.style.display = 'flex';
        document.body.style.overflow = 'hidden';
    }
}

function closeMonitoringReportDocument() {
    const modal = document.getElementById('monitoringReportDocumentModal');
    if (modal) modal.style.display = 'none';
    document.body.style.overflow = '';
}

function openVaultDrawer(applicantId) {
    if (!Object.keys(VAULT_DRAWER_MAP).length) {
        loadVaultDrawerMapFromDom();
    }
    const id = String(applicantId || '').trim().toLowerCase();
    let data = vaultLookupApplicantData(id);
    if (!data) {
        loadVaultDrawerMapFromDom();
        data = vaultLookupApplicantData(id);
    }
    if (!data) {
        if (typeof window.showFlowAlert === 'function') {
            window.showFlowAlert(
                'Could not load this applicant’s vault checklist. Refresh the page, or use “Upload Document” in the header to add files.',
                'Documents',
                null,
                'default'
            );
        } else {
            alert('Vault data not available for this applicant.');
        }
        return;
    }
    vaultDrawerApplicantId = id;
    vaultDrawerApplicantName = data.full_name || '';
    const titleEl = document.getElementById('vaultDrawerTitle');
    if (titleEl) {
        titleEl.textContent = 'Document Checklist';
    }
    const meta = document.getElementById('vaultDrawerMeta');
    if (meta) {
        const sit = data.situation;
        const fullName = data.full_name || '';
        const initials = fullName.slice(0, 2).toUpperCase();
        
        let displayTx = data.id || '';
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

        let metaHtml =
            '<div class="applicant-folder-card-wrapper" style="position: relative;">' +
                '<section class="applicant-folder-card" style="position: relative; cursor: pointer; background: #f0fdfa; border: 1px solid #ccfbf1; border-radius: 0.75rem; padding: 0.85rem 1rem; display: flex; align-items: center; gap: 0.85rem; margin-bottom: 0.75rem;">' +
                    '<div style="width: 2.5rem; height: 2.5rem; border-radius: 50%; background: linear-gradient(135deg, #99f6e4 0%, #0d9488 100%); display: flex; align-items: center; justify-content: center; color: white; box-shadow: 0 4px 10px rgba(13, 148, 136, 0.2); flex-shrink: 0;">' +
                        '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.5">' +
                            '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>' +
                            '<polyline points="14 2 14 8 20 8"/>' +
                        '</svg>' +
                    '</div>' +
                    '<div style="min-width: 0; flex: 1; text-align: left;">' +
                        '<div style="font-size: 0.62rem; text-transform: uppercase; color: #0f766e; font-weight: 700; letter-spacing: 0.05em; margin-bottom: 0.15rem;">Applicant Folder</div>' +
                        '<div style="color: #115e59; font-size: 1.05rem; font-weight: 800; line-height: 1.2; overflow-wrap: anywhere;">' + vaultDrawerEscapeHtml(fullName) + '</div>' +
                        '<div style="font-size: 0.72rem; color: #0d9488; font-weight: 600; margin-top: 0.2rem; font-family: monospace; letter-spacing: 0.02em;">Ref: ' + vaultDrawerEscapeHtml(data.reference_number || '—') + '</div>' +
                    '</div>' +
                    '<div class="folder-hover-trigger" style="margin-left: auto; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 0.1rem; background: #ccfbf1; color: #0f766e; border-radius: 0.5rem; padding: 0.35rem 0.5rem;">' +
                        '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5">' +
                            '<circle cx="12" cy="12" r="10"/>' +
                            '<line x1="12" y1="16" x2="12" y2="12"/>' +
                            '<line x1="12" y1="8" x2="12.01" y2="8"/>' +
                        '</svg>' +
                        '<span style="font-size: 0.52rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.03em;">Details</span>' +
                    '</div>' +
                '</section>' +
                
                // Floating Popover Hover Card
                '<div class="applicant-folder-hover-card">' +
                    '<div class="applicant-folder-hover-card-arrow"></div>' +
                    '<div class="hover-card-banner" style="margin: -0.85rem -0.85rem 0.75rem -0.85rem; border-top-left-radius: 12px; border-top-right-radius: 12px; overflow: hidden; background: #ffffff; padding: 0.6rem 0.85rem; border-bottom: 1px solid #cbd5e1; display: flex; justify-content: center; align-items: center;">' +
                        '<img src="/static/images/tha_logo.png" alt="Talisay City Housing Authority Logo" style="width: 100%; max-width: 240px; height: auto; display: block; border-radius: 6px; border: 1px solid #cbd5e1; padding: 0.2rem; background: #ffffff; box-sizing: border-box;">' +
                    '</div>' +
                    '<div class="hover-card-header" style="margin-bottom: 0.5rem; padding-bottom: 0.5rem; border-bottom: 1px solid #f1f5f9; display: flex; align-items: center; gap: 0.65rem;">' +
                        '<div class="hover-card-avatar" style="width: 36px; height: 36px; border-radius: 8px; background: linear-gradient(135deg, #0d9488 0%, #14b8a6 100%); color: #ffffff; display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 0.95rem; flex-shrink: 0;">' + initials + '</div>' +
                        '<div class="hover-card-title-group" style="min-width: 0; flex: 1;">' +
                            '<div class="hover-card-name" style="font-size: 0.9rem; font-weight: 800; color: #1e293b; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="' + vaultDrawerEscapeHtml(fullName) + '">' + vaultDrawerEscapeHtml(fullName) + '</div>' +
                            '<div class="hover-card-tag" style="font-size: 0.58rem; font-weight: 700; text-transform: uppercase; color: #0d9488; letter-spacing: 0.05em; display: inline-block;">Applicant Profile</div>' +
                        '</div>' +
                    '</div>' +
                    '<div class="hover-card-body" style="display: flex; flex-direction: column; gap: 0.45rem;">' +
                        '<div class="hover-card-meta-row" style="display: flex; justify-content: space-between; align-items: center; font-size: 0.72rem; line-height: 1.2;">' +
                            '<span class="hover-card-label" style="color: #64748b; font-weight: 600;">Transaction ID</span>' +
                            '<span class="case-number-badge" style="font-family: monospace; font-size: 0.68rem; padding: 0.15rem 0.35rem; border-radius: 0.25rem; font-weight: 700; color: #2563eb; background: #eff6ff; border: 1px solid #dbeafe;">' + vaultDrawerEscapeHtml(displayTx || '—') + '</span>' +
                        '</div>' +
                        '<div class="hover-card-meta-row" style="display: flex; justify-content: space-between; align-items: center; font-size: 0.72rem; line-height: 1.2;">' +
                            '<span class="hover-card-label" style="color: #64748b; font-weight: 600;">Reference Code</span>' +
                            '<span class="complainant-ref-code" style="font-family: monospace; font-size: 0.68rem; padding: 0.15rem 0.35rem; border-radius: 0.25rem; font-weight: 700; color: #475569; background: #f1f5f9; border: 1px solid #e2e8f0;">' + vaultDrawerEscapeHtml(data.reference_number || '—') + '</span>' +
                        '</div>' +
                        '<div class="hover-card-meta-row" style="display: flex; justify-content: space-between; align-items: center; font-size: 0.72rem; line-height: 1.2;">' +
                            '<span class="hover-card-label" style="color: #64748b; font-weight: 600;">' + (String(data.hover_location || data.barangay || '').startsWith('Block ') ? 'Block &amp; lot' : 'Barangay') + '</span>' +
                            '<span class="hover-card-value" style="font-weight: 700; color: #1e293b;">' + vaultDrawerEscapeHtml(data.hover_location || data.barangay || '—') + '</span>' +
                        '</div>' +
                        '<div class="hover-card-meta-row" style="display: flex; justify-content: space-between; align-items: center; font-size: 0.72rem; line-height: 1.2;">' +
                            '<span class="hover-card-label" style="color: #64748b; font-weight: 600;">Application Stage</span>' +
                            '<span class="hover-card-value" style="font-weight: 700; color: #1e293b;">' + vaultDrawerEscapeHtml(data.status_display || '—') + '</span>' +
                        '</div>';

        if (data.applicant_workflow_status) {
            metaHtml +=
                '<div style="background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 0.5rem; padding: 0.55rem 0.7rem; display: flex; flex-direction: column; gap: 0.15rem; text-align: left; margin-top: 0.25rem;">' +
                    '<div style="font-size: 0.55rem; text-transform: uppercase; color: #166534; font-weight: 700; letter-spacing: 0.05em; display: flex; align-items: center; gap: 0.25rem;">' +
                        '<svg viewBox="0 0 24 24" width="9" height="9" fill="none" stroke="currentColor" stroke-width="2.5" style="flex-shrink:0;">' +
                            '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>' +
                            '<polyline points="22 4 12 14.01 9 11.01"/>' +
                        '</svg>' +
                        'Applicant Status' +
                    '</div>' +
                    '<div style="font-size: 0.72rem; font-weight: 700; color: #14532d; line-height: 1.3;">' + vaultDrawerEscapeHtml(data.applicant_workflow_status) + '</div>';
            if (data.applicant_status_detail) {
                metaHtml +=
                    '<div style="font-size: 0.68rem; font-weight: 600; color: #15803d; border-top: 1px dashed #bbf7d0; padding-top: 0.25rem; margin-top: 0.1rem; display: flex; align-items: center; gap: 0.2rem;">' +
                        '<svg viewBox="0 0 24 24" width="9" height="9" fill="none" stroke="currentColor" stroke-width="2.5" style="flex-shrink:0;">' +
                            '<circle cx="12" cy="12" r="10"/>' +
                            '<line x1="12" y1="8" x2="12" y2="12"/>' +
                            '<line x1="12" y1="16" x2="12.01" y2="16"/>' +
                        '</svg>' +
                        vaultDrawerEscapeHtml(data.applicant_status_detail) +
                    '</div>';
            }
            metaHtml += '</div>';
        }

        if (data.why_disqualified) {
            metaHtml +=
                '<div style="background: #fef2f2; border: 1px solid #fecaca; border-radius: 0.5rem; padding: 0.55rem 0.7rem; display: flex; flex-direction: column; gap: 0.15rem; text-align: left; margin-top: 0.25rem;">' +
                    '<div style="font-size: 0.55rem; text-transform: uppercase; color: #991b1b; font-weight: 700; letter-spacing: 0.05em; display: flex; align-items: center; gap: 0.25rem;">' +
                        '<svg viewBox="0 0 24 24" width="9" height="9" fill="none" stroke="currentColor" stroke-width="2.5" style="flex-shrink:0;">' +
                            '<circle cx="12" cy="12" r="10"/>' +
                            '<line x1="12" y1="8" x2="12" y2="12"/>' +
                            '<line x1="12" y1="16" x2="12.01" y2="16"/>' +
                        '</svg>' +
                        'Disqualification Notes' +
                    '</div>' +
                    '<div style="font-size: 0.7rem; font-weight: 500; color: #7f1d1d; line-height: 1.35;">' + vaultDrawerEscapeHtml(data.why_disqualified) + '</div>' +
                '</div>';
        }

        if (sit && sit.title) {
            metaHtml +=
                '<div style="background: #fffbeb; border: 1px solid #fde68a; border-radius: 0.5rem; padding: 0.55rem 0.7rem; display: flex; flex-direction: column; gap: 0.15rem; text-align: left; margin-top: 0.25rem;">' +
                    '<div style="font-size: 0.55rem; text-transform: uppercase; color: #b45309; font-weight: 700; letter-spacing: 0.05em; display: flex; align-items: center; gap: 0.25rem;">' +
                        '<svg viewBox="0 0 24 24" width="9" height="9" fill="none" stroke="currentColor" stroke-width="2.5" style="flex-shrink:0;">' +
                            '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>' +
                        '</svg>' +
                        'Applicant Situation' +
                    '</div>' +
                    '<div style="font-size: 0.72rem; font-weight: 700; color: #78350f; line-height: 1.3;">' + vaultDrawerEscapeHtml(sit.title) + '</div>';
            if (sit.blurb) {
                metaHtml += '<p style="margin: 0.15rem 0 0; font-size: 0.68rem; color: #92400e; line-height: 1.35; font-weight: 500;">' + vaultDrawerEscapeHtml(sit.blurb) + '</p>';
            }
            if (sit.detail_line) {
                metaHtml += '<div style="margin-top: 0.35rem; padding-top: 0.35rem; border-top: 1px dashed #fde68a; font-size: 0.68rem; color: #78350f; line-height: 1.35; word-break: break-all; overflow-wrap: anywhere;">' +
                    '<strong>Details</strong> — ' + vaultDrawerEscapeHtml(sit.detail_line) + '</div>';
            }
            metaHtml += '</div>';
        }

        metaHtml +=
                    '</div>' +
                    '<div style="text-align: center; border-top: 1px solid #f1f5f9; margin: 0.75rem -0.85rem -0.85rem -0.85rem; padding: 0.5rem; font-size: 0.62rem; color: #64748b; font-weight: 600; border-bottom-left-radius: 12px; border-bottom-right-radius: 12px; background: #f8fafc;">' +
                        'Talisay City Housing Authority' +
                    '</div>' +
                '</div>' +
            '</div>';
        meta.innerHTML = metaHtml;
    }
    const listEl = document.getElementById('vaultDrawerChecklist');
    if (listEl) {
        listEl.innerHTML = '';
        const cardContainer = document.createElement('div');
        cardContainer.className = 'vault-drawer-card-container';
        listEl.appendChild(cardContainer);

        (data.vault_checklist || []).forEach(function (item) {
            const row = document.createElement('div');
            row.className = 'vault-drawer-row';
            const labelSpan = document.createElement('span');
            labelSpan.className = 'vault-drawer-label';
            labelSpan.textContent = item.label || '';

            const actions = document.createElement('div');
            actions.className = 'vault-drawer-row-actions';

            const badge = document.createElement('span');
            const bv = item.badge_variant;
            let badgeKind = item.on_file ? 'ok' : 'missing';
            if (bv === 'pending') {
                badgeKind = 'pending';
            } else if (bv === 'waiting') {
                badgeKind = 'waiting';
            }
            const badgeClassByKind = {
                ok: 'vault-badge vault-badge--ok',
                missing: 'vault-badge vault-badge--missing',
                pending: 'vault-badge vault-badge--pending',
                waiting: 'vault-badge vault-badge--waiting',
            };
            badge.className = badgeClassByKind[badgeKind] || badgeClassByKind.missing;
            badge.textContent =
                item.badge_text != null && String(item.badge_text).length
                    ? item.badge_text
                    : item.on_file
                      ? 'On file'
                      : 'Missing';
            actions.appendChild(badge);

            if (item.is_monitoring_report && item.report) {
                const reportBtn = document.createElement('button');
                reportBtn.type = 'button';
                reportBtn.className = 'vault-view-btn';
                reportBtn.textContent = 'View report';
                reportBtn.addEventListener('click', function () {
                    openMonitoringReportDocument(item.report);
                });
                actions.appendChild(reportBtn);
            } else {
                vaultAppendDrawerDocActions(actions, item);
            }

            row.appendChild(labelSpan);
            row.appendChild(actions);
            cardContainer.appendChild(row);
        });

        const sit2 = data.situation;
        if (sit2) {
            if (sit2.option_d_message) {
                const dmsg = document.createElement('p');
                dmsg.className = 'vault-option-d-only';
                dmsg.textContent = sit2.option_d_message;
                listEl.appendChild(dmsg);
            } else if (sit2.rows && sit2.rows.length) {
                sit2.rows.forEach(function (sr) {
                    const srow = document.createElement('div');
                    srow.className = 'vault-drawer-row';
                    const lab = document.createElement('div');
                    lab.style.flex = '1';
                    lab.style.minWidth = '0';
                    const main = document.createElement('span');
                    main.className = 'vault-drawer-label';
                    main.style.display = 'block';
                    main.appendChild(document.createTextNode(sr.label || ''));
                    const kind = (sr.kind === 'image') ? 'Image' : 'Document';
                    const kindSp = document.createElement('span');
                    kindSp.className = 'vault-row-kind';
                    kindSp.textContent = ' ' + kind;
                    main.appendChild(kindSp);
                    lab.appendChild(main);
                    if (sr.note) {
                        const nt = document.createElement('span');
                        nt.className = 'vault-row-note';
                        nt.textContent = sr.note;
                        lab.appendChild(nt);
                    }
                    const sact = document.createElement('div');
                    sact.className = 'vault-drawer-row-actions';
                    const sb = document.createElement('span');
                    sb.className = sr.on_file ? 'vault-badge vault-badge--ok' : 'vault-badge vault-badge--missing';
                    sb.textContent = sr.on_file ? 'On file' : 'Missing';
                    sact.appendChild(sb);
                    vaultAppendDrawerDocActions(sact, {
                        type_key: sr.type_key,
                        label: sr.label,
                        on_file: sr.on_file,
                        view_url: sr.view_url,
                        view_urls: sr.view_urls,
                        hide_add_file: !sr.add_file,
                        intake_doc_key: sr.intake_doc_key,
                        intake_doc_code: sr.intake_doc_code,
                    });
                    srow.appendChild(lab);
                    srow.appendChild(sact);
                    cardContainer.appendChild(srow);
                });
            }
        }
    }
    const backdrop = document.getElementById('vaultDrawer');
    if (backdrop) {
        backdrop.classList.add('is-open');
        backdrop.style.display = 'flex';
        document.body.style.overflow = 'hidden';
    }
}

function closeVaultDrawer() {
    const backdrop = document.getElementById('vaultDrawer');
    if (backdrop) {
        backdrop.classList.remove('is-open');
        backdrop.style.display = 'none';
    }
    // Remove all body-level Services menus created by vaultBuildServicesMenu
    closeAllVaultSvcMenus();
    document.querySelectorAll('.vault-svc-menu').forEach(function(m) {
        if (m.parentNode === document.body) {
            document.body.removeChild(m);
        }
    });
    document.body.style.overflow = '';
    const params = new URLSearchParams(window.location.search);
    if (params.get('open_vault') === '1') {
        clearDocumentsVaultDeepLinkParams();
        const searchInput = document.getElementById('searchInput');
        if (searchInput) {
            searchInput.value = '';
        }
        applyDocumentsManagementSearch('');
    }
}

function openUploadModal() {
    document.getElementById('uploadModal').style.display = 'flex';
}

function openUploadModalForApplicant(applicantId, applicantName, docTypeKey, intent) {
    // Pre-select the applicant (and optional document type), then open the modal.
    const applicantSelect = document.querySelector('#applicantSelect, select[name="applicant"]');
    if (applicantSelect) {
        const want = String(applicantId || '').trim().toLowerCase();
        let matched = false;
        for (let i = 0; i < applicantSelect.options.length; i++) {
            const v = String(applicantSelect.options[i].value || '').trim().toLowerCase();
            if (v === want) {
                applicantSelect.selectedIndex = i;
                matched = true;
                break;
            }
        }
        if (!matched) {
            applicantSelect.value = applicantId;
        }
        applicantSelect.dispatchEvent(new Event('change', { bubbles: true }));
    }
    const docSelect = document.getElementById('uploadDocumentTypeSelect');
    if (docSelect) {
        if (docTypeKey) {
            docSelect.value = docTypeKey;
        }
        docSelect.dispatchEvent(new Event('change', { bubbles: true }));
    }
    const searchInput = document.querySelector('#applicantSearch, input[placeholder*="Search applicant"]');
    if (searchInput && applicantName) {
        searchInput.value = applicantName;
    }
    openUploadModal();
    if (intent === 'scan' || intent === 'upload') {
        const titleEl = document.getElementById('uploadModalTitle');
        const hintEl = document.getElementById('uploadModalIntentHint');
        const dwtStrip = document.getElementById('uploadModalDwtStrip');
        const fileInput = document.getElementById('fileInput');
        if (titleEl && hintEl) {
            if (intent === 'scan') {
                titleEl.textContent = '📷 Scan document';
                hintEl.textContent = 'Use Dynamsoft (TWAIN) for scanner capture — same as checklist Scan. Or pick a file below.';
                hintEl.style.display = 'block';
                if (dwtStrip) dwtStrip.style.display = 'flex';
                if (fileInput) fileInput.removeAttribute('required');
            } else {
                titleEl.textContent = '📁 Upload document';
                hintEl.textContent = 'Choose a file from this computer.';
                hintEl.style.display = 'block';
                if (dwtStrip) dwtStrip.style.display = 'none';
                if (fileInput) fileInput.setAttribute('required', 'required');
            }
        }
    }
}

function closeUploadModal(e) {
    if (e && e.target.id !== 'uploadModal') return;
    document.getElementById('uploadModal').style.display = 'none';
    document.getElementById('uploadForm').reset();
    document.getElementById('fileName').textContent = '';
    const dwtStrip = document.getElementById('uploadModalDwtStrip');
    if (dwtStrip) dwtStrip.style.display = 'none';
    const fileInput = document.getElementById('fileInput');
    if (fileInput) fileInput.setAttribute('required', 'required');
    const titleEl = document.getElementById('uploadModalTitle');
    const hintEl = document.getElementById('uploadModalIntentHint');
    if (titleEl) {
        titleEl.textContent = '📁 Upload Document';
        titleEl.style.background = 'linear-gradient(135deg, #1e40af 0%, #1e3a8a 100%)';
        titleEl.style.webkitBackgroundClip = 'text';
        titleEl.style.backgroundClip = 'text';
        titleEl.style.webkitTextFillColor = 'transparent';
    }
    if (hintEl) {
        hintEl.style.display = 'none';
        hintEl.textContent = '';
    }
}

function submitUpload() {
    const form = document.getElementById('uploadForm');
    if (!form.checkValidity()) {
        showFlowAlert('Please fill in all required fields');
        return;
    }

    const formData = new FormData(form);
    formData.append('applicant_id', formData.get('applicant') || '');
    formData.append('doc_type', formData.get('document_type') || '');
    const position = window.MANAGEMENT_CONFIG.userPosition;
    fetch(`/documents/${position}/api/upload/`, {
        method: 'POST',
        body: formData,
        headers: {'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value}
    })
    .then(r => r.json())
    .then(d => {
        if (d.success) {
            showFlowAlert('Document uploaded', 'Success', null, 'success');
            closeUploadModal();
            location.reload();
        } else {
            showFlowAlert('Error: ' + (d.error || 'Upload failed'));
        }
    })
    .catch(e => showFlowAlert('Error: ' + e));
}

function deleteDocument(docId) {
    if (!confirm('Delete this document?')) return;

    const position = window.MANAGEMENT_CONFIG.userPosition;
    fetch(`/documents/${position}/${docId}/delete/`, {
        method: 'POST',
        headers: {'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value}
    })
    .then(r => r.json())
    .then(d => {
        if (d.success) {
            showFlowAlert('Document deleted', 'Success', null, 'success');
            location.reload();
        } else {
            showFlowAlert('Error: ' + (d.error || 'Delete failed'));
        }
    });
}

// File input change
document.getElementById('fileInput')?.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (file) {
        document.getElementById('fileName').textContent = `📎 ${file.name} (${(file.size / 1024 / 1024).toFixed(2)} MB)`;
    }
});

function applyDocumentsManagementSearch(query) {
    const q = String(query || '').trim().toLowerCase();
    document.querySelectorAll('.doc-item').forEach(item => {
        const hay = (item.getAttribute('data-search') || item.textContent || '').toLowerCase();
        item.style.display = !q || hay.includes(q) ? 'flex' : 'none';
    });
}

function submitDocumentsManagementSearch() {
    const form = document.getElementById('documentsSearchForm');
    if (!form) return;
    const input = document.getElementById('searchInput');
    if (input && input.name !== 'search') {
        input.setAttribute('name', 'search');
    }
    form.submit();
}

function clearDocumentsVaultDeepLinkParams() {
    try {
        const u = new URL(window.location.href);
        let changed = false;
        ['open_vault', 'applicant_id', 'document_type', 'search'].forEach(function (key) {
            if (u.searchParams.has(key)) {
                u.searchParams.delete(key);
                changed = true;
            }
        });
        if (changed) {
            window.history.replaceState({}, '', u.pathname + (u.search || ''));
        }
    } catch (_e) {}
}

// Search: server-side across all applicants (pagination preserved via GET ?search=)
document.getElementById('documentsSearchForm')?.addEventListener('submit', function () {
    const pageInput = this.querySelector('input[name="page"]');
    if (pageInput) pageInput.remove();
});

document.getElementById('searchInput')?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
        e.preventDefault();
        submitDocumentsManagementSearch();
    }
});

// KPI Card Filtering for Applicants and Blacklisted
let currentKpiFilter = null; // Track which filter is active: 'applicants', 'blacklisted', or null

function applyKpiFilter(filterType) {
    const rows = document.querySelectorAll('.applicant-row');
    let visibleCount = 0;

    rows.forEach(row => {
        let shouldShow = true;

        if (filterType === 'blacklisted') {
            shouldShow = row.getAttribute('data-is-blacklisted') === 'true';
        } else if (filterType === 'applicants') {
            shouldShow = row.getAttribute('data-is-blacklisted') === 'false';
        }

        row.style.display = shouldShow ? '' : 'none';
        if (shouldShow) visibleCount++;
    });

    // Update card active states
    const applicantsCard = document.getElementById('kpiApplicants');
    const blacklistedCard = document.getElementById('kpiBlacklisted');

    if (applicantsCard) {
        applicantsCard.classList.toggle('is-active', filterType === 'applicants');
    }
    if (blacklistedCard) {
        blacklistedCard.classList.toggle('is-active', filterType === 'blacklisted');
    }

    // Store current filter state
    if (filterType) {
        currentKpiFilter = filterType;
    }

    return visibleCount;
}

function updateUrlWithFilter(filterType) {
    const url = new URL(window.location.href);
    if (filterType) {
        url.searchParams.set('kpi_filter', filterType);
    } else {
        url.searchParams.delete('kpi_filter');
    }
    window.history.replaceState({}, '', url.toString());
}

// Attach click handlers to KPI cards
document.getElementById('kpiApplicants')?.addEventListener('click', function () {
    const url = new URL(window.location.href);
    if (url.searchParams.get('kpi_filter') === 'applicants') {
        // Toggle off - remove filter
        url.searchParams.delete('kpi_filter');
        url.searchParams.set('page', '1');
    } else {
        // Filter to applicants only
        url.searchParams.set('kpi_filter', 'applicants');
        url.searchParams.set('page', '1');
    }
    window.location.href = url.toString();
});

document.getElementById('kpiBlacklisted')?.addEventListener('click', function () {
    const url = new URL(window.location.href);
    if (url.searchParams.get('kpi_filter') === 'blacklisted') {
        // Toggle off - remove filter
        url.searchParams.delete('kpi_filter');
        url.searchParams.set('page', '1');
    } else {
        // Filter to blacklisted only
        url.searchParams.set('kpi_filter', 'blacklisted');
        url.searchParams.set('page', '1');
    }
    window.location.href = url.toString();
});

// Check for filter on page load and restore it
function restoreKpiFilter() {
    const params = new URLSearchParams(window.location.search);
    const kpiFilter = params.get('kpi_filter');
    if (kpiFilter === 'applicants' || kpiFilter === 'blacklisted') {
        applyKpiFilter(kpiFilter);
        currentKpiFilter = kpiFilter;
    }
}

// Apply filter on initial page load
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', restoreKpiFilter);
} else {
    restoreKpiFilter();
}
document.addEventListener('keydown', e => {
    if (e.key !== 'Escape') return;
    const vd = document.getElementById('vaultDrawer');
    if (vd && (vd.classList.contains('is-open') || vd.style.display === 'flex')) {
        closeVaultDrawer();
        return;
    }
    closeUploadModal();
});

/** Cross-tab sync: intake checklist vault changes → reload this page without manual refresh. */
const IHSMS_VAULT_SYNC_KEY = 'ihsms_vault_doc_sync';
const IHSMS_VAULT_SYNC_BC = 'ihsms_vault_doc_sync_bc';
let ihsmsVaultSyncTimer = null;
let ihsmsVaultSyncLastTs = '';

function getVaultSyncTs(raw) {
    try {
        const parsed = typeof raw === 'string' ? JSON.parse(raw) : raw;
        return parsed && parsed.ts ? String(parsed.ts) : String(raw || '');
    } catch (_err) {
        return String(raw || '');
    }
}

function scheduleVaultManagementReload() {
    if (ihsmsVaultSyncTimer) clearTimeout(ihsmsVaultSyncTimer);
    ihsmsVaultSyncTimer = setTimeout(function () {
        ihsmsVaultSyncTimer = null;
        location.reload();
    }, 250);
}

function onVaultDocumentSyncEvent(raw) {
    if (!raw) return;
    const ts = getVaultSyncTs(raw);
    if (ts && ts === ihsmsVaultSyncLastTs) return;
    ihsmsVaultSyncLastTs = ts;
    scheduleVaultManagementReload();
}

try {
    const vaultSyncBoot = localStorage.getItem(IHSMS_VAULT_SYNC_KEY);
    if (vaultSyncBoot) ihsmsVaultSyncLastTs = getVaultSyncTs(vaultSyncBoot);
} catch (_bootErr) { /* ignore */ }

window.addEventListener('storage', function (e) {
    if (e.key !== IHSMS_VAULT_SYNC_KEY || e.newValue == null) return;
    onVaultDocumentSyncEvent(e.newValue);
});

try {
    if (typeof BroadcastChannel !== 'undefined') {
        const vaultSyncBc = new BroadcastChannel(IHSMS_VAULT_SYNC_BC);
        vaultSyncBc.onmessage = function (ev) {
            onVaultDocumentSyncEvent(ev && ev.data);
        };
    }
} catch (_bcErr) { /* ignore */ }

document.addEventListener('visibilitychange', function () {
    if (document.visibilityState !== 'visible') return;
    try {
        const raw = localStorage.getItem(IHSMS_VAULT_SYNC_KEY);
        if (!raw) return;
        const ts = getVaultSyncTs(raw);
        if (ts && ts !== ihsmsVaultSyncLastTs) {
            onVaultDocumentSyncEvent(raw);
        }
    } catch (_visErr) { /* ignore */ }
});

// Deep link from Module 2 Applicant Situation Certification (vault upload shortcuts).
document.addEventListener('DOMContentLoaded', () => {
    loadVaultDrawerMapFromDom();
    const vaultDrawerFileInput = document.getElementById('vaultDrawerFileInput');
    if (vaultDrawerFileInput) {
        vaultDrawerFileInput.addEventListener('change', vaultDrawerHandleFileSelected);
    }

    const params = new URLSearchParams(window.location.search);
    const search = params.get('search');
    const applicantId = params.get('applicant_id');
    const openUpload = params.get('open_upload');
    const docType = params.get('document_type');
    const intent = params.get('intent');

    const searchInput = document.getElementById('searchInput');
    const openVaultDeepLink = params.get('open_vault') === '1';
    if (searchInput && openVaultDeepLink) {
        searchInput.value = '';
    }

    if (openUpload === '1') {
        openUploadModal();
        const titleEl = document.getElementById('uploadModalTitle');
        const hintEl = document.getElementById('uploadModalIntentHint');
        const dwtStrip = document.getElementById('uploadModalDwtStrip');
        const fileInput = document.getElementById('fileInput');
        if (titleEl && hintEl) {
            if (intent === 'scan') {
                titleEl.textContent = '📷 Scan document';
                titleEl.style.background = 'linear-gradient(135deg, #6d28d9 0%, #7c3aed 100%)';
                titleEl.style.webkitBackgroundClip = 'text';
                titleEl.style.backgroundClip = 'text';
                titleEl.style.webkitTextFillColor = 'transparent';
                hintEl.textContent = 'Use Dynamsoft (TWAIN) for scanner/camera capture — same as intake requirements “Scan”. Or pick a file below.';
                hintEl.style.display = 'block';
                if (dwtStrip) dwtStrip.style.display = 'flex';
                if (fileInput) fileInput.removeAttribute('required');
            } else if (intent === 'upload') {
                titleEl.textContent = '📁 Upload document';
                titleEl.style.background = 'linear-gradient(135deg, #1e40af 0%, #1e3a8a 100%)';
                titleEl.style.webkitBackgroundClip = 'text';
                titleEl.style.backgroundClip = 'text';
                titleEl.style.webkitTextFillColor = 'transparent';
                hintEl.textContent = 'Choose a file from this computer — same as intake requirements “Upload file”.';
                hintEl.style.display = 'block';
                if (dwtStrip) dwtStrip.style.display = 'none';
                if (fileInput) fileInput.setAttribute('required', 'required');
            }
        }
        const applicantSelect = document.getElementById('applicantSelect');
        if (applicantSelect && applicantId) {
            const want = String(applicantId).trim().toLowerCase();
            for (let i = 0; i < applicantSelect.options.length; i++) {
                const v = String(applicantSelect.options[i].value || '').trim().toLowerCase();
                if (v === want) {
                    applicantSelect.selectedIndex = i;
                    break;
                }
            }
        }
        const typeSel = document.getElementById('uploadDocumentTypeSelect');
        if (typeSel && docType) {
            for (let i = 0; i < typeSel.options.length; i++) {
                if (typeSel.options[i].value === docType) {
                    typeSel.selectedIndex = i;
                    break;
                }
            }
        }

        const autoScan = params.get('auto_scan');
        if (intent === 'scan' && autoScan === '1') {
            try {
                const u = new URL(window.location.href);
                u.searchParams.delete('auto_scan');
                window.history.replaceState({}, '', u.pathname + u.search + u.hash);
            } catch (_e) {}
            setTimeout(function () {
                if (typeof vaultMgmtRunSignedApplicationDwtScan === 'function') {
                    vaultMgmtRunSignedApplicationDwtScan();
                }
            }, 500);
        }
    }

    if (params.get('open_vault') === '1' && applicantId) {
        setTimeout(function () {
            if (typeof openVaultDrawer === 'function') {
                openVaultDrawer(applicantId);
            }
        }, 150);
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
        const hcBrgyLabel = document.getElementById('hcBrgyLabel');
        if (hcBrgyLabel) {
            hcBrgyLabel.textContent = barangay.startsWith('Block ') ? 'Block & lot' : 'Barangay';
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

// Show subtle handoff toast when redirected from Module 2 requirement gate.
(() => {
    const params = new URLSearchParams(window.location.search);
    const reason = params.get('m2_notice');
    const toast = document.getElementById('m2NoticeToast');
    if (reason === 'requirements_gate' && toast) {
        toast.style.display = 'block';
        setTimeout(() => {
            toast.style.transition = 'opacity 250ms ease';
            toast.style.opacity = '0';
            setTimeout(() => { toast.style.display = 'none'; }, 260);
        }, 5200);
    }
})();

/* ── ⋮ Overflow menu helpers ── */
function toggleDmOverflow(btn) {
    const wrap = btn.closest('.dm-overflow-wrap');
    const menu = wrap ? wrap.querySelector('.dm-overflow-menu') : null;
    if (!menu) return;
    const isOpen = menu.style.display !== 'none';
    // Close all open menus first
    closeDmOverflow();
    if (!isOpen) {
        menu.style.display = 'block';
        btn.setAttribute('aria-expanded', 'true');
    }
}

function closeDmOverflow() {
    document.querySelectorAll('.dm-overflow-menu').forEach(function(m) {
        m.style.display = 'none';
    });
    document.querySelectorAll('.dm-overflow-btn').forEach(function(b) {
        b.setAttribute('aria-expanded', 'false');
    });
}

/** Open upload modal pre-filled for a specific applicant row */
function openUploadModalFor(applicantId) {
    const row = document.querySelector('[data-applicant-id="' + applicantId + '"]');
    const name = row ? (row.closest('tr')?.querySelector('.complainant-name')?.textContent?.trim() || '') : '';
    openUploadModalForApplicant(applicantId, name);
}

// Close overflow when clicking outside
document.addEventListener('click', function(e) {
    if (!e.target.closest('.dm-overflow-wrap')) {
        closeDmOverflow();
    }
}, true);

// Close vault Services menus when clicking outside
document.addEventListener('click', function(e) {
    if (!e.target.closest('.vault-svc-wrap')) {
        closeAllVaultSvcMenus();
    }
}, true);

/* ─────────────────────────────────────────
   SMOOTH FILTER TRANSITIONS
   Fires on: ctrl-select change, tab click, search submit
───────────────────────────────────────── */
(function () {
    'use strict';

    function getTableContainer() {
        return document.getElementById('documentsTableContainer');
    }

    function showLoadingState() {
        var tc = getTableContainer();
        if (tc) tc.classList.add('is-loading');
        // Also dim the filter controls slightly
        document.querySelectorAll('.ctrl-select').forEach(function (s) {
            s.classList.add('is-changing');
        });
        document.querySelectorAll('.dm-filter-tab').forEach(function (a) {
            a.style.pointerEvents = 'none';
            a.style.opacity = '0.6';
        });
    }

    // ── Dropdowns (ctrl-select) ──
    document.querySelectorAll('.ctrl-select').forEach(function (sel) {
        // Store original onchange so we can wrap it
        var original = sel.onchange;
        sel.onchange = null;
        sel.addEventListener('change', function () {
            showLoadingState();
            // Small delay so the CSS transition renders before the page freeze
            setTimeout(function () {
                var form = document.getElementById('documentsSearchForm');
                if (form) {
                    form.submit();
                } else if (original) {
                    original.call(sel);
                }
            }, 120);
        });
    });

    // ── Doc-status tab links ──
    document.querySelectorAll('.dm-filter-tab').forEach(function (tab) {
        tab.addEventListener('click', function (e) {
            e.preventDefault();
            var href = tab.getAttribute('href');
            if (!href) return;
            // Press scale — already done via CSS :active, but JS gives us
            // fine-grained control before the navigate
            tab.style.transform = 'scale(0.96)';
            tab.style.opacity   = '0.75';
            showLoadingState();
            setTimeout(function () {
                window.location.href = href;
            }, 110);
        });
    });

    // ── Search form submit ──
    var searchForm = document.getElementById('documentsSearchForm');
    if (searchForm) {
        searchForm.addEventListener('submit', function () {
            showLoadingState();
        });
    }

    // ── Page-out transition when navigating away (pagination, etc.) ──
    document.querySelectorAll('.btn-page:not(.is-disabled)').forEach(function (btn) {
        btn.addEventListener('click', function (e) {
            var href = btn.getAttribute('href');
            if (!href) return;
            e.preventDefault();
            showLoadingState();
            setTimeout(function () { window.location.href = href; }, 100);
        });
    });

}());
