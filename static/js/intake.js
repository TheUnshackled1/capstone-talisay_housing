/**
 * Intake Module JavaScript
 * Talisay Housing Authority - IHSMS
 * Landowner ISF Submission Form
 */

document.addEventListener('DOMContentLoaded', function() {
    // Form elements
    const form = document.getElementById('landowner-form');
    const steps = document.querySelectorAll('.form-step');
    const progressSteps = document.querySelectorAll('.progress-steps .step');
    const stepConnectors = document.querySelectorAll('.step-connector');
    const prevBtn = document.getElementById('prev-btn');
    const nextBtn = document.getElementById('next-btn');
    const submitBtn = document.getElementById('submit-btn');
    const addISFBtn = document.getElementById('add-isf-btn');
    const isfList = document.getElementById('isf-list');
    const isfTemplate = document.getElementById('isf-template');
    const isfDataField = document.getElementById('isf-data-field');
    const isfCountDisplay = document.getElementById('isf-count');
    const consentCheckbox = document.getElementById('consent-checkbox');
    
    let currentStep = 1;
    let isfEntries = [];
    
    // Initialize with one ISF entry
    addISFEntry();
    
    // Navigation
    prevBtn.addEventListener('click', () => navigateStep(-1));
    nextBtn.addEventListener('click', () => navigateStep(1));
    
    // Add ISF button
    addISFBtn.addEventListener('click', addISFEntry);
    
    // Form submission
    form.addEventListener('submit', handleSubmit);
    
    /**
     * Navigate between steps
     */
    function navigateStep(direction) {
        const newStep = currentStep + direction;
        
        // Validate current step before proceeding
        if (direction > 0 && !validateStep(currentStep)) {
            return;
        }
        
        // Collect ISF data before moving to review
        if (currentStep === 3 && direction > 0) {
            collectISFData();
            if (isfEntries.length === 0) {
                alert('Please add at least one ISF household.');
                return;
            }
        }
        
        // Update review section when reaching step 4
        if (newStep === 4) {
            updateReviewSection();
        }
        
        // Update step visibility
        steps.forEach(step => step.classList.remove('active'));
        document.querySelector(`.form-step[data-step="${newStep}"]`).classList.add('active');
        
        // Update progress indicators
        updateProgressIndicators(newStep);
        
        // Update navigation buttons
        currentStep = newStep;
        updateNavigationButtons();
        
        // Scroll to top of form
        window.scrollTo({ top: document.querySelector('.intake-header').offsetTop - 20, behavior: 'smooth' });
    }
    
    /**
     * Update progress step indicators
     */
    function updateProgressIndicators(step) {
        progressSteps.forEach((el, index) => {
            const stepNum = index + 1;
            el.classList.remove('active', 'completed');
            
            if (stepNum < step) {
                el.classList.add('completed');
            } else if (stepNum === step) {
                el.classList.add('active');
            }
        });
        
        // Update connectors
        stepConnectors.forEach((connector, index) => {
            if (index < step - 1) {
                connector.classList.add('completed');
            } else {
                connector.classList.remove('completed');
            }
        });
    }
    
    /**
     * Update navigation button states
     */
    function updateNavigationButtons() {
        prevBtn.disabled = currentStep === 1;
        
        if (currentStep === 4) {
            nextBtn.style.display = 'none';
            submitBtn.style.display = 'flex';
        } else {
            nextBtn.style.display = 'flex';
            submitBtn.style.display = 'none';
        }
    }
    
    /**
     * Validate current step
     */
    function validateStep(step) {
        const currentStepEl = document.querySelector(`.form-step[data-step="${step}"]`);
        const inputs = currentStepEl.querySelectorAll('input[required], select[required], textarea[required]');
        let isValid = true;
        
        inputs.forEach(input => {
            // Skip ISF template inputs
            if (input.closest('template')) return;
            
            // Clear previous errors
            input.classList.remove('error');
            const errorEl = input.parentElement.querySelector('.error-message');
            if (errorEl) errorEl.remove();
            
            if (!input.value.trim()) {
                isValid = false;
                input.classList.add('error');
                showFieldError(input, 'This field is required');
            }
        });
        
        // Step 3: Validate ISF entries
        if (step === 3) {
            const isfValid = validateISFEntries();
            isValid = isValid && isfValid;
        }
        
        if (!isValid) {
            // Focus first error
            const firstError = currentStepEl.querySelector('.error');
            if (firstError) firstError.focus();
        }
        
        return isValid;
    }
    
    /**
     * Validate all ISF entries
     */
    function validateISFEntries() {
        let isValid = true;
        const entries = isfList.querySelectorAll('.isf-entry');
        
        if (entries.length === 0) {
            return false;
        }
        
        entries.forEach(entry => {
            const nameInput = entry.querySelector('.isf-name');
            const membersInput = entry.querySelector('.isf-members');
            const incomeInput = entry.querySelector('.isf-income');
            const yearsInput = entry.querySelector('.isf-years');
            
            [nameInput, membersInput, incomeInput, yearsInput].forEach(input => {
                input.classList.remove('error');
                if (!input.value.trim()) {
                    isValid = false;
                    input.classList.add('error');
                }
            });
        });
        
        return isValid;
    }
    
    /**
     * Show field error message
     */
    function showFieldError(input, message) {
        const existingError = input.parentElement.querySelector('.error-message');
        if (existingError) existingError.remove();
        
        const errorSpan = document.createElement('span');
        errorSpan.className = 'error-message';
        errorSpan.textContent = message;
        input.parentElement.appendChild(errorSpan);
    }
    
    /**
     * Add new ISF entry
     */
    function addISFEntry() {
        const index = isfList.children.length;
        const clone = isfTemplate.content.cloneNode(true);
        const entry = clone.querySelector('.isf-entry');
        
        entry.dataset.index = index;
        entry.querySelector('.isf-number').textContent = index + 1;
        
        // Add remove handler
        entry.querySelector('.btn-remove-isf').addEventListener('click', function() {
            removeISFEntry(entry);
        });
        
        // Add animation class
        entry.style.opacity = '0';
        entry.style.transform = 'translateY(-20px)';
        
        isfList.appendChild(clone);
        
        // Trigger animation
        requestAnimationFrame(() => {
            const addedEntry = isfList.lastElementChild;
            addedEntry.style.transition = 'all 0.3s ease';
            addedEntry.style.opacity = '1';
            addedEntry.style.transform = 'translateY(0)';
        });
        
        updateISFCount();
        
        // Focus the name field
        const nameInput = isfList.lastElementChild.querySelector('.isf-name');
        if (nameInput) nameInput.focus();
    }
    
    /**
     * Remove ISF entry
     */
    function removeISFEntry(entry) {
        // Don't remove if it's the only one
        if (isfList.children.length <= 1) {
            alert('You must have at least one ISF household.');
            return;
        }
        
        // Animate out
        entry.style.transition = 'all 0.3s ease';
        entry.style.opacity = '0';
        entry.style.transform = 'translateX(-20px)';
        
        setTimeout(() => {
            entry.remove();
            renumberISFEntries();
            updateISFCount();
        }, 300);
    }
    
    /**
     * Renumber ISF entries after removal
     */
    function renumberISFEntries() {
        const entries = isfList.querySelectorAll('.isf-entry');
        entries.forEach((entry, index) => {
            entry.dataset.index = index;
            entry.querySelector('.isf-number').textContent = index + 1;
        });
    }
    
    /**
     * Update ISF count display
     */
    function updateISFCount() {
        const count = isfList.children.length;
        isfCountDisplay.textContent = count;
        
        // Also update review count
        const reviewCount = document.getElementById('review-isf-count');
        if (reviewCount) reviewCount.textContent = count;
    }
    
    /**
     * Collect ISF data from form
     */
    function collectISFData() {
        isfEntries = [];
        const entries = isfList.querySelectorAll('.isf-entry');
        
        entries.forEach(entry => {
            const data = {
                full_name: entry.querySelector('.isf-name').value.trim(),
                phone_number: entry.querySelector('.isf-phone').value.trim(),
                household_members: parseInt(entry.querySelector('.isf-members').value) || 1,
                monthly_income: parseFloat(entry.querySelector('.isf-income').value) || 0,
                years_residing: parseFloat(entry.querySelector('.isf-years').value) || 0
            };
            
            if (data.full_name) {
                isfEntries.push(data);
            }
        });
        
        // Update hidden field
        isfDataField.value = JSON.stringify(isfEntries);
    }
    
    /**
     * Update review section with form data
     */
    function updateReviewSection() {
        // Landowner info
        document.getElementById('review-name').textContent = 
            document.querySelector('[name="landowner_name"]').value || '-';
        document.getElementById('review-phone').textContent = 
            document.querySelector('[name="landowner_phone"]').value || '-';
        document.getElementById('review-email').textContent = 
            document.querySelector('[name="landowner_email"]').value || 'Not provided';
        
        // Property info
        document.getElementById('review-address').textContent = 
            document.querySelector('[name="property_address"]').value || '-';
        
        const barangaySelect = document.querySelector('[name="barangay"]');
        document.getElementById('review-barangay').textContent = 
            barangaySelect.options[barangaySelect.selectedIndex]?.text || '-';
        
        // ISF list
        const reviewISFList = document.getElementById('review-isf-list');
        reviewISFList.innerHTML = '';
        
        isfEntries.forEach((isf, index) => {
            const div = document.createElement('div');
            div.className = 'review-isf-item';
            div.innerHTML = `
                <span class="isf-num">${index + 1}</span>
                <span class="isf-name">${isf.full_name}</span>
                <span>${isf.household_members} member${isf.household_members > 1 ? 's' : ''}</span>
                <span>₱${isf.monthly_income.toLocaleString()}/mo</span>
            `;
            reviewISFList.appendChild(div);
        });
        
        document.getElementById('review-isf-count').textContent = isfEntries.length;
    }
    
    /**
     * Handle form submission
     */
    function handleSubmit(e) {
        // Validate consent
        if (!consentCheckbox.checked) {
            e.preventDefault();
            alert('Please check the consent box to proceed.');
            consentCheckbox.focus();
            return;
        }
        
        // Final validation
        if (isfEntries.length === 0) {
            e.preventDefault();
            alert('Please add at least one ISF household.');
            return;
        }
        
        // Ensure ISF data is in hidden field
        isfDataField.value = JSON.stringify(isfEntries);
        
        // Show loading state
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Submitting...';
    }
    
    // Add CSS for error state
    const style = document.createElement('style');
    style.textContent = `
        .form-control.error {
            border-color: var(--intake-danger) !important;
            background-color: rgba(239, 68, 68, 0.05);
        }
        .form-control.error:focus {
            box-shadow: 0 0 0 3px rgba(239, 68, 68, 0.15);
        }
    `;
    document.head.appendChild(style);
    
    // Initialize scroll animations
    initScrollAnimations();
});

/**
 * Initialize scroll animations
 */
function initScrollAnimations() {
    const animatedElements = document.querySelectorAll(
        '.scroll-animate, .scroll-animate-left, .scroll-animate-right, .scroll-animate-scale'
    );
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('animate-visible');
            }
        });
    }, {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    });
    
    animatedElements.forEach(el => observer.observe(el));
}
