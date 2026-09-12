$(document).ready(function() {
    var $menu = $('.panel-group');
    var leaveTimer;
    var enterTimer;
    var enterDelay = 100; // A short delay to prevent accidental opening on fast mouse-overs
    var leaveDelay = 300; // A delay before closing the menu when the mouse leaves the whole area

    $menu.on('mouseenter', '.panel-default', function() {
        var $currentItem = $(this);
        var $currentCollapse = $currentItem.find('.panel-collapse');

        // Cancel any timer that was set to close the menus
        clearTimeout(leaveTimer);

        // Set a short timer to open the new menu
        enterTimer = setTimeout(function() {
            // If this menu is already visibly open from a previous hover, do nothing.
            if ($currentCollapse.hasClass('is-visible')) {
                return;
            }

            // If the menu was open because of a server-render, remove the 'in' class
            // so this script can take over management.
            if ($currentCollapse.hasClass('in')) {
                $currentCollapse.removeClass('in');
            }

            // Calculate the top position relative to the .panel-group
            var parentOffsetTop = $currentItem.position().top;
            $currentCollapse.css('top', parentOffsetTop + 'px'); 

            // Hide any other menus that this script has opened.
            $currentItem.siblings().find('.panel-collapse.is-visible').removeClass('is-visible');

            // Show the current menu.
            $currentCollapse.addClass('is-visible');

        }, enterDelay);
    });

    $menu.on('mouseleave', '.panel-default', function() {
        // If the mouse leaves an item, we cancel the timer that was going to open its menu.
        clearTimeout(enterTimer);
    });

    // A single mouseleave for the entire component to handle closing.
    $menu.on('mouseleave', function() {
        // Cancel any pending open actions.
        clearTimeout(enterTimer);
        // Set a timer to close any menu that is currently open.
        leaveTimer = setTimeout(function() {
            $menu.find('.panel-collapse').removeClass('is-visible');
        }, leaveDelay);
    });
});