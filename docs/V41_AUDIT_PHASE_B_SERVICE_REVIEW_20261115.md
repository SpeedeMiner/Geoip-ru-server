# Phase B — Cloudflare and Google service review, 2026-11-15

This is a report-only review of existing DIRECT coverage. No CIDR, GeoSite category, client profile or release policy was changed.

## Pinned inputs and scope

- GeoIP v41 [snapshot 43712216767.1](https://github.com/SpeedeMiner/Geoip-ru-server/releases/tag/geoip-v41-snapshot-43712216767.1), release tree commit `79bddd4c51a36a8d3c2771e234e5171f574104c8`, DAT SHA-256 `b17fe26ccdcb8d272e6233ec9686a514b309e9d75e75653313a75f329b70fae7`. Compare only the Cloudflare proxy and Google `goog.json` existing CIDRs from the [phase B exact report](V41_AUDIT_PHASE_B_DIRECT_20261115.json.gz) and its [provider snapshot](V41_AUDIT_PHASE_B_PROVIDERS_20261115.json.gz). Google Cloud `cloud.json` is a different scope and is not substituted for `goog.json`.
- Observed origin prefixes are from the manifest-verified retained ipverse archive, SHA-256 `5d3b254a78d4fbbd225d6e18b317a9a29e799f418a6f7b57dbe617b1d1beeb41`. A covering or exact observation is not proof of geography, service, reachability or tenant. A covering origin alongside an exact origin is not exact-prefix MOAS.
- GeoSite [numbered v11.19](https://github.com/SpeedeMiner/Geosite-ru-light/releases/tag/v11.19) at `ec6214b628162011ea1b4ebaf454cf0f6ae795d9`. Verified published hashes and exact rule parity between the DAT and sing-box 1.13.12 decompilation of RU, BLOCK, GOOGLE-PLAY, GOOGLE-DEEPMIND and YOUTUBE SRS. The five groups do not describe all possible client rules. No live client profile was supplied.
- Public recursive DNS queries were made on 15 November 2026, 14:04:37–14:06:10 UTC, using Google and Cloudflare DoH with Google ECS set to `0.0.0.0/0`. Responses include UTC times, CNAME/A/AAAA, status and response hashes. This is not a Russian ISP vantage, localized DNS measurement, HTTPS/reachability test or a real routing decision.

## Disposition of existing DIRECT CIDRs

| Provider scope | Exact scoped intersection | Result |
| --- | --- | --- |
| Cloudflare proxy | 13 IPv4 CIDRs (3,584 addresses), 15 IPv6 /48 | The retained v37 base independently admits all 28 CIDRs. Observed covering or exact prefixes are from AS13335, AS14789 or AS132892, with 15 CIDRs having an exact observation. Example: `104.22.255.0/24` is exact under AS14789 and covered by `104.22.240.0/20` under AS132892. Keep in review. A shared proxy IP cannot identify a specific tenant. |
| Google `goog.json` | 29 IPv4 CIDRs (7,789 addresses), one IPv6 /48 and twelve /64 | The retained v37 base independently admits all 42 CIDRs. Only covering origins AS15169 or AS396982 were present in the retained BGP source. Five AS396982-covered IPv4 ranges (4,608 addresses) also match Hydra DIRECT but are not Hydra-only. Keep in review. Neither origin nor reverse DNS is enough to admit or remove a whole range. |

The 65-host sample (32 corporate/public-service and IP-checker hosts, 24 Google-related hosts, nine Cloudflare controls) returned 260 DNS responses; 258 NOERROR and two Cloudflare SERVFAIL responses for `belarusbank.by`, which had A and AAAA answers via Google. At least one address was returned for every hostname across both resolvers. None of the 304 distinct returned addresses fell into the 70 scoped overlap CIDRs. This does not mean no service uses those addresses. For example, `ip.oxylabs.io` returned Cloudflare proxy addresses outside the scoped DIRECT intersection and has a GeoSite RU exact rule. `ip.nnev.de` also has a GeoSite RU exact rule.

One deterministic PTR sample per minimal CIDR (first address after the network address, or the single host of a /32 or /128) found 28 names, all for Google-scope CIDRs; all 28 forward resolutions included the sampled address. Names under `bc.googleusercontent.com`, `1e100.net` and `fetch.tunnel.googlezip.net` are supporting observations, not a mapping to a customer or an application. The other 42 samples returned NXDOMAIN, which is not evidence that the underlying IP is unused.

## GeoSite collisions for client review

| Exact hostname or example | Matching categories on v11.19 | What to check |
| --- | --- | --- |
| `firebaseinstallations.googleapis.com`, `app-measurement.com` | RU, BLOCK, GOOGLE-PLAY | Examine first-match order and the desired behavior of each hostname. Moving the whole category can affect other domains. |
| `mtalk.google.com` | RU, GOOGLE-PLAY | Explicit PROXY precedence is needed if the profile intends to proxy this hostname. |
| `youtube.ru`, `youtube.by`, `youtube.com.by`, `youtube.kz` | RU, YOUTUBE | A broad RU match may take precedence over the intended YouTube proxy rule. |
| `drivefrontend-pa.clients6.google.com`, `drivelabels.clients6.google.com` | RU, GOOGLE-DEEPMIND | The DeepMind match comes from the wider `clients6.google.com` suffix. It does not demonstrate a DeepMind service. |
| `fcm.googleapis.com` / `firebaselogging.googleapis.com` / `crashlyticsreports-pa.googleapis.com` | RU only / BLOCK only / BLOCK only | Similar names do not imply similar routing. |
| `storage.googleapis.com`, `discord-attachments-uploads-prd.storage.googleapis.com` | RU only | A profile that intends to proxy only this Discord host needs an exact hostname override before RU, not a match on the whole Storage suffix or an HTTP path. |
| `googleapis.com`, `oauth2.googleapis.com` | None of the five groups | The actual decision depends on client-specific overrides, other rules and the default. |

Semantic overlap counts are pairs of rules, not counts of affected domains: BLOCK/RU 28, GOOGLE-PLAY/RU 3, GOOGLE-DEEPMIND/RU 2, RU/YOUTUBE 4, BLOCK/GOOGLE-PLAY 2. Domain overrides should be evaluated on a pinned client profile before proposing a policy change. If a shared CDN service is confirmed, prefer an exact or verified scoped domain rule where GeoSite is supported. A GeoIP-only client needs separate evaluation.

## Evidence and follow-up

- [Machine-readable evidence](V41_AUDIT_PHASE_B_SERVICE_EVIDENCE_20261115.json.gz), gzip SHA-256 `dbf3b24cf5136989c40613d056bd474fbeaa364627c03c8793a032953e5cb89e`, uncompressed JSON SHA-256 `a791555b6f125612d1e035aa10a371ad81b6d535d0db5c13ec2135cc4d36b794`. Includes CIDRs and provenance labels, observed origin relations, DNS query results, per-category matches and illustrative first-match cases. The live DNS responses are retained observations, not expected to replay byte-for-byte.
- No removal is justified by this sample. Remaining evidence for a specific admission or exclusion is a dated regional ISP DNS/availability observation, a supported service identity and, where relevant, a pinned client profile with its explicit rule order. Mirror validation is plan step 3 and is not included in this checkpoint.
