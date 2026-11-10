# Project checkpoint log

Append-only recovery log for the Geoip-ru-server audit work. Keep each completed stage as a short, separate entry. Update the **Current state / resume from** block whenever work moves to a new stage.

## How to resume after an interruption

1. Read **Current state / resume from** first.
2. Verify the recorded branch head, PR state and latest workflow run in GitHub; do not assume a previously in-progress run is still in progress.
3. Continue from the stated next step. Do not redo completed stages unless new evidence invalidates them.
4. After each finished stage, append one compact entry with: UTC date, result, commit SHA(s), workflow run ID/URL and artifact SHA when applicable, plus the next step.
5. Keep the current-state block aligned with the latest verified state.


## Current state / resume from — 2026-11-10

- **Project:** Geoip-ru-server; production baseline is v37.
- **PR #3:** merged; merge/base commit on `main`: `c71b5eff48f34b363ef2430ba6b5c41603f36126`.
- **PR #4:** [Add current exact-origin checks for archived RPKI-invalid prefixes](https://github.com/SpeedeMiner/Geoip-ru-server/pull/4); branch `audit/prefix-review-current-p1-2026-11`; open, Draft, unmerged. Journal introduction commit: `c315b9d8b51224dd4935eba23fd60df4e36ed7d6`. The branch now contains the log and is 18 commits ahead of `main`, zero behind; verify the live branch ref before resuming.
- **Latest code validation:** [GitHub Actions run #81](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/42855998169), run ID `42855998169`, completed successfully on code head `aa2858573e7e3adc9be3a5e194f825f56569312c`; all 16 major workflow steps passed.
- **Latest artifact:** [v37-prefix-audit-4](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/42855998169/artifacts/13782199711), artifact ID `13782199711`, SHA-256 `03c44f71366c10a2f44bb03de837d64599ea231d5f6f09b764544a74fa07ce53`. The ZIP has 25 files. Reconciliation TSV SHA-256: `7b543988bf7999167dc033d870160b460efd3dfa6f5bd585ed7359c39c13b8ed`. Worklist TSV SHA-256: `dbacae414baac4649232902180854b622c9dc496f0b471f3fe0c9083bc2858ca`.
- **Verified output:** 56 worklist rows (52 MOAS, four company-only), 22 external spot-check records; NLRI scope: EXACT_ONLY=5, EXACT_AND_MORE_SPECIFIC=12, MORE_SPECIFIC_ONLY=5. Archived-invalid reconciliation: 19 unique prefixes / 20 exact prefix-origin pairs; all 19 rows remain `STATUS=REVIEW`. Classes: exact-origin set changed=12; exact MOAS with changed per-origin RPKI status=1; exact MOAS with one origin still unconfirmed=1; more-specific-only/no exact verdict=5.
- **Next step:** refresh a synchronized full RIB plus one current VRP set for unresolved exact-prefix cases. Highest-priority checks: `93.181.240.0/20` (test AS12389 and AS13118 on exact /20, and AS12389 separately on child `93.181.248.0/21`); then the five parent NLRI with only child-route observations: `37.19.32.0/20`, `77.45.128.0/17`, `94.131.190.0/23`, `95.158.192.0/18`, `213.154.160.0/19`. Do not project child-route origin/ROA state onto a covering prefix.
- **Safety boundary:** PR #4 is audit-only. Do not merge it, mark it ready, change the company ASN allowlist, alter DIRECT selection, modify production `main`/`release`, or republish the mutable release without a separate explicit approval.

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
