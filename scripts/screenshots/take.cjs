// Retake the product screenshots in screenshots/ from a local demo server.
//
// Setup (once per run; nothing here touches your real data):
//   1. Start the app on a throwaway database in demo mode:
//        DEMO_MODE=1 SECRET_KEY=any-local-value DATABASE_URL=sqlite:////tmp/shots/may.db \
//          python -c "from app import create_app; create_app().run(port=5098)"
//   2. Add the extra vehicles, charging sessions and station prices:
//        DEMO_MODE=1 SECRET_KEY=any-local-value DATABASE_URL=sqlite:////tmp/shots/may.db \
//          python scripts/screenshots/seed.py
//   3. Install the driver beside this run and use your installed Chrome:
//        mkdir -p /tmp/shots-node && cd /tmp/shots-node && npm i playwright-core
//   4. From /tmp/shots-node:
//        DB_PATH=/tmp/shots/may.db OUT_DIR=/path/to/OdoDash/screenshots \
//          node /path/to/OdoDash/scripts/screenshots/take.cjs
//
// Desktop shots are 1800x1116 (1440x893 at 1.25x) and phone shots 780x1688
// (390x844 at 2x), the sizes the README and the landing page already use.
const { createRequire } = require('node:module');
const { execFileSync } = require('node:child_process');
const path = require('node:path');
const { chromium } = createRequire(process.cwd() + '/')('playwright-core');

const BASE = process.env.BASE_URL || 'http://127.0.0.1:5098';
const DB = process.env.DB_PATH;
const OUT = process.env.OUT_DIR || 'screenshots';
if (!DB) { console.error('Set DB_PATH to the demo database'); process.exit(1); }

const sql = (q) => execFileSync('sqlite3', [DB, q]).toString();
const setDark = (on) => sql(`update users set dark_mode=${on ? 1 : 0};`);
const setAccent = (hex) => sql(hex
  ? `insert into app_settings(key,value) values('primary_color','${hex}') on conflict(key) do update set value='${hex}';`
  : `delete from app_settings where key='primary_color';`);

(async () => {
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  const desktop = await browser.newContext({ viewport: { width: 1440, height: 893 }, deviceScaleFactor: 1.25 });
  const phone = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
  const login = async (ctx) => {
    const page = await ctx.newPage();
    await page.goto(BASE + '/auth/login');
    await page.fill('input[name="username"]', 'demo');
    await page.fill('input[name="password"]', 'demo');
    await Promise.all([page.waitForNavigation(), page.click('button[type="submit"]')]);
    return page;
  };
  const dp = await login(desktop);
  const pp = await login(phone);
  const shot = async (page, url, file, prep) => {
    await page.goto(BASE + url, { waitUntil: 'networkidle' });
    if (prep) await prep(page);
    await page.waitForTimeout(700);
    await page.screenshot({ path: path.join(OUT, file) });
    console.log('wrote', file);
  };
  const settingsTab = (label) => async (page) => {
    await page.locator('nav a, nav button, [role="tab"], aside a, aside button')
      .filter({ hasText: new RegExp('^\\s*' + label + '\\s*$') }).first().click();
  };

  setAccent(null); setDark(false);
  await shot(dp, '/dashboard', 'dashboard-light.png');
  await shot(pp, '/dashboard', 'mobile-dashboard.png');
  await shot(pp, '/fuel/new?vehicle_id=1', 'mobile-add-fuel.png', (p) => p.evaluate(() => window.scrollTo(0, 0)));
  await shot(dp, '/auth/settings', 'branding.png', settingsTab('Branding'));

  setDark(true);
  await shot(dp, '/dashboard', 'dashboard-dark.png');
  await shot(dp, '/vehicles/1', 'vehicle-page.png');
  await shot(pp, '/vehicles/1', 'mobile-vehicle.png');
  await shot(dp, '/auth/settings', 'settings.png');

  setDark(false); setAccent('#ea580c');
  await shot(dp, '/dashboard', 'accent-color.png');

  setAccent(null); setDark(false);
  await browser.close();
})().catch((e) => { console.error('FAILED', e.message); process.exit(1); });
