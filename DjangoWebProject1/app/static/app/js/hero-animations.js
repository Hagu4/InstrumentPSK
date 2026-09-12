document.addEventListener('DOMContentLoaded', () => {
    // ═══════════════════════════════════════
    // HERO PARTICLES
    // ═══════════════════════════════════════
    (function createParticles() {
        const container = document.getElementById('heroParticles');
        if (!container) return; // Ensure container exists
        for (let i = 0; i < 30; i++) {
            const spark = document.createElement('div');
            spark.className = 'spark';
            spark.style.left = Math.random() * 100 + '%';
            spark.style.top = (60 + Math.random() * 40) + '%';
            spark.style.animationDuration = (3 + Math.random() * 5) + 's';
            spark.style.animationDelay = Math.random() * 5 + 's';
            spark.style.width = spark.style.height = (1 + Math.random() * 2) + 'px';
            container.appendChild(spark);
        }
    })();

    // ═══════════════════════════════════════
    // COUNTER ANIMATION
    // ═══════════════════════════════════════
    function animateCounter(el, target, suffix = '') { // Removed default '+' suffix as per provided HTML has it
        let current = 0;
        const step = target / 60; // Fixed steps for smoother animation
        const interval = setInterval(() => {
            current += step;
            if (current >= target) {
                current = target;
                clearInterval(interval);
            }
            el.textContent = Math.floor(current).toLocaleString('ru-RU') + suffix;
        }, 20); // Faster interval for smoother animation
    }

    // Observe hero counter
    const heroCounterObs = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                // Ensure the element with id 'heroCounter' exists before animating
                const heroCounterElement = document.getElementById('heroCounter');
                if (heroCounterElement) {
                    animateCounter(heroCounterElement, 5000, '+');
                }
                
                document.querySelectorAll('.hero-stat .num[data-count]').forEach(el => {
                    const target = parseInt(el.dataset.count);
                    const suffix = el.textContent.replace(/[0-9]/g, '');
                    animateCounter(el, target, suffix);
                });
                heroCounterObs.unobserve(entry.target); // Stop observing once animated
            }
        });
    }, { threshold: 0.3 }); // Trigger when 30% of the element is visible

    // Ensure the element with class 'hero-badge' exists before observing
    const heroBadgeElement = document.querySelector('.hero-badge');
    if (heroBadgeElement) {
        heroCounterObs.observe(heroBadgeElement);
    }
});