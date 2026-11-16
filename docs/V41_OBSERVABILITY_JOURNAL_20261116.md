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
