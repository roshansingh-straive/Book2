/* Run against the built app: PLAYWRIGHT_MODULE=/path/to/playwright node qa/check_accuracy_ui.cjs */
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const url = process.env.SHELF_CHECK_URL || 'http://127.0.0.1:8888';
const result = JSON.parse(fs.readFileSync(path.join(root, 'app/public/data/scans/bay_f3.json')));
const health = {
  live_available_by_difficulty: { easy: true, medium: true, hard: true },
};
const errors = [];
(async () => {
  const browser = await chromium.launch({ headless: true, ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}) });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    page.on('pageerror', e => errors.push(e.message));
    await page.route('**/token', route => route.fulfill({ json: {} }));
    await page.goto(url);
    await page.getByRole('button', { name: 'Continue with saved samples' }).click();
    await page.getByRole('button', { name: 'Explore a sample' }).click();
    await page.getByRole('heading', { name: 'Shelf Photo & AI Recognition' }).waitFor();
    assert.equal(await page.getByRole('option', { name: 'Run a new analysis' }).evaluate(option => option.disabled), true);
    assert.equal(await page.getByRole('button', { name: 'All', exact: true }).isDisabled(), true);
    for (const bay of ['bay_a1', 'bay_a2', 'bay_f1', 'bay_f2', 'bay_m1', 'bay_f3']) {
      await page.getByRole('combobox', { name: 'Shelf bay' }).selectOption(bay);
      const saved = JSON.parse(fs.readFileSync(path.join(root, `app/public/data/scans/${bay}.json`)));
      await page.getByRole('heading', { name: saved.bay_name, exact: true }).waitFor();
      await page.getByText('Sample · Saved analysis', { exact: true }).waitFor();
      await page.getByRole('button', { name: 'Reload sample' }).click();
      await page.getByRole('heading', { name: saved.bay_name, exact: true }).waitFor();
      await page.getByText('Sample · Saved analysis', { exact: true }).waitFor();
    }
    await page.getByRole('button', { name: 'Open photo zoom' }).click();
    const photo = page.getByRole('dialog', { name: 'Full-resolution shelf photo' });
    await photo.waitFor();
    await page.getByRole('button', { name: 'Zoom in', exact: true }).click();
    assert.equal(await photo.getByText('150%', { exact: true }).count(), 1);
    await page.getByRole('button', { name: 'Zoom out', exact: true }).click();
    await page.keyboard.press('Escape');
    assert.equal(await photo.isVisible(), false);
    await page.getByRole('button', { name: 'Recognition & accuracy' }).click();
    const accuracy = page.getByRole('dialog', { name: 'Recognition & accuracy' });
    await accuracy.getByText('A closer look at every section', { exact: true }).waitFor();
    assert.doesNotMatch(await page.locator('body').innerText(), /Claude|Opus|Gemini/i);
    await page.keyboard.press('Escape');
    assert.equal(await accuracy.isVisible(), false);
    // Confirming a task must not inflate the observed percentage or write inventory.
    const coverage = page.getByText(`${result.metrics.planogram_compliance_pct}%`, { exact: true });
    await page.getByRole('button', { name: 'Confirm physical count and record check' }).first().click();
    await coverage.waitFor();
    await page.getByRole('button', { name: 'Reviewed (1)' }).click();
    await page.getByText('Reviewed in this demo session', { exact: true }).waitFor();
    await page.getByRole('button', { name: 'Reload sample' }).click();
    await page.getByRole('button', { name: 'All Checks' }).click();
    await page.locator('summary').click();
    await page.getByRole('button', { name: /The Lord of the Rings/ }).first().click();
    await page.getByRole('button', { name: 'Close title details' }).waitFor();
    await page.getByRole('button', { name: 'Close title details' }).click();
    await page.locator('summary').click();
    for (const [name, width, height] of [['desktop', 1440, 1000], ['tablet', 1024, 900], ['mobile', 390, 844]]) {
      await page.setViewportSize({ width, height });
      await page.evaluate(() => window.scrollTo(0, 0));
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, `${name} has horizontal overflow`);
      await page.screenshot({ path: path.join(root, `qa/screenshots/accuracy_${name}.png`), fullPage: true });
    }
    console.log('PASS real app: all six bays, saved replies, zoom, modal, review/reset, desktop/tablet/mobile');

    // Exercise live UI behavior with deterministic network fixtures, never paid calls.
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.unroute('**/token');
    await page.route('**/token', route => route.fulfill({ json: { email: 'test@company.invalid', token: 'mock-browser-token' } }));
    await page.route('**/api/health', route => route.fulfill({ json: health }));
    await page.reload();
    await page.getByRole('combobox', { name: 'Scan mode' }).selectOption('live');
    let requested;
    const live = { ...result, mode: 'live', inference_duration_seconds: 12.5, tokens_used: 240, harness: { tile_count: 1, calls_completed: 2, rotated_verification: true },
      shelf_items: result.shelf_items.map((item, index) => ({ ...item, verification_status: 'verified', box_source: 'model_estimate', box: index === 0 ? { top: .2, left: .1, width: .3, height: .4 } : null })) };
    await page.route('**/api/scan/stream', route => {
      requested = route.request().postDataJSON();
      assert.equal(route.request().headers().authorization, 'Bearer mock-browser-token');
      const events = [{ step: 1, status: 'reading', message: 'Reading section 1' }, { step: 2, status: 'verifying', message: 'Verifying rotated section 1' }, { step: 4, status: 'complete', result: live }];
      return route.fulfill({ contentType: 'text/event-stream', body: events.map(e => `data: ${JSON.stringify(e)}\n\n`).join('') });
    });
    await page.getByRole('button', { name: 'Analyze again', exact: true }).click();
    await page.getByText('Sample · New analysis', { exact: true }).waitFor();
    assert.equal(await page.getByRole('button', { name: 'All', exact: true }).isDisabled(), false);
    await page.getByRole('button', { name: 'All', exact: true }).click();
    await page.getByRole('button', { name: `${live.shelf_items[0].title}: ${live.shelf_items[0].status_label}` }).click();
    await page.getByRole('button', { name: 'Close title details' }).click();
    assert.deepEqual(requested, { bay_id: 'bay_f3', mode: 'live' });
    await page.unroute('**/api/scan/stream');
    await page.route('**/api/scan/stream', route => route.fulfill({ status: 503, json: { detail: 'Provider unavailable: test fixture' } }));
    await page.getByRole('button', { name: 'Analyze again', exact: true }).click();
    await page.getByRole('alert').filter({ hasText: 'currently unavailable' }).waitFor();
    await page.getByText('Sample · New analysis', { exact: true }).waitFor();
    await page.unroute('**/api/scan/stream');
    await page.route('**/api/scan/stream', async route => {
      await new Promise(resolve => setTimeout(resolve, 1200));
      await route.fulfill({ contentType: 'text/event-stream', body: `data: ${JSON.stringify({ step: 4, status: 'complete', result: live })}\n\n` }).catch(() => {});
    });
    await page.getByRole('button', { name: 'Analyze again', exact: true }).click();
    await page.getByRole('button', { name: 'Cancel scan' }).click();
    await page.getByRole('button', { name: 'Analyze again', exact: true }).waitFor();
    await page.getByRole('button', { name: 'Analyze again', exact: true }).click();
    await page.getByRole('button', { name: 'Upload a photo', exact: true }).click();
    await page.getByRole('button', { name: 'Explore a sample' }).click();
    await page.getByRole('combobox', { name: 'Shelf bay' }).selectOption('bay_a1');
    await page.getByText('Sample · Saved analysis', { exact: true }).waitFor();
    await page.waitForTimeout(1400);
    assert.equal(await page.getByText('Sample · Saved analysis', { exact: true }).count(), 1);
    assert.doesNotMatch(await page.locator('body').innerText(), /Claude|Opus|Gemini/i);
    assert.deepEqual(errors, []);
    console.log('PASS mocked live UI: request, completion, explicit failure, retained result, cancellation, stale-result protection');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
