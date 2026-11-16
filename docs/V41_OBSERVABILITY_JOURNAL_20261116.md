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

## 2026-11-16 — complete combined CI and retained evidence

- Exact code head `f7230e5180587fc078737e15c10c982197b3c4e9` passed [v41](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43752966991),
  [v39](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43752965990),
  [prefix audit](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43752966030)
  and [lint](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43752966017).
  The publish job was skipped. CI merge commit
  `949321ecf163bf5b739f3b032d9b7481f24f720f` and code head have identical tree
  `b7017e82bf1151efc5731a75446cc3d6a7b8a1b2`. Full local run: 303 Python
  tests; Go tests, CDN guard and actual-shell baseline failure fixtures passed.
- Verified [candidate ZIP 14177570596](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43752966991/artifacts/14177570596),
  SHA-256 `86cfc5b0d48f1887db93660c1f61bce89b42bd2800fd21a8d428236451de4d28`,
  all ZIP CRCs and release manifest. Its DAT, both SRS, effective block mask
  and input provenance are byte-identical to release `e20cf733`. The direct
  delta is IPv4 +0/−0 and IPv6 +0/−0, with PRIVATE unchanged.
- Verified [ASN/provider ZIP 14177017480](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43752966991/artifacts/14177017480),
  SHA-256 `947f8a07619bb9ef1c88c32e89bf8b0002632659001d41f779b6f9c53c0e7e77`.
  All seven ASN candidate and seven baseline input hashes, all 35 provider
  input bindings and all 11,124 TSV/JSON rows match. Cloudflare, AWS and
  Google scoped inputs were available; Akamai and Discord remained unknown.
  For 118 watched ASN/family pairs, there are no final-DIRECT loss pairs;
  21 absent observations remain unconfirmed.
- The verified DIRECT, Antifilter, ASN and provider artifacts all identify
  release `e20cf733a13d92040134895ebd580b7c9060fa3b` as the comparison.
  The Antifilter report records unknown upstream freshness. GitHub `main`,
  `release`, `cdn` and PR #5 were not modified. Next: validate this
  documentation-only checkpoint and recheck current refs and source drift
  before any production integration.

## 2026-11-16 — monitor scheduled production inputs as well as PRs

- PR-only diagnostics would miss fresh source changes in daily scheduled
  builds. The shared-baseline DIRECT, Antifilter, ASN and provider/Hydra
  reports are therefore enabled for both pull requests and builds on main,
  including scheduled and manual runs. Their inputs are compared before the
  publish job using one previously verified release commit.
- Diagnostic failures remain advisory (`continue-on-error`); missing inputs
  are unknown, and no new publication gate or routing change is introduced.
  Reports and provider snapshots are Actions artifacts, not CDN assets. The
  publish job waits for the build job, so diagnostic execution can delay
  publication until it completes or its bounded step timeout expires.
- Added regression assertions for main and PR execution conditions, bounded
  timeouts, including advisory artifact uploads, and advisory-only failures;
  checksum and failed-fetch fixtures still
  verify that no baseline SHA is emitted on failure. Local/full and GitHub CI
  for this updated production-workflow scope are required before integration.
- Provider summaries show IPv4/IPv6 additions and removals separately for the
  DAT transition and for the provider-feed change against the dated fixed
  capture. New scoped overlaps produce an advisory warning. A watched ASN
  previously selected in DIRECT and actually absent from the new final DAT
  likewise produces an advisory warning; loss of origin attribution alone
  does not. Historical Hydra-only attribution remains unknown.


## 2026-11-16 — exact-head CI and observed CDN cache divergence

- Code head `97e76350d66e31f5615000faf4f1865ea2d75888` passed [v41](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43754263443), [v39](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43754263418), [prefix audit](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43754263425) and [lint](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43754263424). Production publish was skipped. The v41 log records 304 Python tests, DAT SHA-256 `b17fe26ccdcb8d272e6233ec9686a514b309e9d75e75653313a75f329b70fae7`, official Telegram 14/14 pass and both SRS compile/decompile coverage checks. Exact-head artifacts exist but were not independently downloaded during this checkpoint.
- Separately rebuilt both SRS from the fixed-input DAT using sing-box 1.13.12, archive SHA-256 `1540533adb3df24f5ad5f14b5c7ca3dbc2401b10a1c1eb278fcadcada47ec6c4`. Decompiled IPv4/IPv6 coverage passed and both SRS were byte-identical to pinned release `e20cf733a13d92040134895ebd580b7c9060fa3b`.
- At approximately 2026-11-15 19:52 UTC, from one observation point, pinned GitHub Raw and `cdn.jsdelivr.net` delivered the current DAT `b17fe26...` and RU SRS `c60b8a1...`. At that same point `fastly.jsdelivr.net` and `gcore.jsdelivr.net` returned older DAT `5d7e9dd...` and RU SRS `21c54a6...`. PRIVATE SRS matched the current release at all four hosts. This is a bounded vantage-point observation, not a global CDN availability claim.
- Both legacy jsDelivr tree and flat inventories advertised the older DAT (512067 bytes) and RU SRS (128250 bytes), while the pinned GitHub CDN tree contains 512533 and 128392 bytes. The current read-only `--verify-git-tree` audit therefore failed with `pinned GitHub CDN tree differs from public inventory`; the audit without that flag subsequently compared stale inventory to current GitHub Raw and also failed. The old inventory endpoint's response advertised a deprecated successor and an approximately 11-hour cache age. Endpoint semantics and the present state need independent rechecking; no live purge, repair workflow, production ref change or global conclusion was made.
- Additional cache-bypass and metadata requests were not executed because automatic approval review could not be completed after a usage limit was reached. This was not a safety determination. Next: when that limit is resolved, recheck exact branch refs and CDN bytes from more than one vantage point, compare the advertised metadata API with GitHub, and only then consider the existing CDN repair procedure. Independently verify the exact-head CI artifacts; keep PR #52 as a draft while CDN delivery and production effects remain unresolved.

## 2026-11-16 — fresh CI candidate requires review

- On documentation-only head `daa6b47f3acfc120199aef374364e66a4d99f68d`, [v41 run 43802793842](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43802793842) passed, including 304 Python tests and SRS checks; publishing was skipped. Its DAT SHA-256 is `3161fdd5eda4d9c2f962a3c8d1bd0c187e5cab9260284a13679b289a9a6d0855`, versus published `b17fe26...`. The candidate differs; the exact address delta, source attribution and downloaded artifact integrity have not yet been independently verified. Do not infer a cause from the hash alone.
- Prefix validation and lint succeeded; v39 was still running when checked. Prior code head `97e76350d66e31f5615000faf4f1865ea2d75888` passed all workflows.
- Additional CDN cache probes were not executed because automatic approval review could not complete due to a usage limit. The earlier CDN observation is a point-in-time result, not a current global status. Keep PR #52 draft until the candidate delta and CDN behavior can be reviewed.

## 2026-11-16 — independently checked candidate delta

- For [v41 run 43803517572](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43803517572), independently downloaded candidate and advisory ZIPs and verified their SHA-256 against Actions artifact digests. Decoded the candidate DAT and pinned release commit `e20cf733a13d92040134895ebd580b7c9060fa3b` DAT with an independent minimal protobuf reader and recomputed network-set subtraction. DAT hashes are respectively `3161fdd5eda4d9c2f962a3c8d1bd0c187e5cab9260284a13679b289a9a6d0855` and `b17fe26ccdcb8d272e6233ec9686a514b309e9d75e75653313a75f329b70fae7`; the independently computed delta exactly matches the advisory report.
- IPv4 added (2,048 addresses): `48.103.230.0/24`, `85.92.155.0/24`, `85.92.156.0/24`, `152.234.249.0/24`, `201.58.141.0/24`, `201.58.148.0/24`, `213.145.79.0/24`, `213.226.121.0/24`. Removed (1,280 addresses): `177.29.253.0/24`, `177.122.229.0/24`, `177.122.241.0/24`, `177.166.74.0/24`, `177.166.78.0/24`. IPv6 added: `2a0b:4e07:f4::/48`, `2a0f:6280:10ac::/48`; IPv6 removed: none. PRIVATE address sets unchanged.
- All additions are covered by candidate selected RIR-origin ASN prefixes (the `85.92.155.0/24` delta is part of selected `85.92.154.0/23`); this establishes candidate-layer attribution, not by itself the reason for each change. All five removals appeared in the previous selected ASN prefix file; none overlaps the current selected ASN or regional RIR prefix files. The retained build manifests show changes in ipverse BGP, RIPE and LACNIC snapshots, and Antifilter community input, so causation and validity of the removals still require review. Priority-ASN advisory reports no loss among its 118 watched ASN/family pairs, with missing observations still subject to its unknown-state caveat.
- At commit `c7af7a722e09034b1302b15f00f9bfc1e8348746`, v41, v39, prefix audit and lint passed; publish was skipped. Current CDN delivery remains unverified following the earlier usage-limit review failure. PR #52 remains draft.

## 2026-11-16 — investigation of five removed IPv4 prefixes

- Compared the complete retained ipverse archives from the previous published build [43747743430](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43747743430) and candidate build [43803517572](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43803517572). The production artifact ZIP SHA-256 `01b661e70d58af4b5b1f93948ed5482aaf4b47c69736b12ee5b68aff84f7ebe9` matched GitHub's artifact digest. Previous ASN/origin mapping was `177.29.253.0/24` AS219306, `177.122.229.0/24` AS219216, `177.122.241.0/24` AS218568, `177.166.74.0/24` AS219262, `177.166.78.0/24` AS219238. All five old ASN entries are still RIPE RU allocated in both retained registry snapshots, but the corresponding prefixes disappeared from their current ipverse lists.
- A scan of every `ipv4-aggregated.txt` entry in both complete ipverse archives finds each of these exact /24s under its former origin in the previous snapshot and under AS137410 in the current snapshot. Current ipverse metadata labels AS137410 `MDMSL-AS-AP`, MiM Digital Marketing Solution Ltd., country BD. This establishes a change in the origin reported by those snapshots, not the physical location, RPKI validity, cause of the change, a routing hijack, or accessibility from Russia. A /24 exact-match scan does not exclude alternative covering routes.
- In both retained registry inputs, the larger allocations covering these five addresses carry `VG` in RIPE delegated statistics. That is a registry country field, not proof of current hosting location. These ranges therefore do not enter through the RU/BY/KZ address-allocation layer; with the previous RU origins absent from the current ASN selection, their loss from DIRECT is consistent with the observed pipeline inputs. No addresses have been pinned back or removed manually. Independent, time-matched routing/RPKI and operator evidence is needed before deciding whether to preserve them explicitly.

## 2026-11-16 — CURATOR-CDN instruction

- User confirmed AS219306 CURATOR-CDN must remain included. Added it to the company ASN registry, shared-infrastructure classification, and priority ASN monitoring. Observed AS219306-origin prefixes are selected independently of the RIR country and receive shared-infrastructure resolver-only protection; existing hard exclusions remain in force. Missing observations are reported rather than silently treated as an empty authoritative origin set.
- This does not manufacture an AS219306 BGP observation or automatically pin `177.29.253.0/24`: in the latest retained snapshot that prefix appeared under a different origin. Preserving the service and proving control of that particular prefix are distinct questions. Check current routing and operator evidence before any static pin.
- Full Python suite passed before the additional registry consistency test; rerun targeted tests and CI for this change. No release or production change.
