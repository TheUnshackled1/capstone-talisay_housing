/**
 * Talisay Housing Information System
 * Staff Dashboard JavaScript
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize all components
    initSidebar();
    initCurrentDate();
    initAlerts();
    initTooltips();
    initScrollAnimations();
});

/**
 * Sidebar Toggle for Mobile
 */
function initSidebar() {
    const mobileMenuBtn = document.getElementById('mobileMenuBtn');
    const sidebar = document.getElementById('sidebar');
    const sidebarOverlay = document.getElementById('sidebarOverlay');

    if (mobileMenuBtn && sidebar) {
        mobileMenuBtn.addEventListener('click', function() {
            sidebar.classList.toggle('open');
            if (sidebarOverlay) {
                sidebarOverlay.classList.toggle('open');
            }
            // Toggle aria-expanded
            const isOpen = sidebar.classList.contains('open');
            mobileMenuBtn.setAttribute('aria-expanded', isOpen);
        });
    }

    if (sidebarOverlay) {
        sidebarOverlay.addEventListener('click', function() {
            sidebar.classList.remove('open');
            sidebarOverlay.classList.remove('open');
            if (mobileMenuBtn) {
                mobileMenuBtn.setAttribute('aria-expanded', 'false');
            }
        });
    }

    // Close sidebar on escape key
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && sidebar && sidebar.classList.contains('open')) {
            sidebar.classList.remove('open');
            if (sidebarOverlay) {
                sidebarOverlay.classList.remove('open');
            }
            if (mobileMenuBtn) {
                mobileMenuBtn.setAttribute('aria-expanded', 'false');
                mobileMenuBtn.focus();
            }
        }
    });

    // Handle window resize
    let resizeTimer;
    window.addEventListener('resize', function() {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(function() {
            if (window.innerWidth >= 1024) {
                sidebar.classList.remove('open');
                if (sidebarOverlay) {
                    sidebarOverlay.classList.remove('open');
                }
            }
        }, 100);
    });
}

/**
 * Display Current Date
 */
function initCurrentDate() {
    const dateEl = document.getElementById('currentDate');
    if (dateEl) {
        const options = { 
            weekday: 'long', 
            year: 'numeric', 
            month: 'long', 
            day: 'numeric' 
        };
        dateEl.textContent = new Date().toLocaleDateString('en-US', options);
    }
}

/**
 * Auto-dismiss Alerts
 */
function initAlerts() {
    const alerts = document.querySelectorAll('.alert[data-auto-dismiss]');
    alerts.forEach(function(alert) {
        const duration = parseInt(alert.dataset.autoDismiss) || 5000;
        setTimeout(function() {
            dismissAlert(alert);
        }, duration);
    });

    // Add click to dismiss
    const dismissButtons = document.querySelectorAll('.alert-dismiss');
    dismissButtons.forEach(function(btn) {
        btn.addEventListener('click', function() {
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
    setTimeout(function() {
        alert.remove();
    }, 300);
}

/**
 * Initialize Tooltips
 */
function initTooltips() {
    const tooltipTriggers = document.querySelectorAll('[data-tooltip]');
    tooltipTriggers.forEach(function(trigger) {
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
        setTimeout(function() {
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
        const later = function() {
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
        console.error('Failed to copy:', err);
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
    closeBtn.addEventListener('click', function() {
        removeNotification(notification);
    });

    if (duration > 0) {
        setTimeout(function() {
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
    setTimeout(function() {
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

    cancelBtn.addEventListener('click', function() {
        overlay.remove();
        if (onCancel) onCancel();
    });

    confirmBtn.addEventListener('click', function() {
        overlay.remove();
        if (onConfirm) onConfirm();
    });

    overlay.addEventListener('click', function(e) {
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
