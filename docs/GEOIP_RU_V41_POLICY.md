# v41 integration policy — RU+BY+KZ unified DIRECT

Status: **v41 already released. The v41.2 historical policy is a candidate stacked on the v41.1 service/region policy and publication hardening.**

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

1. PRIVATE wins over every DIRECT rule or protected prefix.
2. CORE_CORPORATE selected-origin prefixes are exempt from approved exact/hard **and** resolver-only blocks, except PRIVATE.
3. Only literal IPv4 `/32` and IPv6 `/128` entries from Kyoresuas Standard, HXEHEX and W1ZARDZ inside an RU RIR resource may override hard blocks. Hosts are selected from the original rows before intersection or aggregation. All other service CIDRs, including Escapingworm operator entries of any length and even IPv4 `/25–/31` or IPv6 `/65–/127`, can override only the current `ipresolve.lst` layer. W1ZARDZ resolver protection uses the intersection with RU, BY and KZ RIR resources. A W1ZARDZ host in BY/KZ does not acquire a new hard-block exception.
4. SHARED_INFRA and selected RIR-RU/BY/KZ BGP origins have resolver-only protection. The existing hard layer (`ip.lst`, bounded `subnet.lst`, curated Telegram blocks and the pinned unclassified v38 baseline) takes precedence unless CORE or an eligible literal service host independently applies.
5. Any other block is subtracted from DIRECT as before. No further `ipsum.lst` /24 is automatically carved.
6. RIR origin registration is **not** proof of a company relationship. No recursive import of upstream/peer/affiliate ASNs.

The build uses the actual BY/KZ ASN registry alongside the RU registry, without checking physical location or creating company exemptions. The published sidecar retains the original `geoip_RU_v41_rir_ru_and_company_origin_prefixes.txt` filename for compatibility and records both registry hashes. No change to the corporate registry is required for the already registered BY/KZ networks.

`ip.lst` is itself DNS-derived according to Antifilter. Its existing hard classification is preserved. These source memberships do not prove an active direct IP block, and absence from feeds is not evidence of unblocking.

### v41.2 historical-only IPv4 hosts

A v38 baseline hard/unclassified host may move to the resolver-only layer when it is an IPv4 `/32`, is covered by a selected RU/BY/KZ BGP origin or SHARED_INFRA, and has no address-space overlap with any current `ip.lst`, `ipresolve.lst`, `subnet.lst` entry or curated Telegram route. A covering CIDR in one of those sources vetoes the change even when that CIDR is review-only. The rule never moves whole subnets or IPv6 hosts. If current ipresolve is missing, or a current required feed has tolerated malformed rows, no new reclassification takes place on that build. Invalid required feeds still fail under the existing thresholds.

The original approved union and its provenance remain unchanged. The new `v38-historical-only-regional-resolver` label records the policy decision in the resolver sidecar and source statistics. It does not assert that the original entry came from DNS or that the destination is now reachable. Remaining overlapping hard prefixes and PRIVATE still take precedence. No publication asset name changes.

## Hydra DIRECT / WHITELIST expansion

- The upstream `hydraponique/roscomvpn-geoip` file already enters the v37 builder, but its `direct` and `whitelist` categories were previously counted only as diagnostic candidates.
- Both categories are now explicitly admitted in the v41 overlay as **routing intent**, not as RU geolocation, first-party corporate origin, or unconditional block exemption.
- The source is the same fetched `hydra-geoip.dat` used by the base builder. Its SHA-256, category counts, source-level metrics and exact prefix provenance are recorded.
- Eligibility is `(Hydra DIRECT ∪ Hydra WHITELIST) − PRIVATE − effective v41 blocked set`. Hydra does **not** override hard/exact/legacy/RIR block precedence or create a new class of corporate protected ASN.
- The independent validator checks full eligible Hydra address-space inclusion in the final `geoip:RU`, including IPv4 and IPv6, and verifies the source hash. Missing categories or a default route fail closed.
- Because Hydra may contain non-RU/CDN routing intent, this policy broadens the meaning of the RU routing bucket deliberately; review the exact resulting address delta before production rollout.

## Data and validation contracts

The active `geoip_RU.dat` candidate must contain only RU and PRIVATE, with zero overlap. The resulting RU and effective non-protected blocked sets must be disjoint. Separate masks must be SHA-256 pinned to their source files; source file handles and all output sidecars must be validated independently.

All received but unverified `RPKI/RDAP/IRR` audit candidates remain review-only. PR #5 and `feature/reachability-full-ru-kz-by` are excluded entirely from this task.

## Publication boundary

The existing v41 production workflow runs on main pushes and a daily schedule. This Hydra change is isolated in a PR: production remains unchanged until reviewed and merged. The released v41 tag remains available as a rollback point; publication of the expanded dataset requires a green candidate and explicit address-delta review.
