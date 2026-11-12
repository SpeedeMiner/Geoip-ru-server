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
