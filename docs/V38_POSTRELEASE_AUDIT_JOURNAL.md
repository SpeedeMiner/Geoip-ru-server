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


### 2026-11-12 10:51 +0500 — resumed; normalized audit CI verified; independent RIPEstat run queued

- Re-fetched PR #10 and live refs. PR #10 is OPEN/DRAFT, base `main`, current head `62d290fab955536eb5a123f2897b66509e9596bd`; purpose remains review-only. No merge/readiness transition performed.
- Production refs unchanged: `main=6c856d5c4b16ff6a77ad507572a7017a4cfe2532`; `release=3033248ea54cb298bafded25ddcd2805d5f0e7ac`.
- Verified normalization was not left merely as a local change: workflow run #11 `43092778686`, head `5332f4c7d81f26ec8d159990ac69aa2e0ca46564`, completed `success`. All steps passed, including parser/normalizer tests, live capture, normalization, invariant validation and artifact upload.
- Run #11 artifact: `v38-postrelease-prefix-audit`, ID `13889802705`, size 3,968,416 bytes, GitHub digest `sha256:38ceb79719b7f7a264ec1aeb2acb1bf9535611b9267e60deb682e0df6976f32a`. Logs show label variants recorded separately; the only genuine same-origin RPKI conflict remains explicit. All 56 rows remain REVIEW.
- Confirmed the normalizer at run #11's exact source commit has blob SHA `e74b6b88b7e1b2b08d4adca4e42379f6d9990618`; `not-found` and `notfound` are aliases for comparison only, while raw source strings remain in their original columns and variants field. `valid` and `invalid` remain distinct.
- Subsequent enhancement adds independent RIPEstat RPKI validation for exact prefix/origin pairs. Current PR head `62d290f...` includes collector `.github/scripts/collect_v38_ripestat_rpki_validation.py`, normalization and workflow step. This enhancement has not yet produced evidence.
- Latest audit workflow run #14 `43095830979`, head `62d290fab955536eb5a123f2897b66509e9596bd`, was still `queued` at the latest API check; job list empty, no artifact. Runs #12 and #13 are also queued; newest run #14 is the one matching current PR head. Do not treat queue state as successful capture or infer results.
- Related general v38 PR build run #84 `43095831006` is also queued for the same current head; no production push/release is authorized by this review PR.
- Next: monitor run #14 until it starts/completes. If successful, inspect its artifact and verify per-origin validation counts, raw response retention, release-manifest binding, all 56 REVIEW statuses and no production writes. If it remains queued, inspect workflow-run queue/concurrency/runner state rather than spawning duplicate live captures. Do not re-run source collection unnecessarily.
- Safety boundaries retained: no PR #5 access; no changes to `main`, `release`, tag, release assets, CDN, production GeoIP or classifications. BGP remains optional and was not used.
