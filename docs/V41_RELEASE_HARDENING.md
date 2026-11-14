# v41 release hardening

This change hardens ingestion and publication without enabling a new routing policy.

- The v41 publisher uses `.github/data/v41-upstream-sources.json` to resolve each upstream's current stable release or output branch once per build. Files from the same source use the same release or commit. Release assets are verified against GitHub's digest and size, branch files against their Git blob ID and size, and v2fly against its companion checksum. The old static lock is retained only for reproducing historical releases. The rolling build never falls back silently to it. Official RIR/IANA/BGP, Telegram and current block feeds refresh at build time. Reviewed local exceptions and the v38 historical evidence baseline are intentionally unchanged.
- The independent DAT reader verifies canonical prefixes, category uniqueness, inverse-match semantics, non-overlap with PRIVATE and size/address limits. The hard ceiling is 8 MiB, 350,000 RU CIDRs, 64,000,000 IPv4 addresses and 2^111 IPv6 addresses. The widest allowed RU records are IPv4 /8 and IPv6 /24. It checks added and removed address sets separately against the previous release commit, with thresholds of 0.5% IPv4 and 1% IPv6 (small reference floors 4,096 and 2^80). Any PRIVATE change also requires review. Absolute bounds cannot be waived.
- To confirm a relative overrun, review the candidate artifact and provide its exact SHA-256 as `reviewed_geoip_sha256` when manually dispatching the workflow on main. This is an explicit action by a user with dispatch rights, not a claim of a separate GitHub Environment reviewer. If the regenerated artifact changes, the previous digest will not approve it.
- The build job has read-only repository permissions. The publish job receives only its artifacts and checks them against the same immutable previous branch commit before a fast-forward update. Existing running publishes are not automatically cancelled. The versioned Git tag is staged before the snapshot Release is created. The branch advances only after the required public input archives verify. Versioned GitHub snapshots are never edited by this workflow. This is not GitHub-enforced repository-wide immutability, which would also prevent updates to the compatibility release. A failed upload can leave a staged tag without moving the release branch.
- The orphaned default-branch VPN Gate workflow is removed. The review of any privileged measurement workflow remains with PR #5. Historical v38/v39 compatibility workflows cannot publish and have read-only permissions. The v41 Go builder and BGP extractor are normal source files.
- RDAP bootstrap parsing and hashing consume the same response bytes.

Service exception narrowing, BY/KZ DNS exception policy, source-strength decisions for historical /32 entries and corporate-ownership evidence are intentionally separate from this publication change. A DNS-derived /32 does not establish a current IP-only block. Absence from a current third-party feed does not establish unblocking.

On the fixed v41 snapshot, splitting exact service evidence before collapsing
the CIDRs would remove 91 IPv4 addresses from DIRECT under the current hard
classification, including 88 in current Antifilter ip.lst. These are source
overlaps, not proven live IP blocks. Selected BY/KZ origin protection against
only the resolver layer would restore up to 696 IPv4 on the same snapshot.
Do not sum the estimates with the earlier current-ip.lst DNS-only scenario.

## v41.3 snapshot publication

- Routine builds keep the unique tag format `geoip-v41-snapshot-<run>.<attempt>`. A manual dispatch on `main` can set `snapshot_version` to a one-time version such as `v41.3`. An existing tag is rejected before staging. There is no automatic move or overwrite of a version tag.
- Publication first stages the snapshot tag without moving `release`. The create-only `gh release create --verify-tag` step uploads the versioned Release and its assets without marking it Latest. A separate step reads the public input archives back, verifies them against the provenance committed in that exact tagged tree, then fast-forwards `release` only if its tip still equals the checked parent. The rolling Release assets update last.
- If snapshot publication or archive readback fails, the old `release` and rolling downloads remain in place. The run may leave a Git tag or a draft/versioned Release. Do not reuse or move the tag. For a new attempt, use the default unique tag or another unused explicit version. The original validated candidate artifact remains available during Actions retention for inspection or manual recovery. If rolling asset upload fails after promotion, the new Git tree still references a verified snapshot archive. External changes or deletions are governed by GitHub repository protections, which this workflow does not change.
- Source acquisition, IANA conversion, legacy RIR extraction, v37 artifact validation and publication logic now live in separate files under `.github/scripts/`. The workflow still owns permissions, step order and artifact lists. Go and the ipverse ASN extractor remain the files previously extracted in #17.

## Preserve the exact ipverse archive for later prefix audits

The rolling ipverse download records the actual compressed size and SHA-256 per build. The mutable branch URL is not a recoverable reference once its contents change. Even a GitHub archive for the same commit can have identical file content and a different compressed hash because its archive root differs.

The v41 candidate retains the actual `as-ip-blocks.tar.gz` as an Actions artifact. The create-only versioned release uploads that exact byte stream alongside the validated DAT and report. The corresponding Git tree stores only `geoip_RU_ipverse_snapshot_tag.txt`, so the 16 MiB archive is not added to the rolling release branch history or to rolling release downloads. No source selection, protobuf, or block policy changes.

The prefix audit reads the marker from the same pinned release commit as the TSVs, then checks the retained asset against that commit's exact recorded size and SHA-256. Only a missing marker on a pre-retention release permits the original upstream URL. A present but invalid marker, missing retained asset, or mismatched bytes fails the audit. It cannot be repaired by fetching newer BGP data.

## Retain the original delegated RIR and IANA registries

The five delegated RIR files and both IANA CSVs are archived as
`v41-registry-inputs.tar.gz`. The build verifies each original file against
the recorded input provenance before archiving. The publication job checks
the archive again before creating the versioned Release. After publication
it downloads the public archive, checks its compressed SHA-256 against
`geoip_RU_v41_registry_inputs.sha256sum` in the exact tagged Git tree, and
checks all seven members against that tree's input provenance before moving
`release`. The Git tree contains only the checksum and provenance, not the
archive. The rolling Release does not contain the registry archive.

To recover the exact original bytes, obtain the archive from the versioned
Release, and the checksum and input provenance from the commit for that tag.
Then verify and restore to a new directory:

```sh
sha256sum -c geoip_RU_v41_registry_inputs.sha256sum
python3 .github/scripts/bundle_v41_registry_inputs.py restore \
  geoip_RU_input_provenance.tsv v41-registry-inputs.tar.gz restored-registry-inputs
```

Older snapshots that predate registry retention are not retroactively changed.
The new archive does not change route selection or turn the entire release into
a self-contained build corpus. For newer snapshots, `v41-upstream-inputs.tar.gz` also preserves the exact
rolling routing inputs and official Telegram file. Verify the archive
against `geoip_RU_v41_upstream_inputs.sha256sum` in the versioned Git tree
and use `bundle_v41_registry_inputs.py --upstream-catalog
.github/data/v41-upstream-sources.json restore` with that snapshot's
provenance and source revision. Historical snapshots remain unchanged.
