import test from 'node:test';
import assert from 'node:assert/strict';
import { dispatch } from './index.js';

const env = { GITHUB_REPO: 'Teknoleet/cybersecurity-deals', WORKFLOW_FILE: 'collect.yml', GITHUB_TOKEN: 'secret' };

test('dispatches the publish run on main with the token', async () => {
  let seen;
  const status = await dispatch(env, async (url, init) => { seen = { url, init }; return { status: 204 }; });
  assert.equal(status, 204);
  assert.equal(seen.url, 'https://api.github.com/repos/Teknoleet/cybersecurity-deals/actions/workflows/collect.yml/dispatches');
  assert.equal(seen.init.headers.Authorization, 'Bearer secret');
  assert.deepEqual(JSON.parse(seen.init.body), { ref: 'main', inputs: { publish: 'true' } });
});

test('non-204 is an error, not a silent skip', async () => {
  await assert.rejects(dispatch(env, async () => ({ status: 401 })), /HTTP 401/);
});
