/*
 * Live password guidance for the markup in templates/partials/password_rules.html.
 *
 * Each rule is ticked off as the password is typed, and the confirm field says
 * whether the two agree. Until both are satisfied the inputs carry a custom
 * validity message, so the browser refuses to submit and points at the field,
 * instead of the server bouncing the whole form back empty.
 *
 * Rules mirror app.security.validate_password_strength, which stays the
 * authority: change both together.
 */
(function () {
    'use strict';

    var RULES = {
        length: function (v) { return v.length >= 8; },
        upper: function (v) { return /[A-Z]/.test(v); },
        lower: function (v) { return /[a-z]/.test(v); },
        digit: function (v) { return /\d/.test(v); }
    };

    var TONE = {
        idle: ['text-gray-500', 'dark:text-gray-400'],
        met: ['text-green-700', 'dark:text-green-400'],
        unmet: ['text-red-600', 'dark:text-red-400']
    };
    var ALL_TONES = [].concat(TONE.idle, TONE.met, TONE.unmet);

    function show(el, on, display) {
        el.classList.toggle('hidden', !on);
        el.classList.toggle(display, on);
    }

    function paint(el, state) {
        if (el.getAttribute('data-state') === state) return;
        el.setAttribute('data-state', state);
        el.classList.remove.apply(el.classList, ALL_TONES);
        el.classList.add.apply(el.classList, TONE[state]);
        el.querySelectorAll('[data-icon]').forEach(function (icon) {
            show(icon, icon.getAttribute('data-icon') === state, 'inline-flex');
        });
    }

    function flagInvalid(el, on) {
        if (on) el.setAttribute('aria-invalid', 'true');
        else el.removeAttribute('aria-invalid');
    }

    function describe(input, id) {
        var ids = (input.getAttribute('aria-describedby') || '').split(/\s+/).filter(Boolean);
        if (ids.indexOf(id) === -1) {
            ids.push(id);
            input.setAttribute('aria-describedby', ids.join(' '));
        }
    }

    function init(list) {
        var input = document.getElementById(list.getAttribute('data-password-rules'));
        if (!input || input.dataset.passwordRulesReady) return;
        input.dataset.passwordRulesReady = '1';

        var confirm = document.getElementById(list.getAttribute('data-password-confirm'));
        var match = confirm && document.querySelector('[data-password-match="' + confirm.id + '"]');
        var optional = list.hasAttribute('data-password-optional');
        var msgWeak = list.getAttribute('data-msg-weak');
        var msgMismatch = list.getAttribute('data-msg-mismatch');
        var items = list.querySelectorAll('[data-rule]');
        // Unmet rules stay neutral while someone is still typing; they turn red
        // once the field is left or a submit is attempted.
        var passwordTouched = false;
        var confirmTouched = false;

        describe(input, list.id);
        if (match) describe(confirm, match.id);

        function update() {
            var value = input.value;
            var allMet = true;

            items.forEach(function (li) {
                var ok = RULES[li.getAttribute('data-rule')](value);
                if (!ok) allMet = false;
                paint(li, ok ? 'met' : (passwordTouched && value ? 'unmet' : 'idle'));
            });

            var blankAllowed = optional && value === '';
            // An empty required field is left to the browser's own "required" message.
            input.setCustomValidity(allMet || blankAllowed || value === '' ? '' : msgWeak);
            flagInvalid(input, passwordTouched && !!value && !allMet);

            if (!confirm) return;
            var other = confirm.value;
            var agrees = other === value;
            // Also covers a new password typed with confirm left blank.
            confirm.setCustomValidity(agrees ? '' : msgMismatch);

            if (!match) return;
            // Still typing the confirmation and on track so far: say nothing yet.
            var stillTyping = !confirmTouched && value.indexOf(other) === 0 && other.length < value.length;
            if (other === '' || stillTyping) {
                show(match, false, 'flex');
                paint(match, 'idle');
                flagInvalid(confirm, false);
                return;
            }
            var state = agrees ? 'met' : 'unmet';
            show(match, true, 'flex');
            paint(match, state);
            match.querySelectorAll('[data-match-text]').forEach(function (span) {
                span.classList.toggle('hidden', span.getAttribute('data-match-text') !== state);
            });
            flagInvalid(confirm, !agrees);
        }

        input.addEventListener('input', update);
        input.addEventListener('blur', function () {
            if (input.value) { passwordTouched = true; update(); }
        });
        input.addEventListener('invalid', function () { passwordTouched = true; update(); });

        if (confirm) {
            confirm.addEventListener('input', update);
            confirm.addEventListener('blur', function () {
                if (confirm.value) { confirmTouched = true; update(); }
            });
            confirm.addEventListener('invalid', function () {
                passwordTouched = true;
                confirmTouched = true;
                update();
            });
        }

        // Browsers may autofill after load; start from whatever is there.
        update();
    }

    function initAll() {
        document.querySelectorAll('[data-password-rules]').forEach(init);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initAll);
    } else {
        initAll();
    }
    document.addEventListener('htmx:afterSwap', initAll);
})();
