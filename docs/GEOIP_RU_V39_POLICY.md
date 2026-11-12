# GeoIP RU+BY+KZ DIRECT v39 policy

**Target:** one-file Xray/V2Fly GeoIP for VPN split tunneling. v39 preserves the v38 DIRECT source composition and changes the precedence between approved RKN-derived blocks and exact prefixes originated by curated Russian-company ASNs.

## 1. Output contract

The client file remains `geoip_RU.dat` with exactly two categories:

- **RU** — unified DIRECT bucket for the RU+BY+KZ regional/resource inputs, selected-origin ASN routes, service destinations and company-origin prefixes.
- **PRIVATE** — private, reserved and other non-globally-reachable space, with globally reachable IANA exceptions preserved.

The label RU remains a legacy routing bucket, not a physical-geolocation assertion. The database cannot distinguish unrelated domains hosted on one shared IP.

## 2. v39 corporate company-ASN exception

The company allowlist is `geoip_RU_company_asns.txt`. The normal ASN extractor already writes selected-origin exact prefixes, with origin labels, into `geoip_RU_BY_KZ_asn_bgp_prefixes.txt`.

A new deterministic extractor, `.github/scripts/build_company_asn_prefixes.py`, intersects those exact origin labels with the curated company allowlist and emits `geoip_RU_company_asn_bgp_prefixes.txt`. Its output is bound to the SHA-256 of both the selected-origin file and the allowlist.

For a prefix to receive the v39 exception, at least one exact origin ASN on that selected-origin prefix row must appear in the curated company allowlist. For a MOAS prefix, one allowlisted company origin is sufficient to exempt the exact shared prefix. This is a prefix-level exception, not an exemption for an entire provider, ASN or country.

The effective blocked set is computed as exact address-space subtraction:

`effective_blocked = approved_blocked_inputs - corporate_company_origin_prefixes`

The final DIRECT set is:

`RU = (v37_RU ∪ RU_BY_KZ_RIR ∪ service_DIRECT ∪ corporate_company_origins) - PRIVATE - effective_blocked`

No public BGP registration, BGP community 65444:210, host registration, country-code or RPKI result is inferred from a missing observation.

## 3. Precedence

1. Start from the immutable v37 DIRECT/PRIVATE builder outputs.
2. Add RU/BY/KZ RIR resources and the pinned service-DIRECT feeds as in v38.
3. Add exact selected-origin prefixes from the curated company-ASN allowlist as the corporate protection set.
4. Subtract PRIVATE from all DIRECT candidates.
5. Subtract only the approved RKN block addresses that fall outside the corporate-origin prefix set.
6. Emit the remaining DIRECT addresses as RU and keep PRIVATE separate.

**PRIVATE always wins.** A company-origin prefix which intersects PRIVATE is only retained outside PRIVATE. The corporate exception cannot make RFC1918, loopback, link-local, documentation, reserved or other PRIVATE space public.

## 4. Blocked-source policy retained

The approved blocked inputs remain the same conservative v38 set:

- Antifilter Download `ip.lst` and `ipresolve.lst` host entries;
- bounded `subnet.lst` networks under the existing automatic-carve width thresholds;
- repository-curated Telegram service prefixes.

Antifilter `ipsum.lst` /24 summaries remain review-only and are not automatically carved. Community and Re-filter lists remain review-only. The same corporate exception is removed from the hypothetical /24 impact ledger so company-protected DIRECT space is not counted as collateral VPN routing.

These are third-party RKN-derived feeds, not a direct official RKN API. Public-list cross-checks do not reproduce Antifilter private BGP communities. Domain-only blocks must remain in a domain-rule dataset, not be expanded blindly into shared IP ranges.

## 5. Evidence, provenance and validation

The build publishes:

- `geoip_RU_company_asn_bgp_prefixes.txt` — exact corporate origin prefixes, source hashes and ASN labels;
- `geoip_RU_v39_blocked_ip_exclusions.txt` — effective non-corporate block set actually subtracted;
- `geoip_RU_v39_blocked_provenance.tsv` — original block entries, DIRECT overlap, corporate exemption and net impact;
- `geoip_RU_v39_prefix_provenance.tsv` and `geoip_RU_v39_source_metrics.tsv` — source lineage and non-additive coverage;
- `geoip_RU_v39_manifest.json` — input/output hashes, exact company-exemption counts and precedence flags;
- `geoip_RU_quality_report.txt` — final address totals and v37 delta.

The builder and independent workflow validation prove that:

- the decoded protobuf contains exactly RU and PRIVATE;
- RU and PRIVATE are disjoint;
- RU is disjoint from the effective blocked set;
- corporate-origin prefixes are present in RU except for PRIVATE intersections;
- the effective blocked set is disjoint from the corporate prefix set;
- `ipsum.lst` remains non-automatic;
- output and manifest hashes are verified before a candidate artifact can be accepted.

## 6. Audits and release scope

Exact-origin/RPKI/RDAP/IRR audits that do not propose or validate a build input are not standalone recurring workflows in v39. Useful static findings and provenance are retained in repository documentation; repeated audit-only API collection is closed to avoid consuming CI/API capacity without changing build inputs.

The v39 workflow creates candidate artifacts on pull requests. Release/tag publication, release-branch update and CDN purge remain restricted to a successful run on `main`.


## 7. Empty ipresolve feed and immutable block carry-forward

The v39 workflow pins the previously approved v38 combined blocked set at release commit `3033248ea54cb298bafded25ddcd2805d5f0e7ac`, SHA-256 `df909b12b985b23080075821cedc5e2f73b7b1f89abcd9950293b400ce1e4a5d`. It unions this immutable baseline with the current available `ip.lst` and bounded `subnet.lst` inputs before applying the corporate-origin exception.

During the v39 candidate run, the live Antifilter `ipresolve.lst` endpoint returned an empty body. The workflow records it as `unavailable` and the blocked-source parser emits `EMPTY_FALLBACK_V38_PINNED_BASELINE`. This does **not** mean there are zero resolved-IP blocks: prior approved entries remain carried forward from the pinned baseline. A non-empty but unexpectedly small/truncated feed still fails closed. The final effective blocked set is then reduced by exact corporate company-ASN origin prefixes; PRIVATE still wins.
