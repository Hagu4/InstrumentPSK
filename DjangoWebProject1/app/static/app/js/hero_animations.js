document.addEventListener('DOMContentLoaded', () => {

    // --- Intersection Observer for fade-in animations ---
    const animatedElements = document.querySelectorAll('.hero-text, .hero-visual');

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('is-visible');
                // Animate numbers only when the section is visible
                triggerNumberAnimations(entry.target);
                observer.unobserve(entry.target); // Optional: stop observing once animated
            }
        });
    }, {
        threshold: 0.1 // Trigger when 10% of the element is visible
    });

    animatedElements.forEach(el => {
        observer.observe(el);
    });


    // --- Number Counting Animation ---
    function triggerNumberAnimations(parentElement) {
        const elements = parentElement.querySelectorAll('[data-target]');
        elements.forEach(el => {
            const target = el.dataset.target;
            const isK = target.toUpperCase().includes('K');
            const isPlus = target.includes('+');

            const targetNum = parseFloat(target.replace('K', '').replace('+', ''));
            if (isNaN(targetNum)) return;
            
            let currentNum = 0;
            const duration = 2000; // 2 seconds
            const stepTime = 20; // update every 20ms
            const steps = duration / stepTime;
            const increment = targetNum / steps;

            const timer = setInterval(() => {
                currentNum += increment;
                
                if (currentNum >= targetNum) {
                    clearInterval(timer);
                    el.innerText = target; // Set final text to include 'K' and '+'
                } else {
                    let displayNum = Math.ceil(currentNum);
                    if (isK) {
                        // We don't show 'K' during animation for smoothness
                        el.innerText = displayNum;
                    } else {
                        el.innerText = displayNum;
                    }
                }
            }, stepTime);
        });
    }
});
