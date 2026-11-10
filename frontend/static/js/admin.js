// AURA Admin JavaScript
$(function () {
    var $sidebar = $('#sidebar'), $backdrop = $('#sidebar-backdrop');

    function closeSidebar() { $sidebar.removeClass('open'); $backdrop.removeClass('show'); }

    // Mobile sidebar toggle
    $('#sidebar-toggle').on('click', function (e) {
        e.stopPropagation();
        $sidebar.toggleClass('open');
        $backdrop.toggleClass('show', $sidebar.hasClass('open'));
    });
    $backdrop.on('click', closeSidebar);
    $(document).on('keydown', function (e) { if (e.key === 'Escape') closeSidebar(); });

    // (Delete confirmations are handled by each form's own onsubmit="return confirm(...)")

    // Image upload preview for product / category forms
    $('input[type="file"][accept*="image"], input[type="file"][name="images"], input[type="file"][name="image"]').on('change', function () {
        var $box = $(this).siblings('.upload-preview');
        if (!$box.length) { $box = $('<div class="upload-preview d-flex flex-wrap gap-2 mt-2"></div>').insertAfter(this); }
        $box.empty();
        Array.prototype.slice.call(this.files || [], 0, 8).forEach(function (f) {
            if (!/^image\//.test(f.type)) return;
            var url = URL.createObjectURL(f);
            $box.append('<img src="' + url + '" alt="" style="width:72px;height:96px;object-fit:cover;border-radius:6px;border:1px solid var(--aura-border,#2a2a2a);">');
        });
    });

    // Auto-hide success alerts
    setTimeout(function () { $('.alert-success').fadeOut(300); }, 5000);
});
