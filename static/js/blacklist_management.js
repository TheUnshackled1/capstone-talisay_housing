// -- Modal Functions ----------------------------------------------------------

function openDetailsModal(btn) {
    document.getElementById('mName').textContent = btn.dataset.name.toUpperCase();
    document.getElementById('mRef').textContent = btn.dataset.ref;
    document.getElementById('mDob').textContent = btn.dataset.dob;
    document.getElementById('mBrgy').textContent = btn.dataset.brgy;
    document.getElementById('mReason').textContent = btn.dataset.reason;
    document.getElementById('mDetails').textContent = btn.dataset.details;
    document.getElementById('mNotes').textContent = btn.dataset.notes || String.fromCodePoint(0x2014);
    document.getElementById('mDate').textContent = btn.dataset.date;
    document.getElementById('blDetailsModal').classList.add('active');
}

function closeDetailsModal(event) {
    if (event && event.target && event.target.id !== 'blDetailsModal') return;
    document.getElementById('blDetailsModal').classList.remove('active');
}

// Escape key closes modal
document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
        closeDetailsModal();
    }
});

// -- DOMContentLoaded ---------------------------------------------------------

document.addEventListener('DOMContentLoaded', () => {

    // Attach click listeners to all Review buttons
    document.querySelectorAll('.btn-blacklist-review').forEach(btn => {
        btn.addEventListener('click', function () {
            openDetailsModal(this);
        });
    });

    // -- Premium Hover Card popover -------------------------------------------

    const hoverCard = document.getElementById('applicantHoverCard');
    const hcAvatar  = document.getElementById('hcAvatar');
    const hcName    = document.getElementById('hcName');
    const hcTx      = document.getElementById('hcTx');
    const hcRef     = document.getElementById('hcRef');
    const hcRefRow  = document.getElementById('hcRefRow');
    const hcBrgy    = document.getElementById('hcBrgy');
    const hcDob     = document.getElementById('hcDob');

    if (!hoverCard) return; // guard: hover card template must be present

    let hideTimeout;

    document.addEventListener('mouseover', function (e) {
        const nameSpan    = e.target.closest('.complainant-name.applicant-name');
        const isHoverCard = e.target.closest('#applicantHoverCard');

        if (!nameSpan) {
            if (isHoverCard) clearTimeout(hideTimeout);
            return;
        }

        clearTimeout(hideTimeout);

        const fullName = nameSpan.dataset.fullName || nameSpan.textContent.trim();
        const txId     = nameSpan.dataset.txId     || '';
        const refCode  = nameSpan.dataset.refCode  || '';
        const barangay = nameSpan.dataset.barangay || 'Not specified';
        const dob      = nameSpan.dataset.dob      || 'Not specified';

        // Populate card
        hcName.textContent   = fullName;
        hcAvatar.textContent = fullName.slice(0, 2).toUpperCase();

        // Truncate transaction ID safely
        let displayTx = txId;
        if (displayTx.startsWith('APP-')) {
            const clean = displayTx.substring(4).replace(/[^a-fA-F0-9\-]/g, '').replace(/-/g, '');
            displayTx = 'APP-' + clean.slice(0, 8) + '...';
        } else if (displayTx.startsWith('TX-')) {
            const clean = displayTx.substring(3).replace(/[^a-fA-F0-9\-]/g, '').replace(/-/g, '');
            displayTx = 'TX-' + clean.slice(0, 8) + '...';
        } else if (displayTx.length > 15) {
            displayTx = displayTx.slice(0, 12) + '...';
        }
        hcTx.textContent = displayTx;

        if (refCode) {
            hcRef.textContent      = refCode;
            hcRefRow.style.display = 'flex';
        } else {
            hcRefRow.style.display = 'none';
        }
        hcBrgy.textContent = barangay;
        hcDob.textContent  = dob;

        // Position card above the name span, centered
        const rect = nameSpan.getBoundingClientRect();
        hoverCard.style.display = 'block';
        const cardWidth  = hoverCard.offsetWidth  || 290;
        const cardHeight = hoverCard.offsetHeight || 190;
        hoverCard.style.display = ''; // reset to CSS state

        const scrollX = window.pageXOffset || document.documentElement.scrollLeft;
        const scrollY = window.pageYOffset || document.documentElement.scrollTop;

        let targetLeft = rect.left + scrollX + (rect.width / 2) - (cardWidth / 2);
        let targetTop  = rect.top  + scrollY - cardHeight - 12;

        if (targetLeft < 10) targetLeft = 10;
        if (targetLeft + cardWidth > window.innerWidth - 10) {
            targetLeft = window.innerWidth - cardWidth - 10;
        }

        if (rect.top - cardHeight - 12 < 10) {
            targetTop = rect.bottom + scrollY + 12;
            hoverCard.classList.add('position-below');
        } else {
            hoverCard.classList.remove('position-below');
        }

        hoverCard.style.left = targetLeft + 'px';
        hoverCard.style.top  = targetTop  + 'px';
        hoverCard.classList.add('active');
    });

    document.addEventListener('mouseout', function (e) {
        const nameSpan    = e.target.closest('.complainant-name.applicant-name');
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
