# v41 advisory audit calibration — 2026-11-15

This report compares four published release commits with three distinct, provenance-verified ipverse archives. There are only two transitions with independent archive bytes. The whole DAT can also change because policy, admission sources and blocking masks change. The table does not attribute the full difference to BGP.

| Published transitions | New BGP bytes | DIRECT IPv4 + / − | DIRECT IPv6 | Scoped provider overlap, fixed provider feeds | Block feeds |
| --- | --- | --- | --- | --- | --- |
| `f90d9939` → `7eef1efc` | yes | +27,762 / −126,810 | −3 /48 equivalents | no additions; removed 316 AWS public, 16 Google Cloud and 18 Google-owned IPv4 | `ip.lst` +6,761 / −6,789 IPv4; the other two sets unchanged |
| `7eef1efc` → `a23b381e` | yes | +4,801 / −1,302 | +1 /48 | unchanged | all three address sets unchanged |
| `a23b381e` → `79bddd4c` | no | +0 / −262 | −4 /48 | −5 Cloudflare IPv4; no additions | all three address sets unchanged; `ipresolve.lst` had an order-only SHA change |

Percent-only ASN cutoffs can hide real routes. In the first transition, AS9198 Kazakhtelecom lost observed coverage of `92.46.244.0/22` in the compared ipverse snapshot (previously part of its `92.46.240.0/21`), a loss of 1,024 addresses or **0.06848%** of its previously selected DIRECT space. AS15774 TTK-Svyaz lost `5.8.217.0/24`, or 256 addresses and **0.09116%**. Both exact prefixes were removed from that ASN's observed, selected and selected-in-DIRECT spaces. The whole DAT still covers **both ranges in all four releases**. In the current snapshot the ranges are covered by KZ/RU RIR and the v37 base, respectively; the TTK delta is also covered by selected origin AS49301. This is a loss of attribution to those two ASNs, not a loss of final DIRECT or proof of a realtime withdrawal or outage. A 0.1% filter would have hidden both. The other two transitions had no changes in any of the measured address spaces for the 59 watched ASNs. No complete watched family loss or prefix parse rejection was observed. In every candidate, 21 absent families remain unconfirmed.

The `ip.lst` net reduction of 28 addresses in the first transition hides 13,550 addresses of churn. Both directions are necessary. Counts, percentages and traditional net size should be displayed separately; none alone authorizes a release or a routing exception.

The same 28-domain DNS and GeoSite observations were applied to all four DATs without live lookups. All observed addresses were covered in all four DATs. There were 27 domains with IPv4 observations and four with IPv6 observations. Missing DNS observations and actual client routes remain unknown.

## Evidence and reproducibility

- [Historical JSON](V41_AUDIT_PHASE_D_HISTORICAL_20261115.json.gz), gzip SHA-256 `941c0ccf7430fa0bc271e90db8d8f1e157165882dcbc66c165c78e847e9136ad`. It records full release refs, all policy and input digests, exact feed/provider and changed-ASN CIDRs, and fixed service results. For large historical DAT deltas it retains exact counts and the digest of the canonical LF-delimited CIDRs rather than adding tens of thousands of rows to Git. Exact IPv6 CIDRs are preserved, including /47 representations of adjacent /48s.
- Restore each DAT, policy, provenance and origin inventories from the exact Git release commit. Verify the DAT sidecar and the policy-to-origin hash chain, then verify archived ipverse and raw feed bytes against the Git-pinned provenance. The old `f90d9939` policy predates the provenance SHA field, so only this offline historical replay uses the full pinned Git tree as the trust root for that provenance. There is **no** legacy bypass in PR or publisher scripts. The newer three policies bind the provenance directly. A historical comparison does not imply eligibility as an automatic last-live fallback baseline.
- `7eef1efc` has retained [versioned release inputs](https://github.com/SpeedeMiner/Geoip-ru-server/releases/tag/geoip-v41-snapshot-43617500418.1). `a23b381e` uses [retained build 43709200004](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43709200004/artifacts/14159950854). `79bddd4c` comes from [snapshot 43712216767.1](https://github.com/SpeedeMiner/Geoip-ru-server/releases/tag/geoip-v41-snapshot-43712216767.1). The 13 November archive used a retained local copy with the exact release SHA-256 and size. Do not substitute the current upstream tarball if those bytes are unavailable.
- Provider scope is the single captured 15 November snapshot for all comparisons, not assumed historical membership. Akamai and Discord remain unknown. Historical Hydra-only attribution requires the original policy and build layers and was not inferred from comparing DATs. Full reconstruction was exercised on the retained current CI candidate and exactly matched its DAT.

## Recommended CI disposition

| Signal | Advisory interpretation now |
| --- | --- |
| Exact ASN routes removed from selected DIRECT | Report each prefix and relative size. Separately highlight whole-family loss and parser rejection. |
| New scoped provider overlap | Report exact CIDRs and candidate applicability. An unchanged or missing provider feed is not a geographic guarantee. Do not create blanket exceptions. |
| Block-feed churn, fallback or stale/unknown coverage | Report additions and removals separately. Keep unknown baseline and degraded fallback explicit. |
| Fixed DNS or GeoSite replay differs from candidate | Review the exact case against the same retained observations. Do not report new DNS or connectivity without separate measurements. |

No numeric threshold is calibrated from two distinct-input transitions. Use the reports in PRs first and gather more independent observations. Existing integrity and release-policy gates are unchanged.
