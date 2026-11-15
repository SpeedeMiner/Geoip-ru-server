# v41 observability and input resilience journal

## 2026-11-16 00:10 UTC+05 — integration checkpoint

- Task: develop option B without changing the DIRECT admission policy, PR #5,
  production CDN file inventory, or the meaning of fallback states.
- Starting main `c0d2a01ba1fb5f5c0e48965d614945348083a900`; release
  `e20cf733a13d92040134895ebd580b7c9060fa3b`; CDN
  `8a226b83c82323c869054ca5b299612ad3a91e2d`. Production build
  [43747743430](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43747743430)
  passed and reports public CDN readback verified. The release and CDN git
  trees identify the same three client blobs; the CDN root has three files.
- PR #49 already updates the project status in a separate branch and must not be
  overwritten or treated as merged. The project attachment is an older snapshot.
- Created a local integration of PR #47
  `6ff13ccda6bd73aebca8a607e1163bbbac287f6b`, then PR #46
  `9f6153b0f5b7e8d924eb94ae13cac11e65702775`; both original PR commits are
  retained as merge parents. Both merges and `git diff --check` were clean.
- 279 Python tests passed locally; Bash syntax and CDN workflow guard passed.
  A local Go test initially encountered `/usr/bin/go`, which is not the Go
  compiler. An official Go 1.26.10 archive was downloaded and its SHA-256
  `ccfe7ae822d2c2f41f4fe7c956199967a4dac22d0ee0d2b2bfdb440aab3b20c5`
  checked against the official release metadata; the Go test remains pending.
- Fixed-input verification uses production artifact 14174864343, ZIP SHA-256
  `01b661e70d58af4b5b1f93948ed5482aaf4b47c69736b12ee5b68aff84f7ebe9`;
  ZIP CRC and the full release manifest passed. Registry inputs restored from
  the manifest-bound archive. Overlay and block-input replay is in progress;
  do not infer its result from the unit tests.
- Next: verify fixed-input output and exact DIRECT delta; run Go tests and
  exact-head CI; isolate the ASN, global-network and Hydra advisory reports
  from #44 without duplicating changes already in main. Keep unknown provider
  coverage, missing baselines and actual observed losses distinct from zero.

## 2026-11-16 — validated integration and advisory composition

- PR #50 head `139e9ddd9d550a5f2dde74d29ef54e633cbd5c53` passed [v41](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43751030476),
  [v39](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43751030427),
  [prefix audit](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43751030493)
  and [lint](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43751030397).
  The PR publish job was skipped. The GitHub merge commit
  `c06bfd9df6212ef820d01f57d71291f1fd09da08` and PR head have tree
  `92946da44806a19538b005fbe72cadcb089dc5d9`.
- Candidate ZIP [14175914609](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43751030476/artifacts/14175914609),
  SHA-256 `fe18a60abbaa782882c3dba69cc6ba3dc7b74b7e5e932b819cae1010b02d6102`,
  passed CRC and release-manifest validation. DAT, both SRS, effective block
  mask and input provenance match pinned release `e20cf733` byte-for-byte.
  Its exact DIRECT artifact reports IPv4 +0/−0, IPv6 +0/−0, and unchanged
  PRIVATE. The Antifilter report has no normalized feed or layer delta and
  does not claim upstream freshness.
- Go 1.26.10 tests and build passed. The retained RIR, IANA, ipverse,
  Telegram and mandatory Antifilter inputs passed the new staged validators
  with original UTC date 2026-11-15. LACNIC's published ASN count discrepancy
  was logged; address record totals still matched. The v37 base was rebuilt
  byte-for-byte from retained inputs, SHA-256
  `3b196ba746ee67f9b993337e2725887f130a280e4e76e53cb57448bf94d1eb8a`.
  Rebuilt v41 DAT SHA-256
  `b17fe26ccdcb8d272e6233ec9686a514b309e9d75e75653313a75f329b70fae7`
  also matched; all three blocked layers and effective mask matched.
- PR #51 head `f8a2dcbe112f532b93ec0915e075ec7c8d858281` isolates
  ASN/IPv6/provider/Hydra advisory reporting; its retained inputs, exact
  evidence and 285-test local result are documented in
  [the advisory journal](V41_ADVISORY_EXECUTION_JOURNAL_20261116.md).
- Composition of #50 and #51 required one conflict resolution in
  `extract_ru_asn_prefixes_v41.py`: keep both the shared ASN classifier
  import and the shared minimum ipverse record-count import. Workflow changes
  merged automatically. Composition tests and exact-head Actions are pending.
  No production refs or PR #5 were changed in this checkpoint.

## 2026-11-16 — one release identity across advisory reports

- After composing PR #50 and #51, identified that their independent reads of
  `release` could resolve different commits if publication happened mid-run.
  This integration now fetches and checksum-verifies the release DAT once,
  then passes the same full SHA to the DIRECT, Antifilter, ASN and scoped
  provider reports. The provider JSON records that release SHA and the exact
  DAT hash. Missing or invalid baseline yields unknown comparisons, not zero;
  ASN may still report candidate-only observations.
- A fixture runs the actual workflow's baseline shell with fake Git. It checks
  successful SHA export, failed fetch and incorrect DAT checksum. Neither
  failure writes a release SHA, and both record unknown comparison status.
- Local pre-integration code tree passed 301 Python tests, Go tests, YAML
  parsing and CDN guard. On retained production inputs its block layers,
  v41 DAT, source metrics and provenance are byte-identical; IPv4/IPv6 delta
  is +0/−0 and PRIVATE unchanged. The independent hard-policy gate returned
  zero hard/DIRECT intersections for both families; all 14 official Telegram
  CIDRs passed. The shared-baseline change adds workflow and reporting logic;
  its combined exact-head CI and full local test run are pending.
