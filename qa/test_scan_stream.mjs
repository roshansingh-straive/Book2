import assert from 'node:assert/strict';
import { test } from 'node:test';
import { consumeScanEvents } from '../app/src/scanStream.ts';

function response(chunks) {
  return new Response(new ReadableStream({ start(controller) {
    const bytes = new TextEncoder().encode(chunks.join(''));
    // Split inside JSON, event delimiters and multibyte Devanagari characters.
    for (let i = 0; i < bytes.length; i += 7) controller.enqueue(bytes.slice(i, i + 7));
    controller.close();
  } }), { headers: { 'Content-Type': 'text/event-stream' } });
}

test('POST stream handles fragmented UTF-8, CRLF and heartbeats', async () => {
  const events = [];
  await consumeScanEvents(response([
    ': keepalive\r\n\r\n',
    'data: {"step":1,"status":"reading","message":"जादू"}\r\n\r\n',
    'data: {"step":4,"status":"complete","result":{"mode":"live"}}\r\n\r\n',
  ]), event => events.push(event));
  assert.equal(events.length, 2);
  assert.equal(events[0].message, 'जादू');
  assert.equal(events[1].result.mode, 'live');
});

test('provider failure is surfaced without reporting completion', async () => {
  await assert.rejects(consumeScanEvents(response(['data: {"status":"error","message":"Provider failed"}\n\n']), () => assert.fail()), /Provider failed/);
});

test('authentication failures trigger a session refresh callback', async () => {
  let refreshes = 0;
  await assert.rejects(
    consumeScanEvents(
      new Response('{"detail":"Sign in again"}', { status: 401, headers: { 'Content-Type': 'application/json' } }),
      () => {},
      () => { refreshes += 1; },
    ),
    /Sign in again/,
  );
  assert.equal(refreshes, 1);
  await assert.rejects(
    consumeScanEvents(response(['data: {"status":"error","code":"authentication","message":"Session expired"}\n\n']), () => {}, () => { refreshes += 1; }),
    /Session expired/,
  );
  assert.equal(refreshes, 2);
});

test('interrupted connection never counts as a completed scan', async () => {
  await assert.rejects(consumeScanEvents(response(['data: {"step":1,"status":"reading"}\n\n']), () => {}), /ended before completion/);
});

test('completion without a result is rejected', async () => {
  await assert.rejects(consumeScanEvents(response(['data: {"step":4,"status":"complete"}\n\n']), () => {}), /without a result/);
});

test('HTTP failures and unexpected HTML are explicit', async () => {
  await assert.rejects(consumeScanEvents(new Response('{"detail":"Missing credentials"}', { status: 503, headers: { 'Content-Type': 'application/json' } }), () => {}), /Missing credentials/);
  await assert.rejects(consumeScanEvents(new Response('<html>app fallback</html>', { headers: { 'Content-Type': 'text/html' } }), () => {}), /progress stream/);
});
