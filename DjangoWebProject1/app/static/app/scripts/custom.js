$(document).ready(function() {
    $('.dropdown-submenu a.test').on("click", function(e){
        // Close other open submenus at the same level
        $(this).parents('.dropdown-menu').find('.dropdown-submenu .dropdown-menu').not($(this).next('ul')).hide();
        // Toggle the current submenu
        $(this).next('ul').toggle();
        e.stopPropagation();
        // This prevents the parent dropdown from closing immediately.
        // We might need a more robust solution for closing the main dropdown on outside click.
    });

    // Close all dropdowns when clicking outside
    $(document).on("click", function() {
        $('.dropdown-submenu .dropdown-menu').hide();
    });
});

/* --- Profile Dropdown Logic (Plain JavaScript) --- */
document.addEventListener('DOMContentLoaded', function() {
    const dropdownBtn = document.getElementById('profile-dropdown-btn');
    const dropdownMenu = document.getElementById('profile-dropdown-menu');

    if (dropdownBtn && dropdownMenu) {
        // Toggle dropdown on button click
        dropdownBtn.addEventListener('click', function(event) {
            event.stopPropagation();
            const isVisible = dropdownMenu.classList.toggle('show');
            dropdownBtn.classList.toggle('active', isVisible);
        });

        // Close dropdown if clicked outside
        document.addEventListener('click', function(event) {
            if (!dropdownMenu.contains(event.target) && !dropdownBtn.contains(event.target)) {
                dropdownMenu.classList.remove('show');
                dropdownBtn.classList.remove('active');
            }
        });

        // Close dropdown on Escape key
        document.addEventListener('keydown', function(event) {
            if (event.key === 'Escape' && dropdownMenu.classList.contains('show')) {
                dropdownMenu.classList.remove('show');
                dropdownBtn.classList.remove('active');
            }
        });
    }
});