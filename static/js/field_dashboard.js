        let fieldCameraStream = null;
        let fieldCameraFacingMode = 'environment';
        const fieldEvidenceFiles = [];
        const fieldEvidenceObjectUrls = [];

        document.addEventListener('DOMContentLoaded', function() {
            initScrollAnimations();
            initFieldKpiCards();
            if (typeof initListPagination === 'function') {
                initListPagination({
                    pageSize: 5,
                    rowSelector: '#fieldPendingTableBody > tr',
                    cardSelector: '#fieldPendingMobileCards .mobile-verification-card',
                    infoEl: 'fieldPendingPaginationInfo',
                    prevBtn: 'fieldPendingPrevBtn',
                    nextBtn: 'fieldPendingNextBtn',
                    pageIndicator: 'fieldPendingPageIndicator'
                });
            }
            const startBtn = document.getElementById('fieldCameraStartBtn');
            const capBtn = document.getElementById('fieldCameraCaptureBtn');
            const switchBtn = document.getElementById('fieldCameraSwitchBtn');
            const stopBtn = document.getElementById('fieldCameraStopBtn');
            const pickBtn = document.getElementById('fieldEvidenceFilePickBtn');
            const fileInput = document.getElementById('fieldEvidenceFileInput');
            if (startBtn) startBtn.addEventListener('click', startFieldCamera);
            if (capBtn) capBtn.addEventListener('click', captureFieldPhoto);
            if (switchBtn) switchBtn.addEventListener('click', toggleFieldCamera);
            if (stopBtn) stopBtn.addEventListener('click', stopFieldCamera);
            if (pickBtn && fileInput) {
                pickBtn.addEventListener('click', function() { fileInput.click(); });
                fileInput.addEventListener('change', onFieldEvidenceFilesSelected);
            }

            /* --- Carousel nav wiring --- */
            const fePrev = document.getElementById('fieldEvidencePrev');
            const feNext = document.getElementById('fieldEvidenceNext');
            const feRem  = document.getElementById('fieldEvidenceRemoveBtn');
            if (fePrev) fePrev.addEventListener('click', function() {
                if (fieldEvidenceCarouselIndex > 0) {
                    fieldEvidenceCarouselIndex--;
                    refreshFieldEvidenceCarousel();
                }
            });
            if (feNext) feNext.addEventListener('click', function() {
                if (fieldEvidenceCarouselIndex < fieldEvidenceFiles.length - 1) {
                    fieldEvidenceCarouselIndex++;
                    refreshFieldEvidenceCarousel();
                }
            });
            if (feRem) feRem.addEventListener('click', function() {
                removeFieldEvidenceAt(fieldEvidenceCarouselIndex);
            });

            const certifiedModal = document.getElementById('certifiedApplicantsModal');
            if (certifiedModal) {
                certifiedModal.addEventListener('click', function(e) {
                    if (e.target === certifiedModal) closeCertifiedApplicantsModal();
                });
            }
            const todaySummaryModal = document.getElementById('todaySummaryModal');
            if (todaySummaryModal) {
                todaySummaryModal.addEventListener('click', function(e) {
                    if (e.target === todaySummaryModal) closeTodaySummaryModal();
                });
            }
            document.addEventListener('keydown', function(e) {
                if (e.key !== 'Escape') return;
                const vm = document.getElementById('verificationModal');
                if (vm && vm.style.display === 'flex') { closeVerificationModal(); return; }
                const cm = document.getElementById('certifiedApplicantsModal');
                if (cm && cm.style.display === 'flex') { closeCertifiedApplicantsModal(); return; }
                const tm = document.getElementById('todaySummaryModal');
                if (tm && tm.style.display === 'flex') closeTodaySummaryModal();
            });
        });

        function initFieldKpiCards() {
            document.querySelectorAll('.field-kpi-card--interactive').forEach(function(card) {
                card.addEventListener('click', function() {
                    const action = card.getAttribute('data-kpi-action');
                    if (action === 'pending') scrollToFieldPendingQueue();
                    else if (action === 'certified') openCertifiedApplicantsModal();
                    else if (action === 'today') showMyVerifications();
                });
                card.addEventListener('keydown', function(e) {
                    if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        card.click();
                    }
                });
            });
        }

        function scrollToFieldPendingQueue() {
            const el = document.getElementById('field-pending-queue');
            if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }

        function openCertifiedApplicantsModal() {
            const m = document.getElementById('certifiedApplicantsModal');
            if (!m) return;
            m.style.display = 'flex';
            document.body.style.overflow = 'hidden';
        }

        window.closeCertifiedApplicantsModal = closeCertifiedApplicantsModal;
        function closeCertifiedApplicantsModal() {
            const m = document.getElementById('certifiedApplicantsModal');
            if (!m) return;
            m.style.display = 'none';
            document.body.style.overflow = '';
        }

        /**
         * Scroll Animations - Intersection Observer
         */
        function initScrollAnimations() {
            // Check for reduced motion preference
            const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

            if (prefersReducedMotion) {
                // Just show everything immediately
                document.querySelectorAll(
                    '.scroll-animate, .scroll-animate-left, .scroll-animate-right, ' +
                    '.scroll-animate-scale, .scroll-animate-fade, .scroll-animate-bounce, ' +
                    '.scroll-animate-rotate, .scroll-animate-blur, .scroll-animate-card'
                ).forEach(function(el) {
                    el.classList.add('animate-in');
                });
                return;
            }

            // Select all elements with scroll animation classes
            const animatedElements = document.querySelectorAll(
                '.scroll-animate, .scroll-animate-left, .scroll-animate-right, ' +
                '.scroll-animate-scale, .scroll-animate-fade, .scroll-animate-bounce, ' +
                '.scroll-animate-rotate, .scroll-animate-blur, .scroll-animate-card'
            );

            // Create intersection observer
            const observerOptions = {
                root: null, // viewport
                rootMargin: '0px 0px -50px 0px', // trigger slightly before element enters
                threshold: 0.1 // 10% visible triggers animation
            };

            const scrollObserver = new IntersectionObserver(function(entries, observer) {
                entries.forEach(function(entry) {
                    if (entry.isIntersecting) {
                        entry.target.classList.add('animate-in');
                        // Once animated, stop observing (one-time animation)
                        observer.unobserve(entry.target);
                    }
                });
            }, observerOptions);

            // Observe each element
            animatedElements.forEach(function(element) {
                scrollObserver.observe(element);
            });
        }

        // Auto-refresh data every 5 minutes
        setTimeout(() => {
            location.reload();
        }, 5 * 60 * 1000);

        function clearFieldEvidenceUI() {
            fieldEvidenceObjectUrls.forEach(function(u) { try { URL.revokeObjectURL(u); } catch (e) {} });
            fieldEvidenceObjectUrls.length = 0;
            fieldEvidenceFiles.length = 0;
            fieldEvidenceCarouselIndex = 0;
            if (_fieldEvidenceObjUrl) { try { URL.revokeObjectURL(_fieldEvidenceObjUrl); } catch(e) {} _fieldEvidenceObjUrl = null; }
            const fi = document.getElementById('fieldEvidenceFileInput');
            if (fi) fi.value = '';
            refreshFieldEvidenceCarousel();
        }

        let fieldEvidenceCarouselIndex = 0;
        let _fieldEvidenceObjUrl = null;

        function refreshFieldEvidenceCarousel() {
            if (typeof updateVerificationProgress === 'function') updateVerificationProgress();
            const carousel = document.getElementById('fieldEvidenceCarousel');
            const img      = document.getElementById('fieldEvidenceImg');
            const counter  = document.getElementById('fieldEvidenceCounter');
            const prev     = document.getElementById('fieldEvidencePrev');
            const next     = document.getElementById('fieldEvidenceNext');
            const label    = document.getElementById('fieldEvidenceNoPhotoLabel');

            if (!carousel || !img) return;

            if (fieldEvidenceFiles.length === 0) {
                carousel.hidden = true;
                if (label) { label.style.display = 'block'; label.textContent = '0 / 4 photos captured'; }
                return;
            }

            carousel.hidden = false;
            if (label) label.style.display = 'none';

            if (_fieldEvidenceObjUrl) { try { URL.revokeObjectURL(_fieldEvidenceObjUrl); } catch(e) {} }
            _fieldEvidenceObjUrl = URL.createObjectURL(fieldEvidenceFiles[fieldEvidenceCarouselIndex]);
            img.src = _fieldEvidenceObjUrl;

            const total = fieldEvidenceFiles.length;
            if (counter) counter.textContent = (fieldEvidenceCarouselIndex + 1) + ' / ' + total;
            if (prev) prev.hidden = (total <= 1);
            if (next) next.hidden = (total <= 1);
        }

        function requestFieldDashboardCameraStream(onSuccess, onError) {
            const facing = fieldCameraFacingMode;
            const attempts = [
                { video: { facingMode: { ideal: facing } }, audio: false },
                { video: { facingMode: facing }, audio: false },
                { video: true, audio: false },
            ];
            let lastErr = null;
            let index = 0;
            function tryNext() {
                if (index >= attempts.length) {
                    onError(lastErr || new Error('Could not open camera'));
                    return;
                }
                navigator.mediaDevices.getUserMedia(attempts[index++])
                    .then(onSuccess)
                    .catch(function(err) {
                        lastErr = err;
                        if (err && (err.name === 'NotAllowedError' || err.name === 'SecurityError' || err.name === 'NotReadableError')) {
                            onError(err);
                            return;
                        }
                        tryNext();
                    });
            }
            tryNext();
        }

        function showFieldCameraUi(stream) {
            fieldCameraStream = stream;
            const vWrap = document.getElementById('fieldVideoWrap');
            if (vWrap) vWrap.style.display = 'flex';
            const mainBtns = document.getElementById('fieldMainButtons');
            if (mainBtns) mainBtns.style.display = 'none';
            const v = document.getElementById('fieldCameraVideo');
            if (v) {
                v.srcObject = stream;
                const playPromise = v.play();
                if (playPromise && typeof playPromise.catch === 'function') {
                    playPromise.catch(function() {});
                }
            }
        }

        function stopFieldCamera() {
            if (fieldCameraStream) {
                fieldCameraStream.getTracks().forEach(function(t) { t.stop(); });
                fieldCameraStream = null;
            }
            const v = document.getElementById('fieldCameraVideo');
            if (v) {
                v.srcObject = null;
            }
            const vWrap = document.getElementById('fieldVideoWrap');
            if (vWrap) vWrap.style.display = 'none';
            const mainBtns = document.getElementById('fieldMainButtons');
            if (mainBtns) mainBtns.style.display = 'flex';
        }

        function fieldNotify(message, title, variant) {
            if (typeof window.showFlowAlert === 'function') {
                window.showFlowAlert(message, title || 'Notice', null, variant || 'default');
            } else {
                alert(message);
            }
        }

        function startFieldCamera() {
            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                fieldNotify('This browser does not support in-page camera access. Please use “Attach from device” to upload photographs.', 'Camera unavailable');
                return;
            }
            if (fieldCameraStream) {
                fieldCameraStream.getTracks().forEach(function(t) { t.stop(); });
                fieldCameraStream = null;
            }
            requestFieldDashboardCameraStream(
                showFieldCameraUi,
                function(err) {
                    stopFieldCamera();
                    const detail = err && err.message ? err.message : 'permission denied';
                    fieldNotify('Could not open camera: ' + detail + '. Click Allow when prompted, or use Attach from device.', 'Camera blocked');
                }
            );
        }

        function toggleFieldCamera() {
            fieldCameraFacingMode = (fieldCameraFacingMode === 'environment') ? 'user' : 'environment';
            if (fieldCameraStream) {
                startFieldCamera();
            }
        }

        function captureFieldPhoto() {
            const v = document.getElementById('fieldCameraVideo');
            const c = document.getElementById('fieldCameraCanvas');
            if (!v || !c || !v.videoWidth) {
                fieldNotify('Wait for the camera preview to appear, then capture again.', 'Camera not ready');
                return;
            }
            if (fieldEvidenceFiles.length >= 4) {
                fieldNotify('Maximum 4 evidence photos.', 'Photo limit reached', 'warning');
                return;
            }
            let origWidth = v.videoWidth || 1280;
            let origHeight = v.videoHeight || 720;
            
            /* Crop to match the UI's exact rendered aspect ratio so the photo perfectly matches the preview */
            let rect = v.getBoundingClientRect();
            let targetAspect = rect.width / rect.height || (16 / 9);
            let sourceAspect = origWidth / origHeight;
            let srcCropWidth = origWidth;
            let srcCropHeight = origHeight;
            let srcOffsetX = 0;
            let srcOffsetY = 0;

            if (sourceAspect > targetAspect) {
                srcCropWidth = Math.floor(origHeight * targetAspect);
                srcOffsetX = Math.floor((origWidth - srcCropWidth) / 2);
            } else if (sourceAspect < targetAspect) {
                srcCropHeight = Math.floor(origWidth / targetAspect);
                srcOffsetY = Math.floor((origHeight - srcCropHeight) / 2);
            }

            /* Optimization: Scale down 4K/high-res streams to max 1280px */
            let destWidth = srcCropWidth;
            let destHeight = srcCropHeight;
            const MAX_DIMENSION = 1280;
            if (destWidth > MAX_DIMENSION || destHeight > MAX_DIMENSION) {
                const ratio = Math.min(MAX_DIMENSION / destWidth, MAX_DIMENSION / destHeight);
                destWidth = Math.floor(destWidth * ratio);
                destHeight = Math.floor(destHeight * ratio);
            }

            c.width = destWidth;
            c.height = destHeight;
            c.getContext('2d').drawImage(v, srcOffsetX, srcOffsetY, srcCropWidth, srcCropHeight, 0, 0, destWidth, destHeight);
            
            c.toBlob(function(blob) {
                if (!blob) return;
                const file = new File([blob], 'site-evidence-' + Date.now() + '.jpg', { type: 'image/jpeg' });
                addFieldEvidenceFile(file);
            }, 'image/jpeg', 0.8);
        }

        function addFieldEvidenceFile(file) {
            if (fieldEvidenceFiles.length >= 4) {
                fieldNotify('Maximum 4 evidence photos.', 'Photo limit reached', 'warning');
                return;
            }
            const maxBytes = 6 * 1024 * 1024;
            if (file.size > maxBytes) {
                fieldNotify('Each photo must be 6 MB or smaller: ' + (file.name || 'file'), 'Photo too large');
                return;
            }
            fieldEvidenceFiles.push(file);
            fieldEvidenceCarouselIndex = fieldEvidenceFiles.length - 1;
            refreshFieldEvidenceCarousel();
        }

        function removeFieldEvidenceAt(index) {
            if (index < 0 || index >= fieldEvidenceFiles.length) return;
            fieldEvidenceFiles.splice(index, 1);
            if (fieldEvidenceCarouselIndex >= fieldEvidenceFiles.length) {
                fieldEvidenceCarouselIndex = Math.max(0, fieldEvidenceFiles.length - 1);
            }
            refreshFieldEvidenceCarousel();
        }

        function onFieldEvidenceFilesSelected(ev) {
            const files = ev.target.files;
            if (!files) return;
            for (let i = 0; i < files.length; i++) {
                if (fieldEvidenceFiles.length >= 4) break;
                addFieldEvidenceFile(files[i]);
            }
            ev.target.value = '';
        }

        function formatHazardClassification(code) {
            if (!code || !String(code).trim()) return '—';
            const key = String(code).trim().toLowerCase().replace(/-/g, '_');
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
            return map[key] || String(code).replace(/_/g, ' ');
        }

        const FIELD_PENDING_CDRRMO_META = (function () {
            const el = document.getElementById('field-pending-cdrrmo-meta');
            if (!el || !el.textContent) return {};
            try {
                return JSON.parse(el.textContent);
            } catch (e) {
                return {};
            }
        })();

        function formatFieldCdrrmoDateTime(iso) {
            if (!iso) return '—';
            const d = new Date(iso);
            if (Number.isNaN(d.getTime())) return '—';
            const datePart = d.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' });
            const timePart = d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
            return datePart + ' ' + timePart;
        }

        const FIELD_CDRRMO_META_URL_TEMPLATE = (window.DASHBOARD_CONFIG && window.DASHBOARD_CONFIG.cdrrmoMetaUrlTemplate) || '';

        function applyFieldCdrrmoMeta(meta) {
            const cdrrmoStatusText = document.getElementById('cdrrmoStatusText');
            const cdrrmoDateText = document.getElementById('cdrrmoDateText');
            if (!cdrrmoStatusText || !cdrrmoDateText) return;
            if (!meta) {
                cdrrmoStatusText.textContent = '—';
                cdrrmoDateText.textContent = '—';
                if (typeof updateVerificationProgress === 'function') updateVerificationProgress();
                return;
            }
            if (meta.status === 'certified') {
                cdrrmoStatusText.textContent = 'Certified — danger zone (government record)';
                cdrrmoStatusText.style.color = '#166534';
            } else if (meta.status === 'not_certified') {
                cdrrmoStatusText.textContent = 'Not certified — hazard claim not verified';
                cdrrmoStatusText.style.color = '#991b1b';
            } else if (meta.document_at) {
                cdrrmoStatusText.textContent = 'CDRRMO certification on file — awaiting field verification report';
                cdrrmoStatusText.style.color = '#1d4ed8';
            } else {
                cdrrmoStatusText.textContent = 'Pending — awaiting field verification report';
                cdrrmoStatusText.style.color = '#78350f';
            }
            const verifiedIso = meta.certified_at || meta.document_at || null;
            cdrrmoDateText.textContent = formatFieldCdrrmoDateTime(verifiedIso);
            if (typeof updateVerificationProgress === 'function') updateVerificationProgress();
        }

        async function refreshFieldCdrrmoMeta(applicantId) {
            const embedded = FIELD_PENDING_CDRRMO_META[String(applicantId)] || {};
            applyFieldCdrrmoMeta(embedded);
            const url = FIELD_CDRRMO_META_URL_TEMPLATE.replace(
                '00000000-0000-4000-8000-000000000001',
                encodeURIComponent(applicantId)
            );
            try {
                const resp = await fetch(url, {
                    headers: { Accept: 'application/json' },
                    credentials: 'same-origin',
                });
                const contentType = (resp.headers.get('content-type') || '').toLowerCase();
                if (!resp.ok || !contentType.includes('application/json')) return;
                const data = await resp.json();
                if (data.success && data.meta) {
                    applyFieldCdrrmoMeta(data.meta);
                    FIELD_PENDING_CDRRMO_META[String(applicantId)] = data.meta;
                }
            } catch (err) {
                /* keep embedded snapshot */
            }
        }

        // Field Verification Modal
        window.openVerificationModal = openVerificationModal;
        async function openVerificationModal(applicantId, applicantName, address, dangerZoneType, dangerZoneLocation, referenceNumber) {
            clearFieldEvidenceUI();
            stopFieldCamera();

            // Reset accordions to collapsed state
            ['sectionApplicantDec', 'cdrrmoStatusBox', 'sectionSitePhotos'].forEach(id => {
                const el = document.getElementById(id);
                if (el) {
                    el.classList.remove('expanded');
                    el.classList.add('collapsed');
                }
            });

            document.getElementById('verificationModalApplicantId').value = applicantId;
            document.getElementById('verificationModalName').textContent = applicantName;
            document.getElementById('verificationModalAddress').textContent = address;
            document.getElementById('verificationModalDangerZone').textContent = formatHazardClassification(dangerZoneType);
            document.getElementById('verificationModalLocation').textContent =
                (dangerZoneLocation && dangerZoneLocation.trim()) ? dangerZoneLocation.trim() : '—';

            const cdrrmoStatusBox = document.getElementById('cdrrmoStatusBox');
            const cdrrmoRefText = document.getElementById('cdrrmoRefText');

            cdrrmoRefText.textContent = referenceNumber && referenceNumber.trim() ? referenceNumber.trim() : '—';

            if (dangerZoneType) {
                cdrrmoStatusBox.style.display = 'block';
                void refreshFieldCdrrmoMeta(applicantId);
            } else {
                cdrrmoStatusBox.style.display = 'none';
                applyFieldCdrrmoMeta(null);
            }

            document.getElementById('verificationModal').style.display = 'flex';
            document.body.style.overflow = 'hidden';
            if (typeof updateVerificationProgress === 'function') updateVerificationProgress();
        }

        window.closeVerificationModal = closeVerificationModal;
        function closeVerificationModal() {
            stopFieldCamera();
            clearFieldEvidenceUI();
            document.getElementById('verificationModal').style.display = 'none';
            document.body.style.overflow = 'auto';
            document.getElementById('verificationForm').reset();
        }

        function submitVerification(event) {
            event.preventDefault();

            const applicantId = document.getElementById('verificationModalApplicantId').value;
            const notesEl = document.getElementById('verificationNotes');
            const verificationNotes = notesEl ? notesEl.value.trim() : '';

            if (!fieldEvidenceFiles.length) {
                fieldNotify('Attach at least one site photograph (capture from camera or pick from device) before submitting. Photos are required so Module 2 can verify the field record.', 'Site photo required');
                return;
            }

            const formData = new FormData();
            formData.append('applicant_id', applicantId);
            formData.append('verification_decision', 'certified');
            formData.append('verification_notes', verificationNotes);
            fieldEvidenceFiles.forEach(function(file) {
                formData.append('evidence_photos', file, file.name);
            });

            const dash = document.querySelector('.dashboard-container');
            const currentPosition = (dash && dash.dataset.userPosition) ? dash.dataset.userPosition : 'field';

            fetch(`/applications/staff/${currentPosition}/field-verify-cdrrmo/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]')?.value ||
                                 document.querySelector('input[name="_token"]')?.value ||
                                 getCookie('csrftoken')
                },
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    var photoMsg = (typeof data.photos_saved === 'number' && data.photos_saved > 0)
                        ? ('\n\nAttached ' + data.photos_saved + ' site photograph(s) to this certification.')
                        : '';
                    var smsMsg = '';
                    if (Object.prototype.hasOwnProperty.call(data, 'sms_dispatched')) {
                        smsMsg = data.sms_dispatched
                            ? '\n\nA status SMS was queued for the applicant’s contact number (check SMSLog / server output if using console mode).'
                            : '\n\nNo SMS was queued (missing or invalid mobile number, or gateway error).';
                    }
                    try {
                        var _ts = String(Date.now());
                        localStorage.setItem('tha_field_cert_sync', _ts);
                        if (typeof BroadcastChannel !== 'undefined') {
                            var _bc = new BroadcastChannel('tha_field_cert_sync_bc');
                            _bc.postMessage({ t: _ts });
                            _bc.close();
                        }
                    } catch (ignoreLs) { /* private mode / quota */ }
                    var successMessage = data.message + photoMsg + smsMsg
                        + '\n\nThe field certification has been recorded and is now available in Module 2 (Application & Eligibility) for staff review.';
                    var onAck = function () {
                        closeVerificationModal();
                        setTimeout(function () { location.reload(); }, 200);
                    };
                    if (typeof window.showFlowAlert === 'function') {
                        window.showFlowAlert(successMessage, 'Verification recorded', onAck, 'success');
                    } else {
                        alert(successMessage);
                        onAck();
                    }
                } else {
                    var errMsg = 'Submission could not be completed: ' + data.error;
                    if (typeof window.showFlowAlert === 'function') {
                        window.showFlowAlert(errMsg, 'Submission failed', null, 'default');
                    } else {
                        alert(errMsg);
                    }
                }
            })
            .catch(error => {
                var netMsg = 'Network or server error: ' + error;
                if (typeof window.showFlowAlert === 'function') {
                    window.showFlowAlert(netMsg, 'Network error', null, 'default');
                } else {
                    alert(netMsg);
                }
                console.error('Fetch error:', error);
            });
        }

        function getCookie(name) {
            let cookieValue = null;
            if (document.cookie && document.cookie !== '') {
                const cookies = document.cookie.split(';');
                for (let i = 0; i < cookies.length; i++) {
                    const cookie = cookies[i].trim();
                    if (cookie.substring(0, name.length + 1) === (name + '=')) {
                        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                        break;
                    }
                }
            }
            return cookieValue;
        }

        // Close modal when clicking outside
        window.addEventListener('click', function(event) {
            const modal = document.getElementById('verificationModal');
            if (event.target === modal) {
                closeVerificationModal();
            }
        });

        // Show "Today's summary" modal (recorded + photographed today)
        function showMyVerifications() {
            const m = document.getElementById('todaySummaryModal');
            if (!m) return;
            m.style.display = 'flex';
            document.body.style.overflow = 'hidden';
        }

        window.closeTodaySummaryModal = closeTodaySummaryModal;
        function closeTodaySummaryModal() {
            const m = document.getElementById('todaySummaryModal');
            if (!m) return;
            m.style.display = 'none';
            document.body.style.overflow = '';
        }

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

        window.toggleAccordion = function(sectionId) {
            const el = document.getElementById(sectionId);
            if (!el) return;
            if (el.classList.contains('collapsed')) {
                el.classList.remove('collapsed');
                el.classList.add('expanded');
            } else {
                el.classList.remove('expanded');
                el.classList.add('collapsed');
            }
        };

        window.updateVerificationProgress = function() {
            // Update Photos
            const photoCount = typeof fieldEvidenceFiles !== 'undefined' ? fieldEvidenceFiles.length : 0;
            const progressPhotosCount = document.getElementById('progressPhotosCount');
            if (progressPhotosCount) {
                progressPhotosCount.textContent = photoCount + '/4';
                if (photoCount >= 1) {
                    progressPhotosCount.className = 'progress-icon success';
                    if (photoCount === 4) { progressPhotosCount.textContent = '✓'; }
                } else {
                    progressPhotosCount.className = 'progress-icon warning';
                }
            }

            // Update CDRRMO Status
            const cdrrmoStatusTextEl = document.getElementById('cdrrmoStatusText');
            const progressCdrrmoStatus = document.getElementById('progressCdrrmoStatus');
            const progressCdrrmoIcon = document.getElementById('progressCdrrmoIcon');
            const cdrrmoStatusBox = document.getElementById('cdrrmoStatusBox');
            
            if (cdrrmoStatusBox && cdrrmoStatusBox.style.display !== 'none') {
                if(progressCdrrmoStatus) progressCdrrmoStatus.style.display = 'flex';
                const statusStr = cdrrmoStatusTextEl ? cdrrmoStatusTextEl.textContent : '';
                if (statusStr.includes('Certified') && !statusStr.includes('Not certified')) {
                    if(progressCdrrmoIcon) { progressCdrrmoIcon.className = 'progress-icon success'; progressCdrrmoIcon.textContent = '✓'; }
                } else if (statusStr.includes('Not certified')) {
                    if(progressCdrrmoIcon) { progressCdrrmoIcon.className = 'progress-icon warning'; progressCdrrmoIcon.textContent = '⚠'; }
                } else {
                    if(progressCdrrmoIcon) { progressCdrrmoIcon.className = 'progress-icon warning'; progressCdrrmoIcon.textContent = '⚠'; }
                }
            } else {
                if(progressCdrrmoStatus) progressCdrrmoStatus.style.display = 'none';
            }
        };
