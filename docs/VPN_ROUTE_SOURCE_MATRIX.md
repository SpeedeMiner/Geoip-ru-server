# VPN split-routing sources: coverage, provenance and candidate-build plan

**Research snapshot:** 2026-11-11  
**Baseline:** production unified DIRECT RU+BY+KZ v37, immutable release commit ac2e9a4322c0b7efe293983c88cf5b304771e4c5  
**Status:** isolated candidate builder added; CI will download pinned inputs and publish a review artifact. No production source, policy, geoip_RU.dat, release, or main changes.

## 1. Main finding

The current repository already has a substantial source collection, but it mixes different routing intents. Improving the final database requires adding coverage while preserving these distinctions:

- Geographic RU GeoIP: country/address-zone datasets. These form the geographic reference layer, but country registration or a GeoIP label is not proof of the physical location of every server.
- Named Russian service DIRECT: IP networks used by Russian services. Useful to prevent Russian bank, marketplace, government and media traffic from leaving through a foreign VPN. Not a general Russian country database; may include cloud, CDN or shared hosting ranges.
- Domain/service lists: FQDNs and domain suffixes. Improve a separate geosite/domain rule set and help discover service IPs, but DNS answers are dynamic and should not become permanent ownership claims.
- Reverse route / PROXY lists: destinations blocked in Russia or foreign services rejecting Russian exits. Their polarity is opposite to DIRECT; store separately and never import into the RU category.
- VPN node subscriptions: VLESS/VMess/Trojan/Shadowsocks server endpoints. These are proxy infrastructure, not destination-route data or GeoIP evidence.

The current v37 output is a legacy combined DIRECT category for RU+BY+KZ and selected company/affiliate networks. Preserve that behavior. A strict geographic RU database should be a separate future output, not a silent reinterpretation of the existing geoip:ru.

## 2. What v37 currently contains

The successful v37 canonical inventory run #218 verified one consistent immutable release snapshot:

| Metric | v37 |
|---|---:|
| Final RU/DIRECT exact CIDRs | 76,293 |
| Final RU/DIRECT IPv4 address union | 52,619,113 |
| Final RU/DIRECT IPv6 address union | 1,192,441,883,226,834,356,864,992 |
| Geographic RU+BY+KZ source CIDR inputs | 154,821 |
| Direct/whitelist candidate CIDR inputs | 133,213 |
| Selected-origin BGP input CIDRs | 23,564 |
| RU-RIR resource input CIDRs | 13,679 |
| Global ipverse 90-day exact prefixes | 520,065 |
| Accepted additional GeoIP provenance prefixes | 193 |

The builder already downloads these VPN/service candidate feeds:
- HXEHEX cidrwhitelist.txt (candidate-only).
- W1ZARDZ dist/ru-direct-ipv4.txt (candidate-only).

They are not missing from the repository. Their value is diagnostic and candidate-discovery only. The next step is to compare pinned source revisions, inspect companion feeds, classify individual prefixes and measure new address space—not blindly re-add them to final output.

The v37 source manifest recorded HXEHEX CIDR SHA-256 149d27a8e3502b95b9a378817854c87af6417c2a9bbf0b17eb8f7affef1f3868 and W1ZARDZ IPv4 SHA-256 deae4b8811b93c3d0997803da634ec8c75aa6ccdc4b5b7154e5aaeb7b3dcc739.

## 3. Newly compared VPN-routing feeds

| Source | Current public coverage facts | Usefulness | Limitation / decision |
|---|---|---|---|
| kyoresuas/ru-direct | Manifest generated 2026-11-11: Lite 356 IPv4 + 25 IPv6 CIDRs, 481 domains, 29 services; Standard 630 IPv4 + 74 IPv6, 1,683 domains, 90 services; Full 8,683 IPv4 + 2,168 IPv6. | New pinned comparison source; Lite/Standard reveal service-specific endpoints, Full offers broader country-zone comparator. | MIT declared. Three tiers are one publisher, not independent votes. Full is composite/ipdeny-correlated. |
| escapingworm/russia-whitelist | Small CIDR aggregate of Russian mobile-operator whitelists; current pinned file inspected. | New candidate layer for operator-whitelisted services and networks surviving mobile restrictions. | MIT declared. Correlated with HXEHEX/mobile whitelist evidence; operator routing is not country ownership. |
| hxehex/russia-mobile-internet-whitelist | v37 already imports cidrwhitelist.txt; repository also publishes ipwhitelist.txt host-IP companion and whitelist.txt domains. | Existing CIDR input plus new IP-only and domain discovery layers. | MIT declared. Availability/whitelist observations; host IPs are not broad country prefixes. |
| w1zardz/amnezia-vpn-russia-split-tunneling | Manifest generated 2026-11-11: 66 services, 1,159 domains, 946 compacted IPv4 CIDRs, 495,878 IPv4 addresses; source catalog has 17 external feed entries. | Useful method and service inventory: external-source aggregation followed by IP→ASN/known-service validation. | MIT declared. Existing v37 candidate feed; source groups correlated and historical import counts are not current coverage. |
| WhisperOfTheSteppe/ru-rules-dat | Release includes ru-ip.txt, domain list, Shadowrocket lists, sing-box rule sets and Xray GeoIP. README says IP set comes from ipdeny RU country zones. | Independent format/output benchmark and current country-zone comparison. | No repository license declared in inspected metadata; do not redistribute CIDRs until licensing clarified. Correlated with ipdeny. |
| lib4u/amnezia-tunneling-ru | Amnezia JSON with hostnames and resolved IP arrays; project claims 1,900+ Russian service domains and daily updates. | Domain-to-IP discovery; potential new service hosts and CDN endpoints missing from static lists. | Dynamic DNS answers, overlapping endpoints and stale-snapshot risk. Keep hostname→IP provenance in the audit sidecar; do not automatically promote to GeoIP. May overlap v2fly geosite. |
| jirnobruh/Split-Tunneling-Amnezia-for-Russia | Amnezia JSON with hostname, ip and ips values; last repo update older than the other feeds. | Another service-domain/IP snapshot for comparison and drift discovery. | No repository license found. Metrics-only; no prefix redistribution. |
| pvd-dog/russia-no-vpn-list | Pinned JSON contains 1,029 IPv4 prefixes, all `/24`; `hostname` and `ip` fields both contain the network, not a domain. | Broad network-candidate comparison only. | Not domain→IP evidence and not independent service confirmation. Keep metrics/review-only; every `/24` may include unrelated co-hosted destinations. |
| jutsu-dev/ru-route-lists | MIT; release updates every 3 hours. Provides RKN-restricted domains/IP sets and foreign-geoblock domains/IP sets. | Important reverse-polarity source for a future separate PROXY / foreign-exit route set. | Never add IP sets to RU DIRECT. README warns about shared CDN impact; domain lists safer first input. |
| itdoginfo/allow-domains | Russia/outside-raw.lst identifies RU-side domain routing; Russia/inside-raw.lst has opposite meaning. | Geosite/domain coverage and DNS discovery. | Domain-only; keep inside/outside polarity explicit. |
| UnRKN/ru-blocklist | Domains marked by maintainers as restricted over VPN / subject to Russian restrictions. | Reverse route/domain evidence for PROXY. | Not geographic RU or prefix admission; verify licensing before redistribution. |
| wlunlocker/vpn-configs | Public VLESS/VMess/Trojan/Shadowsocks endpoints and node subscriptions, grouped by exit country. | Understand actual VPN nodes and test endpoints, but not destination routes. | Exclude from GeoIP ingestion. Subscription strings contain credentials and third-party node parameters. |
| slimmi/amnezia-split-tunneling | Repository describes MaxMind GeoLite2 as primary and ipdeny as fallback. | Independent benchmark architecture for geographic country-zone comparison. | MaxMind account/data redistribution and repo license must be checked before use. |

## 4. Wider source graph from W1ZARDZ

W1ZARDZ config/external-sources.json describes a useful candidate-aggregation graph. It references:
- HXEHEX mobile CIDRs/domains;
- Escapingworm operator CIDRs;
- UnRKN VPN-domain flags;
- itdog Russia/outside domains;
- lib4u Amnezia;
- v2fly/domain-list-community RU service categories;
- Jirnobruh Amnezia;
- older Kyoresuas ru-bypass and essential lists;
- Pincetgore IP list;
- Kozlov domains;
- Egkodin RU sites;
- Supertico domains;
- PVD Dog;
- OpenCCK IP list;
- RockBlack RU route files.

A W1ZARDZ external-report.md snapshot dated 2026-09-12 reported historical raw→accepted counts: HXEHEX 30,228→266, operator whitelist 88→18, lib4u 1,532→262, Jirnobruh 768→142, old Kyoresuas list 8,799→725, PVD Dog 1,029→288, OpenCCK 1,449→251 and RockBlack 334→68. These are historical results, not current counts or approval to import. The report says the 1,000-network ceiling dropped 459 otherwise accepted networks. New builds must compute fresh counts and must not inherit this arbitrary ceiling.

The most useful W1ZARDZ architecture is its filter:
1. Parse source CIDR/IP/domain records.
2. Resolve current IP→ASN mapping.
3. Accept only ranges tied to an already verified service catalog.
4. Reject foreign, unknown, cross-ASN, already-covered, carrier, shared CDN/cloud, private and overbroad ranges.
5. Keep accepted and rejected counts, source hash and exact reason per source.

Improve this by retaining exact prefix and address-space delta, BGP observation timestamp/collector, RDAP holder, IRR and RPKI evidence. The service filter is a candidate gate, not geographic proof.

## 5. Isolated candidate build added

The experiment branch adds:
- tools/build_vpn_route_candidates.py
- tools/tests/test_vpn_route_candidates.py
- .github/workflows/vpn-route-candidate-build.yml
- docs/VPN_ROUTE_SOURCE_MATRIX.md
- docs/VPN_ROUTE_SOURCE_REGISTRY.tsv

The script downloads immutable commit-pinned sources, records SHA-256 and byte size, parses public IPv4/IPv6 CIDRs and Amnezia IP observations, and compares address-space coverage against pinned v37 production output.

The isolated candidate protobuf uses namespaced categories:
- ru_vpn_kyoresuas_lite
- ru_vpn_kyoresuas_standard
- ru_vpn_kyoresuas_full
- ru_vpn_w1zardz_direct
- ru_vpn_hxehex_cidr
- ru_vpn_hxehex_ip
- ru_vpn_operator_whitelist
- ru_vpn_export_union
- ru_vpn_new_vs_v37

These are not aliases for RU. Existing clients routing geoip:ru therefore do not silently change. Outputs include candidate_source_metrics.tsv, candidate_source_prefixes.tsv, candidate_new_vs_v37.txt and a manifest.

Amnezia hostname/IP observations are retained in a separate audit sidecar, not the candidate .dat. Broad CIDR and country-zone feeds remain metrics/review-only until exact prefixes are checked for shared hosting, origin ASN and overlap. License verification is not a project release gate; source attribution and immutable refs remain recorded. Sources in multiple tiers or a correlated group are not multiple independent confirmations.

## 6. Measured v37 candidate build results (2026-11-11)

The first successful policy-aware build is run **43017072072** (all CI steps passed). Its candidate artifact contains the protobuf, immutable source manifest, per-source metrics, source-prefix inventory and exact RIR residual coverage. The production baseline is unchanged.

- 11 pinned source inputs loaded successfully; the candidate union contains **183,820 unique CIDRs**.
- Compared with the legacy RU output alone, candidate address space adds **31,774,573 IPv4 addresses** and **11,532,729,195,086,697,206,485,771,878,400 IPv6 addresses**. These are comparison figures, not approved additions.
- After subtracting v37 RU, PRIVATE and approved BLOCKED carve-outs, the candidate union still contains **31,760,166 IPv4 addresses** and the same IPv6 remainder. This is a candidate-only set, not a production policy change.
- Source results are uneven. HXEHEX CIDR contributes 31,482,258 IPv4 addresses not in v37 RU, but HXEHEX CIDR is already a candidate-only production input; it is not a newly integrated source. The new HXEHEX host-IP companion contributes 122,974 IPv4 addresses versus RU alone and 122,948 outside RU+PRIVATE+BLOCKED. Escapingworm has only 79 IPv4 addresses new vs RU and zero remaining after current policy.

Per-source address space outside RU + PRIVATE + approved BLOCKED (the rows below overlap and **must not be summed**):

| Source | IPv4 addresses outside existing policy | Interpretation |
|---|---:|---|
| Kyoresuas Full | 329,004 | New geographic-composite comparison; ipdeny-correlated. |
| Kyoresuas Lite | 64 | Service-tier-only residue. |
| Kyoresuas Standard | 64 | Service-tier-only residue; same publisher as Lite/Full. |
| HXEHEX CIDR | 31,474,575 | Already present as candidate-only input in v37; same source bytes as v37 snapshot. |
| HXEHEX host-IP companion | 122,948 | New companion feed, host-level routes only. |
| W1ZARDZ Direct | 518 | Existing v37 candidate feed; changed pinned snapshot but limited additional space. |
| Escapingworm operator whitelist | 0 | All 79 new-vs-RU addresses are already covered by PRIVATE/BLOCKED or overlap. |
| Whisper (metrics-only) | 328,935 | ipdeny-correlated; unlicensed in inspected repo metadata, do not redistribute. |
| Lib4u / Jirnobruh (domain→IP, metrics-only) | 335 / 45 | Resolved service-host observations; export hostname/IP pairs for domain-level review. |
| PVD Dog (CIDR-only, metrics-only) | 27,433 | 1,029 `/24` networks; not domain-resolved observations. |

- **Kyoresuas Full** is the standout geographic residual comparator: it covers **320/320 IPv4 and 40/40 IPv6 RU-RIR residual prefix rows** after existing policy; exact CIDR matches are 214/320 IPv4 and 40/40 IPv6; unique residual address coverage is 100% in each family.
- **Whisper** covers 319/320 IPv4 residual rows, 213 exact CIDR matches and 99.922174% of unique IPv4 residual address space, but the repository has no declared license in inspected metadata and the dataset is ipdeny-derived. It is benchmark-only and its prefixes are not redistributed.

**Interpretation:** the Kyoresuas Full result identifies the feed lineage that appears to explain the entire registered-resource residual. It does not independently prove ownership or live route status: its country-zone component is ipdeny-correlated, and a country file may include static/registered ranges that are not currently announced. Before any production admission, exact candidates must be joined to the RIR residual ledger and checked against exact current RouteViews/RIPE RIS NLRI, per-origin VRP/RPKI maxLength, IRR route objects and holder/assignment evidence. The upstream data license/attribution for the embedded country-zone portion also needs confirmation despite the repository's MIT declaration.

Artifact: vpn-route-candidates-5, run #43017072072, SHA-256 999389acc931cfceca2f40a56fe947cf616465156c32aefce6c0271bf0c9d8c8. Candidate protobuf SHA-256: 0978561c1c3607ea4288724507a8544e715f8b36283dc04a43fe57bf546b0072. It contains namespaced ru_vpn_* categories and does not replace or mutate production geoip:ru.



**PVD Dog source-shape check (pinned snapshot):** all 1,029 rows parse as IPv4 `/24`; total covered address space is 263,424 addresses. No hostname row is a DNS name. These prefixes overlap 841 of 1,843 unique Lib4u host IPs and 512 of 755 unique Jirnobruh host IPs. They should not be counted as independent hostname-level service observations. The builder now exports the raw Amnezia hostname/IP/CIDR mapping sidecar for audit, but none of these metric-only feeds is added to the candidate protobuf.

## 7. Next improvements to final production build

1. Preserve existing semantics. Keep legacy RU+BY+KZ/company DIRECT unchanged. Introduce a separate strict geographic RU output and separate service-DIRECT output, with explicit policy and client mapping.
2. Use independent source groups, not raw source count. Grimbird+Digne remain one group; HXEHEX+Escapingworm are one mobile/operator group; Kyoresuas tiers are one publisher; ipdeny-derived country feeds are one group.
3. Improve service-IP validation. Add IP→ASN snapshots (e.g. iptoasn) plus exact RIB origin. For a service candidate, require service catalog and verified ownership/control of route; reject or isolate global CDN, cloud, transit, hosting and carrier aggregates. A service DIRECT entry may be legitimate when not general geographic RU, but it must be clearly typed.
4. Add exact route evidence. Use RouteViews and RIPE RIS exact NLRI captures, timestamp, collector and peer counts. ipverse rolling 90-day aggregate remains discovery/history only. Match RPKI VRP/maxLength to same snapshot.
5. Add domain layer. Parse v2fly/geosite, itdog outside-raw, HXEHEX domains and service catalogs into independent geosite output. Do not flatten domains into CIDRs without DNS time, answer set, ASN and source provenance.
6. Add reverse PROXY layer. Treat jutsu/RussiaFancyLists and UnRKN as separate negative-polarity sets; prefer domains before IP ranges. Preserve existing blocked carve-out policy; do not import every RKN IP list into geographic builder.
7. Create a source graph. Store source IDs, immutable refs, content SHA-256, license, cadence, correlation group, polarity, coverage and parser version. Mirrors are transport fallbacks, not independent corroboration.
8. Keep exact CIDR and address-space diffs. A /23 replacing two /24 entries may change CIDR count without changing addresses; review both. Every proposed change includes prefix-level provenance and reason.
9. Build all candidates in parallel first. Publish isolated artifact and compare to production baseline. Only reviewed exact-prefix decisions can be promoted via separate production change.

## 8. Safety and branch boundaries

This experiment does not edit .github/workflows/blank.yml; production inputs; company ASN allowlist; DIRECT or PRIVATE policy; production geoip_RU.dat; production tags/releases; main; PR #5, PR #6 or PR #7. It does not auto-promote any candidate CIDR.

The candidate branch and PR must remain Draft until source coverage artifact and exact delta are reviewed. Any merge into main is not a no-op: production blank.yml runs on pushes to main and publishes a new release even after docs-only merges.
