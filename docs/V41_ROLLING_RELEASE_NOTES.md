# GeoIP DIRECT RU+BY+KZ CLIENT v41 — Regional and Service DIRECT

## Routing policy
- Exactly two GeoIP categories are emitted: `RU` and `PRIVATE`. `RU` is the unified DIRECT bucket for RU+BY+KZ address resources and origins, plus reviewed service and Hydra DIRECT/WHITELIST intent.
- PRIVATE always wins. The full official Telegram prefix set, bounded Antifilter subnet input and separately reviewed direct IP/subnet records cannot be overridden by any DIRECT protection class.
- DNS-derived `ip.lst` and `ipresolve.lst` and unverified historical v38 records do not carve registered RU/BY/KZ resources, selected regional origins, CORE/SHARED origins eligible existing service masks or individually reviewed operator prefixes. They still apply outside these protections where applicable.
- REG.RU AS197695 is SHARED_INFRA, with no ASN-wide admission outside the existing regional selection. Corporate and shared prefixes retain exact-origin provenance, including MOAS.
- Regional eligibility relies on address registration and routing evidence, not a physical geolocation filter. The build separately excludes exact, reviewed foreign operational assignments. This is not RKN blocking and does not remove their parent allocations from the RIR inventory.
- See [v41 policy and exact regional evidence](https://github.com/SpeedeMiner/Geoip-ru-server/blob/main/docs/GEOIP_RU_V41_POLICY.md).

## Reviewed operator routes
- The exact reviewed-prefix table covers verified RU/BY/KZ assignments. Its protection is resolver-only and does not exempt an entire ASN. The overlay and independent publication validators check its digest and eligible coverage.
- The PR #27 evidence includes the [last two verified batches](https://github.com/SpeedeMiner/Geoip-ru-server/blob/main/docs/v41-geo-only-operator-rukz-20261114.json). Unconfirmed geography-only rows were not promoted.

## Service DIRECT outside geolocation
- Kyoresuas `ru-standard` service prefixes are imported with per-service category/name/ASN/domain provenance.
- W1ZARDZ service-direct, HXEHEX exact host-IP whitelist, and Escapingworm operator whitelist prefixes are separately attributed.
- These feeds are treated as service/availability intent, not geographic proof. Their prefixes are still subject to PRIVATE and RKN exclusions.
- Service-source coverage and exact address-space deltas are published in `geoip_RU_v41_source_metrics.tsv` and `geoip_RU_v41_prefix_provenance.tsv`.

## RKN blocked destinations
- DNS-derived host lists and historical inputs remain preserved for provenance. A domain/URL entry or shared DNS address does not establish a hard IP block.
- The reviewed direct-IP input includes 746 exact IPv4 hosts cross-checked against a dated public registry mirror. This is not a signed official export. Only the recorded IP scope is used, without expanding it to adjacent networks.
- Antifilter and Re-filter `ipsum.lst` and community suggestions remain review-only. The build does not automatically carve a /24 containing unrelated tenants.
- The [v41 public-source cross-check](https://github.com/SpeedeMiner/Geoip-ru-server/blob/feature/geoip-direct-rukzby-v41-integration/docs/V39_PUBLIC_RKN_SOURCE_CROSSCHECK.md) documents the pinned input lineage and its limitations. The workflow does not claim Antifilter community 65444:210 membership.
- GeoIP cannot distinguish unrelated domains on the same IP. Domain-only rules remain a separate client GeoSite layer.

## Audit outputs
- `geoip_RU_quality_report.txt` records final v41 address coverage and the exact new-vs-v37 delta after PRIVATE and RKN policy.
- `geoip_RU_v41_manifest.json` records immutable source refs, source hashes and output SHA-256.
- `geoip_RU_BY_KZ_rir_registered_prefixes.tsv` retains country, RIR and resource-status provenance.
- The final client file remains `geoip_RU.dat` with `geoip:RU` and `geoip:PRIVATE` only.
- `geoip_RU_company_asn_bgp_prefixes.txt` lists exact prefix-level company exceptions; it does not exempt whole ASNs outside the selected-origin snapshot.

## Attribution and limitations
- Preserve v2fly/geoip CC-BY-SA-4.0 and DB-IP CC-BY-4.0 notices, plus upstream licenses/attributions for service feeds.
- RIR registration, BGP announcements, service association and RKN block evidence are distinct signals and are reported separately.
- No ASN or service protection overrides an effective hard block. The independent release gate verifies hard provenance and DIRECT disjointness before publication.
