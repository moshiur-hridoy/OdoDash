/*
 * Small behaviours shared by the design-system components.
 *
 * [data-password-toggle="<input id>"]  flips a password field between hidden
 *   and visible text, swapping the eye icon and the button's label.
 * form[data-busy-submit]  disables its submit button once the form is sent,
 *   so a slow round trip cannot be submitted twice.
 */
(function () {
    'use strict';

    document.addEventListener('click', function (event) {
        var toggle = event.target.closest('[data-password-toggle]');
        if (!toggle) return;
        var input = document.getElementById(toggle.getAttribute('data-password-toggle'));
        if (!input) return;
        var reveal = input.type === 'password';
        input.type = reveal ? 'text' : 'password';
        toggle.setAttribute('aria-pressed', reveal ? 'true' : 'false');
        toggle.setAttribute('aria-label', toggle.getAttribute(reveal ? 'data-label-hide' : 'data-label-show'));
        toggle.querySelector('[data-eye="show"]').hidden = reveal;
        toggle.querySelector('[data-eye="hide"]').hidden = !reveal;
    });

    document.addEventListener('submit', function (event) {
        var form = event.target;
        if (!form.hasAttribute('data-busy-submit') || event.defaultPrevented) return;
        // Defer so the button's own name/value is still sent with the form.
        setTimeout(function () {
            form.querySelectorAll('button[type="submit"]').forEach(function (button) {
                button.disabled = true;
                button.setAttribute('aria-busy', 'true');
            });
        }, 0);
    });

    // A page restored from the back/forward cache keeps the disabled state.
    window.addEventListener('pageshow', function () {
        document.querySelectorAll('form[data-busy-submit] button[aria-busy="true"]').forEach(function (button) {
            button.disabled = false;
            button.removeAttribute('aria-busy');
        });
    });
})();

/* File drop zones: show the chosen file's name in place of the prompt. */
(function () {
    'use strict';
    document.addEventListener('change', function (event) {
        var input = event.target;
        if (!input.matches || !input.matches('[data-file-drop]')) return;
        var zone = input.closest('.ds-drop');
        var label = zone && zone.querySelector('[data-file-name]');
        if (!label) return;
        if (!label.dataset.prompt) label.dataset.prompt = label.textContent;
        var file = input.files && input.files[0];
        var names = Array.prototype.map.call(input.files || [], function (f) { return f.name; });
        label.textContent = file ? names.join(', ') : label.dataset.prompt;
        zone.classList.toggle('has-file', !!file);
    });
    ['dragenter', 'dragover'].forEach(function (type) {
        document.addEventListener(type, function (event) {
            var zone = event.target.closest && event.target.closest('.ds-drop');
            if (zone) zone.classList.add('is-dragging');
        });
    });
    ['dragleave', 'drop'].forEach(function (type) {
        document.addEventListener(type, function (event) {
            var zone = event.target.closest && event.target.closest('.ds-drop');
            if (zone) zone.classList.remove('is-dragging');
        });
    });
})();

/* Disclosure buttons: [data-disclosure][aria-controls] shows and hides the
   element it names, keeping aria-expanded in step. */
(function () {
    'use strict';
    document.addEventListener('click', function (event) {
        var button = event.target.closest('[data-disclosure][aria-controls]');
        if (!button) return;
        var target = document.getElementById(button.getAttribute('aria-controls'));
        if (!target) return;
        var open = button.getAttribute('aria-expanded') !== 'true';
        button.setAttribute('aria-expanded', open ? 'true' : 'false');
        target.hidden = !open;
    });
})();
