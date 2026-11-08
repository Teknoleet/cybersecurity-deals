# Collector implementation status

This file is a dated implementation log. Earlier sections describe the state at the time they were written; the current limits are in `config/sources.json` (`policy`) and `collector/http.py`, and current source coverage is in [docs/current-coverage.md](../docs/current-coverage.md).

The genuine initial `state/snapshot.json` is available now: 33 course-level TrainSec offers corroborated by a fresh first-party extraction of https://trainsec.net/cybersecurity-courses-black-friday/ at **2026-11-03T10:43:50Z**. Each has its own course title and advertised sale/reference price; all are training, including hardware-hacking courses. Currency is null with `$` symbol, expiry is `November 2026 only` and `ends_at` is null. Checkout is not tested. Missing-price and price/percentage-conflicting cards are excluded as candidates.

A finite actual CLI run subsequently completed: `python3 -m collector.run --output state/snapshot.json --source trainsec-black-friday --source github-0x90n --max-sources 2`. TrainSec direct HTTP returned 403 and is honestly `unavailable`; its source automatic `last_successful_fetch_at` remains null and offer confirmations remain **10:43:50Z**, not the run time. The GitHub README was actually fetched and classified historical (2025), publishing no codes or offers. `state/collector-status.json` records run counts and actual completion. Top-level public snapshot keys remain exact; there are no internal top-level fields to strip.

**Persistence:** `state/history.json` contains HTTP validators, bounded representation cache, candidates and reviewed-evidence receipt; keep this alongside `state/snapshot.json`. `state/candidates.json` and `state/reviewed-evidence-receipt.json` are convenience mirrors, not required to preserve cache or evidence. The snapshot is the only frontend offer input. Do not publish history/candidates in static assets. They are safe public-Git data but not public offers. No full fetched HTML or coupon values copied from historical Markdown are persisted.

The CLI supports repeatable `--source ID` and comma-separated IDs; default max sources is 16 (8 when this was first written), max followed links 4. At the time, only TrainSec official parsing and the 0x90n master Markdown discovery were enabled. Canonical source `url` remains unchanged in the registry/public state; GitHub's raw endpoint is the separate `fetch_url` registry key. Other explicit source URLs and the names-only watchlist are intentionally unsupported/discovery-only, not claimed live coverage.

Pinned installed Jinja2 3.1.6 and MarkupSafe 3.0.4 were added for the parent's builder. **Completed validation:** `python3 -m unittest discover -s tests -v` passed all **56 tests** in 0.708 seconds; `pyright collector tests` reports **0 errors, 0 warnings**. `python3 -m compileall -q collector tests` also passed. Logs are in `state/tests.log`, `state/python-diagnostics.log` and `state/live-collection.log`.

The final bounded live run completed at **2026-11-03T10:53:56Z** using **4 HTTP requests**: 1 source successful (historical GitHub), 1 failed (TrainSec 403), 33 genuine previously corroborated offers retained with **10:43:50Z unchanged**. The unavailable TrainSec source note explicitly explains that the retained observation was a reviewed first-party research extraction, not successful automated HTTP. No commits, publication, DNS, recurring jobs, new repositories, secrets or paid service operations were performed.

## Operational limitations

Robots policies are cached in memory per origin for each finite run. Network/403/5xx/redirect/HTML responses for robots fail closed; 404/410 is treated as an explicitly absent policy. Crawl delay/request-rate directives are honored within the global time budget. No retry, environment proxy, cookies, authentication, browser/CAPTCHA bypass or automatic research-tool fallback is used. DNS answers are validated and socket connections are pinned to numerical public addresses while TLS retains hostname validation. Requests are bounded to 2 MiB decoded content, 3 redirects, 48 requests total and 12 per domain, with 4s connect / 7s read timeouts and a 180s collection budget (24 requests and 95s before the 4 November coverage expansion). Blocking OS DNS resolution is subject to the host resolver's own timeout; the budget cannot interrupt a stuck system resolver.

Conditional ETag/Last-Modified state is private to browser output in `history.json`. A 304 is accepted only for the registered URL, adapter version, exact final response URI (including path and query), validated representation hash and normalized-data digest; bare, tampered, mismatched-target or conflicting-entity-tag 304s cannot refresh offers. No full body cache is required. Missing expiry remains unknown; the explicit November-only campaign is conservatively excluded once November has ended in every timezone, without fabricating an exact `ends_at` or vendor timezone. The directory is not comprehensive: all other registry sources need maintained parsing/evidence review before offers can publish.

## Read-only review fixes

A focused independent implementation review found two medium edge cases, both corrected. Conditional validators now bind to the actual final response URI, preserving path, trailing slash and query; redirects to a different resource drop validators, and cache version 2 invalidates older records. Stale future offers keep an always-visible “Upcoming · Recheck pending” status, independently of source freshness. Four offline HTTP-identity regressions, one browser status regression, and one server-rendered badge regression were added. Collector tests now total 60; browser tests 8; builder tests 8. No new network collection or publication was needed to verify these fixes.

## Coverage expansion, 4 November 2026

A second official adapter, `practical_devsecops`, publishes individual certification cards from the vendor's 2026 Black Friday article; bundles and "Coming Soon" courses are candidates. A generic `html_discovery` adapter records headings, declared publication dates and outbound links from roundups, trackers and vendor pages without an offer parser; it never publishes. Two more GitHub lists use the existing Markdown adapter. TrainSec's registered URL moved to the vendor's 2026 campaign path, which answers the unchanged collector user agent, so its 33 offers are now confirmed by automated HTTP. Default budgets rose to 16 sources, 48 requests and 180 seconds to cover the whole registry in one run. The live run at 2026-11-04T00:36:42Z used 23 requests: 11 sources succeeded, DFIR Diva returned 403, and 43 offers from two vendors were published. Collector tests now total 64.

## TrainSec removed, 5 November 2026

The owner removed TrainSec from the source registry. Its 33 offers left the public snapshot on the next run with reason `source_removed_from_registry`. The adapter, fixture and reviewed-evidence receipt stay in the repository as test coverage and provenance only.

## Structured-data adapter, 7 November 2026

A config-driven `structured_offers` adapter publishes schema.org `Offer` data from a vendor's own 2026 campaign page, under the same evidence bar as the maintained adapters; see [operations](../docs/operations.md#adding-a-vendor-with-structured-data-no-new-parser). Independently of any adapter, the collector now refuses to publish offers from a source that is not `type: official` on a hostname in `supported_official_domains`. No vendor is registered for the new adapter yet. Collector tests now total 74.

## Current prices only, 8 November 2026

By owner decision, prices are no longer a publication filter. No price history is kept (`price_history` stays empty), offers with the same identity publish the most recently confirmed price instead of being quarantined, and adapters no longer withhold 2026 offers over a missing or non-higher reference price, an invalid currency code or a stated saving that disagrees with the prices; such offers show their price alone or an unspecified currency. Offers with no price at all, "Coming Soon" courses, off-domain links and non-2026 evidence are still withheld.
