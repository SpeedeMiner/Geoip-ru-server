# v38 Lib4u/Jirnobruh hostname-to-IP distribution checkpoint

**Captured from:** review/v38_pr8_new_host_ip_candidates_20261111.tsv.gz
**Branch:** experiment/vpn-route-candidate-build-2026-11
**Review baseline:** PR #9 v38 candidate run #71; output SHA-256 445c2cb66e3840e61aff8cf5c53ab151ab4951189d2da462f13a9264a43ac515
**Status:** analysis-only. No address promoted to DIRECT.

## Exact inventory validation

- 360 rows / 360 unique IPv4 addresses.
- All 360 are globally routable IPv4 and canonical exact /32.
- Zero overlap with v38 RU, PRIVATE or approved blocked inputs at the recorded baseline.
- 275 distinct hostnames across the 360 candidate IPs.
- 117 IPs have more than one associated hostname; maximum observed hostname_count is 31.
- All candidates remain REVIEW.

Source sets are mutually exclusive after deduplication:
- Lib4u only: 315
- Jirnobruh only: 25
- Both feeds: 20

The hostname-to-IP data are upstream snapshot observations, not a fresh authoritative DNS resolution performed during this review. The new RIPEstat/RDAP CI enrichment is separate and does not prove present DNS association or exclusive service use.

## Concentrated hostname groups

| Group | Unique hostnames | Candidate IPs associated with the group |
|---|---:|---:|
| Kaspersky / KSN | 129 | 113 |
| HiWiFi / Xiaomi | 3 | 59 |
| AWS / CloudFront | 1 | 39 |
| .ru / .рф suffixes | 22 | 37 |

These group counts are associations, not disjoint totals. Hosting/CDN/provider labels are review hints, not automatic exclusions.

Examples of repeated hostname mappings:

| Hostname | Candidate IPs |
|---|---:|
| hiwifi.com | 47 |
| kp-configs-smart-tv.s3.eu-central-1.amazonaws.com | 39 |
| ksn-file-geo.kaspersky-labs.com | 22 |
| ksn-file.geoksn.kaspersky.com | 21 |
| ksn-url-geo.kaspersky-labs.com | 21 |
| ksn-crypto-url-geo.kaspersky-labs.com | 20 |

## Review interpretation

1. A hostname mapped to multiple IPs is normal for distributed services and does not establish dedicated ownership.
2. Multiple hostnames mapped to one IP are a shared-IP / co-hosting risk, particularly where the address belongs to cloud or CDN infrastructure.
3. A non-RU suffix does not disqualify a regional service; it increases the need for exact hostname/service attribution.
4. Public RIPE RIS route-origin, RPKI, IRR and RDAP evidence is supplemental. It does not replace DNS evidence or the private Antifilter AS65444 BGP session.
5. No automatic DIRECT admission is allowed. Candidate decisions require exact BGP origin, current DNS/hostname validation, holder and shared-infrastructure analysis, and comparison with the 65444:210 snapshot when available.

## Current automated check

PR #8 Actions run #18 (43064874646) builds the pinned source artifact, then queries RIPEstat and IANA/RIR RDAP for the 360 exact-host candidates with bounded concurrency. The raw response sidecar and manifest are uploaded as review artifacts. This checkpoint records the source-side distribution independently of that live enrichment.