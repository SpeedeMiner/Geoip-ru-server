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

## 2026-11-16 — CURATOR-CDN exact-head CI and remaining loss

- All four PR checks passed on code head `e9188f48b124f37c3b672a678f1ce15b6b83e9db`; [v41 run 43807991550](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43807991550) generated advisory artifacts and skipped publishing. Independently downloaded both direct-delta and ASN advisory ZIPs and verified their SHA-256 against GitHub Actions artifact digests.
- The final candidate DAT remains `3161fdd5eda4d9c2f962a3c8d1bd0c187e5cab9260284a13679b289a9a6d0855`. Compared with release `b17fe26ccdcb8d272e6233ec9686a514b309e9d75e75653313a75f329b70fae7`, the ASN advisory now correctly flags the AS219306 IPv4 pair: the previously selected `177.29.253.0/24` is absent in the candidate final DIRECT, 256 addresses. Candidate ASN observation is `FAMILY_NOT_OBSERVED`; the report marks absence unconfirmed. IPv6 has no previous selected address space and is also unconfirmed.
- Adding an ASN to the company registry protects its currently observed selected-origin prefixes, but does not retain a previous prefix after its observed origin changes. Therefore the user goal of retaining the prior CURATOR-CDN coverage is **not yet fulfilled** for this /24. This PR remains draft; independently verify current origin, RPKI and operator control and make an evidence-backed retention decision before merging. Continue to preserve existing hard-block and CDN publication policy.

## 2026-11-16 — additional CDN and protection ASNs

- User requested review and addition of six CDN/protection networks. Retained RIPE delegated snapshot registers AS57363 CDNvideo, AS204720 Global Cloud Network and AS201706 Servicepipe as RU; ipverse identifies those entities separately. Added the three to company registry, SHARED_INFRA exception policy and advisory watchlist. They were already eligible for RIR-RU origin selection; classification additionally affects resolver-only protection, while hard exclusions continue to apply. No corporate ownership relationship is inferred between the companies.
- AS60068 CDN77, AS59796 StormWall and AS199524 Gcore are registered respectively GB, SK and LU in the retained registry input. Added to advisory monitoring only; their global origin prefixes are not automatically admitted to DIRECT. Russian peering alone does not prove that all their prefixes serve RU/BY/KZ; review individual prefix/service evidence before a policy change.
- Retained ipverse snapshot observed IPv4/IPv6 prefix counts: 57363 39/7, 204720 34/8, 201706 12/1, 60068 194/32, 59796 9/6, 199524 307/50. These are snapshot counts, not address unions or proof of geography.
- AS219306 previous /24 remains unresolved; no static pin. Existing warning, release gate and hard blocks are unchanged. Run tests and review the new exact-head CI and output delta before considering merge.

## 2026-11-16 — validation and development plan

### Progress and verified state

- **Done:** integrated staged mirror validation, a pinned-release DIRECT delta, priority ASN/IPv6 monitoring and scoped global-provider/Hydra advisories in draft PR #52. Reports run in PR and scheduled/main builds, preserve unknown states, and are advisory; publish uses the established gates and CDN binary contract. PR #5 was not changed.
- **Done:** classified AS219306 CURATOR-CDN and the three RU-registered CDN/protection ASNs AS57363, AS204720 and AS201706 as shared infrastructure, with resolver-only protection and existing hard exclusions retained. Added these four plus AS60068, AS59796 and AS199524 to priority observation; the latter three are monitoring-only, not global ASN admission.
- **Done:** all four workflows passed on code head `dad2e800cb9e14428849f626ea3bac76de03f446`, including [v41 run 43809352866](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43809352866); publish was skipped. The full local Python suite passed 305 tests. Independently downloaded DIRECT-delta and ASN advisory artifacts and verified SHA-256 against Actions digests (`a058ed2c808ccb41c30cbf55e684dffe5fc8d9e5c7fdc8ce14827d4250f42ba5`, `24819d07925102071da205ac49fc7eafcf87df125db61042b782c34c8d0b8e19`).
- **Done:** on that run observed AS57363, AS204720 and AS201706 prefixes were fully represented in the selected/direct layers for both families; observed IPv4 unions respectively 16,640, 14,848 and 6,400 addresses. No previous selected DIRECT space was lost for these pairs. The three monitoring-only global ASNs had no selected-origin space; this does not imply their ranges have no overlap with DIRECT via other sources. Counts are per ASN, not additive address unions.
- **Open:** candidate DAT `3161fdd5eda4d9c2f962a3c8d1bd0c187e5cab9260284a13679b289a9a6d0855` differs from release `b17fe26ccdcb8d272e6233ec9686a514b309e9d75e75653313a75f329b70fae7` by +2,048/-1,280 IPv4 addresses and +2 IPv6 /48, -0 IPv6, with PRIVATE unchanged. Of 132 watched ASN/family pairs, one pair has prior selected space lost from final DIRECT: AS219306 IPv4 `177.29.253.0/24`; no current origin observation is confirmed. Do not treat an absent observation as proof the CDN no longer serves the prefix.

### Development queue (in priority order)

1. **In progress — CURATOR-CDN:** obtain independent, time-stamped BGP and RPKI evidence plus evidence of operator/service control for `177.29.253.0/24`; compare with previous AS219306 and newer AS137410 observations. Decide whether a bounded static entry is warranted; otherwise leave it in a review queue. Ensure any retention preserves PRIVATE, hard-block and Telegram protections. Record evidence and tests. User instruction is to retain CURATOR-CDN; current candidate does not yet retain the historical /24.
2. **Pending — remaining four removed /24s:** review each changed origin and operator/service evidence, and document a decision consistent with RU/BY/KZ and protected-infrastructure policy; do not infer a routing hijack from the snapshots alone.
3. **Pending — CDN delivery:** once the earlier usage-limit review failure is resolved, compare pinned Git refs, canonical and provider endpoint bytes and current metadata from independent vantage points. Record timestamps and hashes. The previous divergence is a historical observation, not a statement about current global delivery. Do not bypass the denied CDN probes or perform a purge without a verified diagnosis.
4. **Pending — global CDN networks:** examine individual RU/BY/KZ service prefixes and overlap with final DIRECT for CDN77, StormWall and Gcore using dated source/provenance evidence; propose narrowly scoped additions only where justified. Keep report-only observations separate from policy admission.
5. **Pending — integration and release readiness:** after the unresolved coverage and delivery issues have decisions, rerun all checks on the exact final head, independently verify candidate DAT/SRS, address deltas and hashes against pinned source/release, and review provider overlap plus advisory warnings. Preserve audit files outside the CDN. Only then assess PR #52 for readiness; scheduled release production behavior must be verified as a separate step.

Progress rule: append dated evidence, artifact identities, decisions and remaining unknowns here; do not report a task complete merely because an advisory CI step returned success. Do not modify PR #5 or production refs while these reviews are open.

## 2026-11-16 — initial overlap review for global CDN origins

- Examined the candidate ASN advisory from run 43809352866 and verified the retained local `geoip_RU.dat` and `as-ip-blocks.tar.gz` independently against the report's candidate hashes. Intersections are between each ASN's observed prefix union and final DIRECT, not proof of an admission source, address ownership, regional deployment or Russian accessibility. Different ASN intersections may overlap and must not be summed.
- AS59796 StormWall: observed IPv4 union 4,608 addresses, of which 1,280 intersect DIRECT; observed IPv6 intersects DIRECT by zero addresses in this snapshot.
- AS60068 CDN77: observed IPv4 union 131,840 addresses, of which 255 intersect DIRECT; IPv6 intersection is 309485009821345068724781056 addresses (one minimal CIDR). This is address-space arithmetic, not a count of active hosts.
- AS199524 Gcore: observed IPv4 union 114,944 addresses, of which 3,840 intersect DIRECT; IPv6 intersection is 51983791796684980802813952 addresses (24 minimal CIDRs). This is address-space arithmetic, not a count of active hosts.
- These global ASN observations had zero prefixes selected by their own ASN in this build; intersections can arise through other sources and need per-prefix provenance and service evidence. No blanket addition or removal is justified by this aggregate alone. Next: generate/review exact intersecting CIDRs and source layers before proposing policy changes.

## 2026-11-16 — exact CDN overlap and source-layer review

- Independently downloaded candidate build artifact 14200111061 from run 43809352866; its ZIP SHA-256 `45ca834dc5170749b4a575ba9b08a601fb156683be36491fe576625318be2bc0` matched Actions. The retained `geoip_RU.dat` and ipverse snapshot match the candidate hashes bound to the priority-ASN advisory. Used the existing `read_layers`/`split_evidence` implementation and exact interval intersection with the candidate DIRECT set. The resulting [96-row TSV](V41_CDN_ORIGIN_DIRECT_OVERLAPS_20261116.tsv) has SHA-256 `8ce086c6d0e6ad013fd673b7b315fdda0ad1658fbd5222416f63def8aa217ccd`.
- Totals independently agree with the ASN advisory: AS59796 IPv4 1,280, IPv6 0; AS60068 IPv4 255, IPv6 `2a02:6ea0:dd00::/40`; AS199524 IPv4 3,840 and IPv6 51983791796684980802813952 addresses. Rows are split at every layer boundary, so row counts are not counts of provider prefixes and ASN totals can overlap.
- Examples: CDN77 `37.19.202.0/24` intersects DIRECT except `37.19.202.24/32`; the retained v37 base and multiple RU-labelled upstream datasets cover the included parts. StormWall `185.121.243.0/24` has overlapping Hydra, RU-labelled upstream and selected AS43298 evidence on parts. Several Gcore IPv4 and IPv6 ranges coincide with v2fly KZ and v37 base; other ranges overlap RU-labelled inputs and Hydra. These are same-snapshot input-layer intersections, not proof of a unique cause, ownership, service geography, direct accessibility or an exact per-prefix admission history. In particular upstream layers may overlap independently and Hydra is a policy layer, not geolocation evidence.
- All four workflows passed on documentation head `6032ea5f1ffee67cf1d35906fd88340d89f7dcca`; the previous code head had already passed its checks. No mass CDN removal, network admission, or production changes were made. Next: review the listed ranges with operator/service and regional evidence and consider reproducible provenance automation; keep CURATOR-CDN and remaining /24 decisions open.

## 2026-11-16 — regional registration review of CDN overlaps

- Intersected the 96 evidence segments from `V41_CDN_ORIGIN_DIRECT_OVERLAPS_20261116.tsv` with allocated/assigned address rows from all five delegated registry input files retained inside candidate build artifact 14200111061. Produced [96-row registry table](V41_CDN_ORIGIN_REGISTRY_OVERLAPS_20261116.tsv), SHA-256 `2d6988cb287c65e0177d02f5708928ce83eec6efc46b8bfc773c79238110c237`. The country is the delegated allocation country field; it is not proof of current origin, service location or reachability. Registrations may describe allocations broader than the intersection, and separate provider sets may overlap.
- StormWall AS59796 IPv4: 512 of 1,280 intersecting addresses are covered by RU allocations (`193.84.85.0/24`, `193.84.88.0/24`); 768 by SK allocations (`185.121.240.0/24`, `185.121.242.0/23`). There is no IPv6 overlap in this snapshot. Under the established policy retain RU ranges and review other evidence for SK ranges; these are review notes, not routing changes.
- CDN77 AS60068: all 255 overlapping IPv4 addresses in `37.19.202.0/24` excluding `.24`, and overlapping IPv6 `2a02:6ea0:dd00::/40`, are under GB allocations in the retained snapshot. The existing RU-labelled upstream coverage may still be relevant; it is not proof of current RU service usage. Do not remove or add addresses on allocation country alone.
- Gcore AS199524: 512 IPv4 addresses (`91.188.250.0/24`, `185.109.31.0/24`) are under CY allocations, 3,328 under LU; the overlapping IPv6 space is under LU allocations. These registry tags do not settle regional service use; inspect the detailed table and v2fly KZ, RU and Hydra source evidence before any decision.
- All four workflows passed on documentation head `89239b7f9c745247916d8b333043fb223a560bda`. No address was removed, pinned, or published. Continue operator/service evidence review and exact-head checks; AS219306 historic /24 remains unresolved.

## 2026-11-16 — five-prefix review checkpoint

- Reverified SHA-256 identities for the retained published and candidate DAT and ipverse archives; created the [five-prefix evidence and decision queue](V41_FIVE_REMOVED_PREFIX_REVIEW_20261116.md). It distinguishes the historical AS219306 observation from current operator control and captures all four other former RU ASN origins. All five remain OPEN; no automatic exclusion, static pin or release decision follows from the snapshot observation alone.
- Attempted direct RIPEstat RPKI, RIPE database and Cloudflare RPKI API lookups on 2026-11-16; these endpoints were inaccessible in this research environment. RPKI status remains UNKNOWN for each prefix/origin, not invalid or absent. Obtain time-stamped primary routing/RPKI and operator evidence when possible; do not interpret cached third-party listings as a current ROA result.
- All four workflows passed on documentation head `0b41ac55e1e4cb1106359998c0c6579ea38b3408`. This checkpoint records investigation only and leaves PR #52 draft and production unchanged.

## 2026-11-16 — user-directed retention of five trusted-source prefixes

- User instructed that these prefixes should not be dropped when present in Hydra, Loyalsoldier or v2fly. Checked exact retained candidate inputs: none overlaps Hydra DIRECT/WHITELIST or Loyalsoldier RU/BY; v2fly contains the full five /24s, three in US and two in DE. These category labels are upstream observations, not proof of regional geography or current origin. The instruction is applied to the five explicitly discussed ranges only; US/DE categories are not admitted wholesale.
- Added a bounded user-approved prefix file, with SHA-256 in the v41 manifest and provenance/audit layer. Prefixes are admitted explicitly and protected from resolver-only exclusions; PRIVATE, reviewed admission exclusions, confirmed hard blocks and Telegram retain priority. The entries do not claim present origin ASN or ownership. Release/overlay validation and diagnostic reconstruction include the trusted layer.
- On the previously retained build inputs, the rebuilt DAT SHA-256 is `937126f01f6790e9662d1913263e45550d4d2a117aeea00245200553e170b392`. Exact set comparison to candidate `3161fdd5eda4d9c2f962a3c8d1bd0c187e5cab9260284a13679b289a9a6d0855`: IPv4 +1,280 / -0, IPv6 +0 / -0; PRIVATE unchanged. All five were absent from the previous candidate, and none intersects the retained exact-block or Telegram inputs. This is a local candidate on pinned inputs, not a published release and not a claim about a future rolling build.
- Full local Python suite passed 306 tests including a test for exact five ranges, DNS-only protection and hard/Telegram precedence. Next: execute all GitHub CI on this change, independently verify DAT/SRS and compare against the current published release and the exact build's inputs; keep PR draft pending CI and CDN review. User instruction supersedes the earlier tentative decision to leave these five ranges absent. The earlier route/RPKI uncertainty remains recorded and is not resolved by this inclusion.

## 2026-11-16 — user requires reachability verification before retention

- User clarified that the five prefixes found only in v2fly US/DE need accessibility testing from Russia. The preceding static retention was premature; revert its code, data and validator changes while preserving this journal history. AS219306 remains in the corporate policy and watchlist; the five /24 decisions remain OPEN, not approved or rejected based on geographic labels alone. No production release was published.
- Before deciding, test representative actual responsive service endpoints from verified independent Russian residential/provider egresses, with timestamp, measured public exit IP/ASN, endpoint IP/port, protocol, and per-attempt result. Record timeouts, refusals, lack of a service, HTTP responses and vantage failure separately. A failed connection or absence of a server does not prove an entire /24 is blocked; a successful connection does not establish Russian ownership, geographic location or whether DIRECT is desirable. Compare a reference vantage point where available. Do not mass-scan 1,280 hosts or treat network/broadcast addresses as services; select defensible endpoints or known domains and respect existing project constraints including no changes to PR #5.
- Current execution environment has no OpenVPN or WireGuard executable, no /dev/net/tun, and no effective network administration capability; no verified Russian egress is available. vpnobratno.info publishes Russian VPN profiles, but a listing is not proof of an active connection, residential ASN, or successful measurement. No reachability test was performed and all five statuses remain UNKNOWN. Resume when an isolated verified Russian measurement vantage and relevant targets are available.
- Previous commit `3c844c356980c1a52ddee3a83913260504d0ea84` CI passed; its candidate included the five static /24s, but it is superseded by this correction and must not be used as the publication candidate. Rerun exact-head checks after the revert.

## 2026-11-16 — reuse established VPNObratno method

- User correctly pointed to `feature/reachability-full-ru-kz-by`. Its worklog records [live Run #24 / 43093976146](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43093976146): one verified RU exit on AS6856 and 25 HTTP responses, with 28/30 targets tested. The runner's two-source exit-country check and isolated namespace were exercised. Residential household access remains unverified; the earlier statement that there was no demonstrated usable method was incorrect. Run #24 did not test the present five ranges.
- The current feature workflow accepts a fixed domain target file and is manual-only; the GitHub UI currently reports its workflow path unavailable on the default branch. This local environment cannot create a VPN namespace; the GitHub connector does not expose workflow dispatch. A separate, disposable diagnostic branch derived from the feature branch is being prepared to run only bounded IPv4 TCP/443 samples (.1 and .2) for each of the five /24s plus an HTTPS control. It uses the existing VPN exit verification, firewall and namespace wrapper, does not alter PR #5 or the feature branch, and keeps all results advisory. Successful TCP confirms only that endpoint/port at that moment; refusal or timeout is inconclusive for the subnet or censorship. The sample IPs are not established service endpoints and do not establish ownership. No results yet.

## 2026-11-16 — bounded five-prefix VPN diagnostic started

- Created a separate `diagnostics/five-prefix-vpn-20261116` branch from reachability feature commit `30e797f05ddb8e38ccc2c44938b64846b4fce2fb`; PR #5 and its branch are unchanged. Diagnostic commit `83db6362a5acb7d4d62ad31d776517e0a4a5c432` reuses the namespace, VPNObratno discovery and independent RU exit verification; it limits destination probes to TCP port 443 on .1 and .2 in each of the five /24s plus `example.com` HTTPS control. These sample addresses are not independently known services. TCP connected/refused/timeout are observations of an address and port only, not a verdict for its subnet or censorship. Exit household nature remains unverified.
- Locally 143 reachability tests passed with proxy environment variables removed for the hermetic direct-home-probe fixtures; targeted tests cover bounded IP allowlist and success/timeout classification, and target file validates with 11 entries. No local VPN was attempted.
- Push-triggered isolated [diagnostic run 43818392218](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43818392218) started at this exact commit. At this checkpoint it is in progress: no exit, service response, or other result is yet claimed. Do not change routing or treat green CI without a verified RU exit and complete report as proof of reachability. Download and verify artifacts, exit IP/country/ASN, control, rows and errors after completion.

## 2026-11-16 11:41–11:42 UTC+05 — first bounded RU VPN samples

- [Diagnostic run 43818392218](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43818392218) checked out `83db6362a5acb7d4d62ad31d776517e0a4a5c432`, completed successfully and uploaded [artifact 14203711322](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43818392218/artifacts/14203711322). Downloaded ZIP SHA-256 `3c376333a529ec16434acdc696c4d293c556c43faf61fb4f183f0c16bd3e4f18` matches GitHub Actions. Summary records one verified RU exit, AS15774, provider label TTK-DV/Khabarovsk dynamic pool; volunteer household access is not independently verified. Two-source exit verification succeeded, target scan COMPLETE 11/11, HTTPS control `example.com` returned 200. Namespace cleanup logged `host_firewall_restored=true`, `cleanup_failed=0`.
- At 06:42:01–06:42:28 UTC, TCP/443 connections to `.1` and `.2` in each of `177.29.253.0/24`, `177.122.229.0/24`, `177.122.241.0/24`, `177.166.74.0/24`, and `177.166.78.0/24` each timed out after three seconds. These are ten sampled addresses, not known responsive HTTPS servers. All results remain INCONCLUSIVE; timeouts do not establish subnet inaccessibility, RKN blocking, or absence of service. 11/11 scan completion means all targets produced records, not that ten sampled ports were reachable.
- Next run will compare these exact samples from the GitHub runner's ordinary egress before invoking the isolated RU VPN; this reference is not assumed to be outside Russia until independently verified. Continue to seek known live IP/domain targets and independent provider exits. No routing or release changes; PR #5 and its source branch remain untouched.

## 2026-11-16 — runner-reference comparison started

- Diagnostic commit `22db58622670a96c05de977122f8e8bdc024f814` on the separate branch adds an ordinary GitHub runner-egress TCP/443 comparison for the same ten samples before entering the isolated verified-RU VPN. Its location and provider remain unverified; it is a connectivity reference, not proof of a non-Russian vantage. Reference rows are included in the diagnostic artifact under `vpn_gate_runner_reference.jsonl`. Neither sample failure nor success establishes reachability of an entire /24 or traffic filtering.
- Locally 144 hermetic reachability tests passed, including timeout/refusal classification. [Diagnostic run 43818799995](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43818799995) is in progress at the recorded commit; no results are yet claimed. The earlier successful RU VPN run with ten inconclusive timeouts remains independently preserved.

## 2026-11-16 11:44–11:46 UTC+05 — runner versus RU VPN

- [Run 43818799995](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43818799995) succeeded at `22db58622670a96c05de977122f8e8bdc024f814`; [artifact 14203423598](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43818799995/artifacts/14203423598) was downloaded and SHA-256 `75c107313b8f44c90ff20414b3e77daac9929d227dfa20aace767875aedfcb07` matches Actions. It records one RU VPN exit AS15774, 11/11 target rows and HTTP 200 control, with no report write errors. The same public VPN exit was used in the two diagnostic runs; these are not independent ISP or exit observations.
- Ten TCP/443 samples through RU VPN timed out. At `06:44:42 UTC`, reference runner TCP connected to `177.122.229.2:443`; at `06:45:57 UTC` the RU VPN attempt timed out. The two checks were sequential, and no HTTP/TLS identity, service ownership, independent provider, RPKI status, or entire-prefix availability was established. This single asymmetry warrants repeated comparisons, not a blocking or censorship conclusion.
- Remaining nine sampled addresses timed out both from this runner reference and the RU VPN. Their sample hosts were not known responsive services, so their respective subnet status remains UNKNOWN. Runner reference geography was not verified. No automatic IP/prefix inclusion or exclusion follows.
- Next: repeat the responsive address against the runner and, if available, a second independently verified RU VPN exit/ASN, retain timestamps/metadata and compare only equivalent TCP/443 probes. Continue seeking authenticated service/domain evidence. No main, release, PR #5 or original feature branch modification.

## 2026-11-16 — focused cross-exit recheck started

- Started [diagnostic run 43819246154](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43819246154) at separate-branch commit `21f206ce1844d0e99abf99e60de40b881be6bffc`. It tests `177.122.229.2:443` twice from the normal runner and twice per verified RU exit, plus an HTTPS control, with a target of two verified RU exits and at most six VPN connection attempts. The goal is to repeat the observed single-IP asymmetry, not to classify a /24. It may return partial exit coverage or the same ASN twice; evaluate actual IP/ASN diversity and report incomplete runs honestly.
- Local hermetic suite: 144 tests passed; target schema accepted three rows. At this checkpoint the run is in progress, and no result is claimed. Source feature branch, PR #5 and production remain unchanged.

## 2026-11-16 11:48–11:49 UTC+05 — repeated check from two RU ASNs

- [Run 43819246154](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43819246154) succeeded at exact diagnostic commit `21f206ce1844d0e99abf99e60de40b881be6bffc`; downloaded [artifact 14204095213](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43819246154/artifacts/14204095213), SHA-256 `3c517be9d0d319fcda585d7b89b41bd7d113076d260e364c85ce1a3dfdc42ffa`, matches Actions. Two distinct RU exit IPs and ASNs were verified: AS15774 TTK-DV/Khabarovsk dynamic pool and AS52043 LLC Multiservice. Their volunteer or household access type is unverified. Both control HTTPS `example.com` requests returned 200; scan COMPLETE with six rows and no report errors.
- Runner reference connected to `177.122.229.2:443` twice at 06:48:37–06:48:38 UTC. Through RU AS15774, both attempts timed out at 06:49:14 and 06:49:17 UTC; through RU AS52043, both timed out at 06:49:34 and 06:49:37 UTC. These are sequential comparisons of one IP and TCP port 443, each VPN attempt bounded to three seconds; not an HTTP response, service identification, proven RKN block, confirmed geolocation, or whole-/24 reachability result. Runner country remains unverified. DNS/routing/target-side or provider-side filtering and transient effects remain possible.
- Combined with earlier all-five sampling, this is a repeatable asymmetry for one endpoint at the measured time and two RU ASNs; the other nine sampled IPs remain inconclusive because neither the RU VPN nor reference connected. Do not infer that `177.29.253.0/24` or any entire range is inaccessible, or change DIRECT categorically. Seek representative known services and broader targeted checks before a decision. PR #5, feature branch, main and release remain unchanged.

## 2026-11-16 — reference metadata and service characterization

- Searches for known active services in the five /24s yielded no sufficiently attributable target. The only previously observed responsive endpoint was `177.122.229.2:443` from the GitHub runner; its identity and location remain unknown.
- Started [diagnostic run 43820309250](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43820309250) at separate-branch commit `b293cdf9061fb619c8788050fb699967af4de9e0`. The runner reference now uses the existing two-source metadata consensus to identify country and ASN (without saving the runner IP); failures remain UNKNOWN. A single bounded TLS handshake and GET against the observed endpoint use an explicitly unverified certificate and no credentials; certificate fingerprint/protocol/status are diagnostic hints, not authenticated service identity or a trust decision. Two Russian VPN exits are requested; their access type still needs independent verification.
- Local hermetic suite: 145 tests passed. Run is in progress; no result yet. This does not add or remove IPs, alter PR #5 or modify production.
