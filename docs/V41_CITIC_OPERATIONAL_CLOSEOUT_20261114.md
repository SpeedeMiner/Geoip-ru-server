# v41 CITIC exact IPv6 operational closeout

**Decision — keep the ten /128s in the audit fixture and leave production unchanged.** The operator geofeed and forward-confirmed DNS identify the candidates as backbone routers in Moscow and Saint Petersburg. The available evidence does not identify a public application destination among them. No claim is made about private services or the operator's management plane.

## What the operational follow-up established

- A fresh [Globalping result](https://globalping.io/measurements/2X1krVmFousGPwwUc00021VCr) returned three of three ICMP replies to the exact IPv6 literal `2001:ad0:cff::6` from one Moscow Timeweb probe, AS9123. Average RTT was 1.485 ms. The other nine exact IPv6 addresses were not measured. The [machine-readable decision](v41-citic-operational-decision-20261114.json) records the quota and other measurement limits, API response digest, historical positive control and per-address disposition.
- The [Moscow RIS observation](v41-citic-ipv6-ris-local-20261114.json) sees the AS3327 /32 via four IPv6-next-hop paths. A covering announcement and a ping to one host do not prove reachability of the others, and neither shows that users connect to these addresses as application endpoints. Xray matches the destination of the connection, not intermediate hops that forward packets.
- Of [15 independently identified operator/service controls](v41-citic-ipv6-service-attribution-20261114.json), none of the 17 distinct DNS answers is one of the ten IPv6 candidates. The Russian operator domain already matches GeoSite RU and its A and AAAA are in GeoIP DIRECT. All three separately verified AS12976 regional prefixes are fully present.
- The [fixed-source parity check](v41-citic-fixed-hydra-parity-20261114.json) finds all 20 A answers of the ten Russian loopback names in the v37 base, the frozen Hydra DIRECT category, and the released v41 DAT. None of their ten AAAA answers appears in the v37 base or either frozen Hydra routing category, and none is in the effective block set. The asymmetry is missing IPv6 coverage in these checked source layers, not a v41 resolver-block regression.
- No blanket admission follows from those results. The mixed `2001:ad0:cff::/48` contains 52 operator-labelled router addresses in the checked archive, including 41 nonregional controls and the separate Almaty control. None of the 42 control addresses changes route in the shadow. The /48 has no production DIRECT address and no effective block or PRIVATE overlap. A blanket admission would therefore change far more than the ten reviewed destinations, including those controls.

## Actual Xray results

| Fixed input to Xray v26.7.28 | Route changes with shadow DAT |
| --- | --- |
| AsIs, 71 destinations checked against each DAT | Only the ten exact IPv6 literals change, PROXY to DIRECT |
| IPOnDemand and UseIPv4, 11 names | None |
| IPOnDemand and UseIP, 11 names | None |
| IPOnDemand and UseIPv6, 11 names | Ten RU names change, PROXY to DIRECT. Almaty stays PROXY. |

These are observations of a fixed rule order in the matcher. They are not a test of live outbound address selection, the user's full Xray config or public application reachability. Both route tags end at local SOCKS sinks. DNS lookups in the three IPOnDemand cases use the checked-in answers served on localhost.

Recreate the shadow DAT as described in the [previous closeout](V41_IPV6_NON_DNS_CLOSEOUT_20261114.md). Use the fixed released v41 DAT, [Xray Linux x64 v26.7.28](https://github.com/XTLS/Xray-core/releases/tag/v26.7.28) and the [fixed GeoSite Light asset](https://github.com/SpeedeMiner/Geosite-ru-light/releases/tag/latest-optimized) with the digests recorded by the replay script. The script rejects changed inputs and uses only temporary files and local sockets.

```bash
python3 .github/scripts/replay_v41_citic_xray.py \
  --xray /path/to/xray \
  --fixed /path/to/released/geoip_RU.dat \
  --shadow /tmp/v41-citic-shadow-20261114/candidate/geoip_RU.dat \
  --geosite /path/to/geosite_RU.dat
```

Expected output is 142 AsIs and 66 IPOnDemand routing observations reproduced locally. The audit suite passed 148 tests. Production rolling and immutable releases and the release ref returned identical DAT bytes. No publication, branch merge, input or threshold change was made in this follow-up.

If an actual user-facing service or an explicit routing requirement for operator management addresses appears, revisit just that destination with its exact address family. Additional ICMP alone would refine reachability coverage and would not establish such a requirement. The prior IPv4 and other IPv6 hold cohorts stay closed.
