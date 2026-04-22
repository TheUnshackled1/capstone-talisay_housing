// Mobile Menu Toggle
document.addEventListener('DOMContentLoaded', function() {
    const mobileMenuBtn = document.getElementById('mobileMenuBtn');
    const mobileMenu = document.getElementById('mobileMenu');
    const menuIcon = document.getElementById('menuIcon');
    const closeIcon = document.getElementById('closeIcon');

    if (mobileMenuBtn && mobileMenu) {
        mobileMenuBtn.addEventListener('click', function() {
            mobileMenu.classList.toggle('hidden');
            menuIcon.classList.toggle('hidden');
            closeIcon.classList.toggle('hidden');
        });

        // Close mobile menu when clicking on a link
        const mobileLinks = mobileMenu.querySelectorAll('a');
        mobileLinks.forEach(function(link) {
            link.addEventListener('click', function() {
                mobileMenu.classList.add('hidden');
                menuIcon.classList.remove('hidden');
                closeIcon.classList.add('hidden');
            });
        });
    }

    // Smooth scroll for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(function(anchor) {
        anchor.addEventListener('click', function(e) {
            const targetId = this.getAttribute('href');
            if (targetId === '#') return;
            
            const targetElement = document.querySelector(targetId);
            if (targetElement) {
                e.preventDefault();
                targetElement.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });

    // ========================================
    // SCROLL ANIMATIONS - Intersection Observer
    // ========================================

    // Check for reduced motion preference
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    let scrollObserver; // Declare outside if block for scope access

    if (!prefersReducedMotion) {
        // Select all elements with scroll animation classes
        const animatedElements = document.querySelectorAll(
            '.scroll-animate, .scroll-animate-left, .scroll-animate-right, ' +
            '.scroll-animate-scale, .scroll-animate-fade, .scroll-animate-bounce, ' +
            '.scroll-animate-rotate, .scroll-animate-blur, .scroll-animate-card'
        );

        // Create intersection observer
        const observerOptions = {
            root: null, // viewport
            rootMargin: '0px 0px -80px 0px', // trigger slightly before element enters
            threshold: 0.15 // 15% visible triggers animation
        };

        scrollObserver = new IntersectionObserver(function(entries, observer) {
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

        // Auto-apply animation classes to common elements
        autoApplyScrollAnimations();
    }

    // ========================================
    // AUTO-APPLY ANIMATIONS TO COMMON ELEMENTS
    // ========================================
    function autoApplyScrollAnimations() {
        // Stats section - stagger the stat items
        const statItems = document.querySelectorAll('.stats-section .stat-item, .stats-section > div > div');
        statItems.forEach(function(item, index) {
            if (!item.classList.contains('scroll-animate')) {
                item.classList.add('scroll-animate-scale');
                item.classList.add('scroll-delay-' + Math.min(index + 1, 6));
                scrollObserver.observe(item);
            }
        });

        // Service/feature cards
        const cards = document.querySelectorAll('.service-card, .feature-card, [class*="card"]');
        cards.forEach(function(card, index) {
            if (!card.classList.contains('scroll-animate') && 
                !card.classList.contains('scroll-animate-card')) {
                card.classList.add('scroll-animate-card');
                card.classList.add('scroll-delay-' + Math.min((index % 3) + 1, 3));
                scrollObserver.observe(card);
            }
        });

        // Section headings
        const headings = document.querySelectorAll('section h2, section h3, .section-title');
        headings.forEach(function(heading) {
            if (!heading.classList.contains('scroll-animate')) {
                heading.classList.add('scroll-animate');
                scrollObserver.observe(heading);
            }
        });

        // Paragraphs in sections (not in header/nav)
        const sectionParagraphs = document.querySelectorAll('section > p, section > div > p');
        sectionParagraphs.forEach(function(p, index) {
            if (!p.classList.contains('scroll-animate') && 
                !p.closest('header') && !p.closest('nav')) {
                p.classList.add('scroll-animate-fade');
                p.classList.add('scroll-delay-' + Math.min(index + 1, 2));
                scrollObserver.observe(p);
            }
        });

        // Images (except logo/icons)
        const images = document.querySelectorAll('section img:not([class*="logo"]):not([class*="icon"])');
        images.forEach(function(img) {
            if (!img.classList.contains('scroll-animate')) {
                img.classList.add('scroll-animate-scale');
                scrollObserver.observe(img);
            }
        });

        // Grid items
        const gridItems = document.querySelectorAll('.grid > div, .grid > article');
        gridItems.forEach(function(item, index) {
            if (!item.classList.contains('scroll-animate') && 
                !item.classList.contains('scroll-animate-card')) {
                item.classList.add('scroll-animate');
                item.classList.add('scroll-delay-' + Math.min((index % 4) + 1, 4));
                scrollObserver.observe(item);
            }
        });

        // Footer sections
        const footerSections = document.querySelectorAll('footer > div > div');
        footerSections.forEach(function(section, index) {
            if (!section.classList.contains('scroll-animate')) {
                section.classList.add('scroll-animate');
                section.classList.add('scroll-delay-' + Math.min(index + 1, 4));
                scrollObserver.observe(section);
            }
        });
    }

    // ========================================
    // ANIMATED COUNTER FOR STATS (Optional)
    // ========================================
    function animateCounter(element, target, duration) {
        let start = 0;
        const increment = target / (duration / 16);
        const suffix = element.textContent.replace(/[\d,]/g, '').trim();
        
        function updateCounter() {
            start += increment;
            if (start < target) {
                element.textContent = Math.floor(start).toLocaleString() + suffix;
                requestAnimationFrame(updateCounter);
            } else {
                element.textContent = target.toLocaleString() + suffix;
            }
        }
        updateCounter();
    }

    // Animate stat numbers when they come into view
    const statNumbers = document.querySelectorAll('.stat-number, [class*="stat"] .text-4xl, [class*="stat"] .text-3xl');
    const counterObserver = new IntersectionObserver(function(entries) {
        entries.forEach(function(entry) {
            if (entry.isIntersecting) {
                const element = entry.target;
                const text = element.textContent;
                const number = parseInt(text.replace(/[^\d]/g, ''));
                
                if (!isNaN(number) && number > 0 && !element.dataset.animated) {
                    element.dataset.animated = 'true';
                    animateCounter(element, number, 1500);
                }
                counterObserver.unobserve(element);
            }
        });
    }, { threshold: 0.5 });

    statNumbers.forEach(function(num) {
        counterObserver.observe(num);
    });
});
