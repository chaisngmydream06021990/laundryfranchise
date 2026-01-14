document.addEventListener('DOMContentLoaded', () => {
    // Mobile Menu Toggle
    // --- Stats Counter Animation ---
    const statsSection = document.querySelector('.stats-section');
    const counters = document.querySelectorAll('.stat-number');
    let started = false; // Function started ? No

    function startCount(el) {
        const target = +el.getAttribute('data-target');
        const duration = 2000; // 2 seconds
        const step = target / (duration / 16); // 60fps

        let current = 0;
        const timer = setInterval(() => {
            current += step;
            if (current >= target) {
                el.innerText = formatNumber(target); // Helper to format 1000->1k if needed, or just raw
                if (target > 1000) el.innerText = (target / 1000).toFixed(0) + 'K+';
                if (target > 1000000) el.innerText = (target / 1000000).toFixed(0) + 'M+';
                if (target < 1000) el.innerText = target + '%';
                clearInterval(timer);
            } else {
                if (target > 1000000) {
                    el.innerText = (current / 1000000).toFixed(1) + 'M';
                } else if (target > 1000) {
                    el.innerText = (current / 1000).toFixed(0) + 'K';
                } else {
                    el.innerText = Math.ceil(current);
                }
            }
        }, 16);
    }

    function formatNumber(num) {
        return num.toLocaleString();
    }

    if (statsSection) {
        const observer = new IntersectionObserver((entries) => {
            if (entries[0].isIntersecting && !started) {
                counters.forEach(counter => startCount(counter));
                started = true;
            }
        }, { threshold: 0.5 });

        observer.observe(statsSection);
    }

    // --- Pincode Availability Checker ---
    const pincodeInput = document.querySelector('.pincode-box input');
    const checkBtn = document.querySelector('.btn-check');

    if (checkBtn && pincodeInput) {
        checkBtn.addEventListener('click', (e) => {
            e.preventDefault();
            const pincode = pincodeInput.value.trim();

            // Validate pincode format (6 digits)
            if (!/^\d{6}$/.test(pincode)) {
                showPincodeResult('Please enter a valid 6-digit pincode', 'error');
                return;
            }

            // Check if Bhopal pincode (starts with 462)
            if (pincode.startsWith('462')) {
                showPincodeResult('Available! 🎉', 'success');
            } else {
                showPincodeResult('Not available in this area yet. Coming soon!', 'info');
            }
        });

        // Allow Enter key to trigger check
        pincodeInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                checkBtn.click();
            }
        });
    }

    function showPincodeResult(message, type) {
        // Remove any existing result
        const existingResult = document.querySelector('.pincode-result');
        if (existingResult) existingResult.remove();

        const resultDiv = document.createElement('div');
        resultDiv.className = `pincode-result pincode-result-${type}`;
        resultDiv.style.cssText = `
            margin-top: 1rem;
            padding: 1rem 1.5rem;
            border-radius: 12px;
            font-weight: 500;
            animation: fadeIn 0.3s ease;
        `;

        if (type === 'success') {
            resultDiv.style.background = 'rgba(16, 185, 129, 0.1)';
            resultDiv.style.border = '2px solid #10B981';
            resultDiv.style.color = '#047857';

            resultDiv.innerHTML = `
                <div style="font-size: 1.1rem; margin-bottom: 0.5rem;">${message}</div>
                <div style="font-size: 0.9rem; margin-top: 0.8rem;">Contact us to start your journey:</div>
                <div style="display: flex; gap: 1rem; margin-top: 0.5rem; flex-wrap: wrap;">
                    <a href="https://wa.me/917777818187?text=Hi," 
                       target="_blank"
                       style="background: #25D366; color: white; padding: 0.5rem 1rem; border-radius: 8px; text-decoration: none; display: inline-flex; align-items: center; gap: 0.5rem; font-size: 0.9rem;">
                        💬 WhatsApp
                    </a>
                    <a href="tel:+917777818188" 
                       style="background: var(--color-primary); color: var(--color-secondary); padding: 0.5rem 1rem; border-radius: 8px; text-decoration: none; display: inline-flex; align-items: center; gap: 0.5rem; font-size: 0.9rem;">
                        📞 Call Now
                    </a>
                </div>
            `;
        } else if (type === 'error') {
            resultDiv.style.background = 'rgba(239, 68, 68, 0.1)';
            resultDiv.style.border = '2px solid #EF4444';
            resultDiv.style.color = '#991B1B';
            resultDiv.innerHTML = message;
        } else {
            resultDiv.style.background = 'rgba(59, 130, 246, 0.1)';
            resultDiv.style.border = '2px solid #3B82F6';
            resultDiv.style.color = '#1E40AF';
            resultDiv.innerHTML = `${message}<br><small style="margin-top: 0.5rem; display: block;">📞 Call us: <a href="tel:+917777818188" style="color: inherit; font-weight: 600;">+91 77778 18188</a></small>`;
        }

        const pincodeCheck = document.querySelector('.hero-pincode-check');
        pincodeCheck.appendChild(resultDiv);
    }

    // --- Mobile Menu Toggle ---
    const mobileToggle = document.querySelector('.mobile-toggle');
    const navLinks = document.querySelector('.nav-links');

    if (mobileToggle) {
        mobileToggle.addEventListener('click', () => {
            navLinks.classList.toggle('active');
            mobileToggle.textContent = navLinks.classList.contains('active') ? '✕' : '☰';
        });
    }

    // Close menu when clicking a link
    document.querySelectorAll('.nav-links a').forEach(link => {
        link.addEventListener('click', () => {
            navLinks.classList.remove('active');
            if (mobileToggle) mobileToggle.textContent = '☰';
        });
    });

    // ========================================
    // Scroll Reveal Animation
    // ========================================
    const revealElements = document.querySelectorAll('.fade-in, .fade-in-left, .fade-in-right');

    const revealObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('visible');
                revealObserver.unobserve(entry.target);
            }
        });
    }, { threshold: 0.1, rootMargin: '0px 0px -50px 0px' });

    revealElements.forEach(el => revealObserver.observe(el));

    // ========================================
    // Form Submission - WhatsApp Redirect
    // ========================================
    const handleFormSubmit = async (e) => {
        e.preventDefault();
        const form = e.target;
        const btn = form.querySelector('button[type="submit"]');
        if (!btn) return;

        const originalText = btn.textContent;

        // Get form data
        const formData = new FormData(form);
        const name = formData.get('name') || 'Not provided';
        const phone = formData.get('phone') || 'Not provided';
        const email = formData.get('email') || 'Not provided';
        const city = formData.get('city') || 'Not provided';

        // Validate required fields
        if (!formData.get('name') || !formData.get('phone')) {
            alert('Please fill in all required fields');
            return;
        }

        // Create WhatsApp message
        const message = `Hi! I'm interested in Cleanzit Franchise.%0A%0A` +
            `📝 *My Details:*%0A` +
            `Name: ${encodeURIComponent(name)}%0A` +
            `Phone: ${encodeURIComponent(phone)}%0A` +
            `Email: ${encodeURIComponent(email)}%0A` +
            `City: ${encodeURIComponent(city)}%0A%0A` +
            `Please share the franchise details.`;

        // WhatsApp number (bot/franchise inquiry line)
        const whatsappNumber = '917777818187';
        const whatsappURL = `https://wa.me/${whatsappNumber}?text=${message}`;

        // UI Feedback
        btn.textContent = 'Redirecting to WhatsApp...';
        btn.disabled = true;

        // Redirect to WhatsApp
        setTimeout(() => {
            window.open(whatsappURL, '_blank');

            // Reset form and button
            form.reset();
            btn.textContent = '✓ Sent! Check WhatsApp';
            btn.style.backgroundColor = 'var(--color-success, #16A34A)';

            setTimeout(() => {
                btn.textContent = originalText;
                btn.style.backgroundColor = '';
                btn.disabled = false;
            }, 3000);
        }, 500);
    };

    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', handleFormSubmit);
    });

    // ========================================
    // Smooth Scroll
    // ========================================
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth'
                });
            }
        });
    });
});
