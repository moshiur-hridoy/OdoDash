// Quick fuel entry form behaviour. Scoped to one <form data-quick-fuel-form>
// so the same form can live on its own page or inside the quick-fuel sheet
// without its fields colliding with the page underneath.
(function () {
    function initQuickFuelForm(form) {
        if (!form || form.dataset.quickFuelReady) return;
        form.dataset.quickFuelReady = '1';

        var field = function (name) { return form.querySelector('[name="' + name + '"]'); };
        var part = function (role) { return form.querySelector('[data-qf="' + role + '"]'); };
        var vehicle = field('vehicle_id');
        var odometer = field('odometer');
        var volume = field('volume');
        var price = field('price_per_unit');
        var total = field('total_cost');
        var station = field('station');
        var stationSelect = field('station_id');
        var parse = window.parseDecimal || function (v) { var n = parseFloat(v); return isNaN(n) ? null : n; };

        function recalc(changed) {
            var v = parse(volume.value);
            var p = parse(price.value);
            var t = parse(total.value);
            if (changed === 'volume' || changed === 'price') {
                if (v > 0 && p !== null && p >= 0) total.value = (v * p).toFixed(2);
            } else if (changed === 'total') {
                // Keep the chosen price stable while editing the total.
                if (t > 0 && p > 0) volume.value = (t / p).toFixed(3);
            }
        }

        function onVehicleChange() {
            var option = vehicle.options[vehicle.selectedIndex];
            if (!option) return;
            price.value = option.dataset.lastPrice || '';
            recalc('price');

            var unit = option.dataset.odometerUnit || form.dataset.distanceUnit;
            var hint = part('last-odometer');
            var badge = part('tessie-badge');
            var unitBadge = part('odometer-unit');
            var label = part('reading-label');
            if (unitBadge) unitBadge.textContent = unit;
            // An hours-metered vehicle is asked for engine hours (#324).
            if (option.dataset.readingLabel && label) label.textContent = option.dataset.readingLabel;

            if (option.dataset.usesTessie === 'true' && option.dataset.tessieOdometer) {
                badge.classList.remove('hidden');
                odometer.readOnly = true;
                odometer.value = Math.round(parseFloat(option.dataset.tessieOdometer));
                odometer.classList.add('bg-gray-100', 'dark:bg-gray-600');
                hint.textContent = form.dataset.tFromTessie;
            } else {
                badge.classList.add('hidden');
                odometer.readOnly = false;
                odometer.classList.remove('bg-gray-100', 'dark:bg-gray-600');
                var last = option.dataset.odometer;
                if (last && parseFloat(last) > 0) {
                    hint.textContent = form.dataset.tLast + ': ' + parseFloat(last).toLocaleString() + ' ' + unit;
                    odometer.placeholder = last;
                } else {
                    hint.textContent = '';
                    odometer.placeholder = '0';
                }
            }
        }

        vehicle.addEventListener('change', onVehicleChange);
        volume.addEventListener('input', function () { recalc('volume'); });
        price.addEventListener('input', function () { recalc('price'); });
        total.addEventListener('input', function () { recalc('total'); });
        if (stationSelect && station) {
            stationSelect.addEventListener('change', function () {
                var option = stationSelect.options[stationSelect.selectedIndex];
                var name = option ? option.getAttribute('data-name') : '';
                if (name) station.value = name;
            });
        }
        onVehicleChange();
    }

    window.initQuickFuelForm = initQuickFuelForm;
    document.addEventListener('DOMContentLoaded', function () {
        document.querySelectorAll('form[data-quick-fuel-form]').forEach(initQuickFuelForm);
    });
})();
