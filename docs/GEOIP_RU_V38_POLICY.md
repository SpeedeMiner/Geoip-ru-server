# GeoIP RU+BY+KZ DIRECT v38 policy

**Target:** one-file GeoIP for VPN split tunneling. Traffic in the RU+BY+KZ regional/service set goes DIRECT regardless of physical IP geolocation; known RKN-blocked destinations are carved from DIRECT and therefore fall through to the user's VPN route. PRIVATE always has highest precedence.

## 1. Routing semantics

The output is deliberately still a two-category Xray/V2Fly GeoIP file:

- **RU** — unified DIRECT aggregate for RU, BY and KZ regional resources, current regional origin-ASN networks, curated company/service networks, and named service destinations.
- **PRIVATE** — private, reserved and other non-globally-reachable address space, with IANA globally reachable exceptions preserved.

The category name RU is a legacy single-bucket label. It does not mean physical geography. A destination can be DIRECT because the address resource is registered to RU/BY/KZ, because a named regional service uses it, or because a vetted routing/service feed identifies it as a regional destination even when its GeoIP country is elsewhere.

The database is an IP routing input, not a complete policy engine. Unknown destinations remain handled by the user's default VPN route. A shared IP cannot be split by domain inside a GeoIP database; RKN domain-only destinations belong in a separate geosite/domain rule set.

## 2. v37 base retained

v38 starts with the current v37 geographical/ASN baseline and preserves its:
- Loyalsoldier RU/BY and PRIVATE layers;
- v2fly RU/BY/KZ layers;
- current selected-origin BGP prefixes from regional RIR ASNs and curated company ASNs, regardless of ipverse countryCode;
- vetted additional GeoIP sources and existing company/static-direct exceptions;
- IANA non-global precedence and approved legacy RKN exclusions.

The v37 base output is kept as a separate build intermediate and is not overwritten during the v38 assembly.

## 3. v38 additions to DIRECT

### Registered resources, not geolocation

A new independent inventory converts the five authoritative RIR delegated-stat snapshots into exact CIDR components for all three resource-registration countries:
- RU
- BY
- KZ

Only allocated, assigned and legacy resource statuses are included. Each row preserves country, prefix, source RIR registry and status. The complete inventory is unioned into DIRECT regardless of BGP countryCode or GeoIP location.

RIR registration is not proof of physical server location, current origin announcement or actual application hosting. The final quality report and RIR inventory preserve those distinctions; route reachability remains separately measurable.

### Named service DIRECT, not geolocation

The candidate v38 service layer adds:
- Kyoresuas ru-standard IPv4 and IPv6 service prefixes, with the accompanying pinned services.json used to retain service/category/ASN/domain attribution;
- W1ZARDZ RU Direct output, a service feed built around a service catalog and IP→ASN validation;
- HXEHEX ipwhitelist.txt exact host-IP entries (separate from the much broader cidrwhitelist.txt, which remains a diagnostic candidate and is not bulk-imported);
- Escapingworm operator whitelist CIDRs.

These are service/availability intent sources. A foreign GeoIP location does not disqualify them. They are still carved by PRIVATE and the RKN block union. Per-source raw counts, unique CIDRs, unique address space, exact prefix attribution and new-vs-v37 address delta are exported.

Source groups are not independent votes: Kyoresuas tiers are one publisher; W1ZARDZ references HXEHEX and other upstreams; HXEHEX and Escapingworm are correlated mobile/operator-whitelist evidence. v38 includes these feeds as explicit service/direct policy sources, not as independent country proofs.

## 4. RKN-only DIRECT carve-outs

v38 retains the v37 conservative blocked set:
- Antifilter Download ip.lst exact host records;
- Antifilter Download ipresolve.lst exact host records;
- bounded explicit subnet.lst networks;
- curated Telegram prefixes already accepted by the repository's policy.

It additionally downloads Antifilter Download ipsum.lst for a separate review-only impact analysis. The publisher documents it as a summary of individual blocked IPv4 addresses into /24 prefixes and currently reports 19,015 such prefixes versus 50,806 individual ip.lst records. The site says its source data is supplied in accordance with Government Resolution 1101, but this is still a third-party feed/aggregator, not a direct RKN API endpoint. The exact downloaded bytes and SHA-256 are retained.

**Collateral risk:** a /24 summary can cover 256 addresses even when only one or a few IPs in that block appeared in the source list. On shared hosting, CDN or multi-tenant ranges this could send unrelated co-resident traffic through VPN. Therefore v38 does **not** automatically carve ipsum /24s. It publishes a per-prefix review ledger and counts the potential extra DIRECT address space that would be affected. Only exact host addresses from approved sources and the existing bounded subnet policy remain automatic.

Community Antifilter and Re-filter candidate lists remain review-only. They are not automatically subtracted from DIRECT. Privacy/telemetry classification does not move traffic to VPN; only membership in the approved RKN-derived blocked set does.

Domain-only blocked rules should be handled separately. A future client-compatible domain sidecar can use RKN domain feeds (for example the domain output from jutsu-dev/ru-route-lists), but it must not be flattened into broad GeoIP CIDRs where shared IPs would be overblocked.

## 5. Final precedence

For each address:
1. Add v37 DIRECT baseline plus RU/BY/KZ RIR resources and named service DIRECT prefixes.
2. Subtract PRIVATE.
3. Subtract the approved v37 RKN carve-outs. Keep Antifilter ipsum.lst /24 summaries review-only; they do not change the client output.
4. Emit the remaining addresses as RU; emit PRIVATE unchanged.

The final protobuf is independently decoded and checked to contain only RU and PRIVATE. Validation confirms no RU address overlaps PRIVATE or any approved blocked prefix.

## 6. v38 artifacts

- geoip_RU.dat — final client GeoIP protobuf (RU + PRIVATE only).
- geoip_RU.dat.sha256sum — exact output digest.
- geoip_RU_quality_report.txt — final v38 address counts and exact v37 delta after precedence.
- geoip_RU_v38_manifest.json — output digest, immutable source refs and input SHA-256 values.
- geoip_RU_v38_source_metrics.tsv — per-source CIDR/address contribution; rows overlap and must not be summed.
- geoip_RU_v38_prefix_provenance.tsv — per-service and regional resource prefix attribution.
- geoip_RU_v38_blocked_provenance.tsv — approved block overlaps plus review-only /24 collateral estimates.
- geoip_RU_v38_blocked_ip_exclusions.txt — exact combined blocked set applied to v38.
- geoip_RU_BY_KZ_rir_registered_prefixes.tsv and geoip_RU_BY_KZ_rir_stats.txt — regional resource-registration inventory.
- geoip_RU_v37_base.dat and geoip_RU_v37_base_quality_report.txt — retained baseline intermediate for exact comparison.

## 7. Build safety

The feature branch is a candidate only. Its workflow_dispatch / pull-request run uploads a CI artifact and skips all release/tag, release branch push and CDN purge steps. Only a run on main can publish latest-geoip-client-v38.

PR #5, PR #6, PR #7 and PR #8 remain separate and untouched. No main, production release, tag or release branch is changed by this v38 candidate build.
