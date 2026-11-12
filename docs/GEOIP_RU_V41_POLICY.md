# v41 integration policy — RU+BY+KZ unified DIRECT

Status: **candidate / Draft PR only**. No release has been authorized or published by this branch.

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
3. Vetted Russian service prefixes from Kyoresuas Standard, HXEHEX and Escapingworm are exempt from approved exact/hard and resolver-only blocks, except PRIVATE. W1ZARDZ must overlap an RU RIR resource first.
4. SHARED_INFRA origin prefixes and RIR-RU selected-origin prefixes have resolver-only protection: exact `ip.lst`, bounded `subnet.lst`, curated Telegram blocks and the unclassified pinned v38 baseline still apply. This intentionally resolves the v39/v40 policy conflict without granting blanket hard-block exceptions to access/transit/hosting providers.
5. Any other block is subtracted from DIRECT as before. No further `ipsum.lst` /24 is automatically carved.
6. RIR origin registration is **not** proof of a company relationship. No recursive import of upstream/peer/affiliate ASNs.

This is a policy change from the broader v39 PR #12 proposal, which protected RIR origins from all block sources. The v39 source and tests are retained in the branch, while v41 explicitly restricts RIR protection to resolver-only to avoid false DIRECT routing of blocked hosted addresses. This conflict must be reviewed using candidate provenance before production release.

## Data and validation contracts

The active `geoip_RU.dat` candidate must contain only RU and PRIVATE, with zero overlap. The resulting RU and effective non-protected blocked sets must be disjoint. Separate masks must be SHA-256 pinned to their source files; source file handles and all output sidecars must be validated independently.

All received but unverified `RPKI/RDAP/IRR` audit candidates remain review-only. PR #5 and `feature/reachability-full-ru-kz-by` are excluded entirely from this task.

## Publication boundary

The v41 workflow is PR/manual candidate only. No schedule or push-to-main automatic publication has been enabled. Release/tag/CDN publication remains prohibited until a successful, verified candidate and separate release decision. The released v39 tag is retained as rollback.