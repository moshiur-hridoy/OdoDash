/* Shared Chart.js theme.
 *
 * Loaded once from base.html. It only changes Chart.defaults and registers a
 * presentation plugin, so every existing chart picks it up without any change
 * to its data, labels or callbacks. Options a chart sets itself still win.
 * A no-op on pages that do not load Chart.js.
 */
(function () {
    'use strict';
    if (!window.Chart) return;

    var root = document.documentElement;
    var FONT = '"Inter var", "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif';

    function isDark() { return root.classList.contains('dark'); }

    function cssVar(name, fallback) {
        var v = getComputedStyle(root).getPropertyValue(name).trim();
        return v || fallback;
    }

    // --- colour helpers ----------------------------------------------------
    function parseColor(str) {
        if (typeof str !== 'string') return null;
        var m = str.match(/^rgba?\(\s*(\d+)[,\s]+(\d+)[,\s]+(\d+)(?:[,\s/]+([\d.]+))?\s*\)$/i);
        if (m) return { r: +m[1], g: +m[2], b: +m[3], a: m[4] === undefined ? 1 : +m[4] };
        m = str.match(/^#([0-9a-f]{3}|[0-9a-f]{6})$/i);
        if (m) {
            var h = m[1].length === 3 ? m[1].replace(/./g, '$&$&') : m[1];
            return { r: parseInt(h.slice(0, 2), 16), g: parseInt(h.slice(2, 4), 16), b: parseInt(h.slice(4, 6), 16), a: 1 };
        }
        return null;
    }
    function rgba(c, a) { return 'rgba(' + c.r + ',' + c.g + ',' + c.b + ',' + a + ')'; }

    // --- theme (re-applied when light/dark flips) ---------------------------
    function applyTheme() {
        var dark = isDark();
        var D = Chart.defaults;
        D.font.family = FONT;
        D.font.size = 12;
        D.color = dark ? '#9aa3b2' : '#6b7280';
        D.borderColor = dark ? 'rgba(255,255,255,0.06)' : 'rgba(16,24,40,0.06)';

        D.animation = { duration: 700, easing: 'easeOutQuart' };
        D.transitions.active = { animation: { duration: 180 } };

        D.layout.padding = 4;
        D.elements.bar.borderRadius = 6;
        D.elements.bar.borderSkipped = false;
        D.elements.line.tension = 0.35;
        D.elements.line.borderWidth = 2.5;
        D.elements.line.borderCapStyle = 'round';
        D.elements.point.radius = 0;
        D.elements.point.hoverRadius = 5;
        D.elements.point.hitRadius = 14;
        D.elements.point.borderWidth = 2;
        D.elements.arc.borderWidth = 2;
        D.elements.arc.borderColor = dark ? '#12151c' : '#ffffff';
        D.elements.arc.hoverOffset = 6;

        D.interaction.mode = 'index';
        D.interaction.intersect = false;

        var P = D.plugins;
        P.legend.labels.usePointStyle = true;
        P.legend.labels.pointStyle = 'circle';
        P.legend.labels.boxWidth = 8;
        P.legend.labels.boxHeight = 8;
        P.legend.labels.padding = 16;

        var t = P.tooltip;
        t.backgroundColor = dark ? 'rgba(10,12,18,0.94)' : 'rgba(17,24,39,0.94)';
        t.titleColor = '#f3f4f6';
        t.bodyColor = '#d1d5db';
        t.borderColor = dark ? 'rgba(255,255,255,0.10)' : 'rgba(255,255,255,0.06)';
        t.borderWidth = 1;
        t.cornerRadius = 10;
        t.padding = { top: 10, bottom: 10, left: 12, right: 12 };
        t.boxPadding = 4;
        t.usePointStyle = true;
        t.titleFont = { family: FONT, weight: '600', size: 12 };
        t.bodyFont = { family: FONT, size: 12 };
        t.caretSize = 6;

        // Scale defaults: light dashed grid, no axis line, quiet ticks.
        var grid = dark ? 'rgba(255,255,255,0.06)' : 'rgba(16,24,40,0.06)';
        ['linear', 'category', 'time', 'logarithmic'].forEach(function (type) {
            var s = Chart.overrides && Chart.defaults.scales && Chart.defaults.scales[type];
            if (!s) return;
            s.grid = Object.assign({}, s.grid, { color: grid, drawTicks: false, tickLength: 0 });
            s.border = Object.assign({}, s.border, { display: false, dash: [3, 4] });
            s.ticks = Object.assign({}, s.ticks, { padding: 8 });
        });
    }

    // --- gradient plugin ----------------------------------------------------
    // Turns flat single-colour fills into soft vertical gradients at draw time.
    // The original value is kept on the dataset so data, legends and callbacks
    // keep seeing exactly what the page configured.
    var gradients = {
        id: 'odoGradients',
        beforeDatasetsDraw: function (chart) {
            var area = chart.chartArea;
            if (!area || chart.options.indexAxis === 'y') return;
            var ctx = chart.ctx;
            var type = chart.config.type;

            chart.data.datasets.forEach(function (ds, i) {
                var meta = chart.getDatasetMeta(i);
                var dsType = meta.type || type;

                if (dsType === 'bar') {
                    if (ds._odoBase === undefined) ds._odoBase = ds.backgroundColor;
                    var base = parseColor(ds._odoBase);
                    if (!base) return;
                    var g = ctx.createLinearGradient(0, area.top, 0, area.bottom);
                    g.addColorStop(0, rgba(base, Math.min(1, base.a + 0.15)));
                    g.addColorStop(1, rgba(base, Math.max(0.35, base.a - 0.35)));
                    ds.backgroundColor = g;
                } else if (dsType === 'line' && ds.fill) {
                    if (ds._odoBase === undefined) ds._odoBase = ds.backgroundColor;
                    var line = parseColor(ds.borderColor) || parseColor(ds._odoBase);
                    if (!line) return;
                    var f = ctx.createLinearGradient(0, area.top, 0, area.bottom);
                    f.addColorStop(0, rgba(line, 0.28));
                    f.addColorStop(1, rgba(line, 0));
                    ds.backgroundColor = f;
                }
            });
        }
    };

    // Dots appear on hover only; show a white ring so the point reads clearly.
    var pointRing = {
        id: 'odoPointRing',
        beforeUpdate: function (chart) {
            chart.data.datasets.forEach(function (ds) {
                if (ds.pointHoverBackgroundColor === undefined) ds.pointHoverBackgroundColor = isDark() ? '#12151c' : '#ffffff';
                if (ds.pointHoverBorderColor === undefined && typeof ds.borderColor === 'string') ds.pointHoverBorderColor = ds.borderColor;
            });
        }
    };

    Chart.register(gradients, pointRing);
    applyTheme();

    // Follow the app's light/dark switch live, without reloading charts.
    new MutationObserver(function () {
        applyTheme();
        Object.keys(Chart.instances).forEach(function (k) {
            var c = Chart.instances[k];
            if (c) c.update('none');
        });
    }).observe(root, { attributes: true, attributeFilter: ['class'] });
})();
