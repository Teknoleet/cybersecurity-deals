# Cybersecurity Deals — 2026

An account-free, source-transparent directory of cybersecurity and AI-security offers, including VPNs. Python collects supported public evidence and builds portable HTML, JSON, CSS, and browser JavaScript. Search and filters run in the browser. There is no Node.js backend, database, admin interface, checkout verification, or paid API dependency.

**Deployment status.** The intended domain is `deals.teknoleet.com`. Collection runs every 30 minutes from GitHub Actions; publication to Cloudflare is gated by the `GO_LIVE_APPROVED` repository variable and the `production` environment, and DNS is an owner-controlled step. See [operations](docs/operations.md) and the [Cloudflare setup guide](docs/cloudflare.md).

**Current coverage:** Practical DevSecOps publishes automatically from its own 2026 campaign page (individual certifications and certification bundles). Nine further registered lists, trackers and vendor pages are fetched for discovery only and never publish; two are blocked by robots rules and stay unfetched. TrainSec was removed from the registry by owner decision. Read [current coverage](docs/current-coverage.md) for the exact state of each source. Vendors whose 2026 campaign pages publish schema.org offer data can be added by configuration alone through the `structured_offers` adapter; see [operations](docs/operations.md#adding-a-vendor-with-structured-data-no-new-parser).

## Run locally

Use Python 3.12 or newer. Run these commands from the repository root:

```sh
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install --no-cache-dir -r requirements.txt
python3 -m unittest discover -s tests
python3 -m unittest scripts.test_build
python3 scripts/build.py
python3 scripts/check_static.py
python3 scripts/serve.py --port 3000
```

Open `http://localhost:3000`. The build reads `state/snapshot.json` and `config/taxonomy.json` and generates `dist/`. It includes the directory at `/`, source-health information at `/sources/`, methodology at `/methodology/`, a real unknown-route 404 page, and static assets and JSON. `dist/` is generated output, not a database. Do not use a generic single-page-app fallback that turns missing routes into successful home-page responses.

Optional browser-logic checks run with `node --test web/tests/filters.test.mjs`; this is test tooling, not a backend. The default static build displays the review notice and is marked noindex. `python3 scripts/build.py --production` removes those review-only settings, but does not deploy anything or enable collection.

To attempt live public-source collection locally:

```sh
python3 -m collector.run --output state/snapshot.json
# Small diagnostic run (first three enabled sources, no followed links):
python3 -m collector.run --output state/snapshot.json --max-sources 3 --max-links 0
# One registered source; replace SOURCE_ID with an ID from config/sources.json:
python3 -m collector.run --output state/snapshot.json --source SOURCE_ID
python3 scripts/build.py
```

Collection performs bounded network requests and changes local state. A successful process does not mean every source succeeded or every candidate was accepted. Read the snapshot's source health and `/sources/`. Unsupported pages, blocked requests, historical lists, and ambiguous offers are not silently converted into current offers. An empty directory is preferable to invented deals. Fixtures exist only to test code; they must never be displayed as live offers.

## What qualifies

An offer needs either explicit **2026 offer/campaign evidence**, or a credible **original publication date from 1–31 October 2026** on the containing page. An unrelated footer year, year in a course title, or updated 2025 article is not enough. An October roundup can establish date eligibility and identify a lead, but accessible current vendor evidence must support the particular automatically published offer. A November article must qualify through explicit 2026 campaign evidence, not a broadened publication-date exception.

Date eligibility is not proof that an offer remains redeemable. Historical, expired, conflicting, unsupported, and date-ambiguous candidates stay out of current results. Future offers are labeled upcoming. Missing expiry, price, timezone, VAT, or renewal terms remain unknown. The edition stays 2026 until a reviewed lifecycle decision changes it.

Cards distinguish **Vendor-published**, **Marketplace-published**, and **Stale — recheck pending**. These describe evidence, not successful checkout or product endorsement. Original currencies and billing periods are preserved; an advertised crossed-out reference price is not a verified historical baseline. Any lowest-observed claim starts only when comparable tracking began. Third-party book and training bundles identify the seller; software-license offers require established seller authorization.

## Freshness and source limitations

“Last Check” means the latest completed collection, not the last successful confirmation of every offer. Attempt time, successful fetch time, and actual offer-confirmation time are separate. Downloading a page without finding the offer cannot refresh its confirmation. Three hours without successful offer confirmation produces a stale warning, calculated by the browser even if collection has stopped. Routine rechecks do not make unchanged offers look newly discovered.

The source registry is a monitoring and discovery list, not a guarantee that every attached source has an automated parser. Login-only content, CAPTCHAs, inaccessible pages, unsupported markup, source restrictions, and rate limits can prevent collection. We do not bypass them. Source health and parser capability must remain explicit. See [operations](docs/operations.md) for configuration, failure handling, history, and safe parser additions.

## Code, data, and publishing

Reviewed code and configuration live on `main`. A later authorized manual Actions run stores only `state/snapshot.json` and, if used, `state/history.json` on an independent `deals-data` branch. Compact history may also live inside the snapshot. The workflow reads Git blobs from an isolated temporary object store; it never checks out or executes data-branch code. Its first data commit has no code-branch parent. It validates and builds before committing state, and publication uses the exact saved state commit with the same reviewed code commit.

`.github/workflows/collect.yml` runs **every 30 minutes (minutes 17 and 47)** and on manual dispatch. It has no push trigger, PR trigger, artifact database, or Actions cache. Every run collects and saves state without Cloudflare secrets. Publication requires the repository variable `GO_LIVE_APPROVED` equal to the exact string `true` (plus the `publish` checkbox on manual runs) and the separate `production` environment holding the scoped Cloudflare secrets. For unattended hourly publishing, do not add required reviewers to that environment; restrict its deployment branches to `main`.

Cloudflare Workers Static Assets serves the generated directory directly, without a runtime script. Node 22 is used only for the pinned Wrangler deployment tool. Cloudflare-hosted builds, Pages build cycles, managed databases, R2, KV, D1, and visitor-triggered scraping are not required. See the [Cloudflare setup guide](docs/cloudflare.md) for later activation, least-privilege credentials, free-plan caveats, and domain setup boundaries.

## Project files

- `collector/`, `config/`, `schemas/`, and `tests/` contain collection, policy, source capabilities, and tests.
- `web/` and `scripts/` contain templates, browser assets, the Python build, and the local preview server.
- `state/snapshot.json` is normalized current state and source health, with compact observations where implemented.
- `.github/workflows/collect.yml`, `wrangler.jsonc`, and `docs/` drive scheduled collection and static publication; `scheduler/` is an optional Cloudflare cron Worker that dispatches the workflow on a reliable clock.
- `plan.md` and `TODO.md` record the agreed behavior and Stage 1 review outcomes.

## Service-cost boundary

The design targets free services, not an unconditional lifetime cost guarantee. Standard GitHub-hosted runners are free in public repositories; larger runners are not. Cloudflare documents static-asset requests as free and unlimited with no additional asset-storage fee, while Worker-script invocations and other services have separate rules. Provider policies and limits can change. [1] [2]

Do not authorize paid upgrades, paid caches or artifacts, paid APIs, trial-only services, or automatic overages. Keep the future repository public and use standard `ubuntu-latest` runners. If a free limit prevents operation, stop and report the limitation rather than purchasing capacity. Existing domain-registration costs are outside hosting. No license is asserted by this README; choose and review one separately if desired.

## References

[1]: https://docs.github.com/en/billing/concepts/product-billing/github-actions "GitHub Actions billing"
[2]: https://developers.cloudflare.com/workers/static-assets/billing-and-limitations/ "Cloudflare Static Assets billing and limitations"

## License

Code is released under the [MIT License](LICENSE). Bundled fonts carry their own SIL Open Font License files in `web/public/fonts/`. Offer text and prices are vendor claims quoted as evidence and remain the property of their publishers.
