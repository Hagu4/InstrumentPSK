document.addEventListener('DOMContentLoaded', function() {
    console.log('Scroll animations loaded');
    
    function animateOnScroll() {
        var elements = document.querySelectorAll('.scroll-animate');
        console.log('Found elements:', elements.length);
        
        elements.forEach(function(el) {
            if (!el.classList.contains('visible')) {
                var position = el.getBoundingClientRect();
                var windowHeight = window.innerHeight;
                
                console.log('Element position:', position.top, 'Window height:', windowHeight);
                
                if (position.top < windowHeight * 0.85) {
                    el.classList.add('visible');
                    console.log('Animated element');
                }
            }
        });
    }
    
    window.addEventListener('scroll', animateOnScroll);
    animateOnScroll();
});
