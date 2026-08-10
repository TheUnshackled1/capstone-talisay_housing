    const CASE_POSITION = window.CM_CONFIG ? window.CM_CONFIG.casePosition : '';
    const CASE_DESK_MODE = window.CM_CONFIG ? window.CM_CONFIG.caseDeskMode : 'monitor';
    let currentCaseId = null;
    let complainantSearchTimer = null;
    let subjectSearchTimer = null;

    function csrfToken() {
        return document.querySelector('[name=csrfmiddlewaretoken]').value;
    }

    function resetCaseModalSections() {
        ['subjectSection', 'investigationSection', 'referralSection', 'resolutionSection',
            'priorCasesSection', 'respondentSettledLogsSection', 'modalHouseholdMembersWrap', 'caseIntakeEvidenceSection',
            'caseSettlementEvidenceSection'].forEach((id) => {
                const el = document.getElementById(id);
                if (el) el.style.display = 'none';
            });
        const householdList = document.getElementById('modalHouseholdMembersList');
        if (householdList) householdList.innerHTML = '';
        const settledLogsList = document.getElementById('respondentSettledLogsList');
        if (settledLogsList) settledLogsList.innerHTML = '';
        caseIntakeSavedUrls = [];
        caseIntakeSavedIndex = 0;
        caseSettlementViewUrls = [];
        caseSettlementViewIndex = 0;
        const intakeCarousel = document.getElementById('caseIntakeSavedCarousel');
        if (intakeCarousel) intakeCarousel.hidden = true;
        const settlementCarousel = document.getElementById('caseSettlementViewCarousel');
        if (settlementCarousel) settlementCarousel.hidden = true;
    }

    let caseIntakeSavedUrls = [];
    let caseIntakeSavedIndex = 0;
    let caseSettlementViewUrls = [];
    let caseSettlementViewIndex = 0;

    function classifyCaseEvidenceList(evidence) {
        const intake = [];
        const settlement = [];
        (evidence || []).forEach((ev) => {
            const cap = (ev.caption || '').toLowerCase();
            if (cap.includes('initial intake')) {
                intake.push(ev);
            } else {
                settlement.push(ev);
            }
        });
        return { intake, settlement };
    }

    function refreshCaseIntakeSavedCarousel() {
        const carousel = document.getElementById('caseIntakeSavedCarousel');
        const img = document.getElementById('caseIntakeSavedImg');
        const counter = document.getElementById('caseIntakeSavedCounter');
        const prev = document.getElementById('caseIntakeSavedPrev');
        const next = document.getElementById('caseIntakeSavedNext');
        const n = caseIntakeSavedUrls.length;

        if (!carousel || !img) return;
        if (!n) {
            carousel.hidden = true;
            caseIntakeSavedIndex = 0;
            img.removeAttribute('src');
            return;
        }

        carousel.hidden = false;
        if (caseIntakeSavedIndex >= n) caseIntakeSavedIndex = n - 1;
        img.src = caseIntakeSavedUrls[caseIntakeSavedIndex];
        img.alt = 'Intake photo ' + String(caseIntakeSavedIndex + 1) + ' of ' + String(n);
        if (counter) {
            counter.textContent = n > 1 ? String(caseIntakeSavedIndex + 1) + ' / ' + String(n) : '1 photo';
        }
        if (prev) prev.hidden = n <= 1;
        if (next) next.hidden = n <= 1;
    }

    function caseIntakeSavedCarouselStep(delta) {
        const n = caseIntakeSavedUrls.length;
        if (n <= 1) return;
        caseIntakeSavedIndex = (caseIntakeSavedIndex + delta + n) % n;
        refreshCaseIntakeSavedCarousel();
    }

    function refreshCaseSettlementViewCarousel() {
        const carousel = document.getElementById('caseSettlementViewCarousel');
        const img = document.getElementById('caseSettlementViewImg');
        const counter = document.getElementById('caseSettlementViewCounter');
        const prev = document.getElementById('caseSettlementViewPrev');
        const next = document.getElementById('caseSettlementViewNext');
        const n = caseSettlementViewUrls.length;

        if (!carousel || !img) return;
        if (!n) {
            carousel.hidden = true;
            caseSettlementViewIndex = 0;
            img.removeAttribute('src');
            return;
        }

        carousel.hidden = false;
        if (caseSettlementViewIndex >= n) caseSettlementViewIndex = n - 1;
        img.src = caseSettlementViewUrls[caseSettlementViewIndex];
        img.alt = 'Settlement photo ' + String(caseSettlementViewIndex + 1) + ' of ' + String(n);
        if (counter) {
            counter.textContent = n > 1 ? String(caseSettlementViewIndex + 1) + ' / ' + String(n) : '1 photo';
        }
        if (prev) prev.hidden = n <= 1;
        if (next) next.hidden = n <= 1;
    }

    function caseSettlementViewCarouselStep(delta) {
        const n = caseSettlementViewUrls.length;
        if (n <= 1) return;
        caseSettlementViewIndex = (caseSettlementViewIndex + delta + n) % n;
        refreshCaseSettlementViewCarousel();
    }

    function renderCaseIntakeEvidenceOnRecord(evidence) {
        const section = document.getElementById('caseIntakeEvidenceSection');
        const { intake } = classifyCaseEvidenceList(evidence);

        if (!section) return;
        if (!intake.length) {
            section.style.display = 'none';
            caseIntakeSavedUrls = [];
            caseIntakeSavedIndex = 0;
            const carousel = document.getElementById('caseIntakeSavedCarousel');
            if (carousel) carousel.hidden = true;
            return;
        }

        section.style.display = 'block';
        caseIntakeSavedUrls = intake.map((ev) => ev.url).filter(Boolean);
        caseIntakeSavedIndex = 0;
        refreshCaseIntakeSavedCarousel();
    }

    function renderCaseSettlementEvidenceOnRecord(evidence) {
        const section = document.getElementById('caseSettlementEvidenceSection');
        const { settlement } = classifyCaseEvidenceList(evidence);

        if (!section) return;
        if (!settlement.length) {
            section.style.display = 'none';
            caseSettlementViewUrls = [];
            caseSettlementViewIndex = 0;
            const carousel = document.getElementById('caseSettlementViewCarousel');
            if (carousel) carousel.hidden = true;
            return;
        }

        section.style.display = 'block';
        caseSettlementViewUrls = settlement.map((ev) => ev.url).filter(Boolean);
        caseSettlementViewIndex = 0;
        refreshCaseSettlementViewCarousel();
    }

    function renderCaseEvidenceOnMonitor(evidence) {
        renderCaseIntakeEvidenceOnRecord(evidence);
        renderCaseSettlementEvidenceOnRecord(evidence);
        bindCaseEvidenceViewControls();
    }

    function bindCaseEvidenceViewControls() {
        if (window._staffCaseEvidenceViewBound) return;
        window._staffCaseEvidenceViewBound = true;
        document.getElementById('caseIntakeSavedPrev')?.addEventListener('click', () => caseIntakeSavedCarouselStep(-1));
        document.getElementById('caseIntakeSavedNext')?.addEventListener('click', () => caseIntakeSavedCarouselStep(1));
        document.getElementById('caseSettlementViewPrev')?.addEventListener('click', () => caseSettlementViewCarouselStep(-1));
        document.getElementById('caseSettlementViewNext')?.addEventListener('click', () => caseSettlementViewCarouselStep(1));
    }

    function isMonitorCaseDesk(c) {
        return CASE_DESK_MODE === 'monitor' || !!(c && c.workflow && c.workflow.is_monitor_desk);
    }

    function openCaseModal(caseId) {
        currentCaseId = caseId;
        document.getElementById('newCaseModal').style.display = 'none';
        resetCaseModalSections();
        document.body.style.overflow = 'hidden';
        fetch(`/cases/${CASE_POSITION}/${caseId}/details/`)
            .then((r) => r.json())
            .then((d) => {
                if (d.success) populateCaseModal(d.case);
                else alert('Error: ' + d.error);
            });
    }

    function escapeHtml(value) {
        return String(value ?? '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    function staffAvatarClass(positionKey) {
        if (positionKey === 'second_member') return 'second-member';
        if (positionKey === 'fourth_member') return 'fourth-member';
        if (positionKey === 'ronda') return 'ronda';
        return 'other';
    }

    function populateResolutionMonitorCard(c) {
        const section = document.getElementById('resolutionSection');
        const notesEl = document.getElementById('modalResolutionNotes');
        const dateEl = document.getElementById('modalResolvedDate');
        if (!section) return;

        const isResolved = c.status === 'resolved' || c.status === 'closed';
        const hasNotes = !!(c.resolution_notes && String(c.resolution_notes).trim());
        const hasDate = !!c.resolved_at;

        if (!isResolved && !hasNotes && !hasDate) {
            section.style.display = 'none';
            if (notesEl) notesEl.textContent = 'â€”';
            if (dateEl) dateEl.textContent = '';
            return;
        }

        section.style.display = 'block';
        if (notesEl) {
            notesEl.textContent = hasNotes ? c.resolution_notes.trim() : 'Case resolved.';
        }
        if (dateEl) {
            dateEl.textContent = hasDate
                ? `Resolved: ${new Date(c.resolved_at).toLocaleDateString()}`
                : '';
        }
    }

    function populateCaseModal(c) {
        const filed = new Date(c.received_at);
        document.getElementById('modalCaseNumber').textContent = c.case_number;
        const statusEl = document.getElementById('modalStatusBadge');
        if (statusEl) {
            statusEl.textContent = c.status_display;
            statusEl.className = `case-status-pill case-status-pill--${c.status}`;
        }
        const filedMeta = document.getElementById('modalFiledMeta');
        if (filedMeta) {
            let filedText = `Filed ${filed.toLocaleDateString()} Â· ${filed.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}`;
            if (c.received_by) {
                filedText += ` Â· Recorded by ${c.received_by}`;
                if (c.received_by_position) filedText += ` (${c.received_by_position})`;
            }
            filedMeta.textContent = filedText;
        }
        const deskBadge = document.getElementById('modalDeskBadge');
        if (deskBadge) deskBadge.style.display = 'inline-block';

        const avatarEl = document.getElementById('modalStaffAvatar');
        const staffName = c.received_by || 'Unassigned';
        const staffRole = c.received_by_position || 'â€”';
        const initials = c.received_by_initials || (staffName !== 'Unassigned' ? staffName.slice(0, 2).toUpperCase() : 'â€”');
        if (avatarEl) {
            avatarEl.textContent = initials;
            avatarEl.className = `handled-by-avatar ${staffAvatarClass(c.received_by_position_key || '')}`;
        }
        const staffNameEl = document.getElementById('modalStaffName');
        const staffRoleEl = document.getElementById('modalStaffRole');
        if (staffNameEl) staffNameEl.textContent = staffName;
        if (staffRoleEl) staffRoleEl.textContent = staffRole;

        document.getElementById('modalComplainantName').textContent = c.complainant_name;
        document.getElementById('modalComplainantPhone').textContent = c.complainant_phone || 'â€”';
        document.getElementById('modalComplainantRef').textContent = c.complainant_reference || 'â€”';
        document.getElementById('modalComplainantUnit').textContent = c.complainant_unit_label || 'â€”';

        const profile = c.beneficiary_profile;
        const sexEl = document.getElementById('modalBeneficiarySex');
        const householdEl = document.getElementById('modalBeneficiaryHousehold');
        const householdWrap = document.getElementById('modalHouseholdMembersWrap');
        const householdList = document.getElementById('modalHouseholdMembersList');
        if (sexEl) sexEl.textContent = profile?.sex_display || 'â€”';
        if (householdEl) {
            const n = profile?.household_members;
            householdEl.textContent = n != null ? `${n} member${n === 1 ? '' : 's'}` : 'â€”';
        }
        if (householdWrap && householdList) {
            const rows = profile?.household_member_rows || [];
            if (rows.length) {
                householdWrap.style.display = 'block';
                householdList.innerHTML = `
                    <table class="modal-household-table">
                        <thead><tr><th>Name</th><th>Relationship</th><th>Sex</th></tr></thead>
                        <tbody>
                            ${rows.map((m) => `
                                <tr>
                                    <td style="font-weight:600;">${escapeHtml(m.name || 'â€”')}</td>
                                    <td>${escapeHtml(m.relationship || 'â€”')}</td>
                                    <td>${escapeHtml(m.sex_display || 'â€”')}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>`;
            } else {
                householdWrap.style.display = 'none';
                householdList.innerHTML = '';
            }
        }
        document.getElementById('modalDescription').textContent = c.initial_description || 'â€”';
        const typeEl = document.getElementById('modalComplaintType');
        if (typeEl) {
            typeEl.innerHTML = `<span class="case-type-pill">${escapeHtml(c.case_type_display)}</span>`;
        }

        const subjectSection = document.getElementById('subjectSection');
        if (c.subject_name && subjectSection) {
            subjectSection.style.display = 'block';
            document.getElementById('modalSubjectName').textContent = c.subject_name;
            document.getElementById('modalSubjectPhone').textContent = c.subject_phone || 'â€”';
            document.getElementById('modalSubjectRef').textContent = c.subject_reference || 'â€”';
            document.getElementById('modalSubjectUnit').textContent = c.subject_unit_label || 'â€”';

            const sProfile = c.subject_profile;
            const sSexEl = document.getElementById('modalSubjectSex');
            const sHouseholdEl = document.getElementById('modalSubjectHousehold');
            const sHouseholdWrap = document.getElementById('modalSubjectHouseholdMembersWrap');
            const sHouseholdList = document.getElementById('modalSubjectHouseholdMembersList');
            if (sSexEl) sSexEl.textContent = sProfile?.sex_display || 'â€”';
            if (sHouseholdEl) {
                const n = sProfile?.household_members;
                sHouseholdEl.textContent = n != null ? `${n} member${n === 1 ? '' : 's'}` : 'â€”';
            }
            if (sHouseholdWrap && sHouseholdList) {
                const rows = sProfile?.household_member_rows || [];
                if (rows.length) {
                    sHouseholdWrap.style.display = 'block';
                    sHouseholdList.innerHTML = `
                        <table class="modal-household-table">
                            <thead><tr><th>Name</th><th>Relationship</th><th>Sex</th></tr></thead>
                            <tbody>
                                ${rows.map((m) => `
                                    <tr>
                                        <td style="font-weight:600;">${escapeHtml(m.name || 'â€”')}</td>
                                        <td>${escapeHtml(m.relationship || 'â€”')}</td>
                                        <td>${escapeHtml(m.sex_display || 'â€”')}</td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>`;
                } else {
                    sHouseholdWrap.style.display = 'none';
                    sHouseholdList.innerHTML = '';
                }
            }
        } else if (subjectSection) {
            subjectSection.style.display = 'none';
        }

        const investigationSection = document.getElementById('investigationSection');
        if (c.investigation_notes && investigationSection) {
            investigationSection.style.display = 'block';
            document.getElementById('modalInvestigationNotes').textContent = c.investigation_notes;
            const invByEl = document.getElementById('modalInvestigatedBy');
            if (invByEl) {
                if (c.investigated_by) {
                    invByEl.textContent = `Investigated by: ${c.investigated_by}`;
                    invByEl.style.display = 'block';
                } else {
                    invByEl.textContent = '';
                    invByEl.style.display = 'none';
                }
            }
        } else if (investigationSection) {
            investigationSection.style.display = 'none';
        }

        if (c.referred_to) {
            document.getElementById('referralSection').style.display = 'block';
            document.getElementById('modalReferredTo').textContent = `Referred to: ${c.referred_to}`;
            document.getElementById('modalReferralNotes').textContent = c.referral_notes || '';
            document.getElementById('modalReferralDate').textContent = c.referred_at
                ? `Referred: ${new Date(c.referred_at).toLocaleDateString()}` : '';
        }

        populateResolutionMonitorCard(c);

        const settledLogsSection = document.getElementById('respondentSettledLogsSection');
        const settledLogsList = document.getElementById('respondentSettledLogsList');
        const settledLogs = c.respondent_settled_incident_logs || [];
        if (settledLogsSection && settledLogsList) {
            if (c.subject_name && settledLogs.length) {
                settledLogsSection.style.display = 'block';
                settledLogsList.innerHTML = settledLogs.map((log) => {
                    const when = log.logged_at
                        ? new Date(log.logged_at).toLocaleDateString()
                        : '';
                    const unit = log.respondent_unit_label || log.unit_label || 'â€”';
                    return `
                    <tr>
                        <td>${escapeHtml(when)}</td>
                        <td>${escapeHtml(unit)}</td>
                        <td>${escapeHtml(log.case_type_display || 'â€”')}</td>
                        <td>${escapeHtml(log.description || 'â€”')}</td>
                    </tr>`;
                }).join('');
            } else {
                settledLogsSection.style.display = 'none';
                settledLogsList.innerHTML = '';
            }
        }

        const priorSection = document.getElementById('priorCasesSection');
        const priorList = document.getElementById('priorCasesList');
        if (priorSection && priorList) {
            if (c.prior_cases && c.prior_cases.length) {
                priorSection.style.display = 'block';
                priorList.innerHTML = c.prior_cases.map((pc) => `
                    <button type="button" class="prior-case-item" onclick="openCaseModal('${pc.id}')">
                        <strong>${escapeHtml(pc.case_number)}</strong>
                        â€” ${escapeHtml(pc.case_type_display)} Â· ${escapeHtml(pc.status_display)}
                    </button>`).join('');
            } else {
                priorSection.style.display = 'none';
                priorList.innerHTML = '';
            }
        }

        renderCaseEvidenceOnMonitor(c.evidence || []);

        const modal = document.getElementById('caseModal');
        modal.style.display = 'flex';
        document.body.style.overflow = 'hidden';
    }

    function postCaseUpdate(body) {
        return fetch(`/cases/${CASE_POSITION}/update/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() },
            body: JSON.stringify({ case_id: currentCaseId, ...body }),
        }).then((r) => r.json());
    }

    function reloadCaseModal() {
        if (currentCaseId) openCaseModal(currentCaseId);
    }

    function scrollToCaseDetails() {
        document.querySelector('.tha-case-view-modal .case-record-card')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    function scrollToCaseEvidence() {
        document.getElementById('evidenceSection')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    function renderCaseMonitorPanel(c, wf) {
        const section = document.getElementById('monitorSection');
        const workflowSection = document.getElementById('workflowSection');
        if (workflowSection) workflowSection.style.display = 'none';
        if (!section) return;
        section.style.display = 'block';

        const alertsEl = document.getElementById('monitorAlerts');
        if (alertsEl) {
            const alerts = wf.monitoring_alerts || [];
            alertsEl.innerHTML = alerts.length
                ? alerts.map((a) => `
                    <p class="case-workflow-alert case-workflow-alert--${escapeHtml(a.level || 'info')}">${escapeHtml(a.text)}</p>
                `).join('')
                : '';
        }

        const logEl = document.getElementById('monitorActionsLogList');
        if (logEl) {
            const log = wf.actions_log || [];
            logEl.innerHTML = log.length
                ? log.map((row) => `
                    <div class="case-actions-log-item">
                        <strong>${escapeHtml(row.label)}</strong>
                        ${row.details ? `<div>${escapeHtml(row.details)}</div>` : ''}
                        <div class="case-evidence-meta">${escapeHtml(row.created_by)} Â· ${new Date(row.created_at).toLocaleString()}</div>
                    </div>
                `).join('')
                : '<p class="case-evidence-empty">No desk actions recorded yet.</p>';
        }
    }

    function renderCaseWorkflow(c) {
        const wf = c.workflow || {};
        if (isMonitorCaseDesk(c)) {
            renderCaseMonitorPanel(c, wf);
            return;
        }

        const section = document.getElementById('workflowSection');
        const monitorSection = document.getElementById('monitorSection');
        if (monitorSection) monitorSection.style.display = 'none';
        if (!section) return;

        if (!wf.can_manage_workflow) {
            section.style.display = 'none';
            return;
        }
        section.style.display = 'block';

        const engNote = document.getElementById('engineeringReferralNote');
        if (engNote) engNote.style.display = wf.show_engineering_note ? 'block' : 'none';

        const alertsEl = document.getElementById('workflowAlerts');
        if (alertsEl) {
            const alerts = wf.monitoring_alerts || [];
            alertsEl.innerHTML = alerts.map((a) => `
                <p class="case-workflow-alert case-workflow-alert--${escapeHtml(a.level || 'info')}">${escapeHtml(a.text)}</p>
            `).join('');
        }

        const reviewInput = document.getElementById('reviewNotesInput');
        if (reviewInput) reviewInput.value = c.investigation_notes || '';

        const guideEl = document.getElementById('typeActionsGuide');
        if (guideEl) guideEl.textContent = wf.type_action_guide || '';

        const terminal = !!wf.is_terminal;
        const pending = c.status === 'pending_review';

        const transBtns = document.getElementById('workflowTransitionBtns');
        if (transBtns) {
            const buttons = wf.workflow_buttons || [];
            transBtns.innerHTML = buttons.length
                ? buttons.map((b) => `
                    <button type="button" class="case-wf-btn ${b.style === 'primary' ? 'case-wf-btn--primary' : ''}"
                        ${terminal ? 'disabled' : ''} onclick="runWorkflowTransition('${b.transition}')">${escapeHtml(b.label)}</button>
                `).join('')
                : '<span class="case-workflow-hint">No status transition available.</span>';
        }

        const typeBtns = document.getElementById('typeActionBtns');
        if (typeBtns) {
            const actions = wf.allowed_actions || [];
            typeBtns.innerHTML = actions.length
                ? actions.map((a) => {
                    const refer = a.code === 'refer_engineering';
                    const cls = refer ? 'case-wf-btn case-wf-btn--refer' : 'case-wf-btn case-wf-btn--primary';
                    const disabled = terminal || pending;
                    return `<button type="button" class="${cls}" ${disabled ? 'disabled' : ''} onclick="recordCaseAction('${a.code}')">${escapeHtml(a.label)}</button>`;
                }).join('')
                : '<span class="case-workflow-hint">No type-specific actions for this complaint.</span>';
        }

        const actionInput = document.getElementById('actionDetailsInput');
        if (actionInput) actionInput.disabled = terminal || pending;

        const logEl = document.getElementById('actionsLogList');
        if (logEl) {
            const log = wf.actions_log || [];
            logEl.innerHTML = log.length
                ? log.map((row) => `
                    <div class="case-actions-log-item">
                        <strong>${escapeHtml(row.label)}</strong>
                        ${row.details ? `<div>${escapeHtml(row.details)}</div>` : ''}
                        <div class="case-evidence-meta">${escapeHtml(row.created_by)} Â· ${new Date(row.created_at).toLocaleString()}</div>
                    </div>
                `).join('')
                : '<p class="case-evidence-empty">No desk actions recorded yet.</p>';
        }
    }

    function runWorkflowTransition(transition) {
        postCaseUpdate({ action: 'workflow_transition', transition })
            .then((d) => {
                if (!d.success) { alert(d.error || 'Update failed'); return; }
                alert(d.message || 'Status updated');
                reloadCaseModal();
            })
            .catch(() => alert('Could not update case.'));
    }

    function recordCaseAction(actionType) {
        const details = document.getElementById('actionDetailsInput')?.value.trim() || '';
        if (actionType === 'refer_engineering' && !details) {
            if (!confirm('Record City Engineering referral in the system? Add remarks below if needed, then click again.')) return;
        }
        postCaseUpdate({ action: 'record_action', action_type: actionType, details })
            .then((d) => {
                if (!d.success) { alert(d.error || 'Action failed'); return; }
                alert(d.message || 'Action recorded');
                reloadCaseModal();
            })
            .catch(() => alert('Could not record action.'));
    }

    function saveCaseReviewNotes() {
        const review_notes = document.getElementById('reviewNotesInput')?.value.trim() || '';
        if (!review_notes) {
            alert('Enter review notes before saving.');
            return;
        }
        postCaseUpdate({ action: 'save_review', review_notes })
            .then((d) => {
                if (!d.success) { alert(d.error || 'Could not save'); return; }
                alert(d.message || 'Remarks saved');
                reloadCaseModal();
            })
            .catch(() => alert('Could not save remarks.'));
    }

    function resolveCasePrompt() {
        const resolution_notes = prompt('Resolution outcome (required):');
        if (!resolution_notes || !resolution_notes.trim()) return;
        postCaseUpdate({ action: 'workflow_transition', transition: 'resolve', resolution_notes: resolution_notes.trim() })
            .then((d) => {
                if (!d.success) { caseFlowAlert(d.error || 'Could not resolve', 'Error', 'warning'); return; }
                caseFlowAlert(d.message || 'Case resolved', 'Success', 'success');
                reloadCaseModal();
            })
            .catch(() => caseFlowAlert('Could not resolve case.', 'Error', 'warning'));
    }

    function closeCasePrompt() {
        const closure_outcome = prompt('Closure summary (required â€” case must be resolved first):');
        if (!closure_outcome || !closure_outcome.trim()) return;
        postCaseUpdate({ action: 'workflow_transition', transition: 'close', closure_outcome: closure_outcome.trim() })
            .then((d) => {
                if (!d.success) { caseFlowAlert(d.error || 'Could not close', 'Error', 'warning'); return; }
                caseFlowAlert(d.message || 'Case closed', 'Success', 'success');
                reloadCaseModal();
            })
            .catch(() => caseFlowAlert('Could not close case.', 'Error', 'warning'));
    }

    function closeCaseModal(e) {
        if (e && e.target.id !== 'caseModal') return;
        document.getElementById('caseModal').style.display = 'none';
        document.body.style.overflow = '';
    }

    function openNewCaseModal() {
        const caseModal = document.getElementById('caseModal');
        if (caseModal) caseModal.style.display = 'none';
        resetNewCaseForm();
        document.body.style.overflow = 'hidden';
        document.getElementById('newCaseModal').style.display = 'flex';
    }

    function closeNewCaseModal(e) {
        if (e && e.target.id !== 'newCaseModal') return;
        document.getElementById('newCaseModal').style.display = 'none';
        document.body.style.overflow = '';
    }

    function setReadonlyField(id, value) {
        const el = document.getElementById(id);
        if (el) el.value = value || '';
    }

    function clearComplainantAutoFill() {
        ['complainantAutoName', 'complainantAutoRef', 'complainantAutoUnit', 'complainantAutoPhone'].forEach((id) => setReadonlyField(id, ''));
        document.getElementById('complainantAutoFill')?.classList.remove('is-linked');
    }

    function getSelectedComplainantApplicantId() {
        return (document.getElementById('complainantApplicantId')?.value || '').trim();
    }

    function isSameApplicantAsComplainant(applicantId) {
        const cid = getSelectedComplainantApplicantId();
        return !!(cid && applicantId && String(applicantId) === cid);
    }

    function filterOutComplainantFromResults(results) {
        const cid = getSelectedComplainantApplicantId();
        if (!cid) return results;
        return results.filter((row) => String(row.id) !== cid);
    }

    function applyBeneficiarySelection(row) {
        document.getElementById('complainantApplicantId').value = row.id || '';
        document.getElementById('relatedUnitId').value = row.unit_id || '';
        document.getElementById('newComplainantName').value = row.full_name || '';
        document.getElementById('newComplainantPhone').value = row.phone_number || '';
        setReadonlyField('complainantAutoName', row.full_name);
        setReadonlyField('complainantAutoRef', row.reference_number);
        setReadonlyField('complainantAutoUnit', row.unit_label);
        setReadonlyField('complainantAutoPhone', row.phone_number);
        const panel = document.getElementById('complainantAutoFill');
        if (panel) panel.classList.add('is-linked');
        document.getElementById('complainantSearchResults').style.display = 'none';
        document.getElementById('complainantSearchInput').value = row.full_name || '';
        if (isSameApplicantAsComplainant(document.getElementById('subjectApplicantId')?.value)) {
            clearSubjectAutoFill();
            document.getElementById('subjectApplicantId').value = '';
            document.getElementById('newSubjectName').value = '';
            document.getElementById('subjectSearchInput').value = '';
        }
    }

    function clearSubjectAutoFill() {
        ['subjectAutoName', 'subjectAutoRef', 'subjectAutoUnit'].forEach((id) => setReadonlyField(id, ''));
        document.getElementById('subjectAutoFill')?.classList.remove('is-linked');
    }

    function applySubjectSelection(row) {
        if (isSameApplicantAsComplainant(row.id)) {
            alert('Reported party cannot be the same person as the complainant. Choose a different occupant or leave reported party blank.');
            return;
        }
        document.getElementById('subjectApplicantId').value = row.id || '';
        document.getElementById('newSubjectName').value = row.full_name || '';
        setReadonlyField('subjectAutoName', row.full_name);
        setReadonlyField('subjectAutoRef', row.reference_number);
        setReadonlyField('subjectAutoUnit', row.unit_label);
        document.getElementById('subjectAutoFill')?.classList.add('is-linked');
        document.getElementById('subjectSearchResults').style.display = 'none';
        document.getElementById('subjectSearchInput').value = row.full_name || '';
    }

    function updateDescCount() {
        const el = document.getElementById('newDescription');
        const c = document.getElementById('newDescriptionCount');
        if (el && c) c.textContent = `${(el.value || '').length} / 100`;
    }

    function resetNewCaseForm() {
        ['complainantSearchInput', 'newDescription', 'subjectSearchInput'].forEach((id) => {
            const el = document.getElementById(id);
            if (el) el.value = '';
        });
        ['complainantApplicantId', 'relatedUnitId', 'subjectApplicantId', 'newComplainantName', 'newComplainantPhone', 'newSubjectName'].forEach((id) => {
            const el = document.getElementById(id);
            if (el) el.value = '';
        });
        const typeEl = document.getElementById('newCaseType');
        if (typeEl) typeEl.value = '';
        ['complainantSearchResults', 'subjectSearchResults'].forEach((id) => {
            const el = document.getElementById(id);
            if (el) { el.style.display = 'none'; el.innerHTML = ''; }
        });
        clearComplainantAutoFill();
        clearSubjectAutoFill();
        updateDescCount();
    }

    function formatHousingBeneficiaryRow(row) {
        const parts = [];
        if (row.lot_map_label) parts.push(row.lot_map_label);
        if (row.reference_number) parts.push(row.reference_number);
        if (row.unit_label && !row.lot_map_label) parts.push(row.unit_label);
        if (row.site_name) parts.push(row.site_name);
        const meta = parts.join(' Â· ') || 'Occupied unit';
        return `<strong>${row.full_name}</strong><br><span style="color: #64748b;">${meta}</span>`;
    }

    function bindBeneficiarySearchResults(box, results, onSelect) {
        box.innerHTML = results.map((row, i) => `
        <button type="button" data-index="${i}" style="display: block; width: 100%; text-align: left; padding: 0.5rem 0.65rem; border: none; border-bottom: 1px solid #f1f5f9; background: #fff; cursor: pointer; font-size: 0.8rem;">
            ${formatHousingBeneficiaryRow(row)}
        </button>`).join('');
        box.style.display = 'block';
        box.querySelectorAll('button').forEach((btn) => {
            const idx = parseInt(btn.dataset.index, 10);
            btn.onclick = () => onSelect(results[idx]);
        });
    }

    function runBeneficiarySearch(q, box, onSelect, options = {}) {
        if (!box) return;
        q = (q || '').trim();
        const excludeComplainant = !!options.excludeComplainant;
        box.innerHTML = '<p style="padding:0.5rem;font-size:0.8rem;color:#64748b;margin:0;">Loadingâ€¦</p>';
        box.style.display = 'block';
        fetch(`/cases/${CASE_POSITION}/beneficiary-search/?q=${encodeURIComponent(q)}`)
            .then((r) => r.json())
            .then((d) => {
                if (!d.success) {
                    box.innerHTML = '<p style="padding: 0.5rem; font-size: 0.8rem; color: #64748b; margin: 0;">Search failed.</p>';
                    box.style.display = 'block';
                    return;
                }
                let results = d.results || [];
                if (excludeComplainant) {
                    results = filterOutComplainantFromResults(results);
                }
                if (!results.length) {
                    let emptyMsg = q
                        ? 'No matches. Try name, APP ref, or lot (1-1).'
                        : 'No occupied housing units in the system yet.';
                    if (excludeComplainant && (d.results || []).length) {
                        emptyMsg = 'No other occupants match. The complainant cannot be selected as reported party.';
                    } else if (excludeComplainant && getSelectedComplainantApplicantId()) {
                        emptyMsg = 'Select complainant first, then pick a different person as reported party.';
                    }
                    box.innerHTML = `<p style="padding: 0.5rem; font-size: 0.8rem; color: #64748b; margin: 0;">${emptyMsg}</p>`;
                    box.style.display = 'block';
                    return;
                }
                bindBeneficiarySearchResults(box, results, onSelect);
            })
            .catch(() => {
                box.innerHTML = '<p style="padding:0.5rem;font-size:0.8rem;color:#b91c1c;margin:0;">Search failed.</p>';
                box.style.display = 'block';
            });
    }

    function runComplainantSearch(q) {
        runBeneficiarySearch(q, document.getElementById('complainantSearchResults'), applyBeneficiarySelection);
    }

    function runSubjectSearch(q) {
        if (!getSelectedComplainantApplicantId()) {
            const box = document.getElementById('subjectSearchResults');
            if (box) {
                box.innerHTML = '<p style="padding: 0.5rem; font-size: 0.8rem; color: #64748b; margin: 0;">Select the complainant first.</p>';
                box.style.display = 'block';
            }
            return;
        }
        runBeneficiarySearch(q, document.getElementById('subjectSearchResults'), applySubjectSelection, { excludeComplainant: true });
    }

    function createNewCase() {
        const data = {
            complainant_name: document.getElementById('newComplainantName').value.trim(),
            complainant_phone: document.getElementById('newComplainantPhone').value.trim(),
            case_type: document.getElementById('newCaseType').value,
            received_at_location: document.getElementById('newReceivedAt').value,
            initial_description: document.getElementById('newDescription').value.trim(),
            subject_name: document.getElementById('newSubjectName').value.trim(),
            complainant_applicant_id: document.getElementById('complainantApplicantId').value,
            subject_applicant_id: document.getElementById('subjectApplicantId').value,
            related_unit_id: document.getElementById('relatedUnitId').value,
        };
        const linked = document.getElementById('complainantApplicantId')?.value;
        if (!linked) {
            alert('Search and select a complainant from the housing unit list.');
            return;
        }
        const subjectId = (document.getElementById('subjectApplicantId')?.value || '').trim();
        if (!subjectId) {
            alert('Search and select a reported party from the housing unit list.');
            return;
        }
        if (subjectId === linked) {
            alert('Reported party cannot be the same person as the complainant.');
            return;
        }
        if (!data.complainant_name || !data.case_type || !data.initial_description) {
            alert('Fill required fields: complainant, reported party, complaint type, and incident description.');
            return;
        }
        if (data.initial_description.length > 100) {
            alert('Incident description must be 100 characters or less.');
            return;
        }
        fetch(`/cases/${CASE_POSITION}/create/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() },
            body: JSON.stringify(data),
        })
            .then((r) => r.json())
            .then((d) => {
                if (!d.success) {
                    alert('Error: ' + (d.error || 'Could not create case'));
                    return;
                }
                if (window.CaseDeskSync) window.CaseDeskSync.notifyChange();
                showCaseRecordedSuccess(d.case, d.message);
            })
            .catch(() => alert('Could not create case. Try again.'));
    }

    function uploadCaseEvidence() {
        const fileInput = document.getElementById('evidenceFile');
        if (!fileInput?.files?.[0]) {
            alert('Choose a file to upload.');
            return;
        }
        const fd = new FormData();
        fd.append('file', fileInput.files[0]);
        fd.append('caption', document.getElementById('evidenceCaption')?.value.trim() || '');
        fetch(`/cases/${CASE_POSITION}/${currentCaseId}/evidence/upload/`, {
            method: 'POST',
            headers: { 'X-CSRFToken': csrfToken() },
            body: fd,
        })
            .then((r) => r.json())
            .then((d) => {
                if (d.success) {
                    alert(d.message);
                    openCaseModal(currentCaseId);
                } else alert(d.error || 'Upload failed');
            });
    }

    function viewSettledIncidentLog(btn) {
        if (!btn) return;
        const complainantUnit = btn.getAttribute('data-complainant-unit-label')
            || btn.getAttribute('data-unit-label')
            || 'â€”';
        const respondentUnit = btn.getAttribute('data-respondent-unit-label') || 'â€”';
        const complainant = btn.getAttribute('data-complainant-name') || 'â€”';
        const respondent = btn.getAttribute('data-respondent-name') || 'â€”';
        const typeDisplay = btn.getAttribute('data-case-type-display') || 'â€”';
        const description = btn.getAttribute('data-description') || 'â€”';
        const loggedAt = btn.getAttribute('data-logged-at') || 'â€”';
        const loggedBy = btn.getAttribute('data-logged-by') || 'Field';

        // Populate fields
        let loggedText = `Logged: ${loggedAt}`;
        if (loggedBy && loggedBy !== 'â€”') {
            loggedText += ` Â· Recorded by ${loggedBy}`;
            if (loggedBy !== 'Field') {
                loggedText += ` (Field Personnel)`;
            }
        }
        document.getElementById('settledIncidentLoggedMeta').textContent = loggedText;
        document.getElementById('settledIncidentStaffName').textContent = loggedBy;

        const initials = loggedBy !== 'Field' ? loggedBy.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2) : 'FC';
        document.getElementById('settledIncidentStaffAvatar').textContent = initials;

        document.getElementById('settledIncidentSubjectName').textContent = respondent;
        document.getElementById('settledIncidentComplainantName').textContent = complainant;
        document.getElementById('settledIncidentComplainantUnit').textContent = complainantUnit;

        const subjUnitEl = document.getElementById('settledIncidentSubjectUnit');
        const subjUnitWrap = document.getElementById('settledIncidentSubjectUnitWrap');
        if (subjUnitEl && subjUnitWrap) {
            if (respondent && respondent !== 'â€”' && respondent !== '') {
                subjUnitEl.textContent = respondentUnit || 'â€”';
                subjUnitWrap.style.display = 'block';
            } else {
                subjUnitWrap.style.display = 'none';
            }
        }

        document.getElementById('settledIncidentComplaintType').innerHTML = `<span class="case-type-pill">${typeDisplay}</span>`;
        document.getElementById('settledIncidentDescription').textContent = description;

        // Open modal
        document.getElementById('settledIncidentModal').style.display = 'flex';
        document.body.style.overflow = 'hidden';
    }

    function closeSettledIncidentModal(e) {
        if (e && e.target.id !== 'settledIncidentModal') return;
        const modal = document.getElementById('settledIncidentModal');
        if (modal) modal.style.display = 'none';
        const caseModalOpen = document.getElementById('caseModal')?.style.display === 'flex';
        const newCaseModalOpen = document.getElementById('newCaseModal')?.style.display === 'flex';
        if (!caseModalOpen && !newCaseModalOpen) {
            document.body.style.overflow = '';
        }
    }

    function setQuickStatusFilter(status) {
        const url = new URL(window.location.href);
        const q = document.getElementById('searchInput')?.value.trim() || '';
        const t = document.getElementById('typeFilter')?.value || 'all';
        if (q) url.searchParams.set('q', q);
        else url.searchParams.delete('q');
        if (t && t !== 'all') url.searchParams.set('type', t);
        else url.searchParams.delete('type');
        if (status && status !== 'all') {
            url.searchParams.set('status', status);
        } else {
            url.searchParams.delete('status');
        }
        url.searchParams.delete('tab');
        window.location.href = url.toString();
    }

    function applyCaseFilters() {
        const url = new URL(window.location.href);
        const q = document.getElementById('searchInput')?.value.trim() || '';
        const t = document.getElementById('typeFilter')?.value || 'all';
        if (q) url.searchParams.set('q', q);
        else url.searchParams.delete('q');
        if (t && t !== 'all') url.searchParams.set('type', t);
        else url.searchParams.delete('type');
        url.searchParams.delete('tab');
        window.location.href = url.toString();
    }

    function printCaseRecord() {
        window.print();
    }

    function bindBeneficiarySearchFocus(inputId, runSearch) {
        const input = document.getElementById(inputId);
        if (!input) return;
        const openList = () => runSearch((input.value || '').trim());
        input.addEventListener('focus', openList);
        input.addEventListener('click', openList);
    }

    bindBeneficiarySearchFocus('complainantSearchInput', runComplainantSearch);
    bindBeneficiarySearchFocus('subjectSearchInput', runSubjectSearch);

    document.getElementById('complainantSearchInput')?.addEventListener('input', (e) => {
        clearTimeout(complainantSearchTimer);
        const q = e.target.value.trim();
        complainantSearchTimer = setTimeout(() => runComplainantSearch(q), 300);
    });

    document.getElementById('subjectSearchInput')?.addEventListener('input', (e) => {
        clearTimeout(subjectSearchTimer);
        const q = e.target.value.trim();
        subjectSearchTimer = setTimeout(() => runSubjectSearch(q), 300);
    });

    document.getElementById('searchInput')?.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') applyCaseFilters();
    });

    document.getElementById('typeFilter')?.addEventListener('change', applyCaseFilters);

    function anyCaseDeskDrawerOpen() {
        return document.getElementById('resolvedCasesDrawer')?.classList.contains('is-open')
            || document.getElementById('settledIncidentsDrawer')?.classList.contains('is-open')
            || document.getElementById('pendingCasesDrawer')?.classList.contains('is-open');
    }

    function restoreCaseDeskBodyScroll() {
        const caseModalOpen = document.getElementById('caseModal')?.style.display === 'flex';
        const newCaseModalOpen = document.getElementById('newCaseModal')?.style.display === 'flex';
        const settledModalOpen = document.getElementById('settledIncidentModal')?.style.display === 'flex';
        if (!caseModalOpen && !newCaseModalOpen && !settledModalOpen && !anyCaseDeskDrawerOpen()) {
            document.body.style.overflow = '';
        }
    }

    function openPendingCasesDrawer() {
        closeResolvedCasesDrawer();
        closeSettledIncidentsDrawer();
        const drawer = document.getElementById('pendingCasesDrawer');
        const btn = document.getElementById('pendingKpiBtn');
        if (!drawer) return;
        drawer.classList.add('is-open');
        document.body.style.overflow = 'hidden';
        if (btn) {
            btn.classList.add('is-active');
            btn.setAttribute('aria-expanded', 'true');
        }
    }

    function closePendingCasesDrawer(e) {
        if (e && e.target && e.target.id !== 'pendingCasesDrawer') return;
        const drawer = document.getElementById('pendingCasesDrawer');
        const btn = document.getElementById('pendingKpiBtn');
        if (!drawer) return;
        drawer.classList.remove('is-open');
        if (btn) {
            btn.classList.remove('is-active');
            btn.setAttribute('aria-expanded', 'false');
        }
        restoreCaseDeskBodyScroll();
    }

    function openResolvedCasesDrawer() {
        closePendingCasesDrawer();
        closeSettledIncidentsDrawer();
        const drawer = document.getElementById('resolvedCasesDrawer');
        const btn = document.getElementById('resolvedKpiBtn');
        if (!drawer) return;
        drawer.classList.add('is-open');
        document.body.style.overflow = 'hidden';
        if (btn) {
            btn.classList.add('is-active');
            btn.setAttribute('aria-expanded', 'true');
        }
    }

    function closeResolvedCasesDrawer(e) {
        if (e && e.target && e.target.id !== 'resolvedCasesDrawer') return;
        const drawer = document.getElementById('resolvedCasesDrawer');
        const btn = document.getElementById('resolvedKpiBtn');
        if (!drawer) return;
        drawer.classList.remove('is-open');
        if (btn) {
            btn.classList.remove('is-active');
            btn.setAttribute('aria-expanded', 'false');
        }
        restoreCaseDeskBodyScroll();
    }

    function openSettledIncidentsDrawer() {
        closePendingCasesDrawer();
        closeResolvedCasesDrawer();
        const drawer = document.getElementById('settledIncidentsDrawer');
        const btn = document.getElementById('settledOnSiteKpiBtn');
        if (!drawer) return;
        drawer.classList.add('is-open');
        document.body.style.overflow = 'hidden';
        if (btn) {
            btn.classList.add('is-active');
            btn.setAttribute('aria-expanded', 'true');
        }
    }

    function closeSettledIncidentsDrawer(e) {
        if (e && e.target && e.target.id !== 'settledIncidentsDrawer') return;
        const drawer = document.getElementById('settledIncidentsDrawer');
        const btn = document.getElementById('settledOnSiteKpiBtn');
        if (!drawer) return;
        drawer.classList.remove('is-open');
        if (btn) {
            btn.classList.remove('is-active');
            btn.setAttribute('aria-expanded', 'false');
        }
        restoreCaseDeskBodyScroll();
    }

    function openCaseFromPendingDrawer(caseId) {
        closePendingCasesDrawer();
        openCaseModal(caseId);
    }

    function openCaseFromResolvedDrawer(caseId) {
        closeResolvedCasesDrawer();
        openCaseModal(caseId);
    }

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closePendingCasesDrawer();
            closeResolvedCasesDrawer();
            closeSettledIncidentsDrawer();
            closeCaseModal();
            closeNewCaseModal();
            closeSettledIncidentModal();
        }
    });

    function loadCasePageDeepLinks() {
        const preEl = document.getElementById('prefill-beneficiary');
        const params = new URLSearchParams(window.location.search);
        if (preEl && params.get('new_case')) {
            try {
                const row = JSON.parse(preEl.textContent);
                openNewCaseModal();
                applyBeneficiarySelection(row);
            } catch (err) {
                console.warn('Case prefill failed', err);
            }
        } else if (window.CM_CONFIG && window.CM_CONFIG.openNewCase) {
            openNewCaseModal();
        }
        const openId = params.get('case_id') || (window.CM_CONFIG ? window.CM_CONFIG.openCaseId : '');
        if (openId) openCaseModal(openId);
    }

    function caseFlowAlert(message, title, variant, onConfirm) {
        const tone = variant === 'success' ? 'success' : 'default';
        if (typeof showFlowAlert === 'function') {
            showFlowAlert(message || '', title || 'Notice', onConfirm || null, tone);
            return;
        }
        alert(message || '');
        if (typeof onConfirm === 'function') onConfirm();
    }

    function showCaseRecordedSuccess(casePayload, fallbackMessage) {
        let caseNumber = (casePayload && casePayload.case_number) ? String(casePayload.case_number).trim() : '';
        let statusText = 'Pending Review';
        if (fallbackMessage) {
            const caseMatch = fallbackMessage.match(/CASE-[A-Za-z0-9-]+/i);
            if (!caseNumber && caseMatch) caseNumber = caseMatch[0];
            const statusMatch = fallbackMessage.match(/Status:\s*([A-Za-z\s]+)/i);
            if (statusMatch) statusText = statusMatch[1].replace(/\.$/, '').trim();
        }
        closeNewCaseModal();
        const message = caseNumber
            ? `Case ${caseNumber} was saved.\nStatus: ${statusText}.\n\nThe field desk will open this record for site monitoring and settlement photographs.`
            : `The complaint was saved.\nStatus: ${statusText}.\n\nThe field desk will open this record for site monitoring and settlement photographs.`;
        caseFlowAlert(message, 'Case recorded', 'success');
        const refWrap = document.getElementById('flowAlertRefWrap');
        if (refWrap && caseNumber) {
            refWrap.innerHTML = '';
            const pill = document.createElement('span');
            pill.className = 'flow-alert-ref-pill';
            pill.textContent = caseNumber;
            refWrap.appendChild(pill);
            refWrap.style.display = 'block';
        }
    }

    document.addEventListener('DOMContentLoaded', () => {
        loadCasePageDeepLinks();

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
            const nameSpan = e.target.closest('.applicant-name');
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
            const nameSpan = e.target.closest('.applicant-name');
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
