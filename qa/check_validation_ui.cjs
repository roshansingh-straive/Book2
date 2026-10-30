/* Regression for the office screenshot. Uses real local upload/comparison APIs;
   company authentication and paid inference are blocked. */
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const { execFileSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
const url = process.env.SHELF_CHECK_URL || 'http://127.0.0.1:8890';
const python = process.env.PYTHON || path.join(root, process.platform === 'win32' ? '.venv/Scripts/python.exe' : '.venv/bin/python');
(async () => {
  const browser = await chromium.launch({ headless: true, ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}) });
  try {
    const page = await browser.newPage({ viewport: { width: 1600, height: 1050 } });
    const errors = [];
    let inferenceCalls = 0;
    page.on('pageerror', error => errors.push(error.message));
    await page.route('**/token', route => route.fulfill({ json: {} }));
    await page.route('**/api/scan/stream', route => { inferenceCalls++; return route.abort(); });
    const response = await page.request.post(`${url}/api/uploads?filename=validation-shelf.jpg`, {
      headers: { 'Content-Type': 'image/jpeg' }, data: fs.readFileSync(path.join(root, 'app/public/photos/e.jpg')),
    });
    assert.equal(response.status(), 201);
    const photo = await response.json();
    // Create deterministic, independently agreed text with deliberately uncertain
    // boxes. Only test input is simulated; comparison and persistence are real.
    execFileSync(python, ['-c', `
import json,sys
from server.main import get_store
from server.comparison import compare_books
from server.recognition import merge_readings
from server.uploads import save_analysis
photo=json.loads(sys.argv[1]); store=get_store()
bay=next(b for b in store['bays'] if b['id']=='bay_m1')
observations=[]
for title,author in [('Before I Go to Sleep','S.J. Watson'),('Speaking for Myself','Cherie Blair'),('Brilliance of the Moon','Lian Hearn')]:
 for phase in ['read','verify']:
  observations.append(dict(title=title,author=author,visible_text=title,uncertain=False,box=None,tile_id='fixture',**{'pass':phase}))
result=dict(bay_id=bay['id'],bay_name=bay['name'],bay_code=bay['code'],photo_url=photo['photo_url'],photo_filename=photo['filename'],upload_id=photo['upload_id'],source_kind='upload',mode='live',model='fixture',effort='high',run_id='validation-ui-fixture',scanned_at=None,inference_duration_seconds=None,tokens_used=None,estimated_cost_usd=None,**compare_books(store,bay,merge_readings(observations)))
save_analysis(photo['upload_id'],bay['id'],result)
`, JSON.stringify(photo)], { cwd: root });
    await page.goto(`${url}/analysis?bay=bay_m1&upload=${photo.upload_id}`);
    await page.getByRole('button', { name: 'Continue with saved samples' }).click();
    await page.getByText('Your photo · Analysis complete', { exact: true }).waitFor();
    await page.getByText('Check the selected comparison shelf', { exact: true }).waitFor();
    await page.getByRole('button', { name: 'Compare with suggested shelf' }).click();
    await page.waitForURL(new RegExp(`bay=bay_f1&upload=${photo.upload_id}`));
    await page.getByText('Your photo · Analysis complete', { exact: true }).waitFor();
    assert.equal(await page.getByText('Check the selected comparison shelf', { exact: true }).count(), 0);
    await page.locator('summary').click();
    await page.getByRole('button', { name: /^Before I Go to Sleep/ }).click();
    await page.getByText('Location unconfirmed · title retained', { exact: true }).waitFor();
    await page.getByText('Title matched', { exact: true }).waitFor();
    assert.equal(await page.getByRole('button', { name: 'All', exact: true }).isDisabled(), true, 'Uncertain boxes must not become misleading outlines');
    await page.getByRole('button', { name: /^Not confirmed/ }).click();
    assert.equal(await page.locator('article').filter({ hasText: 'Before I Go to Sleep' }).count(), 0, 'Identified title must not also appear missing');
    await page.getByText(/3 location estimates are unavailable or unconfirmed/).waitFor();
    await page.getByRole('button', { name: 'All Checks', exact: true }).click();
    assert.equal(await page.locator('article').filter({ hasText: 'Before I Go to Sleep' }).count(), 0, 'Location-only uncertainty must not create a separate per-book issue');
    await page.getByRole('button', { name: 'Confirm shelf and backroom check' }).first().click();
    await page.getByRole('button', { name: 'Reviewed (1)' }).click();
    await page.getByText('Reviewed in this demo session', { exact: true }).waitFor();
    await page.getByRole('button', { name: 'All Checks', exact: true }).click();
    for (const [name,width,height] of [['desktop',1600,1050],['tablet',1024,900],['mobile',390,844]]) {
      await page.setViewportSize({ width,height });
      await page.evaluate(() => window.scrollTo(0,0));
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, `${name} overflow`);
      await page.screenshot({ path: path.join(root,`qa/screenshots/validation_${name}.png`),fullPage:true });
    }
    await page.reload();
    await page.getByText('Your photo · Analysis complete', { exact: true }).waitFor();
    assert.equal(new URL(page.url()).searchParams.get('upload'), photo.upload_id);
    // Replay the actual recorded public-image replies through current matching.
    // This is postprocessing of stored output, never another model request.
    const recorded = JSON.parse(execFileSync(python, ['-c', `
import json,sys
from pathlib import Path
from server.main import get_store
from server.comparison import compare_books
from server.recognition import reprocess_audit
from server.uploads import save_analysis
photo=json.loads(sys.argv[1]); store=get_store(); bay=next(b for b in store['bays'] if b['id']=='bay_f1')
fixture=json.loads(Path('qa/fixtures/live_e_replies.json').read_text())
result=dict(bay_id=bay['id'],bay_name=bay['name'],bay_code=bay['code'],photo_url=photo['photo_url'],photo_filename='recorded-public-shelf.jpg',upload_id=photo['upload_id'],source_kind='upload',mode='live',model='recorded-fixture',effort='high',run_id='recorded-public-fixture',scanned_at=None,inference_duration_seconds=None,tokens_used=None,estimated_cost_usd=None,**compare_books(store,bay,reprocess_audit(fixture['audit'])))
save_analysis(photo['upload_id'],bay['id'],result)
print(json.dumps(dict(count=len(result['shelf_items']),metrics=result['metrics'])))
`, JSON.stringify(photo)], { cwd: root, encoding: 'utf8' }));
    await page.setViewportSize({width:1600,height:1050});
    await page.reload();
    await page.getByText(`${recorded.count} title candidates`, {exact:true}).waitFor();
    await page.locator('summary').first().click();
    const candidates = page.locator('details').first();
    assert.equal(await candidates.getByRole('button', {name:/^JOHN GRISHAM(?:\s|$)/i}).count(),0);
    assert.equal(await candidates.getByRole('button', {name:/^Unknown Title(?:\s|$)/i}).count(),0);
    await candidates.getByRole('button', {name:/^Leading(?:\s|$)/}).click();
    await page.getByText('Title matched',{exact:true}).waitFor();
    await candidates.getByRole('button', {name:/^Speaking for Myself(?:\s|$)/}).click();
    await page.getByText('Title agreed across two readings',{exact:true}).waitFor();
    await page.getByText(/Combined readings:.*the autobiography/).waitFor();
    await page.evaluate(() => window.scrollTo(0,0));
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    await page.screenshot({path:path.join(root,'qa/screenshots/live_run_reprocessed.png'),fullPage:true});
    console.log(`PASS recorded run UI: ${recorded.metrics.matched_count} confirmed catalogue matches; author-only text excluded; subtitle aliases combined; uncertainty retained`);
    const single = JSON.parse(execFileSync(python, ['-c', `
import json,sys
from pathlib import Path
from server.main import get_store
from server.comparison import compare_books
from server.recognition import reprocess_audit
from server.uploads import save_analysis
photo=json.loads(sys.argv[1]); store=get_store(); bay=next(b for b in store['bays'] if b['id']=='bay_f1')
fixture=json.loads(Path('qa/fixtures/live_e_replies.json').read_text())
result=dict(bay_id=bay['id'],bay_name=bay['name'],bay_code=bay['code'],photo_url=photo['photo_url'],photo_filename='recorded-first-pass.jpg',upload_id=photo['upload_id'],source_kind='upload',mode='live',model='fixture',effort='high',run_id='single-pass-fixture',scanned_at=None,inference_duration_seconds=None,tokens_used=None,estimated_cost_usd=None,**compare_books(store,bay,reprocess_audit(fixture['audit'],first_pass_only=True),reading_mode='single_pass'))
save_analysis(photo['upload_id'],bay['id'],result)
print(json.dumps(dict(count=len(result['shelf_items']),metrics=result['metrics'])))
`, JSON.stringify(photo)], {cwd:root,encoding:'utf8'}));
    await page.reload();
    await page.getByText('Single-pass analysis · No rotated reread · Locations are estimates',{exact:true}).waitFor();
    await page.getByText(`${single.count} title candidates`,{exact:true}).waitFor();
    await page.getByText('Single reading · Catalogue matches have not been independently verified.',{exact:true}).waitFor();
    await page.locator('summary').first().click();
    await page.locator('details').first().getByRole('button',{name:/^Leading(?:\s|$)/}).click();
    await page.getByText('Catalogue matched',{exact:true}).waitFor();
    await page.getByText('Single reading · Not independently verified',{exact:true}).waitFor();
    assert.equal(await page.getByText('Title agreed across two readings',{exact:true}).count(),0);
    assert.equal(single.metrics.independent_verified_count,0);
    assert.doesNotMatch(await page.locator('body').innerText(), /across both readings/);
    await page.getByRole('button',{name:'All',exact:true}).click();
    await page.getByRole('button',{name:'Off',exact:true}).click();
    await page.evaluate(() => window.scrollTo(0,0));
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    await page.screenshot({path:path.join(root,'qa/screenshots/single_pass_recorded.png'),fullPage:true});
    console.log(`PASS recorded first pass UI: ${single.metrics.matched_count} catalogue matches; no independent verification claimed; no new inference`);
    assert.equal(inferenceCalls, 0, 'Correction and reload must not start paid inference');
    assert.doesNotMatch(await page.locator('body').innerText(), /Gemini|Claude|Opus|Missing \/ OOS/i);
    assert.deepEqual(errors, []);
    console.log('PASS validation regression: correct titles retained, wrong-shelf suggestion, real recompare without inference, no duplicate missing alert, uncertain boxes hidden, review does not inflate coverage, responsive layouts, refresh');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode=1; });
