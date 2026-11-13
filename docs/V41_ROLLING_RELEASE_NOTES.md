# GeoIP DIRECT RU+BY+KZ CLIENT v41 — Regional and Service DIRECT

## Routing policy
- Exactly two GeoIP categories are emitted: `RU` and `PRIVATE`.
- `RU` is the unified DIRECT bucket for RU+BY+KZ regional address resources, regional GeoIP/BGP layers, and named service-direct destinations. Physical GeoIP location is not an admission gate.
- `PRIVATE` always wins over DIRECT.
- CORE_CORPORATE exact origin prefixes are protected from all approved RKN-derived inputs.
- SHARED_INFRA origins are protected only from current resolver-derived ipresolve candidates; exact ip.lst, bounded subnet.lst and ineligible v38 hard records still carve them.
- MOAS receives CORE_CORPORATE precedence when any exact origin is CORE; otherwise a SHARED_INFRA origin receives resolver-only protection.
- RIR RU/BY/KZ registration is not proof of corporate ownership and does not create a blanket block exception.
- PRIVATE retains absolute precedence for both classes.

## Regional resource and BGP layers
- v37 geographic/ASN sources remain the trusted starting point.
- v41 additionally imports allocated/assigned/legacy RU, BY and KZ address resources from the five RIR delegated-stat snapshots.
- RIR country is resource-registration evidence, not physical geolocation or proof of current BGP reachability; route observation remains separately reported.
- Only CORE company prefixes and eligible literal service hosts can override hard blocks; SHARED and selected RIR origins can override only the ipresolve layer.

## Service DIRECT outside geolocation
- Kyoresuas `ru-standard` service prefixes are imported with per-service category/name/ASN/domain provenance.
- W1ZARDZ service-direct, HXEHEX exact host-IP whitelist, and Escapingworm operator whitelist prefixes are separately attributed.
- These feeds are treated as service/availability intent, not geographic proof. Their prefixes are still subject to PRIVATE and RKN exclusions.
- Service-source coverage and exact address-space deltas are published in `geoip_RU_v41_source_metrics.tsv` and `geoip_RU_v41_prefix_provenance.tsv`.

## RKN blocked destinations
- Existing exact-host Antifilter `ip.lst` and `ipresolve.lst`, bounded `subnet.lst`, and curated Telegram prefixes remain active.
- A v38-only IPv4 /32 can move from hard to resolver-only inside a selected RU/BY/KZ origin or SHARED mask when none of the three current Antifilter feeds or curated Telegram prefixes covers it. The approved union is unchanged.
- v41 downloads Antifilter Download `ipsum.lst` as a review-only /24 summary of individual blocked IPs; it is not automatically carved because each /24 may route unrelated shared-hosting/CDN addresses through VPN.
- The report publishes the potential DIRECT address-space impact of these /24 candidates in `geoip_RU_v41_blocked_provenance.tsv`; only exact-host and bounded subnet exclusions already approved by the v37 policy are automatically applied.
- Community Antifilter and Re-filter suggestions remain review-only; privacy/telemetry labels do not change DIRECT.
- The no-BGP public-source fallback cross-checks pinned bol-van/rulist ipban4 vs resolved4 and correlated prebuilt datasets; it does not claim or infer Antifilter community 65444:210 membership.
- BGP registration is not a v41 release gate. All 360 new Lib4u/Jirnobruh host-IP candidates remain review-only; shared CIDR matches are not bulk-carved or promoted.
- If Antifilter ipresolve.lst is empty/unavailable, v41 carries forward the SHA-256-pinned v38 approved block snapshot (3033248ea54cb298bafded25ddcd2805d5f0e7ac / df909b12b985b23080075821cedc5e2f73b7b1f89abcd9950293b400ce1e4a5d); no v38 hard entries are reclassified on that build.
- Full pinned refs, candidate-match counts, enrichment limitations and source lineage are documented in [V41 public-source cross-check](https://github.com/SpeedeMiner/Geoip-ru-server/blob/feature/geoip-direct-rukzby-v41-integration/docs/V39_PUBLIC_RKN_SOURCE_CROSSCHECK.md).
- GeoIP cannot distinguish unrelated domains on the same IP; domain-only RKN rules remain a separate client geosite layer.

## Audit outputs
- `geoip_RU_quality_report.txt` records final v41 address coverage and the exact new-vs-v37 delta after PRIVATE and RKN policy.
- `geoip_RU_v41_manifest.json` records immutable source refs, source hashes and output SHA-256.
- `geoip_RU_BY_KZ_rir_registered_prefixes.tsv` retains country, RIR and resource-status provenance.
- The final client file remains `geoip_RU.dat` with `geoip:RU` and `geoip:PRIVATE` only.
- `geoip_RU_company_asn_bgp_prefixes.txt` lists exact prefix-level company exceptions; it does not exempt whole ASNs outside the selected-origin snapshot.

## Attribution and limitations
- Preserve v2fly/geoip CC-BY-SA-4.0 and DB-IP CC-BY-4.0 notices, plus upstream licenses/attributions for service feeds.
- RIR registration, BGP announcements, service association and RKN block evidence are distinct signals and are reported separately.
- RIR RU/BY/KZ selected origin prefixes receive an ipresolve-only exception. Only CORE and explicitly listed service hosts can override hard blocks.
