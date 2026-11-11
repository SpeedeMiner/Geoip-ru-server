# v38 Lib4u/Jirnobruh exact hostname→IP review

**Baseline:** decoded PR #9 candidate artifact from run #71 (`43050025980`), GeoIP SHA-256 `445c2cb66e3840e61aff8cf5c53ab151ab4951189d2da462f13a9264a43ac515`.
**Candidate source:** PR #8 run #16 (`43051888120`), artifact `13869656430`, ZIP SHA-256 `940828a10486181ef8467c785ddc27e5ebab497692e0b3349c1891a2df4aa44f`.
**Review-only status:** all 360 exact IPv4 `/32` entries remain `REVIEW`; this is not an input to the production/v38 builder.

## Reconciliation

The candidate artifact sidecar was reparsed and deduplicated by exact IPv4 address. It was compared against the decoded v38 RU/PRIVATE protobuf categories and the exact v38 approved blocked-IP union.

| Measure | Count |
|---|---:|
| Unique Lib4u + Jirnobruh exact IPv4 addresses | 2,089 |
| Already covered by v38 RU/DIRECT | 1,535 |
| Covered by v38 approved blocked inputs | 194 |
| Remaining exact host candidates | **360** |
| Present in both Lib4u and Jirnobruh among the 360 | 20 |
| Lib4u-only among the 360 | 315 |
| Jirnobruh-only among the 360 | 25 |

The source split is mutually exclusive: 315 + 25 + 20 = 360. All remaining candidates are canonical IPv4 `/32` values. The compressed source file SHA-256 is `159ab81a1444fa94daea8fe9e2c1d48b4c618d0b69b67b6d5dca9efcf1b4d392`; its decompressed TSV SHA-256 is `00cf82af9c2883c5d051a8a08d212d20de5f39ff63bba68e0ac1bc40e960f0e0`. None is in v38 RU, PRIVATE or the approved blocked set at the captured baseline.

## Live enrichment

The CI review step queries, without changing any routing input:

- RIPEstat `network-info` for each candidate IP to obtain its current RIS-associated covering prefix;
- RIPEstat `routing-status` for each distinct returned prefix to preserve exact origins, visibility, query time and exact route objects (IRR observations);
- RIPEstat `rpki-validation` for every exact prefix/origin pair;
- RIPEstat `as-overview` for origin-holder labels;
- IANA RDAP IPv4 bootstrap followed by the authoritative RIR RDAP service for one representative IP per covering prefix (or the individual IP when RIS has no prefix).

At most four lookups run concurrently. Raw response bodies, HTTP status, URL, capture timestamp and SHA-256 are retained in a compressed JSONL sidecar. The normalized TSV is one row per candidate. `manifest.json` records input/output hashes, individual source query times, counts and errors.

This public RIPE RIS evidence is a separate observation layer: it **does not prove Antifilter `65444:210` membership** and does not replace the dedicated AS65444 peer session. RIPE `network-info` uses RISwhois 8-hour dumps; `routing-status` reports the latest RIS collection time (normally 00:00, 08:00 or 16:00 UTC). RPKI `unknown` is not `invalid`; an IRR object is not proof of legal holder or service exclusivity; RDAP registrant data is not proof that the IP is dedicated to a hostname.

Shared infrastructure flags (AWS/CloudFront, Cloudflare, Google, Microsoft, Akamai, Fastly, OVH, Hetzner, DigitalOcean, Gcore, CDN77 and other hosting/CDN providers) are conservative review hints only. They never automatically reject or approve a candidate.

## Decision policy

- No automatic admission of any candidate to DIRECT.
- `NO_RIS_PREFIX_FOR_IP` or an API error is a coverage limitation, not proof that the address is safe or unused.
- MOAS, RPKI invalid/unknown, absent exact IRR, cloud/CDN/hosting holder and shared-IP/domain ambiguity all remain explicit review issues.
- Direct `65444:210` evidence, if subsequently captured from the user’s registered VPS, overrides service-DIRECT evidence at the exact affected IP/prefix.
- No GeoIP protobuf, production source, release, `main`, `release`, tag or CDN asset is modified by this review.
