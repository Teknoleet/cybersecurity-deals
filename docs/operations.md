# Collection and operations

The checked-in workflow is **manual-only**. Stage 1 authorizes local review, not external workflow execution, deployment, repository creation, DNS modification, secrets setup, or scheduled jobs. Do not activate any of those while following this document. A later manual collection run is an external action and still needs owner authorization.

## Source registry and Git-managed corrections

Read `config/sources.json` to find each source's stable ID, canonical URL, capability, and collection method. A source being registered does not mean it has a working offer parser. Preserve unsupported and historical sources as monitoring leads rather than advertising them as freshly checked. GitHub lists and roundups can discover candidates; they do not independently confirm a linked vendor's current price or coupon.

Review `config/taxonomy.json` when assigning one product-type category and independent security topics. Maintain offer corrections and exclusions in `config/overrides.json`, following the schema and examples present in that file. Do not guess override field names or add an admin endpoint. Every policy change should be an ordinary reviewed code/configuration change on `main`, with a regression test. Overrides cannot justify fabricating absent evidence or making a checkout-tested claim.

When adding a parser, confirm the source permits the proposed access method and that it works without login, CAPTCHA bypass, paid APIs, proxy services, or a browser farm. Prefer supported feeds, structured public pages, and conditional requests. Register the parser's actual capability; record unsupported sources honestly. Add fixtures clearly marked as test-only and test representative good, absent, expired, and malformed evidence. Never copy fixture offers into live state.

Treat network content as hostile data. Keep HTTP(S)-only public-address checks, redirect checks, bounded response sizes, timeouts, retry budgets, per-domain limits, and escaped text rendering. Block local/private/metadata destinations. Honor robots/access restrictions, rate limits, and applicable terms. Do not execute remote scripts, evaluate page markup, or bypass source restrictions. Store only compact evidence excerpts, not full-page archives.

## Manual collection and state

Local commands, from the repository root with Python dependencies installed:

```sh
python3 -m unittest discover -s tests
python3 -m collector.run --output state/snapshot.json --max-sources 8
python3 scripts/build.py
python3 scripts/serve.py --port 3000
```

Omit `--max-sources 8` for the normal bounded run, or use `--source SOURCE_ID` to diagnose one registered source. Limited runs do not prove unvisited sources are healthy. Do not reset timestamps just to make the page look current. A successful fetch is not an offer confirmation; unchanged responses reconfirm evidence only when tied to the previously validated representation.

Later, an authorized owner can dispatch **Collect and optionally publish** from `main`. Leave `publish` unchecked to collect without publication. Publication requires a checked `publish` input, the exact repository variable value `GO_LIVE_APPROVED=true`, and the configured `production` environment review. The job refuses branch selections other than `main`; it has no PR or push trigger and no privileged `pull_request_target` path.

## Independent data branch

`main` contains reviewed code and initial state. `deals-data` contains only `state/snapshot.json` and optionally `state/history.json`; compact changed-price observations may instead be embedded in the snapshot. The workflow uses a fresh temporary Git object store, reads only allowlisted regular JSON blobs, rejects unexpected paths and symlinks, enforces a 10 MiB per-file limit, and never checks out or executes the branch. No downloaded code can replace the current reviewed checkout.

The first data commit is an orphan/root commit built from an empty index, with no copy of main's code and no main parent. Later commits parent the prior data commit. Saving uses an explicit expected-old lease, not an unconditional overwrite; a concurrent human or external writer causes a safe failure. Workflow-level concurrency serializes collection and deployment together with cancellation disabled. GitHub may keep only one pending run in a concurrency group, so do not assume every queued manual request will execute. Data commits cannot loop back into this workflow because it has no push trigger.

Tests and a complete static build must succeed before state is committed. No Actions artifact or cache is used as persistence. The publish job rereads the exact collected commit and rebuilds with the same reviewed code commit, avoiding a branch-head race. The data branch is not trusted executable code; changes to its allowlist or schema require reviewed workflow changes.

Keep evidence and price observations compact and bounded. Record an observation only when a comparable price changes, not on every fetch; compare the same product, plan, currency, billing period, and scope. Do not turn vendor reference prices into observed history. Git still retains old commits even when current arrays are bounded: monitor branch size and plan an owner-approved retention/reset procedure if growth becomes material. Do not silently rewrite remote history. Do not add arbitrary `history/` files without first reviewing the workflow's exact allowlist.

## Failure and recovery

Individual source failures retain last-known-good offers with original confirmation timestamps. Explicit withdrawal or expiry removes offers from current results; a transport error alone does not expire them. Unknown or conflicting evidence stays out of automatic publication. The UI marks an offer stale after three hours without confirmation, including when no new collection completes. “Last Check” is not a universal fresh-offer guarantee.

A test or build failure means no new state commit and no publication. A branch-write race means no publication. A Cloudflare publication failure can leave newer state on `deals-data` while the deployed site remains at its prior version. Read the workflow result and deployment version separately. The workflow never switches to paid services, buys capacity, or treats an unsuccessful deployment as success.

To recover, diagnose the source/configuration error, fix code through review, run tests and a local build, and request the next authorized manual collection. An authorized Cloudflare owner may redeploy a previously reviewed known-good version when necessary. Do not delete the data branch as a routine retry: losing state also loses historical discovery and confirmation context. A corrupt or unexpected branch tree causes a visible refusal instead of being silently replaced.

## Future hourly schedule: documentation only

No schedule is enabled now. After explicit authorization for recurring collection, review a workflow change on `main` that adds the following event alongside `workflow_dispatch`:

```yaml
# Example for a future reviewed change only — NOT active configuration.
on:
  workflow_dispatch:
    inputs:
      publish:
        type: boolean
        default: false
  schedule:
    - cron: '17 * * * *'
```

Adding this snippet alone will **not** make the current jobs run on schedule: their guards deliberately require `workflow_dispatch`. That future change must also review both job conditions, define whether scheduled runs may publish, and maintain the `GO_LIVE_APPROVED` check and `production` protections. Scheduled runs do not have a manual publish input. Make the scheduled publication rule explicit rather than treating a missing input as permission. Do not remove all event guards just to get a green run.

GitHub schedules use the default branch and are best-effort: they can be delayed or dropped, and public-repository schedules are disabled after 60 days without repository activity. Minute 17 avoids the start-of-hour peak but promises no hourly SLA. Keep the manual rerun path and inspect failures. Do not create external monitoring or another scheduler without separate authorization. [1]

Standard runners in public repositories are documented as free; larger runners are billed, and artifact/cache storage has separate rules. Keep `ubuntu-latest`, no paid runner labels, no artifact database, and no cache expansion. Provider quotas and policies can change. Failure is preferable to an unapproved upgrade. [2]

## References

[1]: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule "GitHub scheduled workflow behavior"
[2]: https://docs.github.com/en/billing/concepts/product-billing/github-actions "GitHub Actions billing"
