# Production GeoIP source catalog — v1

**Catalog version:** 1.0  
**Repository baseline inspected:** `main` at `d6fa94a691a9635b72be4e6b941c87d29c802dfa`  
**Production workflow:** `.github/workflows/blank.yml`  
**Purpose:** describe the inputs and their actual roles in the existing v37 builder. This catalog is metadata; it does not change the production workflow or make any inclusion/exclusion decision.

The machine-readable register is [GEOIP_RU_SOURCE_CATALOG_v1.tsv](GEOIP_RU_SOURCE_CATALOG_v1.tsv). It contains 38 source and derived-input records with stable `SOURCE_ID` keys.

## How to read the catalog

- `REQUIRED` describes acquisition/runtime behavior in the current workflow: `required` means the build fails if the fetch or embedded source is missing; `optional` means the build continues with an unavailable placeholder; `embedded` is repository-owned policy/code; `derived` is generated from listed parent inputs.
- `PRODUCTION_ROLE` describes how the builder actually consumes the input. A required source can still be candidate-only or review-only.
- `UPSTREAM_PRIMARY` and `UPSTREAM_FALLBACKS` list the fetch order in the workflow, not an assertion that mirrors are independent publishers.
- `REF_PINNING` describes the requested upstream reference. A mutable branch or `latest` URL is not an immutable snapshot.
- `PROVENANCE_CAPTURE` describes the provenance currently available. The production download helper records the selected URL, SHA-256, byte count and status in `geoip_RU_input_provenance.tsv`; the provenance file itself is checksummed.
- `LICENSE_STATUS` is intentionally conservative. Unless the workflow's generated manifest explicitly records an attribution, this catalog does not infer a license from the repository name or file format.

## Production layers — keep their meanings separate

### 1. Geographic GeoIP inputs

- **Protected core:** Loyalsoldier `ru.dat` and v2fly `geoip.dat` `ru` category.
- **Regional legacy DIRECT layers:** Loyalsoldier `by.dat` and v2fly `by` / `kz` categories. They are deliberately folded into the one legacy `geoip_RU.dat` RU category; they are not strict Russian geography.
- **Additional geographic feeds:** Grimbird, Digne, Davoyan and Golukon. Grimbird and Digne are one correlated logical group. Additional feed coverage is admitted only through the builder's corroboration policy (distinct logical groups or selected-origin BGP / RU RIR-resource overlap).
- **Private layer:** Loyalsoldier `private.dat`, IANA non-globally-reachable special-purpose entries and embedded built-in reserved networks are inserted into the higher-priority PRIVATE trie.

### 2. Candidate-only inputs

Hydra direct/whitelist, Kirill whitelist, HXEHEX and W1ZARDZ feed diagnostic candidates. They do **not** independently add geographic RU space and do not subtract from DIRECT. A source being required for a reproducible build does not turn its entries into approved output.

### 3. Independent registration and routing evidence

- Five RIR delegated-stat snapshots generate RU ASN, BY/KZ ASN and RU-registered address-resource inventories. The code accepts allocated/assigned/legacy records, requires a recent snapshot end date (no older than 14 days), and uses RU address resources as corroboration only. BY/KZ ASN registrations contribute their origin prefixes; BY/KZ address allocations are not blindly imported.
- The curated company ASN allowlist is policy input. It may be overridden by a repository-root `geoip_RU_company_asns.txt`; otherwise the workflow writes an embedded default. Only explicitly listed origin ASNs are imported; peers/upstreams are not recursively imported.
- ipverse `aggregated.json` files supply global origin observations and selected-ASN origin prefixes. The observation window is **up to 90 days**, not a complete or live global RIB. Its `countryCode` is not an inclusion filter for selected RIR/company origins.

### 4. IANA and blocked-destination policy

- IANA IPv4/IPv6 special-purpose CSV rows with `Globally Reachable=False` feed PRIVATE. `True` entries are explicit carve-backs from broad special-purpose blocks.
- Antifilter `ip.lst` and `ipresolve.lst` contribute exact host exclusions only. `subnet.lst` is auto-carved only up to /16 IPv4 or /112 IPv6; wider prefixes remain review-only.
- Twelve RunetFreedom Telegram prefixes are embedded policy exceptions, not fetched dynamically at build time. The URL to RunetFreedom's config is a reference for the embedded list.
- Antifilter `community.lst` and Re-filter `ipsum.lst` are optional review candidates; they never enter the approved exclusion set automatically.

## Provenance and reproducibility findings

The current downloader already provides a useful per-build record: selected mirror URL, downloaded bytes, SHA-256 and status. However, it does **not** consistently pin the upstream commit or release identity:

1. Most GeoIP feeds use mutable GitHub `main`, `master` or `release` references.
2. The ipverse archive uses `refs/heads/master` (or a mutable `latest` release fallback) and is a rolling 90-day observation set.
3. RIR endpoints are daily `delegated-*-latest` resources. The parser checks the snapshot end date, but the URL remains mutable.
4. IANA CSV paths are fixed names but the data can be revised; only the downloaded bytes are hashed.
5. Antifilter lists are unversioned endpoints.
6. v2fly is the strongest current content-integrity case: the downloaded database is checked against its fetched SHA-256 sidecar. The sidecar itself is still obtained from a mutable release/branch.
7. Kirill resolves the GitHub Release API's `latest` asset (with a `0.3.11` tag fallback), records the asset download URL, and verifies the API-provided asset digest when present. The selected release tag and asset id should be made first-class manifest fields.

A checksum proves the bytes that were downloaded; it does not, by itself, identify the upstream commit/tag or establish that the publisher reference will resolve to the same bytes later.

## Next step: immutable raw snapshot bundle

The catalog is not the snapshot bundle. For each future build/run, capture the raw bytes before parsing and never overwrite a previous run. The snapshot manifest should include at least:

`catalog_version`, `run_id`, `source_id`, `local_file`, `requested_primary_url`, `selected_final_url`, `mirror_rank`, `upstream_repository`, `upstream_commit_sha`, `release_tag`, `asset_id`, `upstream_digest`, `local_sha256`, `byte_count`, `downloaded_at_utc`, `upstream_snapshot_date`, `etag`, `last_modified`, `http_status`, `acquisition_status`, `parser_version`, `license_evidence_ref`.

For embedded or derived inputs, record the repository commit and all parent `source_id` + SHA-256 references instead of inventing a remote URL.

Recommended immutable layout:

```text
source-snapshots/
  <run-id>/
    manifest.tsv
    SHA256SUMS
    raw/
      <source-id>.<original-extension>
    derived/
      <derived-source-id>.txt
```

The raw bundle must be retained as a separate artifact/release asset with an expiry/retention policy. A future workflow should resolve Git refs to commit SHAs, capture GitHub Release tag + asset ID + digest, retain upstream date headers for RIR data, and fail closed when a required source's bytes cannot be verified. Optional review-only feeds must keep their explicit unavailable state.

## Explicit non-goals

- No change to `geoip_RU.dat`, company ASN policy, source-selection rules, PRIVATE precedence or blocked exclusions.
- No assumption that ASN registration country or RIR resource country proves physical server location.
- No promotion of candidate-only or review-only inputs.
- No conversion of the legacy RU+BY+KZ DIRECT category into a strict geographic RU set in place.
