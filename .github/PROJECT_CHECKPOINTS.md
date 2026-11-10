# Project checkpoint log

Append-only recovery log for the Geoip-ru-server audit work. Keep each completed stage as a short, separate entry. Update the **Current state / resume from** block whenever work moves to a new stage.

## How to resume after an interruption

1. Read **Current state / resume from** first.
2. Verify the recorded branch head, PR state and latest workflow run in GitHub; do not assume a previously in-progress run is still in progress.
3. Continue from the stated next step. Do not redo completed stages unless new evidence invalidates them.
4. After each finished stage, append one compact entry with: UTC date, result, commit SHA(s), workflow run ID/URL and artifact SHA when applicable, plus the next step.
5. Keep the current-state block aligned with the latest verified state.


## Current state / resume from — 2026-11-10

- **Project:** Geoip-ru-server; current production tag is `latest-geoip-client-v37`.
- **PR #3:** merged; baseline merge SHA `c71b5eff48f34b363ef2430ba6b5c41603f36126`.
- **PR #4:** [Add current exact-origin checks for archived RPKI-invalid prefixes](https://github.com/SpeedeMiner/Geoip-ru-server/pull/4) is CLOSED and MERGED. Merge commit: `226214fde6100818bfe8c4d214c330027a593ea3`. PR was audit-only: no production builder, company ASN allowlist or DIRECT selection changed.
- **Latest completed PR validation:** [run #91](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/42862618510), ID `42862618510`, success on head `b0fae825dd43c6c1f0757d327eea5c87bbf5f6ce`; all 17 steps passed.
- **Post-merge production build:** [v37 run #29](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/42863173174), ID `42863173174`, success on merge commit `226214fde6100818bfe8c4d214c330027a593ea3`; build, protobuf/coverage/blocked-exclusion validation, GitHub Release publish and release-branch publish all passed.
- **Published release:** [`latest-geoip-client-v37`](https://github.com/SpeedeMiner/Geoip-ru-server/releases/tag/latest-geoip-client-v37); release branch SHA `d4a5de9de898ca5c2f10f0308e04c3c0c3484c25`. `geoip_RU.dat` is 950,909 bytes; checksum sidecar SHA-256 `cbe460b3c352dcf33f055e488f15e15caccfb6487e71e0e3ea81d508cda9bad1`. New quality report: RU=76,231 CIDRs / 52,613,105 IPv4 addresses; IPv6 count unchanged; Yandex Turkey AS212066 checks remain 2/2.
- **CDN purge:** all seven requested paths reported `finished`, not throttled, with Cloudflare and Fastly both true (`CF=true`, `FY=true`).
- **Production-input drift:** compared against the prior v37 release SHA `fc9900456cb8e69059257e7193f23e6ce5eec2aaf99de6e70ff9ec8547e3fea2` (951,279 bytes), current output is 370 bytes smaller and has 7 fewer IPv4 addresses / 37 fewer RU CIDRs; IPv6 and PRIVATE counts are unchanged. Recorded production input provenance shows the Antifilter `antifilter-ip.lst` changed (old SHA `16677d55acf724c2a2c86aa34a87051d941a5cd11ac41f223a8b9b9d1a7a1878`, 51,273 rows; new SHA `d68a9d5bd5f617bb4bac0b7c0421423c80badacc162244a72ced52c5eaf39d32`, 50,763 rows). Other recorded GeoIP, RIR, IANA, ipverse and blocked-feed source hashes remained the same. Approved blocked-prefix records decreased from 193,639 to 193,242. This explains the observed output drift as refreshed live inputs rather than a change to the PR's builder logic; no rollback was performed.
- **Audit result carried into main:** worklist 56 rows, reconciliation 19 rows / 20 archived invalid pairs, all `REVIEW`; scope EXACT_ONLY=5, EXACT_AND_MORE_SPECIFIC=16, MORE_SPECIFIC_ONLY=1; reconciliation classes 16/1/1/1. Remaining caveats stay REVIEW: `94.131.190.0/23` has only observed /24 child evidence, and `93.181.240.0/20` has non-synchronized exact /20 vs child /21 observations.
- **Resume from:** there is no unfinished PR #4 or release step. For a future continuation, first verify live `main`, `release`, tag and latest workflow run, then resume the requested next audit stage. Continue appending one short record after each completed stage.
- **Safety boundary:** no audit row authorizes DIRECT changes or an ownership conclusion. The merged journal/workflow preserve review-only status and exact-NLRI scope separation.


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
