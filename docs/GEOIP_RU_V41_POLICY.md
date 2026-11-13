# v41 integration policy — RU+BY+KZ unified DIRECT

Status: **v41 already released. This provenance-aware revision is a candidate and does not replace the published v41 yet.**

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
3. Antifilter [documents](https://antifilter.download/) `ip.lst` and `ipresolve.lst` as DNS-derived. They, and unverified historical v38 entries, remain in the source union and advisory layer. They cannot carve selected RU/BY/KZ origins, registered RU/BY/KZ resource ranges, corporate/shared origins, or the existing service resolver masks. Outside those protections, prior resolver filtering still applies. `ipsum.lst` remains review-only.
4. `.github/data/v41-reviewed-rkn-ip-records.tsv` accepts only manually reviewed direct IP or subnet records with canonical CIDR, review date and evidence URL. Domain/URL-only evidence is not sufficient. The 2026-11-13 [reviewed evidence extract](v41-pr26-direct-ip-evidence-20261113.json) ties the exact host rows to individual decision metadata in a dated registry mirror snapshot. The extract is not an official signed export, and the snapshot is not a rolling build input. Automatic size limits stay in place.
5. REG.RU AS197695 is classified as SHARED_INFRA and is admitted only by the existing regional ASN selection, not by its new classification. The same class already covers the reviewed origins of Timeweb, Selectel and DDoS-Guard. No recursive import of peer/upstream/tenant ASNs. Registration is routing evidence, not a per-tenant reachability guarantee.

The v37 base and approved-union filenames remain unchanged. The base still subtracts the full union. The v41 overlay restores eligible regional/service coverage against advisory evidence and re-applies the effective exclusions. No source is removed, no GeoSite policy is edited and no checked domain is treated as a direct IP block. The historical raw feeds are retained for attribution, not as current confirmation.

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
