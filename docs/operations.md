# Collection and operations

The checked-in workflow runs every 30 minutes on `main` and can also be dispatched manually. Publication is gated by the `GO_LIVE_APPROVED` repository variable and the `production` environment; see the schedule section below.

## Source registry and Git-managed corrections

Read `config/sources.json` to find each source's stable ID, canonical URL, capability, and collection method. A source being registered does not mean it has a working offer parser. Preserve unsupported and historical sources as monitoring leads rather than advertising them as freshly checked. GitHub lists and roundups can discover candidates; they do not independently confirm a linked vendor's current price or coupon.

Review `config/taxonomy.json` when assigning one product-type category and independent security topics. Maintain offer corrections and exclusions in `config/overrides.json`, following the schema and examples present in that file. Do not guess override field names or add an admin endpoint. Every policy change should be an ordinary reviewed code/configuration change on `main`, with a regression test. Overrides cannot justify fabricating absent evidence or making a checkout-tested claim.

When adding a parser, confirm the source permits the proposed access method and that it works without login, CAPTCHA bypass, paid APIs, proxy services, or a browser farm. Prefer supported feeds, structured public pages, and conditional requests. Register the parser's actual capability; record unsupported sources honestly. Add fixtures clearly marked as test-only and test representative good, absent, expired, and malformed evidence. Never copy fixture offers into live state.

### Adding a vendor with structured data (no new parser)

Many vendor campaign pages describe their products with schema.org `Offer` data in `<script type="application/ld+json">`. The `structured_offers` adapter publishes those offers from configuration alone. To add a vendor:

1. Confirm the vendor's own page is a 2026 campaign page: its `<h1>` must name Black Friday, Cyber Monday or BFCM together with 2026. Check that robots rules and terms permit fetching it.
2. View the page source and confirm its JSON-LD offers include a `price`. Being on the vendor's 2026 campaign page is what qualifies an offer; prices are not checked against history or a reference. A `priceSpecification` whose `priceType` is `ListPrice` or `StrikethroughPrice` above the price is shown as the crossed-out price; otherwise the offer shows its price alone. An invalid `priceCurrency` is shown as unspecified.
3. Register it in `config/sources.json` with `"type": "official"`, `"adapter": "structured_offers"`, `"capability": "supported"` and a `structured` block, then add its exact hostname to `policy.supported_official_domains`:

   ```json
   "structured": {"vendor": "Vendor name", "category": "training", "topics": ["offensive-security"]}
   ```

   `category` and `topics` must come from `config/taxonomy.json`. Optional `item_types` narrows the schema.org types read (default: Product, Course, SoftwareApplication, WebApplication, MobileApplication, Service, Book, EducationalOccupationalProgram, ProductGroup). Unknown keys and values fail closed.
4. Run `python3 -m collector.run --source SOURCE_ID` and review `state/candidates.json` before merging.

The adapter never reads coupons from structured data. It publishes only offers that link to the vendor's own domain or its subdomains. Offers with no price at all, aggregate price ranges, sold-out items and malformed JSON-LD are kept as candidates. A timezone-aware `validThrough` becomes `ends_at`. A date-only `validThrough` or `priceValidUntil` is shown as the vendor's date and enforced through `expiry_cutoff_at`, the first instant at which that date has passed in every time zone; no exact deadline is invented.

Independently of the adapter, the collector refuses to publish offers from any source that is not `type: official` on a hostname listed in `supported_official_domains`. Registering a new publishing vendor therefore always needs that reviewed two-line change.

Treat network content as hostile data. Keep HTTP(S)-only public-address checks, redirect checks, bounded response sizes, timeouts, retry budgets, per-domain limits, and escaped text rendering. Block local/private/metadata destinations. Honor robots/access restrictions, rate limits, and applicable terms. Do not execute remote scripts, evaluate page markup, or bypass source restrictions. Store only compact evidence excerpts, not full-page archives.

## Manual collection and state

Local commands, from the repository root with Python dependencies installed:

```sh
python3 -m unittest discover -s tests
python3 -m collector.run --output state/snapshot.json
python3 scripts/build.py
python3 scripts/serve.py --port 3000
```

The default run attempts every enabled source (up to 16). Use `--max-sources N` for a smaller run, or use `--source SOURCE_ID` to diagnose one registered source. Limited runs do not prove unvisited sources are healthy. Do not reset timestamps just to make the page look current. A successful fetch is not an offer confirmation; unchanged responses reconfirm evidence only when tied to the previously validated representation.

An owner can also dispatch **Collect and publish** from `main`. Leave `publish` unchecked to collect without publication. Manual publication requires the checked `publish` input, `GO_LIVE_APPROVED=true`, and the `production` environment. The job refuses branch selections other than `main`; it has no PR or push trigger and no privileged `pull_request_target` path.

## Independent data branch

`main` contains reviewed code and initial state. `deals-data` contains only `state/snapshot.json` and optionally `state/history.json`; The workflow uses a fresh temporary Git object store, reads only allowlisted regular JSON blobs, rejects unexpected paths and symlinks, enforces a 10 MiB per-file limit, and never checks out or executes the branch. No downloaded code can replace the current reviewed checkout.

The first data commit is an orphan/root commit built from an empty index, with no copy of main's code and no main parent. Later commits parent the prior data commit. Saving uses an explicit expected-old lease, not an unconditional overwrite; a concurrent human or external writer causes a safe failure. Workflow-level concurrency serializes collection and deployment together with cancellation disabled. GitHub may keep only one pending run in a concurrency group, so do not assume every queued manual request will execute. Data commits cannot loop back into this workflow because it has no push trigger.

Tests and a complete static build must succeed before state is committed. No Actions artifact or cache is used as persistence. The publish job rereads the exact collected commit and rebuilds with the same reviewed code commit, avoiding a branch-head race. The data branch is not trusted executable code; changes to its allowlist or schema require reviewed workflow changes.

Keep evidence compact and bounded. No price history is recorded: each offer carries only the vendor's current price (`price_history` stays an empty list for schema compatibility). Git still retains old commits even when current arrays are bounded: monitor branch size and plan an owner-approved retention/reset procedure if growth becomes material. Do not silently rewrite remote history. Do not add arbitrary `history/` files without first reviewing the workflow's exact allowlist.

## Failure and recovery

Individual source failures retain last-known-good offers with original confirmation timestamps. Explicit withdrawal or expiry removes offers from current results; a transport error alone does not expire them. Unknown or conflicting evidence stays out of automatic publication. The UI marks an offer stale after three hours without confirmation, including when no new collection completes. “Last Check” is not a universal fresh-offer guarantee.

A test or build failure means no new state commit and no publication. A branch-write race means no publication. A Cloudflare publication failure can leave newer state on `deals-data` while the deployed site remains at its prior version. Read the workflow result and deployment version separately. The workflow never switches to paid services, buys capacity, or treats an unsuccessful deployment as success.

To recover, diagnose the source/configuration error, fix code through review, run tests and a local build, and request the next authorized manual collection. An authorized Cloudflare owner may redeploy a previously reviewed known-good version when necessary. Do not delete the data branch as a routine retry: losing state also loses historical discovery and confirmation context. A corrupt or unexpected branch tree causes a visible refusal instead of being silently replaced.

## Collection schedule

The workflow runs at minutes 17 and 47 of every hour on the default branch and can still be dispatched manually. Every run collects, tests, rebuilds and saves validated state to `deals-data`. A run publishes when the repository variable `GO_LIVE_APPROVED` is exactly `true`; manual runs additionally need the `publish` input checked. Scheduled runs have no input, so the variable alone is the publication switch. Set it to `false` to keep collecting without publishing.

For unattended publication the `production` environment must not require manual reviewers, otherwise every scheduled publish waits for approval and queues. Keep its deployment-branch restriction to `main`. The scoped Cloudflare token lives only in that environment.

**Reliable clock (optional).** GitHub's own cron can go hours without firing. `scheduler/` holds a separate, tiny Cloudflare Worker whose cron trigger calls the GitHub workflow-dispatch API at the same minutes. It never serves site traffic (`workers_dev` is off and its fetch handler returns 404). Deploy it once from a machine logged in to Wrangler, with a fine-grained GitHub token scoped to this repository and the single permission Actions: read and write:

```sh
cd scheduler
npx wrangler@4.156.2 secret put GITHUB_TOKEN
npx wrangler@4.156.2 deploy
```

When both clocks fire, the workflow concurrency group runs them one after the other; the duplicate costs about 30 seconds of runner time. Rotate the token before it expires or the Worker's dispatches fail silently in its logs. Remove the Worker with `npx wrangler@4.156.2 delete`.

GitHub schedules are best-effort: they can be delayed or dropped, and public-repository schedules are disabled after 60 days without repository activity. Minutes 17 and 47 avoid the start-of-hour peak but promise no SLA. Keep the manual rerun path and inspect failures. Do not create external monitoring or another scheduler without separate authorization. [1]

An already-open page polls `/data/snapshot.json` every five minutes and on tab focus, and reloads itself when a newer snapshot is published, so visitors see updates without a manual refresh. Stale labels are derived in the browser from each offer's confirmation time, so a stopped schedule becomes visible within three hours.

Standard runners in public repositories are documented as free; larger runners are billed, and artifact/cache storage has separate rules. Keep `ubuntu-latest`, no paid runner labels, no artifact database, and no cache expansion. Provider quotas and policies can change. Failure is preferable to an unapproved upgrade. [2]

## References

[1]: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule "GitHub scheduled workflow behavior"
[2]: https://docs.github.com/en/billing/concepts/product-billing/github-actions "GitHub Actions billing"
