    const CASE_POSITION = (window.CASE_CONFIG && window.CASE_CONFIG.position) || '';
    let currentCaseId = null;
    let complainantSearchTimer = null;
    let subjectSearchTimer = null;
    let settledLogComplainantSearchTimer = null;
    let settledLogSubjectSearchTimer = null;

    function csrfToken() {
        return document.querySelector('[name=csrfmiddlewaretoken]').value;
    }

    function resetCaseModalSections() {
        ['subjectSection', 'investigationSection', 'referralSection', 'resolutionSection',
            'respondentPriorSection'].forEach((id) => {
                const el = document.getElementById(id);
                if (el) el.style.display = 'none';
            });
        const respPriorTableWrap = document.getElementById('respondentPriorTableWrap');
        if (respPriorTableWrap) respPriorTableWrap.style.display = 'none';
        const settledLogsSection = document.getElementById('respondentSettledLogsSection');
        if (settledLogsSection) settledLogsSection.style.display = 'none';
        const settledLogsList = document.getElementById('respondentSettledLogsList');
        if (settledLogsList) settledLogsList.innerHTML = '';
        const respondentPriorCards = document.getElementById('respondentPriorCards');
        if (respondentPriorCards) respondentPriorCards.innerHTML = '';
        const respondentSettledLogsCards = document.getElementById('respondentSettledLogsCards');
        if (respondentSettledLogsCards) respondentSettledLogsCards.innerHTML = '';
        const evidenceList = document.getElementById('evidenceList');
        if (evidenceList) {
            evidenceList.innerHTML = '';
            evidenceList.hidden = true;
        }
        caseSettlementSavedUrls = [];
        caseSettlementSavedIndex = 0;
        caseIntakeSavedUrls = [];
        caseIntakeSavedIndex = 0;
        const intakeSection = document.getElementById('caseIntakeEvidenceSection');
        if (intakeSection) intakeSection.style.display = 'none';
        const intakeCarousel = document.getElementById('caseIntakeSavedCarousel');
        if (intakeCarousel) intakeCarousel.hidden = true;
        const savedCarousel = document.getElementById('caseSettlementSavedCarousel');
        if (savedCarousel) savedCarousel.hidden = true;
        clearCaseSettlementPendingEvidence();
        stopCaseSettlementCamera();
        const updateNote = document.getElementById('updateNote');
        const newStatus = document.getElementById('newStatus');
        if (updateNote) updateNote.value = '';
        if (newStatus) newStatus.value = '';
    }

    function fetchCaseDetails(caseId) {
        return fetch(`/cases/${CASE_POSITION}/${caseId}/details/`)
            .then((r) => {
                if (!r.ok) throw new Error('Could not load case (' + r.status + ')');
                return r.json();
            });
    }

    function openCaseModal(caseId) {
        currentCaseId = caseId;
        document.getElementById('newCaseModal').style.display = 'none';
        resetCaseModalSections();
        document.body.style.overflow = 'hidden';

        function showCaseFromResponse(d) {
            if (d.success) populateCaseModal(d.case);
            else alert('Error: ' + (d.error || 'Could not load case'));
        }

        fetchCaseDetails(caseId)
            .then((d) => {
                if (!d.success) {
                    showCaseFromResponse(d);
                    return;
                }
                const wf = d.case.workflow || {};
                if (!wf.needs_auto_start_review) {
                    showCaseFromResponse(d);
                    return;
                }
                return postCaseUpdate({ action: 'start_review' })
                    .then((upd) => {
                        if (!upd.success) {
                            alert(upd.error || 'Could not start review');
                            return;
                        }
                        updateCaseListRowStatus(
                            caseId,
                            upd.new_status || 'under_review',
                            upd.status_display || 'Under Review'
                        );
                        return fetchCaseDetails(caseId).then(showCaseFromResponse);
                    });
            })
            .catch(() => {
                alert('Could not load case details. Make sure the server is running, then try again.');
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
            if (notesEl) notesEl.textContent = '—';
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

    function populateCaseModal(c, options = {}) {
        const filed = new Date(c.received_at);
        document.getElementById('modalCaseNumber').textContent = c.case_number;
        const statusEl = document.getElementById('modalStatusBadge');
        if (statusEl) {
            statusEl.textContent = c.status_display;
            statusEl.className = `case-status-pill case-status-pill--${c.status}`;
        }
        const filedMeta = document.getElementById('modalFiledMeta');
        if (filedMeta) {
            let filedText = `Filed ${filed.toLocaleDateString()} · ${filed.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}`;
            if (c.received_by) {
                filedText += ` · Recorded by ${c.received_by}`;
                if (c.received_by_position) filedText += ` (${c.received_by_position})`;
            }
            filedMeta.textContent = filedText;
        }

        // Populate Recorded by card (replicated from staff dashboard)
        const avatarEl = document.getElementById('modalStaffAvatar');
        const staffName = c.received_by || 'Unassigned';
        const staffRole = c.received_by_position || '—';
        const initials = c.received_by_initials || (staffName !== 'Unassigned' ? staffName.slice(0, 2).toUpperCase() : '—');
        if (avatarEl) {
            avatarEl.textContent = initials;
            avatarEl.className = `handled-by-avatar ${staffAvatarClass(c.received_by_position_key || '')}`;
        }
        const staffNameEl = document.getElementById('modalStaffName');
        const staffRoleEl = document.getElementById('modalStaffRole');
        if (staffNameEl) staffNameEl.textContent = staffName;
        if (staffRoleEl) staffRoleEl.textContent = staffRole;

        document.getElementById('modalComplainantName').textContent = c.complainant_name;
        document.getElementById('modalComplainantPhone').textContent = c.complainant_phone || '—';
        document.getElementById('modalComplainantRef').textContent = c.complainant_reference || '—';
        document.getElementById('modalComplainantUnit').textContent = c.complainant_unit_label || '—';

        const profile = c.beneficiary_profile;
        const sexEl = document.getElementById('modalBeneficiarySex');
        const householdEl = document.getElementById('modalBeneficiaryHousehold');
        const householdWrap = document.getElementById('modalHouseholdMembersWrap');
        const householdList = document.getElementById('modalHouseholdMembersList');
        if (sexEl) sexEl.textContent = profile?.sex_display || '—';
        if (householdEl) {
            const n = profile?.household_members;
            householdEl.textContent = n != null ? `${n} member${n === 1 ? '' : 's'}` : '—';
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
                                    <td style="font-weight:600;">${escapeHtml(m.name || '—')}</td>
                                    <td>${escapeHtml(m.relationship || '—')}</td>
                                    <td>${escapeHtml(m.sex_display || '—')}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>`;
            } else {
                householdWrap.style.display = 'none';
                householdList.innerHTML = '';
            }
        }
        document.getElementById('modalDescription').textContent = c.initial_description || '—';
        const typeEl = document.getElementById('modalComplaintType');
        if (typeEl) {
            typeEl.innerHTML = `<span class="case-type-pill">${c.case_type_display}</span>`;
        }

        const subjectSection = document.getElementById('subjectSection');
        if (c.subject_name) {
            subjectSection.style.display = 'block';
            document.getElementById('modalSubjectName').textContent = c.subject_name;
            document.getElementById('modalSubjectPhone').textContent = c.subject_phone || '—';
            document.getElementById('modalSubjectRef').textContent = c.subject_reference || '—';
            document.getElementById('modalSubjectUnit').textContent = c.subject_unit_label || '—';

            const sProfile = c.subject_profile;
            const sSexEl = document.getElementById('modalSubjectSex');
            const sHouseholdEl = document.getElementById('modalSubjectHousehold');
            const sHouseholdWrap = document.getElementById('modalSubjectHouseholdMembersWrap');
            const sHouseholdList = document.getElementById('modalSubjectHouseholdMembersList');
            if (sSexEl) sSexEl.textContent = sProfile?.sex_display || '—';
            if (sHouseholdEl) {
                const n = sProfile?.household_members;
                sHouseholdEl.textContent = n != null ? `${n} member${n === 1 ? '' : 's'}` : '—';
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
                                        <td style="font-weight:600;">${escapeHtml(m.name || '—')}</td>
                                        <td>${escapeHtml(m.relationship || '—')}</td>
                                        <td>${escapeHtml(m.sex_display || '—')}</td>
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

        const respPriorSection = document.getElementById('respondentPriorSection');
        const respPriorList = document.getElementById('respondentPriorList');
        const respPriorCards = document.getElementById('respondentPriorCards');
        const respPriorTableWrap = document.getElementById('respondentPriorTableWrap');
        const respPriorHeading = document.getElementById('respondentPriorHeading');
        const respPriorEmpty = document.getElementById('respondentPriorEmpty');
        if (respPriorSection) {
            if (c.subject_name) {
                respPriorSection.style.display = 'block';
                const respLabel = c.subject_name + (c.subject_reference ? ` (${c.subject_reference})` : '');
                if (respPriorHeading) respPriorHeading.textContent = respLabel;
                const respPriors = c.respondent_prior_cases || [];
                if (respPriors.length) {
                    if (respPriorEmpty) respPriorEmpty.style.display = 'none';
                    if (respPriorTableWrap) respPriorTableWrap.style.display = 'block';
                    
                    if (respPriorList) {
                        respPriorList.innerHTML = respPriors.map((pc) => {
                            const statusKey = escapeHtml(pc.status || '');
                            const filed = pc.received_at
                                ? new Date(pc.received_at).toLocaleDateString()
                                : '';
                            return `
                            <tr>
                                <td class="case-prior-table-case"><strong>${escapeHtml(pc.case_number)}</strong></td>
                                <td class="case-prior-table-status">
                                    <span class="case-prior-status-pill case-prior-status-pill--${statusKey}">${escapeHtml(pc.status_display)}</span>
                                    ${filed ? `<span class="case-prior-table-date">${escapeHtml(filed)}</span>` : ''}
                                </td>
                                <td class="case-prior-table-type">${escapeHtml(pc.case_type_display)}</td>
                                <td class="case-prior-table-desc">${escapeHtml(pc.initial_description || '—')}</td>
                                <td class="case-prior-table-action">
                                    <button type="button" class="case-prior-open-link" onclick="openCaseModal('${pc.id}')">Open record</button>
                                </td>
                            </tr>`;
                        }).join('');
                    }

                    if (respPriorCards) {
                        respPriorCards.innerHTML = respPriors.map((pc) => {
                            const statusKey = escapeHtml(pc.status || '');
                            const filed = pc.received_at
                                ? new Date(pc.received_at).toLocaleDateString()
                                : '';
                            return `
                            <div class="prior-case-mobile-card">
                                <div class="prior-card-header">
                                    <span class="prior-card-case"><strong>${escapeHtml(pc.case_number)}</strong></span>
                                    <span class="prior-card-type">${escapeHtml(pc.case_type_display)}</span>
                                </div>
                                <div class="prior-card-body">
                                    <div class="prior-card-row">
                                        <span class="prior-card-label">Status:</span>
                                        <span class="prior-card-value">
                                            <span class="case-prior-status-pill case-prior-status-pill--${statusKey}">${escapeHtml(pc.status_display)}</span>
                                            ${filed ? `<span class="case-prior-table-date">${escapeHtml(filed)}</span>` : ''}
                                        </span>
                                    </div>
                                    <div class="prior-card-row">
                                        <span class="prior-card-label">Description:</span>
                                        <span class="prior-card-value prior-card-desc">${escapeHtml(pc.initial_description || '—')}</span>
                                    </div>
                                </div>
                                <div class="prior-card-actions">
                                    <button type="button" class="case-prior-open-link" onclick="openCaseModal('${pc.id}')">Open record</button>
                                </div>
                            </div>`;
                        }).join('');
                    }
                } else {
                    if (respPriorList) respPriorList.innerHTML = '';
                    if (respPriorCards) respPriorCards.innerHTML = '';
                    if (respPriorTableWrap) respPriorTableWrap.style.display = 'none';
                    if (respPriorEmpty) respPriorEmpty.style.display = 'block';
                }
            } else {
                respPriorSection.style.display = 'none';
                if (respPriorList) respPriorList.innerHTML = '';
                if (respPriorCards) respPriorCards.innerHTML = '';
                if (respPriorTableWrap) respPriorTableWrap.style.display = 'none';
                if (respPriorEmpty) respPriorEmpty.style.display = 'none';
            }
        }

        const settledLogsSection = document.getElementById('respondentSettledLogsSection');
        const settledLogsList = document.getElementById('respondentSettledLogsList');
        const settledLogsCards = document.getElementById('respondentSettledLogsCards');
        const settledLogs = c.respondent_settled_incident_logs || [];
        if (settledLogsSection) {
            if (c.subject_name && settledLogs.length) {
                settledLogsSection.style.display = 'block';
                if (settledLogsList) {
                    settledLogsList.innerHTML = settledLogs.map((log) => {
                        const when = log.logged_at
                            ? new Date(log.logged_at).toLocaleDateString()
                            : '';
                        return `
                        <tr>
                            <td>${escapeHtml(when)}</td>
                            <td>${escapeHtml(log.unit_label || '—')}</td>
                            <td>${escapeHtml(log.case_type_display || '—')}</td>
                            <td>${escapeHtml(log.description || '—')}</td>
                        </tr>`;
                    }).join('');
                }
                if (settledLogsCards) {
                    settledLogsCards.innerHTML = settledLogs.map((log) => {
                        const when = log.logged_at
                            ? new Date(log.logged_at).toLocaleDateString()
                            : '';
                        return `
                        <div class="settled-log-mobile-card">
                            <div class="settled-card-header">
                                <span class="settled-card-date"><strong>${escapeHtml(when)}</strong></span>
                                <span class="settled-card-unit">${escapeHtml(log.unit_label || '—')}</span>
                            </div>
                            <div class="settled-card-body">
                                <div class="settled-card-row">
                                    <span class="settled-card-label">Type:</span>
                                    <span class="settled-card-value">${escapeHtml(log.case_type_display || '—')}</span>
                                </div>
                                <div class="settled-card-row">
                                    <span class="settled-card-label">Description:</span>
                                    <span class="settled-card-value settled-card-desc">${escapeHtml(log.description || '—')}</span>
                                </div>
                            </div>
                        </div>`;
                    }).join('');
                }
            } else {
                settledLogsSection.style.display = 'none';
                if (settledLogsList) settledLogsList.innerHTML = '';
                if (settledLogsCards) settledLogsCards.innerHTML = '';
            }
        }

        const wf = c.workflow || {};
        const deskBadge = document.getElementById('modalDeskBadge');
        if (deskBadge) {
            deskBadge.style.display = 'inline-block';
            if (wf.can_mark_reviewed) {
                deskBadge.textContent = 'Field follow-up';
                deskBadge.className = 'case-desk-badge case-desk-badge--intake';
            } else if (wf.show_case_carousel) {
                deskBadge.textContent = 'Settlement';
                deskBadge.className = 'case-desk-badge case-desk-badge--intake';
            } else {
                deskBadge.textContent = 'View only';
                deskBadge.className = 'case-desk-badge case-desk-badge--monitor';
            }
        }
        populateCaseIntakeEvidenceSection(c);
        applyFieldCaseModalLayout(c, wf, options);
        if (wf.show_case_carousel) {
            populateFieldCaseEvidence(c, wf);
        }

        const modal = document.getElementById('caseModal');
        modal.style.display = 'flex';
        document.body.style.overflow = 'hidden';
    }

    let fieldCaseCarouselIndex = 0;
    const CASE_SETTLEMENT_MAX_PHOTOS = 4;
    let caseSettlementPendingFiles = [];
    let caseSettlementPendingObjectUrls = [];
    let caseSettlementPendingIndex = 0;
    let caseSettlementSavedUrls = [];
    let caseSettlementSavedIndex = 0;
    let caseIntakeSavedUrls = [];
    let caseIntakeSavedIndex = 0;
    let caseSettlementCameraStream = null;
    let caseSettlementCameraFacingMode = 'environment';

    function classifyCaseEvidenceList(evidence) {
        const intake = [];
        const settlement = [];
        (evidence || []).forEach((ev) => {
            const cap = (ev.caption || '').toLowerCase();
            if (cap.includes('settlement')) {
                settlement.push(ev);
            } else {
                intake.push(ev);
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
        if (caseIntakeSavedIndex >= n) {
            caseIntakeSavedIndex = n - 1;
        }
        img.src = caseIntakeSavedUrls[caseIntakeSavedIndex];
        img.alt = 'Intake photo ' + String(caseIntakeSavedIndex + 1) + ' of ' + String(n);
        if (counter) {
            counter.textContent = n > 1 ? String(caseIntakeSavedIndex + 1) + ' / ' + String(n) : '1 photo';
        }
        if (prev) prev.hidden = n <= 1;
        if (next) next.hidden = n <= 1;
        syncFieldCaseCarouselLayout();
    }

    function caseIntakeSavedCarouselStep(delta) {
        const n = caseIntakeSavedUrls.length;
        if (n <= 1) return;
        caseIntakeSavedIndex = (caseIntakeSavedIndex + delta + n) % n;
        refreshCaseIntakeSavedCarousel();
    }

    function populateCaseIntakeEvidenceSection(c) {
        const section = document.getElementById('caseIntakeEvidenceSection');
        const { intake } = classifyCaseEvidenceList(c.evidence || []);

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
        bindCaseIntakeEvidenceViewControls();
    }

    function bindCaseIntakeEvidenceViewControls() {
        if (window._caseIntakeEvidenceViewBound) return;
        window._caseIntakeEvidenceViewBound = true;
        document.getElementById('caseIntakeSavedPrev')?.addEventListener('click', () => caseIntakeSavedCarouselStep(-1));
        document.getElementById('caseIntakeSavedNext')?.addEventListener('click', () => caseIntakeSavedCarouselStep(1));
    }

    function syncFieldCaseCarouselLayout() {
        const trackWrap = document.querySelector('.field-case-carousel-track-wrap');
        if (!trackWrap || trackWrap.offsetParent === null) return;
        requestAnimationFrame(() => {
            setFieldCaseCarouselPage(fieldCaseCarouselIndex);
        });
    }

    function clearCaseSettlementPendingEvidence() {
        caseSettlementPendingObjectUrls.forEach((u) => {
            try { URL.revokeObjectURL(u); } catch (e) { /* ignore */ }
        });
        caseSettlementPendingObjectUrls = [];
        caseSettlementPendingFiles = [];
        caseSettlementPendingIndex = 0;
        const carousel = document.getElementById('caseSettlementPendingCarousel');
        if (carousel) carousel.hidden = true;
        const fi = document.getElementById('caseSettlementEvidenceFileInput');
        if (fi) fi.value = '';
    }

    function refreshCaseSettlementPendingCarousel() {
        caseSettlementPendingObjectUrls.forEach((u) => {
            try { URL.revokeObjectURL(u); } catch (e) { /* ignore */ }
        });
        caseSettlementPendingObjectUrls = caseSettlementPendingFiles.map((file) => URL.createObjectURL(file));

        const carousel = document.getElementById('caseSettlementPendingCarousel');
        const img = document.getElementById('caseSettlementPendingImg');
        const counter = document.getElementById('caseSettlementPendingCounter');
        const prev = document.getElementById('caseSettlementPendingPrev');
        const next = document.getElementById('caseSettlementPendingNext');
        const n = caseSettlementPendingObjectUrls.length;

        if (!carousel || !img) return;
        if (!n) {
            carousel.hidden = true;
            caseSettlementPendingIndex = 0;
            img.removeAttribute('src');
            return;
        }

        carousel.hidden = false;
        if (caseSettlementPendingIndex >= n) {
            caseSettlementPendingIndex = n - 1;
        }
        if (caseSettlementPendingIndex < 0) {
            caseSettlementPendingIndex = 0;
        }

        img.src = caseSettlementPendingObjectUrls[caseSettlementPendingIndex];
        img.alt = 'Settlement photo ' + String(caseSettlementPendingIndex + 1) + ' of ' + String(n);
        if (counter) {
            counter.textContent = n > 1 ? String(caseSettlementPendingIndex + 1) + ' / ' + String(n) : '1 photo';
        }
        if (prev) prev.hidden = n <= 1;
        if (next) next.hidden = n <= 1;
        syncFieldCaseCarouselLayout();
    }

    function caseSettlementPendingCarouselStep(delta) {
        const n = caseSettlementPendingObjectUrls.length;
        if (n <= 1) return;
        caseSettlementPendingIndex = (caseSettlementPendingIndex + delta + n) % n;
        refreshCaseSettlementPendingCarousel();
    }

    function refreshCaseSettlementSavedCarousel() {
        const carousel = document.getElementById('caseSettlementSavedCarousel');
        const img = document.getElementById('caseSettlementSavedImg');
        const counter = document.getElementById('caseSettlementSavedCounter');
        const prev = document.getElementById('caseSettlementSavedPrev');
        const next = document.getElementById('caseSettlementSavedNext');
        const n = caseSettlementSavedUrls.length;

        if (!carousel || !img) return;
        if (!n) {
            carousel.hidden = true;
            caseSettlementSavedIndex = 0;
            img.removeAttribute('src');
            return;
        }

        carousel.hidden = false;
        if (caseSettlementSavedIndex >= n) {
            caseSettlementSavedIndex = n - 1;
        }
        img.src = caseSettlementSavedUrls[caseSettlementSavedIndex];
        img.alt = 'Saved settlement photo ' + String(caseSettlementSavedIndex + 1) + ' of ' + String(n);
        if (counter) {
            counter.textContent = n > 1 ? String(caseSettlementSavedIndex + 1) + ' / ' + String(n) : '1 photo';
        }
        if (prev) prev.hidden = n <= 1;
        if (next) next.hidden = n <= 1;
        syncFieldCaseCarouselLayout();
    }

    function caseSettlementSavedCarouselStep(delta) {
        const n = caseSettlementSavedUrls.length;
        if (n <= 1) return;
        caseSettlementSavedIndex = (caseSettlementSavedIndex + delta + n) % n;
        refreshCaseSettlementSavedCarousel();
    }

    function addCaseSettlementPendingFile(file) {
        if (caseSettlementPendingFiles.length >= CASE_SETTLEMENT_MAX_PHOTOS) {
            casePhotoLimitAlert();
            return;
        }
        const maxBytes = 6 * 1024 * 1024;
        if (file.size > maxBytes) {
            alert('Each photo must be 6 MB or smaller.');
            return;
        }
        const okType = /^image\/(jpeg|png|webp)$/i.test(file.type || '');
        if (!okType) {
            alert('Only JPEG, PNG, or WebP photos are allowed.');
            return;
        }
        caseSettlementPendingFiles.push(file);
        if (caseSettlementPendingFiles.length === 1) {
            caseSettlementPendingIndex = 0;
        } else {
            caseSettlementPendingIndex = caseSettlementPendingFiles.length - 1;
        }
        refreshCaseSettlementPendingCarousel();
    }

    function removeCaseSettlementPendingAt(index) {
        if (index < 0 || index >= caseSettlementPendingFiles.length) return;
        caseSettlementPendingFiles.splice(index, 1);
        if (caseSettlementPendingIndex >= caseSettlementPendingFiles.length) {
            caseSettlementPendingIndex = Math.max(0, caseSettlementPendingFiles.length - 1);
        }
        refreshCaseSettlementPendingCarousel();
    }

    function removeCurrentCaseSettlementPendingPhoto() {
        removeCaseSettlementPendingAt(caseSettlementPendingIndex);
    }

    function stopCaseSettlementCamera() {
        if (caseSettlementCameraStream) {
            caseSettlementCameraStream.getTracks().forEach((t) => t.stop());
            caseSettlementCameraStream = null;
        }
        const v = document.getElementById('caseSettlementCameraVideo');
        if (v) {
            v.srcObject = null;
        }
        const vWrap = document.getElementById('caseSettlementVideoWrap');
        if (vWrap) vWrap.style.display = 'none';
        const mainBtns = document.getElementById('caseSettlementMainButtons');
        if (mainBtns) mainBtns.style.display = 'flex';
    }

    async function startCaseSettlementCamera() {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            alert('This browser does not support in-page camera access. Use Attach from device.');
            return;
        }
        try {
            if (caseSettlementCameraStream) {
                caseSettlementCameraStream.getTracks().forEach((t) => t.stop());
            }
            caseSettlementCameraStream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: { ideal: caseSettlementCameraFacingMode } },
                audio: false,
            });
            const v = document.getElementById('caseSettlementCameraVideo');
            if (v) {
                v.srcObject = caseSettlementCameraStream;
                await v.play();
            }
            const vWrap = document.getElementById('caseSettlementVideoWrap');
            if (vWrap) vWrap.style.display = 'flex';
            const mainBtns = document.getElementById('caseSettlementMainButtons');
            if (mainBtns) mainBtns.style.display = 'none';
            const cap = document.getElementById('caseSettlementCameraCaptureBtn');
            if (cap) { cap.style.display = 'inline-block'; cap.disabled = false; }
            const stp = document.getElementById('caseSettlementCameraStopBtn');
            if (stp) { stp.style.display = 'inline-block'; stp.disabled = false; }
            const swt = document.getElementById('caseSettlementCameraSwitchBtn');
            if (swt) { swt.style.display = 'inline-block'; swt.disabled = false; }
        } catch (err) {
            alert('Could not open camera. Use Attach from device, or ensure you are on HTTPS or localhost.');
        }
    }

    async function toggleCaseSettlementCamera() {
        caseSettlementCameraFacingMode = (caseSettlementCameraFacingMode === 'environment') ? 'user' : 'environment';
        if (caseSettlementCameraStream) {
            await startCaseSettlementCamera();
        }
    }

    function captureCaseSettlementPhoto() {
        const v = document.getElementById('caseSettlementCameraVideo');
        const c = document.getElementById('caseSettlementCameraCanvas');
        if (!v || !c || !v.videoWidth) {
            alert('Wait for the camera preview, then capture again.');
            return;
        }
        let vWidth = v.videoWidth || 1280;
        let vHeight = v.videoHeight || 720;
        
        /* Optimization: Scale down 4K/high-res streams to max 1280px for faster field uploads */
        const MAX_DIMENSION = 1280;
        if (vWidth > MAX_DIMENSION || vHeight > MAX_DIMENSION) {
            const ratio = Math.min(MAX_DIMENSION / vWidth, MAX_DIMENSION / vHeight);
            vWidth = Math.floor(vWidth * ratio);
            vHeight = Math.floor(vHeight * ratio);
        }

        /* Crop to 16:9 to match the UI's cinematic object-fit: cover */
        let targetAspect = 16 / 9;
        let sourceAspect = vWidth / vHeight;
        let cropWidth = vWidth;
        let cropHeight = vHeight;
        let offsetX = 0;
        let offsetY = 0;

        if (sourceAspect > targetAspect) {
            cropWidth = Math.floor(vHeight * targetAspect);
            offsetX = Math.floor((vWidth - cropWidth) / 2);
        } else if (sourceAspect < targetAspect) {
            cropHeight = Math.floor(vWidth / targetAspect);
            offsetY = Math.floor((vHeight - cropHeight) / 2);
        }

        c.width = cropWidth;
        c.height = cropHeight;
        c.getContext('2d').drawImage(v, offsetX, offsetY, cropWidth, cropHeight, 0, 0, cropWidth, cropHeight);
        c.toBlob((blob) => {
            if (!blob) return;
            const file = new File([blob], 'settlement-' + Date.now() + '.jpg', { type: 'image/jpeg' });
            addCaseSettlementPendingFile(file);
        }, 'image/jpeg', 0.8);
    }

    function onCaseSettlementEvidenceFilesSelected(ev) {
        const files = ev.target.files;
        if (!files) return;
        for (let i = 0; i < files.length; i++) {
            if (caseSettlementPendingFiles.length >= CASE_SETTLEMENT_MAX_PHOTOS) break;
            addCaseSettlementPendingFile(files[i]);
        }
        ev.target.value = '';
    }

    function bindCaseSettlementEvidenceControls() {
        if (window._caseSettlementEvidenceBound) return;
        window._caseSettlementEvidenceBound = true;
        document.getElementById('caseSettlementCameraStartBtn')?.addEventListener('click', startCaseSettlementCamera);
        document.getElementById('caseSettlementCameraCaptureBtn')?.addEventListener('click', captureCaseSettlementPhoto);
        document.getElementById('caseSettlementCameraStopBtn')?.addEventListener('click', stopCaseSettlementCamera);
        document.getElementById('caseSettlementCameraSwitchBtn')?.addEventListener('click', toggleCaseSettlementCamera);
        document.getElementById('caseSettlementEvidenceFilePickBtn')?.addEventListener('click', () => {
            document.getElementById('caseSettlementEvidenceFileInput')?.click();
        });
        document.getElementById('caseSettlementEvidenceFileInput')?.addEventListener('change', onCaseSettlementEvidenceFilesSelected);
        document.getElementById('caseSettlementPendingPrev')?.addEventListener('click', () => caseSettlementPendingCarouselStep(-1));
        document.getElementById('caseSettlementPendingNext')?.addEventListener('click', () => caseSettlementPendingCarouselStep(1));
        document.getElementById('caseSettlementPendingRemoveBtn')?.addEventListener('click', removeCurrentCaseSettlementPendingPhoto);
        document.getElementById('caseSettlementSavedPrev')?.addEventListener('click', () => caseSettlementSavedCarouselStep(-1));
        document.getElementById('caseSettlementSavedNext')?.addEventListener('click', () => caseSettlementSavedCarouselStep(1));
    }

    let newCaseEvidencePendingFiles = [];
    let newCaseEvidencePendingObjectUrls = [];
    let newCaseEvidencePendingIndex = 0;
    let newCaseCameraStream = null;
    let newCaseCameraFacingMode = 'environment';

    function clearNewCasePendingEvidence() {
        newCaseEvidencePendingObjectUrls.forEach((u) => {
            try { URL.revokeObjectURL(u); } catch (e) { /* ignore */ }
        });
        newCaseEvidencePendingObjectUrls = [];
        newCaseEvidencePendingFiles = [];
        newCaseEvidencePendingIndex = 0;
        const carousel = document.getElementById('newCasePendingCarousel');
        if (carousel) carousel.hidden = true;
        const fi = document.getElementById('newCaseEvidenceFileInput');
        if (fi) fi.value = '';
    }

    function refreshNewCasePendingCarousel() {
        newCaseEvidencePendingObjectUrls.forEach((u) => {
            try { URL.revokeObjectURL(u); } catch (e) { /* ignore */ }
        });
        newCaseEvidencePendingObjectUrls = newCaseEvidencePendingFiles.map((file) => URL.createObjectURL(file));

        const carousel = document.getElementById('newCasePendingCarousel');
        const img = document.getElementById('newCasePendingImg');
        const counter = document.getElementById('newCasePendingCounter');
        const prev = document.getElementById('newCasePendingPrev');
        const next = document.getElementById('newCasePendingNext');
        const n = newCaseEvidencePendingObjectUrls.length;

        if (!carousel || !img) return;
        if (!n) {
            carousel.hidden = true;
            newCaseEvidencePendingIndex = 0;
            img.removeAttribute('src');
            return;
        }

        carousel.hidden = false;
        if (newCaseEvidencePendingIndex >= n) {
            newCaseEvidencePendingIndex = n - 1;
        }
        if (newCaseEvidencePendingIndex < 0) {
            newCaseEvidencePendingIndex = 0;
        }

        img.src = newCaseEvidencePendingObjectUrls[newCaseEvidencePendingIndex];
        img.alt = 'Evidence photo ' + String(newCaseEvidencePendingIndex + 1) + ' of ' + String(n);
        if (counter) {
            counter.textContent = n > 1 ? String(newCaseEvidencePendingIndex + 1) + ' / ' + String(n) : '1 photo';
        }
        if (prev) prev.hidden = n <= 1;
        if (next) next.hidden = n <= 1;
    }

    function newCasePendingCarouselStep(delta) {
        const n = newCaseEvidencePendingObjectUrls.length;
        if (n <= 1) return;
        newCaseEvidencePendingIndex = (newCaseEvidencePendingIndex + delta + n) % n;
        refreshNewCasePendingCarousel();
    }

    function addNewCasePendingFile(file) {
        if (newCaseEvidencePendingFiles.length >= CASE_SETTLEMENT_MAX_PHOTOS) {
            casePhotoLimitAlert();
            return;
        }
        const maxBytes = 6 * 1024 * 1024;
        if (file.size > maxBytes) {
            alert('Each photo must be 6 MB or smaller.');
            return;
        }
        const okType = /^image\/(jpeg|png|webp)$/i.test(file.type || '');
        if (!okType) {
            alert('Only JPEG, PNG, or WebP photos are allowed.');
            return;
        }
        newCaseEvidencePendingFiles.push(file);
        if (newCaseEvidencePendingFiles.length === 1) {
            newCaseEvidencePendingIndex = 0;
        } else {
            newCaseEvidencePendingIndex = newCaseEvidencePendingFiles.length - 1;
        }
        refreshNewCasePendingCarousel();
    }

    function removeNewCasePendingAt(index) {
        if (index < 0 || index >= newCaseEvidencePendingFiles.length) return;
        newCaseEvidencePendingFiles.splice(index, 1);
        if (newCaseEvidencePendingIndex >= newCaseEvidencePendingFiles.length) {
            newCaseEvidencePendingIndex = Math.max(0, newCaseEvidencePendingFiles.length - 1);
        }
        refreshNewCasePendingCarousel();
    }

    function removeCurrentNewCasePendingPhoto() {
        removeNewCasePendingAt(newCaseEvidencePendingIndex);
    }

    function stopNewCaseCamera() {
        if (newCaseCameraStream) {
            newCaseCameraStream.getTracks().forEach((t) => t.stop());
            newCaseCameraStream = null;
        }
        const v = document.getElementById('newCaseCameraVideo');
        if (v) {
            v.srcObject = null;
        }
        const vWrap = document.getElementById('newCaseVideoWrap');
        if (vWrap) vWrap.style.display = 'none';
        const mainBtns = document.getElementById('newCaseMainButtons');
        if (mainBtns) mainBtns.style.display = 'flex';
    }

    async function startNewCaseCamera() {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            alert('This browser does not support in-page camera access. Use Attach from device.');
            return;
        }
        try {
            if (newCaseCameraStream) {
                newCaseCameraStream.getTracks().forEach((t) => t.stop());
            }
            newCaseCameraStream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: { ideal: newCaseCameraFacingMode } },
                audio: false,
            });
            const v = document.getElementById('newCaseCameraVideo');
            if (v) {
                v.srcObject = newCaseCameraStream;
                await v.play();
            }
            const vWrap = document.getElementById('newCaseVideoWrap');
            if (vWrap) vWrap.style.display = 'flex';
            const mainBtns = document.getElementById('newCaseMainButtons');
            if (mainBtns) mainBtns.style.display = 'none';
            const cap = document.getElementById('newCaseCameraCaptureBtn');
            if (cap) { cap.style.display = 'inline-block'; cap.disabled = false; }
            const stp = document.getElementById('newCaseCameraStopBtn');
            if (stp) { stp.style.display = 'inline-block'; stp.disabled = false; }
            const swt = document.getElementById('newCaseCameraSwitchBtn');
            if (swt) { swt.style.display = 'inline-block'; swt.disabled = false; }
        } catch (err) {
            alert('Could not open camera. Use Attach from device, or ensure you are on HTTPS or localhost.');
        }
    }

    async function toggleNewCaseCamera() {
        newCaseCameraFacingMode = (newCaseCameraFacingMode === 'environment') ? 'user' : 'environment';
        if (newCaseCameraStream) {
            await startNewCaseCamera();
        }
    }

    function captureNewCasePhoto() {
        const v = document.getElementById('newCaseCameraVideo');
        const c = document.getElementById('newCaseCameraCanvas');
        if (!v || !c || !v.videoWidth) {
            alert('Wait for the camera preview, then capture again.');
            return;
        }
        let vWidth = v.videoWidth || 1280;
        let vHeight = v.videoHeight || 720;
        
        /* Optimization: Scale down 4K/high-res streams to max 1280px for faster field uploads */
        const MAX_DIMENSION = 1280;
        if (vWidth > MAX_DIMENSION || vHeight > MAX_DIMENSION) {
            const ratio = Math.min(MAX_DIMENSION / vWidth, MAX_DIMENSION / vHeight);
            vWidth = Math.floor(vWidth * ratio);
            vHeight = Math.floor(vHeight * ratio);
        }

        /* Crop to 16:9 to match the UI's cinematic object-fit: cover */
        let targetAspect = 16 / 9;
        let sourceAspect = vWidth / vHeight;
        let cropWidth = vWidth;
        let cropHeight = vHeight;
        let offsetX = 0;
        let offsetY = 0;

        if (sourceAspect > targetAspect) {
            cropWidth = Math.floor(vHeight * targetAspect);
            offsetX = Math.floor((vWidth - cropWidth) / 2);
        } else if (sourceAspect < targetAspect) {
            cropHeight = Math.floor(vWidth / targetAspect);
            offsetY = Math.floor((vHeight - cropHeight) / 2);
        }

        c.width = cropWidth;
        c.height = cropHeight;
        c.getContext('2d').drawImage(v, offsetX, offsetY, cropWidth, cropHeight, 0, 0, cropWidth, cropHeight);
        c.toBlob((blob) => {
            if (!blob) return;
            const file = new File([blob], 'intake-' + Date.now() + '.jpg', { type: 'image/jpeg' });
            addNewCasePendingFile(file);
        }, 'image/jpeg', 0.8);
    }

    function onNewCaseEvidenceFilesSelected(ev) {
        const files = ev.target.files;
        if (!files) return;
        for (let i = 0; i < files.length; i++) {
            if (newCaseEvidencePendingFiles.length >= CASE_SETTLEMENT_MAX_PHOTOS) break;
            addNewCasePendingFile(files[i]);
        }
        ev.target.value = '';
    }

    function bindNewCaseEvidenceControls() {
        if (window._newCaseEvidenceBound) return;
        window._newCaseEvidenceBound = true;
        document.getElementById('newCaseCameraStartBtn')?.addEventListener('click', startNewCaseCamera);
        document.getElementById('newCaseCameraCaptureBtn')?.addEventListener('click', captureNewCasePhoto);
        document.getElementById('newCaseCameraStopBtn')?.addEventListener('click', stopNewCaseCamera);
        document.getElementById('newCaseCameraSwitchBtn')?.addEventListener('click', toggleNewCaseCamera);
        document.getElementById('newCaseEvidenceFilePickBtn')?.addEventListener('click', () => {
            document.getElementById('newCaseEvidenceFileInput')?.click();
        });
        document.getElementById('newCaseEvidenceFileInput')?.addEventListener('change', onNewCaseEvidenceFilesSelected);
        document.getElementById('newCasePendingPrev')?.addEventListener('click', () => newCasePendingCarouselStep(-1));
        document.getElementById('newCasePendingNext')?.addEventListener('click', () => newCasePendingCarouselStep(1));
        document.getElementById('newCasePendingRemoveBtn')?.addEventListener('click', removeCurrentNewCasePendingPhoto);
    }

    function renderCaseSettlementSavedEvidence(evidence) {
        const { settlement } = classifyCaseEvidenceList(evidence || []);
        caseSettlementSavedUrls = settlement.map((ev) => ev.url).filter(Boolean);
        caseSettlementSavedIndex = 0;
        refreshCaseSettlementSavedCarousel();
        const legacyList = document.getElementById('evidenceList');
        if (legacyList) {
            legacyList.innerHTML = '';
            legacyList.hidden = true;
        }
    }

    function populateFieldCaseEvidence(c, wf) {
        const evidenceSection = document.getElementById('evidenceSection');
        const uploadForm = document.getElementById('evidenceUploadForm');
        if (!evidenceSection) return;

        evidenceSection.style.display = 'block';
        renderCaseSettlementSavedEvidence(c.evidence);
        if (uploadForm) {
            const canUpload = wf.can_upload_evidence !== false && !['resolved', 'closed'].includes(c.status);
            uploadForm.style.display = canUpload ? 'block' : 'none';
        }
        clearCaseSettlementPendingEvidence();
        stopCaseSettlementCamera();
        bindCaseSettlementEvidenceControls();
    }

    function postCaseUpdate(body) {
        return fetch(`/cases/${CASE_POSITION}/update/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() },
            body: JSON.stringify({ case_id: currentCaseId, ...body }),
        }).then((r) => r.json());
    }

    function updateCaseListRowStatus(caseId, status, statusDisplay) {
        // Desktop table row status update
        const row = document.querySelector(`tr[data-case-id="${caseId}"]`);
        if (row) {
            row.dataset.caseStatus = status;
            const pill = row.querySelector('[data-case-status-pill]');
            if (pill) {
                updateStatusPill(pill, status, statusDisplay);
            }
        }
        
        // Mobile card simulator status update
        const card = document.getElementById(`case-card-${caseId}`);
        if (card) {
            const pill = card.querySelector('[data-case-status-pill]');
            if (pill) {
                updateStatusPill(pill, status, statusDisplay);
            }
        }
    }

    function updateStatusPill(pill, status, statusDisplay) {
        pill.className = `status-pill-flex status-pill-flex--${status}`;
        let innerHTML = '';
        if (status === 'resolved') {
            innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" style="width: 0.75rem; height: 0.75rem; color: #16a34a; flex-shrink: 0; margin-right: 0.15rem;"><path d="M20 6L9 17l-5-5"></path></svg>`;
        } else if (status === 'closed') {
            innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="width: 0.75rem; height: 0.75rem; color: #475569; flex-shrink: 0; margin-right: 0.15rem;"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>`;
        }
        pill.innerHTML = innerHTML + statusDisplay;
    }

    function applyFieldCaseModalLayout(c, wf, options = {}) {
        const staticWrap = document.getElementById('fieldCaseStaticWrap');
        const markWrap = document.getElementById('fieldMarkReviewedWrap');
        const carouselWrap = document.getElementById('fieldCaseCarouselWrap');
        const primary = document.getElementById('caseRecordPrimary');
        const slide1 = document.getElementById('fieldCaseSlide1Mount');

        if (wf.can_mark_reviewed) {
            if (staticWrap) staticWrap.style.display = 'block';
            if (markWrap) markWrap.style.display = 'block';
            if (carouselWrap) carouselWrap.style.display = 'none';
            if (primary && staticWrap && !staticWrap.contains(primary)) {
                staticWrap.appendChild(primary);
            }
            const btn = document.getElementById('btnMarkReviewed');
            if (btn) {
                btn.disabled = false;
                btn.textContent = 'Mark Reviewed';
            }
        } else if (wf.show_case_carousel) {
            if (staticWrap) staticWrap.style.display = 'none';
            if (markWrap) markWrap.style.display = 'none';
            if (carouselWrap) carouselWrap.style.display = 'block';
            if (primary && slide1 && !slide1.contains(primary)) {
                slide1.appendChild(primary);
            }
            const startSlide = options.carouselSlide ?? 0;
            initFieldCaseSectionCarousel(2, startSlide);
        } else {
            if (staticWrap) staticWrap.style.display = 'block';
            if (markWrap) markWrap.style.display = 'none';
            if (carouselWrap) carouselWrap.style.display = 'none';
            if (primary && staticWrap && !staticWrap.contains(primary)) {
                staticWrap.appendChild(primary);
            }
        }
    }

    function markFieldCaseReviewed() {
        const btn = document.getElementById('btnMarkReviewed');
        if (!currentCaseId || !btn) return;
        btn.disabled = true;
        btn.textContent = 'Saving”¦';
        postCaseUpdate({ action: 'mark_field_reviewed' })
            .then((d) => {
                if (!d.success) {
                    alert(d.error || 'Could not update case');
                    btn.disabled = false;
                    btn.textContent = 'Mark Reviewed';
                    return;
                }
                if (d.new_status && d.status_display) {
                    updateCaseListRowStatus(currentCaseId, d.new_status, d.status_display);
                }
                fetchCaseDetails(currentCaseId)
                    .then((resp) => {
                        if (resp.success) {
                            populateCaseModal(resp.case, { carouselSlide: 1 });
                        }
                    });
            })
            .catch(() => {
                alert('Could not update case. Check that the server is running.');
                btn.disabled = false;
                btn.textContent = 'Mark Reviewed';
            });
    }

    function setFieldCaseCarouselPage(index) {
        const track = document.getElementById('fieldCaseCarouselTrack');
        const wrap = track?.parentElement;
        const total = 2;
        if (!track || !wrap) return;
        fieldCaseCarouselIndex = Math.max(0, Math.min(index, total - 1));
        const slideWidth = wrap.getBoundingClientRect().width;
        track.style.transform = `translateX(-${fieldCaseCarouselIndex * slideWidth}px)`;

        const counter = document.getElementById('fieldCaseCarouselCounter');
        if (counter) counter.textContent = `Section ${fieldCaseCarouselIndex + 1} of ${total}`;

        // Toggle slide active classes to collapse inactive height
        document.querySelectorAll('.field-case-modal-slide').forEach((slide, i) => {
            slide.classList.toggle('is-active', i === fieldCaseCarouselIndex);
        });

        // Scroll parent modal body cleanly back to top when switching tabs
        const monitorBody = document.querySelector('.tha-case-view-modal--monitor .case-monitor-body');
        if (monitorBody) {
            monitorBody.scrollTop = 0;
        }

        document.querySelectorAll('.field-case-carousel-dot').forEach((dot, i) => {
            dot.classList.toggle('is-active', i === fieldCaseCarouselIndex);
            dot.setAttribute('aria-current', i === fieldCaseCarouselIndex ? 'true' : 'false');
        });

        document.querySelectorAll('.field-case-carousel-label').forEach((label, i) => {
            const active = i === fieldCaseCarouselIndex;
            label.classList.toggle('is-active', active);
            label.setAttribute('aria-selected', active ? 'true' : 'false');
        });

        const prev = document.getElementById('fieldCaseCarouselPrev');
        const next = document.getElementById('fieldCaseCarouselNext');
        if (prev) prev.disabled = fieldCaseCarouselIndex <= 0;
        if (next) next.disabled = fieldCaseCarouselIndex >= total - 1;
    }

    function initFieldCaseSectionCarousel(slideCount, startIndex = 0) {
        const dotsWrap = document.getElementById('fieldCaseCarouselDots');
        if (dotsWrap) {
            dotsWrap.innerHTML = Array.from({ length: slideCount }, (_, i) => `
                <button type="button" class="field-case-carousel-dot${i === startIndex ? ' is-active' : ''}"
                    data-index="${i}" aria-label="Section ${i + 1} of ${slideCount}"${i === startIndex ? ' aria-current="true"' : ''}></button>
            `).join('');
            dotsWrap.querySelectorAll('.field-case-carousel-dot').forEach((dot) => {
                dot.addEventListener('click', () => {
                    setFieldCaseCarouselPage(parseInt(dot.dataset.index, 10) || 0);
                });
            });
        }

        const prev = document.getElementById('fieldCaseCarouselPrev');
        const next = document.getElementById('fieldCaseCarouselNext');
        if (prev && !prev.dataset.bound) {
            prev.dataset.bound = '1';
            prev.addEventListener('click', () => setFieldCaseCarouselPage(fieldCaseCarouselIndex - 1));
        }
        if (next && !next.dataset.bound) {
            next.dataset.bound = '1';
            next.addEventListener('click', () => setFieldCaseCarouselPage(fieldCaseCarouselIndex + 1));
        }

        document.querySelectorAll('.field-case-carousel-label').forEach((label) => {
            if (label.dataset.bound) return;
            label.dataset.bound = '1';
            label.addEventListener('click', () => {
                const idx = parseInt(label.dataset.slideIndex, 10);
                setFieldCaseCarouselPage(Number.isNaN(idx) ? 0 : idx);
            });
        });

        requestAnimationFrame(() => {
            setFieldCaseCarouselPage(startIndex);
            requestAnimationFrame(() => {
                setFieldCaseCarouselPage(startIndex);
                syncFieldCaseCarouselLayout();
            });
        });
    }

    function closeCaseModal(e) {
        if (e && e.target.id !== 'caseModal') return;
        if (typeof stopCaseSettlementCamera === 'function') {
            stopCaseSettlementCamera();
        }
        document.getElementById('caseModal').style.display = 'none';
        document.body.style.overflow = '';
    }

    function openNewCaseModal() {
        const caseModal = document.getElementById('caseModal');
        if (caseModal) caseModal.style.display = 'none';
        resetNewCaseForm();
        bindNewCaseEvidenceControls();
        syncNewCasePartyMode();
        document.body.style.overflow = 'hidden';
        document.getElementById('newCaseModal').style.display = 'flex';
    }

    function closeNewCaseModal(e) {
        if (e && e.target.id !== 'newCaseModal') return;
        stopNewCaseCamera();
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

    function isIllegalOccupantCaseType() {
        return document.getElementById('newCaseType')?.value === 'illegal_occupant';
    }

    function syncNewCasePartyMode() {
        const form = document.getElementById('addCaseForm');
        const section = document.getElementById('newCaseSubjectSection');
        const illegal = isIllegalOccupantCaseType();
        if (form) {
            form.classList.toggle('is-illegal-occupant-mode', illegal);
        }
        if (!section) return;
        const title = document.getElementById('newCaseSubjectSectionTitle');
        const searchLabel = document.getElementById('newCaseSubjectSearchLabel');
        const searchHelp = document.getElementById('newCaseSubjectSearchHelp');
        const nameLabel = document.getElementById('newCaseSubjectAutoNameLabel');
        const searchInput = document.getElementById('subjectSearchInput');
        if (illegal) {
            if (title) title.textContent = section.dataset.titleIllegal || 'Beneficiary (illegal occupant concern)';
            if (searchLabel) {
                searchLabel.innerHTML = `${section.dataset.searchLabelIllegal || 'Search beneficiary (illegal occupant concern)'} <span class="req">*</span>`;
            }
            if (searchHelp) {
                searchHelp.textContent = section.dataset.helpIllegal || '';
            }
            if (nameLabel) nameLabel.textContent = section.dataset.nameLabelIllegal || 'Beneficiary name';
            if (searchInput) {
                searchInput.placeholder = section.dataset.searchPlaceholderIllegal || 'e.g. Juan Dela Cruz, APP ref, or 1-1';
            }
            clearComplainantAutoFill();
            ['complainantApplicantId', 'relatedUnitId', 'newComplainantName', 'newComplainantPhone'].forEach((id) => {
                const el = document.getElementById(id);
                if (el) el.value = '';
            });
            const cSearch = document.getElementById('complainantSearchInput');
            if (cSearch) cSearch.value = '';
        } else {
            if (title) title.textContent = section.dataset.titleStandard || 'Reported Party';
            if (searchLabel) {
                searchLabel.innerHTML = `${section.dataset.searchLabelStandard || 'Search reported party / against whom'} <span class="req">*</span>`;
            }
            if (searchHelp) searchHelp.textContent = section.dataset.helpStandard || '';
            if (nameLabel) nameLabel.textContent = section.dataset.nameLabelStandard || 'Reported party name';
            if (searchInput) {
                searchInput.placeholder = section.dataset.searchPlaceholderStandard || 'e.g. name, APP ref, or lot';
            }
        }
    }

    function isSameApplicantAsComplainant(applicantId) {
        const cid = getSelectedComplainantApplicantId();
        return !!(cid && applicantId && String(applicantId) === cid);
    }

    function filterOutComplainantFromResults(results, complainantApplicantId) {
        const cid = complainantApplicantId || getSelectedComplainantApplicantId();
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
        if (!isIllegalOccupantCaseType() && isSameApplicantAsComplainant(row.id)) {
            alert('Reported party cannot be the same person as the complainant. Choose a different occupant.');
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
        if (isIllegalOccupantCaseType()) {
            document.getElementById('relatedUnitId').value = row.unit_id || '';
        }
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
        clearNewCasePendingEvidence();
        stopNewCaseCamera();
        updateDescCount();
        syncNewCasePartyMode();
    }

    function formatHousingBeneficiaryRow(row) {
        const parts = [];
        if (row.lot_map_label) parts.push(row.lot_map_label);
        if (row.reference_number) parts.push(row.reference_number);
        if (row.unit_label && !row.lot_map_label) parts.push(row.unit_label);
        if (row.site_name) parts.push(row.site_name);
        const meta = parts.join(' · ') || 'Occupied unit';
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
        const getComplainantApplicantId = typeof options.getComplainantApplicantId === 'function'
            ? options.getComplainantApplicantId
            : getSelectedComplainantApplicantId;
        box.innerHTML = '<p style="padding:0.5rem;font-size:0.8rem;color:#64748b;margin:0;">Loading”¦</p>';
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
                    results = filterOutComplainantFromResults(results, getComplainantApplicantId());
                }
                if (!results.length) {
                    let emptyMsg = q
                        ? 'No matches. Try name, APP ref, or lot (1-1).'
                        : 'No occupied housing units in the system yet.';
                    if (excludeComplainant && (d.results || []).length) {
                        emptyMsg = 'No other occupants match. The complainant cannot be selected as reported party.';
                    } else if (excludeComplainant && getComplainantApplicantId()) {
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
        if (!isIllegalOccupantCaseType() && !getSelectedComplainantApplicantId()) {
            const box = document.getElementById('subjectSearchResults');
            if (box) {
                box.innerHTML = '<p style="padding: 0.5rem; font-size: 0.8rem; color: #64748b; margin: 0;">Select the complainant first.</p>';
                box.style.display = 'block';
            }
            return;
        }
        const options = isIllegalOccupantCaseType()
            ? {}
            : { excludeComplainant: true };
        runBeneficiarySearch(q, document.getElementById('subjectSearchResults'), applySubjectSelection, options);
    }

    function createNewCase() {
        const illegalOccupant = isIllegalOccupantCaseType();
        const subjectId = (document.getElementById('subjectApplicantId')?.value || '').trim();
        const subjectName = document.getElementById('newSubjectName').value.trim();
        let complainantId = (document.getElementById('complainantApplicantId')?.value || '').trim();
        let complainantName = document.getElementById('newComplainantName').value.trim();
        let complainantPhone = document.getElementById('newComplainantPhone').value.trim();
        let relatedUnitId = document.getElementById('relatedUnitId').value;

        if (illegalOccupant) {
            if (!subjectId) {
                alert('Search and select the beneficiary for this illegal occupant concern.');
                return;
            }
            complainantId = subjectId;
            complainantName = subjectName;
            relatedUnitId = relatedUnitId || '';
        } else {
            if (!complainantId) {
                alert('Search and select a complainant from the housing unit list.');
                return;
            }
            if (!subjectId) {
                alert('Search and select a reported party from the housing unit list.');
                return;
            }
            if (subjectId === complainantId) {
                alert('Reported party cannot be the same person as the complainant.');
                return;
            }
        }

        const data = {
            complainant_name: complainantName,
            complainant_phone: complainantPhone,
            case_type: document.getElementById('newCaseType').value,
            received_at_location: document.getElementById('newReceivedAt').value,
            initial_description: document.getElementById('newDescription').value.trim(),
            subject_name: subjectName,
            complainant_applicant_id: complainantId,
            subject_applicant_id: subjectId,
            related_unit_id: relatedUnitId,
        };
        if (!data.case_type || !data.initial_description) {
            alert(illegalOccupant
                ? 'Fill complaint type, beneficiary, and incident description.'
                : 'Fill all required fields: complainant, reported party, complaint type, and incident description.');
            return;
        }
        if (!illegalOccupant && !data.complainant_name) {
            alert('Fill all required fields: complainant, reported party, complaint type, and incident description.');
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
            .then(async (d) => {
                if (!d.success) {
                    alert('Error: ' + (d.error || 'Could not create case'));
                    return;
                }
                const files = newCaseEvidencePendingFiles.slice();
                if (files.length && d.case?.id) {
                    for (const file of files) {
                        const fd = new FormData();
                        fd.append('file', file);
                        fd.append('caption', 'Initial intake evidence');
                        await fetch(`/cases/${CASE_POSITION}/${d.case.id}/evidence/upload/`, {
                            method: 'POST',
                            headers: { 'X-CSRFToken': csrfToken() },
                            body: fd,
                        });
                    }
                }
                if (window.CaseDeskSync) window.CaseDeskSync.notifyChange();
                showCaseRecordedSuccess(d.case, d.message);
            })
            .catch(() => alert('Could not create case. Try again.'));
    }

    function saveCaseSettlement() {
        if (!caseSettlementPendingFiles.length) {
            alert('Add at least one settlement photograph before marking resolved.');
            return;
        }
        const fd = new FormData();
        fd.append('settlement_outcome', 'settled');
        caseSettlementPendingFiles.forEach((file) => fd.append('files', file));
        const btn = document.querySelector('.case-evidence-save-submit');
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = `<svg class="btn-icon" style="width: 0.95rem; height: 0.95rem; animation: spin 1s linear infinite;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="2" x2="12" y2="6"></line><line x1="12" y1="18" x2="12" y2="22"></line><line x1="4.93" y1="4.93" x2="7.76" y2="7.76"></line><line x1="16.24" y1="16.24" x2="19.07" y2="19.07"></line><line x1="2" y1="12" x2="6" y2="12"></line><line x1="18" y1="12" x2="22" y2="12"></line><line x1="4.93" y1="19.07" x2="7.76" y2="16.24"></line><line x1="16.24" y1="7.76" x2="19.07" y2="4.93"></line></svg> Saving”¦`;
        }
        fetch(`/cases/${CASE_POSITION}/${currentCaseId}/settlement/save/`, {
            method: 'POST',
            headers: { 'X-CSRFToken': csrfToken() },
            body: fd,
        })
            .then((r) => r.json())
            .then((d) => {
                if (!d.success) {
                    caseFlowAlert(d.error || 'Could not mark case resolved', 'Error', 'warning');
                    return;
                }
                if (d.new_status && d.status_display) {
                    updateCaseListRowStatus(currentCaseId, d.new_status, d.status_display);
                }
                caseFlowAlert(d.message || 'Case marked resolved.', 'Success', 'success');
                clearCaseSettlementPendingEvidence();
                stopCaseSettlementCamera();
                fetchCaseDetails(currentCaseId).then((resp) => {
                    if (resp.success) populateCaseModal(resp.case, { carouselSlide: 1 });
                });
                if (window.CaseDeskSync) window.CaseDeskSync.notifyChange();
            })
            .catch(() => caseFlowAlert('Could not mark case resolved. Check that the server is running.', 'Connection Error', 'warning'))
            .finally(() => {
                if (btn) {
                    btn.disabled = false;
                    btn.innerHTML = `<svg class="btn-icon" style="width: 0.95rem; height: 0.95rem;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg> Resolved`;
                }
            });
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

    function applyCaseFilters(options = {}) {
        const url = new URL(window.location.href);
        const q = document.getElementById('searchInput')?.value.trim() || '';
        const t = document.getElementById('typeFilter')?.value || 'all';
        const s = document.getElementById('statusDropdownFilter')?.value || 'all';
        
        if (q) url.searchParams.set('q', q);
        else url.searchParams.delete('q');
        
        if (t && t !== 'all') url.searchParams.set('type', t);
        else url.searchParams.delete('type');
        
        if (s && s !== 'all') {
            url.searchParams.set('status', s);
        } else if (options.status === 'mediation_monitoring') {
            url.searchParams.set('status', 'mediation_monitoring');
        } else if (options.clearStatus) {
            url.searchParams.delete('status');
        } else {
            url.searchParams.delete('status');
        }
        
        url.searchParams.delete('tab');
        window.location.href = url.toString();
    }

    function filterSettlementCases() {
        const url = new URL(window.location.href);
        const isActive = url.searchParams.get('status') === 'mediation_monitoring';
        if (isActive) {
            url.searchParams.delete('status');
        } else {
            url.searchParams.set('status', 'mediation_monitoring');
        }
        url.searchParams.delete('tab');
        window.location.href = url.toString();
    }

    function viewSettledIncidentLog(btn) {
        if (!btn) return;
        const complainantUnit = btn.getAttribute('data-complainant-unit-label')
            || btn.getAttribute('data-unit-label')
            || '—';
        const respondentUnit = btn.getAttribute('data-respondent-unit-label') || '—';
        const complainant = btn.getAttribute('data-complainant-name') || '—';
        const respondent = btn.getAttribute('data-respondent-name') || '—';
        const typeDisplay = btn.getAttribute('data-case-type-display') || '—';
        const description = btn.getAttribute('data-description') || '—';
        const loggedAt = btn.getAttribute('data-logged-at') || '—';
        const loggedBy = btn.getAttribute('data-logged-by') || 'Field';

        // Populate fields
        let loggedText = `Logged: ${loggedAt}`;
        if (loggedBy && loggedBy !== '—') {
            loggedText += ` · Recorded by ${loggedBy}`;
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
            if (respondent && respondent !== '—' && respondent !== '') {
                subjUnitEl.textContent = respondentUnit || '—';
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

    function deleteSettledIncidentLog(logId) {
        if (!logId) return;
        if (!confirm('Remove this incident log entry? This cannot be undone.')) return;
        fetch(`/cases/${CASE_POSITION}/settled-log/${encodeURIComponent(logId)}/delete/`, {
            method: 'POST',
            headers: { 'X-CSRFToken': csrfToken() },
        })
            .then((r) => r.json())
            .then((d) => {
                if (!d.success) {
                    alert(d.error || 'Could not remove incident log.');
                    return;
                }
                if (typeof showFlowAlert === 'function') {
                    showFlowAlert(d.message || 'Incident log removed.', 'Removed', null, 'success');
                }
                if (window.CaseDeskSync) window.CaseDeskSync.notifyChange();
            })
            .catch(() => alert('Could not remove incident log.'));
    }

    function openSettledLogModal() {
        document.getElementById('caseModal').style.display = 'none';
        document.getElementById('newCaseModal').style.display = 'none';
        resetSettledLogForm();
        document.body.style.overflow = 'hidden';
        document.getElementById('settledLogModal').style.display = 'flex';
    }

    function closeSettledLogModal(e) {
        if (e && e.target.id !== 'settledLogModal') return;
        document.getElementById('settledLogModal').style.display = 'none';
        document.body.style.overflow = '';
    }

    function resetSettledLogForm() {
        ['settledLogComplainantSearchInput', 'settledLogSubjectSearchInput', 'settledLogDescription'].forEach((id) => {
            const el = document.getElementById(id);
            if (el) el.value = '';
        });
        ['settledLogComplainantApplicantId', 'settledLogRelatedUnitId', 'settledLogComplainantName',
            'settledLogComplainantPhone', 'settledLogSubjectApplicantId', 'settledLogSubjectName'].forEach((id) => {
            const el = document.getElementById(id);
            if (el) el.value = '';
        });
        const typeEl = document.getElementById('settledLogType');
        if (typeEl) typeEl.value = '';
        clearSettledLogComplainantAutoFill();
        clearSettledLogSubjectAutoFill();
        ['settledLogComplainantSearchResults', 'settledLogSubjectSearchResults'].forEach((id) => {
            const el = document.getElementById(id);
            if (el) { el.style.display = 'none'; el.innerHTML = ''; }
        });
        updateSettledLogDescCount();
    }

    function clearSettledLogComplainantAutoFill() {
        ['settledLogComplainantAutoName', 'settledLogComplainantAutoRef', 'settledLogComplainantAutoUnit', 'settledLogComplainantAutoPhone']
            .forEach((id) => setReadonlyField(id, ''));
        document.getElementById('settledLogComplainantAutoFill')?.classList.remove('is-linked');
    }

    function clearSettledLogSubjectAutoFill() {
        ['settledLogSubjectAutoName', 'settledLogSubjectAutoRef', 'settledLogSubjectAutoUnit'].forEach((id) => setReadonlyField(id, ''));
        document.getElementById('settledLogSubjectAutoFill')?.classList.remove('is-linked');
    }

    function getSelectedSettledLogComplainantApplicantId() {
        return (document.getElementById('settledLogComplainantApplicantId')?.value || '').trim();
    }

    function isSameSettledLogComplainant(applicantId) {
        const cid = getSelectedSettledLogComplainantApplicantId();
        return !!(cid && applicantId && String(applicantId) === cid);
    }

    function applySettledLogComplainantSelection(row) {
        document.getElementById('settledLogComplainantApplicantId').value = row.id || '';
        document.getElementById('settledLogRelatedUnitId').value = row.unit_id || '';
        document.getElementById('settledLogComplainantName').value = row.full_name || '';
        document.getElementById('settledLogComplainantPhone').value = row.phone_number || '';
        setReadonlyField('settledLogComplainantAutoName', row.full_name);
        setReadonlyField('settledLogComplainantAutoRef', row.reference_number);
        setReadonlyField('settledLogComplainantAutoUnit', row.unit_label);
        setReadonlyField('settledLogComplainantAutoPhone', row.phone_number);
        document.getElementById('settledLogComplainantAutoFill')?.classList.add('is-linked');
        document.getElementById('settledLogComplainantSearchResults').style.display = 'none';
        document.getElementById('settledLogComplainantSearchInput').value = row.full_name || '';
        if (isSameSettledLogComplainant(document.getElementById('settledLogSubjectApplicantId')?.value)) {
            clearSettledLogSubjectAutoFill();
            document.getElementById('settledLogSubjectApplicantId').value = '';
            document.getElementById('settledLogSubjectName').value = '';
            document.getElementById('settledLogSubjectSearchInput').value = '';
        }
    }

    function applySettledLogSubjectSelection(row) {
        if (isSameSettledLogComplainant(row.id)) {
            alert('Reported party cannot be the same person as the complainant. Choose a different occupant.');
            return;
        }
        document.getElementById('settledLogSubjectApplicantId').value = row.id || '';
        document.getElementById('settledLogSubjectName').value = row.full_name || '';
        setReadonlyField('settledLogSubjectAutoName', row.full_name);
        setReadonlyField('settledLogSubjectAutoRef', row.reference_number);
        setReadonlyField('settledLogSubjectAutoUnit', row.unit_label);
        document.getElementById('settledLogSubjectAutoFill')?.classList.add('is-linked');
        document.getElementById('settledLogSubjectSearchResults').style.display = 'none';
        document.getElementById('settledLogSubjectSearchInput').value = row.full_name || '';
    }

    function updateSettledLogDescCount() {
        const el = document.getElementById('settledLogDescription');
        const c = document.getElementById('settledLogDescriptionCount');
        if (el && c) c.textContent = `${(el.value || '').length} / 150`;
    }

    function runSettledLogComplainantSearch(q) {
        runBeneficiarySearch(q, document.getElementById('settledLogComplainantSearchResults'), applySettledLogComplainantSelection);
    }

    function runSettledLogSubjectSearch(q) {
        if (!getSelectedSettledLogComplainantApplicantId()) {
            const box = document.getElementById('settledLogSubjectSearchResults');
            if (box) {
                box.innerHTML = '<p style="padding: 0.5rem; font-size: 0.8rem; color: #64748b; margin: 0;">Select the complainant first.</p>';
                box.style.display = 'block';
            }
            return;
        }
        runBeneficiarySearch(q, document.getElementById('settledLogSubjectSearchResults'), applySettledLogSubjectSelection, {
            excludeComplainant: true,
            getComplainantApplicantId: getSelectedSettledLogComplainantApplicantId,
        });
    }

    function submitSettledLog() {
        const relatedUnitId = (document.getElementById('settledLogRelatedUnitId')?.value || '').trim();
        const complainantApplicantId = (document.getElementById('settledLogComplainantApplicantId')?.value || '').trim();
        const complainantName = (document.getElementById('settledLogComplainantName')?.value || '').trim();
        const caseType = (document.getElementById('settledLogType')?.value || '').trim();
        const description = (document.getElementById('settledLogDescription')?.value || '').trim();
        if (!relatedUnitId || !complainantApplicantId || !complainantName) {
            alert('Search and select a complainant from the housing unit list.');
            return;
        }
        if (!caseType) {
            alert('Select a complaint type.');
            return;
        }
        if (!description) {
            alert('Enter an incident description.');
            return;
        }
        if (description.length > 150) {
            alert('Description must be 150 characters or less.');
            return;
        }
        const subjectApplicantId = (document.getElementById('settledLogSubjectApplicantId')?.value || '').trim();
        if (!subjectApplicantId) {
            alert('Search and select a reported party from the housing unit list.');
            return;
        }
        if (subjectApplicantId === complainantApplicantId) {
            alert('Reported party cannot be the same person as the complainant.');
            return;
        }
        fetch(`/cases/${CASE_POSITION}/settled-log/create/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() },
            body: JSON.stringify({
                related_unit_id: relatedUnitId,
                complainant_applicant_id: (document.getElementById('settledLogComplainantApplicantId')?.value || '').trim(),
                complainant_name: complainantName,
                complainant_phone: (document.getElementById('settledLogComplainantPhone')?.value || '').trim(),
                subject_applicant_id: (document.getElementById('settledLogSubjectApplicantId')?.value || '').trim(),
                subject_name: (document.getElementById('settledLogSubjectName')?.value || '').trim(),
                case_type: caseType,
                description,
            }),
        })
            .then((r) => r.json())
            .then((d) => {
                if (!d.success) {
                    alert('Error: ' + (d.error || 'Could not save log'));
                    return;
                }
                closeSettledLogModal();
                if (typeof showFlowAlert === 'function') {
                    showFlowAlert('success', d.message || 'Settled incident logged.');
                } else {
                    alert(d.message || 'Settled incident logged.');
                }
                if (window.CaseDeskSync) window.CaseDeskSync.notifyChange();
            })
            .catch(() => alert('Could not save log. Try again.'));
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
    bindBeneficiarySearchFocus('settledLogComplainantSearchInput', runSettledLogComplainantSearch);
    bindBeneficiarySearchFocus('settledLogSubjectSearchInput', runSettledLogSubjectSearch);

    document.getElementById('settledLogComplainantSearchInput')?.addEventListener('input', (e) => {
        clearTimeout(settledLogComplainantSearchTimer);
        const q = e.target.value.trim();
        settledLogComplainantSearchTimer = setTimeout(() => runSettledLogComplainantSearch(q), 300);
    });

    document.getElementById('settledLogSubjectSearchInput')?.addEventListener('input', (e) => {
        clearTimeout(settledLogSubjectSearchTimer);
        const q = e.target.value.trim();
        settledLogSubjectSearchTimer = setTimeout(() => runSettledLogSubjectSearch(q), 300);
    });

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

    document.getElementById('newCaseType')?.addEventListener('change', syncNewCasePartyMode);

    function anyCaseDeskDrawerOpen() {
        return document.getElementById('resolvedCasesDrawer')?.classList.contains('is-open')
            || document.getElementById('settledIncidentsDrawer')?.classList.contains('is-open');
    }

    function restoreCaseDeskBodyScroll() {
        const caseModalOpen = document.getElementById('caseModal')?.style.display === 'flex';
        const newCaseModalOpen = document.getElementById('newCaseModal')?.style.display === 'flex';
        const settledModalOpen = document.getElementById('settledIncidentModal')?.style.display === 'flex';
        const settledLogModalOpen = document.getElementById('settledLogModal')?.style.display === 'flex';
        if (!caseModalOpen && !newCaseModalOpen && !settledModalOpen && !settledLogModalOpen && !anyCaseDeskDrawerOpen()) {
            document.body.style.overflow = '';
        }
    }

    function openResolvedCasesDrawer() {
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

    function openCaseFromResolvedDrawer(caseId) {
        closeResolvedCasesDrawer();
        openCaseModal(caseId);
    }

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
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
        } else if (window.CASE_CONFIG && window.CASE_CONFIG.openNewCase) {
            openNewCaseModal();
        }
        const openId = params.get('case_id') || (window.CASE_CONFIG && window.CASE_CONFIG.openCaseId) || '';
        if (openId) openCaseModal(openId);
    }

    function caseFlowAlert(message, title, variant, onConfirm) {
        var tone = 'default';
        if (variant === 'success') tone = 'success';
        else if (variant === 'warning') tone = 'warning';
        if (typeof showFlowAlert === 'function') {
            showFlowAlert(message || '', title || 'Notice', onConfirm || null, tone);
            return;
        }
        alert(message || '');
        if (typeof onConfirm === 'function') onConfirm();
    }

    function casePhotoLimitAlert() {
        caseFlowAlert(
            'Maximum 4 evidence photos.\n\nRemove one before adding another.',
            'Photo limit reached',
            'warning'
        );
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
            ? `Case ${caseNumber} was saved and added to the case list.\nStatus: ${statusText}.`
            : `The complaint was saved and added to the case list.\nStatus: ${statusText}.`;
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
        bindNewCaseEvidenceControls();
        if (typeof initListPagination === 'function') {
            window.caseDeskPaginationApi = initListPagination({
                pageSize: 5,
                rowSelector: '#caseDeskTableBody > tr',
                cardSelector: '#caseDeskMobileCards .m-case-card',
                infoEl: 'caseDeskPaginationInfo',
                prevBtn: 'caseDeskPrevBtn',
                nextBtn: 'caseDeskNextBtn',
                pageIndicator: 'caseDeskPageIndicator'
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

        let hideTimeout;

        function hideApplicantHoverCard() {
            if (!hoverCard) return;
            hoverCard.classList.remove('active', 'position-below');
            hoverCard.setAttribute('hidden', '');
            hoverCard.setAttribute('aria-hidden', 'true');
            hoverCard.style.left = '';
            hoverCard.style.top = '';
        }

        function showApplicantHoverCard() {
            if (!hoverCard) return;
            hoverCard.removeAttribute('hidden');
            hoverCard.setAttribute('aria-hidden', 'false');
            hoverCard.classList.add('active');
        }

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

            // Position card (fixed — follows viewport, not document flow)
            const rect = nameSpan.getBoundingClientRect();

            hoverCard.removeAttribute('hidden');
            hoverCard.style.visibility = 'hidden';
            hoverCard.style.pointerEvents = 'none';
            hoverCard.style.display = 'block';
            const cardWidth = hoverCard.offsetWidth || 290;
            const cardHeight = hoverCard.offsetHeight || 190;
            hoverCard.style.display = '';
            hoverCard.style.visibility = '';
            hoverCard.style.pointerEvents = '';
            hoverCard.setAttribute('hidden', '');

            let targetLeft = rect.left + (rect.width / 2) - (cardWidth / 2);
            let targetTop = rect.top - cardHeight - 12;

            if (targetLeft < 10) targetLeft = 10;
            if (targetLeft + cardWidth > window.innerWidth - 10) {
                targetLeft = window.innerWidth - cardWidth - 10;
            }

            if (rect.top - cardHeight - 12 < 10) {
                targetTop = rect.bottom + 12;
                hoverCard.classList.add('position-below');
            } else {
                hoverCard.classList.remove('position-below');
            }

            hoverCard.style.left = targetLeft + 'px';
            hoverCard.style.top = targetTop + 'px';
            showApplicantHoverCard();
        });

        document.addEventListener('mouseout', function (e) {
            const nameSpan = e.target.closest('.applicant-name');
            const isHoverCard = e.target.closest('#applicantHoverCard');

            if (nameSpan || isHoverCard) {
                hideTimeout = setTimeout(hideApplicantHoverCard, 250);
            }
        });

        if (hoverCard) {
            hoverCard.addEventListener('mouseenter', function () {
                clearTimeout(hideTimeout);
            });

            hoverCard.addEventListener('mouseleave', function () {
                hideTimeout = setTimeout(hideApplicantHoverCard, 250);
            });
        }
    });

    /* ── Add Case accordion toggle ─────────────────────────────────── */
    window.toggleCaseAccordion = function (accordionId) {
        const el = document.getElementById(accordionId);
        if (!el) return;
        el.classList.toggle('collapsed');
    };
