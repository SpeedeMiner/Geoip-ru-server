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

