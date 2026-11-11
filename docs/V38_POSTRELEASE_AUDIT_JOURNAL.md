# v38 Post-release Audit Journal

Append-only operational journal for PR #10. Keep each checkpoint short, timestamped, and evidence-backed. This journal is stored on the PR #10 audit branch and is deliberately excluded from the workflow path filter so journal updates do not re-trigger live collection.

## Scope and invariants

- Target branch: `main`; baseline main commit: `6c856d5c4b16ff6a77ad507572a7017a4cfe2532`.
- Production release commit: `3033248ea54cb298bafded25ddcd2805d5f0e7ac`.
- Published release tag: `latest-geoip-client-v38`.
- Published GeoIP SHA-256: `e757c1b7b8ca5b47c11117784eb78ab25c59fbadc0f6ab55229827560db76800`.
- PR #10 remains Draft; its purpose is post-release evidence review only.
- All 56 target rows must remain `REVIEW`. No automatic changes to DIRECT/PRIVATE, blocked sets, GeoIP files, releases, tags, CDN or production branches.
- Do not inspect or touch PR #5 or `feature/reachability-full-ru-kz-by`. PR #6–#8 remain separate.

## Checkpoints

### 2026-11-11 19:16:05 UTC — run #7 completed successfully

- Workflow run: `43084575538`, run number 7, conclusion `success`.
- Job steps: immutable bundle verification, collector pin, parser tests, live capture, post-processing, review-only validation and artifact upload all succeeded.
- Artifact: `v38-postrelease-prefix-audit`, ID `13884984650`, ZIP size 3,981,555 bytes.
- Artifact digest reported by GitHub: `sha256:1ec1ad241b5e602b62fc35765ba07176328887d19483f1f8d915d06009e6e856`.
- Capture time: `2026-11-11T19:16:00Z`; 56 target prefixes, 224 requests, all 224 returned HTTP 200.
- Release binding verified: release commit `3033248ea54cb298bafded25ddcd2805d5f0e7ac`, GeoIP SHA above, blocked-set SHA `df909b12b985b23080075821cedc5e2f73b7b1f89abcd9950293b400ce1e4a5d`.
- Coverage reconciliation: 54 target prefixes FULL in RU, 2 PARTIAL due to approved blocked addresses, 0 NONE; PRIVATE overlap 0.

### 2026-11-12 00:24 +0500 — resumed after interrupted connection

- Re-checked PRs #6–#10 and branches. PR #10 remains open/Draft, head `773bbd89460f16d8dd31745eda5118aa611947a1`.
- `main` is unchanged at `6c856d5c4b16ff6a77ad507572a7017a4cfe2532`; `release` unchanged at `3033248ea54cb298bafded25ddcd2805d5f0e7ac`.
- Re-downloaded and unpacked artifact #7; all 56 output rows are still `REVIEW`.
- Exact-origin comparison: 50 rows have equal non-empty origin sets in all three views; 4 rows disagree; 2 have no exact NLRI in any of the three source views. The two empty rows are `94.131.190.0/23` and `178.154.128.0/18`; they must not be counted as source agreement.
- Four origin-set disagreement rows: `5.45.215.0/24`, `91.231.134.0/24`, `2a02:6b8:215::/48`, `90.156.247.0/24`.
- In 10 rows, the only apparent same-origin RPKI state difference is the textual spelling `not-found` vs `notfound`; this is a normalization bug, not evidence of an RPKI conflict.
- One genuine same-origin status disagreement remains: `5.45.215.0/24`, origin AS208398 is `invalid` in the near-real-time RouteViews exact-NLRI response and `valid` in the separate RouteViews timestamped aggregate VRP snapshot (`2026-11-11T19:00:13.443Z`). Preserve both views and their timestamps; do not merge into a single result.
- After conservative canonicalization of status labels only, expected RPKI view counts: 26 `ORIGIN_SETS_AND_STATES_MATCH`, 24 `ORIGIN_SET_DIFFERS`, 3 `NO_TIMESTAMPED_VRP_STATE`, 2 `NO_EXACT_ROUTE`, 1 `SAME_ORIGIN_STATUS_DIFFERS`.
- Archived-invalid check: `177.1.199.0/24` still has AS49505 on an exact route and route-level `invalid`, while AS401152 is `valid`; keep REVIEW. Other archived origins not observed remain REVIEW, not cleared as safe.
- Next: update PR #10 workflow post-processing to normalize `not-found`/ `notfound` for comparison only, retain raw source strings in a separate audit column, add regression tests, run parser tests, and re-run validation against the immutable captured artifact without making a new live query unless required.

### Journal discipline

Add a checkpoint after every meaningful phase: artifact receipt, parsing result, discovered issue, code correction, test completion, CI completion and PR state change. Do not wait until the end of a long task to record the work. Record exact run IDs, commit SHAs, artifact IDs and hashes whenever available.

### 2026-11-12 00:31 +0500 — RPKI normalization correction implemented and locally tested

- Added `.github/scripts/normalize_v38_postrelease_prefix_audit.py` and eight regression tests in `.github/scripts/test_normalize_v38_postrelease_prefix_audit.py`.
- Canonicalization changes only comparison labels: `not-found`, `notfound` and `not_found` are treated as the same `not-found` value. Raw values remain preserved in the output's source fields and are also recorded in `RPKI_STATUS_LABEL_VARIANTS`.
- True status conflicts remain explicit in `RPKI_STATUS_CONFLICTS`; `valid` and `invalid` are never collapsed.
- Local tests against the exact run #7 artifact: 8/8 passed.
- Local reprocessing of the exact run #7 56-row TSV: 56 rows retained as REVIEW; 10 spelling-only variants; 1 semantic conflict (`5.45.215.0/24`, AS208398 invalid vs valid).
- Corrected view counts: 26 `ORIGIN_SETS_AND_STATES_MATCH`, 24 `ORIGIN_SET_DIFFERS`, 3 `NO_TIMESTAMPED_VRP_STATE`, 2 `NO_EXACT_ROUTE`, 1 `SAME_ORIGIN_STATUS_DIFFERS`.
- The postprocessing code and tests are committed on PR #10 branch; workflow updated to run those tests and the normalizer. Awaiting GitHub Actions verification.

### 2026-11-12 00:36 +0500 — GitHub run #10 validated the RPKI normalizer

- Audit workflow run: `43092507694`, workflow run number 10, commit `33dd1bbd501bbc150432f45b8b98db4f5cfa2a10`, conclusion `success`.
- CI executed both parser suites: 8 existing post-release audit tests + 8 RPKI normalization regression tests; all passed.
- Fresh capture: `2026-11-11T20:05:39Z`; 56 prefixes; 224/224 HTTP 200. RouteViews aggregate VRP snapshot timestamp: `2026-11-11T20:00:13.348Z`.
- Uploaded artifact: ID `13889422624`, size 3,971,238 bytes, GitHub digest `sha256:64f9cfc536b57d33f53926a05bcce987d67cb112d8ad292926c0ae7f39ee6b1a`.
- Artifact files were downloaded and independently rechecked. Manifest SHA-256 is `4850f77f72e0f49f62c158b9ca02d181a502cb64cc8aa4be66f59400566c496a`; TSV SHA-256 is `4c7b4718c46f541bbf52184dd05bf6af6ae59388b7b65e4b640c3ce6ee2e5898`; exact capture JSON SHA-256 is `8ff3b193b34bac11026f6d838b422efcbf03134f0089f3d225bef571666ac47e`; raw observation gzip SHA-256 is `44ea689d7b1a23bf96fb626137e55bb3ceed33e268b8508667df62c4bbe84a59`.
- Exact origin cross-check: all three exact-NLRI source sets returned non-empty observations for all 56 targets. 52/56 origin sets agree; 4/56 disagree. Disagreements:
  - `5.45.215.0/24`: RouteViews and RIPEstat Routing Status `13238, 208398, 212066`; 24h Looking Glass also sees `207304`.
  - `91.231.134.0/24`: RouteViews and Looking Glass `28709, 47541, 47764`; Routing Status sees `47541, 47764`.
  - `2a02:6b8:215::/48`: same pattern as `5.45.215.0/24`; Looking Glass additionally sees `207304`.
  - `90.156.247.0/24`: RouteViews and Looking Glass `201512, 57073`; Routing Status sees only `57073`.
- RPKI comparison after normalization: 26 origin sets/states match; 24 origin sets differ; 3 have no timestamped VRP state; 2 have no exact route; 1 genuine same-origin status conflict remains. Ten `not-found` vs `notfound` spelling variants are retained in a separate manifest/TSV list and are not semantic conflicts.
- Genuine status conflict: `5.45.215.0/24`, AS208398 near-real-time RouteViews route-level state `invalid` vs two-hour aggregate VRP snapshot `valid`. Preserve both observations; do not resolve by choosing one.
- Archived-invalid queue: 19 rows remain REVIEW. `177.1.199.0/24` still observes archived-invalid AS49505 in exact RouteViews with `invalid`, while AS401152 is `valid`. The other 18 archived-invalid origin entries are not currently seen as exact origins (one target has no exact route); their statuses are not converted to approval/clearance.
- v38 overlap remains 54 FULL, 2 PARTIAL because of approved blocked IPs, 0 NONE; PRIVATE overlap remains 0. All 56 TSV rows are `REVIEW`.
- Production pin still verified: release branch commit `3033248ea54cb298bafded25ddcd2805d5f0e7ac`, GeoIP hash `e757c1b7b8ca5b47c11117784eb78ab25c59fbadc0f6ab55229827560db76800`, blocked-set hash `df909b12b985b23080075821cedc5e2f73b7b1f89abcd9950293b400ce1e4a5d`.
- Related PR-triggered GeoIP workflow run #81 (`43092778886`) on the audit branch completed candidate build/validation and uploaded candidate artifact `13888274829`; both GitHub Release and release-branch publication steps were explicitly `skipped`. It did not change production.
- PR #10 remains Draft. A second audit run (#11, `43092778686`) was queued by a subsequent PR synchronization while this journal was updated; it is being allowed to finish rather than assuming its outcome. No production action is connected to this audit run.

