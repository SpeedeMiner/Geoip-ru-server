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
