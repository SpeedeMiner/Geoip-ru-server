# Review queue: five IPv4 prefixes absent from the v41 candidate

Updated 2026-11-16. Each row is an exact /24 present in published DIRECT at release `e20cf733a13d92040134895ebd580b7c9060fa3b`, but absent from the verified PR #52 candidate. This is not a production removal. The queue is advisory and no static pin or exclusion is authorized by these observations.

| Prefix | Former selected BGP origin | First AS137410 update in RIS, 15 Nov UTC | v2fly in pinned input | Full Loyalsoldier (not a build input) | Published → candidate DIRECT | Review |
| --- | --- | --- | --- | --- | ---: | --- |
| `177.29.253.0/24` | AS219306 CURATOR-CDN (HLL LLC) | 14:14:32 | US | VG | 256 → 0 | OPEN: confirm exact-prefix service use with HLL or an authenticated service |
| `177.122.229.0/24` | AS219216 TELECOMSTROYSERVICE-AS | 14:15:04 | US | VG | 256 → 0 | OPEN: one asymmetric TCP/443 result, no authenticated service |
| `177.122.241.0/24` | AS218568 SGP22-AS | 14:16:10 | US | VG | 256 → 0 | OPEN: no verified public service target |
| `177.166.74.0/24` | AS219262 WAICORE-RUSSIA | 14:16:44 | DE | VG | 256 → 0 | OPEN: no verified public service target |
| `177.166.78.0/24` | AS219238 NSKIB-ASN | 14:17:22 | DE | VG | 256 → 0 | OPEN: no verified public service target |

## What has been verified

- **BGP:** RIPE RIS observed former origin paths via AS401322, a coordinated visibility drop on 15 Nov, then AS137410 via AS62610 for all five. RouteViews independently returned AS137410 on all five. The adjacent `177.29.252.0/24` retained AS219305 via AS401322 in the same time samples and retained 256 → 256 DIRECT addresses.
- **IRR, RDAP and RPKI:** RIPE exact route objects for all five under `hk-larus-1-mnt` were created for AS137410 within six seconds, at 07:31:48–07:31:53 UTC on 15 Nov. RIPE RDAP names the exact allocations as Novacart-Commerce-llc with country field HK. This differs from the RIPE VG label in the pinned delegated statistics, which is a separate registration field. On 16 Nov RIPEstat RPKI returned `valid` for each pairing with AS137410, AS17561 and the respective former origin. Neither RDAP nor RPKI identifies the hosted service or the reason for the BGP change. Earlier unsuccessful RPKI queries were superseded by these dated results.
- **Reachability:** In [VPNObratno run 43820309250](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43820309250), the two verified RU ASN exits timed out on `177.122.229.2:443` while both HTTPS controls returned 200. The US runner connected at TCP level but received a TLS protocol error. No HTTP response, certificate or FQDN tied this IP to a service. The other nine earlier sample addresses were inconclusive, and household access type is unverified. Public RIPE Atlas target-network lookups returned no listed measurements for these five /24s and did not start new measurements.
- **Service identity:** official Curator public assets and AdGuard's documented CDN hostname demonstrated real CDN endpoints and DNS variation across resolver/ECS samples, but none of 30 DNS samples mapped them into these five /24s. The three returned IPv4 addresses for sampled RU ECS hints were already covered by both published and candidate DIRECT. A DNS ECS hint is not a probe from a residential network.
- **Trusted source scope:** the same archived Hydra and Loyalsoldier RU/BY/PRIVATE input files have zero overlap, while v2fly matches 256/256 per row in US/DE. The independently verified [complete Loyalsoldier DAT](https://github.com/Loyalsoldier/geoip/blob/ec6f8d0f6b5c6c6924d9230f2ed893f69585d38c/geoip.dat), which is not ingested by this build, labels the same five /24s and the neighboring control VG at 256/256. Neither the current builder's narrow files nor the full DAT outside its policy scope proves that a service works directly in RU. Do not describe them as absent from Loyalsoldier as a whole.
- **Geofeed and passive DNS:** the broader RIPE INETNUM's published [LARUS geofeed](https://larus.net/geofeed-trusted) had 2,546 parseable network rows and no exact, covering, or more-specific match for any of the five or the adjacent control. Exact INETNUM objects did not expose a separate geofeed. A bounded passive lookup found no service name for six sampled addresses, but also missed a known CDN control. This is a source coverage limit, not a negative service determination.
- **Build:** the verified release and candidate binaries disagree for these five while PRIVATE, effective block mask, hard mask and resolver-only input are unchanged. All five cease to be covered by the v37 base and selected regional BGP layer in the candidate. No overlap with Hydra DIRECT/WHITELIST or retained Loyalsoldier RU/BY was found in the pinned input. v2fly US/DE is not admitted as a country category. AS219306 stays registered and monitored in PR #52.

## References and next evidence

- [Published workflow 43747743430](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43747743430), DAT `b17fe26ccdcb8d272e6233ec9686a514b309e9d75e75653313a75f329b70fae7`, ipverse `5d3b254a78d4fbbd225d6e18b317a9a29e799f418a6f7b57dbe617b1d1beeb41`.
- [Verified PR workflow 43822933071](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43822933071), DAT `3161fdd5eda4d9c2f962a3c8d1bd0c187e5cab9260284a13679b289a9a6d0855`, ipverse `84af740b9546cf54448ff0782f5ddc15d458e15b0d2409fcff8de3d5733baa34`.
- [Execution journal](V41_OBSERVABILITY_JOURNAL_20261116.md) and [traceable observation matrix](V41_FIVE_PREFIX_TRANSITION_EVIDENCE_20261116.json). Routing admission remains undecided. Next useful evidence is an operator-confirmed test hostname/URL or an independently authenticated service observed in a disputed range, followed by bounded DNS and HTTPS checks from verified RU access networks and a contemporaneous reference. A negative check against unnamed IP samples does not classify a /24. See the dated follow-up in the journal for collector timestamps, full-database classification, and the separate publication hold in Draft #53. No operator was contacted as part of this pass.


## Scheduled main can reproduce the loss without PR #52

A read-only replay on unchanged production code isolated the loss to the rolling ipverse archive. The checked-in prepublication validator accepted the exact replay without overrides. The observed release is unchanged, but a later scheduled refresh can publish the loss. See the [same-code replay and admission review](V41_SCHEDULED_MAIN_IPVERSE_REPLAY_20261116.md). This does not change the five OPEN decisions or pin any disputed network.

## Publication-readiness review

The [isolated publication handoff](V41_PUBLICATION_READINESS_20261116.md) verifies that Draft #53 holds the disputed candidate before any snapshot tag is created against the clean current baseline. The two genuine public HTTPS controls still have no verified DNS address inside these five prefixes. A missing archive result, a route-origin change and divergent country labels each remain insufficient to settle the presence of a service. All five rows are still OPEN. This observation does not remove any prefix from the current public release.

## Raw collector follow-up, 16 Nov UTC

The periodic 08:00 UTC RIBs from [Moscow RRC13](https://data.ris.ripe.net/rrc13/2026.11/bview.20261116.0800.gz)
and [Stockholm RRC07](https://data.ris.ripe.net/rrc07/2026.11/bview.20261116.0800.gz)
both contain all five exact /24s under AS137410. The two collectors see
the adjacent control `177.29.252.0/24` under AS219305. The 23 contiguous
five-minute update files from each collector (08:00 inclusive to 09:55
exclusive UTC) contain no exact-prefix update or observed peer-session
loss affecting those routes. The prior concern about a lagging summary API
does not apply to these raw dump observations. It remains possible that
other peers saw changes in this interval.

Moscow's historical RIBs show the old origins at 00:00, no exact paths for
the five at 08:00, and AS137410 for all five at 16:00 UTC on 15 November.
The independently useful comparison is per peer and time, not a claim of
a global outage. All five **remain OPEN** because BGP does not establish
whether a customer-facing service in any of them works from a RU home ISP.

[Machine-readable raw collector evidence](V41_RAW_RIS_MRT_FOLLOWUP_20261116.json)
records source URLs, compressed SHA-256 values, time windows and exact
paths. It also documents the unrelated MOAS sighting difference between
the two collectors for the two disputed additions.
