// Dispatches the "Collect and publish" workflow. No site traffic reaches this Worker.
export async function dispatch(env, fetchImpl = fetch) {
  const url = `https://api.github.com/repos/${env.GITHUB_REPO}/actions/workflows/${env.WORKFLOW_FILE}/dispatches`;
  const response = await fetchImpl(url, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${env.GITHUB_TOKEN}`,
      Accept: 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28',
      'User-Agent': 'cybersecurity-deals-scheduler',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ ref: 'main', inputs: { publish: 'true' } }),
  });
  if (response.status !== 204) throw new Error(`dispatch failed: HTTP ${response.status}`);
  return response.status;
}

export default {
  scheduled(_event, env, ctx) { ctx.waitUntil(dispatch(env)); },
  fetch() { return new Response('Not found', { status: 404 }); },
};
