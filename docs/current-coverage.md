# Current source coverage

Last bounded live run: 2026-11-04T00:36:42Z, 23 HTTP requests, 11 of 14 registered sources fetched successfully. Two official sources publish offers; everything else is discovery only or deliberately unfetched.

## Publishing sources

**TrainSec** (33 individual courses). The vendor moved its campaign page to `/cybersecurity-courses-black-friday-2026/`; that URL answers the collector's ordinary user agent, so offers are now confirmed by automated HTTP rather than the earlier reviewed first-party extraction. The older URL still returns 403 and is no longer registered. A dollar sign without an ISO code means currency stays null. Ten catalog cards with prices that contradict the 40% campaign and two without a course-specific price remain quarantined candidates.

**Practical DevSecOps** (10 individual certifications). The vendor's own article "Best InfoSec Black Friday Deals 2026" (published 3 November 2026) lists per-certification sale prices at 15% off. The vendor's banner cards state the same prices in USD, so currency is recorded as USD only where the banner matches the article card. The site simultaneously labels the discount a "CSA Month Sale" and shows expiry only as a countdown; both facts appear in each offer's conditions and no end date is invented. Fourteen bundle cards and one "Coming Soon" course are candidates, not offers.

## Discovery-only sources (fetched, never publish)

- **GitHub lists:** 0x90n (2025 edition, historical), hysnsec (2025 heading, historical), twf-nikhila (2026 edition, general developer deals with a small Security & Privacy section). Links become candidates; coupon lines are never copied.
- **Ciphers Security tracker:** 2026 article published 27 October 2026. Every entry read "Not announced yet (checked 27 Oct 2026)" at the last run, so it yields no candidate links yet.
- **BleepingComputer offers:** dated StackCommerce storefront posts. Marketplace software is excluded by policy without seller authorization; training bundles would need per-article seller evidence before any adapter could publish them.
- **AppSecEngineer pricing, SANS specials, StackSocial:** official or marketplace pages with no 2026 campaign evidence. Checked and recorded as discovery so their status is visible; nothing publishes.
- **Practical DevSecOps 2025 article:** explicit 2025 heading, historical.
- **DFIR Diva:** the registered page says discounts moved to a community listings site; the collector currently receives HTTP 403 from the page and the listings site returns a server error. Reported as unavailable.

## Deliberately unfetched

- **Modern Security:** its robots.txt returns 403, so the fetcher fails closed. Its page also has no 2026 campaign text and exceeds the 2 MiB response limit.
- **r/cybersecurity megathread:** robots.txt disallows the path. Historical 2025 content anyway.

## What this does not establish

The vendor watchlist (TryHackMe, Hack The Box, OffSec, and about sixty others) has no registered URLs and no adapters. Roundup links to those vendors become candidates only; each needs its own official 2026 campaign page and a maintained parser before it can publish. The collector does not change its user agent, bypass robots rules or retry blocked hosts to widen coverage.
