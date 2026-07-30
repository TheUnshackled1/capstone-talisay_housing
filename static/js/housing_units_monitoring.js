let currentUnitId = null;
let currentUnitDetail = null;
const MODULE5_CASES_LIST_URL = '{% if request.user.position == "second_member" or request.user.position == "fourth_member" %}{% url "accounts:second_member_cases" %}{% else %}{% url "accounts:field_cases" %}{% endif %}';

function module5CaseOpenUrl(caseId) {
    if (!caseId) return MODULE5_CASES_LIST_URL;
    const sep = MODULE5_CASES_LIST_URL.includes('?') ? '&' : '?';
    return `${MODULE5_CASES_LIST_URL}${sep}case_id=${encodeURIComponent(caseId)}`;
}

function module5RecordCaseUrl(unit) {
    if (unit && unit.module5_record_case_url) {
        return unit.module5_record_case_url;
    }
    const ben = unit && unit.beneficiary_info;
    if (!ben || !ben.applicant_id || !unit || !unit.id) {
        return null;
    }
    const params = new URLSearchParams({
        applicant_id: ben.applicant_id,
        unit_id: unit.id,
        new_case: '1',
    });
    const sep = MODULE5_CASES_LIST_URL.includes('?') ? '&' : '?';
    return `${MODULE5_CASES_LIST_URL}${sep}${params.toString()}`;
}

function module5CasesListUrl(unit) {
    return (unit && unit.module5_cases_url) || MODULE5_CASES_LIST_URL;
}
let pendingInspectionTask = null;
let activeInspectionTask = null;
let currentMonitoringTasks = [];
let inspectionCarouselIndex = 0;

function getCookie(name) {
    const v = document.cookie.match('(^|;) ?' + name + '=([^;]*)(;|$)');
    return v ? decodeURIComponent(v[2]) : null;
}

async function parseMonitoringJsonResponse(res) {
    const text = await res.text();
    if (!text) {
        throw new Error('Empty response from server.');
    }
    try {
        return JSON.parse(text);
    } catch (parseErr) {
        if (text.trimStart().startsWith('<')) {
            throw new Error(
                res.status === 403
                    ? 'Session expired or access denied. Refresh the page and try again.'
                    : 'Server returned a page instead of data. Refresh the page and try again.'
            );
        }
        throw new Error('Could not read server response.');
    }
}

function updateFooterSmsButton(unit) {
    const smsBtn = document.querySelector('.unit-detail-action-sms');
    if (!smsBtn) return;
    const enable = Boolean(unit && unit.can_send_beneficiary_sms);
    smsBtn.disabled = !enable;
    smsBtn.style.opacity = enable ? '1' : '0.45';
    smsBtn.style.cursor = enable ? 'pointer' : 'not-allowed';
    smsBtn.style.pointerEvents = enable ? 'auto' : 'none';
    smsBtn.title = enable
        ? 'Open Send SMS — review or edit contact number and message.'
        : 'Send SMS requires an active lot award with a linked beneficiary.';
}

function openUnitBeneficiarySmsModal() {
    const unit = lastOpenedUnitPayload;
    const compose = unit && unit.beneficiary_sms_compose;
    if (!currentUnitId || !unit || !compose) {
        monitoringFlowAlert(
            'Send SMS requires an active lot award with a linked beneficiary.',
            'Send SMS',
            'default',
            null
        );
        return;
    }
    const modal = document.getElementById('unitBeneficiarySmsModal');
    const summary = document.getElementById('unitSmsComposeSummary');
    const phoneInp = document.getElementById('unitSmsPhoneInput');
    const msgInp = document.getElementById('unitSmsMessageInput');
    const saveCb = document.getElementById('unitSmsSavePhoneCheckbox');
    if (!modal || !phoneInp || !msgInp) return;

    const locLabel = unit.is_housing_unit_on_file
        ? `Block ${unit.block}, Unit ${unit.lot}`
        : `Block ${unit.block}, Lot ${unit.lot}`;
    const name = compose.full_name || unit.occupant_name || 'Beneficiary';
    const ref = compose.reference_number ? ` · Ref ${compose.reference_number}` : '';
    if (summary) {
        summary.textContent = `${name}${ref} · ${locLabel}`;
    }
    phoneInp.value = compose.phone_number || '';
    originalSmsPhone = phoneInp.value;
    toggleSmsPhoneEdit(false);
    msgInp.value = compose.default_message || '';
    if (saveCb) saveCb.checked = true;

    modal.style.display = 'flex';
}

let originalSmsPhone = '';

function toggleSmsPhoneEdit(editMode) {
    const phoneInp = document.getElementById('unitSmsPhoneInput');
    const editBtn = document.getElementById('unitSmsPhoneEditBtn');
    const cancelBtn = document.getElementById('unitSmsPhoneCancelBtn');
    if (!phoneInp || !editBtn || !cancelBtn) return;
    
    if (editMode) {
        phoneInp.removeAttribute('readonly');
        phoneInp.style.background = '#ffffff';
        phoneInp.style.cursor = 'text';
        phoneInp.focus();
        editBtn.style.display = 'none';
        cancelBtn.style.display = 'inline-block';
    } else {
        phoneInp.value = originalSmsPhone;
        phoneInp.setAttribute('readonly', 'true');
        phoneInp.style.background = '#f1f5f9';
        phoneInp.style.cursor = 'default';
        editBtn.style.display = 'inline-block';
        cancelBtn.style.display = 'none';
    }
}

function closeUnitBeneficiarySmsModal(e) {
    if (e && e.target.id !== 'unitBeneficiarySmsModal') return;
    const modal = document.getElementById('unitBeneficiarySmsModal');
    if (modal) modal.style.display = 'none';
}

async function submitUnitBeneficiarySms() {
    if (!currentUnitId) return;
    const phoneInp = document.getElementById('unitSmsPhoneInput');
    const msgInp = document.getElementById('unitSmsMessageInput');
    const saveCb = document.getElementById('unitSmsSavePhoneCheckbox');
    const submitBtn = document.getElementById('unitSmsSubmitBtn');
    const phone = phoneInp ? phoneInp.value.trim() : '';
    const message = msgInp ? msgInp.value.trim() : '';
    if (!phone) {
        monitoringFlowAlert('Enter the beneficiary contact number.', 'Send SMS', 'default', null);
        return;
    }
    if (message.length < 10) {
        monitoringFlowAlert('Message must be at least 10 characters.', 'Send SMS', 'default', null);
        return;
    }
    const position = '{{ request.user.position }}';
    const prevLabel = submitBtn ? submitBtn.textContent : 'Send SMS';
    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.textContent = 'Sending…';
    }
    try {
        const res = await fetch(
            `/units/housing-units/${position}/${encodeURIComponent(currentUnitId)}/sms/`,
            {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken') || '',
                    'X-Requested-With': 'XMLHttpRequest',
                },
                credentials: 'same-origin',
                body: JSON.stringify({
                    phone_number: phone,
                    message,
                    save_phone_to_applicant: saveCb ? saveCb.checked : true,
                }),
            }
        );
        const data = await parseMonitoringJsonResponse(res);
        if (!res.ok || !data.success) {
            throw new Error(data.error || 'Could not send SMS.');
        }
        closeUnitBeneficiarySmsModal();
        monitoringFlowAlert(
            data.message || 'SMS sent to the beneficiary.',
            'Send SMS',
            'success',
            () => { openUnitModal(currentUnitId); }
        );
    } catch (e) {
        monitoringFlowAlert((e && e.message) ? e.message : 'Could not send SMS.', 'Send SMS', 'default', null);
    } finally {
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.textContent = prevLabel;
        }
    }
}

/**
 * Uses global showFlowAlert (staff_base + flow-alert.css) instead of window.alert.
 * variant: 'success' | 'warning' | 'default'
 */
function monitoringFlowAlert(message, title, variant, onConfirm) {
    let tone = 'default';
    if (variant === 'success') tone = 'success';
    else if (variant === 'warning') tone = 'warning';
    if (typeof showFlowAlert === 'function') {
        showFlowAlert(message || '', title || 'Notice', onConfirm || null, tone);
        return;
    }
    window.alert(message || '');
    if (typeof onConfirm === 'function') onConfirm();
}

function highlightExtensionFailedDisqualifyPath() {
    const onAck = () => {
        if (lastOpenedUnitPayload) {
            applyVmapLotMapBadge(lastOpenedUnitPayload);
            applyUnitDrawerStatusPill(lastOpenedUnitPayload);
        }
        const unitModal = document.getElementById('unitModal');
        const disp = unitModal && unitModal.style.display;
        const drawerOpen = unitModal && (disp === 'flex' || disp === 'block');
        const btn = document.getElementById('disqualifyBeneficiaryBtn');
        if (drawerOpen && btn) {
            btn.classList.add('unit-detail-action-disqualify--highlight');
            btn.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            setTimeout(() => btn.classList.remove('unit-detail-action-disqualify--highlight'), 12000);
        }
    };
    monitoringFlowAlert(
        'Extension marked as Failed.',
        'Failed',
        'default',
        onAck
    );
}

function openCreateSiteModal() {
    const m = document.getElementById('createSiteModal');
    if (!m) return;
    const err = document.getElementById('createSiteFormError');
    if (err) { err.style.display = 'none'; err.textContent = ''; }
    m.style.display = 'flex';
    const nm = document.getElementById('siteNameInput');
    if (nm) setTimeout(() => nm.focus(), 50);
}

function closeCreateSiteModal() {
    const m = document.getElementById('createSiteModal');
    if (!m) return;
    m.style.display = 'none';
    const f = document.getElementById('createSiteForm');
    if (f) f.reset();
    const err = document.getElementById('createSiteFormError');
    if (err) { err.style.display = 'none'; err.textContent = ''; }
}

{% if can_create_relocation_site %}
document.getElementById('createSiteForm')?.addEventListener('submit', async function (e) {
    e.preventDefault();
    const errEl = document.getElementById('createSiteFormError');
    const btn = document.getElementById('createSiteSubmitBtn');
    const body = new URLSearchParams();
    const csrfInput = document.querySelector('#createSiteForm input[name="csrfmiddlewaretoken"]');
    body.append('csrfmiddlewaretoken', (csrfInput && csrfInput.value) || getCookie('csrftoken') || '');
    body.append('name', (document.getElementById('siteNameInput')?.value || '').trim());
    body.append('code', (document.getElementById('siteCodeInput')?.value || '').trim().toUpperCase());
    body.append('barangay_id', (document.getElementById('siteBarangayInput')?.value || '').trim());
    body.append('address', (document.getElementById('siteAddressInput')?.value || '').trim());
    body.append('total_blocks', (document.getElementById('siteBlocksInput')?.value || '0').trim());
    body.append('total_lots', (document.getElementById('siteLotsInput')?.value || '0').trim());
    body.append('notes', (document.getElementById('siteNotesInput')?.value || '').trim());
    errEl.style.display = 'none';
    btn.disabled = true;
    try {
        const res = await fetch('{% url "units:create_relocation_site" request.user.position %}', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: body.toString(),
        });
        const data = await res.json();
        if (data.success) {
            closeCreateSiteModal();
            window.location.reload();
        } else {
            errEl.textContent = data.error || 'Could not create relocation site.';
            errEl.style.display = 'block';
        }
    } catch (ex) {
        errEl.textContent = ex.message || 'Network error.';
        errEl.style.display = 'block';
    } finally {
        btn.disabled = false;
    }
});
{% endif %}

function openAddUnitModal(blockNumber, lotNumber, polygonIndex) {
    const m = document.getElementById('addUnitModal');
    if (!m) return;
    const err = document.getElementById('addUnitFormError');
    if (err) { err.style.display = 'none'; err.textContent = ''; }

    const b = document.getElementById('addUnitBlock');
    const l = document.getElementById('addUnitLot');
    const polyIdxEl = document.getElementById('addUnitPlanPolygonIndex');
    const hasPrefill = blockNumber != null && blockNumber !== ''
        && lotNumber != null && lotNumber !== '';

    if (!hasPrefill) {
        const f = document.getElementById('addUnitForm');
        if (f) f.reset();
        {% if all_sites|length <= 1 %}
        const hid = document.getElementById('addUnitSiteId');
        if (hid && hid.type === 'hidden') hid.value = '{{ site.id }}';
        {% endif %}
        if (polyIdxEl) {
            polyIdxEl.value = (polygonIndex != null && polygonIndex !== '')
                ? String(polygonIndex) : '';
        }
    } else {
        if (b) b.value = String(blockNumber).replace(/\D/g, '');
        if (l) l.value = String(lotNumber).replace(/\D/g, '');
        if (polyIdxEl) {
            polyIdxEl.value = (polygonIndex != null && polygonIndex !== '')
                ? String(polygonIndex) : '';
        }
    }

    m.style.display = 'flex';
    const focusEl = hasPrefill ? document.getElementById('addUnitSubmitBtn') : b;
    if (focusEl) setTimeout(() => focusEl.focus(), 50);
}

function closeAddUnitModal() {
    const m = document.getElementById('addUnitModal');
    if (!m) return;
    m.style.display = 'none';
    const f = document.getElementById('addUnitForm');
    if (f) f.reset();
    const polyIdxEl = document.getElementById('addUnitPlanPolygonIndex');
    if (polyIdxEl) polyIdxEl.value = '';
    const err = document.getElementById('addUnitFormError');
    if (err) { err.style.display = 'none'; err.textContent = ''; }
    {% if all_sites|length <= 1 %}
    const hid = document.getElementById('addUnitSiteId');
    if (hid && hid.type === 'hidden') hid.value = '{{ site.id }}';
    {% endif %}
}

{% if can_add_housing_unit %}
async function linkUnitPlanPolygon(unitId, polygonIndex) {
    const csrfInput = document.querySelector('#addUnitForm input[name="csrfmiddlewaretoken"]')
        || document.querySelector('input[name="csrfmiddlewaretoken"]');
    const body = new URLSearchParams();
    body.append('csrfmiddlewaretoken', (csrfInput && csrfInput.value) || getCookie('csrftoken') || '');
    body.append('plan_polygon_index', String(polygonIndex));
    const position = '{{ request.user.position }}';
    const res = await fetch(`/units/housing-units/${position}/${unitId}/link-plan-polygon/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: body.toString(),
    });
    const data = await res.json();
    if (data.success) {
        closeAddUnitModal();
        monitoringFlowAlert(
            data.message || 'Linked to map plan.',
            'Success',
            'success',
            function () { window.location.reload(); }
        );
    } else {
        monitoringFlowAlert(data.error || 'Could not link to map.', 'Link failed', 'warning', null);
    }
    return data;
}

document.getElementById('addUnitForm')?.addEventListener('submit', async function (e) {
    e.preventDefault();
    const errEl = document.getElementById('addUnitFormError');
    const btn = document.getElementById('addUnitSubmitBtn');
    const siteField = document.getElementById('addUnitSiteId');
    const body = new URLSearchParams();
    const csrfInput = document.querySelector('#addUnitForm input[name="csrfmiddlewaretoken"]');
    body.append('csrfmiddlewaretoken', (csrfInput && csrfInput.value) || getCookie('csrftoken') || '');
    body.append('site_id', siteField ? siteField.value : '');
    body.append('block_number', (document.getElementById('addUnitBlock')?.value || '').trim());
    body.append('lot_number', (document.getElementById('addUnitLot')?.value || '').trim());
    const polyIdx = document.getElementById('addUnitPlanPolygonIndex');
    if (polyIdx && polyIdx.value.trim()) {
        body.append('plan_polygon_index', polyIdx.value.trim());
    }
    errEl.style.display = 'none';
    btn.disabled = true;
    try {
        const res = await fetch('{% url "units:create_housing_unit" request.user.position %}', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: body.toString(),
        });
        const data = await res.json();
        if (data.success) {
            closeAddUnitModal();
            monitoringFlowAlert(
                data.message || 'Housing unit added.',
                'Success',
                'success',
                function() { window.location.reload(); }
            );
        } else if (data.duplicate) {
            const dupHead = 'Not created — this block/lot already exists. Nothing was saved again.';
            const dupDetail = data.error || '';
            errEl.textContent = '';
            const msgP = document.createElement('p');
            msgP.style.margin = '0';
            msgP.textContent = dupHead + (dupDetail ? ' ' + dupDetail : '');
            errEl.appendChild(msgP);
            if (data.existing_unit_id) {
                const polyIdxEl = document.getElementById('addUnitPlanPolygonIndex');
                const polyIdx = polyIdxEl ? polyIdxEl.value.trim() : '';
                if (polyIdx) {
                    const linkBtn = document.createElement('button');
                    linkBtn.type = 'button';
                    linkBtn.className = 'dup-view-existing-btn';
                    linkBtn.textContent = 'Link to this map box';
                    linkBtn.addEventListener('click', function () {
                        linkUnitPlanPolygon(data.existing_unit_id, polyIdx);
                    });
                    errEl.appendChild(linkBtn);
                }
                const viewBtn = document.createElement('button');
                viewBtn.type = 'button';
                viewBtn.className = 'dup-view-existing-btn';
                viewBtn.textContent = 'View existing lot';
                viewBtn.addEventListener('click', function () {
                    closeAddUnitModal();
                    openUnitModal(data.existing_unit_id);
                });
                errEl.appendChild(viewBtn);
            }
            errEl.style.display = 'block';
            monitoringFlowAlert(
                dupHead + (dupDetail ? '\n\n' + dupDetail : ''),
                'Not created',
                'warning',
                null
            );
        } else {
            errEl.textContent = data.error || 'Could not add unit.';
            errEl.style.display = 'block';
        }
    } catch (ex) {
        errEl.textContent = ex.message || 'Network error.';
        errEl.style.display = 'block';
    } finally {
        btn.disabled = false;
    }
});
{% endif %}

function applyUnitInventoryActions(unit) {
    const editBtn = document.getElementById('editInventoryUnitBtn');
    const delBtn = document.getElementById('deleteInventoryUnitBtn');
    if (editBtn) editBtn.style.display = unit && unit.can_edit_inventory ? 'inline-flex' : 'none';
    if (delBtn) delBtn.style.display = unit && unit.can_delete_inventory ? 'inline-flex' : 'none';
}

{% if can_add_housing_unit %}
function openEditUnitModal() {
    const unit = lastOpenedUnitPayload;
    if (!unit || !unit.can_edit_inventory) return;
    const m = document.getElementById('editUnitModal');
    if (!m) return;
    document.getElementById('editUnitId').value = unit.id || '';
    document.getElementById('editUnitBlock').value = unit.block || '';
    document.getElementById('editUnitLot').value = unit.lot || '';
    const notesEl = document.getElementById('editUnitNotes');
    if (notesEl) notesEl.value = unit.location_notes || '';
    const err = document.getElementById('editUnitFormError');
    if (err) { err.style.display = 'none'; err.textContent = ''; }
    m.style.display = 'flex';
}

function closeEditUnitModal() {
    const m = document.getElementById('editUnitModal');
    if (m) m.style.display = 'none';
}

document.getElementById('editUnitForm')?.addEventListener('submit', async function (e) {
    e.preventDefault();
    const unitId = document.getElementById('editUnitId')?.value;
    if (!unitId) return;
    const errEl = document.getElementById('editUnitFormError');
    const btn = document.getElementById('editUnitSubmitBtn');
    const position = '{{ request.user.position }}';
    const body = new URLSearchParams();
    const csrfInput = document.querySelector('#editUnitForm input[name="csrfmiddlewaretoken"]');
    body.append('csrfmiddlewaretoken', (csrfInput && csrfInput.value) || getCookie('csrftoken') || '');
    body.append('block_number', (document.getElementById('editUnitBlock')?.value || '').trim());
    body.append('lot_number', (document.getElementById('editUnitLot')?.value || '').trim());
    body.append('location_notes', (document.getElementById('editUnitNotes')?.value || '').trim());
    errEl.style.display = 'none';
    btn.disabled = true;
    try {
        const res = await fetch(`/units/housing-units/${position}/${unitId}/update/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: body.toString(),
        });
        const data = await res.json();
        if (data.success) {
            closeEditUnitModal();
            closeUnitModal();
            monitoringFlowAlert(data.message || 'Unit updated.', 'Success', 'success', function () {
                window.location.reload();
            });
        } else {
            errEl.textContent = data.error || 'Could not update unit.';
            errEl.style.display = 'block';
        }
    } catch (ex) {
        errEl.textContent = ex.message || 'Network error.';
        errEl.style.display = 'block';
    } finally {
        btn.disabled = false;
    }
});

function confirmDeleteHousingUnit() {
    const unit = lastOpenedUnitPayload;
    if (!unit || !unit.can_delete_inventory) return;
    const label = `B${unit.block} - L${unit.lot}`;
    monitoringFlowAlert(
        `Remove ${label} from the inventory? This cannot be undone.`,
        'Delete housing unit',
        'warning',
        function () { deleteHousingUnit(unit.id); },
    );
}

async function deleteHousingUnit(unitId) {
    const position = '{{ request.user.position }}';
    const body = new URLSearchParams();
    body.append('csrfmiddlewaretoken', getCookie('csrftoken') || '');
    try {
        const res = await fetch(`/units/housing-units/${position}/${unitId}/delete/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: body.toString(),
        });
        const data = await res.json();
        if (data.success) {
            closeUnitModal();
            monitoringFlowAlert(data.message || 'Unit removed.', 'Deleted', 'success', function () {
                window.location.reload();
            });
        } else {
            monitoringFlowAlert(data.error || 'Could not delete unit.', 'Delete failed', 'default', null);
        }
    } catch (ex) {
        monitoringFlowAlert(ex.message || 'Network error.', 'Delete failed', 'default', null);
    }
}
{% endif %}

document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && document.getElementById('createSiteModal')?.style.display === 'flex') {
        closeCreateSiteModal();
        return;
    }
    if (e.key === 'Escape' && document.getElementById('addUnitModal')?.style.display === 'flex') {
        closeAddUnitModal();
        return;
    }
    if (e.key === 'Escape' && document.getElementById('editUnitModal')?.style.display === 'flex') {
        closeEditUnitModal();
        return;
    }
});

/* ==========================================================
   LOT PLAN MAP — exact lot polygons traced from lot_plan.png.
   Polygons (normalized 0..1) are loaded from a static JSON built
   offline by scripts/trace_lot_plan.py and rendered as an SVG
   overlay. Lots are linked to HousingUnit records (from the hidden
   schematic grid) in reading order; extra drawn lots stay inert.
   ========================================================== */
const SVG_NS = 'http://www.w3.org/2000/svg';
const LOT_PLAN_VIEW = 1000; // SVG viewBox size (normalized coords * this)
const LOT_PLAN_STATUS_CLASSES = [
    'vmap-lot--occupied',
    'vmap-lot--vacant',
    'vmap-lot--housing-unit',
    'vmap-lot--extension-failed',
];

function lotPlanStatusClassFrom(sourceLot) {
    for (const cls of LOT_PLAN_STATUS_CLASSES) {
        if (sourceLot.classList.contains(cls)) return 'lotplan-' + cls.slice(5);
    }
    return '';
}

let lotPlanPolygonsPromise = null;
function loadLotPlanPolygons(url) {
    if (!lotPlanPolygonsPromise) {
        lotPlanPolygonsPromise = fetch(url)
            .then(r => (r.ok ? r.json() : Promise.reject(r.status)))
            .catch(() => ({ lots: [] }));
    }
    return lotPlanPolygonsPromise;
}

let lotPlanSlotsPromise = null;
function loadLotPlanSlots(url) {
    if (!lotPlanSlotsPromise) {
        lotPlanSlotsPromise = fetch(url)
            .then(r => (r.ok ? r.json() : Promise.reject(r.status)))
            .catch(() => ({ blocks: {} }));
    }
    return lotPlanSlotsPromise;
}

let lotPlanClustersPromise = null;
function loadLotPlanClusters(url) {
    if (!lotPlanClustersPromise) {
        lotPlanClustersPromise = fetch(url)
            .then(r => (r.ok ? r.json() : Promise.reject(r.status)))
            .catch(() => ({ blocks: {} }));
    }
    return lotPlanClustersPromise;
}

function lotPlanUnitsByBlock() {
    return Array.from(document.querySelectorAll('#gridView-content .vmap-block')).map(blockEl => {
        const nameEl = blockEl.querySelector('.vmap-block-name');
        const m = nameEl ? nameEl.textContent.match(/Block\s+(\d+)/i) : null;
        return {
            block: m ? m[1] : null,
            units: Array.from(blockEl.querySelectorAll('.vmap-lot')),
        };
    }).filter(b => b.block && b.units.length);
}

function lotPlanPolyInRegion(poly, region) {
    const cx = poly.cx || 0;
    const cy = poly.cy || 0;
    return cx >= region.x && cx < (region.x + region.w)
        && cy >= region.y && cy < (region.y + region.h);
}

/** Polygons tagged with block/lot in JSON are reserved for that block only. */
function lotPlanPolyAvailableForBlock(poly, blockNum) {
    if (poly.block == null || poly.block === '') return true;
    return String(poly.block) === String(blockNum);
}

function lotPlanParseBlockLot(unitEl) {
    const idEl = unitEl && unitEl.querySelector('.vmap-lot-id');
    const m = idEl ? idEl.textContent.trim().match(/^B(\d+)\s*-\s*L(\d+)$/i) : null;
    return m ? { block: m[1], lot: m[2] } : null;
}

function lotPlanUnitByLotNumber(blockUnits, lotNum) {
    const want = String(lotNum);
    return blockUnits.find(u => {
        const bl = lotPlanParseBlockLot(u);
        return bl && bl.lot === want;
    });
}

/** Group polygon candidates into horizontal rows (top→bottom), each row left→right. */
function lotPlanClusterIntoRows(candidates, rowBand) {
    const sorted = [...candidates].sort((a, b) => (a.p.cy - b.p.cy) || (a.p.cx - b.p.cx));
    const rows = [];
    sorted.forEach(item => {
        let row = rows.find(r => Math.abs(r.avgCy - item.p.cy) <= rowBand);
        if (!row) {
            row = { items: [], avgCy: item.p.cy };
            rows.push(row);
        }
        row.items.push(item);
        row.avgCy = row.items.reduce((s, x) => s + x.p.cy, 0) / row.items.length;
    });
    rows.sort((a, b) => a.avgCy - b.avgCy);
    rows.forEach(r => r.items.sort((a, b) => a.p.cx - b.p.cx));
    return rows;
}

/** Match inventory lots to nearest polygon using per-block anchor slots. */
function lotPlanPolyMatchesSlotBounds(p, slot) {
    const b = slot && slot.bounds;
    if (!b) return true;
    if (b.minCy != null && p.cy < b.minCy) return false;
    if (b.maxCy != null && p.cy >= b.maxCy) return false;
    if (b.minCx != null && p.cx < b.minCx) return false;
    if (b.maxCx != null && p.cx >= b.maxCx) return false;
    return true;
}

function lotPlanAssignBySlots(blockNum, blockUnits, candidates, blockSlots, assignedPolyIdx, assignments, assignedUnitIds) {
    if (!blockSlots || !Object.keys(blockSlots).length) return false;

    const pool = [...candidates];
    const lotNums = Object.keys(blockSlots).map(n => parseInt(n, 10)).sort((a, b) => a - b);

    lotNums.forEach(lotNum => {
        const slot = blockSlots[String(lotNum)];
        if (!slot) return;
        const unit = lotPlanUnitByLotNumber(blockUnits, lotNum);
        if (!unit || !pool.length) return;
        const uid = unit.dataset.unitId || '';
        if (assignedUnitIds.has(uid)) return;

        let best = null;
        let bestDist = Infinity;
        pool.forEach(cand => {
            if (!lotPlanPolyMatchesSlotBounds(cand.p, slot)) return;
            const dx = cand.p.cx - slot.cx;
            const dy = cand.p.cy - slot.cy;
            const dist = dx * dx + dy * dy;
            if (dist < bestDist) {
                bestDist = dist;
                best = cand;
            }
        });
        if (!best) return;

        const bl = lotPlanParseBlockLot(unit) || { block: blockNum, lot: String(lotNum) };
        assignments.set(best.i, { unit, block: bl.block, lot: bl.lot });
        assignedPolyIdx.add(best.i);
        assignedUnitIds.add(uid);
        pool.splice(pool.indexOf(best), 1);
    });
    return true;
}

/**
 * Assign polygons in a block's primary physical cluster to inventory lots.
 * Polygons outside the primary cluster are never used for this block.
 */
function lotPlanAssignBlockRegion(blockNum, primary, blockUnits, lots, blockSlots, assignedPolyIdx, assignments, assignedUnitIds) {
    const candidates = lots
        .map((p, i) => ({ p, i }))
        .filter(({ p, i }) => !assignedPolyIdx.has(i)
            && lotPlanPolyInRegion(p, primary)
            && lotPlanPolyAvailableForBlock(p, blockNum));

    if (!candidates.length || !blockUnits.length) return;

    const slots = blockSlots[blockNum];
    if (lotPlanAssignBySlots(
        blockNum, blockUnits, candidates, slots,
        assignedPolyIdx, assignments, assignedUnitIds,
    )) {
        return;
    }

    const rowBand = 0.04;
    const sortedUnits = [...blockUnits].sort((a, b) => {
        const la = parseInt((lotPlanParseBlockLot(a) || {}).lot || '0', 10);
        const lb = parseInt((lotPlanParseBlockLot(b) || {}).lot || '0', 10);
        return la - lb;
    });

    const rows = lotPlanClusterIntoRows(candidates, rowBand);
    const ordered = rows.flatMap(r => r.items);
    sortedUnits.forEach((unit, uIdx) => {
        const cand = ordered[uIdx];
        if (!cand) return;
        const uid = unit.dataset.unitId || '';
        if (assignedUnitIds.has(uid)) return;
        const bl = lotPlanParseBlockLot(unit) || { block: blockNum, lot: String(uIdx + 1) };
        assignments.set(cand.i, { unit, block: bl.block, lot: bl.lot });
        assignedPolyIdx.add(cand.i);
        assignedUnitIds.add(uid);
    });
}

function lotPlanAppendLabel(g, poly, blockNum, lotNum, V) {
    const cx = ((poly.cx || 0) * V).toFixed(1);
    const cy = ((poly.cy || 0) * V).toFixed(1);
    const text = document.createElementNS(SVG_NS, 'text');
    text.setAttribute('x', cx);
    text.setAttribute('y', cy);
    text.style.pointerEvents = 'none';
    const tspan1 = document.createElementNS(SVG_NS, 'tspan');
    tspan1.setAttribute('x', cx);
    tspan1.setAttribute('dy', '-0.4em');
    tspan1.style.pointerEvents = 'none';
    tspan1.textContent = 'B' + blockNum;
    const tspan2 = document.createElementNS(SVG_NS, 'tspan');
    tspan2.setAttribute('x', cx);
    tspan2.setAttribute('dy', '1.1em');
    tspan2.style.pointerEvents = 'none';
    tspan2.textContent = 'L' + lotNum;
    text.appendChild(tspan1);
    text.appendChild(tspan2);
    g.appendChild(text);
}

function lotPlanWireLinkedLot(g, poly, unit, blockNum, lotNum, V) {
    g.classList.add('lotplan-lot--linked');
    const unitId = unit.dataset.unitId || '';
    g.setAttribute('data-unit-id', unitId);
    g.setAttribute('data-status', unit.dataset.status || '');
    g.setAttribute('data-construction', unit.dataset.construction || '');
    g.setAttribute('data-housing-unit-on-file', unit.dataset.housingUnitOnFile || '0');
    g.setAttribute('data-historical-beneficiary', unit.dataset.historicalBeneficiary || '0');
    g.setAttribute('data-extension-failed', unit.dataset.extensionFailed || '0');
    if (poly.cx != null) g.setAttribute('data-lot-cx', String(poly.cx));
    if (poly.cy != null) g.setAttribute('data-lot-cy', String(poly.cy));

    const statusCls = lotPlanStatusClassFrom(unit);
    if (statusCls) g.classList.add(statusCls);

    const idText = 'B' + blockNum + ' - L' + lotNum;
    const titleText = unit.getAttribute('title') || idText;
    // We intentionally do NOT create a <title> element here, 
    // so the native tooltip doesn't conflict with the premium hover card popover.

    lotPlanAppendLabel(g, poly, blockNum, lotNum, V);

    g.setAttribute('role', 'button');
    g.setAttribute('tabindex', '0');
    g.setAttribute('aria-label', titleText);
    g.setAttribute('title', ''); // Prevent Chrome from showing aria-label as native tooltip
    if (unitId) {
        g.addEventListener('click', () => openUnitModal(unitId));
        g.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                openUnitModal(unitId);
            }
        });
    }


    if (unit.style.display === 'none') g.style.display = 'none';
}

/** Empty traced lot on the plan — open Add housing unit with blank block/lot fields. */
function lotPlanWireInertLot(g, polygonIndex) {
    if (!document.getElementById('addUnitModal')) return;

    g.classList.add('lotplan-lot--addable');
    g.setAttribute('role', 'button');
    g.setAttribute('tabindex', '0');
    g.setAttribute('aria-label', 'Add housing unit for this lot on the plan');
    if (polygonIndex != null) {
        g.setAttribute('data-polygon-index', String(polygonIndex));
    }

    const openAdd = function () {
        openAddUnitModal(null, null, polygonIndex);
    };
    g.addEventListener('click', openAdd);
    g.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            openAdd();
        }
    });
    g.addEventListener('mousedown', function (e) {
        e.stopPropagation();
    });
}

/** Link units to the map polygon clicked when they were added (DB plan_polygon_index). */
function lotPlanAssignByPolygonIndex(allUnits, lots, assignedPolyIdx, assignments, assignedUnitIds, blockGroups, svg) {
    allUnits.forEach(unit => {
        const uid = unit.dataset.unitId || '';
        if (!uid || assignedUnitIds.has(uid)) return;
        const idxRaw = unit.dataset.planPolygonIndex;
        if (!idxRaw) return;
        const idx = parseInt(idxRaw, 10);
        if (!Number.isFinite(idx) || idx < 0 || idx >= lots.length) return;
        if (assignedPolyIdx.has(idx)) return;
        const bl = lotPlanParseBlockLot(unit);
        if (!bl) return;

        assignments.set(idx, { unit, block: bl.block, lot: bl.lot });
        assignedPolyIdx.add(idx);
        assignedUnitIds.add(uid);

        if (!blockGroups.has(bl.block)) {
            const bg = document.createElementNS(SVG_NS, 'g');
            bg.setAttribute('class', 'lotplan-block');
            bg.dataset.block = bl.block;
            blockGroups.set(bl.block, bg);
            svg.appendChild(bg);
        }
    });
}

/** Link inventory lots to polygons tagged with block/lot in lot_plan_polygons.json. */
function lotPlanAssignByPolygonMetadata(allUnits, lots, assignedPolyIdx, assignments, assignedUnitIds, blockGroups, svg) {
    allUnits.forEach(unit => {
        const uid = unit.dataset.unitId || '';
        if (!uid || assignedUnitIds.has(uid)) return;
        const bl = lotPlanParseBlockLot(unit);
        if (!bl) return;
        const wantBlock = parseInt(bl.block, 10);
        const wantLot = parseInt(bl.lot, 10);
        if (!Number.isFinite(wantBlock) || !Number.isFinite(wantLot)) return;

        const matchIdx = lots.findIndex((poly, i) => {
            if (assignedPolyIdx.has(i)) return false;
            const pb = parseInt(poly.block, 10);
            const pl = parseInt(poly.lot, 10);
            return pb === wantBlock && pl === wantLot;
        });
        if (matchIdx < 0) return;

        assignments.set(matchIdx, { unit, block: bl.block, lot: bl.lot });
        assignedPolyIdx.add(matchIdx);
        assignedUnitIds.add(uid);

        if (!blockGroups.has(bl.block)) {
            const bg = document.createElementNS(SVG_NS, 'g');
            bg.setAttribute('class', 'lotplan-block');
            bg.dataset.block = bl.block;
            blockGroups.set(bl.block, bg);
            svg.appendChild(bg);
        }
    });
}

async function buildLotPlan() {
    const svg = document.getElementById('lotplan-svg');
    if (!svg) return;

    const units = Array.from(document.querySelectorAll('#gridView-content .vmap-lot'));
    const unitsByBlock = lotPlanUnitsByBlock();
    const unitByBlockMap = {};
    unitsByBlock.forEach(b => { unitByBlockMap[b.block] = b.units; });

    const url = svg.dataset.polygonsUrl ? (svg.dataset.polygonsUrl + '?v=' + Date.now()) : null;
    const slotsUrl = svg.dataset.slotsUrl ? (svg.dataset.slotsUrl + '?v=' + Date.now()) : null;
    const clustersUrl = svg.dataset.clustersUrl ? (svg.dataset.clustersUrl + '?v=' + Date.now()) : null;
    const [data, slotsData, clustersData] = await Promise.all([
        url ? loadLotPlanPolygons(url) : { lots: [] },
        slotsUrl ? loadLotPlanSlots(slotsUrl) : { blocks: {} },
        clustersUrl ? loadLotPlanClusters(clustersUrl) : { blocks: {} },
    ]);
    const lots = (data && data.lots) || [];
    const blockSlots = (slotsData && slotsData.blocks) || {};
    const blockClusters = (clustersData && clustersData.blocks) || {};

    while (svg.firstChild) svg.removeChild(svg.firstChild);
    if (!lots.length) return;

    const V = LOT_PLAN_VIEW;
    const assignments = new Map();
    const assignedPolyIdx = new Set();
    const assignedUnitIds = new Set();
    const blockGroups = new Map();
    const allGridUnits = Array.from(document.querySelectorAll('#gridView-content .vmap-lot'));

    // Map click binding first, then JSON metadata, then spatial clusters.
    lotPlanAssignByPolygonIndex(
        allGridUnits, lots, assignedPolyIdx, assignments, assignedUnitIds, blockGroups, svg,
    );
    lotPlanAssignByPolygonMetadata(
        allGridUnits, lots, assignedPolyIdx, assignments, assignedUnitIds, blockGroups, svg,
    );

    Object.keys(blockClusters)
        .sort((a, b) => parseInt(a, 10) - parseInt(b, 10))
        .forEach(blockNum => {
            const blockUnits = unitByBlockMap[blockNum] || [];
            const cluster = blockClusters[blockNum];
            if (!blockUnits.length || !cluster || !cluster.primary) return;
            lotPlanAssignBlockRegion(
                blockNum, cluster.primary, blockUnits, lots, blockSlots,
                assignedPolyIdx, assignments, assignedUnitIds,
            );
            const bg = document.createElementNS(SVG_NS, 'g');
            bg.setAttribute('class', 'lotplan-block');
            bg.dataset.block = blockNum;
            blockGroups.set(blockNum, bg);
            svg.appendChild(bg);
        });

    const inertLayer = document.createElementNS(SVG_NS, 'g');
    inertLayer.setAttribute('class', 'lotplan-inert-layer');
    svg.appendChild(inertLayer);

    lots.forEach((poly, i) => {
        const g = document.createElementNS(SVG_NS, 'g');
        g.setAttribute('class', 'lotplan-lot');

        const polygon = document.createElementNS(SVG_NS, 'polygon');
        polygon.setAttribute(
            'points',
            (poly.points || [])
                .map(p => (p[0] * V).toFixed(1) + ',' + (p[1] * V).toFixed(1))
                .join(' ')
        );
        g.appendChild(polygon);

        const assign = assignments.get(i);
        if (assign) {
            lotPlanWireLinkedLot(g, poly, assign.unit, assign.block, assign.lot, V);
            const parent = blockGroups.get(assign.block) || svg;
            parent.appendChild(g);
        } else {
            g.classList.add('lotplan-lot--inert');
            lotPlanWireInertLot(g, i);
            inertLayer.appendChild(g);
        }
    });
    lotPlanRenderUnmappedPanel();
}

function lotPlanRenderUnmappedPanel() {
    const panel = document.getElementById('lotplan-unmapped-panel');
    const list = document.getElementById('lotplan-unmapped-list');
    const countEl = document.getElementById('lotplan-unmapped-count');
    if (!panel || !list) return;

    const linkedIds = new Set(
        Array.from(document.querySelectorAll('.lotplan-lot--linked[data-unit-id]'))
            .map(g => g.getAttribute('data-unit-id'))
            .filter(Boolean)
    );

    const unmapped = Array.from(document.querySelectorAll('#gridView-content .vmap-lot'))
        .filter(el => {
            const uid = el.dataset.unitId;
            return uid && !linkedIds.has(uid);
        })
        .sort((a, b) => {
            const ba = parseInt(a.dataset.block || '0', 10);
            const bb = parseInt(b.dataset.block || '0', 10);
            if (ba !== bb) return ba - bb;
            return parseInt(a.dataset.lot || '0', 10) - parseInt(b.dataset.lot || '0', 10);
        });

    list.innerHTML = '';
    if (!unmapped.length) {
        panel.hidden = true;
        return;
    }

    unmapped.forEach(el => {
        const li = document.createElement('li');
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'lotplan-unmapped-item';
        btn.textContent = 'B' + (el.dataset.block || '?') + ' - L' + (el.dataset.lot || '?');
        const unitId = el.dataset.unitId;
        if (unitId) {
            btn.addEventListener('click', () => openUnitModal(unitId));
        }
        li.appendChild(btn);
        const tag = el.querySelector('.vmap-lot-tag');
        if (tag && tag.textContent.trim()) {
            const status = document.createElement('span');
            status.className = 'lotplan-unmapped-status';
            status.textContent = tag.textContent.trim();
            li.appendChild(status);
        }
        list.appendChild(li);
    });

    if (countEl) countEl.textContent = String(unmapped.length);
    panel.hidden = false;
}

/* ==========================================================
   LOT PLAN SEARCH — Google Maps-style block/lot finder
   ========================================================== */
function lotPlanBuildSearchIndex() {
    return Array.from(document.querySelectorAll('#gridView-content .vmap-lot')).map(el => {
        const block = el.dataset.block || '';
        const lot = el.dataset.lot || '';
        const tag = el.querySelector('.vmap-lot-tag');
        let status = el.dataset.status || '';
        if (tag && tag.textContent.trim()) status = tag.textContent.trim();
        return {
            unitId: el.dataset.unitId || '',
            block,
            lot,
            label: 'B' + block + ' - L' + lot,
            status,
        };
    }).filter(item => item.unitId);
}

function lotPlanParseSearchQuery(q) {
    const raw = (q || '').trim().toLowerCase();
    if (!raw) return null;

    let m = raw.match(/(?:block\s*)?(\d+)\s*(?:lot\s*|l\s*|[-/]\s*)?(\d+)?/);
    if (!m) m = raw.match(/b\s*(\d+)\s*(?:l\s*|[-/]\s*)?(\d+)?/);
    if (m) return { block: m[1], lot: m[2] || null };

    const nums = raw.match(/\d+/g);
    if (!nums || !nums.length) return null;
    if (nums.length >= 2) return { block: nums[0], lot: nums[1] };
    return { block: nums[0], lot: null };
}

function lotPlanSearchFilter(index, query) {
    const parsed = lotPlanParseSearchQuery(query);
    if (!parsed) return [];

    return index.filter(item => {
        if (parsed.lot) {
            return item.block === parsed.block && item.lot === parsed.lot;
        }
        return item.block === parsed.block;
    }).sort((a, b) => {
        const bk = parseInt(a.block, 10) - parseInt(b.block, 10);
        return bk || parseInt(a.lot, 10) - parseInt(b.lot, 10);
    });
}

let _lotPlanSearchHitEl = null;

function lotPlanSearchSelect(unitId, keepHighlight) {
    // Clear previous highlight
    if (_lotPlanSearchHitEl) {
        _lotPlanSearchHitEl.classList.remove('lotplan-lot--search-hit');
        _lotPlanSearchHitEl = null;
    }

    const g = document.querySelector('.lotplan-lot--linked[data-unit-id="' + unitId + '"]');
    if (g) {
        const cx = parseFloat(g.getAttribute('data-lot-cx') || g.dataset?.lotCx);
        const cy = parseFloat(g.getAttribute('data-lot-cy') || g.dataset?.lotCy);
        if (window.lotPlanScrollTo && !isNaN(cx) && !isNaN(cy)) {
            window.lotPlanScrollTo(cx, cy);
        }
        g.classList.remove('lotplan-lot--search-hit');
        void g.getBoundingClientRect(); // force reflow
        g.classList.add('lotplan-lot--search-hit');
        _lotPlanSearchHitEl = g;

        if (!keepHighlight) {
            // Auto-clear after 4s if not persistent
            setTimeout(() => {
                g.classList.remove('lotplan-lot--search-hit');
                if (_lotPlanSearchHitEl === g) _lotPlanSearchHitEl = null;
            }, 4000);
        }

        // Scroll the polygon into view
        const rect = g.getBoundingClientRect();
        if (rect.top < 60 || rect.bottom > window.innerHeight - 60) {
            g.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    } else if (unitId && typeof openUnitModal === 'function') {
        openUnitModal(unitId);
    }
    // Do NOT auto-open modal when map zone exists — highlight only
}

function initLotPlanSearch() {
    const input = document.getElementById('lotplan-search-input');
    const resultsEl = document.getElementById('lotplan-search-results');
    const clearBtn = document.getElementById('lotplan-search-clear');
    const toggleBtn = document.getElementById('lotplan-search-toggle');
    const expandable = document.getElementById('lotplan-search-expandable');
    const pill = document.getElementById('lotplan-search-pill');

    // Wire up the toggle button - morphs the pill horizontally
    if (toggleBtn && pill) {
        toggleBtn.addEventListener('click', function (e) {
            e.stopPropagation();
            const isOpen = pill.classList.contains('is-open');
            if (isOpen) {
                pill.classList.remove('is-open');
                toggleBtn.setAttribute('aria-expanded', 'false');
                if (input) { input.value = ''; }
                if (resultsEl) { resultsEl.classList.remove('is-open'); resultsEl.innerHTML = ''; }
                if (clearBtn) clearBtn.classList.remove('is-visible');
            } else {
                pill.classList.add('is-open');
                toggleBtn.setAttribute('aria-expanded', 'true');
                // Focus input after width transition completes
                setTimeout(() => { if (input) input.focus(); }, 360);
            }
        });

        // Close when clicking outside the search
        document.addEventListener('click', function (e) {
            if (!pill.contains(e.target) && !resultsEl?.contains(e.target)) {
                if (pill.classList.contains('is-open')) {
                    pill.classList.remove('is-open');
                    toggleBtn.setAttribute('aria-expanded', 'false');
                    if (input) input.value = '';
                    if (resultsEl) { resultsEl.classList.remove('is-open'); resultsEl.innerHTML = ''; }
                    if (clearBtn) clearBtn.classList.remove('is-visible');
                }
            }
        });
    }

    if (!input || !resultsEl) return;

    const index = lotPlanBuildSearchIndex();
    let activeIdx = -1;
    let visible = [];

    function closeResults() {
        resultsEl.classList.remove('is-open');
        input.setAttribute('aria-expanded', 'false');
        activeIdx = -1;
        visible = [];
    }

    function renderResults(matches) {
        visible = matches.slice(0, 8);
        resultsEl.innerHTML = '';
        if (!visible.length) {
            const li = document.createElement('li');
            li.className = 'lotplan-search-empty';
            li.textContent = input.value.trim() ? 'No matching block/lot' : 'Type a block or lot (e.g. 12 1)';
            resultsEl.appendChild(li);
        } else {
            visible.forEach((item, i) => {
                const li = document.createElement('li');
                li.className = 'lotplan-search-result' + (i === activeIdx ? ' is-active' : '');
                li.setAttribute('role', 'option');
                li.dataset.unitId = item.unitId;
                li.innerHTML =
                    '<span class="lotplan-search-result-label">' + item.label + '</span>' +
                    '<span class="lotplan-search-result-status">' + (item.status || '—') + '</span>';
                li.addEventListener('mousedown', (e) => {
                    e.preventDefault();
                    lotPlanSearchSelect(item.unitId, true);
                    input.value = item.label;
                    if (clearBtn) clearBtn.classList.add('is-visible');
                    closeResults();
                });
                resultsEl.appendChild(li);
            });
        }
        resultsEl.classList.add('is-open');
        input.setAttribute('aria-expanded', 'true');
    }

    function runSearch() {
        const q = input.value;
        if (clearBtn) clearBtn.classList.toggle('is-visible', !!q.trim());
        if (!q.trim()) {
            closeResults();
            resultsEl.innerHTML = '';
            return;
        }
        activeIdx = -1;
        renderResults(lotPlanSearchFilter(index, q));
    }

    input.addEventListener('input', runSearch);
    input.addEventListener('focus', () => {
        if (input.value.trim()) runSearch();
    });

    input.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closeResults();
            return;
        }
        if (!resultsEl.classList.contains('is-open') || !visible.length) {
            if (e.key === 'Enter') {
                e.preventDefault();
                runSearch();
                if (visible.length === 1) {
                    lotPlanSearchSelect(visible[0].unitId, true);
                    input.value = visible[0].label;
                    closeResults();
                }
            }
            return;
        }
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            activeIdx = Math.min(activeIdx + 1, visible.length - 1);
            renderResults(visible);
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            activeIdx = Math.max(activeIdx - 1, 0);
            renderResults(visible);
        } else if (e.key === 'Enter') {
            e.preventDefault();
            const pick = visible[activeIdx >= 0 ? activeIdx : 0];
            if (pick) {
                lotPlanSearchSelect(pick.unitId, true);
                input.value = pick.label;
                closeResults();
            }
        }
    });

    if (clearBtn) {
        clearBtn.addEventListener('click', () => {
            input.value = '';
            clearBtn.classList.remove('is-visible');
            closeResults();
            // Clear the orange highlight
            if (_lotPlanSearchHitEl) {
                _lotPlanSearchHitEl.classList.remove('lotplan-lot--search-hit');
                _lotPlanSearchHitEl = null;
            }
            resultsEl.innerHTML = '';
            input.focus();
        });
    }

    document.addEventListener('click', (e) => {
        if (!e.target.closest('#lotplan-search')) closeResults();
    });
}

/* ==========================================================
   LOT PLAN ZOOM / PAN — Google-Maps-style interaction.
   Wheel to zoom, drag to pan, +/- buttons, pinch on touch.
   ========================================================== */
function initLotPlanZoom() {
    const wrapper = document.getElementById('lotplan-zoom-wrapper');
    const stage   = document.getElementById('lotplan-zoomable');
    if (!wrapper || !stage) return;

    const btnIn    = document.getElementById('lotplan-zoom-in');
    const btnOut   = document.getElementById('lotplan-zoom-out');
    const btnReset = document.getElementById('lotplan-zoom-reset');
    const levelEl  = document.getElementById('lotplan-zoom-level');

    const MIN_ZOOM = 0.75; // 75% standard minimum zoom
    const MAX_ZOOM = 4;   // 400%
    const ZOOM_STEP = 0.25;
    const DEFAULT_ZOOM = 0.75;

    let scale = DEFAULT_ZOOM;
    let panX = 0;
    let panY = 0;
    let isDragging = false;
    let dragStartX = 0;
    let dragStartY = 0;
    let panStartX = 0;
    let panStartY = 0;
    let wheelTimer = null;

    function getNaturalStageH() {
        // Height of stage at scale=1 (offsetHeight before transform)
        return stage.offsetHeight;
    }

    function clampPan() {
        const wW = wrapper.clientWidth;
        const wH = wrapper.clientHeight;
        const sW = wW * scale;
        const sH = getNaturalStageH() * scale;
        // When zoomed out the map is smaller than the wrapper — center it
        if (sW <= wW) {
            panX = (wW - sW) / 2;
        } else {
            panX = Math.max(Math.min(0, panX), wW - sW);
        }
        if (sH <= wH) {
            panY = (wH - sH) / 2;
        } else {
            panY = Math.max(Math.min(0, panY), wH - sH);
        }
    }

    function applyTransform() {
        clampPan();
        stage.style.transform = `translate(${panX}px, ${panY}px) scale(${scale})`;
        if (levelEl) levelEl.textContent = Math.round(scale * 100) + '%';
    }

    function zoomTo(newScale, cx, cy) {
        const oldScale = scale;
        newScale = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, newScale));
        if (newScale === oldScale) return;
        const ratio = newScale / oldScale;
        panX = cx - ratio * (cx - panX);
        panY = cy - ratio * (cy - panY);
        scale = newScale;
        applyTransform();
    }

    function resetZoom() {
        scale = DEFAULT_ZOOM;
        panX = 0;
        panY = 0;
        applyTransform();
    }

    function flyTo(normCx, normCy, targetScale) {
        const wW = wrapper.clientWidth;
        const wH = wrapper.clientHeight;
        const stageW = wW;
        const stageH = getNaturalStageH();
        const px = normCx * stageW;
        const py = normCy * stageH;
        const newScale = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, targetScale || 2.5));
        scale = newScale;
        panX = wW / 2 - px * scale;
        panY = wH / 2 - py * scale;
        applyTransform();
    }

    window.lotPlanMap = { flyTo, resetZoom };

    // --- Mouse wheel zoom (responsive — no transition during wheel) ---
    wrapper.addEventListener('wheel', function (e) {
        e.preventDefault();
        stage.classList.add('is-wheeling');
        clearTimeout(wheelTimer);
        wheelTimer = setTimeout(() => stage.classList.remove('is-wheeling'), 120);
        const rect = wrapper.getBoundingClientRect();
        const cx = e.clientX - rect.left;
        const cy = e.clientY - rect.top;
        const delta = e.deltaY > 0 ? -ZOOM_STEP : ZOOM_STEP;
        zoomTo(scale + delta, cx, cy);
    }, { passive: false });

    // --- Drag to pan (works at any zoom level) ---
    wrapper.addEventListener('mousedown', function (e) {
        if (e.button !== 0) return;
        isDragging = true;
        dragStartX = e.clientX;
        dragStartY = e.clientY;
        panStartX = panX;
        panStartY = panY;
        stage.classList.add('is-dragging');
        e.preventDefault();
    });

    document.addEventListener('mousemove', function (e) {
        if (!isDragging) return;
        panX = panStartX + (e.clientX - dragStartX);
        panY = panStartY + (e.clientY - dragStartY);
        applyTransform();
    });

    document.addEventListener('mouseup', function () {
        if (isDragging) {
            isDragging = false;
            stage.classList.remove('is-dragging');
        }
    });

    // --- Touch: pinch-to-zoom + drag ---
    let lastTouchDist = 0;
    let lastTouchCenter = null;

    wrapper.addEventListener('touchstart', function (e) {
        if (e.touches.length === 2) {
            e.preventDefault();
            const dx = e.touches[0].clientX - e.touches[1].clientX;
            const dy = e.touches[0].clientY - e.touches[1].clientY;
            lastTouchDist = Math.hypot(dx, dy);
            const rect = wrapper.getBoundingClientRect();
            lastTouchCenter = {
                x: (e.touches[0].clientX + e.touches[1].clientX) / 2 - rect.left,
                y: (e.touches[0].clientY + e.touches[1].clientY) / 2 - rect.top,
            };
        } else if (e.touches.length === 1) {
            isDragging = true;
            dragStartX = e.touches[0].clientX;
            dragStartY = e.touches[0].clientY;
            panStartX = panX;
            panStartY = panY;
        }
    }, { passive: false });

    wrapper.addEventListener('touchmove', function (e) {
        if (e.touches.length === 2 && lastTouchDist) {
            e.preventDefault();
            const dx = e.touches[0].clientX - e.touches[1].clientX;
            const dy = e.touches[0].clientY - e.touches[1].clientY;
            const dist = Math.hypot(dx, dy);
            const newScale = scale * (dist / lastTouchDist);
            zoomTo(newScale, lastTouchCenter.x, lastTouchCenter.y);
            lastTouchDist = dist;
        } else if (isDragging && e.touches.length === 1) {
            e.preventDefault();
            panX = panStartX + (e.touches[0].clientX - dragStartX);
            panY = panStartY + (e.touches[0].clientY - dragStartY);
            applyTransform();
        }
    }, { passive: false });

    wrapper.addEventListener('touchend', function () {
        lastTouchDist = 0;
        lastTouchCenter = null;
        isDragging = false;
    });

    // --- Buttons ---
    if (btnIn) btnIn.addEventListener('click', function () {
        const rect = wrapper.getBoundingClientRect();
        zoomTo(scale + ZOOM_STEP, rect.width / 2, rect.height / 2);
    });
    if (btnOut) btnOut.addEventListener('click', function () {
        const rect = wrapper.getBoundingClientRect();
        zoomTo(scale - ZOOM_STEP, rect.width / 2, rect.height / 2);
    });
    if (btnReset) btnReset.addEventListener('click', resetZoom);
    // Clicking the zoom level label also resets
    if (levelEl) levelEl.addEventListener('click', resetZoom);

    // --- Keyboard shortcuts (only when map is in view) ---
    document.addEventListener('keydown', function (e) {
        if (!wrapper) return;
        const rect = wrapper.getBoundingClientRect();
        const inViewport = rect.top < window.innerHeight && rect.bottom > 0;
        if (!inViewport) return;
        // Ignore if focus is inside a text input
        const tag = document.activeElement && document.activeElement.tagName;
        if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
        const cx = rect.width / 2;
        const cy = rect.height / 2;
        if (e.key === '+' || e.key === '=') {
            e.preventDefault();
            zoomTo(scale + ZOOM_STEP, cx, cy);
        } else if (e.key === '-') {
            e.preventDefault();
            zoomTo(scale - ZOOM_STEP, cx, cy);
        } else if (e.key === '0') {
            e.preventDefault();
            resetZoom();
        }
    });

    // --- Double-click to zoom in ---
    wrapper.addEventListener('dblclick', function (e) {
        const rect = wrapper.getBoundingClientRect();
        const cx = e.clientX - rect.left;
        const cy = e.clientY - rect.top;
        if (scale >= MAX_ZOOM) {
            resetZoom();
        } else {
            zoomTo(scale + ZOOM_STEP * 2, cx, cy);
        }
    });

    // --- Initial setup ---
    // Apply the default zoom scale (75%) immediately
    applyTransform();

    // Re-apply if the image loads after initialization (which changes offsetHeight)
    const lotplanImg = stage.querySelector('.lotplan-img');
    if (lotplanImg) {
        if (lotplanImg.complete) {
            applyTransform();
        } else {
            lotplanImg.addEventListener('load', applyTransform);
        }
    }
}

function applyUnitDetailHeader(unit) {
    const kicker = document.getElementById('modalUnitKicker');
    const titleEl = document.getElementById('modalUnitTitle');
    if (!unit || !titleEl) return;
    const isHistorical = !!unit.is_historical_beneficiary;
    const isHu = !!(unit.is_housing_unit_on_file || unit.status_display === 'Housing unit');
    if (kicker) {
        kicker.textContent = (isHu || isHistorical) ? 'Unit detail' : 'Lot detail';
    }
    titleEl.textContent = (isHu || isHistorical)
        ? `B${unit.block} - Unit ${unit.lot}`
        : `B${unit.block} - L${unit.lot}`;
}

function applyUnitDrawerStatusPill(unit) {
    const statusPill = document.getElementById('modalUnitStatus');
    if (!statusPill || !unit) return;
    const statusKeyMap = {
        Occupied: 'occupied',
        'Vacant — available': 'vacant',
        'Under notice (30-day)': 'notice30',
        'Final notice (10-day)': 'final',
        Repossessed: 'repo',
        'Housing unit': 'housing-unit',
        Unit: 'historical-unit',
    };
    if (unit.is_housing_unit_on_file || unit.status_display === 'Housing unit') {
        statusPill.textContent = 'Housing unit';
        statusPill.dataset.state = 'housing-unit';
        statusPill.title = 'Recognized housing unit: final monitoring done and construction complete — this lot is counted as a completed unit in inventory.';
    } else if (unit.is_historical_beneficiary) {
        statusPill.textContent = 'Unit';
        statusPill.dataset.state = 'historical-unit';
        statusPill.title = 'Historical on-site beneficiary — registered before THA field monitoring was tracked in this system.';
    } else if (unit.extension_final_visit_failed) {
        statusPill.textContent = 'Failed';
        statusPill.dataset.state = 'failed';
        statusPill.title = 'Extension final 120 Day visit marked Failed — review blacklist beneficiary when eligible.';
    } else {
        statusPill.textContent = unit.status_display || unit.status;
        statusPill.dataset.state = statusKeyMap[unit.status] || 'vacant';
        statusPill.removeAttribute('title');
    }
}

function applyVmapLotMapBadge(unit) {
    const unitId = String((unit && unit.id) != null ? unit.id : unit);

    // Keep the lot-plan zone (if rendered) in sync with status changes.
    const planZone = document.querySelector(`.lotplan-lot[data-unit-id="${unitId}"]`);
    if (planZone) {
        const zOnFile = !!(unit && unit.is_housing_unit_on_file);
        const zHistorical = !!(unit && unit.is_historical_beneficiary);
        const zExtFailed = !!(unit && unit.extension_final_visit_failed);
        const zSt = (unit && unit.status) != null ? unit.status : (planZone.dataset.status || '');
        planZone.dataset.housingUnitOnFile = zOnFile ? '1' : '0';
        planZone.dataset.historicalBeneficiary = zHistorical ? '1' : '0';
        planZone.dataset.extensionFailed = zExtFailed ? '1' : '0';
        if (zSt) planZone.dataset.status = zSt;
        planZone.classList.remove(
            'lotplan-lot--occupied', 'lotplan-lot--vacant',
            'lotplan-lot--housing-unit', 'lotplan-lot--extension-failed',
        );
        if (zOnFile || zHistorical) planZone.classList.add('lotplan-lot--housing-unit');
        else if (zExtFailed) planZone.classList.add('lotplan-lot--extension-failed');
        else if (zSt === 'Occupied') planZone.classList.add('lotplan-lot--occupied');
        else if (zSt === 'Vacant — available') planZone.classList.add('lotplan-lot--vacant');
    }

    const chip = document.querySelector(`button.vmap-lot[data-unit-id="${unitId}"]`);
    if (!chip) return;
    const tag = chip.querySelector('.vmap-lot-tag');
    const isOnFile = !!(unit && unit.is_housing_unit_on_file);
    const isHistorical = !!(unit && unit.is_historical_beneficiary);
    const extFailed = !!(unit && unit.extension_final_visit_failed);
    const st = (unit && unit.status) != null ? unit.status : (chip.dataset.status || '');
    chip.classList.remove(
        'vmap-lot--housing-unit', 'vmap-lot--occupied', 'vmap-lot--vacant', 'vmap-lot--extension-failed',
    );
    chip.dataset.housingUnitOnFile = isOnFile ? '1' : '0';
    chip.dataset.historicalBeneficiary = isHistorical ? '1' : '0';
    chip.dataset.extensionFailed = extFailed ? '1' : '0';
    if (isOnFile) {
        chip.classList.add('vmap-lot--housing-unit');
        if (tag) tag.textContent = 'Unit';
        return;
    }
    if (isHistorical) {
        chip.classList.add('vmap-lot--housing-unit');
        if (tag) tag.textContent = 'Unit';
        return;
    }
    if (extFailed) {
        chip.classList.add('vmap-lot--extension-failed');
        if (tag) tag.textContent = 'Failed';
        return;
    }
    if (st === 'Occupied') {
        chip.classList.add('vmap-lot--occupied');
        if (tag) tag.textContent = 'Occupied';
    } else if (st === 'Vacant — available') {
        chip.classList.add('vmap-lot--vacant');
        if (tag) tag.textContent = 'Vacant';
    } else if (tag) {
        tag.textContent = st || '—';
    }
}

function kpiFilter(card) {
    if (!card) return;
    const kind = card.dataset.fkind;
    const val = card.dataset.fval;
    const cards = document.querySelectorAll('.units-kpi[role="button"]');
    const reset = card.classList.contains('is-active') && kind !== 'all';  // click active card again -> clear
    cards.forEach(c => c.classList.remove('is-active'));
    if (!reset) card.classList.add('is-active');
    const showAll = reset || kind === 'all';

    function lotIsRecognizedHousingUnit(lot) {
        return (lot.dataset.housingUnitOnFile || '') === '1'
            || (lot.dataset.historicalBeneficiary || '') === '1';
    }

    document.querySelectorAll('.vmap-lot').forEach(lot => {
        let show = true;
        if (!showAll) {
            if (kind === 'status') {
                if (val === 'Occupied') {
                    show = (lot.dataset.status || '') === val
                        && (lot.dataset.historicalBeneficiary || '') !== '1';
                } else {
                    show = (lot.dataset.status || '') === val;
                }
            } else if (kind === 'housing_unit') {
                show = lotIsRecognizedHousingUnit(lot);
            }
        }
        lot.style.display = show ? '' : 'none';
    });

    document.querySelectorAll('.vmap-block').forEach(block => {
        const any = Array.from(block.querySelectorAll('.vmap-lot')).some(
            l => l.style.display !== 'none'
        );
        block.style.display = any ? '' : 'none';
    });

    document.querySelectorAll('.lotplan-lot').forEach(lot => {
        let show = true;
        if (!showAll) {
            if (kind === 'status') {
                if (val === 'Occupied') {
                    show = (lot.dataset.status || '') === val
                        && (lot.dataset.historicalBeneficiary || '') !== '1';
                } else {
                    show = (lot.dataset.status || '') === val;
                }
            } else if (kind === 'housing_unit') {
                show = lotIsRecognizedHousingUnit(lot);
            }
        }
        lot.style.display = show ? '' : 'none';
    });
}

function monitoringTaskDisplayTitle(task) {
    if (!task) return '—';
    if (task.label) return task.label;
    if (task.task_type === 'day_60_inspection') return '90 Day Inspection';
    if (task.task_type === 'month_1_inspection') return 'Extension 90 Day Inspection';
    if (task.task_type === 'month_2_inspection') return 'Extension 120 Day Inspection';
    if (task.task_type === 'day_30_inspection') return '120 Day Inspection';
    return '—';
}

function monitoringTaskPhase(task) {
    if (!task) return 'other';
    if (task.task_type === 'day_60_inspection' || task.task_type === 'month_1_inspection') return 'initial';
    if (task.task_type === 'day_30_inspection' || task.task_type === 'month_2_inspection') return 'final';
    return 'other';
}

function monitoringStaffDecisionLabels(task) {
    if (task && task.task_type === 'month_2_inspection') {
        return {
            normal_progress: 'Housing unit',
            no_progress: 'Failed',
        };
    }
    if (monitoringTaskPhase(task) === 'final') {
        return {
            normal_progress: 'Housing unit',
            no_progress: 'Explanation letter',
        };
    }
    return {
        normal_progress: 'Normal Progress',
        no_progress: 'No Progress',
    };
}

function monitoringStaffDecisionDisplayLabel(task, assessment) {
    if (!assessment) return '';
    const labels = monitoringStaffDecisionLabels(task);
    return labels[assessment] || assessment;
}

function monitoringBeneficiarySubjectPronoun(beneficiaryInfo) {
    const sex = (beneficiaryInfo && beneficiaryInfo.sex || '').trim().toUpperCase();
    if (sex === 'F') return 'she';
    if (sex === 'M') return 'he';
    return 'they';
}

function monitoringReportIsUnoccupied(report) {
    const occKey = String((report && report.occupancy_status_key) || '').toLowerCase();
    return occKey === 'unoccupied_abandoned' || occKey === 'temporarily_vacant';
}

/**
 * Caretaker report → recommended staff outcome: normal_progress | no_progress | null.
 * 90 Day: Normal Progress vs No Progress. Final / extension 120 Day: Housing unit vs Explanation letter or Failed.
 */
function monitoringRecommendedStaffDecision(task, report) {
    if (!task || !report || (report.progress_assessment || '').trim()) return null;
    const occKey = String(report.occupancy_status_key || '').toLowerCase();
    const conKey = String(report.construction_status_key || '').toLowerCase();
    const unoccupied = monitoringReportIsUnoccupied(report);

    if (task.task_type === 'day_30_inspection' || task.task_type === 'month_2_inspection') {
        if (occKey === 'properly_occupied' && conKey === 'completed_occupied') return 'normal_progress';
        if (unoccupied && conKey === 'no_structure') return 'no_progress';
        return null;
    }
    if (task.task_type === 'day_60_inspection') {
        if (occKey === 'properly_occupied' && conKey === 'ongoing_construction') return 'normal_progress';
        if (unoccupied && conKey === 'no_structure') return 'no_progress';
        return null;
    }
    return null;
}

function isMonitoringReportReadyForHousingUnit(task, report) {
    return task
        && (task.task_type === 'day_30_inspection' || task.task_type === 'month_2_inspection')
        && monitoringRecommendedStaffDecision(task, report) === 'normal_progress';
}

function isMonitoringReportReadyForExplanationLetter(task, report) {
    return task && task.task_type === 'day_30_inspection'
        && monitoringRecommendedStaffDecision(task, report) === 'no_progress';
}

function monitoringRecommendedDecisionHint(task, recommendation) {
    if (!task || !recommendation) return '';
    if (task.task_type === 'day_60_inspection') {
        if (recommendation === 'normal_progress') {
            return 'Caretaker reported Properly Occupied and Ongoing Construction — use Normal Progress.';
        }
        if (recommendation === 'no_progress') {
            return 'Caretaker reported Unoccupied and No Structure — use No Progress.';
        }
    }
    if (task.task_type === 'day_30_inspection') {
        if (recommendation === 'normal_progress') {
            return 'Caretaker reported Properly Occupied and Build finished — use Housing unit.';
        }
        if (recommendation === 'no_progress') {
            return 'Caretaker reported Unoccupied and Build not finished — use Explanation letter.';
        }
    }
    if (task.task_type === 'month_2_inspection') {
        if (recommendation === 'normal_progress') {
            return 'Caretaker reported Properly Occupied and Build finished — use Housing unit.';
        }
        if (recommendation === 'no_progress') {
            return 'Caretaker reported Unoccupied and Build not finished — use Failed.';
        }
    }
    return '';
}

function updateInspectionDecisionButtons(task) {
    const actions = document.getElementById('inspectionDecisionActions');
    if (!actions) return;
    const labels = monitoringStaffDecisionLabels(task);
    const normalBtn = actions.querySelector('.inspection-info-btn--normal-progress');
    const noBtn = actions.querySelector('.inspection-info-btn--no-progress');
    const report = (task && task.report) || {};
    const rec = monitoringRecommendedStaffDecision(task, report);
    if (normalBtn) {
        normalBtn.textContent = labels.normal_progress;
        normalBtn.classList.toggle('inspection-info-btn--housing-ready-pulse', rec === 'normal_progress');
        normalBtn.classList.remove('inspection-info-btn--explanation-letter-pulse');
        normalBtn.title = rec === 'normal_progress' ? monitoringRecommendedDecisionHint(task, 'normal_progress') : '';
    }
    if (noBtn) {
        noBtn.textContent = labels.no_progress;
        noBtn.classList.toggle('inspection-info-btn--explanation-letter-pulse', rec === 'no_progress');
        noBtn.classList.remove('inspection-info-btn--housing-ready-pulse');
        noBtn.title = rec === 'no_progress' ? monitoringRecommendedDecisionHint(task, 'no_progress') : '';
    }
}

function monitoringTaskRelativeLine(task) {
    if (!task) return '';
    if (task.task_type === 'month_1_inspection') {
        return '120-day extension — Extension 90 Day visit (90 days after extension start)';
    }
    if (task.task_type === 'month_2_inspection') {
        return '120-day extension — Extension 120 Day visit (120 days after extension start; not the original program 120 Day visit)';
    }
    if (task.monitoring_window_line) return task.monitoring_window_line;
    if (monitoringTaskPhase(task) === 'initial') return 'Initial monitoring — first 90 days';
    if (monitoringTaskPhase(task) === 'final') return 'Final monitoring — 120 days after 90 Day visit';
    const d = task.days_from_award;
    return (d != null && d !== '') ? `${d} days after monitoring starts` : '';
}

function monitoringEarlyScheduleHint(task) {
    if (task && task.task_type === 'month_1_inspection') {
        return 'Extension 90 Day visit — click to test early inspection schedule';
    }
    if (task && task.task_type === 'month_2_inspection') {
        return 'Extension window — 120 Day visit due — click to test early inspection schedule';
    }
    if (!task) return 'Click to test early inspection warning';
    if (monitoringTaskPhase(task) === 'initial') {
        return 'Initial monitoring visit — click to test early inspection schedule';
    }
    if (monitoringTaskPhase(task) === 'final') {
        return 'Final monitoring visit — click to test early inspection schedule';
    }
    return 'Click to test early inspection warning';
}

function isPriorNoProgressLetterVisit(task, letterWorkflowApplies) {
    if (!letterWorkflowApplies || !task) return false;
    if (task.task_type !== 'day_60_inspection' && task.task_type !== 'day_30_inspection') return false;
    return task.status === 'completed'
        && task.report
        && task.report.progress_assessment === 'no_progress';
}

function filterMainTasksForTopGrid(mainTasks, letterWorkflowApplies) {
    if (!letterWorkflowApplies) return mainTasks || [];
    return (mainTasks || []).filter((t) =>
        !isPriorNoProgressLetterVisit(t, true)
        && t.task_type !== 'month_1_inspection'
        && t.task_type !== 'month_2_inspection'
    );
}

function mergeMonitoringTasksForState(main, ext120) {
    const merged = [...(main || [])];
    if (ext120) merged.push(ext120);
    return merged;
}

function premiumCardChevronHtml() {
    return '<span class="premium-card-chevron" aria-hidden="true"><svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="6 9 12 15 18 9"/></svg></span>';
}

function buildMonitoringTaskCardElement(task, initialVisitReviewed) {
    const details = document.createElement('details');
    const borderTone = task.task_type === 'day_60_inspection' ? 'border-green' : 'border-amber';
    details.className = `premium-data-card premium-data-card--collapsible ${borderTone} monitoring-task-details`;
    details.open = false;

    const card = document.createElement('div');
    const isNotified = Boolean(task.notified_at);
    const isCompleted = task.status === 'completed';
    const isBlocked = (
        task.task_type === 'day_30_inspection' && !initialVisitReviewed
    );

    let statusClass = 'upcoming';
    if (isBlocked) statusClass = 'blocked';
    else if (isCompleted) statusClass = 'completed';
    else if (task.is_overdue) statusClass = 'overdue';
    else if (task.is_due) statusClass = 'ready';
    else if (isNotified) statusClass = 'notified';

    let completedTone = '';
    if (isCompleted && task.report) {
        if (task.report.progress_assessment === 'no_progress') {
            completedTone = ' completed--no-progress';
        } else if (task.report.progress_assessment === 'normal_progress') {
            completedTone = ' completed--normal-progress';
        } else {
            completedTone = ' completed--pending-review';
        }
    }
    card.className = `monitoring-task-card ${statusClass}${completedTone}`;

    const statusText = isBlocked ? 'Blocked' : (isCompleted ? 'Completed' : (task.is_overdue ? 'Overdue' : (task.is_due ? 'Ready' : (isNotified ? 'Notified' : 'Upcoming'))));
    let availabilityText;
    let hintClass = 'monitoring-task-hint';
    if (isBlocked) {
        availabilityText = 'Finish and review the 90 Day Inspection first';
        hintClass += ' monitoring-task-hint--blocked';
    } else if (isCompleted && task.report) {
        const by = task.report.assessed_by ? ` · ${task.report.assessed_by}` : '';
        if (task.report.progress_assessment === 'normal_progress') {
            const decisionLabel = monitoringStaffDecisionDisplayLabel(task, 'normal_progress');
            if (task.final_monitoring_program_complete) {
                availabilityText = `${decisionLabel} — final monitoring complete${by}`;
                hintClass += ' monitoring-task-hint--decision-normal monitoring-task-hint--program-complete';
            } else if (task.initial_monitoring_complete || monitoringTaskPhase(task) === 'initial') {
                availabilityText = `${decisionLabel} — initial monitoring recorded${by}`;
                hintClass += ' monitoring-task-hint--decision-normal';
            } else {
                availabilityText = `${decisionLabel}${by}`;
                hintClass += ' monitoring-task-hint--decision-normal';
            }
        } else if (task.report.progress_assessment === 'no_progress') {
            const decisionLabel = monitoringStaffDecisionDisplayLabel(task, 'no_progress');
            if (monitoringTaskPhase(task) === 'final') {
                availabilityText = task.task_type === 'month_2_inspection'
                    ? `${decisionLabel} — review blacklist beneficiary when eligible${by}`
                    : `${decisionLabel} — explanation letter workflow may apply${by}`;
            } else {
                availabilityText = `${decisionLabel}${by}`;
            }
            hintClass += ' monitoring-task-hint--decision-no';
        } else {
            availabilityText = 'Caretaker monitoring report submitted — staff decision pending';
            hintClass += ' monitoring-task-hint--pending-review';
        }
    } else {
        availabilityText = isCompleted
            ? 'Caretaker monitoring report submitted'
            : task.is_due
                ? (monitoringTaskPhase(task) === 'final'
                    ? 'Final monitoring — available to inspect now'
                    : (monitoringTaskPhase(task) === 'initial'
                        ? 'Initial monitoring — available to inspect now'
                        : 'Available to inspect now'))
                : (isNotified
                    ? 'Waiting for caretaker monitoring report'
                    : monitoringEarlyScheduleHint(task));
    }

    card.addEventListener('click', () => {
        if (isBlocked) {
            openInspectionBlockedModal(task);
            return;
        }
        if (isCompleted || (isNotified && !task.is_due)) {
            openInspectionInfoModal(task);
            return;
        }
        if (!task.is_due) {
            openInspectionConfirmModal(task);
            return;
        }
        notifySelectedInspectionTask(task.id);
    });

    card.innerHTML = `
        <p class="monitoring-task-relative">${monitoringTaskRelativeLine(task)}</p>
        <p class="monitoring-task-date">${formatDisplayDate(task.due_date)}</p>
        <div class="monitoring-task-status-row">
            <span class="monitoring-task-status-badge">${statusText}</span>
            <p class="${hintClass}">${availabilityText}</p>
        </div>
    `;

    const summary = document.createElement('summary');
    summary.className = 'premium-card-summary';
    summary.innerHTML = `<span class="premium-card-title">${monitoringTaskDisplayTitle(task)}</span>${premiumCardChevronHtml()}`;

    const body = document.createElement('div');
    body.className = 'premium-card-body monitoring-task-details-body';
    body.appendChild(card);

    details.appendChild(summary);
    details.appendChild(body);
    return details;
}

function renderMonitoringTaskCards(mainTasks, mergedForState, letterWorkflowApplies, unitContext) {
    const wrap = document.getElementById('monitoringTaskCards');
    if (!wrap) return;
    const unit = unitContext || lastOpenedUnitPayload;
    const merged = mergedForState != null ? mergedForState : (mainTasks || []);
    currentMonitoringTasks = merged;
    const gridTasks = filterMainTasksForTopGrid(mainTasks, letterWorkflowApplies);
    wrap.innerHTML = '';

    const initialVisitTask = merged.find((item) => item.task_type === 'day_60_inspection');
    const initialVisitReviewed = Boolean(
        initialVisitTask &&
        initialVisitTask.status === 'completed' &&
        initialVisitTask.report &&
        initialVisitTask.report.progress_assessment
    );

    if (!gridTasks.length) {
        const empty = document.createElement('div');
        empty.style.cssText = 'padding:0.8rem;border:1px dashed #cbd5e1;border-radius:0.75rem;color:#64748b;font-size:0.8rem;';
        const nestedInSeparateCard = letterWorkflowApplies && (merged || []).some((t) => isPriorNoProgressLetterVisit(t, true));
        const historicalMsg = unit && unit.historical_monitoring_message;
        empty.textContent = historicalMsg || (
            nestedInSeparateCard
                ? 'Completed visits that used the Explanation letter path are listed in the separate card below.'
                : 'No 90 Day or 120 Day monitoring tasks generated yet.'
        );
        wrap.appendChild(empty);
        return;
    }

    gridTasks.forEach((task) => {
        wrap.appendChild(buildMonitoringTaskCardElement(task, initialVisitReviewed));
    });
}

function renderPriorNoProgressVisitsPanel(letterWorkflowApplies) {
    const panel = document.getElementById('priorNoProgressVisitsPanel');
    const wrap = document.getElementById('priorNoProgressVisitsGrid');
    if (!panel || !wrap) return;
    wrap.innerHTML = '';
    if (!letterWorkflowApplies) {
        panel.style.display = 'none';
        return;
    }
    const merged = currentMonitoringTasks || [];
    const prior = merged
        .filter((t) => isPriorNoProgressLetterVisit(t, true))
        .sort((a, b) => String(a.due_date || '').localeCompare(String(b.due_date || '')));
    if (!prior.length) {
        panel.style.display = 'none';
        return;
    }
    const initialVisitTask = merged.find((item) => item.task_type === 'day_60_inspection');
    const initialVisitReviewed = Boolean(
        initialVisitTask &&
        initialVisitTask.status === 'completed' &&
        initialVisitTask.report &&
        initialVisitTask.report.progress_assessment
    );
    panel.style.display = 'block';
    prior.forEach((task) => {
        wrap.appendChild(buildMonitoringTaskCardElement(task, initialVisitReviewed));
    });
}

function renderExplanationExtensionTaskCards(ext120) {
    const wrap = document.getElementById('explanationExtension30DayCardWrap');
    if (!wrap) return;
    wrap.innerHTML = '';
    if (!ext120 || ext120.task_type !== 'month_2_inspection') {
        wrap.style.display = 'none';
        return;
    }
    const initialVisitTask = (currentMonitoringTasks || []).find((item) => item.task_type === 'day_60_inspection');
    const initialVisitReviewed = Boolean(
        initialVisitTask &&
        initialVisitTask.status === 'completed' &&
        initialVisitTask.report &&
        initialVisitTask.report.progress_assessment
    );
    wrap.style.display = 'grid';
    wrap.appendChild(buildMonitoringTaskCardElement(ext120, initialVisitReviewed));
}

function openInspectionConfirmModal(task) {
    const modal = document.getElementById('inspectionConfirmModal');
    const text = document.getElementById('inspectionConfirmText');
    if (!modal || !text) return;

    pendingInspectionTask = task;
    const due = formatDisplayDate(task.due_date);
    const relative = monitoringTaskRelativeLine(task);
    let scheduleText;
    if (task.task_type === 'month_2_inspection') {
        const unit = lastOpenedUnitPayload;
        const ext = unit && unit.explanation_build_extension;
        const ms = task.monitoring_starts_on
            ? formatDisplayDate(String(task.monitoring_starts_on).slice(0, 10))
            : null;
        const extStaffChoice = (
            ' Staff choose Housing unit if the lot build is finished, or Failed if not '
            + '(Failed supports Blacklist beneficiary when office rules allow).'
        );
        if (ext && ext.start_date && ext.end_date) {
            const fromD = formatDisplayDate(String(ext.start_date).slice(0, 10));
            const until = formatDisplayDate(String(ext.end_date).slice(0, 10));
            scheduleText = (
                'This is the Extension 120 Day inspection after the written explanation letter was placed on file. '
                + `Another 120-day build extension applies from ${fromD} through ${until}.`
                + (ms
                    ? ` Extension monitoring is counted from ${ms}, then ${relative} — inspection due ${due}.${extStaffChoice} Continue?`
                    : ` Then ${relative} — inspection due ${due}.${extStaffChoice} Continue?`)
            );
        } else {
            scheduleText = (
                'This is the Extension 120 Day inspection after the written explanation letter was placed on file. '
                + (ms
                    ? `Extension monitoring is counted from ${ms}, then ${relative} — inspection due ${due}.${extStaffChoice} Continue?`
                    : `Schedule: ${relative} — inspection due ${due}.${extStaffChoice} Continue?`)
            );
        }
    } else if (task.task_type === 'day_60_inspection') {
        const awardDate = task.award_date ? formatDisplayDate(task.award_date) : 'award date';
        scheduleText = (
            `Initial monitoring: award ${awardDate} + 30-day grace, then ${relative} — due ${due}. `
            + 'This is the first monitoring visit. Continue?'
        );
    } else if (task.task_type === 'day_30_inspection') {
        const awardDate = task.award_date ? formatDisplayDate(task.award_date) : 'award date';
        scheduleText = (
            `Final monitoring: award ${awardDate} + 30-day grace, then ${relative} — due ${due}. `
            + 'Staff will confirm whether the lot build is finished (Housing unit closes monitoring) or record Explanation letter to open that workflow. Continue?'
        );
    } else {
        const awardDate = task.award_date ? formatDisplayDate(task.award_date) : 'award date';
        scheduleText = `The inspection schedule is: Award date ${awardDate} + 30-day grace, then ${relative} — due ${due}. Continue?`;
    }
    text.textContent = scheduleText;
    modal.style.display = 'flex';
}

function closeInspectionConfirmModal(e) {
    if (e && e.target.id !== 'inspectionConfirmModal') return;
    const modal = document.getElementById('inspectionConfirmModal');
    if (modal) modal.style.display = 'none';
    pendingInspectionTask = null;
}

function continueInspectionWarning() {
    if (!pendingInspectionTask) return;
    const task = pendingInspectionTask;
    const modal = document.getElementById('inspectionConfirmModal');
    if (modal) modal.style.display = 'none';
    pendingInspectionTask = null;
    openInspectionInfoModal(task);
}

function openInspectionBlockedModal(task) {
    const modal = document.getElementById('inspectionInfoModal');
    const title = document.getElementById('inspectionInfoTitle');
    const text = document.getElementById('inspectionInfoText');
    const banner = document.getElementById('inspectionInfoBanner');
    const summary = document.getElementById('inspectionReportSummary');
    const decisionActions = document.getElementById('inspectionDecisionActions');
    const dashboardBtn = document.getElementById('inspectionDashboardBtn');
    const actions = modal ? modal.querySelector('.inspection-info-actions') : null;
    const body = modal ? modal.querySelector('.inspection-info-body') : null;
    const card = modal ? modal.querySelector('.inspection-info-card') : null;
    if (!modal || !title || !text) return;

    if (card) {
        card.classList.remove('inspection-info-card--large');
        card.classList.add('inspection-info-card--alert');
        card.classList.remove('inspection-info-card--centered');
    }
    if (body) body.classList.remove('centered');
    if (actions) actions.classList.remove('centered');
    if (banner) banner.style.display = 'none';

    activeInspectionTask = null;
    title.textContent = `${monitoringTaskDisplayTitle(task)} is blocked`;
    text.textContent = '120 Day Inspection cannot be opened yet. Complete the 90 Day Inspection caretaker report first, then staff must mark the 90 Day Inspection result as Normal Progress or No Progress.';
    if (summary) {
        summary.classList.remove('active');
        summary.innerHTML = '';
    }
    if (decisionActions) {
        decisionActions.classList.remove('active');
    }
    if (dashboardBtn) {
        dashboardBtn.style.display = 'none';
    }
    modal.style.display = 'flex';
}

function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function formatDisplayDate(value) {
    if (!value) return '—';
    const raw = String(value).slice(0, 10);
    const parts = raw.split('-').map(Number);
    if (parts.length !== 3 || parts.some(Number.isNaN)) return raw;
    return new Date(parts[0], parts[1] - 1, parts[2]).toLocaleDateString('en-US', {
        month: 'long',
        day: 'numeric',
        year: 'numeric',
    });
}

function buildHouseholdAddRelationshipSelect(relOpts) {
    const opts = Array.isArray(relOpts) ? relOpts : [];
    const inner = ['<option value="">— Select —</option>']
        .concat(opts.map((o) => `<option value="${escapeHtml(o.value)}">${escapeHtml(o.label)}</option>`))
        .join('');
    return `<select id="hhAddRelationship" class="household-add-select">${inner}</select>`;
}

function buildHouseholdAddPanel(relOpts) {
    return `
    <div class="household-add-panel" role="region" aria-label="Add household member">
        <p class="household-add-title">Add household member</p>
        <div class="household-add-form">
            <div class="household-add-field">
                <label class="household-add-label" for="hhAddFullName">Full name</label>
                <input type="text" id="hhAddFullName" class="household-add-input" maxlength="30" placeholder="" autocomplete="name">
            </div>
            <div class="household-add-field">
                <label class="household-add-label" for="hhAddRelationship">Relationship to beneficiary</label>
                ${buildHouseholdAddRelationshipSelect(relOpts)}
            </div>
            <div class="household-add-field">
                <span class="household-add-label" id="hhAddSexLegend">Sex</span>
                <div class="household-add-radios" role="radiogroup" aria-labelledby="hhAddSexLegend">
                    <label class="household-add-radio"><input type="radio" name="hhAddSex" value="M"> Male</label>
                    <label class="household-add-radio"><input type="radio" name="hhAddSex" value="F"> Female</label>
                </div>
            </div>
            <div class="household-add-inline-row">
                <div class="household-add-field household-add-field--age">
                    <label class="household-add-label" for="hhAddAge">Age</label>
                    <input type="number" id="hhAddAge" class="household-add-input household-add-age-input" min="0" max="120" placeholder="">
                </div>
                <div class="household-add-actions--inline">
                    <button type="button" class="household-add-btn" onclick="submitAddHouseholdMember(event)">Add member</button>
                </div>
            </div>
        </div>
    </div>`;
}

function renderHouseholdMembersRecord(members, meta) {
    const wrap = document.getElementById('householdMembersRecord');
    if (!wrap) return;
    const canAdd = meta && meta.can_add_household_members;
    const relOpts = (meta && meta.relationship_options) ? meta.relationship_options : [];
    const addPanel = canAdd ? buildHouseholdAddPanel(relOpts) : '';

    if (!Array.isArray(members) || !members.length) {
        wrap.innerHTML = `
            <p class="occupied-record-empty">No household member rows recorded.</p>
            ${addPanel}
        `;
        return;
    }
    wrap.innerHTML = `
        <div class="premium-table-wrap">
            <table class="premium-table">
                <thead><tr><th>Name</th><th>Relationship</th><th>Sex</th><th>Age</th></tr></thead>
                <tbody>
                    ${members.map((member) => {
                        const ageRaw = member.age;
                        let ageDisp = '—';
                        if (ageRaw != null && ageRaw !== '') {
                            const n = Number(ageRaw);
                            if (Number.isFinite(n)) ageDisp = String(n);
                        }
                        return `
                        <tr>
                            <td style="font-weight: 700;">${escapeHtml(member.name || '—')}</td>
                            <td style="color: #64748b;">${escapeHtml(member.relationship || '—')}</td>
                            <td style="color: #64748b;">${escapeHtml(member.sex_display || '—')}</td>
                            <td style="color: #64748b;">${escapeHtml(ageDisp)}</td>
                        </tr>`;
                    }).join('')}
                </tbody>
            </table>
        </div>
        ${addPanel}
    `;
}

async function submitAddHouseholdMember(event) {
    if (event) event.preventDefault();
    if (!currentUnitId) return;
    const name = (document.getElementById('hhAddFullName') && document.getElementById('hhAddFullName').value || '').trim();
    const relationship = (document.getElementById('hhAddRelationship') && document.getElementById('hhAddRelationship').value || '').trim();
    const sexRadio = document.querySelector('input[name="hhAddSex"]:checked');
    const sex = sexRadio ? String(sexRadio.value || '').trim() : '';
    const ageVal = document.getElementById('hhAddAge') ? document.getElementById('hhAddAge').value : '';
    const position = '{{ request.user.position }}';
    if (!name) {
        monitoringFlowAlert('Enter the household member’s full name.', 'Reminder', 'default', null);
        return;
    }
    if (!relationship) {
        monitoringFlowAlert('Select relationship to the beneficiary.', 'Reminder', 'default', null);
        return;
    }
    const body = { full_name: name, relationship: relationship, sex: sex, age: ageVal };
    try {
        const res = await fetch(`/units/housing-units/${position}/${currentUnitId}/household-member/add/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken') || '',
                'X-Requested-With': 'XMLHttpRequest',
            },
            body: JSON.stringify(body),
        });
        const data = await res.json();
        if (!res.ok || !data.success) {
            throw new Error(data.error || 'Could not add household member.');
        }
        openUnitModal(currentUnitId);
    } catch (e) {
        monitoringFlowAlert(e.message || 'Could not add household member.', 'Could not add member', 'default', null);
    }
}

function renderMonitoringHistoryRecord(history, unitContext) {
    const wrap = document.getElementById('monitoringHistoryRecord');
    if (!wrap) return;
    const unit = unitContext || lastOpenedUnitPayload;
    if (!Array.isArray(history) || !history.length) {
        const historicalMsg = unit && unit.historical_monitoring_message;
        wrap.innerHTML = `<p class="occupied-record-empty">${escapeHtml(
            historicalMsg || 'No 90 Day / 120 Day monitoring history yet.'
        )}</p>`;
        return;
    }
    wrap.innerHTML = `
        <div class="premium-table-wrap">
            <table class="premium-table">
                <thead><tr><th>Date</th><th>Result</th><th>Decision</th></tr></thead>
                <tbody>
                    ${history.map((item) => {
                        let cssClass = '';
                        const decisionText = (item.decision || '').toLowerCase();
                        const resultText = (item.result || '').toLowerCase();
                        
                        if (item.progress_assessment === 'normal_progress' || 
                            decisionText.includes('normal progress') ||
                            decisionText.includes('approved') || 
                            decisionText.includes('granted') ||
                            resultText.includes('approved')) {
                            cssClass = ' monitoring-history-decision--normal';
                        } else if (item.progress_assessment === 'no_progress' || 
                                   decisionText.includes('no progress') ||
                                   decisionText.includes('explanation letter') || 
                                   decisionText.includes('failed') || 
                                   decisionText.includes('disqualified') ||
                                   decisionText.includes('eviction') ||
                                   resultText.includes('failed') ||
                                   resultText.includes('no structure')) {
                            cssClass = ' monitoring-history-decision--no';
                        }
                        
                        return `
                        <tr>
                            <td>
                                <div style="font-weight: 700;">${escapeHtml(item.label || '—')}</div>
                                <div style="font-size: 0.65rem; color: #64748b; margin-top: 0.2rem;">${formatDisplayDate(item.date)}</div>
                            </td>
                            <td>
                                <span style="display: inline-block; padding: 0.2rem 0.6rem; background: #f1f5f9; border-radius: 6px; font-weight: 700; font-size: 0.72rem;">
                                    ${escapeHtml(item.result || '—')}
                                </span>
                            </td>
                            <td>
                                <span class="monitoring-history-decision${cssClass}">${escapeHtml(item.decision || '—')}</span>
                            </td>
                        </tr>
                        `;
                    }).join('')}
                </tbody>
            </table>
        </div>
    `;
}

function buildMonitoringHistoryFromTasks(tasks) {
    if (!Array.isArray(tasks) || !tasks.length) return [];
    return tasks.map((task) => {
        const report = task.report || null;
        let result = task.status_label || task.status || '—';
        if (report && report.construction_status) {
            result = report.construction_status;
        } else if (task.status === 'completed' && report && !report.construction_status) {
            result = 'Report submitted';
        }
        const decision = (report && report.progress_assessment_label)
            ? report.progress_assessment_label
            : '—';
        const label = monitoringTaskDisplayTitle(task).replace(/\s*Inspection\s*$/i, '').trim() || '—';
        return {
            label,
            date: task.due_date,
            result: result || '—',
            decision: decision || '—',
            progress_assessment: (report && report.progress_assessment) ? report.progress_assessment : '',
        };
    });
}

function renderUnitCaseRecord(unit) {
    const wrap = document.getElementById('unitCaseRecord');
    if (!wrap) return;
    currentUnitDetail = unit || null;
    const cases = unit && Array.isArray(unit.module5_cases) ? unit.module5_cases : [];
    const recordUrl = module5RecordCaseUrl(unit);
    const listUrl = module5CasesListUrl(unit);
    const ben = unit && unit.beneficiary_info;

    if (!cases.length) {
        let html = '<p class="occupied-record-empty">No case linked to this lot yet.</p>';
        if (recordUrl && ben && ben.applicant_id) {
            html += `
                <div class="unit-case-record-footer">
                    <a href="${escapeHtml(recordUrl)}" class="unit-case-record-link btn-case-record">Record case for this beneficiary</a>
                    <a href="${escapeHtml(listUrl)}" class="unit-case-record-link btn-case-all">All cases</a>
                </div>
            `;
        } else if (!ben || !ben.applicant_id) {
            html += '<p class="occupied-record-empty" style="margin-top: 0.5rem;">Link a formal lot award beneficiary to record a case.</p>';
        }
        wrap.innerHTML = html;
        return;
    }

    const caseRows = cases.map((c) => {
        const openUrl = (c.view_url && c.view_url !== '#') ? c.view_url : module5CaseOpenUrl(c.id);
        return `
                <article class="unit-case-record-item">
                    <a href="${escapeHtml(openUrl)}" class="unit-case-record-case-link">${escapeHtml(c.case_number || 'Case')}</a>
                    <span class="unit-case-record-meta">${escapeHtml(c.case_type_display || '')} · ${escapeHtml(c.status_display || '')}</span>
                    <span class="unit-case-record-meta">Complainant: ${escapeHtml(c.complainant_name || '—')}</span>
                    ${c.initial_description ? `<span class="unit-case-record-meta">${escapeHtml(c.initial_description)}</span>` : ''}
                    <div class="unit-case-record-actions">
                        <a href="${escapeHtml(openUrl)}" class="unit-case-record-link btn-case-open">Open case record</a>
                    </div>
                </article>
            `;
    }).join('');

    const footerLinks = `
        <div class="unit-case-record-footer">
            ${recordUrl ? `<a href="${escapeHtml(recordUrl)}" class="unit-case-record-link btn-case-record">Record another case</a>` : ''}
            <a href="${escapeHtml(listUrl)}" class="unit-case-record-link btn-case-all">All cases</a>
        </div>
    `;

    wrap.innerHTML = `<div class="unit-case-record-list">${caseRows}</div>${footerLinks}`;
}

function renderComplianceRecordsRecord(records) {
    const wrap = document.getElementById('complianceRecordsRecord');
    if (!wrap) return;
    const card = wrap.closest('.premium-data-card');
    if (!Array.isArray(records) || !records.length) {
        wrap.innerHTML = '';
        if (card) card.style.display = 'none';
        return;
    }
    if (card) card.style.display = '';
    wrap.innerHTML = `
        <div class="compliance-record-list">
            ${records.map((record) => `
                <div class="compliance-record-item">
                    <strong>${escapeHtml(record.title || 'Compliance record')}</strong>
                    <span>${escapeHtml(record.status || 'Recorded')}</span>
                    <span>${escapeHtml(record.detail || '')}</span>
                </div>
            `).join('')}
        </div>
    `;
}


function monitoringMirrorOccupancyOptions(task) {
    if (monitoringTaskPhase(task) === 'final') {
        return {
            positive: {
                title: 'Properly Occupied',
                sub: 'Beneficiary or immediate family is residing in the unit at this final visit.',
            },
            negative: {
                title: 'Unoccupied',
                sub: 'Unit is vacant, abandoned, or occupied by unauthorized persons at this final visit.',
            },
        };
    }
    return {
        positive: {
            title: 'Properly Occupied',
            sub: 'Beneficiary or immediate family is residing in the unit.',
        },
        negative: {
            title: 'Unoccupied',
            sub: 'Unit is abandoned, temporarily vacant, or occupied by unauthorized persons.',
        },
    };
}

function monitoringMirrorConstructionOptions(task) {
    if (monitoringTaskPhase(task) === 'final') {
        return {
            positive: {
                title: 'Build finished',
                sub: 'Structure is substantially complete — the lot build is ready to count as a finished housing unit.',
            },
            negative: {
                title: 'Build not finished',
                sub: 'No finished structure on site, or construction is clearly incomplete at this final visit.',
            },
        };
    }
    return {
        positive: {
            title: 'Ongoing Construction',
            sub: 'Active building, structural improvements, or materials present on site.',
        },
        negative: {
            title: 'No Structure',
            sub: 'No signs of construction; lot remains vacant or untouched.',
        },
    };
}

function resolveOccupancySelection(report) {
    const key = String(report.occupancy_status_key || '').toLowerCase();
    if (key === 'properly_occupied') return 'positive';
    if (key === 'unoccupied_abandoned' || key === 'temporarily_vacant') return 'negative';
    const label = String(report.occupancy_status || '').toLowerCase();
    if (label.includes('unoccupied') || label.includes('abandon') || label.includes('vacant')) return 'negative';
    return 'positive';
}

function resolveConstructionSelection(report) {
    const key = String(report.construction_status_key || '').toLowerCase();
    if (key === 'no_structure') return 'negative';
    if (key === 'completed_occupied' || key === 'ongoing_construction') return 'positive';
    const label = String(report.construction_status || '').toLowerCase();
    if (label.includes('no structure') || label.includes('not finished')) return 'negative';
    if (label.includes('finished') || label.includes('complete')) return 'positive';
    return 'positive';
}

function renderInspectionDecisionCard(tone, title, sub, isSelected) {
    const state = isSelected ? ' is-selected' : ' is-muted';
    return `<div class="monitoring-decision-label ${tone}${state}">
        <strong class="monitoring-decision-title">${escapeHtml(title)}</strong>
        <p class="monitoring-decision-sub">${escapeHtml(sub)}</p>
    </div>`;
}

function stripMonitoringReportBoilerplate(text) {
    if (!text) return text;
    return String(text)
        .replace(/\s*\(no separate occupancy narrative submitted\)\.?/gi, '.')
        .replace(/\s*\(no separate construction progress narrative submitted\)\.?/gi, '.')
        .trim();
}

function renderCompletedReportSummary(task) {
    const report = task.report || {};
    const photos = Array.isArray(report.photo_urls) ? report.photo_urls : (report.photo_url ? [report.photo_url] : []);
    inspectionCarouselIndex = 0;
    const photoCarousel = photos.length
        ? `
            <div class="inspection-summary-item full-width">
                <span class="inspection-summary-label">Photo evidence</span>
                <div class="inspection-photo-carousel" data-photo-count="${photos.length}">
                    ${photos.map((url, index) => `
                        <div class="inspection-photo-slide ${index === 0 ? 'active' : ''}" data-photo-index="${index}">
                            <img src="${escapeHtml(url)}" alt="Monitoring photo evidence ${index + 1}">
                        </div>
                    `).join('')}
                    <div class="inspection-photo-controls">
                        <button type="button" class="inspection-photo-control" onclick="event.stopPropagation(); moveInspectionPhoto(-1)" ${photos.length <= 1 ? 'disabled' : ''}>Previous</button>
                        <span id="inspectionPhotoCounter">1 of ${photos.length}</span>
                        <button type="button" class="inspection-photo-control" onclick="event.stopPropagation(); moveInspectionPhoto(1)" ${photos.length <= 1 ? 'disabled' : ''}>Next</button>
                    </div>
                </div>
            </div>
        `
        : '';
    const decisionTone = report.progress_assessment === 'no_progress'
        ? 'decision--no_progress'
        : report.progress_assessment === 'normal_progress'
        ? 'decision--normal_progress'
        : '';
    const staffDecisionLabel = monitoringStaffDecisionDisplayLabel(task, report.progress_assessment)
        || report.progress_assessment_label;
    const decision = staffDecisionLabel
        ? `<div class="inspection-summary-item full-width decision ${decisionTone}"><span class="inspection-summary-label">Staff decision</span><p class="inspection-summary-value">${escapeHtml(staffDecisionLabel)}${report.assessed_by ? ` · ${escapeHtml(report.assessed_by)}` : ''}</p></div>`
        : '';

    const occupancyPick = resolveOccupancySelection(report);
    const constructionPick = resolveConstructionSelection(report);
    const occupancyOpts = monitoringMirrorOccupancyOptions(task);
    const constructionOpts = monitoringMirrorConstructionOptions(task);
    const constructionHeading = monitoringTaskPhase(task) === 'final' ? 'Lot build status (final)' : 'Construction status';

    return `
        <div class="inspection-summary-grid">
            <div class="inspection-report-mirror">
                <div class="inspection-report-mirror-col">
                    <p class="inspection-report-mirror-heading">
                        <span>Occupancy classification</span>
                        <span class="inspection-report-mirror-required">Required</span>
                    </p>
                    <div class="monitoring-decision-grid">
                        ${renderInspectionDecisionCard(
                            'positive',
                            occupancyOpts.positive.title,
                            occupancyOpts.positive.sub,
                            occupancyPick === 'positive'
                        )}
                        ${renderInspectionDecisionCard(
                            'negative',
                            occupancyOpts.negative.title,
                            occupancyOpts.negative.sub,
                            occupancyPick === 'negative'
                        )}
                    </div>
                </div>
                <div class="inspection-report-mirror-col">
                    <p class="inspection-report-mirror-heading">
                        <span>${constructionHeading}</span>
                        <span class="inspection-report-mirror-required">Required</span>
                    </p>
                    <div class="monitoring-decision-grid">
                        ${renderInspectionDecisionCard(
                            'positive',
                            constructionOpts.positive.title,
                            constructionOpts.positive.sub,
                            constructionPick === 'positive'
                        )}
                        ${renderInspectionDecisionCard(
                            'negative',
                            constructionOpts.negative.title,
                            constructionOpts.negative.sub,
                            constructionPick === 'negative'
                        )}
                    </div>
                </div>
            </div>
            ${photoCarousel}
            ${decision}
        </div>
    `;
}

function moveInspectionPhoto(delta) {
    const carousel = document.querySelector('.inspection-photo-carousel');
    if (!carousel) return;
    const slides = [...carousel.querySelectorAll('.inspection-photo-slide')];
    if (!slides.length) return;
    inspectionCarouselIndex = (inspectionCarouselIndex + delta + slides.length) % slides.length;
    slides.forEach((slide, index) => {
        slide.classList.toggle('active', index === inspectionCarouselIndex);
    });
    const counter = document.getElementById('inspectionPhotoCounter');
    if (counter) counter.textContent = `${inspectionCarouselIndex + 1} of ${slides.length}`;
}

function openInspectionInfoModal(task) {
    const modal = document.getElementById('inspectionInfoModal');
    const title = document.getElementById('inspectionInfoTitle');
    const text = document.getElementById('inspectionInfoText');
    const banner = document.getElementById('inspectionInfoBanner');
    const dashboardBtn = document.getElementById('inspectionDashboardBtn');
    const summary = document.getElementById('inspectionReportSummary');
    const decisionActions = document.getElementById('inspectionDecisionActions');
    const actions = modal ? modal.querySelector('.inspection-info-actions') : null;
    const body = modal ? modal.querySelector('.inspection-info-body') : null;
    const card = modal ? modal.querySelector('.inspection-info-card') : null;
    if (!modal || !title || !text) return;

    const isCompleted = task.status === 'completed';
    const isInformational = !isCompleted;
    const hasDecision = Boolean(task.report && task.report.progress_assessment_label);
    const isReviewPending = isCompleted && !hasDecision;

    if (card) {
        card.classList.remove('inspection-info-card--alert');
        card.classList.toggle('inspection-info-card--large', isCompleted);
        card.classList.toggle('inspection-info-card--centered', isInformational || isCompleted);
    }

    activeInspectionTask = task;
    if (summary) {
        summary.classList.remove('active');
        summary.innerHTML = '';
    }
    if (decisionActions) {
        decisionActions.classList.remove('active');
    }
    if (banner) {
        banner.style.display = 'block';
        if (!isCompleted || hasDecision) {
            banner.classList.remove('inspection-info-banner--housing-ready');
            banner.classList.remove('inspection-info-banner--explanation-letter');
        }
    }

    if (body) body.classList.toggle('centered', isInformational || isCompleted);
    if (actions) {
        actions.classList.toggle('centered', isInformational || isReviewPending);
        actions.classList.toggle('inspection-info-actions--review', isReviewPending);
    }

    if (isCompleted) {
        title.textContent = `${monitoringTaskDisplayTitle(task)} is completed`;
        const reportForReady = task.report || {};
        const staffRec = isReviewPending ? monitoringRecommendedStaffDecision(task, reportForReady) : null;
        const recommendNormal = staffRec === 'normal_progress';
        const recommendNoProgress = staffRec === 'no_progress';
        if (banner) {
            banner.classList.toggle('inspection-info-banner--housing-ready', recommendNormal);
            banner.classList.toggle('inspection-info-banner--explanation-letter', recommendNoProgress);
        }
        if (hasDecision) {
            text.textContent = 'Caretaker monitoring report has been reviewed. The saved staff decision is shown in the summary below.';
        } else if (recommendNormal && task.task_type === 'day_30_inspection') {
            text.textContent = (
                'This beneficiary is ready for housing unit. '
                + 'The caretaker reported Properly Occupied and Build finished. '
                + 'Choose Housing unit to record the completed lot and close monitoring. '
                + 'Explanation letter does not apply for this visit.'
            );
        } else if (recommendNoProgress && task.task_type === 'day_30_inspection') {
            text.textContent = (
                'Explanation letter applies for this beneficiary. '
                + 'The caretaker reported Unoccupied and Build not finished. '
                + 'Choose Explanation letter to open that workflow. '
                + 'Housing unit does not apply for this visit.'
            );
        } else if (recommendNormal && task.task_type === 'month_2_inspection') {
            text.textContent = (
                'This beneficiary is ready for housing unit. '
                + 'The caretaker reported Properly Occupied and Build finished on the extension final visit. '
                + 'Choose Housing unit to record the completed lot and close monitoring. '
                + 'Failed does not apply for this visit.'
            );
        } else if (recommendNoProgress && task.task_type === 'month_2_inspection') {
            text.textContent = (
                'Failed applies for this extension final visit. '
                + 'The caretaker reported Unoccupied and Build not finished. '
                + 'Choose Failed when the lot does not pass—Failed leads toward Blacklist beneficiary when office rules allow. '
                + 'Housing unit does not apply for this visit.'
            );
        } else if (recommendNormal && task.task_type === 'day_60_inspection') {
            const labels = monitoringStaffDecisionLabels(task);
            text.textContent = (
                'Initial monitoring supports ' + labels.normal_progress + '. '
                + 'The caretaker reported Properly Occupied and Ongoing Construction. '
                + 'Choose ' + labels.normal_progress + ' to record initial monitoring. '
                + labels.no_progress + ' does not match this visit.'
            );
        } else if (recommendNoProgress && task.task_type === 'day_60_inspection') {
            const labels = monitoringStaffDecisionLabels(task);
            text.textContent = (
                'Initial monitoring supports ' + labels.no_progress + '. '
                + 'The caretaker reported Unoccupied and No Structure. '
                + 'Choose ' + labels.no_progress + ' for this visit. '
                + labels.normal_progress + ' does not match this visit.'
            );
        } else if (monitoringTaskPhase(task) === 'final') {
            text.textContent = task.task_type === 'month_2_inspection'
                ? 'Caretaker monitoring report was submitted for the Extension 120 Day visit. Review the summary, then choose Housing unit if the lot build is finished, or Failed if it does not pass—Failed leads to Blacklist beneficiary when the case is eligible.'
                : 'Caretaker monitoring report has been submitted. Review the summary, then choose Housing unit if the lot build is finished, or Explanation letter to open that workflow.';
        } else {
            text.textContent = 'Caretaker monitoring report has been submitted. Review the summary, then mark the result as Normal Progress or No Progress.';
        }
        if (summary) {
            summary.innerHTML = renderCompletedReportSummary(task);
            summary.classList.add('active');
        }
        if (decisionActions && isReviewPending) {
            decisionActions.classList.add('active');
            updateInspectionDecisionButtons(task);
        }
    } else if (task.notified_at) {
        title.textContent = `${monitoringTaskDisplayTitle(task)} is waiting for caretaker`;
        text.textContent = `This task was already notified to Monitoring Dashboard. It remains scheduled for ${formatDisplayDate(task.due_date)} and is waiting for the caretaker field report.`;
    } else {
        title.textContent = 'Inspection details';
        if (task.task_type === 'month_2_inspection') {
            const unit = lastOpenedUnitPayload;
            const ext = unit && unit.explanation_build_extension;
            const extLine = (ext && ext.start_date && ext.end_date)
                ? (
                    ` The 120-day build extension runs from ${formatDisplayDate(String(ext.start_date).slice(0, 10))} `
                    + `through ${formatDisplayDate(String(ext.end_date).slice(0, 10))}.`
                )
                : '';
            text.textContent = (
                `Extension 120 Day inspection opens on ${formatDisplayDate(task.due_date)} (${monitoringTaskRelativeLine(task)}).`
                + extLine
                + ' Staff record Housing unit when the build is complete, or Failed when this extension visit does not pass—Failed leads toward Blacklist beneficiary when office rules allow. Use Monitoring Dashboard to test an early schedule if needed.'
            );
        } else if (task.task_type === 'day_30_inspection') {
            text.textContent = (
                `Final monitoring opens on ${formatDisplayDate(task.due_date)} (${monitoringTaskRelativeLine(task)}). `
                + 'Use this visit to confirm the lot build is finished. Housing unit records the lot and closes monitoring; Explanation letter opens that workflow.'
            );
        } else if (task.task_type === 'day_60_inspection') {
            text.textContent = (
                `Initial monitoring opens on ${formatDisplayDate(task.due_date)} (${monitoringTaskRelativeLine(task)}). `
                + 'Use Monitoring Dashboard if you want to proceed early for testing.'
            );
        } else {
            text.textContent = `Inspection opens on ${formatDisplayDate(task.due_date)} (${monitoringTaskRelativeLine(task)}). Use Monitoring Dashboard if you want to proceed early for testing.`;
        }
    }
    
    if (dashboardBtn) {
        const hideDashboardButton = task.status === 'completed' || Boolean(task.report && task.report.progress_assessment_label);
        dashboardBtn.style.display = hideDashboardButton ? 'none' : '';
        dashboardBtn.disabled = Boolean(task.notified_at) || task.status === 'completed';
        dashboardBtn.textContent = task.status === 'completed'
            ? 'Report submitted'
            : (task.notified_at ? 'Already notified' : 'Notify Monitoring Dashboard');
    }
    modal.style.display = 'flex';
}

function alertMonitoringStaffDecisionMismatch(task, attemptedDecision, recommendedDecision) {
    const ben = lastOpenedUnitPayload && lastOpenedUnitPayload.beneficiary_info;
    const pronoun = monitoringBeneficiarySubjectPronoun(ben);
    const labels = monitoringStaffDecisionLabels(task);
    const attemptedLabel = labels[attemptedDecision] || attemptedDecision;
    const recommendedLabel = labels[recommendedDecision] || recommendedDecision;
    let title = 'Use ' + recommendedLabel;
    let body = '';

    if (task.task_type === 'day_30_inspection' && recommendedDecision === 'normal_progress') {
        title = 'Ready for housing unit';
        body = (
            'You cannot open an explanation letter for this beneficiary because '
            + pronoun
            + ' is ready for housing unit. Choose Housing unit to record the completed lot and close monitoring.'
        );
    } else if (task.task_type === 'day_30_inspection' && recommendedDecision === 'no_progress') {
        title = 'Use Explanation letter';
        body = (
            'You cannot record Housing unit for this beneficiary because '
            + pronoun
            + ' requires the Explanation letter workflow (Unoccupied and Build not finished on the final visit). '
            + 'Choose Explanation letter to continue.'
        );
    } else if (task.task_type === 'month_2_inspection' && recommendedDecision === 'normal_progress') {
        title = 'Ready for housing unit';
        body = (
            'You cannot record Failed for this beneficiary because '
            + pronoun
            + ' is ready for housing unit on the extension final visit. '
            + 'Choose Housing unit to record the completed lot and close monitoring.'
        );
    } else if (task.task_type === 'month_2_inspection' && recommendedDecision === 'no_progress') {
        title = 'Use Failed';
        body = (
            'You cannot record Housing unit for this beneficiary because '
            + pronoun
            + ' did not pass the extension final visit (Unoccupied and Build not finished). '
            + 'Choose Failed to continue—Failed leads toward Blacklist beneficiary when office rules allow.'
        );
    } else if (task.task_type === 'day_60_inspection' && recommendedDecision === 'normal_progress') {
        title = 'Use ' + recommendedLabel;
        body = (
            'You cannot record ' + attemptedLabel + ' for this beneficiary because '
            + pronoun
            + ' should be marked as ' + recommendedLabel
            + ' (Properly Occupied and Ongoing Construction on the initial visit). Choose '
            + recommendedLabel + ' instead.'
        );
    } else if (task.task_type === 'day_60_inspection' && recommendedDecision === 'no_progress') {
        title = 'Use ' + recommendedLabel;
        body = (
            'You cannot record ' + attemptedLabel + ' for this beneficiary because '
            + pronoun
            + ' should be marked as ' + recommendedLabel
            + ' (Unoccupied and No Structure on the initial visit). Choose '
            + recommendedLabel + ' instead.'
        );
    } else {
        body = (
            'You cannot record ' + attemptedLabel + ' for this beneficiary. Choose '
            + recommendedLabel + ' based on the caretaker report.'
        );
    }
    monitoringFlowAlert(body, title, 'default', null);
}

async function submitProgressAssessment(decision) {
    if (!activeInspectionTask || activeInspectionTask.status !== 'completed') return;
    const report = activeInspectionTask.report || {};
    const recommended = monitoringRecommendedStaffDecision(activeInspectionTask, report);
    if (recommended && decision !== recommended) {
        alertMonitoringStaffDecisionMismatch(activeInspectionTask, decision, recommended);
        return;
    }
    const decisionActions = document.getElementById('inspectionDecisionActions');
    const text = document.getElementById('inspectionInfoText');
    if (decisionActions) {
        [...decisionActions.querySelectorAll('button')].forEach((button) => button.disabled = true);
    }

    try {
        const body = new URLSearchParams();
        body.append('decision', decision);
        const res = await fetch(`/units/monitoring-task/${encodeURIComponent(activeInspectionTask.id)}/assess/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken') || '',
                'X-Requested-With': 'XMLHttpRequest',
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: body.toString(),
        });
        const data = await parseMonitoringJsonResponse(res);
        if (!res.ok || !data.success) {
            throw new Error(data.error || 'Could not save staff decision.');
        }

        const updatedTask = {
            ...activeInspectionTask,
            initial_monitoring_complete: Boolean(
                activeInspectionTask.task_type === 'day_60_inspection'
                && (decision === 'normal_progress' || decision === 'no_progress')
            ),
            final_monitoring_program_complete: Boolean(
                data.monitoring_program_complete
                && (activeInspectionTask.task_type === 'day_30_inspection'
                    || activeInspectionTask.task_type === 'month_2_inspection')
                && decision === 'normal_progress'
            ),
            initial_monitoring_program_complete: Boolean(
                activeInspectionTask.task_type === 'day_60_inspection'
                && (decision === 'normal_progress' || decision === 'no_progress')
            ),
            report: {
                ...(activeInspectionTask.report || {}),
                progress_assessment: data.decision,
                progress_assessment_label: data.decision_label,
                assessed_at: data.assessed_at,
                assessed_by: data.assessed_by,
            },
        };
        activeInspectionTask = updatedTask;
        currentMonitoringTasks = currentMonitoringTasks.map((task) => (
            String(task.id) === String(updatedTask.id) ? updatedTask : task
        ));
        closeInspectionInfoModal();
        const extensionMarkedFailed = Boolean(
            data.extension_final_visit_failed
            || (updatedTask.task_type === 'month_2_inspection' && decision === 'no_progress')
        );
        if (extensionMarkedFailed && lastOpenedUnitPayload) {
            lastOpenedUnitPayload.extension_final_visit_failed = true;
            applyUnitDetailHeader(lastOpenedUnitPayload);
            applyUnitDrawerStatusPill(lastOpenedUnitPayload);
            applyVmapLotMapBadge(lastOpenedUnitPayload);
        }
        if (data.monitoring_program_complete && currentUnitId) {
            openUnitModal(currentUnitId);
        } else {
            const ext120 = lastOpenedUnitPayload && lastOpenedUnitPayload.explanation_extension_final_task;
            const merged = mergeMonitoringTasksForState(currentMonitoringTasks.filter(
                (t) => t.task_type !== 'month_1_inspection' && t.task_type !== 'month_2_inspection'
            ), ext120);
            currentMonitoringTasks = merged;
            const main = merged.filter((t) => t.task_type !== 'month_1_inspection' && t.task_type !== 'month_2_inspection');
            const letterWf = lastOpenedUnitPayload && lastOpenedUnitPayload.explanation_letter_workflow_applies === true;
            renderMonitoringTaskCards(main, merged, letterWf);
            renderPriorNoProgressVisitsPanel(letterWf);
            renderExplanationExtensionTaskCards(ext120);
            renderMonitoringHistoryRecord(buildMonitoringHistoryFromTasks(currentMonitoringTasks));
            if (data.housing_unit_on_file && currentUnitId) {
                const position = '{{ request.user.position }}';
                fetch(`/units/housing-units/${position}/${encodeURIComponent(currentUnitId)}/details/`)
                    .then((r) => r.json())
                    .then((payload) => {
                        if (payload.success && payload.unit) {
                            const u = payload.unit;
                            lastOpenedUnitPayload = u;
                            applyUnitDetailHeader(u);
                            applyUnitDrawerStatusPill(u);
                            applyVmapLotMapBadge(u);
                        }
                    })
                    .catch(() => { /* ignore */ });
            }
        }
        if (extensionMarkedFailed && currentUnitId) {
            const position = '{{ request.user.position }}';
            fetch(`/units/housing-units/${position}/${encodeURIComponent(currentUnitId)}/details/`)
                .then((r) => r.json())
                .then((payload) => {
                    if (payload.success && payload.unit) {
                        const u = payload.unit;
                        lastOpenedUnitPayload = u;
                        applyUnitDetailHeader(u);
                        applyUnitDrawerStatusPill(u);
                        syncExplanationLetterPanel(u);
                        applyVmapLotMapBadge(u);
                        updateFooterSmsButton(u);
                    }
                    setTimeout(() => highlightExtensionFailedDisqualifyPath(), 150);
                })
                .catch(() => {
                    setTimeout(() => highlightExtensionFailedDisqualifyPath(), 150);
                });
        }
        try {
            const _ts = String(Date.now());
            localStorage.setItem('tha_monitoring_task_sync', _ts);
            if (typeof BroadcastChannel !== 'undefined') {
                const _bc = new BroadcastChannel('tha_monitoring_task_sync_bc');
                _bc.postMessage({ t: _ts });
                _bc.close();
            }
        } catch (ignoreLs) { /* private mode / quota */ }
    } catch (err) {
        if (text) {
            text.textContent = err.message || 'Could not save staff decision.';
        }
    } finally {
        if (decisionActions) {
            [...decisionActions.querySelectorAll('button')].forEach((button) => button.disabled = false);
        }
    }
}

function closeInspectionInfoModal(e) {
    if (e && e.target.id !== 'inspectionInfoModal') return;
    const modal = document.getElementById('inspectionInfoModal');
    if (modal) modal.style.display = 'none';
    activeInspectionTask = null;
}

async function notifySelectedInspectionTask() {
    if (!activeInspectionTask) return;
    const dashboardBtn = document.getElementById('inspectionDashboardBtn');
    const text = document.getElementById('inspectionInfoText');
    if (dashboardBtn) {
        dashboardBtn.disabled = true;
        dashboardBtn.textContent = 'Notifying...';
    }

    try {
        const res = await fetch(`/units/monitoring-task/${encodeURIComponent(activeInspectionTask.id)}/notify/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken') || '',
                'X-Requested-With': 'XMLHttpRequest',
            },
        });
        const data = await res.json();
        if (!res.ok || !data.success) {
            throw new Error(data.error || 'Could not notify monitoring dashboard.');
        }
        const notifiedAt = data.notified_at || new Date().toISOString();
        activeInspectionTask.notified_at = notifiedAt;
        currentMonitoringTasks = currentMonitoringTasks.map((task) => {
            if (String(task.id) === String(activeInspectionTask.id)) {
                return { ...task, notified_at: notifiedAt };
            }
            return task;
        });
        try {
            const _ts = String(Date.now());
            localStorage.setItem('tha_monitoring_task_sync', _ts);
            if (typeof BroadcastChannel !== 'undefined') {
                const _bc = new BroadcastChannel('tha_monitoring_task_sync_bc');
                _bc.postMessage({ t: _ts });
                _bc.close();
            }
        } catch (ignoreLs) { /* private mode / quota */ }
        closeInspectionInfoModal();
        const ext120 = lastOpenedUnitPayload && lastOpenedUnitPayload.explanation_extension_final_task;
        const merged = mergeMonitoringTasksForState(
            currentMonitoringTasks.filter((t) => t.task_type !== 'month_1_inspection' && t.task_type !== 'month_2_inspection'),
            ext120
        );
        currentMonitoringTasks = merged;
        const main = merged.filter((t) => t.task_type !== 'month_1_inspection' && t.task_type !== 'month_2_inspection');
        const letterWf = lastOpenedUnitPayload && lastOpenedUnitPayload.explanation_letter_workflow_applies === true;
        renderMonitoringTaskCards(main, merged, letterWf);
        renderPriorNoProgressVisitsPanel(letterWf);
        renderExplanationExtensionTaskCards(ext120);
    } catch (err) {
        if (text) {
            text.textContent = err.message || 'Could not notify monitoring dashboard.';
        }
        if (dashboardBtn) {
            dashboardBtn.disabled = false;
            dashboardBtn.textContent = 'Notify Monitoring Dashboard';
        }
    }
}

let lastOpenedUnitPayload = null;

let explanationLetterDwtObject = null;
if (window.Dynamsoft && window.Dynamsoft.DWT) {
    Dynamsoft.DWT.RegisterEvent('OnWebTwainReady', function () {
        try {
            explanationLetterDwtObject = Dynamsoft.DWT.GetWebTwain('dwtcontrolContainer');
        } catch (_e) {
            explanationLetterDwtObject = null;
        }
    });
}

async function explanationLetterWaitForDwtReady(timeoutMs = 12000) {
    const startedAt = Date.now();
    while (!explanationLetterDwtObject && (Date.now() - startedAt) < timeoutMs) {
        await new Promise(function (resolve) { setTimeout(resolve, 100); });
    }
    return explanationLetterDwtObject;
}

function explanationLetterClearDwtBuffer(dwt) {
    if (!dwt) return;
    try {
        if (typeof dwt.RemoveAllImages === 'function') {
            dwt.RemoveAllImages();
        }
    } catch (_e) { /* ignore */ }
}

function explanationLetterConvertDwtScanToPngFile(dwt) {
    return new Promise(function (resolve, reject) {
        const index = Number(dwt.CurrentImageIndexInBuffer);
        if (Number.isNaN(index) || index < 0) {
            reject(new Error('No scanned image in buffer.'));
            return;
        }
        const fail = function (_code, msg) {
            reject(new Error(msg || 'Export failed.'));
        };
        const finishBlob = function (blob) {
            if (!blob) {
                reject(new Error('Could not export scan.'));
                return;
            }
            const name = 'explanation-letter-scan.png';
            resolve(new File([blob], name, { type: blob.type || 'image/png' }));
        };
        if (typeof dwt.ConvertToBlob === 'function') {
            dwt.ConvertToBlob([index], Dynamsoft.DWT.EnumDWT_ImageType.IT_PNG, function (result) {
                if (result instanceof Blob) {
                    finishBlob(result);
                    return;
                }
                if (result && result.blob instanceof Blob) {
                    finishBlob(result.blob);
                    return;
                }
                reject(new Error('Unexpected scan export format.'));
            }, fail);
            return;
        }
        if (typeof dwt.ConvertToBase64 === 'function') {
            dwt.ConvertToBase64([index], Dynamsoft.DWT.EnumDWT_ImageType.IT_PNG, function (base64) {
                try {
                    let b64 = String(base64 || '').trim();
                    if (b64.includes(',')) b64 = b64.split(',')[1] || '';
                    const bin = atob(b64);
                    const arr = new Uint8Array(bin.length);
                    for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
                    finishBlob(new Blob([arr], { type: 'image/png' }));
                } catch (err) {
                    reject(err);
                }
            }, fail);
            return;
        }
        reject(new Error('Scanner export API not available. Use Upload.'));
    });
}

async function explanationScanLetterWithDwt() {
    const scanBtn = document.getElementById('explanationTwainScanBtn');
    if (scanBtn && scanBtn.disabled) return;
    const unit = lastOpenedUnitPayload;
    const c = unit && unit.explanation_letter_case;
    if (!c || !c.can_upload_letter) {
        monitoringFlowAlert('Set the letter deadline first, then upload or scan.', 'Notice', 'default', null);
        return;
    }
    const oldText = scanBtn ? scanBtn.textContent : '';
    if (scanBtn) {
        scanBtn.disabled = true;
        scanBtn.textContent = 'Scanning…';
    }
    try {
        const dwt = await explanationLetterWaitForDwtReady();
        if (!dwt) throw new Error('Scanner SDK is not ready. Refresh the page and try again.');
        await dwt.SelectSourceAsync();
        const beforeCount = Number(dwt.HowManyImagesInBuffer || 0);
        await dwt.AcquireImageAsync({ IfCloseSourceAfterAcquire: true });
        const afterCount = Number(dwt.HowManyImagesInBuffer || 0);
        if (afterCount <= beforeCount) throw new Error('No image was acquired from the scanner.');
        const file = await explanationLetterConvertDwtScanToPngFile(dwt);
        explanationLetterClearDwtBuffer(dwt);
        await uploadExplanationLetterFile(file);
    } catch (e) {
        monitoringFlowAlert((e && e.message) ? e.message : 'Scan failed.', 'Scan failed', 'default', null);
    } finally {
        if (scanBtn) {
            scanBtn.disabled = false;
            scanBtn.textContent = oldText || 'Scan';
        }
    }
}

function explanationUploadLetterFromComputer() {
    const btn = document.getElementById('explanationUploadLetterBtn');
    if (btn && btn.disabled) return;
    const unit = lastOpenedUnitPayload;
    const c = unit && unit.explanation_letter_case;
    if (!c || !c.can_upload_letter) {
        monitoringFlowAlert('Set the letter deadline first, then upload or scan.', 'Notice', 'default', null);
        return;
    }
    document.getElementById('explanationLetterFile')?.click();
}

function updateExplanationBuildExtensionNote(unit) {
    const el = document.getElementById('explanationBuildExtensionNote');
    if (!el) return;
    const ext = unit && unit.explanation_build_extension;
    if (ext && ext.end_date) {
        const until = formatDisplayDate(String(ext.end_date).slice(0, 10));
        const fromD = ext.start_date ? formatDisplayDate(String(ext.start_date).slice(0, 10)) : '';
        el.textContent = fromD
            ? (
                `Letter on file triggers a 120-day build extension (${fromD}–${until}). `
                + 'Original 90 Day and 120 Day visits stay in the card above; the Extension 120 Day visit appears below.'
            )
            : (
                `Letter on file triggers a 120-day build extension (through ${until}). `
                + 'Original visits stay above; the Extension 120 Day visit appears below.'
            );
        el.style.display = 'block';
    } else {
        el.textContent = '';
        el.style.display = 'none';
    }
}

function syncExplanationLetterPanel(unit) {
    lastOpenedUnitPayload = unit;
    const panel = document.getElementById('explanationLetterPanel');
    const status = document.getElementById('explanationLetterStatus');
    const deadlineForm = document.getElementById('explanationDeadlineForm');
    const fileActions = document.getElementById('explanationLetterFileActions');
    const extNote = document.getElementById('explanationBuildExtensionNote');
    const dqBtn = document.getElementById('disqualifyBeneficiaryBtn');
    const uploadBtn = document.getElementById('explanationUploadLetterBtn');
    const scanBtn = document.getElementById('explanationTwainScanBtn');
    const viewBtn = document.getElementById('explanationViewLetterBtn');
    const subBtn = document.getElementById('explanationSubmitScanBtn');
    const nameEl = document.getElementById('explanationSelectedFileName');
    const fi = document.getElementById('explanationLetterFile');
    if (!panel || !status || !deadlineForm || !fileActions) {
        updateFooterSmsButton(unit);
        return;
    }

    if (extNote) {
        extNote.style.display = 'none';
        extNote.textContent = '';
    }

    status.textContent = '';
    status.style.display = 'none';

    function setLetterButtons(canUpload, uploadHint, canScan, scanHint, canView, letterUrl) {
        if (uploadBtn) {
            uploadBtn.style.display = 'inline-flex';
            uploadBtn.disabled = !canUpload;
            uploadBtn.style.opacity = canUpload ? '1' : '0.55';
            uploadBtn.style.cursor = canUpload ? 'pointer' : 'not-allowed';
            uploadBtn.title = uploadHint || '';
        }
        if (scanBtn) {
            scanBtn.style.display = 'inline-flex';
            scanBtn.disabled = !canScan;
            scanBtn.style.opacity = canScan ? '1' : '0.55';
            scanBtn.style.cursor = canScan ? 'pointer' : 'not-allowed';
            scanBtn.title = scanHint || '';
        }
        if (viewBtn) {
            viewBtn.style.display = 'inline-flex';
            viewBtn.disabled = !canView;
            viewBtn.style.opacity = canView ? '1' : '0.55';
            viewBtn.style.cursor = canView ? 'pointer' : 'not-allowed';
            viewBtn.dataset.url = letterUrl || '';
            viewBtn.title = canView
                ? 'Open the explanation letter in a new tab.'
                : 'No scanned explanation letter saved yet.';
        }
    }

    const c = unit.explanation_letter_case;
    const viewUrl = (c && c.letter_document_url) || (!c && (unit.explanation_letter_view_url || '')) || '';
    const hasAward = Boolean(unit.lot_award_id);

    if (!hasAward) {
        panel.style.display = 'none';
        panel.classList.remove('explanation-letter-panel--dormant');
        deadlineForm.style.display = 'none';
        fileActions.style.display = 'none';
        if (uploadBtn) uploadBtn.style.display = 'none';
        if (scanBtn) scanBtn.style.display = 'none';
        if (viewBtn) viewBtn.style.display = 'none';
        if (subBtn) subBtn.style.display = 'none';
        if (nameEl) nameEl.style.display = 'none';
        if (fi) fi.value = '';
        if (dqBtn) {
            dqBtn.style.opacity = '0.45';
            dqBtn.style.pointerEvents = 'none';
        }
        updateFooterSmsButton(unit);
        return;
    }

    if (unit.explanation_letter_workflow_applies !== true) {
        panel.style.display = 'none';
        panel.classList.remove('explanation-letter-panel--dormant');
        deadlineForm.style.display = 'none';
        fileActions.style.display = 'none';
        if (uploadBtn) uploadBtn.style.display = 'none';
        if (scanBtn) scanBtn.style.display = 'none';
        if (viewBtn) viewBtn.style.display = 'none';
        if (subBtn) subBtn.style.display = 'none';
        if (nameEl) nameEl.style.display = 'none';
        if (fi) fi.value = '';
        if (dqBtn) {
            dqBtn.style.opacity = '0.45';
            dqBtn.style.pointerEvents = 'none';
        }
        updateFooterSmsButton(unit);
        return;
    }

    if (!c && !viewUrl) {
        panel.style.display = 'block';
        panel.classList.add('explanation-letter-panel--dormant');
        deadlineForm.style.display = 'none';
        fileActions.style.display = 'block';
        const dormantHint = 'Available after a 120 Day Explanation letter outcome and a letter deadline is set.';
        setLetterButtons(false, dormantHint, false, dormantHint, false, '');
        if (subBtn) subBtn.style.display = 'none';
        if (nameEl) nameEl.style.display = 'none';
        if (fi) fi.value = '';
        if (dqBtn) {
            dqBtn.style.opacity = '0.45';
            dqBtn.style.pointerEvents = 'none';
        }
        updateFooterSmsButton(unit);
        return;
    }

    panel.style.display = 'block';
    panel.classList.remove('explanation-letter-panel--dormant');

    if (!c && viewUrl) {
        deadlineForm.style.display = 'none';
        fileActions.style.display = 'block';
        const lockedHint = 'Letter on file. Upload and scan are unavailable until a new 120 Day Explanation letter case is opened.';
        setLetterButtons(false, lockedHint, false, lockedHint, true, viewUrl);
        if (subBtn) subBtn.style.display = 'none';
        if (nameEl) nameEl.style.display = 'none';
        if (fi) fi.value = '';
        if (dqBtn) {
            const enable = Boolean(unit.extension_final_visit_failed);
            dqBtn.style.opacity = enable ? '1' : '0.45';
            dqBtn.style.pointerEvents = enable ? 'auto' : 'none';
        }
        updateFooterSmsButton(unit);
        updateExplanationBuildExtensionNote(unit);
        return;
    }

    const parts = [];
    if (c.letter_deadline_display) {
        parts.push(`Deadline: ${c.letter_deadline_display}`);
    } else if (c.letter_deadline_at) {
        const d = new Date(c.letter_deadline_at);
        if (!Number.isNaN(d.getTime())) {
            parts.push(`Deadline: ${d.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })}`);
        } else {
            parts.push(`Deadline: ${formatDisplayDate(String(c.letter_deadline_at).slice(0, 10))}`);
        }
    } else {
        parts.push('Deadline not set — set date and time below, then save.');
    }
    if (c.has_letter_document) {
        parts.push('Letter on file.');
    }
    status.style.display = 'block';
    status.textContent = parts.join(' ');

    deadlineForm.style.display = c.can_set_deadline ? 'flex' : 'none';

    fileActions.style.display = 'block';
    const canAct = Boolean(c.can_upload_letter);
    const canView = Boolean(viewUrl);
    const idleHint = canAct ? '' : 'Set the letter deadline first, then upload or scan.';
    setLetterButtons(canAct, idleHint, canAct, idleHint, canView, viewUrl);
    if (subBtn) subBtn.style.display = 'none';
    if (nameEl) nameEl.style.display = 'none';
    if (fi) fi.value = '';

    if (dqBtn) {
        const extFail = Boolean(unit.extension_final_visit_failed);
        const enable = extFail || Boolean(c.can_disqualify);
        dqBtn.style.opacity = enable ? '1' : '0.45';
        dqBtn.style.pointerEvents = enable ? 'auto' : 'none';
    }

    updateFooterSmsButton(unit);

    const inp = document.getElementById('explanationDeadlineInput');
    if (inp && (c.letter_deadline_local_input || c.letter_deadline_at)) {
        if (c.letter_deadline_local_input) {
            inp.value = c.letter_deadline_local_input;
        } else {
            const d = new Date(c.letter_deadline_at);
            if (!Number.isNaN(d.getTime())) {
                const pad = (n) => String(n).padStart(2, '0');
                inp.value = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
            }
        }
    } else if (inp) {
        inp.value = '';
    }
    updateExplanationBuildExtensionNote(unit);
}

function explanationLetterFileChosen() {
    const unit = lastOpenedUnitPayload;
    const c = unit && unit.explanation_letter_case;
    const fi = document.getElementById('explanationLetterFile');
    const nameEl = document.getElementById('explanationSelectedFileName');
    const subBtn = document.getElementById('explanationSubmitScanBtn');
    if (!fi || !fi.files || !fi.files[0]) {
        if (nameEl) nameEl.style.display = 'none';
        if (subBtn) subBtn.style.display = 'none';
        return;
    }
    if (nameEl) {
        nameEl.textContent = `Selected: ${fi.files[0].name}`;
        nameEl.style.display = 'block';
    }
    if (subBtn) {
        subBtn.style.display = (c && c.can_upload_letter) ? 'inline-block' : 'none';
    }
}

function explanationViewLetter() {
    const btn = document.getElementById('explanationViewLetterBtn');
    if (!btn || btn.disabled) return;
    const url = btn.dataset.url;
    if (url) {
        window.open(url, '_blank', 'noopener,noreferrer');
    }
}

async function saveExplanationLetterDeadline() {
    const inp = document.getElementById('explanationDeadlineInput');
    if (!inp || !inp.value) {
        monitoringFlowAlert('Choose a deadline date and time.', 'Reminder', 'default', null);
        return;
    }
    const position = '{{ request.user.position }}';
    try {
        const res = await fetch(`/units/housing-units/${position}/${currentUnitId}/explanation-letter/deadline/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken') || '',
                'X-Requested-With': 'XMLHttpRequest',
            },
            body: JSON.stringify({
                deadline_local: inp.value,
                notify_beneficiary: document.getElementById('explanationNotifySms') ? document.getElementById('explanationNotifySms').checked : true,
            }),
        });
        const data = await parseMonitoringJsonResponse(res);
        if (!res.ok || !data.success) {
            throw new Error(data.error || 'Could not save deadline.');
        }
        const smsNote = data.sms_sent === false && document.getElementById('explanationNotifySms')?.checked
            ? ' Deadline saved. SMS was not sent (check phone number or SMS provider).'
            : (data.sms_sent ? ' Deadline saved and SMS sent to the beneficiary.' : '');
        if (smsNote) {
            monitoringFlowAlert(smsNote.trim(), 'Deadline saved', 'success', () => { openUnitModal(currentUnitId); });
        } else {
            openUnitModal(currentUnitId);
        }
    } catch (e) {
        monitoringFlowAlert(e.message || 'Could not save deadline.', 'Could not save', 'default', null);
    }
}

async function uploadExplanationLetterFile(fileOverride) {
    const fi = document.getElementById('explanationLetterFile');
    const file = (fileOverride instanceof File)
        ? fileOverride
        : (fi && fi.files && fi.files[0]);
    if (!file) {
        monitoringFlowAlert('Choose a file to upload.', 'Reminder', 'default', null);
        return;
    }
    const position = '{{ request.user.position }}';
    const body = new FormData();
    body.append('letter_file', file);
    body.append('csrfmiddlewaretoken', getCookie('csrftoken') || '');
    try {
        const res = await fetch(`/units/housing-units/${position}/${currentUnitId}/explanation-letter/upload/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken') || '',
                'X-Requested-With': 'XMLHttpRequest',
            },
            body,
        });
        const data = await res.json();
        if (!res.ok || !data.success) {
            throw new Error(data.error || 'Upload failed.');
        }
        if (fi) fi.value = '';
        monitoringFlowAlert(
            data.message || 'Letter saved.',
            'Explanation letter stored',
            'success',
            () => { openUnitModal(currentUnitId); }
        );
    } catch (e) {
        monitoringFlowAlert(e.message || 'Upload failed.', 'Upload failed', 'default', null);
    }
}

function fillBlacklistModalSituation() {
    const wrap = document.getElementById('blacklistModalSituation');
    if (!wrap) return;
    const unit = lastOpenedUnitPayload;
    if (!unit) {
        wrap.innerHTML = '';
        wrap.style.display = 'none';
        return;
    }

    const ext = unit.explanation_build_extension;
    const ext120 = unit.explanation_extension_final_task;
    const extFailed = Boolean(unit.extension_final_visit_failed);
    const c = unit.explanation_letter_case;

    let paragraph = '';

    const extRangeSentence = () => {
        if (!ext || !ext.start_date || !ext.end_date) return '';
        const fromD = formatDisplayDate(String(ext.start_date).slice(0, 10));
        const until = formatDisplayDate(String(ext.end_date).slice(0, 10));
        return `Build extension (after letter): ${fromD}–${until}. Original 90 & 120 Day visits stay in the card above; extension visits are separate below.`;
    };

    if (extFailed && ext120 && ext120.task_type === 'month_2_inspection') {
        const rep = ext120.report || {};
        const due = ext120.due_date ? formatDisplayDate(ext120.due_date) : '';
        const labels = monitoringStaffDecisionLabels(ext120);
        const outcomeLabel = rep.progress_assessment_label
            || (rep.progress_assessment === 'no_progress' ? labels.no_progress : '')
            || 'Failed';
        const by = rep.assessed_by ? ` · ${rep.assessed_by}` : '';
        const visitSummary = (
            `Extension final visit`
            + (due ? ` (${due})` : '')
            + `: ${outcomeLabel}${by}.`
        );
        const tail = (c && c.has_letter_document)
            ? ' Eligible for blacklist (letter may already be on file).'
            : ' Eligible for blacklist.';
        const lead = extRangeSentence();
        paragraph = [lead, visitSummary + tail].filter(Boolean).join(' ');
    } else if (extFailed) {
        const lead = extRangeSentence();
        paragraph = (
            [lead, 'Extension final visit assessed Failed. Eligible for blacklist.']
                .filter(Boolean)
                .join(' ')
        );
    } else if (c && c.can_disqualify) {
        const lead = extRangeSentence();
        paragraph = (
            [lead, 'Letter deadline passed with no compliant letter on file. Eligible for blacklist.']
                .filter(Boolean)
                .join(' ')
        );
    } else {
        paragraph = 'Reload this lot’s details to show blacklist context.';
    }

    wrap.innerHTML = `<p>${paragraph}</p>`;
    wrap.style.display = 'block';
}

function openDisqualifyBeneficiaryModal() {
    const modal = document.getElementById('disqualifyBeneficiaryModal');
    const ta = document.getElementById('disqualifyReasonInput');
    if (ta) ta.value = '';
    fillBlacklistModalSituation();
    if (modal) modal.style.display = 'flex';
}

function closeDisqualifyBeneficiaryModal(e) {
    if (e && e.target.id !== 'disqualifyBeneficiaryModal') return;
    const modal = document.getElementById('disqualifyBeneficiaryModal');
    if (modal) modal.style.display = 'none';
}

async function submitDisqualifyBeneficiary() {
    const ta = document.getElementById('disqualifyReasonInput');
    const reason = (ta && ta.value) ? ta.value.trim() : '';
    if (reason.length < 10) {
        monitoringFlowAlert('Enter a blacklist reason (at least 10 characters).', 'Reminder', 'default', null);
        return;
    }
    const position = '{{ request.user.position }}';
    try {
        const res = await fetch(`/units/housing-units/${position}/${currentUnitId}/disqualify-beneficiary/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken') || '',
                'X-Requested-With': 'XMLHttpRequest',
            },
            body: JSON.stringify({ reason }),
        });
        let data;
        try {
            data = await res.json();
        } catch (parseErr) {
            throw new Error('Unexpected server response while blacklisting. Check that you are logged in and try again.');
        }
        if (!res.ok || !data.success) {
            throw new Error(data.error || 'Blacklist failed.');
        }
        closeDisqualifyBeneficiaryModal();
        monitoringFlowAlert(
            data.message || 'Beneficiary blacklisted.',
            'Blacklisted',
            'success',
            () => {
                window.location.href = `/units/blacklists/${position}/`;
            }
        );
    } catch (e) {
        monitoringFlowAlert(e.message || 'Blacklist failed.', 'Could not blacklist', 'default', null);
    }
}

/* ── Award profile: beneficiary avatar, lot award record, validation log ── */

function applyBeneficiaryAvatar(ben) {
    const avatarEl = document.getElementById('beneficiaryAvatar');
    const nameEl = document.getElementById('beneficiaryAvatarName');
    const refEl = document.getElementById('beneficiaryAvatarRef');
    if (!avatarEl) return;
    const name = (ben && ben.full_name) ? ben.full_name : '';
    const ref = (ben && ben.reference_number) ? ben.reference_number : '';
    if (name) {
        const initials = name.split(' ').filter(Boolean).map(w => w[0].toUpperCase()).slice(0, 2).join('');
        avatarEl.textContent = initials || '?';
    } else {
        avatarEl.textContent = '?';
    }
    if (nameEl) nameEl.textContent = name || '—';
    if (refEl) refEl.textContent = ref || '—';
}

function _renderStaffPill(avatarEl, nameEl, badgeEl, profile, noAuthText) {
    if (!avatarEl) return;
    if (profile) {
        const initials = (profile.initials || profile.full_name.split(' ').filter(Boolean).map(w => w[0].toUpperCase()).slice(0, 2).join('')) || '?';
        avatarEl.textContent = initials;
        avatarEl.style.opacity = '1';
        if (nameEl) nameEl.textContent = profile.full_name || '—';
        if (badgeEl) { badgeEl.textContent = profile.position_label || profile.position || ''; }
    } else {
        avatarEl.textContent = '—';
        avatarEl.style.opacity = '0.4';
        if (nameEl) nameEl.textContent = noAuthText || '—';
        if (badgeEl) badgeEl.textContent = '';
    }
}

function renderAwardProfile(profile) {
    const recordCard = document.getElementById('lotAwardRecordCard');
    const logCard = document.getElementById('validationLogCard');
    if (!recordCard || !logCard) return;
    if (!profile) {
        recordCard.hidden = true;
        logCard.hidden = true;
        return;
    }
    recordCard.hidden = false;
    logCard.hidden = false;

    // Awarded by
    _renderStaffPill(
        document.getElementById('awardedByAvatar'),
        document.getElementById('awardedByName'),
        document.getElementById('awardedByBadge'),
        profile.awarded_by,
        '—'
    );
    const awardedAtEl = document.getElementById('awardRecordAwardedAt');
    if (awardedAtEl) awardedAtEl.textContent = profile.awarded_at_display || '—';

    // Authenticated by
    _renderStaffPill(
        document.getElementById('authenticatedByAvatar'),
        document.getElementById('authenticatedByName'),
        document.getElementById('authenticatedByBadge'),
        profile.authenticated_by,
        'Not yet authenticated'
    );
    const authAtEl = document.getElementById('authenticatedAtValue');
    if (authAtEl) authAtEl.textContent = profile.authenticated_at_display || '—';

    // Validation log
    const logEntries = document.getElementById('validationLogEntries');
    const logCount = document.getElementById('validationLogCount');
    const logs = profile.validation_logs || [];
    if (logCount) logCount.textContent = logs.length ? String(logs.length) : '';
    if (logEntries) {
        if (logs.length === 0) {
            logEntries.innerHTML = '<p style="font-size:0.77rem;color:#94a3b8;font-style:italic;margin:0.5rem 0;">No validation events recorded yet.</p>';
        } else {
            logEntries.innerHTML = logs.map((vl, i) => {
                const by = vl.validated_by ? vl.validated_by.full_name : '—';
                const pos = vl.validated_by ? (vl.validated_by.position_label || '') : '';
                const initials = vl.validated_by ? (vl.validated_by.initials || by.split(' ').filter(Boolean).map(w => w[0].toUpperCase()).slice(0, 2).join('')) : '?';
                const isFirst = i === logs.length - 1;
                return `<div style="display:flex;align-items:flex-start;gap:0.6rem;padding:0.55rem 0;${i > 0 ? 'border-top:1px solid #f1f5f9;' : ''}">
                    <div style="width:26px;height:26px;border-radius:50%;background:linear-gradient(135deg,#6366f1,#a855f7);display:flex;align-items:center;justify-content:center;font-size:0.62rem;font-weight:700;color:#fff;flex-shrink:0;">${initials}</div>
                    <div style="flex:1;min-width:0;">
                        <div style="display:flex;align-items:center;gap:0.4rem;flex-wrap:wrap;">
                            <span style="font-size:0.78rem;font-weight:700;color:#0f172a;">${by}</span>
                            ${pos ? `<span style="font-size:0.6rem;font-weight:700;padding:0.08rem 0.35rem;border-radius:4px;background:#ede9fe;color:#4c1d95;">${pos}</span>` : ''}
                            ${isFirst ? '<span style="font-size:0.6rem;font-weight:700;padding:0.08rem 0.35rem;border-radius:4px;background:#fef3c7;color:#92400e;">First · Authenticator</span>' : ''}
                        </div>
                        <p style="margin:0.18rem 0 0;font-size:0.71rem;color:#475569;">${vl.validated_at_display}</p>
                        ${vl.notes ? `<p style="margin:0.25rem 0 0;font-size:0.72rem;color:#374151;font-style:italic;">"${vl.notes}"</p>` : ''}
                    </div>
                    <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="#10b981" stroke-width="2.5" style="flex-shrink:0;margin-top:0.2rem;"><polyline points="20 6 9 17 4 12"/></svg>
                </div>`;
            }).join('');
        }
    }

    // Show/hide validate action button
    const validateAction = document.getElementById('validateDocumentAction');
    if (validateAction) {
        validateAction.hidden = !profile.can_validate_document;
    }
}

async function submitDocumentValidation() {
    const btn = document.getElementById('validateDocBtn');
    const errEl = document.getElementById('validateDocError');
    const notes = (document.getElementById('validateDocNotes') || {}).value || '';
    if (errEl) { errEl.style.display = 'none'; errEl.textContent = ''; }
    if (btn) { btn.disabled = true; btn.textContent = 'Saving…'; }
    const position = '{{ request.user.position }}';
    try {
        const res = await fetch(`/units/housing-units/${position}/${currentUnitId}/lot-award/validate/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') || '' },
            body: JSON.stringify({ notes }),
        });
        const data = await res.json();
        if (data.success) {
            renderAwardProfile(data.award_profile);
            // Clear textarea
            const ta = document.getElementById('validateDocNotes');
            if (ta) ta.value = '';
        } else {
            if (errEl) { errEl.textContent = data.error || 'Validation failed.'; errEl.style.display = 'block'; }
        }
    } catch (e) {
        if (errEl) { errEl.textContent = 'Network error. Please try again.'; errEl.style.display = 'block'; }
    } finally {
        if (btn) { btn.disabled = false; btn.innerHTML = '<svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg> Submit validation'; }
    }
}

function openUnitModal(unitId) {
    currentUnitId = unitId;
    const position = '{{ request.user.position }}';
    fetch(`/units/housing-units/${position}/${unitId}/details/`)
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                const unit = data.unit;
                lastOpenedUnitPayload = unit;
                applyUnitDetailHeader(unit);
                applyUnitDrawerStatusPill(unit);
                const ben = unit.beneficiary_info;
                document.getElementById('modalBeneficiaryName').textContent =
                    (ben && ben.full_name) ? ben.full_name : '—';
                document.getElementById('modalBeneficiaryRef').textContent =
                    (ben && ben.reference_number) ? ben.reference_number : '—';
                const sexEl = document.getElementById('modalBeneficiarySex');
                if (sexEl) {
                    sexEl.textContent = (ben && ben.sex_display) ? ben.sex_display : '—';
                }
                const hmEl = document.getElementById('modalHouseholdMembers');
                if (ben && ben.household_members != null && ben.household_members !== '') {
                    hmEl.textContent = String(ben.household_members);
                } else {
                    hmEl.textContent = '—';
                }
                renderHouseholdMembersRecord(ben ? ben.household_member_rows : [], {
                    can_add_household_members: !!unit.can_add_household_members,
                    relationship_options: unit.household_relationship_options || [],
                });
                const possession = unit.possession_info || null;
                document.getElementById('lotAwardedDate').textContent = possession && possession.awarded_at ? formatDisplayDate(possession.awarded_at) : '—';
                document.getElementById('lotPossessedDate').textContent = possession && possession.possessed_at ? formatDisplayDate(possession.possessed_at) : '—';
                document.getElementById('lotPossessedDays').textContent = possession && Number.isFinite(Number(possession.days_possessed))
                    ? `${Number(possession.days_possessed)} day(s)`
                    : '—';
                document.getElementById('awardActivationDate').textContent = possession && possession.awarded_at ? formatDisplayDate(possession.awarded_at) : '—';
                document.getElementById('monitoringStartsOn').textContent = possession && possession.monitoring_starts_on ? formatDisplayDate(possession.monitoring_starts_on) : '—';
                const footnoteEl = document.getElementById('lotPossessionFootnote');
                if (footnoteEl) {
                    footnoteEl.textContent = unit.historical_possession_note
                        || 'The award date starts possession. The beneficiary has 30 days to show house-building progress before scheduled monitoring begins.';
                }
                // Profile avatar + award record + validation log
                applyBeneficiaryAvatar(ben);
                renderAwardProfile(unit.award_profile || null);
                const main = unit.monitoring_tasks || [];
                const ext120 = unit.explanation_extension_final_task || null;
                const merged = mergeMonitoringTasksForState(main, ext120);
                const letterWf = unit.explanation_letter_workflow_applies === true;
                renderMonitoringTaskCards(main, merged, letterWf, unit);
                renderMonitoringHistoryRecord(unit.monitoring_history || [], unit);
                renderComplianceRecordsRecord(unit.compliance_records || []);
                renderUnitCaseRecord(unit);
                syncExplanationLetterPanel(unit);
                renderPriorNoProgressVisitsPanel(letterWf);
                renderExplanationExtensionTaskCards(ext120);
                applyVmapLotMapBadge(unit);
                updateFooterSmsButton(unit);
                applyUnitInventoryActions(unit);
                document.getElementById('unitModal').style.display = 'flex';
                if (unit.explanation_letter_workflow_applies === true && (unit.explanation_letter_case || unit.explanation_letter_view_url)) {
                    requestAnimationFrame(() => {
                        document.getElementById('explanationLetterPanel')?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                    });
                }
            } else {
                console.error('Failed to fetch unit details:', data.error);
            }
        })
        .catch(err => {
            console.error('Error fetching unit details:', err);
        });
}

function closeUnitModal(e) {
    if (e && e.target.id !== 'unitModal') return;
    const modal = document.getElementById('unitModal');
    modal.classList.add('drawer-closing');
    modal.addEventListener('animationend', function handler(ev) {
        if (ev.target !== modal) return;
        modal.removeEventListener('animationend', handler);
        modal.style.display = 'none';
        modal.classList.remove('drawer-closing');
    });
}

function switchUnitTab(btn) {
    if (!btn) return;
    const tabs = btn.parentElement.querySelectorAll('.unit-tab');
    tabs.forEach(function (tab) {
        const targetId = tab.getAttribute('data-tab-target');
        const panel = targetId ? document.getElementById(targetId) : null;
        const active = tab === btn;
        tab.classList.toggle('is-active', active);
        tab.setAttribute('aria-selected', active ? 'true' : 'false');
        if (panel) panel.hidden = !active;
    });
}

/* ── Ripple effect on footer buttons ── */
(function initFooterBtnRipple() {
    document.addEventListener('click', function (e) {
        const btn = e.target.closest('.unit-detail-footer-btn');
        if (!btn) return;
        const rect = btn.getBoundingClientRect();
        const ripple = document.createElement('span');
        ripple.className = 'btn-ripple';
        /* pick a ripple color based on the button type */
        if (btn.classList.contains('unit-detail-action-sms')) {
            ripple.style.background = 'rgba(255,255,255,0.4)';
        } else if (btn.classList.contains('unit-detail-action-disqualify')) {
            ripple.style.background = 'rgba(255,255,255,0.35)';
        } else if (btn.classList.contains('unit-detail-action-update')) {
            ripple.style.background = 'rgba(255,255,255,0.35)';
        } else {
            ripple.style.background = 'rgba(15,23,42,0.12)';
        }
        ripple.style.left = (e.clientX - rect.left) + 'px';
        ripple.style.top  = (e.clientY - rect.top) + 'px';
        btn.appendChild(ripple);
        ripple.addEventListener('animationend', function () { ripple.remove(); });
    });
})();

function sendSMS() {
    if (!currentUnitId) {
        monitoringFlowAlert('Open a lot first.', 'Send SMS', 'default', null);
        return;
    }
    openUnitBeneficiarySmsModal();
}

(function setupMonitoringTaskSyncListener() {
    function refreshOpenUnitIfNeeded() {
        if (!currentUnitId) return;
        const modal = document.getElementById('unitModal');
        if (!modal) return;
        const disp = modal.style.display;
        if (disp !== 'flex' && disp !== 'block') return;
        openUnitModal(currentUnitId);
    }
    window.addEventListener('storage', function (e) {
        if (e.key !== 'tha_monitoring_task_sync' || e.newValue == null) return;
        refreshOpenUnitIfNeeded();
    });
    if (typeof BroadcastChannel !== 'undefined') {
        try {
            const bc = new BroadcastChannel('tha_monitoring_task_sync_bc');
            bc.onmessage = function () { refreshOpenUnitIfNeeded(); };
        } catch (ignoreBc) { /* unsupported */ }
    }
})();

(function openUnitFromQuery() {
    const uid = new URLSearchParams(window.location.search).get('unit_id');
    if (uid) openUnitModal(uid);
})();

document.addEventListener('keydown', e => {
    if (e.key !== 'Escape') return;
    const smsModal = document.getElementById('unitBeneficiarySmsModal');
    if (smsModal && smsModal.style.display === 'flex') {
        closeUnitBeneficiarySmsModal();
        return;
    }
    closeUnitModal();
});

document.addEventListener('DOMContentLoaded', () => {
    // Build lot-plan zones up front so status syncs work even before the
    // plan view is opened (zones live-recolor via applyVmapLotMapBadge).
    try { buildLotPlan(); } catch (e) { /* lot plan optional */ }
    try { initLotPlanZoom(); } catch (e) { /* zoom optional */ }
    try { initLotPlanSearch(); } catch (e) { /* search optional */ }

    // Premium Hover Card popover initialization
    const hoverCard = document.getElementById('applicantHoverCard');
    const hcAvatar = document.getElementById('hcAvatar');
    const hcName = document.getElementById('hcName');
    const hcTx = document.getElementById('hcTx');
    const hcRef = document.getElementById('hcRef');
    const hcRefRow = document.getElementById('hcRefRow');
    const hcBlockLot = document.getElementById('hcBlockLot');
    const hcBlockLotRow = document.getElementById('hcBlockLotRow');
    const hcBrgy = document.getElementById('hcBrgy');
    const hcDob = document.getElementById('hcDob');

    let hideTimeout;

    function isHoverPopoverZone(el) {
        if (!el || el === document) return false;
        return !!(
            el.closest('#applicantHoverCard') ||
            el.closest('.occupant-name.applicant-name') ||
            el.closest('button.vmap-lot') ||
            el.closest('g.lotplan-lot--linked') ||
            (el.nodeName === 'polygon' && el.parentElement && el.parentElement.classList.contains('lotplan-lot--linked'))
        );
    }

    function scheduleHoverHide(delayMs) {
        clearTimeout(hideTimeout);
        hideTimeout = setTimeout(function () {
            hoverCard.classList.remove('active');
            setTimeout(() => { hoverCard.style.display = 'none'; }, 220);
        }, delayMs);
    }

    function resolveHoverTarget(e) {
        // 1. Occupant name span (hidden grid tiles)
        const nameSpan = e.target.closest('.occupant-name.applicant-name');
        if (nameSpan && nameSpan.dataset.fullName) return { source: nameSpan, anchor: nameSpan, mode: 'occupant' };

        // 2. SVG map polygon — mouseover bubbles through SVG reliably even after pan mousedown
        const svgLot = e.target.closest('g.lotplan-lot--linked');
        if (svgLot) {
            const unitId = svgLot.dataset.unitId || svgLot.getAttribute('data-unit-id') || '';
            const vmapBtn = unitId ? document.querySelector(`button.vmap-lot[data-unit-id="${unitId}"]`) : null;
            if (vmapBtn) {
                const inner = vmapBtn.querySelector('.occupant-name.applicant-name');
                if (inner && (inner.dataset.fullName || inner.getAttribute('data-full-name'))) {
                    return { source: inner, anchor: svgLot, mode: 'occupant', originalBtn: vmapBtn };
                }
                return { source: null, anchor: svgLot, mode: 'vacant', originalBtn: vmapBtn };
            }
            // Lot exists on the map but has no matching inventory entry — show minimal card
            const blockNum = svgLot.getAttribute('data-block') || '';
            const lotNum   = svgLot.getAttribute('data-lot')   || '';
            return { source: null, anchor: svgLot, mode: 'vacant', originalBtn: null,
                     fallbackLabel: blockNum && lotNum ? `B${blockNum} - L${lotNum}` : '' };
        }

        // 3. Any vmap-lot button (hidden grid)
        const vmapBtn = e.target.closest('button.vmap-lot');
        if (vmapBtn) {
            const inner = vmapBtn.querySelector('.occupant-name.applicant-name');
            if (inner && inner.dataset.fullName) return { source: inner, anchor: vmapBtn, mode: 'occupant', originalBtn: vmapBtn };
            return { source: null, anchor: vmapBtn, mode: 'vacant', originalBtn: vmapBtn };
        }
        return null;
    }

    document.addEventListener('mouseover', function (e) {
        const isHoverCard = e.target.closest('#applicantHoverCard');
        if (isHoverCard) { clearTimeout(hideTimeout); return; }

        const hit = resolveHoverTarget(e);
        if (!hit) return;

        clearTimeout(hideTimeout);

        const anchor = hit.anchor;
        const mode   = hit.mode;
        const vmapBtn = hit.originalBtn;

        // Block / Lot label — from grid tile, SVG data attributes, or fallback
        let blockLotText = hit.fallbackLabel || '';
        let unitStatus = '';
        if (vmapBtn) {
            const lotIdEl = vmapBtn.querySelector('.vmap-lot-id');
            blockLotText = lotIdEl ? lotIdEl.textContent.trim()
                : (vmapBtn.dataset.block ? `B${vmapBtn.dataset.block} - L${vmapBtn.dataset.lot}` : blockLotText);
            unitStatus = vmapBtn.dataset.unitStatus || vmapBtn.dataset.status || '';
        } else if (anchor && anchor.dataset) {
            // SVG lot with no matching grid button
            unitStatus = anchor.dataset.status || '';
        }

        if (mode === 'vacant') {
            // Minimal card for vacant / no-occupant tiles
            hcName.textContent = blockLotText || 'Vacant Lot';
            hcAvatar.textContent = '🏠';
            hcAvatar.style.background = 'linear-gradient(135deg, #dbeafe 0%, #93c5fd 100%)';
            hcAvatar.style.color = '#1e40af';
            hcAvatar.style.fontSize = '1.1rem';
            const hcTag = document.getElementById('hcTag');
            if (hcTag) hcTag.textContent = 'Lot Status';
            // TX row hidden for vacant
            const txRow = document.getElementById('hcTxRow');
            if (txRow) txRow.style.display = 'none';
            hcRefRow.style.display = 'none';
            // Status
            const statusEl = document.getElementById('hcStatus');
            const statusRowEl = document.getElementById('hcStatusRow');
            if (statusEl && statusRowEl) {
                statusEl.textContent = unitStatus || 'Vacant — available';
                statusRowEl.style.display = 'flex';
            }
            // Block/Lot
            hcBlockLot.textContent = blockLotText;
            hcBlockLotRow.style.display = 'flex';
            // Hide barangay/dob for vacant
            const brgyRow = document.getElementById('hcBrgyRow');
            const dobRow  = document.getElementById('hcDobRow');
            if (brgyRow) brgyRow.style.display = 'none';
            if (dobRow)  dobRow.style.display  = 'none';
        } else {
            // Full occupant card
            const nameSpan = hit.source;
            hcAvatar.style.background = 'linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%)';
            hcAvatar.style.color = '#ffffff';
            hcAvatar.style.fontSize = '0.85rem';
            const hcTag = document.getElementById('hcTag');
            if (hcTag) hcTag.textContent = 'Applicant Profile';

            const fullName = nameSpan.dataset.fullName || nameSpan.textContent.trim();
            const txId = nameSpan.dataset.txId || '';
            const refCode = nameSpan.dataset.refCode || '';
            const barangay = nameSpan.dataset.barangay || 'Not specified';
            const dob = nameSpan.dataset.dob || 'Not specified';

            hcName.textContent = fullName;
            hcAvatar.textContent = fullName.slice(0, 2).toUpperCase();

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

            const txRow = document.getElementById('hcTxRow');
            if (txRow) txRow.style.display = 'flex';
            hcTx.textContent = displayTx || '—';

            if (refCode) {
                hcRef.textContent = refCode;
                hcRefRow.style.display = 'flex';
            } else {
                hcRefRow.style.display = 'none';
            }

            const statusEl = document.getElementById('hcStatus');
            const statusRowEl = document.getElementById('hcStatusRow');
            if (statusEl && statusRowEl) {
                statusEl.textContent = unitStatus;
                statusRowEl.style.display = unitStatus ? 'flex' : 'none';
            }

            hcBlockLot.textContent = blockLotText;
            hcBlockLotRow.style.display = blockLotText ? 'flex' : 'none';

            // Restore brgy/dob rows (may have been hidden in vacant mode)
            const brgyRow = document.getElementById('hcBrgyRow');
            const dobRow  = document.getElementById('hcDobRow');
            if (brgyRow) brgyRow.style.display = 'flex';
            if (dobRow)  dobRow.style.display  = 'flex';
            hcBrgy.textContent = barangay;
            hcDob.textContent = dob;
        }

        // Position card — fixed positioning uses viewport coordinates directly (no scroll offset)
        const rect = anchor.getBoundingClientRect();

        hoverCard.style.visibility = 'hidden';
        hoverCard.style.display = 'block';
        const cardWidth  = hoverCard.offsetWidth  || 290;
        const cardHeight = hoverCard.offsetHeight || 220;
        hoverCard.style.visibility = '';

        let targetLeft = rect.left + (rect.width / 2) - (cardWidth / 2);
        let targetTop  = rect.top  - cardHeight - 12;

        if (targetLeft < 10) targetLeft = 10;
        if (targetLeft + cardWidth > window.innerWidth - 10)
            targetLeft = window.innerWidth - cardWidth - 10;

        if (rect.top - cardHeight - 12 < 10) {
            targetTop = rect.bottom + 12;
            hoverCard.classList.add('position-below');
        } else {
            hoverCard.classList.remove('position-below');
        }

        hoverCard.style.left = targetLeft + 'px';
        hoverCard.style.top  = targetTop  + 'px';
        hoverCard.style.display = 'block';
        requestAnimationFrame(() => hoverCard.classList.add('active'));
    });

    document.addEventListener('mouseout', function (e) {
        if (!isHoverPopoverZone(e.target)) return;
        if (isHoverPopoverZone(e.relatedTarget)) return;
        scheduleHoverHide(200);
    });

    hoverCard.addEventListener('mouseenter', function () {
        clearTimeout(hideTimeout);
    });

    hoverCard.addEventListener('mouseleave', function (e) {
        if (isHoverPopoverZone(e.relatedTarget)) return;
        scheduleHoverHide(200);
    });

});