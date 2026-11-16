# Scheduled-main publication audit: 16 November 2026

**Outcome:** The verified rolling ipverse update is sufficient to reproduce the full candidate DIRECT delta with the existing production code, independent of PR #52. The current publication preflight accepts that candidate. This is a reproducible publication risk, not an actual publication or a routing policy decision.

## Reproduction

The code is the unmodified production commit [`c0d2a01`](https://github.com/SpeedeMiner/Geoip-ru-server/commit/c0d2a01ba1fb5f5c0e48965d614945348083a900), including its own company ASN registry and policy. The original raw inputs were read from the checked and manifest-bound [published build](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43747743430/artifacts/14174864343) and [PR #52 build](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43824800380/artifacts/14206197490). The replays regenerated RIR and IANA data, selected origins, hard and resolver-only block layers, the v37 base, and the v41 overlay. The RIR dates were fixed to the corresponding build's UTC dates. Go 1.26.10 and sing-box 1.13.12 were hash-verified.

| Original bundle | ipverse archive commit used | v37 and v41 outcome |
| --- | --- | --- |
| 15 Nov production | `54c5fec676bc504d44a09e9d45d0fe578795cbff` | Both match published build |
| 16 Nov PR | `e23603237f0e178c026963fea2b36165d1badd75` | Both match PR candidate |
| 15 Nov production | `e23603237f0e178c026963fea2b36165d1badd75` only | Both match PR candidate |
| 16 Nov PR | `54c5fec676bc504d44a09e9d45d0fe578795cbff` only | Both match published build |

The rolling archive was independently downloaded from the workflow's master URL and matched the newer PR archive byte-for-byte. Its PAX commit and SHA-256 were checked. The effective block mask has the same SHA-256 in all four replays. The original and newer DAT digests are `b17fe26ccdcb8d272e6233ec9686a514b309e9d75e75653313a75f329b70fae7` and `3161fdd5eda4d9c2f962a3c8d1bd0c187e5cab9260284a13679b289a9a6d0855`. The two regenerated candidate SRS matched the PR artifact. No client asset was pushed.

The [main workflow](https://github.com/SpeedeMiner/Geoip-ru-server/blob/c0d2a01ba1fb5f5c0e48965d614945348083a900/.github/workflows/geoip-v41.yml) schedules daily builds at 03:45 UTC. A successful scheduled build on `main` is eligible for the publish job without a PR merge. The checked-in read-only publication preflight passed with no overrides after independently reading and verifying release `e20cf73`. The candidate has IPv4 +2,048/−1,280, IPv6 +2 /48/−0, identical PRIVATE and unchanged hard/resolver-only/Telegram policy. The IPv4 size bound for that release is 267,011 addresses and returned `needs_review: false`. Actual snapshot creation, asset readback, promotion and CDN write were not exercised. At the pass's observed refs, the 15 Nov release was still in place. A later successful run may change that.

## Additional admission review

| Added exact /24 | Selected by the candidate | Other origin in RIS | RIPEstat RPKI | Assessment |
| --- | --- | --- | --- | --- |
| `48.103.230.0/24` | AS219095 | AS401152 | AS219095 `invalid_asn`, AS401152 `valid` | Review both origin pairs before promotion |
| `201.58.141.0/24` | AS219095 | AS401152 | AS219095 `invalid_asn`, AS401152 `valid` | Same condition, not evidence of a hijack |
| `213.226.121.0/24` | AS44790 | AS62146 | Both `unknown` | Separate review, do not equate no ROA with invalid |

Both collectors see the two origins for each of the first two prefixes. RIS had 8 AS219095 rows versus 323 and 320 AS401152 rows at its 16 Nov 05:59:57 UTC state. RouteViews had 2 AS219095 rows for each in its observed result and 173 and 149 AS401152 rows, respectively. The latest path update timestamps in that document are not equivalent to a synchronized sample. RIPE RDAP registers the first two exact allocation objects as ASTRA-NETWORKS-LTD, country field NL. The third exact object is OPTI-SPE-NET, field UA. These fields are resource registration, not service location. RPKI distinguishes origin authorization from a claim that a route is malicious.

The other five added IPv4 /24s and both added IPv6 /48s had valid origin pairs in the dated RIPEstat check. The ipverse exact-origin list for `85.92.155.0/24` is empty because its admission came from the covering `85.92.154.0/23` in that archive. RIS sees the exact /24 via the same AS41745, while the /23 query returned the two more-specifics. Full observations and source digests are in the [reproduction evidence JSON](V41_SCHEDULED_MAIN_IPVERSE_REPLAY_EVIDENCE_20261116.json).

PR #52's current provenance advisory counts exact MOAS on the pinned ipverse view, but that view listed only AS219095 on `48.103.230.0/24`, and emitted provider-scoped rows do not enumerate these three changes. Its watched-ASN report does not watch the four origins in the table. The exact DIRECT advisory lists the additions, but does not adjudicate RPKI, and none of these advisories is a production gate. This is why a small origin-level change can pass the existing size and block-feed gates.

A local diagnostic modified only the AS219095 observation file, removing the two exact origin pairs from an otherwise identical archive. The build then removed precisely those two /24s (512 IPv4) from candidate DIRECT, with no additions, no IPv6/PRIVATE change and a byte-identical effective block mask. The counterfactual DAT was `b66e645e006059a257333ed854231a0f00f6cd0125044686c5c75c3425cb005f`. No repository input was changed. The replay tests causality only and does not authorize removing either prefix.

## Decision to keep explicit

- The [five lost prefixes](V41_FIVE_REMOVED_PREFIX_REVIEW_20261116.md) remain open. Neither sufficiently attributable Russian reachability evidence nor a confirmed service hostname inside `177.29.253.0/24` has been obtained. The current published binaries still cover all five unless a later deployment happens.
- Prioritize the two AS219095 additions in the review queue. If a protection against automatic promotion is requested, prefer a narrowly scoped hold on the reviewed delta at the publication checkpoint. Such a hold would not pin ambiguous CIDRs into DIRECT and would not change PRIVATE, hard blocks, or Telegram precedence. Do not silently turn RPKI `unknown`, MOAS, or unavailable evidence into a blanket rejection.
- Continue read-only verification of the next main run and publication refs. To settle CURATOR-CDN service ownership, ask for an exact-prefix confirmation and a public hostname or URL with expected DNS/HTTPS behavior. [Official Curator contacts](https://curator.pro/company/contacts/). No message was sent.
