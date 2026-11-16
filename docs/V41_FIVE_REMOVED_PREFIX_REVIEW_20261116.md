# Review queue: five IPv4 prefixes absent from the v41 candidate

Updated 2026-11-16. Each row is an exact /24 present in published DIRECT at release `e20cf733a13d92040134895ebd580b7c9060fa3b`, but absent from the verified PR #52 candidate. This is not a production removal. The queue is advisory and no static pin or exclusion is authorized by these observations.

| Prefix | Former selected BGP origin | First AS137410 update in RIS, 15 Nov UTC | v2fly in pinned input | Published → candidate DIRECT | Review |
| --- | --- | --- | --- | ---: | --- |
| `177.29.253.0/24` | AS219306 CURATOR-CDN (HLL LLC) | 14:14:32 | US | 256 → 0 | OPEN: confirm exact-prefix service use with HLL or an authenticated service |
| `177.122.229.0/24` | AS219216 TELECOMSTROYSERVICE-AS | 14:15:04 | US | 256 → 0 | OPEN: one asymmetric TCP/443 result, no authenticated service |
| `177.122.241.0/24` | AS218568 SGP22-AS | 14:16:10 | US | 256 → 0 | OPEN: no verified public service target |
| `177.166.74.0/24` | AS219262 WAICORE-RUSSIA | 14:16:44 | DE | 256 → 0 | OPEN: no verified public service target |
| `177.166.78.0/24` | AS219238 NSKIB-ASN | 14:17:22 | DE | 256 → 0 | OPEN: no verified public service target |

## What has been verified

- **BGP:** RIPE RIS observed former origin paths via AS401322, a coordinated visibility drop on 15 Nov, then AS137410 via AS62610 for all five. RouteViews independently returned AS137410 on all five. The adjacent `177.29.252.0/24` retained AS219305 via AS401322 in the same time samples and retained 256 → 256 DIRECT addresses.
- **IRR, RDAP and RPKI:** RIPE exact route objects for all five under `hk-larus-1-mnt` were created for AS137410 within six seconds, at 07:31:48–07:31:53 UTC on 15 Nov. RIPE RDAP names the exact allocations as Novacart-Commerce-llc with country field HK. This differs from the RIPE VG label in the pinned delegated statistics, which is a separate registration field. On 16 Nov RIPEstat RPKI returned `valid` for each pairing with AS137410, AS17561 and the respective former origin. Neither RDAP nor RPKI identifies the hosted service or the reason for the BGP change. Earlier unsuccessful RPKI queries were superseded by these dated results.
- **Reachability:** In [VPNObratno run 43820309250](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43820309250), the two verified RU ASN exits timed out on `177.122.229.2:443` while both HTTPS controls returned 200. The US runner connected at TCP level but received a TLS protocol error. No HTTP response, certificate or FQDN tied this IP to a service. The other nine earlier sample addresses were inconclusive, and household access type is unverified. Public RIPE Atlas target-network lookups returned no listed measurements for these five /24s and did not start new measurements.
- **Service identity:** official Curator public assets and AdGuard's documented CDN hostname demonstrated real CDN endpoints and DNS variation across resolver/ECS samples, but none of 30 DNS samples mapped them into these five /24s. The three returned IPv4 addresses for sampled RU ECS hints were already covered by both published and candidate DIRECT. A DNS ECS hint is not a probe from a residential network.
- **Build:** the verified release and candidate binaries disagree for these five while PRIVATE, effective block mask, hard mask and resolver-only input are unchanged. All five cease to be covered by the v37 base and selected regional BGP layer in the candidate. No overlap with Hydra DIRECT/WHITELIST or retained Loyalsoldier RU/BY was found in the pinned input. v2fly US/DE is not admitted as a country category. AS219306 stays registered and monitored in PR #52.

## References and next evidence

- [Published workflow 43747743430](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43747743430), DAT `b17fe26ccdcb8d272e6233ec9686a514b309e9d75e75653313a75f329b70fae7`, ipverse `5d3b254a78d4fbbd225d6e18b317a9a29e799f418a6f7b57dbe617b1d1beeb41`.
- [Verified PR workflow 43822933071](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43822933071), DAT `3161fdd5eda4d9c2f962a3c8d1bd0c187e5cab9260284a13679b289a9a6d0855`, ipverse `84af740b9546cf54448ff0782f5ddc15d458e15b0d2409fcff8de3d5733baa34`.
- [Execution journal](V41_OBSERVABILITY_JOURNAL_20261116.md) and [traceable observation matrix](V41_FIVE_PREFIX_TRANSITION_EVIDENCE_20261116.json). Routing admission remains undecided. Next useful evidence is an operator-confirmed test hostname/URL or an independently authenticated service observed in a disputed range, followed by bounded DNS and HTTPS checks from verified RU access networks and a contemporaneous reference. A negative check against unnamed IP samples does not classify a /24. No operator was contacted as part of this pass.


## Scheduled main can reproduce the loss without PR #52

A read-only replay on unchanged production code isolated the loss to the rolling ipverse archive. The checked-in prepublication validator accepted the exact replay without overrides. The observed release is unchanged, but a later scheduled refresh can publish the loss. See the [same-code replay and admission review](V41_SCHEDULED_MAIN_IPVERSE_REPLAY_20261116.md). This does not change the five OPEN decisions or pin any disputed network.
