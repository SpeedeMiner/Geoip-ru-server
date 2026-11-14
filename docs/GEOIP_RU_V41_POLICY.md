# v41 integration policy — RU+BY+KZ unified DIRECT

The policy below describes the v41 publisher and the regional/block-provenance revision in PR #26. The rolling release and run-specific snapshots identify the deployed build.

## Preservation of v39 and v40

v41 branches from PR #12's corrected v39 head, preserving:
- Corrected Russian-company ASN registry (removes 13 falsely attributed or unverified ASN names).
- RIR-RU **selected-origin** routes from the pinned ipverse observation file, not loose GeoIP geolocation assumptions.
- Kyoresuas Standard, HXEHEX host IPs and Escapingworm operator-service DIRECT inputs.
- W1ZARDZ DIRECT prefixes only where they overlap RIR-RU address resources.
- Approved Antifilter ip.lst / ipresolve.lst / bounded subnet.lst and curated Telegram sources, with `ipsum.lst` review-only.
- v37 base GeoIP RU/PRIVATE, PRIVATE precedence, full provenance and independent read-back validation.
- Corrected v37 quality-report source for the prefix-audit workflow; that audit's 57-versus-56 target selection remains a separate unresolved issue.

v41 imports from v40:
- Version-controlled two-class ASN policy `CORE_CORPORATE` and `SHARED_INFRA`.
- Source-separated exact/hard and resolver-only blocked-address datasets.
- Pinned v38 approved blocked baseline, treated as **unclassified hard** rather than assuming every row came from ipresolve.
- Deterministic exact-origin class extractor, class-specific origin sidecars, independent protobuf/policy validator.
- Seven additional corrected company ASN registry rows available in the v40 review work; verified candidates remain reviewable as source records.

## Explicit precedence for conflicts

1. PRIVATE always wins. The pinned official Telegram set remains non-exempt.
2. Current bounded Antifilter `subnet.lst` entries and separately reviewed direct IP/subnet registry records are hard. They cannot be overridden by CORE, SHARED, regional origin, or service masks. The subnet feed is an upstream signal, not a verified direct lookup of every row in the official registry.
3. Antifilter [documents](https://antifilter.download/) `ip.lst` and `ipresolve.lst` as DNS-derived. They, and unverified historical v38 entries, remain in the source union and advisory layer. They cannot carve selected RU/BY/KZ origins, registered RU/BY/KZ resource ranges, corporate/shared origins, the existing service resolver masks, or the exact reviewed operator CIDRs. Outside those protections, prior resolver filtering still applies. `ipsum.lst` remains review-only.
4. `.github/data/v41-reviewed-rkn-ip-records.tsv` accepts only manually reviewed direct IP or subnet records with canonical CIDR, review date and evidence URL. Domain/URL-only evidence is not sufficient. The 2026-11-13 [reviewed evidence extract](v41-pr26-direct-ip-evidence-20261113.json) ties the exact host rows to individual decision metadata in a dated registry mirror snapshot. The extract is not an official signed export, and the snapshot is not a rolling build input. Automatic size limits stay in place.
5. REG.RU AS197695 is classified as SHARED_INFRA and is admitted only by the existing regional ASN selection, not by its new classification. The same class already covers the reviewed origins of Timeweb, Selectel and DDoS-Guard. No recursive import of peer/upstream/tenant ASNs. Registration is routing evidence, not a per-tenant reachability guarantee.

The v37 base and approved-union filenames remain unchanged. The base still subtracts the full union. The v41 overlay restores eligible regional/service coverage against advisory evidence and re-applies the effective exclusions. No source is removed, no GeoSite policy is edited and no checked domain is treated as a direct IP block. The historical raw feeds are retained for attribution, not as current confirmation.

## Hydra DIRECT / WHITELIST expansion

- The upstream `hydraponique/roscomvpn-geoip` file already enters the v37 builder, but its `direct` and `whitelist` categories were previously counted only as diagnostic candidates.
- Both categories are now explicitly admitted in the v41 overlay as **routing intent**, not as RU geolocation, first-party corporate origin, or unconditional block exemption.
- The source is the same fetched `hydra-geoip.dat` used by the base builder. Its SHA-256, category counts, source-level metrics and exact prefix provenance are recorded.
- Eligibility is `(Hydra DIRECT ∪ Hydra WHITELIST) − PRIVATE − effective v41 blocked set − reviewed regional admission exclusions`. Hydra does **not** override hard/exact/legacy/RIR block precedence or create a new class of corporate protected ASN.
- The independent validator checks full eligible Hydra address-space inclusion in the final `geoip:RU`, including IPv4 and IPv6, and verifies the source hash. Missing categories or a default route fail closed.
- Because Hydra may contain non-RU/CDN routing intent, this policy broadens the meaning of the RU routing bucket deliberately; review the exact resulting address delta before production rollout.

## Data and validation contracts

The active `geoip_RU.dat` candidate must contain only RU and PRIVATE, with zero overlap. The resulting RU and effective non-protected blocked sets must be disjoint. Separate masks must be SHA-256 pinned to their source files; source file handles and all output sidecars must be validated independently.

All received but unverified `RPKI/RDAP/IRR` audit candidates remain review-only. PR #5 and `feature/reachability-full-ru-kz-by` are excluded entirely from this task.

## Publication boundary

The existing v41 production workflow runs on main pushes and a daily schedule. Pull-request builds cannot publish. Main builds compare the candidate independently with the prior release before updating the rolling artifact and creating a run-specific snapshot. Use a run-specific snapshot, not the rolling link, for rollback.

## Reviewed operator prefixes and geography-only inputs

The exact CIDRs in [the reviewed operator table](../.github/data/v41-reviewed-operator-prefixes.tsv) are independently reviewed regional routes. They receive resolver-only protection, not an ASN-wide exemption. Confirmed direct IP/subnet evidence, official Telegram ranges, PRIVATE and explicit regional admission exclusions still take precedence. Both validators check the table's SHA-256 and require coverage of every eligible reviewed address.

v2fly and Loyalsoldier country labels alone do not create a resolver exemption. The v37 geographic baseline and the v41 regional and service restoration layers are distinct. Restoring all geography-only coverage would change DIRECT policy and could restore foreign/shared networks. Review exact assignments separately.

Six exact reviewed entries recover 110 IPv4 addresses in the 2026-11-13 fixed-input replay. No address beyond the explicit rows is restored.

| Prefix | Origin | Independent registration and routing evidence | IPv4 restored |
|---|---|---|---:|
| `2.26.8.0/24` | `AS207957` | [Exact RU assignment](https://rdap.db.ripe.net/ip/2.26.8.0/24), [RIS](https://stat.ripe.net/data/routing-status/data.json?resource=2.26.8.0%2F24) | 2 |
| `31.76.71.0/24` | `AS207957` | [Exact RU assignment](https://rdap.db.ripe.net/ip/31.76.71.0/24), [RIS](https://stat.ripe.net/data/routing-status/data.json?resource=31.76.71.0%2F24) | 1 |
| `77.239.107.0/24` | `AS207957` | [Exact RU assignment](https://rdap.db.ripe.net/ip/77.239.107.0/24), [RIS](https://stat.ripe.net/data/routing-status/data.json?resource=77.239.107.0%2F24) | 4 |
| `178.250.186.0/24` | `AS207957` | [Exact RU assignment](https://rdap.db.ripe.net/ip/178.250.186.0/24), [RIS](https://stat.ripe.net/data/routing-status/data.json?resource=178.250.186.0%2F24) | 2 |
| `193.109.246.0/23` | `AS204343` | [Exact RU assignment](https://rdap.db.ripe.net/ip/193.109.246.0/23), [RIS](https://stat.ripe.net/data/routing-status/data.json?resource=193.109.246.0%2F23) | 48 |
| `195.216.243.0/24` | `AS204343` | [Exact RU assignment](https://rdap.db.ripe.net/ip/195.216.243.0/24), [RIS](https://stat.ripe.net/data/routing-status/data.json?resource=195.216.243.0%2F24) | 53 |


The [SERV.HOST geofeed](https://status.serv.host/geofeed/subnet.csv) corroborates the four AS207957 entries. The two Compubyte ranges are exact RU assignments to the origin holder, with the UCOZ-NET /23 covered by two same-origin /24s and COMPUBYTE-NET announced as a /24. The larger historical ipverse aggregates do not widen the approved scope.

The [second prefix review](v41-geo-only-operator-evidence-20261114.json) adds 22 exact RU rows (HOSTKEY, FIRSTSERVER, IHOR/PSERVERS and TIME-HOST). Every row has an exact RU registry object and a matching RIS announcement with no conflicting observed origins. The first three operators have matching exact geofeed entries. TIME-HOST has exact assignments to ORG-TH111-RIPE and matching RIS origins. No ASN-wide action. Keep the conflicting IHOR `94.142.141.0/24` and `193.124.191.0/24` out of this exception table. The existing exact hard entry `185.174.138.82/32` still takes precedence inside the reviewed FIRSTSERVER /24.

The [third prefix review](v41-geo-only-operator-followup-20261114.json) adds 16 exact RU assignments (six FIRSTSERVER and ten IHOR/PSERVERS). Each assignment is corroborated by a registry-linked operator geofeed and a matching exact RIS route or same-origin more-specifics that cover the complete assignment. The current delta is +19 IPv4, all from the original review cohort. At that checkpoint the operator table allowed at most 64 rows, with the existing canonical, non-overlap and prefix-size rules unchanged. This is a cap for manually reviewed entries, not an automated import.

The [fourth prefix review](v41-geo-only-operator-rukz-20261114.json) fills the 16 available slots under the unchanged 64-row cap with exact RU/KZ assignments. The checked evidence is RIPE RDAP, the registry-linked operator geofeed and an exact same-origin RIS route. It restores 59 IPv4 addresses already in the DNS-only review cohort. The evidence file also records 14 separately verified /24s that were initially deferred. The CY-assigned 194.67.193.0/24, mixed-country records and non-exact assignment ranges do not receive protection.

The release admits all 14 deferred /24s from that same evidence file. The table has 78 manually reviewed rows under a limit of 80. The additional rows only exempt DNS-derived exclusions, never hard evidence, PRIVATE, Telegram, or explicit regional admission exclusions. The remaining unconfirmed geography-only candidates are not admitted.

## Reviewed regional admission conflicts

The v41 overlay excludes exact IPv4 prefixes in [the reviewed admission table](../.github/data/v41-regional-admission-exclusions.tsv) from the emitted RU category after candidate assembly. This does not modify RIR inventories, select or reject an entire ASN, add an output category, or alter RKN, Telegram or resolver block inputs and masks. The list is local and reviewed. It is not populated by a country feed or automated geographic filtering. A regional parent allocation alone is not enough for the listed cases because exact or more-specific assignment records and the observed origin point outside the region.

- `185.49.68.0/22` has BY delegated registration. Its six [more-specific RIPE assignments](https://rdap.db.ripe.net/ip/185.49.70.0/25) cover the whole block and show DE. [RIPE RIS](https://stat.ripe.net/data/routing-status/data.json?resource=185.49.68.0%2F22) sees AS28753 for the /22 and all four /24s.
- `185.17.120.0/22` and `195.54.32.0/23` have RU delegated registration. Their exact [RDAP /22](https://rdap.db.ripe.net/ip/185.17.120.0/22) and [RDAP /23](https://rdap.db.ripe.net/ip/195.54.32.0/23) objects show DE and [RIPE RIS](https://stat.ripe.net/data/prefix-overview/data.json?resource=195.54.32.0%2F23) observes AS28753 for the /23, as for the /22. This is prefix-specific operational evidence, not physical geolocation of every IP.
- Inside RU-delegated `145.249.0.0/16`, exact RIPE records for [`145.249.0.0/18`](https://rdap.db.ripe.net/ip/145.249.0.0/18) and [`145.249.64.0/19`](https://rdap.db.ripe.net/ip/145.249.64.0/19) identify Syrian Telecom and country SY. [RIPE RIS](https://stat.ripe.net/data/routing-status/data.json?resource=145.249.0.0%2F18) observes four adjacent /20s from AS29256 covering the /18. The [/19](https://stat.ripe.net/data/routing-status/data.json?resource=145.249.64.0%2F19) is announced by AS29256 directly.
- Exact [RDAP for `145.249.96.0/21`](https://rdap.db.ripe.net/ip/145.249.96.0/21) identifies Media Broadcast Satellite GmbH in DE. [RIPE RIS](https://stat.ripe.net/data/routing-status/data.json?resource=145.249.96.0%2F21) observes AS211095 for the /21 and the observed /24 child. The rest of `145.249.0.0/16` is not excluded, including the `145.249.128.0/17` Kazakhstan route.
- Inside the RU-delegated `31.204.0.0/18`, [exact RIPE RDAP](https://rdap.db.ripe.net/ip/31.204.8.0/21) shows `31.204.8.0/21` as `US-FIXED`, country US, with a WS Telecom technical contact and no registered child assignments. [RIPE RIS](https://stat.ripe.net/data/routing-status/data.json?resource=31.204.8.0%2F21) observes only AS209372 on the exact /21 and no more-specific routes. Keep other ranges, including [`31.204.2.0/24`](https://rdap.db.ripe.net/ip/31.204.2.0/24), an RU assignment with the same origin. Do not use AS209372 as a country-wide exclusion.
- Inside the KZ-delegated `109.238.160.0/20`, [exact RIPE RDAP](https://rdap.db.ripe.net/ip/109.238.168.0/21) shows `109.238.168.0/21` sub-allocated to IPXO with country US. Its two covering child assignments [`109.238.168.0/22`](https://rdap.db.ripe.net/ip/109.238.168.0/22) and [`109.238.172.0/22`](https://rdap.db.ripe.net/ip/109.238.172.0/22) also record US. [RIPE RIS](https://stat.ripe.net/data/routing-status/data.json?resource=109.238.168.0%2F21) observes only AS26548 ([PureVoltage](https://www.peeringdb.com/asn/26548)) on the exact /21 and no more-specific routes. Do not expand the exclusion to the other /21 or to the ASN.
- [RIPE RDAP](https://rdap.db.ripe.net/ip/31.204.16.0/21) records the exact `31.204.16.0/21` as US-FIXED with New York remarks and no more-specific assignments. The two [RIPE RIS child routes](https://stat.ripe.net/data/routing-status/data.json?resource=31.204.16.0%2F21) are both AS213541 and cover the /21.
- RIPE RDAP records `31.204.32.0/20` and `31.204.56.0/21` as [WSAU /20](https://rdap.db.ripe.net/ip/31.204.32.0/20) and [WSAU /21](https://rdap.db.ripe.net/ip/31.204.56.0/21), both AU, with no registered child assignments. The [WS Telecom geofeed](https://ws-sdn.net/feed/wssdnfeed.csv) corroborates AU for both exact ranges. [RIPE RIS](https://stat.ripe.net/data/routing-status/data.json?resource=31.204.32.0%2F20) sees AS9009 at the /20 and both /21 child routes from AS213541, covering the /20. The [separate /21](https://stat.ripe.net/data/routing-status/data.json?resource=31.204.56.0%2F21) is originated directly by AS213541. The table stores the origin covering the full ranges at longest match, not an assertion of exclusive origin across less-specific routes.
- Within the RU-delegated MnogoByte `212.124.96.0/19`, exclude only [`212.124.106.0/24`](https://rdap.db.ripe.net/ip/212.124.106.0/24), an exact US DIGITALONE-NET assignment with no registered children and an exact [AS47328 RIS route](https://stat.ripe.net/data/routing-status/data.json?resource=212.124.106.0%2F24). Other covering routes returned only the parent RDAP allocation, with a DE country value and a RU registrant. No exclusion of the parent, adjacent `212.124.107.0/24` or whole ASN.
- `31.204.28.0/22` stays in DIRECT for this revision. Its exact US assignment and foreign origin are noted, but the holder remains RU-associated and the operator geofeed does not cover it. Retain the rest of the unresolved queue without a bulk change.
