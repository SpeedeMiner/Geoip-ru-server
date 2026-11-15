# v41 input mirror validation — 2026-11-15

Extracted the mirror validation change from audit commit `3393c294` into a separate PR against `main` (`fab8870`). The broader audit in PR #44 is unchanged. This change does not alter the reviewed routing policy or the publication job.

- Required downloads are validated in a staging file. The accepted mirror alone is recorded as downloaded, with the normal size and digest. A rejected payload is discarded before trying the next configured URL. If none works, the job fails rather than reusing a file from a previous run.
- The five RIR inputs must match the expected registry, delegated-stat structure and existing freshness rule. Both RIR inventory builders use the same UTC date as mirror validation. The existing LACNIC ASN count discrepancy is reported while address record counts remain strict. IANA CSV, the ipverse archive, official Telegram, required block feeds and pinned v38 inputs are checked before acceptance.
- The ipverse check reads records without extraction, bounds expanded size, checks gzip and tar integrity, and validates the aggregate record structure. Existing block-feed thresholds are shared between the download check and the block-preparation step. Optional `ipresolve` fallback and the GitHub upstream group resolver are unchanged.
- Regression cases include HTML on an apparently successful transfer, empty/wrong/stale/truncated RIR inputs, exhausted mirrors, invalid CSV or archive, and digest mismatches. Fixed input validation uses the archived release `58ca38fef851028b51c19f83c7a24c181eaadf97` and its manifest-bound source bundles, with UTC reference 2026-11-15.

Next independent change: exact block-feed deltas and a verified live baseline for `ipresolve` fallback. PR #46 handles the separate DIRECT delta report.
