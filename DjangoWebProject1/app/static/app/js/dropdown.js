document.addEventListener('DOMContentLoaded', function() {
    // This script handles generic dropdowns, like the "Ещё" button in the nav.
    // The profile dropdown is handled separately in custom.js.

    const genericDropdowns = document.querySelectorAll('.dropdown');

    genericDropdowns.forEach(dropdown => {
        const toggle = dropdown.querySelector('.dropdown-toggle');
        const menu = dropdown.querySelector('.dropdown-menu');

        if (toggle && menu) {
            toggle.addEventListener('click', function(event) {
                event.preventDefault();
                event.stopPropagation(); // Prevent window click event from closing it immediately
                
                // Close other open dropdowns
                document.querySelectorAll('.dropdown-menu.show').forEach(openMenu => {
                    if (openMenu !== menu) {
                        openMenu.classList.remove('show');
                    }
                });
                // Toggle current dropdown
                menu.classList.toggle('show');
            });
        }
    });

    // Note: The logic to close dropdowns on outside click is now consolidated in custom.js
    // to handle all dropdown types at once.
});
