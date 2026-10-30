import assert from 'node:assert/strict';
import { test } from 'node:test';
import { checkFoundrySession, foundryLoginUrl, FOUNDRY_AUTH_ORIGIN } from '../app/src/foundryAuth.ts';

test('session check sends credentialed, non-persistent request to the auth host', async () => {
  let requested;
  const result = await checkFoundrySession(async (url, options) => {
    requested = { url, options };
    return Response.json({ email: 'user@company.test', token: 'transient-token' });
  });
  assert.equal(requested.url, `${FOUNDRY_AUTH_ORIGIN}/token`);
  assert.equal(requested.options.credentials, 'include');
  assert.equal(requested.options.cache, 'no-store');
  assert.equal(result.status, 'signed-in');
  if (result.status === 'signed-in') assert.equal(result.token, 'transient-token');
});

test('empty or tokenless sessions are not treated as signed in', async () => {
  for (const payload of [{}, { email: 'user@company.test' }, { token: 'token' }]) {
    const result = await checkFoundrySession(async () => Response.json(payload));
    assert.equal(result.status, 'signed-out');
  }
});

test('authentication denial differs from connection and response errors', async () => {
  assert.equal((await checkFoundrySession(async () => new Response('', { status: 401 }))).status, 'signed-out');
  assert.equal((await checkFoundrySession(async () => new Response('', { status: 503 }))).status, 'connection-error');
  assert.equal((await checkFoundrySession(async () => new Response('{', { status: 200 }))).status, 'connection-error');
  assert.equal((await checkFoundrySession(async () => { throw new TypeError('network'); })).status, 'connection-error');
});

test('login URL preserves a localhost return URL as the next parameter', () => {
  const returnUrl = 'http://127.0.0.1:8001/analysis?bay=bay_f3&upload=abc123';
  const login = new URL(foundryLoginUrl(returnUrl));
  assert.equal(login.origin, FOUNDRY_AUTH_ORIGIN);
  assert.equal(login.pathname, '/login');
  assert.equal(login.searchParams.get('next'), returnUrl);
});
