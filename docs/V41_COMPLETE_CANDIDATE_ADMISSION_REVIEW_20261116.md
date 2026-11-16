# v41 candidate admission review — 16 November 2026

The frozen candidate differs from the published release by **+2,048 / −1,280 IPv4 addresses** and **two added IPv6 /48s**. PR #53 holds the candidate for seven directional IPv4 rows. That is enough to hold this exact artifact and is not an approval of the other changes. This review makes no routing policy, watch-table, or publication change.

- Verified [PR #55 artifact 14215435155](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43844682467/artifacts/14215435155) at ZIP SHA-256 `d57588ce98fdf6eaecc4a247ba3b46187f4d26fb90c81748804387b7ee09b8b0` and checked 13 manifest assets. The candidate DAT is `3161fdd5eda4d9c2f962a3c8d1bd0c187e5cab9260284a13679b289a9a6d0855`. The pinned release DAT at `e20cf73` is `b17fe26ccdcb8d272e6233ec9686a514b309e9d75e75653313a75f329b70fae7`.
- Decoded both DATs and both retained ipverse archives. All ten additions already occur in the candidate v37 base and the selected regional-origin sidecar. None comes from a standalone Hydra or Loyalsoldier RU/BY/PRIVATE overlap, the curated company BGP source, the effective block mask, or the official Telegram feed. The v2fly categories below are audit context, not the admission path.
- Expanded the exact check of the nominal 08:00 UTC Moscow RRC13 and Stockholm RRC07 MRT RIBs to all 15 changed prefixes. Archive hashes match the earlier raw-collector journal. In the table, entries such as “5 / 7” are exact RIB path rows in **Moscow / Stockholm**, not residential reachability observations. RIPEstat Routing Status fell back to 00:00 UTC and is not the 08:00 evidence. The table's RPKI results are independently retrieved for each exact changed prefix and origin.

| Added DIRECT prefix | Frozen admission route | Exact RIB path rows by origin (Moscow / Stockholm) | RPKI on the exact changed prefix | Exact RIPE registration / v2fly |
| --- | --- | --- | --- | --- |
| `48.103.230.0/24` | AS219095, RIR-RU | AS219095 3 / 0, AS401152 2 / 7 | AS219095 invalid_asn, AS401152 valid | NL / US |
| `85.92.155.0/24` | AS41745, RIR-RU, covering `85.92.154.0/23` | AS41745 6 / 8 | valid | US / NL |
| `85.92.156.0/24` | AS41745, RIR-RU | AS41745 6 / 8 | valid | US / NL |
| `152.234.249.0/24` | AS219357, RIR-RU | AS219357 5 / 7 | valid | PL / US |
| `201.58.141.0/24` | AS219095, RIR-RU | AS219095 3 / 0, AS401152 2 / 7 | AS219095 invalid_asn, AS401152 valid | NL / DE |
| `201.58.148.0/24` | AS216150, RIR-BY/KZ | AS216150 5 / 7 | valid | DE (covering /23) / DE |
| `213.145.79.0/24` | AS218184, RIR-BY/KZ | AS218184 5 / 8 | valid | KZ / DE |
| `213.226.121.0/24` | AS44790, RIR-RU | AS44790 3 / 4, AS62146 2 / 4 | both unknown | UA / UA |
| `2a0b:4e07:f4::/48` | AS218330, RIR-RU | AS218330 5 / 8 | valid | NL (covering /46 RU) / EE |
| `2a0f:6280:10ac::/48` | AS218184, RIR-BY/KZ | AS218184 5 / 8 | valid | DE / US |

## Review findings

1. **Leave both AS219095 additions on the hold list.** Their exact route-origin validation conflicts remain. RIPE links the exact assignments to the Astra geofeed, which says NL for both. RIPE links the covering allocations to the Ace Data Centers geofeed, which says US for those same exact /24s. These are conflicting self-published signals, not a geolocation decision, and neither geofeed overrides the exact RPKI result. RouteViews also retains a 7 Nov AS214647 path on `201.58.141.0/24`, not seen in either current raw RIB. A similar 7 Nov AS214647 result remains on `201.58.148.0/24`. The RIPE history sample places both of those old AS214647 exact-origin observations no later than 9 Nov. Do not count them as a newly observed matching origin.
2. **Open a separate advisory item for `213.226.121.0/24`, without appending a hold row.** The published ipverse archive contained only AS62146 for the exact prefix. The candidate archive contains both AS62146 and AS44790, and only AS44790 meets the project registry condition. This is a change in the builder's observed inputs, not first appearance of AS44790 globally. RIS history sees both in its 16 October to 16 November window, including the first bucket. RIPE exact route objects for both date to 2022 and use `OPTI-SPE-MNT`. The exact OPTI-SPE-NET object has country field UA, even though the covering /22 says RU. Both exact route authorization lookups are unknown, not invalid. Google and Cloudflare both resolve `opti.su` to `213.226.121.10` and `bgp.opti.su` to `213.226.121.1`; the latter has forward-confirmed PTR. Both also show reverse-zone delegation to OPTI nameservers, while Google's public DNS resolves `ns1.opti.su` to `213.226.121.4`. A single HTTPS HEAD to the public homepage from the execution environment returned 503, with no verified destination IP or home ISP path. This is a genuine DNS attribution lead, not evidence of a working HTTPS service in the prefix.
3. **Do not validate an ipverse aggregate as if it were a live announcement.** Both RIBs see exact AS41745 for `85.92.155.0/24`, but not its ipverse aggregate `85.92.154.0/23` as an exact route. The historical exact /24s `85.92.154.0/24` and `85.92.155.0/24` were both seen under AS41745 and coexist in the last sample. Exact `85.92.155.0/24` is valid, while exact aggregate /23 checked separately is RPKI unknown. [ipverse documents merge of adjacent/overlapping CIDRs](https://github.com/ipverse/as-ip-blocks). For the AS219095 case, likewise distinguish the frozen covering AS401152 `48.103.230.0/23` from exact AS401152 `48.103.230.0/24` seen in both RIBs.
4. **Keep the two IPv6 additions as advisory review.** Their exact BGP and RPKI results are consistent. Their exact RIPE assignment country fields are NL and DE and neither is the same prefix or selected ASN as the four existing reviewed AS218750 exclusions. The historical table cannot be extended by matching a country label, parent allocation, or apparent adjacency. For IPv4, `152.234.249.0/24` also appears as PL in an exact registration-linked geofeed. These are contextual indications, not service or residence proof.
5. **The five losses remain unresolved.** Both RIBs have AS137410 for all five and the adjacent control remains AS219305. Registrations and former-origin authorization do not name a currently active service. Current public DNS for the known first-party Curator CDN control points outside those five ranges. Public sources did not yield a verified hostname inside them. Do not reuse the OPTI endpoint as evidence for the five removed networks.

Official Cloudflare, AWS, Google and Google Cloud feed snapshots show no overlap with the 15 changed prefixes. The feeds cover their respective published scopes only. This is not a global provider allowlist. Registration and self-published geofeed country fields are not physical location or proof that the service works directly from Russia.

## Local reassembly on exact main

| Input change in disposable ipverse archive | Exact difference from the frozen candidate | #53 watched IPv4 difference from production |
| --- | --- | --- |
| None | DAT and both SRS match the checked CI candidate byte-for-byte | HOLD +512/−1,280 |
| Drop only AS44790 → `213.226.121.0/24` | −256 IPv4, exactly the OPTI /24 | HOLD +512/−1,280 |
| Drop the three selected MOAS records, retaining competing origins | −768 IPv4, exactly the two AS219095 /24s and OPTI | HOLD +0/−1,280 |
| Drop only AS218330 and AS218184 records for the two added /48s | Exactly those two /48s removed | HOLD +512/−1,280 |
| Replace AS41745's ipverse /23 with its two exact /24s | DAT byte-identical | HOLD +512/−1,280 |
| Replace that /23 with its lower /24 only | Only `85.92.155.0/24` removed | HOLD +512/−1,280 |

The effective block mask and PRIVATE are unchanged in every experiment. sing-box 1.13.12 compiled and independently checked IPv4/IPv6 coverage of both SRS files for the first four rows. The existing numeric publication bounds, Telegram checks and four reviewed historical IPv6 exclusions pass for those four rows. The raw-route split is a positive control for normalization, not a proposed build input. Synthetic archives and rebuilt release assets were not uploaded.

Separately operated Routinator at [rpki.ro](https://rpki.ro/ui/) agreed with RIPEstat on all 25 queried pairs, after equating `unknown` with `not-found` and `invalid_asn` with `invalid/as`. It reported a 10:37:59 UTC validation timestamp.

## Next decision

Keep PR #53 separate and unchanged. Its scoped hold acts before the first tag, and its three CI runs and exact-head tests passed. A merge can trigger production Actions, so this review did not merge it or change its Draft state. If approved later, recheck the queue and release SHA before merging. The five loss rows remain open until an attributable hostname or operator confirmation allows a matched RU-home and non-RU test. For the added OPTI prefix, request confirmation of the roles of AS44790 and AS62146 and a public test URL with an expected result before treating a matched HTTPS measurement as service evidence. For the two added IPv6 assignments, gather operator/service or independently reproducible reachability evidence before any decision about exclusions. No operator messages or residential probes were sent.

[Machine-readable evidence and SHA-256 inputs](V41_COMPLETE_CANDIDATE_ADMISSION_EVIDENCE_20261116.json).

Sources: [RIPEstat origin validation](https://stat.ripe.net/docs/data-api/api-endpoints/rpki-validation.html), [RIPE RIS collectors and raw data](https://ris.ripe.net/docs/route-collectors/), [RouteViews API](https://api.routeviews.org/docs/), [RFC 9632](https://www.rfc-editor.org/rfc/rfc9632.html), [Cloudflare ranges](https://www.cloudflare.com/ips/), [AWS ranges](https://docs.aws.amazon.com/vpc/latest/userguide/aws-ip-ranges.html), [Google address data](https://www.gstatic.com/ipranges/goog.json), [Google Cloud address data](https://www.gstatic.com/ipranges/cloud.json).
