# Project checkpoint log

Append-only recovery log for the Geoip-ru-server audit work. Keep each completed stage as a short, separate entry. Update the **Current state / resume from** block whenever work moves to a new stage.

## How to resume after an interruption

1. Read **Current state / resume from** first.
2. Verify the recorded branch head, PR state and latest workflow run in GitHub; do not assume a previously in-progress run is still in progress.
3. Continue from the stated next step. Do not redo completed stages unless new evidence invalidates them.
4. After each finished stage, append one compact entry with: UTC date, result, commit SHA(s), workflow run ID/URL and artifact SHA when applicable, plus the next step.
5. Keep the current-state block aligned with the latest verified state.

## Current state / resume from — 2026-11-11 (run #217 verified)

- **Active workstream:** actual RU IP prefix source inventory and improvement. Plan: docs/GEOIP_RU_SOURCE_IMPROVEMENT_PLAN.md; audit journal: .github/audits/geoip_ru_repository_audit_2026-11.md; resume: .github/audits/GEOIP_RU_AUDIT_RESUME.md.
- **main:** 580a25a7a65d957d46d83e827ccbd9308969713e; production run #35 SUCCESS.
- **Current production v37 release snapshot:** release branch commit ac2e9a4322c0b7efe293983c88cf5b304771e4c5; tag ref latest-geoip-client-v37 observed separately at f8015a10105f55a1d86ce2dc687a92ec30d3deb9.
- **geoip_RU.dat:** 951553 bytes; SHA-256 7ece8f277af01ba528b55c5af54f3cbb88224f3f2a65bc0558876992f9676d13. RU output 76293 CIDR / 52619113 IPv4; PRIVATE 151 CIDR.
- **PR #7:** open Draft, branch docs/source-improvement-plan-2026-11; current HEAD 1af723f808e014a2284eab04a377ac0035d4f77d. Do not mark Ready or merge.
- **Latest fully green audit:** run #217 https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43005737653, 21/21 SUCCESS. Artifact ID 13848571135, 6,871,801 bytes, SHA-256 9f232cab7755381f9c6363ea8c51278f395c450a2ddeed714f6d82a89b7feae4; downloaded and verified.
- **Snapshot alignment:** run #215 proved all canonical artifacts use the same immutable release commit ac2e9a...; GeoIP SHA equals release sidecar; per-file SHA manifest retained. Run #217 revalidated the updated ledger, plan, journal and checkpoints.
- **Current canonical inventory:** 795017 unique exact CIDRs; RU output 76293; PRIVATE 151; selected-origin BGP 23564; RIR RU-registered 13679; global ipverse 90-day 520065; accepted additional feed 193.
- **RU RIR residuals:** 360 exact prefixes (320 IPv4 / 40 IPv6), all REVIEW; unexplained address union 328940 IPv4 and 11532729195086697206485771878400 IPv6.
- **Residual exact BGP:** 123 observed in ipverse archive; 237 not observed; two exact MOAS. No observed origin countryCode=RU; this is ASN metadata, not a resource ownership or geographic verdict.
- **MOAS:** 92.51.48.0/21 and 193.238.192.0/22, exact origins AS9009 + AS209372. Public BGP pages still show both; registration/IRR evidence is mixed; synchronized direct VRP verdict for both exact prefix/origin pairs remains pending. Both REVIEW/NO_CHANGE.
- **Production delta from previous v37:** +1 net exact CIDR; +384 IPv4 addresses; +one IPv6 /48. New exact output 147.45.36.0/23, 192.144.38.0/24, 2001:678:13e0::/48; removed exact output 147.45.36.0/24 and 147.45.37.128/25. This came from production run #35, not PR #7.
- **Build impact:** audit catalog/snapshot/inventory/RIB/VRP/holder/IRR checks do not modify output. Only a separately approved exact-prefix source/policy change connected to builder can change geoip_RU.dat. Merge to main may trigger current production workflow; mutable feeds can update output.
- **Production semantics:** legacy DIRECT bucket remains RU+BY+KZ plus company/affiliate exceptions; strict geographic RU must be a separate output.
- **PR #6:** separate Draft; no retarget/merge.
- **PR #5 / feature/reachability-full-ru-kz-by:** untouched; do not inspect/edit/run CI/measurements for PR #5.
- **Resume from:** independent current RouteViews + RIPE RIS exact RIB for all 123 observed residuals, same-time VRP and maxLength validation, then RDAP/IRR/holder hierarchy. Investigate 237 not observed without inferring withdrawal. Continue immutable raw source retention. No production ADD/EXCLUDE before explicit review.
- **Production caution:** merge of any PR into main triggers the existing production build/publish workflow; docs-only merge is not guaranteed to be a no-op.

## Completed stage records

### 2026-11-10 — Production baseline / PR #3 — DONE

- PR #3 merged at `c71b5eff48f34b363ef2430ba6b5c41603f36126`; production workflow [run 42847404295](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/42847404295) completed successfully.
- Release branch SHA: `099214e18590642a1ec37ae15cb5af8dce812cc9`; tag: [latest-geoip-client-v37](https://github.com/SpeedeMiner/Geoip-ru-server/releases/tag/latest-geoip-client-v37).
- Published `geoip_RU.dat`: 951,279 bytes; SHA-256 `fc9900456cb8e69059257e7193f23e6ce5eec2aaf99de6e70ff9ec8547e3fea2`.
- PR #3 was audit-only; production binary hash did not change. Release publication and seven jsDelivr purge requests completed successfully.
- Resume point after this stage: continue review-only prefix work in PR #4; do not infer permission to merge PR #4 from the PR #3 approval.

### 2026-11-10 — Priority-origin scope and external spot checks — DONE

- PR #4 branch: `audit/prefix-review-current-p1-2026-11`. The 17 commits in the branch before journal creation, oldest to newest:
  `b3f6bf3`, `d6c27f9`, `e195946`, `1fee07d`, `fa95317`, `f842700`, `718e2b3`, `595fb7e`, `8e547b6`, `cd06c01`, `33ff205`, `4c22064`, `4493c40`, `249ea5a`, `4ad8297`, `4b6655b`, `aa28585`. Full commit messages and timestamps are available in [PR #4 commit history](https://github.com/SpeedeMiner/Geoip-ru-server/pull/4/commits).
- External spot-check ledger: 22 dated rows. The analyst worklist is 56 rows: 52 MOAS and four company-only; all rows remain REVIEW.
- Final scope distribution at the current code head: EXACT_ONLY=5, EXACT_AND_MORE_SPECIFIC=12, MORE_SPECIFIC_ONLY=5.
- Earlier CI [run 42851754704](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/42851754704) passed on `1fee07de5fa6b6a52b7b3454c93ed4034e59a40b`; it predates the reconciliation builder and later `93.181.240.0/20` scope refinement, so it is not the final validation.
- Intermediate validation failures were corrected: run `42854477416` exposed a test-fixture RPKI mismatch (corrected in commit `4493c40`); run `42854592923` exposed comma-versus-pipe ASN normalization (corrected in commit `249ea5a`).

### 2026-11-10 — Persistent checkpoint log installed — DONE

- Added `.github/PROJECT_CHECKPOINTS.md` on the PR #4 branch in commit `c315b9d8b51224dd4935eba23fd60df4e36ed7d6`.
- Verified the file from GitHub and updated the PR description with the latest green CI run, artifact digests and a link to this log. The log-only change does not alter the code validated by run #81.
- Resume from the unresolved exact-NLRI refresh listed in the current-state block; append the next short record only after that stage is complete.

### 2026-11-10 — Archived-invalid exact-NLRI reconciliation — DONE

- Added deterministic reconciliation builder and tests: commits `fa95317` and `f842700`; added the 19-prefix assessment seed in `718e2b3`; subsequent validation and evidence refinements are recorded in the PR commit history.
- [CI run 42855140776](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/42855140776) passed all 16 major workflow steps on `249ea5abafff9ccbbc2de65725c67fe23f3987e0`. Its artifact SHA-256 was `73a248dd906060b38e6532943720d8fbe90f73f6845e60bc76f1ebd1f78680bd`; it is superseded by the current artifact because the `93.181.240.0/20` NLRI scope was refined afterward.
- Current [CI run 42855998169](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/42855998169) passed all 16 major steps on `aa2858573e7e3adc9be3a5e194f825f56569312c`. Current artifact and digests are recorded in the state block above.
- Final reconciliation classes: 12 `EXACT_ORIGIN_SET_CHANGED`; one `EXACT_MOAS_RPKI_STATUS_CHANGED` (`177.1.199.0/24`); one `EXACT_MOAS_INVALID_ORIGIN_REMAINS_UNCONFIRMED` (`93.181.240.0/20`); five `MORE_SPECIFIC_ONLY_NO_EXACT_VERDICT`.
- For `93.181.240.0/20`, current non-synchronous observations show AS13118 on exact /20 and AS12389 on child /21; older IPinfo evidence showed exact /20 MOAS. This cannot rule out a contemporaneous exact-prefix MOAS. Keep the AS12389 exact-origin discrepancy unresolved until synchronized full-RIB/VRP evidence exists.
- Resume point: perform synchronized refresh for the unresolved cases listed in the current-state block, then update the analyst assessment and run the full PR validation again.

---

## Append-only checkpoint template

Use one concise record per completed stage:

```text
### YYYY-MM-DD — <stage> — DONE
- Result: <what was completed; counts / validation outcome>.
- Commit(s): <short/full SHA(s)>.
- CI: <run ID + URL + conclusion>; artifact SHA-256: <digest, if any>.
- Resume from: <next concrete step>.
```


### 2026-11-10 — Refreshed exact-origin NLRI evidence — DONE

- Updated the external spot-check ledger in commit `bbfb59bb8b76ac5514d4fd1dfd8956f835a64ae8` using current prefix-level BGP/RPKI views.
- Exact parent routes now independently observed: `37.19.32.0/20` AS34267, `77.45.128.0/17` AS21017, `95.158.192.0/18` AS35125 and `213.154.160.0/19` AS31133. Their AS12389/AS20632 children remain separate more-specific NLRI.
- `94.131.190.0/23` remains child-only: checked sources show `.190/24` and `.191/24` from AS215013/AS219109 with valid ROAs, but no exact /23 verdict. This is not treated as proof of global withdrawal.
- `93.181.240.0/20` remains an unresolved exact-origin discrepancy: the current AS13118 inventory shows exact /20 with valid ROA; AS12389 is shown on child /21; older IPinfo data showed an exact MOAS. Sources are not a synchronized full RIB/VRP set.

### 2026-11-10 — CI scope and reconciliation assertions refreshed — DONE

- Updated the analyst assessment seed in commit `e004cde88b5592f9f125f5d5acc84358dc0b4c8a`: four former child-only cases now have exact parent origin evidence and remain `STATUS=REVIEW`.
- Updated workflow relation/count assertions in commit `7eccd1034d63f2dc46d63ae1d5a500ee5c70d94f`: exact scope counts expected 5/16/1; reconciliation classes expected 16/1/1/1; exact-scope rows 18 and more-specific-only rows 1.
- CI has not yet been rerun on this refreshed head. Resume from the workflow validation run and artifact review, not from the earlier run #81.


### 2026-11-10 — Exact-origin refresh validated — DONE

- Updated external exact-NLRI observations in commit `bbfb59bb8b76ac5514d4fd1dfd8956f835a64ae8`, assessment seed in `e004cde88b5592f9f125f5d5acc84358dc0b4c8a`, and CI expectations in `7eccd1034d63f2dc46d63ae1d5a500ee5c70d94f`; checkpoint update commit: `cbfbb95a05bcba2aa969e294bb8e2826f837bc2c`.
- [CI run #88](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/42861407313) passed all 16 major steps on `cbfbb95a05bcba2aa969e294bb8e2826f837bc2c`.
- Artifact SHA-256: `fa807251ab1b4391d3476520a2af99f79fb22eed3d47aafc3404719e9c2e6076`; reconciliation TSV SHA-256: `5c32120202a37557e58d42efccb85564226e56185f2888c133e4247507379a29`. Counts verified: scope 5/16/1; reconciliation classes 16/1/1/1; 19 rows all REVIEW; worklist 56 rows all REVIEW.
- Resume from: run validation on this journal-updated head, update PR description, perform final checks, then mark ready and merge PR #4 under the user's conditional approval. Verify the production release and purge after merging.


### 2026-11-10 — Refreshed scope, reconciliation and checkpoint validation — DONE

- External exact-NLRI evidence update: `bbfb59bb8b76ac5514d4fd1dfd8956f835a64ae8`; assessment seed update: `e004cde88b5592f9f125f5d5acc84358dc0b4c8a`; expected-scope validator update: `7eccd1034d63f2dc46d63ae1d5a500ee5c70d94f`; checkpoint state update: `cbfbb95a05bcba2aa969e294bb8e2826f837bc2c`; journal-validation workflow update: `7d79847f2c8aedbbee7af8b9b100a73a797e6130`.
- [CI run #90](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/42862087573) passed all 17 steps on `7d79847f2c8aedbbee7af8b9b100a73a797e6130`. The workflow now validates this journal and is triggered by journal changes.
- Artifact SHA-256: `d3784c542395039838b34dd585cdb6e43aac76c07a345b6dc1c2465409d958c3`; reconciliation TSV SHA-256: `5c32120202a37557e58d42efccb85564226e56185f2888c133e4247507379a29`; worklist TSV SHA-256: `403f7c4245b51f5a3b7764da090fba7cc484324da1d7387b8f5006dadd5e3b54`.
- Output checks: scope 5/16/1; reconciliation classes 16/1/1/1; 19 reconciliation rows and 56 worklist rows, all REVIEW.
- Resume from: rerun full validation on the journal checkpoint commit, then final PR readiness checks and merge; verify production workflow/release/purge afterward.


### 2026-11-10 — PR #4 merged and v37 production publication verified — DONE

- PR #4 merged successfully at `226214fde6100818bfe8c4d214c330027a593ea3`; user-authorized merge used expected head `b0fae825dd43c6c1f0757d327eea5c87bbf5f6ce`.
- Final audit validation [run #91](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/42862618510) passed all 17 steps; 19 reconciliation rows and 56 worklist rows remained REVIEW.
- Post-merge production [run #29](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/42863173174) passed all 10 main steps and published the v37 release. Release branch SHA: `d4a5de9de898ca5c2f10f0308e04c3c0c3484c25`.
- New `geoip_RU.dat`: 950,909 bytes, SHA-256 `cbe460b3c352dcf33f055e488f15e15caccfb6487e71e0e3ea81d508cda9bad1`; all seven jsDelivr purge requests succeeded for CF and FY.
- The new build differs from prior v37 by -7 IPv4 addresses / -37 RU CIDRs; provenance identifies the changed Antifilter `ip.lst` snapshot as the changed recorded input. No production builder or company allowlist changed in PR #4.
- Resume from: future requested audit work; PR #4 and its post-merge v37 publication are complete.

### 2026-11-11 — Repository-wide source improvement plan and audit — IN PROGRESS

- Created the plan in commit 6e3e727225fc5c1c70392a8913fc97f3ccec0921: docs/GEOIP_RU_SOURCE_IMPROVEMENT_PLAN.md.
- Recorded the full repository audit in commit 731057857a7ff73dba94b77f6ba28c32a75e893e: .github/audits/geoip_ru_repository_audit_2026-11.md.
- Added the recovery note in commit f561a025c3bf504e0c6fbd8847c6519eba0cb789: .github/audits/GEOIP_RU_AUDIT_RESUME.md.
- Documentation branch: docs/source-improvement-plan-2026-11, based on main d6fa94a691a9635b72be4e6b941c87d29c802dfa. Production builder, prefix inputs, company ASN allowlist, output, tag and release were not changed.
- Audit finding to preserve: current RU category is legacy DIRECT RU+BY+KZ plus company/affiliate origins, not strict geographic RU. Next work starts with immutable source catalog/snapshots and a full exact-prefix inventory/diff.
- The checkpoint header and resume instructions are preserved; existing PR #3/#4 history remains unchanged.
- Resume from: verify the documentation-only Draft PR and read-only validation, then build the versioned source catalog and canonical prefix inventory. Do not change production data before candidate-level evidence review.



### 2026-11-11 — Priority-prefix validation scope drift — BLOCKED

- [PR #7 validation run #148](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/42975245329), head c49c8474ca0a35fb436c2a10cb81d897456e9e83, failed before external RDAP/RPKI queries.
- Compile/tests, legal TSV checks, immutable v37 input fetch, queue generation and queue-vs-quality checks passed. Generated queue counts: 3,169 company-origin and 23,564 full selected-origin rows, all REVIEW.
- ipverse snapshot SHA-256: fadde6a3997e55556c94509032b675dde06684f131e596b88c2910ab907b0f79; 16,268,123 bytes. Release snapshot commit: d613c5f0ef482f2051cbc37a303b2ac30076d313.
- Priority selector observed 53 MOAS + 4 company-only = 57, but hard-coded audit scope expects 52 + 4 = 56. The step failed with "expected 56 company MOAS/company-only priority prefixes, got 57". No RDAP/RPKI network query ran; no run artifact was uploaded.
- Exact additional MOAS prefix is not yet known from this failed run. Do not infer or mechanically update expected counts.
- Audit journal append: commit 5a5d88fcea8799656a6d14fb9a9fae503d5c3df0. Resume note append: commit 6a6237712dc38a626697df940d8e72de9e390316.
- Resume from: reproduce the priority selection from the pinned production inputs and SHA-256-verified ipverse snapshot; identify the exact extra prefix, inspect exact origin set, compare with historic 56-row scope, and only then update the audit inventory/validators. Keep REVIEW. PR #7 remains Draft; PR #5 remains untouched.



### 2026-11-11 — Dynamic priority scope, 5.255.192.0/18 review and dated external spot checks — IN VALIDATION

- CI #159 passed 18/18 after removing hard-coded 56/52/4 assumptions from priority evidence, triage, worklist and workflow validation. Actual scope is selected by exact MOAS OR company-only basis; all records remain REVIEW.
- Artifact #13836209176: 57 priority prefixes, 53 MOAS + 4 company-only; 171/171 RDAP samples OK; 111 RPKI pairs; 57 IRR queries; 19 archived-invalid rows all REVIEW.
- New MOAS candidate 5.255.192.0/18 (AS13238 + AS208398) was reviewed. RIPE allocation/three RDAP samples indicate RU/Yandex resources; both exact ROAs are valid; exact IRR object only AS13238. Treat the AS208398 origin + missing exact queried IRR object as cross-border MOAS reconciliation, not foreign resource proof. Keep REVIEW.
- Added the 23rd curated external spot-check row, CHECKED_2026-11-11; updated worklist date validation to accept real ISO dates and added unit tests. Updated workflow gates for 23 spot checks and 17 EXACT_AND_MORE_SPECIFIC scope relations.
- Updated improvement plan, audit journal and resume checkpoint. All modifications remain audit-only. Production prefix inputs, company allowlist, builder policy, DIRECT, geoip_RU.dat, release/tag are untouched.
- Resume from: full PR #7 CI on the post-spot-check branch head; verify 57 REVIEW / 23 dated spot checks / 19 REVIEW reconciliation; then update PR #7 body and proceed to immutable source catalog + canonical inventory/diff. PR #5/#6 remain untouched.



### 2026-11-11 — External spot-check 5.255.192.0/18 and run #168 — DONE / CHECKPOINT REVALIDATION PENDING

- Added the 23rd external spot-check entry for 5.255.192.0/18, dated CHECKED_2026-11-11, scope exact + more-specific. The 22 earlier checks remain unchanged and retain CHECKED_2026-11-10.
- Worklist builder now accepts any real CHECKED_YYYY-MM-DD date; unit tests cover a later-date entry and invalid calendar date. Workflow gate expects exactly the curated 23-prefix set, verifies each check date and scope relation counts 5/17/1.
- [Run #168](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/42980741689) passed 18/18 on HEAD 75ab08369ab70a4f37743912651f4e96aa0f1dc2.
- Artifact v37-prefix-audit-7, ID 13836819042, 646,543 bytes, SHA-256 da7a57562822236851d5f715a7dffd57ec4548d7d681803a2295fb247e6d1a0c; downloaded and independently verified.
- Run #168 proves: 57 priority rows (53 MOAS + 4 company-only) all REVIEW; 23 external spot-checks; 57 worklist rows; 19 archived-invalid reconciliation rows all REVIEW. New candidate 5.255.192.0/18 remains REVIEW with MOAS AS13238/AS208398, both ROAs valid, Yandex RU resource evidence, and an IRR exact-origin gap for AS208398 in RIPE/GRS sources queried.
- No production prefix input, company allowlist, Go builder, DIRECT policy, geoip_RU.dat, release tag or release branch changed. PR #5/#6 untouched.
- Resume from: validate this checkpoint commit via push-trigger CI; then update PR #7 body with the new run/artifact and continue to source catalog + canonical full inventory/diff.



### 2026-11-11 — Final current-head validation and spot-check handoff — DONE / CHECKPOINT REVALIDATION PENDING

- [Run #171](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/42981204736) passed all 18 steps on HEAD b467babef15dae5d24259771f77849639fd673b5.
- Artifact v37-prefix-audit-7, ID 13837906300, size 646,551 bytes, SHA-256 9c5aa104d10c7b004b91f23183134a43bf21a1441d5f0371283d59e576796a4a; downloaded and digest-verified.
- All 57 priority/triage/worklist rows remain REVIEW; the 23 external spot checks and exact scope checks pass; 19 archived-invalid reconciliation rows remain REVIEW.
- The additional 5.255.192.0/18 spot-check is in the worklist at CHECKED_2026-11-11 / EXACT_AND_MORE_SPECIFIC; it remains REVIEW.
- PR #7 body updated with run #171/artifact and the new candidate interpretation. Production code/data/release unchanged.
- Resume from: validate the current checkpoint commit by push-trigger CI; then continue source catalog and canonical full exact-prefix inventory/diff. PR #5/#6 remain untouched.



### 2026-11-11 — Run #174 and final source-improvement handoff — DONE / CHECKPOINT REVALIDATION PENDING

- [Run #174](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/42981784990) passed all 18 steps on HEAD 543fb9329dfb127cd6fd82dc2dba393e8cccc23e.
- Artifact v37-prefix-audit-7, ID 13837562711, 646,557 bytes, SHA-256 41f8ada9315b872566eb9deea810bbe10dbab13dc4f429064d56964e70b874cf; downloaded and independently verified.
- Artifact confirms 57 priority prefixes (53 MOAS + 4 company-only), all 57 priority/triage/worklist REVIEW; 23 dated external spot checks (22 older + 5.255.192.0/18), 19 archived-invalid reconciliation rows all REVIEW.
- 5.255.192.0/18 remains a cross-border exact MOAS (AS13238 + AS208398) with RU Yandex allocation and both exact ROAs valid; exact RIPE/GRS object only AS13238, so it remains an IRR/BGP discrepancy for review, not production exclusion.
- Run #174 confirms code and previous checkpoint. Audit journal and resume note were then updated with its evidence; this checkpoint update must be validated by the next CI.
- PR #7 remains open Draft; no review threads or comments. No production inputs/builder/allowlist/DIRECT/output/release changed. PR #5/#6 untouched.
- Resume from: validate this checkpoint commit with push-trigger CI. Then begin source catalog + immutable raw snapshot retention and complete canonical exact-prefix inventory/diff against v37; do not add/remove production prefixes before review.



### 2026-11-11 — Unified v37 snapshot, canonical inventory and RIR residual BGP evidence — DONE

- Production run #35 is SUCCESS on main `580a25a7a65d957d46d83e827ccbd9308969713e`; current release branch snapshot is `ac2e9a4322c0b7efe293983c88cf5b304771e4c5`. Tag ref `latest-geoip-client-v37` was `f8015a10105f55a1d86ce2dc687a92ec30d3deb9`; keep the tag pointer and release-branch commit separate.
- [Audit run #215](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43002597856) passed on HEAD `09cbe1db1cc4de7d50bdda59cca471532364f3fb`. Artifact ID `13847281344`, 6,871,809 bytes, SHA-256 `6e5e4e31f53e46c621b85915239891c7ea1d5acb5bf6bf9c4aabc5c469645239`.
- Snapshot alignment proof: root marker and canonical stats use the same release SHA `ac2e9a...`; embedded GeoIP SHA equals sidecar `7ece8f277af01ba528b55c5af54f3cbb88224f3f2a65bc0558876992f9676d13`; per-file SHA list is in `v37-canonical-inputs.sha256`.
- Inventory: 795,017 union exact CIDRs; 76,293 RU output CIDRs; 151 PRIVATE; 23,564 selected-origin BGP; 13,679 RIR RU; 520,065 global 90-day BGP; 193 accepted additional GeoIP; 193,285 approved blocked exclusions; 28,291 blocked review candidates.
- RIR address coverage: 99.255239% IPv4 and 98.649940% IPv6. Residual: 360 exact CIDRs (320 IPv4 / 40 IPv6), all REVIEW; unique unexplained address space 328,940 IPv4 and `11532729195086697206485771878400` IPv6.
- Selected-origin BGP interval coverage: 99.982380% IPv4 / 100% IPv6; the 8,658 IPv4 addresses outside RU output are covered by PRIVATE or approved BLOCKED policy; no unexplained selected-origin address residual.
- Exact ipverse evidence for residual set: 123 observed / 237 not observed / 2 exact MOAS; no observed origin countryCode=RU. MOAS: `92.51.48.0/21` and `193.238.192.0/22`, both AS9009=RO + AS209372=US; external ledger keeps REVIEW/NO_CHANGE.
- Priority scope in the same run: 57 prefixes (53 MOAS + 4 company-only); RDAP 171/171 OK; RPKI 111 pairs (66 valid / 20 invalid_asn / 25 unknown); IRR 57 queries with 55 OK, 1 no exact object in query results, 1 no object in queried sources; 19 archived-invalid rows, all REVIEW.
- Source catalog: 38 validated metadata rows. Raw upstream GeoIP .dat snapshots are still not retained; mutable source pins need work.
- No production inputs, builder, allowlist, DIRECT policy, GeoIP binary, release/tag or main changed by this audit PR. PR #7 remains Draft; PR #5/#6 untouched.
- Next: independent live RouteViews+RIPE RIS exact RIB and same-time VRPs for all 123 observed residuals; then RDAP/IRR for residuals and raw immutable source snapshots. Strict RU remains a separate scope.


### 2026-11-11 — Run #217 validates current ledger and production-impact documentation — DONE

- [Run #217](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43005737653): 21/21 SUCCESS on HEAD 1af723f808e014a2284eab04a377ac0035d4f77d.
- Artifact ID 13848571135; 6,871,801 bytes; SHA-256 9f232cab7755381f9c6363ea8c51278f395c450a2ddeed714f6d82a89b7feae4.
- Updated and validated residual MOAS evidence ledger; both candidate rows remain REVIEW/NO_CHANGE.
- Verified current release snapshot and current 360-prefix residual inventory; no production changes from PR #7.
- Next: independent current RouteViews/RIPE RIS + time-aligned VRP for 123 exact-observed residuals, then holder/IRR and immutable raw-source retention.
