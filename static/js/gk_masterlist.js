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
        var w = wrap.getBoundingClientRect().width || wrap.offsetWidth;
        slides.forEach(function (s) { s.style.width = w + 'px'; });
    }

    function slideWidth() {
        return wrap.getBoundingClientRect().width || wrap.offsetWidth;
    }

    function goTo(idx) {
        current = Math.max(0, Math.min(idx, total - 1));
        track.style.transform = 'translateX(-' + (current * slideWidth()) + 'px)';
        dots.forEach(function (d, i) { d.classList.toggle('is-active', i === current); });
        if (counter) counter.textContent = (current + 1) + ' / ' + total;
        if (prevBtn) prevBtn.disabled = current === 0;
        if (nextBtn) nextBtn.disabled = current === total - 1;
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

    /* Resize: re-size slides and re-apply translate */
    window.addEventListener('resize', function () {
        sizeSlides();
        goTo(current);
    });

    /* Init — defer until browser has finished layout so offsetWidth is non-zero */
    requestAnimationFrame(function () {
        requestAnimationFrame(function () {
            sizeSlides();
            goTo(0);
        });
    });
}());
