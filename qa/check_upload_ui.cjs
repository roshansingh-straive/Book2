/* Browser integration: real local photo upload; recognition responses are mocked. */
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const url = process.env.SHELF_CHECK_URL || 'http://127.0.0.1:8888';
const base = JSON.parse(fs.readFileSync(path.join(root, 'app/public/data/scans/bay_f3.json')));
const names = /Claude|Opus|Gemini|ANTHROPIC_API_KEY/i;
const health = enabled => ({ upload_analysis_available: enabled, live_available_by_difficulty: { easy: enabled, medium: enabled, hard: enabled } });
(async () => {
  const browser = await chromium.launch({ headless: true, ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}) });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    // No test is ever permitted to reach a paid recognition endpoint.
    await page.route('**/api/scan/stream', route => route.fulfill({ status: 503, json: { detail: 'Live recognition unavailable' } }));
    await page.route('**/api/health', route => route.fulfill({ json: health(false) }));
    await page.route('**/token', route => route.fulfill({ json: {} }));
    await page.goto(url);
    await page.getByRole('button', { name: 'Continue with saved samples' }).click();
    await page.getByRole('heading', { name: /A clear picture/ }).waitFor();
    await page.getByLabel('Shelf to check').selectOption('bay_f3');
    assert.equal(await page.getByRole('button', { name: 'Analyze shelf', exact: true }).isDisabled(), true);
    assert.doesNotMatch(await page.locator('body').innerText(), names);
    for (const [name, width, height] of [['desktop', 1440, 1000], ['mobile', 390, 844]]) {
      await page.setViewportSize({ width, height });
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, `${name} home overflow`);
      await page.screenshot({ path: path.join(root, `qa/screenshots/home_${name}.png`), fullPage: true });
    }
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.getByLabel('Shelf photo', { exact: true }).setInputFiles({ name: 'invalid.txt', mimeType: 'text/plain', buffer: Buffer.from('not a photo') });
    await page.getByRole('alert').filter({ hasText: 'JPG, PNG or WebP' }).waitFor();
    // Exercise the actual drag/drop path using an original local sample image.
    const transfer = await page.evaluateHandle(async () => {
      const blob = await fetch('/photos/c.png').then(response => response.blob());
      const dt = new DataTransfer();
      dt.items.add(new File([blob], 'dropped-shelf.png', { type: 'image/png' }));
      return dt;
    });
    await page.getByRole('group', { name: 'Shelf photo upload' }).dispatchEvent('drop', { dataTransfer: transfer });
    await page.getByAltText('Selected shelf photo preview').waitFor();
    await page.getByRole('button', { name: 'Remove photo' }).click();
    await page.getByAltText('Selected shelf photo preview').waitFor({ state: 'detached' });
    // Selecting the same file again must work after removing it.
    await page.getByLabel('Shelf photo', { exact: true }).setInputFiles(path.join(root, 'app/public/photos/c.png'));
    await page.getByAltText('Selected shelf photo preview').waitFor();
    await page.getByRole('button', { name: 'Analyze shelf', exact: true }).click();
    await page.waitForURL(/\/analysis\?bay=bay_f3&upload=[a-f0-9]{32}$/);
    const uploadId = new URL(page.url()).searchParams.get('upload');
    const photoResponse = await page.request.get(`${url}/api/uploads/${uploadId}`);
    assert.equal(photoResponse.status(), 200);
    const photo = await photoResponse.json();
    assert.equal(photo.filename, 'c.png');
    const sourceImage = await page.request.get(`${url}${photo.photo_url}`);
    assert.deepEqual(await sourceImage.body(), fs.readFileSync(path.join(root, 'app/public/photos/c.png')));
    await page.getByRole('heading', { name: 'Your shelf analysis', exact: true }).waitFor();
    await page.getByText('Your photo · Awaiting analysis', { exact: true }).waitFor();
    await page.getByText('Company sign-in and inference access are required for live photo analysis.').waitFor();
    const displayedImage = page.locator('img', { hasNot: page.locator('dialog img') }).first();
    assert.equal(await displayedImage.getAttribute('src'), photo.photo_url);
    assert.equal(await page.getByText('Your results will appear here', { exact: true }).count(), 1);
    assert.doesNotMatch(await page.locator('body').innerText(), names);
    await page.screenshot({ path: path.join(root, 'qa/screenshots/upload_analysis_pending.png'), fullPage: true });
    await page.reload();
    await page.getByText('Your photo · Awaiting analysis', { exact: true }).waitFor();
    assert.equal(await page.locator('img').first().getAttribute('src'), photo.photo_url);
    // Browser Back returns to the homepage; Forward restores the upload route.
    await page.goBack();
    await page.getByRole('heading', { name: /A clear picture/ }).waitFor();
    await page.goForward();
    await page.getByRole('heading', { name: 'Your shelf analysis', exact: true }).waitFor();
    console.log('PASS real upload flow: homepage, validation, drag/drop, preview/remove, selected shelf, submit, original image, unavailable state, refresh and history');

    // Enable fixture capabilities, then return a fixture analysis for this upload.
    await page.unroute('**/token');
    await page.route('**/token', route => route.fulfill({ json: { email: 'test@company.invalid', token: 'mock-browser-token' } }));
    await page.unroute('**/api/health');
    await page.route('**/api/health', route => route.fulfill({ json: health(true) }));
    await page.unroute('**/api/scan/stream');
    const live = { ...base, source_kind: 'upload', upload_id: uploadId, mode: 'live', photo_filename: photo.filename, photo_url: photo.photo_url, model: 'fixture', run_id: 'ui-fixture', inference_duration_seconds: 3.5 };
    let calls = 0;
    await page.route('**/api/scan/stream', route => {
      calls += 1;
      assert.deepEqual(route.request().postDataJSON(), { bay_id: 'bay_f3', upload_id: uploadId, mode: 'live' });
      assert.equal(route.request().headers().authorization, 'Bearer mock-browser-token');
      return route.fulfill({ contentType: 'text/event-stream', body: `data: ${JSON.stringify({ step: 4, status: 'complete', result: live })}\n\n` });
    });
    await page.reload();
    await page.getByText('Your photo · Awaiting analysis', { exact: true }).waitFor();
    assert.equal(calls, 0, 'Opening an upload must not start paid recognition');
    await page.getByRole('button', { name: 'Analyze photo', exact: true }).click();
    await page.getByText('Your photo · Analysis complete', { exact: true }).waitFor();
    assert.equal(calls, 1, 'One explicit click must start exactly one scan');
    assert.equal(await page.getByRole('combobox', { name: 'Scan mode' }).count(), 0, 'Uploads must never offer replay');
    await page.getByRole('button', { name: 'Recognition & accuracy', exact: true }).click();
    await page.getByRole('dialog', { name: 'Recognition & accuracy' }).waitFor();
    assert.doesNotMatch(await page.locator('body').innerText(), names);
    await page.keyboard.press('Escape');
    await page.route(`**/api/uploads/${uploadId}/analysis/bay_f3`, route => route.fulfill({ json: { result: live } }));
    await page.reload();
    await page.getByText('Your photo · Analysis complete', { exact: true }).waitFor();
    assert.equal(calls, 1, 'Refreshing completed analysis must not repeat recognition');
    await page.unroute('**/api/scan/stream');
    await page.route('**/api/scan/stream', route => route.fulfill({ contentType: 'text/event-stream', body: 'data: {"status":"error","code":"permission","message":"Your Straive account does not have access to this inference route."}\n\n' }));
    await page.getByRole('button', { name: 'Start fresh scan', exact: true }).click();
    await page.getByRole('alert').filter({ hasText: 'does not have access' }).waitFor();
    await page.getByText('Your photo · Analysis complete', { exact: true }).waitFor();
    assert.doesNotMatch(await page.locator('body').innerText(), names);
    await page.unroute('**/api/scan/stream');
    await page.route('**/api/scan/stream', async route => {
      await new Promise(resolve => setTimeout(resolve, 1500));
      await route.fulfill({ contentType: 'text/event-stream', body: `data: ${JSON.stringify({ step: 4, status: 'complete', result: live })}\n\n` }).catch(() => {});
    });
    await page.getByRole('button', { name: 'Start fresh scan', exact: true }).click();
    await page.getByRole('button', { name: 'Cancel scan', exact: true }).click();
    await page.getByRole('alert').filter({ hasText: 'cancelled' }).waitFor();
    await page.getByRole('button', { name: 'Start fresh scan', exact: true }).click();
    await page.getByRole('button', { name: 'Upload a photo', exact: true }).click();
    await page.getByRole('heading', { name: /A clear picture/ }).waitFor();
    await page.waitForTimeout(1700);
    assert.equal(new URL(page.url()).pathname, '/');
    await page.goto(`${url}/analysis?bay=bay_f3&upload=${'a'.repeat(32)}`);
    await page.getByRole('alert').filter({ hasText: 'could not be found' }).waitFor();
    await page.getByRole('button', { name: 'Back to upload', exact: true }).click();
    await page.getByRole('heading', { name: /A clear picture/ }).waitFor();
    assert.deepEqual(errors, []);
    console.log('PASS fixture recognition: one explicit scan, correct upload, hidden model names, no replay, cached refresh, errors, retained result, cancellation and stale-result protection');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
