# v41 release hardening

This change hardens ingestion and publication without enabling a new routing policy.

- Static routing inputs are listed in `.github/data/v41-source-lock.json` with versioned upstream URLs, byte lengths and independently reviewed SHA-256 digests. Initial bytes match the published v41 input provenance at release commit `0ef5d68d0cca585dc90cb4a5199dd0abd5ce24d7`. Update the URL, byte length and digest together in a reviewed commit. Official RIR/IANA/BGP and current block feeds still refresh at build time. They are dynamic and protected by transport, parser and publication bounds, not by this lock. Kirill no longer uses third-party proxies.
- The independent DAT reader verifies canonical prefixes, category uniqueness, inverse-match semantics, non-overlap with PRIVATE and size/address limits. The hard ceiling is 8 MiB, 350,000 RU CIDRs, 64,000,000 IPv4 addresses and 2^111 IPv6 addresses. The widest allowed RU records are IPv4 /8 and IPv6 /24. It checks added and removed address sets separately against the previous release commit, with thresholds of 0.5% IPv4 and 1% IPv6 (small reference floors 4,096 and 2^80). Any PRIVATE change also requires review. Absolute bounds cannot be waived.
- To confirm a relative overrun, review the candidate artifact and provide its exact SHA-256 as `reviewed_geoip_sha256` when manually dispatching the workflow on main. This is an explicit action by a user with dispatch rights, not a claim of a separate GitHub Environment reviewer. If the regenerated artifact changes, the previous digest will not approve it.
- The build job has read-only repository permissions. The publish job receives only its artifacts and checks them against the same immutable previous branch commit before a fast-forward update. Existing running publishes are not automatically cancelled. The branch and versioned Git tag are pushed atomically. Versioned GitHub snapshots are never edited by this workflow. This is not GitHub-enforced repository-wide immutability, which would also prevent updates to the compatibility release. Git refs and GitHub Release uploads are separate transactions. If the asset upload fails after a successful push, the versioned Git tag and branch still hold the validated DAT and checksum.
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

- Routine builds keep the unique tag format `geoip-v41-snapshot-<run>.<attempt>`. A manual dispatch on `main` can set `snapshot_version` to a one-time version such as `v41.3`. An existing tag is rejected before the branch/tag push. There is no automatic move or overwrite of a version tag.
- The release branch and selected tag still update with one atomic fast-forward push against the checked previous tip. The GitHub snapshot Release is then created with `gh release create --verify-tag`. The create-only path cannot edit an existing Release. It does not mark the snapshot Latest or change the rolling download URL.
- Git references and GitHub Release assets are still separate operations. If GitHub Release upload fails after the push, the Git snapshot contains the validated DAT and checksum. A published snapshot is protected from external updates or deletion only if the repository has appropriate GitHub immutability or tag protection configured. No repository settings are changed here.
- Source acquisition, IANA conversion, legacy RIR extraction, v37 artifact validation and publication logic now live in separate files under `.github/scripts/`. The workflow still owns permissions, step order and artifact lists. Go and the ipverse ASN extractor remain the files previously extracted in #17.

## Preserve the exact ipverse archive for later prefix audits

The rolling ipverse download records the actual compressed size and SHA-256 per build. The mutable branch URL is not a recoverable reference once its contents change. Even a GitHub archive for the same commit can have identical file content and a different compressed hash because its archive root differs.

The v41 candidate retains the actual `as-ip-blocks.tar.gz` as an Actions artifact. The create-only versioned release uploads that exact byte stream alongside the validated DAT and report. The corresponding Git tree stores only `geoip_RU_ipverse_snapshot_tag.txt`, so the 16 MiB archive is not added to the rolling release branch history or to rolling release downloads. No source selection, protobuf, or block policy changes.

The prefix audit reads the marker from the same pinned release commit as the TSVs, then checks the retained asset against that commit's exact recorded size and SHA-256. Only a missing marker on a pre-retention release permits the original upstream URL. A present but invalid marker, missing retained asset, or mismatched bytes fails the audit. It cannot be repaired by fetching newer BGP data. Git refs and the GitHub Release API are separate transactions. If asset publication fails, the same validated candidate artifact is the recovery source while retained by Actions, and the existing release tag must not be replaced.
