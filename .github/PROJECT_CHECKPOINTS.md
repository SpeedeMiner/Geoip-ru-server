# Project checkpoint log

Append-only recovery log for the Geoip-ru-server audit work. Keep each completed stage as a short, separate entry. Update the **Current state / resume from** block whenever work moves to a new stage.

## How to resume after an interruption

1. Read **Current state / resume from** first.
2. Verify the recorded branch head, PR state and latest workflow run in GitHub; do not assume a previously in-progress run is still in progress.
3. Continue from the stated next step. Do not redo completed stages unless new evidence invalidates them.
4. After each finished stage, append one compact entry with: UTC date, result, commit SHA(s), workflow run ID/URL and artifact SHA when applicable, plus the next step.
5. Keep the current-state block aligned with the latest verified state.


## Current state / resume from — 2026-11-11

- **Project:** Geoip-ru-server disputed-ASN / exact-NLRI audit; production tag remains `latest-geoip-client-v37`.
- **PR #3:** merged at `c71b5eff48f34b363ef2430ba6b5c41603f36126`.
- **PR #4:** merged at `226214fde6100818bfe8c4d214c330027a593ea3`; final audit CI [run #91](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/42862618510) passed 17/17. Its 19 reconciliation rows and 56 worklist rows remained REVIEW.
- **Production baseline:** main `a68e5d6589361814cb1cfedd2af7857e4af806fa`; release branch `6620d5b935d7d57744f937a5a2159e3676ca4e31`. No production builder, allowlist, DIRECT or release file is part of PR #6.
- **Current follow-up PR:** [PR #6](https://github.com/SpeedeMiner/Geoip-ru-server/pull/6), Draft, open, unmerged. Branch `audit/exact-origin-followup-2026-11`. Keep Draft; do not merge without explicit owner approval.
- **Last fully green validation:** [run #123](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/42888293912) passed 18/18 steps on `1cc08ecf71a2e349f737c6955237f178a862552e`. Artifact `v37-prefix-audit-6`, ID `13797283121`, SHA-256 `93ff61761bb56c7dc259270633fdecc274bd550a01a2f40fd8abe86a6a185035`, 759,263 bytes. ZIP digest was independently verified.
- **Run #123 live capture:** artifact contains raw `exact-nlri-live-capture.json`, 20 requests and 20 HTTP 200 JSON responses, collected 2026-11-10 19:46 UTC. Five prefixes × four sources (RouteViews exact RIB, timestamped RouteViews RPKI, RIPEstat Routing Status, RIPEstat Looking Glass 24h). No API/network errors.
- **Live result A — `93.181.240.0/20`:** RouteViews strict exact RIB reports only AS13118, 182 reporting peers, latest peer update 19:29:16Z, route-level RPKI valid. RouteViews aggregate VRP snapshot 19:00:13.437Z reports AS13118 valid. RIPEstat Routing Status exact origin is AS13118 only; the near-real-time Looking Glass shows 23 RRCs / 355 peers with origin AS13118. AS12389 is separately on child `93.181.248.0/21`, which is independently valid. The archived AS12389 invalid exact-/20 observation is now classified as `EXACT_ORIGIN_SET_CHANGED`, not a current MOAS; the archive row remains REVIEW.
- **Live result B — `94.131.190.0/23`:** RouteViews strict exact RIB has no exact entries; RIPEstat exact-origin list is empty and lists four child /24 origin records; RIPEstat 24h Looking Glass has no exact-/23 peers. RouteViews timestamped RPKI API returns null for the /23, not an RPKI invalid/not-found verdict. Both child /24s are dual-origin AS215013/AS219109 in RouteViews exact RIB and RIPEstat; RouteViews route records report both child origins valid. The aggregate RouteViews VRP response reports AS215013 valid but omits AS219109; absence from that response is not an invalid verdict. Keep exact /23 as `MORE_SPECIFIC_ONLY_NO_EXACT_VERDICT` / REVIEW.
- **Updated reconciliation target:** 19 rows, all REVIEW; classes 17 `EXACT_ORIGIN_SET_CHANGED`, 1 `EXACT_MOAS_RPKI_STATUS_CHANGED`, 1 `MORE_SPECIFIC_ONLY_NO_EXACT_VERDICT`, 0 `EXACT_MOAS_INVALID_ORIGIN_REMAINS_UNCONFIRMED`. Worklist remains 56/56 REVIEW. No policy decisions follow from these class changes.
- **Collector parser correction:** RIPEstat Looking Glass uses `data.rrcs[]` with nested `peers[]`; the initial run #123 summary parser expected a dictionary and undercounted peers as zero, although the raw JSON was retained. The parser now handles actual RRC arrays, counts RRCs/peers/origins and preserves per-peer observations. RouteViews exact RIB summary now preserves per-origin RPKI and collector evidence; RouteViews RPKI null response is distinguished explicitly. New tests cover the actual API shape and error/null semantics; validation of these refinements is pending.
- **CI source drift finding:** run #125 failed at step 7 because the workflow downloaded the mutable ipverse `refs/heads/master` archive instead of the version used to build v37. The current archive size differed from the historical provenance value by 3,013 bytes; release branch inputs themselves were fetched from pinned release commit `6620d5b935d7d57744f937a5a2159e3676ca4e31`. Workflow now pins upstream commit `2cc76341e26fbab3009196146c71648480c40e55`, which was the ipverse master commit at the v37 build time, while retaining exact SHA-256/size verification.
- **Next step:** validate the current head after live-evidence parser/tests, updated assessment/class counts and immutable ipverse archive pin. Inspect the new artifact's live capture summaries; if CI reveals a defect, fix and rerun. Keep the PR Draft.
- **Safety boundary:** do not change `geoip_RU.dat`, DIRECT, company allowlist, production `main`/`release` or PR #5. PR #5 is owned by another agent and must not be inspected, edited or otherwise touched.


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


### 2026-11-10 — Rechecked unresolved exact-NLRI evidence — DONE

- Started isolated follow-up branch `audit/exact-origin-followup-2026-11` from current main `a68e5d6589361814cb1cfedd2af7857e4af806fa`.
- External spot-check refresh committed as `af2f56737337c2d2be9949b2c13b6241ee6d0542`; assessment refresh committed as `da31493731f195c7231696a65f75393bd334c24c`.
- `94.131.190.0/23`: ASNBase and IPXO exact-prefix views do not show a /23 announcement; two /24 child routes are observed, with Piko reporting AS215013/AS219109 MOAS and valid ROAs on each child. Exact /23 remains unverified.
- `93.181.240.0/20`: BGP.HE AS13118 view shows exact /20 with valid ROA; AS12389 is separately shown on child /21 by corroborating route data; older IPinfo snapshot showed exact MOAS. Not synchronized, so archived exact AS12389 discrepancy remains unresolved.
- Both entries remain REVIEW; reconciliation class counts and production/direct policy are unchanged.
- Resume from: open a Draft follow-up PR and run prefix audit CI; then continue seeking synchronized full-feed RIB + VRPs for the two exact prefixes. Do not merge without explicit approval.


### 2026-11-10 — Follow-up exact-NLRI audit CI passed — DONE

- [PR #6 audit validation run #92](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/42871961308) passed all 17 steps on branch commit `3d7a0238d2dc2a5d42a24d71d8394ee148f9cc84`.
- Artifact `v37-prefix-audit-6`, ID `13790666311`, SHA-256 `47059459d0a251c4c2122ddf50c860cd61b1c0de706c0904acf62b0b0adc2eb8`; 25 files.
- Verified reconciliation: 19 rows, all REVIEW; class counts 16 `EXACT_ORIGIN_SET_CHANGED`, 1 `EXACT_MOAS_RPKI_STATUS_CHANGED`, 1 `EXACT_MOAS_INVALID_ORIGIN_REMAINS_UNCONFIRMED`, 1 `MORE_SPECIFIC_ONLY_NO_EXACT_VERDICT`.
- Verified analyst worklist: 56 rows, all REVIEW; 22 external spot-check records; NLRI scope EXACT_ONLY=5, EXACT_AND_MORE_SPECIFIC=16, MORE_SPECIFIC_ONLY=1.
- No production, DIRECT, company-allowlist or release files were changed.
- Resume from: run validation on the updated checkpoint head; update PR #6 metadata with the latest green run and keep Draft. Then continue exact-prefix synchronized RIB/VRP research for `93.181.240.0/20` and `94.131.190.0/23`.



### 2026-11-10 — Second current-source pass for exact-prefix follow-up — DONE

- Updated external spot-check ledger in commit `7c3bf526b72e3a89039dafd301bd25c680a93554` and assessment in commit `56608c780e07401782bb9ec322b9106c8677355a`.
- For `93.181.240.0/20`, BGP.HE exact-prefix page now explicitly lists AS13118 as the only exact /20 origin with signed valid ROA; IPIP current BGP summary shows AS13118 on exact /20 and AS12389 only on child /21. Historical IPinfo (2026-06-11) remains contrary. Keep REVIEW pending a synchronized full-feed RIB/VRP snapshot.
- For `94.131.190.0/23`, IPXO and ASNBase views show only child /24s, not the exact parent. IPXO/ASNBase list AS215013; PikoNetwork RIPE RIS-derived views show child /24 MOAS AS215013/AS219109 with both origin ROAs valid. This is a source discrepancy at child level; exact /23 remains unverified.
- Class counts and NLRI scope are unchanged; no production or DIRECT files are modified.
- RouteViews documents the appropriate next exact query: `/prefix/{prefix}?strict-match=yes` returns exact NLRI origins and collector peers; `/rpki?prefix={prefix}` returns RPKI verdicts with a snapshot timestamp. API was not reachable from this session, so no synchronized RouteViews result is claimed.
- Resume from: validate the updated branch head including this journal entry, update PR #6 description if green, and keep Draft. Do not merge without explicit owner approval.


### 2026-11-10 — Second exact-origin refresh validated — DONE

- Latest spot-check ledger commit: `7c3bf526b72e3a89039dafd301bd25c680a93554`; assessment commit: `56608c780e07401782bb9ec322b9106c8677355a`.
- [Prefix-audit CI run #96](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/42875752661) passed all 17 steps on evidence head `11436e6bd99066de488f2f3db1f7dd8686dc767c`.
- Artifact `v37-prefix-audit-6`, ID `13790798179`, SHA-256 `905e832e3194d357fa1c1ddb32171810b5a0b6efc327c42e448ee6b77d4bb83f`, 643,849 bytes; 25 files. Reconciliation 19/19 REVIEW with class counts 16/1/1/1; worklist 56/56 REVIEW; external scope 5/16/1 across 22 checks.
- Exact /20 current views: BGP.HE lists only AS13118 with valid ROA; IPIP shows AS13118 on exact /20 and AS12389 on child /21. Historical IPinfo MOAS evidence from 2026-06-11 is not contemporaneous.
- Exact /23 current child views differ on whether AS219109 is visible; no source confirms exact /23. Keep archived discrepancy unresolved.
- No production, DIRECT, company allowlist or release changes.
- Resume from: validate this journal-updated PR #6 head, update PR description with latest green CI, keep Draft. The next research task is to retrieve synchronized RouteViews exact-prefix RIB plus timestamped RPKI data; no such API response has been obtained in this session.


### 2026-11-10 — Checkpoint head validation after second exact-origin refresh — DONE

- [Prefix audit validation run #97](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/42876474662) passed all 17 steps on head `967ef194c8adba71f4a8eeb646b6beb9e882bb13`.
- Artifact `v37-prefix-audit-6`, ID `13793020367`, SHA-256 `b4414aa65f90819f4299f31a27ff6d0520c7d60b7100c36c13c683ff4f850632`, 643,842 bytes / 25 files.
- Output preserved 19/19 reconciliation REVIEW rows, 56/56 worklist REVIEW rows, classes 16/1/1/1, and scope 5/16/1.
- PR #6 description was updated with run #97 and current evidence; PR remains open and Draft, unmerged.
- No production, DIRECT, company allowlist or release files changed.
- Resume from: validate the journal-updated head, then obtain current exact NLRI and VRP data from RouteViews for `93.181.240.0/20` and `94.131.190.0/23`. Do not close either REVIEW row without synchronized source timestamps and exact-prefix scope.



### 2026-11-10 — Additional independent routing-source cross-checks — DONE

- External spot-check ledger update: `6952f1b634a630b67646ff336a74a1561b441ac8`; assessment update: `a3f62e205d0a98d4e9fde39b3775262d79faeef4`.
- `93.181.240.0/20`: BGP.tools AS13118 originated-prefix table independently lists the exact /20 with valid RPKI; its page is older than current BGPHE/IPIP route views and is corroborative only. Current evidence still supports AS13118 parent /20 and AS12389 child /21, but a synchronized global RIB/VRP result was not obtained.
- `94.131.190.0/23`: PikoNetwork's consolidated AS215013 IRR/BGP/RPKI page dated 2026-11-08 lists both child /24s with AS215013+AS219109 BGP origins and valid ROAs/route objects. IPXO/ASNBase route summaries list AS215013 on the children only. This is a source disagreement about child-level origin visibility; no source establishes exact /23.
- Both analyst classifications and statuses remain REVIEW. Production/DIRECT state is unchanged.
- RouteViews documented exact-prefix and global RPKI endpoints are the next source, but HTTP responses from those endpoints remain inaccessible in this session.
- Resume from: validate current checkpoint branch head with CI; update PR #6 body with latest green result; keep Draft. Continue seeking synchronised RouteViews/RIPE RIS exact NLRI and timestamped VRP snapshots.



### 2026-11-10 — Corroborating origin-source evidence and full audit validation — DONE

- Spot-check ledger commit `6952f1b634a630b67646ff336a74a1561b441ac8`; assessment commit `a3f62e205d0a98d4e9fde39b3775262d79faeef4`.
- Additional corroboration for `93.181.240.0/20`: BGP.tools AS13118 originated-prefix listing includes exact /20 and indicates RPKI-valid, though its indexed aggregate page is older than current BGPHE/IPIP views.
- Additional corroboration for `94.131.190.0/23`: PikoNetwork consolidated AS215013 BGP/IRR/RPKI table dated 2026-11-08 lists both child /24s as MOAS AS215013/AS219109 with valid ROAs and route objects. IPXO/ASNBase lists AS215013 only on the child /24s. No evidence establishes an exact /23 route.
- [Prefix-audit CI run #101](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/42878558622) passed all 17 steps on `4cd3c32f15988058be610a85aaffc1ba98cdc767`.
- Artifact `v37-prefix-audit-6`, ID `13793002062`, SHA-256 `39ce91924c6adedd64584fe0b95d2ee849c221f195db9182572ad3c0cace7b6f`, 643,987 bytes / 25 files. Reconciliation 19/19 REVIEW; worklist 56/56 REVIEW; classes 16/1/1/1; external scope 5/16/1 across 22 spot checks.
- Both disputed prefixes remain REVIEW. No production, DIRECT, company allowlist or release file changes.
- Resume from: validate this journal-updated head, update PR #6 with the latest green run and keep Draft. Continue the synchronized RouteViews/RIPE RIS exact NLRI plus timestamped VRP research; the API response remains a known limitation.



### 2026-11-10 — Exact-prefix source semantics rechecked — DONE

- Refreshed the `94.131.190.0/23` external-ledger note in commit `c10530658872d60d3126a102bc6d17734a596b00`.
- New clarification: ASNLookup's AS215013 overview displays `94.131.190.0/23` under a generic “Network Ranges” section, but this is registry/resource-range context, not an exact BGP RIB observation. It does not contradict the route-specific inventories showing `.190/24` and `.191/24` only.
- Current indexed AS215013 evidence (PikoNetwork, Nov 8; ASNBase refreshed recently) continues to show the two /24 children. Piko lists child MOAS AS215013/AS219109 and valid child ROAs; ASNBase lists AS215013. No source retrieved in this pass establishes exact /23 origin or RPKI state.
- `93.181.240.0/20`: current BGP.HE exact-prefix result and corroborating BGP.tools listing support AS13118 with valid ROA; AS12389 remains separately visible on child `93.181.248.0/21`. Historical IPinfo evidence from 2026-06-11 showed both ASNs on exact /20. These are not synchronized full-feed RIB/VRP snapshots.
- RouteViews documentation confirms `/prefix/{prefix}?strict-match=yes` for exact NLRI and `/rpki?prefix={prefix}` for timestamped global validation (two-hourly collection). Direct responses from both RouteViews and RIPEstat JSON endpoints were inaccessible in this research session; no synchronized result is claimed.
- Both unresolved rows remain `REVIEW`; no assessment classification, allowlist, DIRECT, production, release or `geoip_RU.dat` change. PR #6 remains Draft and must not be merged without explicit approval.
- Resume from: validate the ledger+journal checkpoint head with prefix-audit CI; if green, refresh PR #6 body with the new checkpoint and artifact while keeping Draft. Continue obtaining exact RouteViews/RIPE RIS RIB and same-window VRP responses for both prefixes.


### 2026-11-11 — Date-aware spot-check validation and reconciliation — DONE

- Corrected date validation in the analyst worklist builder, reconciliation builder, tests and workflow inline checks. Valid `CHECKED_YYYY-MM-DD` dates are accepted only when calendrically valid; the source-ledger and worklist dates must match.
- Final validation [Prefix audit run #118](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/42886592152) passed all 17 steps on `2d1a504df8974c3a33945288455b520b4310ef75`.
- Artifact `v37-prefix-audit-6`, ID `13796791673`, SHA-256 `5ef4d21686e3f6eb3721d284feb7439e7d27089abc98b41ac97ccff60db078ff`, 643,802 bytes; downloaded and independently digest-verified.
- Verified 19/19 reconciliation rows REVIEW (classes 16/1/1/1); 56/56 worklist rows REVIEW; 22 external spot checks with dated freshness; scope counts 5/16/1. No production, DIRECT, company allowlist or release files changed.
- Run #106/#109/#112/#114/#116/#117 failures were validation guard/test-fixture defects discovered and corrected; the final run #118 passed all steps. No analyst status or reconciliation class was promoted.
- Both disputed exact-prefix questions remain unresolved pending synchronized RIB + same-window VRP evidence; direct RouteViews and RIPEstat JSON requests were still inaccessible from the research session.
- Resume from: attempt the bounded live RouteViews/RIPE RIS API capture from GitHub Actions, preserve raw responses and timestamps, and keep all rows REVIEW unless exact-prefix evidence is complete and consistent.


### 2026-11-11 — Live exact-NLRI evidence captured; source and parser hardening underway — DONE/PENDING CI

- [Run #123](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/42888293912) passed 18/18 steps on `1cc08ecf71a2e349f737c6955237f178a862552e`; live-evidence artifact ID `13797283121`, SHA-256 `93ff61761bb56c7dc259270633fdecc274bd550a01a2f40fd8abe86a6a185035`.
- Artifact raw capture contains 20/20 HTTP 200 JSON results for five exact prefixes across RouteViews RIB, RouteViews VRP, RIPEstat Routing Status and RIPEstat Looking Glass. Exact /20 is AS13118 only; child /21 is AS12389. Exact /23 is not observed in either exact-RIB/routing-status result; both /24 children show AS215013/AS219109 MOAS. RouteViews per-prefix route records show child origins valid; aggregated VRP snapshot reports AS215013 only, so no status is inferred for omitted AS219109.
- Raw RIPEstat Looking Glass JSON exposed an array schema for `rrcs`; the parser was corrected to read `rrcs[].peers[]`. The RouteViews summary was also strengthened to preserve per-origin RPKI and collector IDs, and null exact-/23 VRP responses are retained distinctly. Added unit tests for these cases.
- Reclassified the archived AS12389 exact-/20 observation as `EXACT_ORIGIN_SET_CHANGED` based on RouteViews exact RIB + VRP and RIPEstat exact-routing/near-real-time peer evidence. All reconciliation and worklist statuses remain REVIEW; no DIRECT or production decision changed.
- Run #125 failed only in the v37 input-fetch step: codeload's mutable ipverse master archive had changed from the release-provenance byte count. The audit workflow now fetches the immutable ipverse commit current at v37 build time (`2cc76341e26fbab3009196146c71648480c40e55`) and verifies the release-pinned SHA-256/size.
- Resume from: run full prefix-audit CI on the current head; verify class counts 17/1/1; inspect new live capture, including RIPEstat RRC peer counts. Keep PR #6 Draft and unmerged.
