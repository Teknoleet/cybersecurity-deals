# Cybersecurity Deals — draft for approval

**Domain:** deals.teknoleet.com
**Edition:** 2026
**Status:** Approved specification; implemented with scheduled collection every 30 minutes. Cloudflare publication and DNS changes are owner-gated.
**Prepared:** 3 November 2026

## 1. What the first release will do

A public, account-free directory of cybersecurity and AI-security offers, including VPNs. Visitors can search immediately, browse product-type categories, and refine results by vendor and security topic. Every offer links to its evidence and shows when it was last successfully checked.

Changes are managed in a public GitHub repository. There is no admin interface, visitor submission form, subscription system, payment flow, or visitor account database. The site is designed around free services only, with no paid APIs and no Node.js backend.

Collection continues every 30 minutes on a best-effort basis, but the landing page does not advertise the cadence. Its status card is titled **Last Check**. This is not a guarantee that every source is accessible or that a new promotion appears immediately.

## 2. Proposed page shape

The revised concept image illustrates the desktop visual direction using **fictional vendors and sample offers**. It is not a working page or a verified deal list. This written draft controls behavior where the image simplifies details.

```text
CYBERSECURITY DEALS

2026 EDITION
Less spend. More security.              Last Check
Cybersecurity offers. Sources included. [collection timestamp]

[ Search deals, vendors, topics, or coupon codes…                       ]

REFINE RESULTS                    CURRENT OFFERS
Category: [All categories v]       [Offer card]         [Offer card]
Vendor: [All vendors v]            [Offer card]         [Offer card]
Topic: [Select topics v]
[Clear filters]

Each card: vendor / product / category / topic tags / offer or price
           coupon if available / conditions / evidence status
           last successful check / source / View offer

Footer: advertised-price notice · supporting information · 2026 edition
```

**Desktop:** A compact editorial masthead showing only the mark and site name, prominent search, a narrow filter rail, and two columns of readable cards. There is no secondary branding line and no header or category tab strip. Product-type category selection is a dropdown in the filter rail. No oversized illustration, advertising carousel, or decorative dashboard counters.

**Mobile:** A single card column and a collapsible filter panel containing category, vendor, and topic controls. No header or category tabs are introduced on mobile. Search stays near the top. Important conditions and stale-data warnings remain visible without hover.

**Supporting information:** `/` contains the directory; `/sources/` explains sources and their health; `/methodology/` explains eligibility, verification, and limitations. Supporting information is reached through modest footer links, not header tabs. Individual offers expand within the directory rather than requiring a separate detail-page system in the first release.

**Status card:** Keep the existing card, titled **Last Check**, with the latest completed collection timestamp beneath it. Partial source failures must not be represented as successful checks of every offer; individual confirmation timestamps and stale warnings remain authoritative. No collection-frequency slogan appears on the landing page.

Search covers vendor, product, description, topic tags, and coupon code. Matching is case-insensitive. Different filter groups combine with AND; selecting several topics matches any selected topic. Result counts reflect the current filters, and a no-results state offers a clear reset. Query parameters preserve search and filters in shareable URLs. Default order is newly discovered offers first; routine successful rechecks do not push unchanged offers to the top.

## 3. Categories and topics

The primary categories are **Training & Labs**, **Certifications & Exams**, **Software & Tools**, **Hardware**, and **Books & Bundles**. The category dropdown defaults to “All categories”; this is an unfiltered view, not a separate category. A product receives one primary category to avoid duplicate cards. Categories are not displayed as tabs.

Topics provide a second, independent way to browse: Offensive Security & Red Team; Blue Team, Detection & DFIR; AppSec; Cloud & DevSecOps; AI Security; OSINT & Threat Intelligence; Reverse Engineering & Malware; Hardware & Physical Security; and Privacy & VPN.

AI offers can carry more specific tags such as `llm-security`, `agent-security`, `mcp-security`, `adversarial-ml`, and `ai-for-security`. Generic AI productivity products do not qualify merely because they use AI. A security-relevant bundle may span several topics without being republished as several offers.

## 4. Your 2026 eligibility rule

An offer can enter the public feed when its supporting evidence meets **either** of these conditions:

1. The offer or relevant campaign explicitly identifies **2026**.
2. The article or page containing the offer has a credible **original publication date between 1 and 31 October 2026**.

An unrelated year in a footer, URL, course title, or navigation does not establish a 2026 promotion. An old 2025 article with a newer “last updated” timestamp does not become eligible solely because it was edited. A November article can qualify through explicit 2026 offer or campaign evidence; the October-publication exception is not silently broadened to other months.

This is a campaign eligibility rule, **not proof that the deal is still active**. The specific product, price or discount, coupon, conditions, and any stated dates must also be supported by accessible current evidence. Known expired offers do not appear as current. Future offers are labeled upcoming and are not presented as redeemable now. Missing expiry dates remain unknown.

An October roundup can establish date eligibility and discover a candidate, but its linked current vendor evidence must support the particular offer before automatic publication. Where source dates conflict or cannot be substantiated, the candidate stays out of the public feed until corrected through Git.

Black Friday/Cyber Monday campaigns and general promotions receive distinct labels. The site will not claim that every qualifying 2026 promotion is a Black Friday deal.

## 5. Sources, marketplace policy, and duplicates

The attachment becomes a deduplicated source registry, not an automatically published inventory of valid offers. It includes GitHub lists, official vendor pages, and public roundups or feeds. Historical codes are monitoring leads only. Every source receives a stable identifier, canonical URL, type, topic coverage, and appropriate collection method.

The collector may follow relevant offer links from these resources, within a bounded request budget. It resolves official vendor destinations and uses supported parsers to extract evidence. It does not attempt an unlimited crawl. Newly encountered pages that cannot be parsed or validated safely become Git-managed candidates; discovery does not guarantee automatic publication.

Relevant marketplace book and training bundles may appear with an explicit **third-party seller** label. Software-license offers are excluded unless the seller's authorization for the product can be established. Unknown license provenance is not treated as acceptable because a discount is attractive. Initial outbound links use direct destinations rather than introducing a site affiliate program.

Repeated references to the same vendor, product/plan, billing period, coupon, and regional scope merge into one offer with multiple evidence links. Separate plans, bundles, license terms, or billing periods remain distinct. Conflicting prices are preserved as conflicts rather than resolved by choosing the largest discount.

## 6. Evidence and freshness on each card

Public cards use precise labels rather than a broad “verified” badge:

- **Vendor-published** means a current official source supports the offer. Checkout has not been tested.
- **Marketplace-published** means an allowed third-party seller supports the offer; the seller is identified.
- **Stale — recheck pending** means previously supported information could not be reconfirmed on schedule.

Historical, date-ambiguous, conflicting, and unsupported candidates stay out of current results. Explicitly expired or withdrawn offers are retained in the repository's history but removed from the current directory. The first release does not need a separate public archive browser.

The collector stores `last_attempt_at`, `last_successful_fetch_at`, and `last_offer_confirmed_at` separately. A successful page download is not sufficient if the offer itself cannot be found or parsed. An unchanged response can reconfirm earlier evidence only when it refers to the previously validated representation. A new collection or deployment timestamp never makes a failed source look fresh.

**Proposed stale threshold:** three hours without successful offer confirmation. Stale offers remain visible with a warning and sort after current confirmed evidence. If the entire collection stops, the browser still derives staleness from the saved timestamps. It never substitutes the visitor's current time for a verification time.

Cards show available coupon codes, original-currency prices, billing period, expiry, and material restrictions. Missing values are not invented. A coupon can have a copy button, but no automated cart creation, login, purchase, or checkout verification is included.

## 7. Prices: useful without overclaiming

Display advertised sale prices and discounts in their original currencies. If the source only offers a percentage, show that without manufacturing a sale price. Unknown VAT or renewal terms are not silently assumed to be favorable; material known restrictions remain visible.

A lightweight history can store a new observation when a comparable price changes. For the first release, this supports an optional “lowest observed since tracking began” note or an expandable text history, not a price-chart subsystem.

Observations are comparable only for the same product, plan, currency, billing period, and relevant eligibility. A crossed-out vendor price is labeled an advertised reference price, not an independently verified baseline. No historical low or true-saving claim is made for dates before collection began. If this feature materially complicates the build, it can be omitted without changing the rest of the site.

## 8. Free hosting and collection architecture

```text
Public GitHub repository
  sources + parsers + policy + manual overrides
                     |
     GitHub Actions — scheduled every 30 minutes, minutes 17 and 47
                     |
       Python: fetch → extract → date/evidence checks
                     |
       normalize → deduplicate → apply overrides
                     |
       validated state + compact observation history
                     |
       generate static HTML + JSON + browser assets
                     |
       direct publish from GitHub Actions
                     |
       Cloudflare Workers Static Assets — Free
                     |
              deals.teknoleet.com
```

**Collection:** Conventional Python runs on standard GitHub-hosted Linux runners in the public repository. GitHub documents those runners as free for public repositories. We will not select larger paid runners or rely on accumulating Actions artifacts as a database. [1]

**Serving:** Cloudflare Workers Static Assets serves precomputed files. Despite the product name, an assets-only site does not need an application backend script. Cloudflare documents static-asset requests as free and unlimited, with no additional asset-storage charge. Search and filters run in the browser; visitor traffic does not trigger scraping or database queries. [2] [3]

**Publishing:** GitHub Actions publishes directly using Cloudflare's deployment tooling and a scoped token stored in GitHub Secrets. Cloudflare documents this external CI path. Node.js may be used to run Wrangler during deployment; it is tooling, not a Node.js backend. Cloudflare-hosted Workers Builds and hourly Pages Git builds are not part of this design. Pages Free's hosted-build allowance is a reason not to tie each collection cycle to a Pages rebuild. [4] [5]

**Persistence:** A dedicated Git data branch stores normalized offer/source state, compact evidence excerpts, and changed-price observations. Main contains reviewed code and configuration. The collector never executes code from fetched pages or the data branch. Bounded retention avoids repository growth from full HTML snapshots or repeated unchanged prices. Data-branch commits do not trigger the code-deployment workflow again.

**Reliability:** Schedules are best-effort; GitHub warns about delays, dropped runs, and disabling schedules in inactive public repositories after 60 days. A manual workflow trigger provides a GitHub-native rerun option. No precise hourly SLA is promised. [6]

Each run has a bounded source count, concurrency, request size, timeout, and retry allowance. Source failures retain last-known-good records. Validation or publishing failures leave the prior deployed site in place. The static HTML and JSON are published together, with short-lived or revalidated mutable data caching and fingerprinted code assets. An already-open page checks for a newer snapshot periodically without querying vendors itself.

This is designed for **zero service spend under the documented free plans**, not a promise that providers will never change their policies. No paid plan, trial-only dependency, paid overage, or automatic upgrade is authorized. If limits prevent an operation, it fails visibly and preserves old data where possible rather than purchasing capacity. No AWS, S3, R2, D1, KV, hosted LLM, or paid scraping service is required.

## 9. Security and collector boundaries

Use deterministic source-specific extraction and ordinary structured feeds where available. Prefer conditional requests and supported APIs over full downloads. Browser automation is not a prerequisite for the first release; pages requiring it may remain unsupported until a free, bounded method is demonstrated. Private Discord/Slack content, login-required pages, CAPTCHAs, and paid APIs are not bypassed.

Fetched pages are untrusted input. Extracted text is escaped before rendering; raw source HTML is not injected into cards. Link discovery permits HTTP(S) destinations only, blocks private/local/metadata addresses, validates redirects, and applies per-domain limits. GitHub Actions has minimal permissions, pinned dependencies/actions, no privileged deployment from untrusted pull requests, and secrets separated from public data.

The repository keeps small evidence excerpts and provenance, not wholesale copies of third-party pages. Collection respects access restrictions, rate limits, and applicable source terms. Sources that cannot be accessed reliably are labeled unsupported rather than advertised as monitored.

## 10. Visual direction

**Selected movement:** Dark editorial technology directory: professional, restrained, and content-first rather than a neon “hacker” theme. Alternative concepts considered were a light technical field guide and a monochrome terminal catalogue. Initial design sampling weights: 0.07, 0.04, and 0.02 respectively; these are creative selection weights, not claims about users.

**Core principles:** Search before decoration; evidence beside the claim; visible freshness; readable offer terms. A graphite background and warm-white type make longer product descriptions comfortable. An electric-lime accent identifies interactive elements and the brand; amber is reserved for caution. Status is always expressed in text as well as color.

**Layout and signature elements:** An asymmetric masthead, slim filter rail, fine rules, compact topic chips, and a bordered coupon strip. Cards remain consistent without reducing the whole page to a generic analytics dashboard. The wordmark pairs a simple geometric tag/shield mark with the name; it should not suggest a security certification or endorsement.

**Typography:** A readable sans-serif such as locally hosted Inter for headings and body, with a compact monospace such as IBM Plex Mono for coupon codes, timestamps, and edition labels. System fallbacks keep the page usable if fonts fail. Product names outrank discounts; conditions remain readable rather than becoming tiny fine print.

**Interaction and motion:** Immediate local search, explicit active filters, keyboard focus states, a clear reset action, and a subtle copy confirmation. Use brief transitions only; no animated counters, flashing sale banners, or motion required to understand state. Reduced-motion preferences are respected.

**Brand essence:** A source-transparent directory helping security practitioners find relevant offers without recycled historical codes. Personality: precise, useful, independent. Voice examples: “Vendor-published. Checkout not tested.” and “Last confirmed 4 hours ago — recheck pending.” The headline concept is “Less spend. More security.” No quality endorsement is implied by listing an offer.

## 11. Proposed repository shape

```text
.github/workflows/    scheduled collection and static publishing
collector/           Python fetching, extraction, normalization, policy
collector/adapters/  maintained source-specific parsers
config/              source registry, taxonomy, exclusions, overrides
web/                 static page templates, styles, browser interactions
schemas/             contracts for offers, evidence, source health
scripts/             static-output assembly and deployment helpers
docs/                methodology and deployment instructions

Dedicated data branch:
state/               normalized current offers and source health
history/             compact changed-price observations
```

At minimum, an offer records vendor, product/plan, category, topics, campaign type/year, eligibility evidence, coupon, original currency, available price/discount, billing period, known conditions, dates, official/seller destination, discovery sources, evidence excerpt, status, and distinct attempt/confirmation timestamps. Unknown fields remain null. Git-managed overrides can correct, exclude, or pin extracted values without an admin UI.

## 12. Approval boundary

Approval of this draft would authorize building the first version and preparing its GitHub workflows and Cloudflare deployment instructions. It does not by itself create a public repository, expose credentials, change DNS, publish the site, or enable recurring jobs. Those steps require the destination accounts/repository and explicit authorization when we reach them.

The 2026 edition is not automatically relabeled 2027. Until you decide its next lifecycle, it remains a 2026 directory, with offers removed from current results as expiry or withdrawal evidence appears.

## References

[1]: https://docs.github.com/en/billing/concepts/product-billing/github-actions "GitHub Actions billing"
[2]: https://developers.cloudflare.com/workers/static-assets/billing-and-limitations/ "Cloudflare Static Assets billing and limitations"
[3]: https://developers.cloudflare.com/workers/static-assets/get-started/ "Cloudflare static-site deployment"
[4]: https://developers.cloudflare.com/workers/ci-cd/external-cicd/github-actions/ "Deploying to Cloudflare from GitHub Actions"
[5]: https://developers.cloudflare.com/pages/platform/limits/ "Cloudflare Pages platform limits"
[6]: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule "GitHub scheduled workflow behavior"
