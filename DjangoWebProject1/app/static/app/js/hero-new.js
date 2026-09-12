document.addEventListener('DOMContentLoaded', function() {

    // --- Particle Animation ---
    const particlesContainer = document.querySelector('.particles-container');
    if (particlesContainer) {
        const particleCount = 50; // Number of particles
        for (let i = 0; i < particleCount; i++) {
            let particle = document.createElement('div');
            particle.classList.add('particle');
            particle.style.left = `${Math.random() * 100}%`;
            particle.style.top = `${Math.random() * 100}%`;
            particle.style.animationDuration = `${Math.random() * 5 + 5}s`; // Random duration between 5-10s
            particle.style.animationDelay = `${Math.random() * 5}s`;      // Random delay up to 5s
            particlesContainer.appendChild(particle);
        }
    }

    // --- Button Ripple Effect ---
    const rippleButtons = document.querySelectorAll('.hero .btn-primary');
    rippleButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            const rect = button.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;

            let ripple = document.createElement('span');
            ripple.classList.add('ripple');
            ripple.style.left = x + 'px';
            ripple.style.top = y + 'px';

            this.appendChild(ripple);

            setTimeout(() => {
                ripple.remove();
            }, 600); // Match animation duration
        });
    });

    // --- Ticker Duplication for seamless loop ---
    const ticker = document.querySelector('.ticker');
    if (ticker) {
        const tickerContent = ticker.innerHTML;
        ticker.innerHTML += tickerContent; // Duplicate content
    }

});
