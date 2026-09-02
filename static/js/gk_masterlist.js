/* GK Masterlist — Block carousel */
(function () {
    'use strict';
    var wrap    = document.querySelector('.gk-carousel-track-wrap');
    var track   = document.getElementById('gkTrack');
    if (!track || !wrap) return;

    var prevBtn = document.getElementById('gkPrev');
    var nextBtn = document.getElementById('gkNext');
    var counter = document.getElementById('gkCounter');
    var dots    = Array.prototype.slice.call(document.querySelectorAll('.gk-dot'));
    var slides  = Array.prototype.slice.call(track.children);
    var total   = slides.length;
    var current = 0;

    /* Give every slide the exact pixel width of the visible wrapper */
    function sizeSlides() {
        if (total <= 1) {
            slides.forEach(function (s) { s.style.width = '100%'; });
            return;
        }
        var w = wrap.getBoundingClientRect().width || wrap.offsetWidth;
        if (w > 0) {
            slides.forEach(function (s) { s.style.width = w + 'px'; });
        }
    }

    function slideWidth() {
        if (total <= 1) return 0;
        return wrap.getBoundingClientRect().width || wrap.offsetWidth;
    }

    function goTo(idx, immediate) {
        current = Math.max(0, Math.min(idx, total - 1));
        if (total <= 1) {
            track.style.transform = 'none';
        } else if (immediate) {
            var prevTrans = track.style.transition;
            track.style.transition = 'none';
            track.style.transform = 'translateX(-' + (current * slideWidth()) + 'px)';
            void track.offsetWidth; // force reflow
            track.style.transition = prevTrans || '';
        } else {
            track.style.transform = 'translateX(-' + (current * slideWidth()) + 'px)';
        }
        dots.forEach(function (d, i) { d.classList.toggle('is-active', i === current); });
        if (counter) counter.textContent = (current + 1) + ' / ' + total;
        if (prevBtn) prevBtn.disabled = current === 0;
        if (nextBtn) nextBtn.disabled = current === total - 1;
    }

    function updateLayout(immediate) {
        sizeSlides();
        goTo(current, immediate);
    }

    if (prevBtn) prevBtn.addEventListener('click', function () { goTo(current - 1); });
    if (nextBtn) nextBtn.addEventListener('click', function () { goTo(current + 1); });
    dots.forEach(function (d) {
        d.addEventListener('click', function () { goTo(parseInt(d.dataset.idx, 10)); });
    });

    /* Keyboard ← → */
    document.addEventListener('keydown', function (e) {
        if (document.activeElement && document.activeElement.tagName === 'INPUT') return;
        if (e.key === 'ArrowLeft')  goTo(current - 1);
        if (e.key === 'ArrowRight') goTo(current + 1);
    });

    /* Touch / pointer swipe */
    var startX = 0;
    track.addEventListener('pointerdown', function (e) {
        startX = e.clientX;
        track.setPointerCapture(e.pointerId);
    });
    track.addEventListener('pointerup', function (e) {
        var diff = e.clientX - startX;
        if (Math.abs(diff) > 55) goTo(diff < 0 ? current + 1 : current - 1);
    });

    /* ResizeObserver: responds immediately whenever container width changes (e.g. sidebar toggle) */
    if (window.ResizeObserver) {
        var ro = new ResizeObserver(function () {
            updateLayout(true);
        });
        ro.observe(wrap);
    }

    /* Window resize */
    window.addEventListener('resize', function () {
        updateLayout(true);
    });

    /* Smooth resizing during sidebar collapse/expand transition (300ms) */
    function animateSidebarResize() {
        var start = performance.now();
        function tick(now) {
            updateLayout(true);
            if (now - start < 360) {
                requestAnimationFrame(tick);
            } else {
                updateLayout(false);
            }
        }
        requestAnimationFrame(tick);
    }

    var toggleBtn = document.getElementById('sidebarToggleBtn');
    if (toggleBtn) {
        toggleBtn.addEventListener('click', animateSidebarResize);
    }
    var mobileMenuBtn = document.getElementById('mobileMenuBtn');
    if (mobileMenuBtn) {
        mobileMenuBtn.addEventListener('click', animateSidebarResize);
    }

    var mainContent = document.querySelector('.main-content');
    if (mainContent) {
        mainContent.addEventListener('transitionend', function (e) {
            if (e.propertyName === 'margin-left' || e.propertyName === 'width') {
                updateLayout(false);
            }
        });
    }

    /* Init — defer until browser has finished layout so offsetWidth is non-zero */
    requestAnimationFrame(function () {
        requestAnimationFrame(function () {
            updateLayout(true);
        });
    });
}());

/* ─────────────────────────────────────────────────────────────────────────────
   GK Masterlist — Modal & Form Logic
   URLs are read from #gkUrlBridge data attributes (set in the HTML template)
   so this file remains a pure static asset with zero Django template tags.
───────────────────────────────────────────────────────────────────────────── */
(function () {
    'use strict';

    /* ── URL bridge ── */
    var bridge = document.getElementById('gkUrlBridge');
    var IMPORT_URL   = bridge ? bridge.dataset.importUrl   : '';
    var REGISTER_URL = bridge ? bridge.dataset.registerUrl : '';

    /* ── CSRF helper ── */
    function getGkCsrf() {
        var el = document.querySelector('#gkImportForm input[name=csrfmiddlewaretoken], #gkRegisterForm input[name=csrfmiddlewaretoken]');
        if (el && el.value) return el.value;
        var m = document.cookie.match(/csrftoken=([^;]+)/);
        return m ? decodeURIComponent(m[1]) : '';
    }

    /* ── Modal helpers ── */
    function openGkImportModal() {
        var m = document.getElementById('gkImportModal');
        if (!m) return;
        document.getElementById('gkImportError').style.display = 'none';
        m.classList.add('is-open');
    }
    function closeGkImportModal() {
        var m = document.getElementById('gkImportModal');
        if (m) m.classList.remove('is-open');
    }
    function openGkRegisterModal() {
        var m = document.getElementById('gkRegisterModal');
        if (!m) return;
        document.getElementById('gkRegisterError').style.display = 'none';
        m.classList.add('is-open');
    }
    function closeGkRegisterModal() {
        var m = document.getElementById('gkRegisterModal');
        if (m) m.classList.remove('is-open');
    }

    /* Expose modal openers globally (called from inline onclick attributes in HTML) */
    window.openGkImportModal   = openGkImportModal;
    window.closeGkImportModal  = closeGkImportModal;
    window.openGkRegisterModal  = openGkRegisterModal;
    window.closeGkRegisterModal = closeGkRegisterModal;

    /* ── Input mask helpers ── */
    function gkBindUpperNameInput(el) {
        if (!el) return;
        el.addEventListener('input', function () {
            var start = el.selectionStart;
            var end   = el.selectionEnd;
            el.value  = el.value.toUpperCase();
            if (start != null && end != null) {
                el.setSelectionRange(start, end);
            }
        });
    }

    function gkBindPhoneInput(el) {
        if (!el) return;
        el.addEventListener('input', function () {
            var digits = el.value.replace(/\D/g, '').slice(0, 11);
            if (digits.length && !digits.startsWith('09')) {
                if (digits.startsWith('9')) {
                    digits = '0' + digits;
                } else if (digits.startsWith('0')) {
                    digits = ('09' + digits.slice(1)).slice(0, 11);
                } else {
                    digits = ('09' + digits).slice(0, 11);
                }
            }
            el.value = digits;
        });
    }

    function gkBindWholeNumberInput(el) {
        if (!el) return;
        el.addEventListener('input', function () {
            el.value = el.value.replace(/\D/g, '');
        });
    }

    /* ── Register form validation ── */
    function validateGkRegisterForm(form) {
        ['last_name', 'first_name', 'middle_name'].forEach(function (field) {
            if (form[field]) {
                form[field].value = form[field].value.trim().toUpperCase();
            }
        });
        var last  = (form.last_name.value  || '').trim();
        var first = (form.first_name.value || '').trim();
        if (!last || !first) {
            return 'Last name and first name are required.';
        }
        var nameRe = /^[A-Z\s'\-\.]+$/;
        if (!nameRe.test(last))  return 'Last name must contain letters only.';
        if (!nameRe.test(first)) return 'First name must contain letters only.';
        var middle = (form.middle_name.value || '').trim();
        if (middle && !nameRe.test(middle)) return 'Middle name must contain letters only.';

        var phone = (form.phone.value || '').trim();
        if (phone && !/^09\d{9}$/.test(phone)) {
            return 'Phone must be exactly 11 digits starting with 09 (e.g. 09171234567).';
        }

        var block = (form.block.value || '').trim();
        var lot   = (form.lot.value   || '').trim();
        if (!/^[1-9]\d*$/.test(block)) return 'Block must be a whole number (e.g. 1).';
        if (!/^[1-9]\d*$/.test(lot))   return 'Lot must be a whole number (e.g. 3).';

        var year = (form.beneficiary_year.value || '').trim();
        if (!/^\d{4}$/.test(year)) {
            return 'Beneficiary year must be a 4-digit whole number (e.g. 2019).';
        }
        return '';
    }

    /* ── Init field masks on register modal ── */
    (function initGkRegisterFieldMasks() {
        gkBindUpperNameInput(document.getElementById('gkRegLast'));
        gkBindUpperNameInput(document.getElementById('gkRegFirst'));
        gkBindUpperNameInput(document.getElementById('gkRegMiddle'));
        gkBindPhoneInput(document.getElementById('gkRegPhone'));
        ['gkRegBlock', 'gkRegLot', 'gkRegYear'].forEach(function (id) {
            gkBindWholeNumberInput(document.getElementById(id));
        });
    })();

    /* ── CSV file name display ── */
    var csvFileInput = document.getElementById('gkCsvFile');
    if (csvFileInput) {
        csvFileInput.addEventListener('change', function () {
            var file   = this.files[0];
            var nameEl = document.getElementById('gkCsvFileName');
            if (!nameEl) return;
            if (file) {
                nameEl.textContent        = file.name;
                nameEl.style.color        = '#166534';
                nameEl.style.background   = '#dcfce7';
            } else {
                nameEl.textContent        = 'No file selected';
                nameEl.style.color        = '#64748b';
                nameEl.style.background   = '#f1f5f9';
            }
        });
    }

    /* ── Import form submit ── */
    var importForm = document.getElementById('gkImportForm');
    if (importForm) {
        importForm.addEventListener('submit', async function (e) {
            e.preventDefault();
            var errEl = document.getElementById('gkImportError');
            var btn   = document.getElementById('gkImportSubmit');
            errEl.style.display = 'none';
            btn.disabled = true;
            try {
                var fd  = new FormData(this);
                var res = await fetch(IMPORT_URL, {
                    method:  'POST',
                    headers: { 'X-CSRFToken': getGkCsrf() },
                    body:    fd,
                });
                var data = await res.json();
                if (data.success) {
                    var msg = data.message || 'Import complete.';
                    if (data.errors && data.errors.length) {
                        msg += '\n\n' + data.errors.map(function (x) {
                            return 'Line ' + x.line + ': ' + x.message;
                        }).join('\n');
                    }
                    alert(msg);
                    window.location.reload();
                } else {
                    errEl.textContent   = data.error || 'Import failed.';
                    errEl.style.display = 'block';
                }
            } catch (ex) {
                errEl.textContent   = ex.message || 'Network error.';
                errEl.style.display = 'block';
            } finally {
                btn.disabled = false;
            }
        });
    }

    /* ── Register form submit ── */
    var registerForm = document.getElementById('gkRegisterForm');
    if (registerForm) {
        registerForm.addEventListener('submit', async function (e) {
            e.preventDefault();
            var errEl           = document.getElementById('gkRegisterError');
            var btn             = document.getElementById('gkRegisterSubmit');
            errEl.style.display = 'none';
            var validationError = validateGkRegisterForm(this);
            if (validationError) {
                errEl.textContent   = validationError;
                errEl.style.display = 'block';
                return;
            }
            btn.disabled = true;
            try {
                var body = new URLSearchParams(new FormData(this));
                var res  = await fetch(REGISTER_URL, {
                    method:  'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                        'X-CSRFToken':  getGkCsrf(),
                    },
                    body: body.toString(),
                });
                var data = await res.json();
                if (data.success) {
                    if (typeof showFlowAlert === 'function') {
                        showFlowAlert(data.message || 'Registered.', 'Success', function () {
                            window.location.reload();
                        }, 'success');
                    } else {
                        alert(data.message || 'Registered.');
                        window.location.reload();
                    }
                } else {
                    errEl.textContent   = data.error || 'Could not register.';
                    errEl.style.display = 'block';
                }
            } catch (ex) {
                errEl.textContent   = ex.message || 'Network error.';
                errEl.style.display = 'block';
            } finally {
                btn.disabled = false;
            }
        });
    }

}());
