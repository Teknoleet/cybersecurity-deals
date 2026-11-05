# Cloudflare Workers Static Assets: later activation

This is a deployment handoff, **not authorization to deploy**. Stage 1 ends with local review. Do not create an account resource, repository, token, environment, recurring job, or DNS record merely because these instructions exist. No payment method or paid upgrade is required by this design. If an account setup screen requires payment or a paid plan, stop and resolve that requirement with the owner rather than accepting it.

## Prepared configuration

`wrangler.jsonc` names the application `cybersecurity-deals`, sets compatibility date `2026-11-03`, and serves `./dist` with `not_found_handling: "404-page"`. There is no `main` script, Worker binding, database, route, custom domain, or scheduled trigger. The build must supply `dist/404.html`. Assets-only deployments do not need an application server. The files are also portable to another conventional static host. [1] [2]

Keep the intended canonical origin `https://deals.teknoleet.com` consistent with the reviewed build output. It is an intended origin, not a configured route. A later temporary `workers.dev` URL should not accidentally replace intended canonical links in production metadata. Test `/`, `/sources/`, `/methodology/`, static JSON, cache headers, and a nonexistent path before approving public use.

## Required owner decisions after local approval

1. Approve public publication and identify the actual public GitHub repository and Cloudflare account. No repository URL is assumed here. Put reviewed code on `main`, make it the default branch, and protect it against unreviewed changes.
2. Confirm the Cloudflare account remains on its Free plan. Do not enable paid Workers, hosted Workers Builds, Pages Git builds, R2, KV, D1, paid add-ons, or automatic upgrades. The workflow uploads static files directly from GitHub Actions; Cloudflare-hosted builds are unnecessary.
3. Create a GitHub environment named `production` and restrict its deployment branches to `main`. Do not add required reviewers if you want the schedule to publish unattended; a reviewer requirement makes every scheduled publish wait for approval.
4. Only with deployment authorization, create a scoped Cloudflare API token and put its value in the `production` environment secret `CLOUDFLARE_API_TOKEN`. Store the selected account's ID as environment secret `CLOUDFLARE_ACCOUNT_ID`. Do not paste either value into source, chat, logs, screenshots, or documentation. Revoke exposed tokens immediately.
5. Only after review, set repository Actions variable `GO_LIVE_APPROVED` to the exact string `true`. From then on every scheduled run publishes; set it back to `false` to keep collecting without publishing.

Cloudflare's official CI guide documents the token and account-ID environment variables. Start from its Workers token guidance, then remove unrelated permissions and scope access to only the target account. For this assets-only deployment, use account-level **Workers Scripts: Edit** with the selected account resource. Do not grant all accounts, Global API Key access, DNS Edit, Zone Edit, Workers Routes Edit, billing access, or unrelated storage permissions. If the API reports an additional permission as required, stop and review the exact documented minimum rather than broadening the token blindly. The usual Workers token scope is account-level, not a promise of restriction to one Worker. Choose a practical expiration and rotate it. [3]

## Manual first publication, only after approval

In the chosen repository's Actions tab, select **Collect and publish**, choose branch `main`, and initially leave `publish` unchecked. A successful collection tests reviewed code, restores prior data safely, collects bounded public sources, rebuilds, and writes a data-only `deals-data` commit. It does not upload an artifact or publish a site. Review the source health and resulting data.

For a separately approved publication, run the same workflow from `main` with `publish` checked. Publication also requires `GO_LIVE_APPROVED == 'true'`. The `publish` job is attached to the `production` environment and therefore waits for its configured reviewers. It rebuilds using the exact saved state commit and the same code commit as collection, then runs this pinned deployment command:

```sh
# Reference only. This command publishes; do not run during Stage 1.
npm exec --yes --package=wrangler@4.156.2 -- wrangler deploy --config wrangler.jsonc
```

The workflow uses Node 22 only to execute Wrangler. The app has no Node backend or npm project dependency. Cloudflare credentials exist only in the deployment step; collection has no Cloudflare credentials. Do not run `wrangler login`, `wrangler deploy`, or a hosted-build setup flow during local review.

Wrangler `4.156.2` was verified as a published npm release during preparation. Official action tag commits were resolved from the upstream repositories: checkout `v7.0.1`, setup-python `v7.1.0`, and setup-node `v7.1.0`. The workflow pins full commit SHAs, not moving tags. Review and verify updates deliberately. Wrangler's top-level version is fixed; npm still resolves its transitive package tree because this dependency-free app does not include a deployment-tool lockfile. If stronger reproducibility is needed, review a separate locked deployment-tools directory before activation. [4] [5] [6] [7]

## Custom domain is a separate authorized step

The configuration does not install routes or custom domains. After the owner has explicitly approved the target account, a successful first publication, and the DNS change, an account administrator can attach `deals.teknoleet.com` as a Worker Custom Domain using Cloudflare's supported process. Check existing records first and do not overwrite another service. Keep the CI token without DNS-edit permissions; domain setup is an owner-controlled action. A Cloudflare-managed zone and its prerequisites must be confirmed before making the change. [8]

After the custom domain is active, check HTTPS, redirects, canonical links, metadata, real 404 status, JSON freshness headers, and source timestamps on the actual origin. The root config intentionally does not disable `workers.dev` in advance; decide whether to retain that public endpoint only during the approved routing review. Setting `GO_LIVE_APPROVED` back to `false` stops future workflow publication but does not unpublish an existing Worker or reverse DNS changes.

## Free-tier limits and failure handling

Cloudflare currently documents static-asset requests as free and unlimited, and asset storage without an additional charge. This does not make all Cloudflare features free; Worker execution, additional services, and account changes have their own pricing and limits. Standard GitHub-hosted runners in public repositories are free; larger runners and other storage choices have different billing. This project uses only `ubuntu-latest`, no uploaded artifacts, and no Actions cache. Check current limits before activation and keep paid upgrades disabled. [9] [10]

Validation failure stops before a data commit. A data commit followed by a failed publication does not mean the site was updated: the previous successful deployment remains authoritative. Retain its version so an owner can redeploy a known-good version after review. Do not pay for capacity or automatically switch providers to repair a failed run. An open browser derives stale labels from last offer confirmation, so a stopped collector must not continue looking fresh.

## References

[1]: https://developers.cloudflare.com/workers/static-assets/get-started/ "Cloudflare static-site deployment"
[2]: https://developers.cloudflare.com/workers/static-assets/routing/advanced/html-handling/ "Cloudflare HTML handling"
[3]: https://developers.cloudflare.com/workers/ci-cd/external-cicd/github-actions/ "Cloudflare external CI with GitHub Actions"
[4]: https://registry.npmjs.org/wrangler/4.156.2 "Published Wrangler 4.156.2 metadata"
[5]: https://github.com/actions/checkout/releases/tag/v7.0.1 "Official checkout release"
[6]: https://github.com/actions/setup-python/releases/tag/v7.1.0 "Official setup-python release"
[7]: https://github.com/actions/setup-node/releases/tag/v7.1.0 "Official setup-node release"
[8]: https://developers.cloudflare.com/workers/configuration/routing/custom-domains/ "Cloudflare Worker Custom Domains"
[9]: https://developers.cloudflare.com/workers/static-assets/billing-and-limitations/ "Cloudflare Static Assets billing and limitations"
[10]: https://docs.github.com/en/billing/concepts/product-billing/github-actions "GitHub Actions billing"
