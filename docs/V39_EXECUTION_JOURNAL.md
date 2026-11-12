# v39 execution journal

Append-only log for the v39 production build initiative. Record each meaningful step, code change, CI result, release action and PR-retirement decision. This journal is intentionally concise and is updated during work, not only at the end.

## 2026-11-12 11:51 +0500 — v39 start and interruption recovery

- User authorization: create v39 with a corporate company-ASN exception to approved blocked-address subtraction; any non-build PR/audit must either be integrated into the build process or closed as ineffective/consuming limits.
- Hard boundary retained from earlier instruction: do not inspect, modify, test, close, or otherwise act on PR #5 or branch `feature/reachability-full-ru-kz-by`.
- Production baseline pinned: main `6c856d5c4b16ff6a77ad507572a7017a4cfe2532`; release `3033248ea54cb298bafded25ddcd2805d5f0e7ac`; tag `latest-geoip-client-v38`; v38 GeoIP SHA-256 `e757c1b7b8ca5b47c11117784eb78ab25c59fbadc0f6ab55229827560db76800`.
- New branch created from v38 main: `feature/geoip-direct-rukzby-v39`. No production refs changed.
- First coding attempt stopped before builder creation because an exact-text patch anchor did not match. No partial overlay was written by that failed patch; the branch contained only the new corporate ASN extractor/tests and its regex correction.
- New extractor `.github/scripts/build_company_asn_prefixes.py` reads the selected-origin prefix list and curated corporate ASN registry, fails closed on missing origin comments/malformed records/empty match, and writes exact prefixes plus source and registry SHA-256 pins.
- Regression tests added for exact company-prefix selection, MOAS exemption, static Yandex company origin, malformed input and empty match.
- v39 overlay created at `.github/scripts/build_v39_overlay.py`: effective block set is `approved_blocked - exact_corporate_origin_prefixes`; company prefixes are explicitly included as DIRECT candidates; PRIVATE still wins. /24 `ipsum.lst` remains review-only and gets the same corporate exception in its hypothetical impact calculation.
- Overlay regression suite added for IPv4 partial-prefix carve, IPv6, PRIVATE precedence, no-overlap policy stability, sidecar parsing and /24 collateral math.
- Build workflow `.github/workflows/geoip-v39.yml` cloned from v38 production workflow with v39 names/tag and corporate prefix extraction integrated before overlay. Candidate PR runs skip release/tag/release-branch/CDN actions; only main builds can publish.
- Independent workflow validation now checks RU/PRIVATE disjointness, no intersection with the effective non-corporate blocked set, corporate prefix retention except PRIVATE, company/effective-block disjointness and manifest SHA binding.
- Policy and source documents added: `docs/GEOIP_RU_V39_POLICY.md`, `docs/GEOIP_RU_V39_SOURCE_REGISTRY.tsv`, `docs/V39_PUBLIC_RKN_SOURCE_CROSSCHECK.md`.
- The prior v38 audit run #15 `43164594875` finished FAILURE after 224/224 RouteViews calls and 106/106 RIPEstat RPKI calls returned HTTP 200. Failure was only final validation: a local TSV parser used a two-character string instead of a tab delimiter. No artifact was uploaded. This audit is not a v39 build prerequisite and will not be rerun.
- The concurrent v38 candidate build run #85 `43164594851` completed SUCCESS and uploaded candidate artifact `13919935494`; release and release-branch steps were SKIPPED because it was a PR run. It did not alter production refs.
- Existing PR state at v39 start: #6/#7/#8/#10 open Draft, all audit-only or candidate-only and not in the production builder; #9 already merged as v38. These PRs are scheduled for closure after v39 PR is created and the retained findings are documented here. No access to PR #5.

## Policy details / invariants

- Corporate exception is exact prefix-space from the selected-origin archive whose origin labels intersect `geoip_RU_company_asns.txt`. It is not a whole-ASN exemption and not a country-wide exemption.
- For MOAS, an exact prefix is corporate-exempt when at least one exact origin ASN is on the curated allowlist; this is recorded in the prefix sidecar.
- Effective RKN carve set: `blocked_base - company_prefixes`.
- Final DIRECT set: `(v37_RU ∪ RU/BY/KZ_RIR ∪ service_DIRECT ∪ company_prefixes) - PRIVATE - effective_blocked`.
- PRIVATE has absolute precedence over corporate exception.
- `ip.lst`, `ipresolve.lst`, bounded `subnet.lst`, and curated Telegram routes remain approved inputs. `ipsum.lst` /24, community and Re-filter remain review-only.
- No RPKI/IRR/RDAP audit status is used as an automated source admission or block-removal signal. No BGP registration or community 65444:210 claim is made.

## Next checkpoints

1. Complete v39 workflow hardening: manifest digest verification, new company-prefix sidecar release/candidate inclusion and purge path.
2. Create v39 Draft PR; inspect CI unit tests and candidate build output. Do not merge until protobuf, checksums, prefix policy invariants and manifest all pass.
3. Close PRs #6, #7, #8 and #10 with explicit reasons and pointers to this consolidated v39 process. Do not touch PR #5.
4. After successful candidate validation and review, publish v39 via main-only workflow, then verify tag, release assets, release branch, hashes and CDN purge.
5. Append exact commit/run/artifact IDs, output counts and SHA-256. Keep v38 untouched as rollback baseline until v39 release is verified.


## 2026-11-12 12:27 +0500 — CI recovery: pinned v38 blocked fallback

- v39 PR #11 candidate run #1 `43173770372` stopped in source download because Antifilter `ipresolve.lst` returned an empty body. The workflow correctly failed closed; it did not treat that empty response as a clean/zero blocklist.
- Confirmed the immutable v38 approved combined block-set sidecar at release commit `3033248ea54cb298bafded25ddcd2805d5f0e7ac`: SHA-256 `df909b12b985b23080075821cedc5e2f73b7b1f89abcd9950293b400ce1e4a5d`.
- Added v39-only `.github/scripts/prepare_blocked_sources_v39.py`: it imports the full pinned v38 approved block set, then unions available current ip.lst and bounded subnet.lst entries. If ipresolve is empty/unavailable, its prior approved rows remain carried by the baseline and the status is explicitly `EMPTY_FALLBACK_V38_PINNED_BASELINE`. This is not a zero-block inference.
- Baseline rows are checked against the exact previous safety thresholds (host /32,/128; bounded subnet /16 IPv4,/112 IPv6; explicit Telegram prefixes). Any unsafe broad prefix in the pinned baseline fails closed.
- Workflow now downloads the baseline from the exact v38 release commit, verifies its SHA-256, records it in source provenance/checksums/artifacts and only treats ipresolve as optionally unavailable. The old v38 parser/workflow code is unchanged; v38 workflow has been set to manual-only with publication steps disabled.
- First blocked-source baseline implementation CI run #4 `43174865988` and #5 `43175021426` passed the downloads, extraction and v37 build, but one test fixture failed because the fabricated baseline range `192.0.2.1+` overlapped the test's community-only address `192.0.2.123`. This was a test-fixture collision, not a policy/code failure.
- Corrected the fixture to use `192.0.10.1+`; run #6 `43175209879` is testing the current branch HEAD `d7b1cc7f6c6b5c034650822801f634266758dec0`. Do not accept earlier run conclusions as validation of the corrected fixture.
- Production refs are unchanged: main `6c856d5c4b16ff6a77ad507572a7017a4cfe2532`, release `3033248ea54cb298bafded25ddcd2805d5f0e7ac`.



## 2026-11-12 12:36 +0500 — v39 candidate run #8 passed; audit-only PRs retired

- Current successful candidate run: #8 `43175484070`, head `088e9231ff7f14abdb1cc693e328fe8d210e0a93`, conclusion SUCCESS. All steps passed: source downloads, RIR/BGP extraction, 63 Python unit tests, Go tests/build, v39 overlay, independent validation and artifact upload. Release/tag/release-branch/CDN steps were correctly SKIPPED on the Draft PR.
- Candidate artifact: ID `13923568122`, size 4,498,069 bytes, ZIP SHA-256 `10fc25106e7d81b4e9849d1a7df4d8ecd6959088f288f66e277afdd97f14a326`.
- Candidate `geoip_RU.dat`: 2,111,942 bytes; SHA-256 `3b7bbc7b9e3fb8f3d3d43f9bedf93df9d694a36f7f5fc6cedb71290e04678c8a`. Exactly two categories: RU and PRIVATE.
- Final RU: 192,807 CIDRs; IPv4 53,100,753; IPv6 1,205,559,184,134,687,078,125,685,748,793,344. PRIVATE: 151 CIDRs; IPv4 592,708,862; IPv6 4,325,545,831,231,176,725,068,219,651,071.
- Corporate exact-origin sidecar: 3,171 prefixes, 19,428,096 IPv4 addresses and 21,293,229,958,131,869,930,423,500,931,072 IPv6 addresses. All corporate-origin space remains RU except PRIVATE intersections.
- Approved block input before company exception: 199,640 unique CIDR records. Effective v39 block set after exact company-origin prefix subtraction: 126,166 records; company exception retained 1,626 DIRECT IPv4 addresses after PRIVATE, zero IPv6 addresses. Effective block union: IPv4 584,225; IPv6 79,232,998,217,542,796,110,242,775,040.
- Current Antifilter `ipresolve.lst`: unavailable (empty response, 0 bytes). Pinned v38 baseline file was downloaded from immutable commit `3033248ea54cb298bafded25ddcd2805d5f0e7ac`, 3,290,594 bytes, SHA-256 `df909b12b985b23080075821cedc5e2f73b7b1f89abcd9950293b400ce1e4a5d`. The workflow records `EMPTY_FALLBACK_V38_PINNED_BASELINE`; no zero-block inference was made.
- `ipsum.lst`: 18,769 IPv4 /24 review-only entries; estimated extra DIRECT overlap outside company-exempt space 522,315 IPv4 addresses. No /24 was automatically carved.
- Independently downloaded/examined artifact and decoded protobuf. Independent exact interval checks passed: RU∩PRIVATE=0; RU∩effective-blocked=0; effective-blocked∩corporate-prefixes=0; every corporate prefix is retained in RU except PRIVATE; effective blocked set is exactly `approved_blocked_input - corporate_prefixes` in IPv4 and IPv6. Output/manifest/sidecar/baseline hashes match.
- PRs #6, #7, #8 and #10 were closed with a rationale added to each PR: their RPKI/RDAP/IRR/VPN-route research remained review-only and produced no approved build input; repeated standalone CI/API runs did not change the production dataset. Their threads and artifacts remain preserved. PR #9 is the merged v38 release. PR #5 and its branch were not accessed or changed.
- Current PR #11 remains OPEN/DRAFT. Main remains `6c856d5c4b16ff6a77ad507572a7017a4cfe2532`; release remains `3033248ea54cb298bafded25ddcd2805d5f0e7ac`. No v39 production release has been published yet.
- Next: update the PR with this verified artifact summary, re-run candidate CI after the documentation/quality-label cleanup below, then merge only after the latest run passes. Main-only v39 workflow will publish tag/release branch/CDN, after which hashes and assets must be rechecked. Keep v38 available as rollback.


## 2026-11-12 12:47 +0500 — v39 production release published and verified

- PR #11 merged (squash) as main commit `610876b5f5cba4603dbea24c79e4a34ea2aa9792`.
- Main-only production workflow run #10 `43177534361` completed SUCCESS. Source download, selected-origin/RIR extraction, v39 build, independent validation, GitHub Release, release-branch publication and URL output all succeeded. The candidate-artifact step was skipped on main, as configured.
- GitHub Release: `latest-geoip-client-v39`, Release ID `442630840`, published 2026-11-12 07:46:35 UTC, 47 assets.
- Tag `latest-geoip-client-v39` points to main merge commit `610876b5f5cba4603dbea24c79e4a34ea2aa9792`.
- Release branch commit: `767031f305b2c26743b71cdd20a66f3575826dd2`.
- Published `geoip_RU.dat`: 2,111,794 bytes, SHA-256 `d2a38fbab40e07569f3c732a37074ff67e2435e9fbad0bc072e8281c62070ed0`. The Release asset digest, `geoip_RU.dat.sha256sum` on release branch and `geoip_RU_v39_manifest.json` all match.
- Final categories: RU 192,797 CIDRs (IPv4 53,100,229; IPv6 1,205,559,204,658,091,812,677,163,847,516,160); PRIVATE 151 CIDRs (IPv4 592,708,862; IPv6 4,325,545,831,231,176,725,068,219,651,071,148,031).
- Company exception: 3,171 exact selected-origin prefixes. The effective blocked set contains 126,166 CIDR records after subtracting those corporate prefix ranges from 199,640 original approved records. 1,626 IPv4 addresses and zero IPv6 addresses intersecting DIRECT remain protected by the company exception after PRIVATE precedence.
- The production-run `ipresolve.lst` was available (2,622,450 bytes; SHA-256 `8d8d11605a299da96006df6303a90b08b4ae25d35c1d1a199708cb83f84cdf44`). The immutable v38 baseline was also bundled (3,290,594 bytes; SHA-256 `df909b12b985b23080075821cedc5e2f73b7b1f89abcd9950293b400ce1e4a5d`) for future empty/unavailable ipresolve snapshots.
- Antifilter ipsum /24 remains review-only: 18,769 entries; estimated 522,315 IPv4 DIRECT overlap outside company-exempt space; no /24 auto-carve.
- Eleven jsDelivr purge calls returned `status=finished`; both providers `CF=true` and `FY=true` for each path.
- Final refs: main `610876b5f5cba4603dbea24c79e4a34ea2aa9792`; release `767031f305b2c26743b71cdd20a66f3575826dd2`. v38 remains available at tag `latest-geoip-client-v38` for rollback.
- Audit-only PRs #6, #7, #8 and #10 are closed; PR #9 (v38) and PR #11 (v39) are merged. PR #5 and `feature/reachability-full-ru-kz-by` were not inspected, modified or tested.
- No further audit-only live collection is scheduled as part of the v39 build. Current production workflow is the single v39 build; the legacy v38 workflow is manual-only and cannot publish.
