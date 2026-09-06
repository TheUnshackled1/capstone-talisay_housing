/**
 * IHSMS — Integrated Housing Services and Monitoring System
 * Staff Dashboard JavaScript
 */

document.addEventListener('DOMContentLoaded', function () {
    // Initialize all components
    initSidebar();
    initSidebarCollapse();
    initSidebarDropdowns();
    initCurrentDate();
    initAlerts();
    initTooltips();
    initScrollAnimations();
});

function initSidebarCollapse() {
    var sidebar = document.getElementById('sidebar');
    var toggleBtn = document.getElementById('sidebarToggleBtn');
    var mainContent = document.querySelector('.main-content');
    if (!sidebar || !toggleBtn) return;

    var KEY = 'ihsms_sidebar_collapsed';

    function setCollapsed(collapsed) {
        if (collapsed) {
            sidebar.classList.add('collapsed');
            toggleBtn.classList.add('is-collapsed');
            if (mainContent) mainContent.classList.add('sidebar-collapsed');
            // Force any open <details> dropdowns closed
            sidebar.querySelectorAll('details[open]').forEach(function (d) {
                d.removeAttribute('open');
            });
        } else {
            sidebar.classList.remove('collapsed');
            toggleBtn.classList.remove('is-collapsed');
            if (mainContent) mainContent.classList.remove('sidebar-collapsed');
        }
        try { localStorage.setItem(KEY, collapsed ? '1' : '0'); } catch (e) { }
    }

    // Restore saved preference
    try {
        if (localStorage.getItem(KEY) === '1') setCollapsed(true);
    } catch (e) { }

    toggleBtn.addEventListener('click', function () {
        setCollapsed(!sidebar.classList.contains('collapsed'));
    });
}


/**
 * Sidebar Toggle for Mobile
 */
function initSidebar() {
    const mobileMenuBtn = document.getElementById('mobileMenuBtn');
    const sidebar = document.getElementById('sidebar');
    const sidebarOverlay = document.getElementById('sidebarOverlay');

    function closeSidebar() {
        if (!sidebar) return;
        sidebar.classList.remove('open');
        if (sidebarOverlay) sidebarOverlay.classList.remove('open');
        document.body.classList.remove('sidebar-locked');
        if (mobileMenuBtn) mobileMenuBtn.setAttribute('aria-expanded', 'false');
    }

    function openSidebar() {
        if (!sidebar) return;
        sidebar.classList.add('open');
        if (sidebarOverlay) sidebarOverlay.classList.add('open');
        document.body.classList.add('sidebar-locked');
        if (mobileMenuBtn) mobileMenuBtn.setAttribute('aria-expanded', 'true');
    }

    if (mobileMenuBtn && sidebar) {
        mobileMenuBtn.addEventListener('click', function () {
            if (sidebar.classList.contains('open')) {
                closeSidebar();
            } else {
                openSidebar();
            }
        });
    }

    if (sidebarOverlay) {
        sidebarOverlay.addEventListener('click', closeSidebar);
    }

    // Auto-close drawer when nav-link clicked on mobile
    if (sidebar) {
        sidebar.querySelectorAll('.nav-link, .logout-btn').forEach(function (link) {
            link.addEventListener('click', function () {
                if (window.innerWidth < 1024) closeSidebar();
            });
        });
    }

    // Close sidebar on escape key
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && sidebar && sidebar.classList.contains('open')) {
            closeSidebar();
            if (mobileMenuBtn) mobileMenuBtn.focus();
        }
    });

    // Handle window resize — auto-close + clear body lock above breakpoint
    let resizeTimer;
    window.addEventListener('resize', function () {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(function () {
            if (window.innerWidth >= 1024) closeSidebar();
        }, 100);
    });
}

/**
 * Display Current Date
 */
function initCurrentDate() {
    const options = {
        weekday: 'long',
        year: 'numeric',
        month: 'long',
        day: 'numeric'
    };
    const dateStr = new Date().toLocaleDateString('en-US', options);

    // Topbar date (hidden, kept for compatibility)
    const dateEl = document.getElementById('currentDate');
    if (dateEl) {
        dateEl.textContent = dateStr;
    }

    // Date badge (new format: "Tue, Apr 21, 2026")
    const badgeEl = document.getElementById('currentDateBadge');
    if (badgeEl) {
        const shortOptions = {
            weekday: 'short',
            month: 'short',
            day: 'numeric',
            year: 'numeric'
        };
        const shortDate = new Date().toLocaleDateString('en-US', shortOptions);
        badgeEl.innerHTML = `<svg style="width: 16px; height: 16px;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg> ${shortDate}`;
    }

    // Welcome banner date
    const welcomeDateEl = document.getElementById('welcomeDate');
    if (welcomeDateEl) {
        welcomeDateEl.textContent = dateStr;
    }
}

/**
 * Auto-dismiss Alerts
 */
function initAlerts() {
    const alerts = document.querySelectorAll('.alert[data-auto-dismiss]');
    alerts.forEach(function (alert) {
        const duration = parseInt(alert.dataset.autoDismiss) || 5000;
        setTimeout(function () {
            dismissAlert(alert);
        }, duration);
    });

    // Add click to dismiss
    const dismissButtons = document.querySelectorAll('.alert-dismiss');
    dismissButtons.forEach(function (btn) {
        btn.addEventListener('click', function () {
            const alert = btn.closest('.alert');
            if (alert) {
                dismissAlert(alert);
            }
        });
    });
}

function dismissAlert(alert) {
    alert.style.opacity = '0';
    alert.style.transform = 'translateY(-10px)';
    setTimeout(function () {
        alert.remove();
    }, 300);
}

/**
 * Initialize Tooltips
 */
function initTooltips() {
    const tooltipTriggers = document.querySelectorAll('[data-tooltip]');
    tooltipTriggers.forEach(function (trigger) {
        trigger.addEventListener('mouseenter', showTooltip);
        trigger.addEventListener('mouseleave', hideTooltip);
        trigger.addEventListener('focus', showTooltip);
        trigger.addEventListener('blur', hideTooltip);
    });
}

function showTooltip(e) {
    const trigger = e.currentTarget;
    const text = trigger.dataset.tooltip;
    if (!text) return;

    const tooltip = document.createElement('div');
    tooltip.className = 'tooltip';
    tooltip.textContent = text;
    tooltip.style.cssText = `
        position: absolute;
        background: #1f2937;
        color: white;
        padding: 0.375rem 0.625rem;
        border-radius: 6px;
        font-size: 0.75rem;
        white-space: nowrap;
        z-index: 1000;
        pointer-events: none;
        opacity: 0;
        transition: opacity 0.15s ease;
    `;

    document.body.appendChild(tooltip);

    const triggerRect = trigger.getBoundingClientRect();
    const tooltipRect = tooltip.getBoundingClientRect();

    tooltip.style.left = `${triggerRect.left + (triggerRect.width / 2) - (tooltipRect.width / 2)}px`;
    tooltip.style.top = `${triggerRect.top - tooltipRect.height - 8 + window.scrollY}px`;

    // Force reflow
    tooltip.offsetHeight;
    tooltip.style.opacity = '1';

    trigger._tooltip = tooltip;
}

function hideTooltip(e) {
    const trigger = e.currentTarget;
    if (trigger._tooltip) {
        trigger._tooltip.style.opacity = '0';
        setTimeout(function () {
            if (trigger._tooltip && trigger._tooltip.parentNode) {
                trigger._tooltip.parentNode.removeChild(trigger._tooltip);
            }
            delete trigger._tooltip;
        }, 150);
    }
}

/**
 * Format Numbers with Commas
 */
function formatNumber(num) {
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

/**
 * Animate Counter
 */
function animateCounter(element, target, duration = 1000) {
    const start = 0;
    const startTime = performance.now();

    function update(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const easeOut = 1 - Math.pow(1 - progress, 3);
        const current = Math.floor(start + (target - start) * easeOut);

        element.textContent = formatNumber(current);

        if (progress < 1) {
            requestAnimationFrame(update);
        } else {
            element.textContent = formatNumber(target);
        }
    }

    requestAnimationFrame(update);
}

/**
 * Debounce Function
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = function () {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

/**
 * Format Date/Time
 */
function formatDateTime(date, format = 'full') {
    const d = new Date(date);
    const options = {
        full: { year: 'numeric', month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit' },
        date: { year: 'numeric', month: 'long', day: 'numeric' },
        short: { month: 'short', day: 'numeric', year: 'numeric' },
        time: { hour: '2-digit', minute: '2-digit' }
    };
    return d.toLocaleDateString('en-US', options[format] || options.full);
}

/**
 * Copy to Clipboard
 */
async function copyToClipboard(text, successMessage = 'Copied!') {
    try {
        await navigator.clipboard.writeText(text);
        showNotification(successMessage, 'success');
        return true;
    } catch (err) {
        showNotification('Failed to copy', 'error');
        return false;
    }
}

/**
 * Show Notification Toast
 */
function showNotification(message, type = 'info', duration = 3000) {
    const container = document.getElementById('notificationContainer') || createNotificationContainer();

    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <span>${message}</span>
        <button class="notification-close">&times;</button>
    `;
    notification.style.cssText = `
        display: flex;
        align-items: center;
        gap: 0.75rem;
        padding: 0.875rem 1rem;
        background: white;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        margin-bottom: 0.5rem;
        animation: slideInRight 0.3s ease;
        font-size: 0.875rem;
    `;

    const colors = {
        success: '#16a34a',
        error: '#dc2626',
        warning: '#d97706',
        info: '#2563eb'
    };
    notification.style.borderLeft = `4px solid ${colors[type] || colors.info}`;

    container.appendChild(notification);

    const closeBtn = notification.querySelector('.notification-close');
    closeBtn.style.cssText = `
        background: none;
        border: none;
        font-size: 1.25rem;
        color: #9ca3af;
        cursor: pointer;
        padding: 0 0.25rem;
    `;
    closeBtn.addEventListener('click', function () {
        removeNotification(notification);
    });

    if (duration > 0) {
        setTimeout(function () {
            removeNotification(notification);
        }, duration);
    }
}

function createNotificationContainer() {
    const container = document.createElement('div');
    container.id = 'notificationContainer';
    container.style.cssText = `
        position: fixed;
        top: 1rem;
        right: 1rem;
        z-index: 9999;
        max-width: 360px;
    `;
    document.body.appendChild(container);
    return container;
}

function removeNotification(notification) {
    notification.style.opacity = '0';
    notification.style.transform = 'translateX(100%)';
    notification.style.transition = 'all 0.3s ease';
    setTimeout(function () {
        notification.remove();
    }, 300);
}

// Add CSS animation for notifications
const style = document.createElement('style');
style.textContent = `
    @keyframes slideInRight {
        from {
            opacity: 0;
            transform: translateX(100%);
        }
        to {
            opacity: 1;
            transform: translateX(0);
        }
    }
`;
document.head.appendChild(style);

/**
 * Confirmation Dialog
 */
function confirmAction(message, onConfirm, onCancel) {
    const overlay = document.createElement('div');
    overlay.style.cssText = `
        position: fixed;
        inset: 0;
        background: rgba(0, 0, 0, 0.5);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 9999;
        animation: fadeIn 0.2s ease;
    `;

    const dialog = document.createElement('div');
    dialog.style.cssText = `
        background: white;
        border-radius: 12px;
        padding: 1.5rem;
        max-width: 400px;
        width: 90%;
        box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
        animation: slideUp 0.3s ease;
    `;
    dialog.innerHTML = `
        <h3 style="margin-bottom: 0.75rem; font-size: 1.1rem; color: #1f2937;">Confirm Action</h3>
        <p style="margin-bottom: 1.5rem; color: #6b7280; font-size: 0.9rem;">${message}</p>
        <div style="display: flex; gap: 0.75rem; justify-content: flex-end;">
            <button class="dialog-cancel" style="padding: 0.5rem 1rem; background: #f3f4f6; border: 1px solid #d1d5db; border-radius: 6px; cursor: pointer; font-size: 0.875rem;">Cancel</button>
            <button class="dialog-confirm" style="padding: 0.5rem 1rem; background: #dc2626; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 0.875rem;">Confirm</button>
        </div>
    `;

    overlay.appendChild(dialog);
    document.body.appendChild(overlay);

    const cancelBtn = dialog.querySelector('.dialog-cancel');
    const confirmBtn = dialog.querySelector('.dialog-confirm');

    cancelBtn.addEventListener('click', function () {
        overlay.remove();
        if (onCancel) onCancel();
    });

    confirmBtn.addEventListener('click', function () {
        overlay.remove();
        if (onConfirm) onConfirm();
    });

    overlay.addEventListener('click', function (e) {
        if (e.target === overlay) {
            overlay.remove();
            if (onCancel) onCancel();
        }
    });
}

// Add CSS for dialog animations
const dialogStyle = document.createElement('style');
dialogStyle.textContent = `
    @keyframes fadeIn {
        from { opacity: 0; }
        to { opacity: 1; }
    }
    @keyframes slideUp {
        from { opacity: 0; transform: translateY(20px); }
        to { opacity: 1; transform: translateY(0); }
    }
`;
document.head.appendChild(dialogStyle);

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
        ).forEach(function (el) {
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

    const scrollObserver = new IntersectionObserver(function (entries, observer) {
        entries.forEach(function (entry) {
            if (entry.isIntersecting) {
                entry.target.classList.add('animate-in');
                // Once animated, stop observing (one-time animation)
                observer.unobserve(entry.target);
            }
        });
    }, observerOptions);

    // Observe each element
    animatedElements.forEach(function (element) {
        scrollObserver.observe(element);
    });
}

/**
 * Initialize Sidebar Dropdown menus (auto-opens if active item is inside)
 */
function initSidebarDropdowns() {
    var sidebar = document.getElementById('sidebar');

    document.querySelectorAll('.sidebar-dropdown').forEach(function (dropdown) {
        var summary = dropdown.querySelector('summary');
        var content = dropdown.querySelector('.sidebar-dropdown-content');

        // Auto-open on load if active item is inside
        if (dropdown.querySelector('.nav-link.active') || dropdown.querySelector('.nav-link[class*="active"]')) {
            dropdown.setAttribute('open', '');
            dropdown.classList.add('active');
            dropdown.classList.add('open-animated');
            // Set height so animation starts correctly
            if (content) {
                content.style.maxHeight = content.scrollHeight + 'px';
                content.style.opacity = '1';
            }
        }

        if (!summary || !content) return;

        summary.addEventListener('click', function (e) {
            e.preventDefault();

            // If sidebar is collapsed, expand it first, then open dropdown
            if (sidebar && sidebar.classList.contains('collapsed')) {
                var toggleBtn = document.getElementById('sidebarToggleBtn');
                sidebar.classList.remove('collapsed');
                if (toggleBtn) toggleBtn.classList.remove('is-collapsed');
                var mainContent = document.querySelector('.main-content');
                if (mainContent) mainContent.classList.remove('sidebar-collapsed');
                try { localStorage.setItem('ihsms_sidebar_collapsed', '0'); } catch (ex) {}

                // Open the dropdown after sidebar expands
                setTimeout(function () {
                    openDropdown(dropdown, content);
                }, 310);
                return;
            }

            if (dropdown.hasAttribute('open')) {
                closeDropdown(dropdown, content);
            } else {
                openDropdown(dropdown, content);
            }
        });
    });

    function openDropdown(dropdown, content) {
        dropdown.setAttribute('open', '');
        dropdown.classList.add('open-animated');

        content.style.maxHeight = '0px';
        content.style.opacity = '0';
        content.style.transform = 'translateY(-10px) scaleY(0.95)';
        content.style.transformOrigin = 'top';
        content.style.overflow = 'hidden';

        // Force reflow
        content.offsetHeight;

        content.style.transition = 'all 0.25s cubic-bezier(0.16, 1, 0.3, 1)';
        content.style.maxHeight = content.scrollHeight + 'px';
        content.style.opacity = '1';
        content.style.transform = 'translateY(0) scaleY(1)';

        // After animation: keep maxHeight open, clear transition
        setTimeout(function () {
            content.style.transition = '';
            content.style.transform = '';
            // Keep maxHeight so it stays open
        }, 260);
    }

    function closeDropdown(dropdown, content) {
        // Snapshot current height for animation start
        content.style.maxHeight = content.scrollHeight + 'px';
        content.style.opacity = '1';
        content.style.transform = 'translateY(0) scaleY(1)';
        content.style.overflow = 'hidden';

        // Force reflow
        content.offsetHeight;

        content.style.transition = 'all 0.22s cubic-bezier(0.4, 0, 0.2, 1)';
        content.style.maxHeight = '0px';
        content.style.opacity = '0';
        content.style.transform = 'translateY(-10px) scaleY(0.95)';

        dropdown.classList.remove('open-animated');

        setTimeout(function () {
            dropdown.removeAttribute('open');
            // Clear all inline styles after close is done
            content.removeAttribute('style');
        }, 230);
    }
}





/* ==========================================
   Merged from dashboard_page.js
   ========================================== */

/* ============================================================
   dashboard_page.js
   Chart rendering and dashboard interactivity for the main
   IHSMS dashboard. Extracted from dashboard.html inline script.

   Django data is passed via data-* attributes on <body>:
     data-blacklist-count  → blacklist_count context variable
   ============================================================ */

// ── Time-of-day greeting ────────────────────────────────────
(function () {
    var el = document.getElementById('welcomeGreeting');
    if (!el) return;
    var h = new Date().getHours();
    el.textContent = h < 12 ? 'Good morning,' : h < 17 ? 'Good afternoon,' : 'Good evening,';
})();

// ── Number Counter Animation ────────────────────────────────────
document.addEventListener('DOMContentLoaded', function () {
    var statValues = document.querySelectorAll('.stat-value');
    statValues.forEach(function (el) {
        var targetStr = el.textContent.trim().replace(/,/g, '');
        var target = parseInt(targetStr, 10);
        if (isNaN(target)) return;

        var startTimestamp = null;
        var duration = 2000; // 1.2s animation

        var step = function (timestamp) {
            if (!startTimestamp) startTimestamp = timestamp;
            var progress = Math.min((timestamp - startTimestamp) / duration, 1);
            // Ease out cubic
            var easeProgress = 1 - Math.pow(1 - progress, 3);
            var current = Math.floor(easeProgress * target);

            el.textContent = current.toLocaleString();

            if (progress < 1) {
                window.requestAnimationFrame(step);
            } else {
                el.textContent = target.toLocaleString();
            }
        };

        window.requestAnimationFrame(step);
    });
});

// ── Analytics Charts ────────────────────────────────────────
document.addEventListener('DOMContentLoaded', function () {
    var el = document.getElementById('tha-analytics-charts');
    if (!el || typeof Chart === 'undefined') return;
    var D;
    try { D = JSON.parse(el.textContent); } catch (e) { return; }
    if (!D) return;

    // Read Django context values passed via data-* on <body>
    var bodyEl = document.body;
    var blacklistCount = parseInt(bodyEl.getAttribute('data-blacklist-count') || '0', 10);

    var PALETTE = [
        '#2F6FD6', // Blue
        '#D4AF37', // Gold
        '#14B8A6', // Teal
        '#22C55E', // Green
        '#64748B', // Slate
        '#8B5CF6', '#F43F5E', '#0EA5E9', '#F59E0B', '#10B981'
    ];

    function hexToRgba(hex, alpha) {
        hex = hex.replace('#', '');
        var r = parseInt(hex.substring(0, 2), 16);
        var g = parseInt(hex.substring(2, 4), 16);
        var b = parseInt(hex.substring(4, 6), 16);
        return 'rgba(' + r + ',' + g + ',' + b + ',' + alpha + ')';
    }

    function sum(arr) {
        return arr.reduce(function (s, n) { return s + (Number(n) || 0); }, 0);
    }

    function getSingleSeriesDataset(key) {
        var spec = D[key];
        if (!spec || !spec.labels || !spec.values || !spec.labels.length) return null;
        return {
            type: 'single',
            labels: spec.labels.map(function (l) {
                var s = String(l);
                var acronyms = ['CDRRMO', 'ISF', 'COMELEC', 'GK', 'ID', 'PHP', 'SMS', 'M2', 'M1', 'M4'];
                if (acronyms.indexOf(s.toUpperCase()) >= 0) return s.toUpperCase();
                if (s === s.toUpperCase() && s.length > 1) {
                    s = s.replace(/\w\S*/g, function (w) {
                        return w.charAt(0).toUpperCase() + w.slice(1).toLowerCase();
                    });
                }
                return s;
            }),
            values: spec.values.map(function (v) { return Number(v) || 0; })
        };
    }

    function getStandardizedDataset(canvasId) {
        switch (canvasId) {
            case 'chartTrend':
                if (!D.trend || !D.trend.labels) return null;
                return {
                    type: 'multi',
                    labels: D.trend.labels,
                    datasets: [
                        { label: 'New applicants', values: D.trend.registrations || [], color: '#2F6FD6', fillOpacity: 0.12 },
                        { label: 'Vault uploads', values: D.trend.vaultUploads || [], color: '#14B8A6', fillOpacity: 0.14 }
                    ]
                };
            case 'chartApplicants': return getSingleSeriesDataset('applicantsByStatus');
            case 'chartChannels': return getSingleSeriesDataset('channels');
            case 'chartBarangays': return getSingleSeriesDataset('topBarangays');
            case 'chartApplications': return getSingleSeriesDataset('applicationsByStatus');
            case 'chartHousing': return getSingleSeriesDataset('housingByStatus');
            case 'chartISFPopulation': return getSingleSeriesDataset('isfPopulation');
            case 'chartISFOverall': return getSingleSeriesDataset('isfOverall');
            case 'chartBlacklist': return getSingleSeriesDataset('blacklistByReason');
            case 'chartConstruction': return getSingleSeriesDataset('constructionProgress');
            case 'chartQueue': return getSingleSeriesDataset('activeQueues');
            case 'chartFunnel': return getSingleSeriesDataset('workflowFunnel');
            case 'chartCaseAging': return getSingleSeriesDataset('caseAging');
            case 'chartRequirements': return getSingleSeriesDataset('requirementsByStatus');
            case 'chartCasesStatus': return getSingleSeriesDataset('casesByStatus');
            case 'chartCasesType': return getSingleSeriesDataset('casesByType');
            case 'chartVoterRegistration':
                return {
                    type: 'single',
                    labels: ['Registered Voter', 'Not Registered'],
                    values: [
                        (D.voterRegistration && D.voterRegistration.values) ? (D.voterRegistration.values[0] || 0) : 0,
                        (D.voterRegistration && D.voterRegistration.values) ? (D.voterRegistration.values[1] || 0) : 0,
                    ],
                    colors: ['#22C55E', '#F43F5E']
                };
            default: return null;
        }
    }

    function getDefaultMode(canvasId) {
        switch (canvasId) {
            case 'chartTrend': return 'line';
            case 'chartApplicants':
            case 'chartChannels':
            case 'chartApplications':
            case 'chartHousing':
            case 'chartISFPopulation':
            case 'chartISFOverall':
            case 'chartBlacklist':
            case 'chartRequirements':
            case 'chartCasesStatus':
            case 'chartCasesType':
            case 'chartVoterRegistration':
                return 'donut';
            case 'chartBarangays':
            case 'chartFunnel':
            case 'chartCaseAging':
                return 'bar';
            default: return 'bar';
        }
    }

    var chartInstances = {};

    function switchChartMode(canvasId, mode) {
        var canvas = document.getElementById(canvasId);
        if (!canvas) return;
        var card = canvas.closest('.rep-card');
        if (!card) return;

        card.querySelectorAll('.rep-switch-btn').forEach(function (btn) {
            if (btn.getAttribute('data-mode') === mode) {
                btn.classList.add('is-active');
            } else {
                btn.classList.remove('is-active');
            }
        });

        if (chartInstances[canvasId]) {
            chartInstances[canvasId].destroy();
            chartInstances[canvasId] = null;
        }

        var canvasWrap = canvas.parentNode;
        var htmlContainer = card.querySelector('.rep-dynamic-container');
        var dataset = getStandardizedDataset(canvasId);

        if (!dataset) return;

        var htmlModes = [];
        if (htmlModes.indexOf(mode) >= 0) {
            canvasWrap.style.display = 'none';
            htmlContainer.style.display = '';
            renderHtmlFallback(htmlContainer, dataset, mode, canvasId);
        } else {
            htmlContainer.style.display = 'none';
            canvasWrap.style.display = '';
            canvas.style.display = '';
            renderChartJS(canvas, dataset, mode, canvasId);
        }
    }

    function renderChartJS(canvas, dataset, mode, canvasId) {
        var config = {
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'right',
                        align: 'center',
                        maxWidth: 140, // Force legend to roughly 35% of typical card width
                        labels: {
                            boxWidth: 10,
                            boxHeight: 10,
                            padding: 10,
                            font: { size: 12, family: 'Inter, sans-serif' },
                            usePointStyle: true
                        }
                    },
                    tooltip: {
                        backgroundColor: '#0f172a',
                        padding: 10,
                        cornerRadius: 6
                    }
                }
            }
        };

        if (canvasId === 'chartTrend') {
            config.options.maintainAspectRatio = false;
            config.options.interaction = { mode: 'index', intersect: false };
        }

        if (dataset.type === 'single') {
            var total = sum(dataset.values);
            if (mode === 'line' || mode === 'area') {
                config.type = 'line';
                config.data = {
                    labels: dataset.labels,
                    datasets: [{
                        label: 'Count',
                        data: dataset.values,
                        borderColor: '#2F6FD6',
                        backgroundColor: mode === 'area' ? 'rgba(47, 111, 214, 0.15)' : 'transparent',
                        tension: 0.35,
                        fill: mode === 'area',
                        pointRadius: 4,
                        pointHoverRadius: 6,
                        borderWidth: 2.5
                    }]
                };
                config.options.plugins.legend.display = false;
                config.options.scales = {
                    y: { beginAtZero: true, grid: { color: '#f1f5f9' }, ticks: { precision: 0 } },
                    x: { grid: { display: false } }
                };
            } else if (mode === 'bar') {
                var isHorizontal = ['chartBarangays', 'chartFunnel'].indexOf(canvasId) >= 0;
                config.type = 'bar';
                config.data = {
                    labels: dataset.labels,
                    datasets: [{
                        label: 'Count',
                        data: dataset.values,
                        backgroundColor: isHorizontal ? '#14B8A6' : dataset.labels.map(function (_, i) { return PALETTE[i % PALETTE.length]; }),
                        borderRadius: 4,
                        barThickness: dataset.labels.length > 8 ? 'flex' : 18
                    }]
                };
                config.options.indexAxis = isHorizontal ? 'y' : 'x';
                config.options.plugins.legend.display = false;
                config.options.scales = isHorizontal ? {
                    x: { beginAtZero: true, grid: { color: '#f1f5f9' }, ticks: { precision: 0 } },
                    y: { grid: { display: false } }
                } : {
                    y: { beginAtZero: true, grid: { color: '#f1f5f9' }, ticks: { precision: 0 } },
                    x: { grid: { display: false }, ticks: { font: { size: 9 }, maxRotation: 45 } }
                };
            } else if (mode === 'stacked') {
                config.type = 'bar';
                var isHorizontal = ['chartBarangays', 'chartFunnel'].indexOf(canvasId) >= 0;
                config.data = {
                    labels: isHorizontal ? ['Total Distribution'] : dataset.labels,
                    datasets: isHorizontal ? dataset.labels.map(function (lbl, i) {
                        return { label: lbl, data: [dataset.values[i]], backgroundColor: PALETTE[i % PALETTE.length] };
                    }) : [{
                        label: 'Value',
                        data: dataset.values,
                        backgroundColor: dataset.labels.map(function (_, i) { return PALETTE[i % PALETTE.length]; }),
                        borderRadius: 4
                    }]
                };
                config.options.indexAxis = isHorizontal ? 'y' : 'x';
                config.options.plugins.legend.display = isHorizontal;
                config.options.scales = {
                    x: { stacked: true, grid: { display: false } },
                    y: { stacked: true, grid: { color: '#f1f5f9' }, ticks: { precision: 0 } }
                };
            } else if (mode === 'pie' || mode === 'donut') {
                config.type = mode === 'pie' ? 'pie' : 'doughnut';
                config.data = {
                    labels: dataset.labels,
                    datasets: [{
                        data: dataset.values,
                        backgroundColor: (dataset.colors && dataset.colors.length)
                            ? dataset.colors
                            : dataset.labels.map(function (_, i) { return PALETTE[i % PALETTE.length]; }),
                        borderWidth: 2,
                        borderColor: '#ffffff',
                        hoverOffset: 6
                    }]
                };
                if (mode === 'donut') { config.options.cutout = '62%'; }
                config.options.maintainAspectRatio = true;
                config.options.aspectRatio = 1;
                config.options.plugins.legend.display = false;
                config.options.plugins.tooltip.callbacks = {
                    footer: function (items) {
                        var i = items[0] && items[0].dataIndex;
                        if (i == null || !total) return '';
                        var pct = Math.round((dataset.values[i] / total) * 1000) / 10;
                        return pct + '% of total';
                    }
                };
            }
        } else if (dataset.type === 'multi') {
            var total1 = sum(dataset.datasets[0].values);
            var total2 = sum(dataset.datasets[1].values);

            if (mode === 'line' || mode === 'area') {
                config.type = 'line';
                config.data = {
                    labels: dataset.labels,
                    datasets: dataset.datasets.map(function (ds, idx) {
                        return {
                            label: ds.label,
                            data: ds.values,
                            borderColor: ds.color,
                            backgroundColor: mode === 'area' ? hexToRgba(ds.color, ds.fillOpacity) : 'transparent',
                            yAxisID: idx === 0 ? 'y' : 'y1',
                            tension: 0.3,
                            fill: mode === 'area',
                            pointRadius: 4,
                            pointHoverRadius: 6,
                            borderWidth: 2.5
                        };
                    })
                };
                config.options.scales = {
                    y: { type: 'linear', position: 'left', beginAtZero: true, title: { display: true, text: 'Applicants', font: { size: 10 } }, grid: { color: '#f1f5f9' }, ticks: { precision: 0 } },
                    y1: { type: 'linear', position: 'right', beginAtZero: true, title: { display: true, text: 'Uploads', font: { size: 10 } }, grid: { drawOnChartArea: false }, ticks: { precision: 0 } },
                    x: { grid: { color: '#f8fafc' } }
                };
            } else if (mode === 'bar') {
                config.type = 'bar';
                config.data = {
                    labels: dataset.labels,
                    datasets: dataset.datasets.map(function (ds) {
                        return { label: ds.label, data: ds.values, backgroundColor: ds.color, borderRadius: 4 };
                    })
                };
                config.options.scales = {
                    y: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: '#f1f5f9' } },
                    x: { grid: { display: false } }
                };
            } else if (mode === 'stacked') {
                config.type = 'bar';
                config.data = {
                    labels: dataset.labels,
                    datasets: dataset.datasets.map(function (ds) {
                        return { label: ds.label, data: ds.values, backgroundColor: ds.color };
                    })
                };
                config.options.scales = {
                    x: { stacked: true, grid: { display: false } },
                    y: { stacked: true, beginAtZero: true, ticks: { precision: 0 }, grid: { color: '#f1f5f9' } }
                };
            } else if (mode === 'pie' || mode === 'donut') {
                config.type = mode === 'pie' ? 'pie' : 'doughnut';
                config.data = {
                    labels: dataset.labels,
                    datasets: dataset.datasets.map(function (ds) {
                        return {
                            label: ds.label,
                            data: ds.values,
                            backgroundColor: dataset.labels.map(function (_, i) {
                                return hexToRgba(ds.color, 0.4 + 0.6 * (i / dataset.labels.length));
                            }),
                            borderWidth: 2,
                            borderColor: '#ffffff',
                            hoverOffset: 6
                        };
                    })
                };
                if (mode === 'donut') { config.options.cutout = '45%'; }
                config.options.maintainAspectRatio = true;
                config.options.aspectRatio = 1;
            }
        }

        Chart.defaults.font.family = "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif";
        Chart.defaults.color = '#475569';

        // Reset canvas wrap layout — canvas always takes full width, legend goes below
        var canvasWrapForLegend = canvas.parentNode;
        canvasWrapForLegend.style.display = '';
        canvasWrapForLegend.style.alignItems = '';
        canvasWrapForLegend.style.justifyContent = '';
        canvasWrapForLegend.style.overflow = '';
        canvas.style.flex = '';
        canvas.style.maxWidth = '';
        canvas.style.maxHeight = '';
        canvas.style.minWidth = '';
        canvas.style.margin = '0 auto';
        canvas.style.display = 'block';

        // Remove any stale bottom legend
        var card = canvas.closest('.rep-card');
        var staleLegend = card && card.querySelector('.chart-bottom-legend');
        if (staleLegend) staleLegend.remove();

        chartInstances[canvasId] = new Chart(canvas, config);

        if (mode === 'pie' || mode === 'donut') {
            canvasWrapForLegend.style.display = 'flex';
            canvasWrapForLegend.style.justifyContent = 'center';
            canvasWrapForLegend.style.alignItems = 'center';
            canvas.style.margin = '0 auto';
            chartInstances[canvasId].resize();
        }

        // Inject bottom legend for ALL donut/pie single-series charts
        if ((mode === 'pie' || mode === 'donut') && dataset.type === 'single' && card) {
            var sliceColors = (dataset.colors && dataset.colors.length)
                ? dataset.colors
                : dataset.labels.map(function (_, i) { return PALETTE[i % PALETTE.length]; });

            var isTwoItem = dataset.labels.length <= 2;
            var isChannels = canvasId === 'chartChannels';
            var isApplicants = canvasId === 'chartApplicants';
            var bottomLegend = document.createElement('div');
            var legendClass = 'chart-bottom-legend';
            if (isChannels) legendClass += ' chart-legend-2col';
            if (isApplicants) legendClass += ' chart-legend-applicants';
            bottomLegend.className = legendClass;

            if (isChannels) {
                bottomLegend.style.cssText = [
                    'display:grid',
                    'grid-template-columns:repeat(2, auto)',
                    'gap:0.35rem 1rem',
                    'justify-content:center',
                    'align-items:center',
                    'margin-top:0.55rem',
                    'padding:0 0.25rem'
                ].join(';') + ';';
            } else if (isApplicants) {
                bottomLegend.style.cssText = [
                    'display:grid',
                    'grid-template-columns:auto auto',
                    'grid-auto-flow:column',
                    'grid-template-rows:repeat(2, auto)',
                    'gap:0.3rem 0.65rem',
                    'justify-content:center',
                    'align-items:center',
                    'margin-top:0.55rem',
                    'padding:0 0.15rem'
                ].join(';') + ';';
            } else {
                bottomLegend.style.cssText = [
                    'display:flex',
                    isTwoItem ? 'flex-wrap:nowrap' : 'flex-wrap:wrap',
                    isTwoItem ? 'gap:0.25rem 0.45rem' : 'gap:0.35rem 0.65rem',
                    'justify-content:center', 'align-items:center',
                    'margin-top:0.55rem',
                    'padding:0 0.1rem'
                ].join(';') + ';';
            }

            dataset.labels.forEach(function (lbl, i) {
                var pill = document.createElement('span');
                var fontSize = isTwoItem ? 'font-size:0.65rem' : (isApplicants ? 'font-size:0.62rem' : 'font-size:0.68rem');
                var letterSpacing = isApplicants ? 'letter-spacing:-0.01em' : '';
                pill.style.cssText = [
                    'display:inline-flex', 'align-items:center', 'gap:0.25rem',
                    fontSize,
                    letterSpacing,
                    'color:var(--text-secondary,#64748b)',
                    'white-space:nowrap'
                ].filter(Boolean).join(';') + ';';

                var dot = document.createElement('span');
                dot.style.cssText = [
                    'width:8px', 'height:8px', 'border-radius:50%',
                    'flex-shrink:0', 'display:inline-block',
                    'background:' + sliceColors[i % sliceColors.length]
                ].join(';') + ';';

                var displayLbl = String(lbl || '');
                if (displayLbl.indexOf(' — ') !== -1) {
                    displayLbl = displayLbl.split(' — ')[0].trim();
                } else if (displayLbl.indexOf(' - ') !== -1 && /^option\s+[a-d]/i.test(displayLbl)) {
                    displayLbl = displayLbl.split(' - ')[0].trim();
                }
                var acronyms = ['CDRRMO', 'ISF', 'COMELEC', 'GK', 'ID', 'PHP', 'SMS', 'M2', 'M1', 'M4'];
                displayLbl = displayLbl.split(' ').map(function (w) {
                    var cw = w.replace(/[^a-zA-Z0-9]/g, '');
                    if (acronyms.indexOf(cw.toUpperCase()) >= 0) return w.replace(cw, cw.toUpperCase());
                    if (w === w.toUpperCase() && w.length > 1) return w.charAt(0).toUpperCase() + w.slice(1).toLowerCase();
                    if (w.length > 0) return w.charAt(0).toUpperCase() + w.slice(1);
                    return w;
                }).join(' ');

                var labelTxt = document.createElement('span');
                labelTxt.textContent = displayLbl + ':';
                labelTxt.style.cssText = 'color:#475569;';

                var countTxt = document.createElement('strong');
                countTxt.textContent = dataset.values[i] !== undefined ? dataset.values[i] : '—';
                countTxt.style.cssText = 'color:#1e293b;font-weight:700;';

                pill.appendChild(dot);
                pill.appendChild(labelTxt);
                pill.appendChild(countTxt);
                bottomLegend.appendChild(pill);
            });

            // Insert after the canvas wrapper (rep-chart-canvas div)
            canvasWrapForLegend.insertAdjacentElement('afterend', bottomLegend);
        }
    }

    function renderHtmlFallback(container, dataset, mode, canvasId) {
        container.innerHTML = '';
        var hasData = false;
        if (dataset.type === 'single') {
            hasData = dataset.values && dataset.values.length && sum(dataset.values) > 0;
        } else if (dataset.type === 'multi') {
            hasData = dataset.datasets && dataset.datasets.length &&
                (sum(dataset.datasets[0].values) > 0 || sum(dataset.datasets[1].values) > 0);
        }
        if (!hasData) {
            var emptyDiv = document.createElement('div');
            emptyDiv.className = 'chart-placeholder';
            emptyDiv.textContent = 'No records recorded to display';
            container.appendChild(emptyDiv);
            return;
        }

        if (mode === 'kpi') {
            var grid = document.createElement('div');
            grid.className = 'rep-kpi-card-grid';
            if (dataset.type === 'single') {
                var total = sum(dataset.values);
                dataset.labels.forEach(function (label, idx) {
                    var val = dataset.values[idx];
                    var pct = total > 0 ? ((val / total) * 100).toFixed(1) : '0.0';
                    var card = document.createElement('div');
                    card.className = 'rep-kpi-card';
                    var rail = document.createElement('div');
                    rail.className = 'rep-kpi-card-rail';
                    rail.style.backgroundColor = PALETTE[idx % PALETTE.length];
                    card.appendChild(rail);
                    var labelP = document.createElement('p');
                    labelP.className = 'rep-kpi-card-label';
                    labelP.textContent = label;
                    card.appendChild(labelP);
                    var valP = document.createElement('p');
                    valP.className = 'rep-kpi-card-value';
                    valP.textContent = val;
                    card.appendChild(valP);
                    var pctSpan = document.createElement('span');
                    pctSpan.className = 'rep-kpi-card-percentage';
                    pctSpan.textContent = pct + '%';
                    card.appendChild(pctSpan);
                    grid.appendChild(card);
                });
            } else if (dataset.type === 'multi') {
                dataset.datasets.forEach(function (ds) {
                    var total = sum(ds.values);
                    var avg = (total / ds.values.length).toFixed(1);
                    var card = document.createElement('div');
                    card.className = 'rep-kpi-card';
                    var rail = document.createElement('div');
                    rail.className = 'rep-kpi-card-rail';
                    rail.style.backgroundColor = ds.color;
                    card.appendChild(rail);
                    var labelP = document.createElement('p');
                    labelP.className = 'rep-kpi-card-label';
                    labelP.textContent = ds.label + ' (Total)';
                    card.appendChild(labelP);
                    var valP = document.createElement('p');
                    valP.className = 'rep-kpi-card-value';
                    valP.textContent = total;
                    card.appendChild(valP);
                    var pctSpan = document.createElement('span');
                    pctSpan.className = 'rep-kpi-card-percentage';
                    pctSpan.textContent = 'Avg: ' + avg + '/mo';
                    card.appendChild(pctSpan);
                    grid.appendChild(card);
                });
                dataset.labels.forEach(function (month, mIdx) {
                    var val1 = dataset.datasets[0].values[mIdx] || 0;
                    var val2 = dataset.datasets[1].values[mIdx] || 0;
                    var card = document.createElement('div');
                    card.className = 'rep-kpi-card';
                    var rail = document.createElement('div');
                    rail.className = 'rep-kpi-card-rail';
                    rail.style.backgroundColor = '#64748b';
                    card.appendChild(rail);
                    var labelP = document.createElement('p');
                    labelP.className = 'rep-kpi-card-label';
                    labelP.textContent = month + ' Activity';
                    card.appendChild(labelP);
                    var valP = document.createElement('p');
                    valP.className = 'rep-kpi-card-value';
                    valP.style.fontSize = '1rem';
                    valP.innerHTML = '\uD83D\uDC64 ' + val1 + ' \u00A0\uD83D\uDCC2 ' + val2;
                    card.appendChild(valP);
                    var pctSpan = document.createElement('span');
                    pctSpan.className = 'rep-kpi-card-percentage';
                    pctSpan.textContent = 'Ratio: ' + (val1 > 0 ? (val2 / val1).toFixed(1) : val2) + ' doc/app';
                    card.appendChild(pctSpan);
                    grid.appendChild(card);
                });
            }
            container.appendChild(grid);
        } else if (mode === 'heatmap') {
            var grid = document.createElement('div');
            grid.className = 'rep-heatmap-grid';
            if (dataset.type === 'single') {
                var total = sum(dataset.values);
                var maxVal = Math.max.apply(null, dataset.values);
                dataset.labels.forEach(function (label, idx) {
                    var val = dataset.values[idx];
                    var pct = total > 0 ? ((val / total) * 100).toFixed(1) : '0.0';
                    var cell = document.createElement('div');
                    cell.className = 'rep-heatmap-cell';
                    var baseHex = PALETTE[idx % PALETTE.length];
                    var weight = maxVal > 0 ? val / maxVal : 0;
                    cell.style.backgroundColor = hexToRgba(baseHex, 0.08 + 0.92 * weight);
                    cell.style.color = weight > 0.45 ? '#ffffff' : '#0f172a';
                    var labelDiv = document.createElement('div');
                    labelDiv.className = 'rep-heatmap-cell-label';
                    labelDiv.textContent = label;
                    cell.appendChild(labelDiv);
                    var metaDiv = document.createElement('div');
                    metaDiv.className = 'rep-heatmap-cell-meta';
                    var valDiv = document.createElement('span');
                    valDiv.className = 'rep-heatmap-cell-value';
                    valDiv.textContent = val;
                    metaDiv.appendChild(valDiv);
                    var pctDiv = document.createElement('span');
                    pctDiv.className = 'rep-heatmap-cell-pct';
                    pctDiv.textContent = pct + '%';
                    metaDiv.appendChild(pctDiv);
                    cell.appendChild(metaDiv);
                    grid.appendChild(cell);
                });
            } else if (dataset.type === 'multi') {
                var allValues = dataset.datasets[0].values.concat(dataset.datasets[1].values);
                var maxVal = Math.max.apply(null, allValues);
                dataset.labels.forEach(function (month, mIdx) {
                    dataset.datasets.forEach(function (ds) {
                        var val = ds.values[mIdx] || 0;
                        var weight = maxVal > 0 ? val / maxVal : 0;
                        var cell = document.createElement('div');
                        cell.className = 'rep-heatmap-cell';
                        cell.style.backgroundColor = hexToRgba(ds.color, 0.08 + 0.92 * weight);
                        cell.style.color = weight > 0.45 ? '#ffffff' : '#0f172a';
                        var labelDiv = document.createElement('div');
                        labelDiv.className = 'rep-heatmap-cell-label';
                        labelDiv.textContent = month + ' · ' + ds.label;
                        cell.appendChild(labelDiv);
                        var metaDiv = document.createElement('div');
                        metaDiv.className = 'rep-heatmap-cell-meta';
                        var valDiv = document.createElement('span');
                        valDiv.className = 'rep-heatmap-cell-value';
                        valDiv.textContent = val;
                        metaDiv.appendChild(valDiv);
                        cell.appendChild(metaDiv);
                        grid.appendChild(cell);
                    });
                });
            }
            container.appendChild(grid);
        } else if (mode === 'timeline') {
            var timeline = document.createElement('div');
            timeline.className = 'rep-timeline-layout';
            if (dataset.type === 'single') {
                var items = [];
                dataset.labels.forEach(function (lbl, i) {
                    items.push({ label: lbl, value: dataset.values[i], originalIndex: i });
                });
                var sequentialCharts = ['chartFunnel', 'chartCaseAging'];
                if (sequentialCharts.indexOf(canvasId) === -1) {
                    items.sort(function (a, b) { return b.value - a.value; });
                }
                var total = sum(dataset.values);
                items.forEach(function (item) {
                    var node = document.createElement('div');
                    node.className = 'rep-timeline-node';
                    var dot = document.createElement('div');
                    dot.className = 'rep-timeline-dot';
                    dot.style.borderColor = PALETTE[item.originalIndex % PALETTE.length];
                    node.appendChild(dot);
                    var content = document.createElement('div');
                    content.className = 'rep-timeline-content';
                    var labelGroup = document.createElement('div');
                    labelGroup.className = 'rep-timeline-label-group';
                    var labelNode = document.createElement('span');
                    labelNode.className = 'rep-timeline-node-label';
                    labelNode.textContent = item.label;
                    labelGroup.appendChild(labelNode);
                    var subNode = document.createElement('span');
                    subNode.className = 'rep-timeline-node-sub';
                    subNode.textContent = total > 0 ? ((item.value / total) * 100).toFixed(1) + '% contribution' : '0.0%';
                    labelGroup.appendChild(subNode);
                    content.appendChild(labelGroup);
                    var valNode = document.createElement('span');
                    valNode.className = 'rep-timeline-node-value';
                    valNode.textContent = item.value;
                    content.appendChild(valNode);
                    node.appendChild(content);
                    timeline.appendChild(node);
                });
            } else if (dataset.type === 'multi') {
                dataset.labels.forEach(function (month, mIdx) {
                    var val1 = dataset.datasets[0].values[mIdx] || 0;
                    var val2 = dataset.datasets[1].values[mIdx] || 0;
                    var node = document.createElement('div');
                    node.className = 'rep-timeline-node';
                    var dot = document.createElement('div');
                    dot.className = 'rep-timeline-dot';
                    dot.style.borderColor = '#10b981';
                    node.appendChild(dot);
                    var content = document.createElement('div');
                    content.className = 'rep-timeline-content';
                    var labelGroup = document.createElement('div');
                    labelGroup.className = 'rep-timeline-label-group';
                    var labelNode = document.createElement('span');
                    labelNode.className = 'rep-timeline-node-label';
                    labelNode.textContent = month + ' Monthly Rollout';
                    labelGroup.appendChild(labelNode);
                    var subNode = document.createElement('span');
                    subNode.className = 'rep-timeline-node-sub';
                    subNode.innerHTML = '\uD83D\uDC64 New: ' + val1 + ' \u00A0\u2022\u00A0 \uD83D\uDCC2 Uploads: ' + val2;
                    labelGroup.appendChild(subNode);
                    content.appendChild(labelGroup);
                    var valNode = document.createElement('span');
                    valNode.className = 'rep-timeline-node-value';
                    valNode.innerHTML = '<span style="color:#0ea5e9;">' + val1 + '</span> / <span style="color:#10b981;">' + val2 + '</span>';
                    content.appendChild(valNode);
                    node.appendChild(content);
                    timeline.appendChild(node);
                });
            }
            container.appendChild(timeline);
        }
    }

    // ── Bootstrap all rep-cards ────────────────────────────
    document.querySelectorAll('.rep-card').forEach(function (card) {
        var canvas = card.querySelector('canvas');
        if (!canvas) return;
        var canvasId = canvas.id;
        var dataset = getStandardizedDataset(canvasId);
        if (!dataset) {
            if (['chartRequirements', 'chartCasesStatus', 'chartCasesType'].indexOf(canvasId) >= 0) {
                card.style.display = 'none';
            }
            return;
        }

        var titleEl = card.querySelector('.rep-card-title');
        var subEl = card.querySelector('.rep-card-sub');
        var header = document.createElement('div');
        header.className = 'rep-card-header';
        var titleGroup = document.createElement('div');
        titleGroup.className = 'rep-card-title-group';

        if (titleEl) {
            titleEl.parentNode.insertBefore(header, titleEl);
            titleGroup.appendChild(titleEl);
            if (subEl) { titleGroup.appendChild(subEl); }
            header.appendChild(titleGroup);
        } else {
            card.insertBefore(header, card.firstChild);
            var prev = card.previousElementSibling;
            if (prev && prev.classList.contains('rep-section')) {
                var h2 = prev.querySelector('h2');
                var note = prev.querySelector('.rep-section-note');
                if (h2) {
                    var pTitle = document.createElement('p');
                    pTitle.className = 'rep-card-title';
                    pTitle.textContent = h2.textContent;
                    titleGroup.appendChild(pTitle);
                    if (note) {
                        var pSub = document.createElement('p');
                        pSub.className = 'rep-card-sub';
                        pSub.textContent = note.textContent;
                        titleGroup.appendChild(pSub);
                    }
                    header.appendChild(titleGroup);
                    prev.style.display = 'none';
                }
            }
        }

        var canvasWrap = canvas.parentNode;
        canvasWrap.style.position = 'relative';
        var htmlContainer = document.createElement('div');
        htmlContainer.className = 'rep-dynamic-container';
        htmlContainer.style.display = 'none';
        canvasWrap.parentNode.insertBefore(htmlContainer, canvasWrap.nextSibling);

        var defMode = getDefaultMode(canvasId);
        switchChartMode(canvasId, defMode);
    });

    // Expose switchChartMode globally so inline onclick handlers can call it
    window.switchChartMode = switchChartMode;
});

