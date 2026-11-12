/**
 * Tailwind build configuration, used by scripts/build_css.py.
 *
 * Pinned to Tailwind v3.4.17 -- the same version as the in-browser runtime
 * (app/static/vendor/tailwindcss.js) this build replaces -- so every class the
 * templates already use compiles to exactly the rules the runtime produced.
 *
 * The compiled CSS can only contain classes it can see in these files. A class
 * assembled at render time (`bg-{{ colour }}-100`) is invisible to it, which
 * tests/test_css_build.py guards against.
 */
const shades = [50, 100, 200, 300, 400, 500, 600, 700, 800, 900];

module.exports = {
  content: [
    './app/templates/**/*.{html,js}',
    './app/static/js/**/*.js',
    './app/**/*.py',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // The accent is chosen at runtime (Settings > Branding), so the
        // palette lives in CSS variables that base.html derives from it. The
        // `-rgb` channel form keeps opacity modifiers such as
        // `bg-primary-900/30` working.
        primary: Object.fromEntries(
          shades.map((s) => [s, `rgb(var(--primary-${s}-rgb) / <alpha-value>)`])
        ),
      },
    },
  },
  plugins: [],
};
