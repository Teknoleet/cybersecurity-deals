# Stage 1 source coverage

The review build contains 33 TrainSec course offers individually corroborated against its official 2026 campaign page through a reviewed first-party public-page extraction. These are actual advertised offers, not fictional mockup cards. Their prices and coupon have not been tested at checkout. The source uses a dollar sign without establishing an ISO currency, so the directory does not assume USD.

The initial evidence receipt is in `state/reviewed-evidence-receipt.json`; each offer also carries its observation method and original confirmation time. Importing reviewed evidence does not create an automated successful-fetch timestamp. The captured complete source pages are not bundled into the repository.

**The automatic TrainSec HTTP request currently returns 403.** This is reported as an unavailable source, not a successful check or an expired sale. Later collection attempts preserve the existing evidence times. After three hours, the browser marks those offers as needing a recheck. An inaccessible source is not bypassed, and manually importing the same evidence cannot legitimately advance its observation time.

The 0x90n GitHub README is accessible to the collector but still identifies its edition as 2025. It is a discovery source, not a source of current 2026 coupon codes. The registry includes other explicit resources from the research, and a separate named vendor watchlist. Entries without maintained/validated adapters are clearly unsupported rather than represented as automatically monitored.

The first release therefore demonstrates the directory and the evidence-preserving pipeline. It does **not** yet establish broad, unattended 2026 deal coverage. Before public go-live, review which sources can be collected reliably from the intended GitHub runner and add supported parsers or leave inaccessible sources explicitly unavailable. There is no promise that simply enabling the prepared schedule will unblock a vendor or turn historical offers into current ones.

No scheduled collection, Cloudflare publication, domain changes, public GitHub repository, deployment credentials, or paid services have been enabled. Preview runs from a static build with a local Python development server only.
