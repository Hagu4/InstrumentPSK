document.addEventListener('DOMContentLoaded', () => {
    const htmlEl = document.documentElement;
    const savedTheme = localStorage.getItem('theme');
    const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;

    // Use saved theme, or preferred scheme, or default to light
    const currentTheme = savedTheme || (prefersDark ? 'dark' : 'light');
    htmlEl.setAttribute('data-theme', currentTheme);

    // No theme switcher button created here, assuming it's part of the static HTML if needed
    // No cursor glow logic here, assuming it's handled in main.js
});
