# Аудит репозитория Geoip-ru-server — журнал 2026-11-11

## Назначение

Append-only журнал полного обзора и перехода к улучшению исходных IP-данных. Каждая новая запись должна содержать дату UTC, baseline/commit, выполненные проверки, URL и hashes важных артефактов, ограничения и следующий шаг. Старые записи не переписывать.

## Точка аудита

- Репозиторий: SpeedeMiner/Geoip-ru-server.
- Default branch: main.
- Проверенный head: d6fa94a691a9635b72be4e6b941c87d29c802dfa.
- Recursive tree main: 21 tracked files; tree response не truncated.
- Production tag: https://github.com/SpeedeMiner/Geoip-ru-server/releases/tag/latest-geoip-client-v37.
- Production run #34: https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/42969783654, success на том же head.
- Release branch commit после run #34: d613c5f0ef482f2051cbc37a303b2ac30076d313.
- geoip_RU.dat: 951 531 bytes; SHA-256 c70310071f7611d5c7ae54d409ae7c8d7b4598bbbbb706cbb44e9f0ca9303904.

## Проверенные компоненты

### Production build
- .github/workflows/blank.yml — около 3 500 строк: schedule/dispatch/push, source downloads/provenance, RIR/IANA/IPVerse parsing, GeoIP protobuf processing, Go trie builder, tests, validators, quality report, GitHub Release и release branch publish.
- В workflow загружаются Hydra, Grimbird, Digne, Davoyan, Kirill, Golukon, v2fly, Loyalsoldier RU/BY/private, HXEHEX, W1ZARDZ; пять RIR delegated files; IANA v4/v6; ipverse; Antifilter/RunetFreedom/Re-filter.
- Go builder embedded в workflow (примерно строки 1237–2753 baseline): CIDR trie, GeoIP parsing, role mapping, PRIVATE/blocked precedence, two-group corroboration, address counts, global BGP reachability, provenance/quality и protobuf output.
- Go tests также встроены heredoc в workflow: parent/child route coverage, IPv6 partial coverage, source categories, blocked carve safety, precedence, correlation, new-address accounting, exact-prefix parser.
- Immutable action commit pins и точные версии Go/protobuf dependencies используются; upstream data refs всё ещё включают floating main/master/release/latest.
- На push в main, расписанию и workflow_dispatch запускается production publish с contents:write; release branch обновляется force-push. Merge даже документационного PR в main запускает production build.

### Python scripts and tests
Проверены исходники/тесты:
- prepare_blocked_sources.py / test_prepare_blocked_sources.py.
- build_company_prefix_review.py / test_build_company_prefix_review.py.
- build_selected_origin_prefix_review.py / test_build_selected_origin_prefix_review.py.
- build_priority_prefix_evidence.py / test_build_priority_prefix_evidence.py.
- build_priority_prefix_triage.py / test_build_priority_prefix_triage.py.
- build_priority_prefix_worklist.py / test_build_priority_prefix_worklist.py.
- build_priority_rpki_reconciliation.py / test_build_priority_prefix_rpki_reconciliation.py.
- prefix-audit-validation.yml.

Обнаружено:
- Audit scripts review-only, строки остаются STATUS=REVIEW.
- RDAP first/middle/last samples не описывают все suballocations внутри большого prefix.
- RPKI проверяется по exact prefix/origin pairs; API errors явные. Но независимые per-pair queries не являются единым VRP snapshot, synchronized с RIB.
- IRR scope — RIPE + GRS sources, доступные через RIPE metadata; отсутствие exact object не равно global IRR absence.
- Текущий priority queue — 56 prefixes (52 MOAS + 4 company-only), external spot checks — 22, archived-invalid RPKI reconciliation — 19 rows. Это не полный inventory всех российских IP-диапазонов.
- Reconciliation и worklist проверяют NLRI scope; more-specific-only evidence не может стать exact-origin verdict для parent.

### Data and release artifacts
Проверены release files: geoip_RU.dat и SHA sidecar; quality report; source manifest/counts; category audit; additional provenance; company ASN list/manifest; selected ASN prefix list/stats; RU RIR prefixes/stats; RU/BY/KZ ASN registries; global BGP prefix set; blocked exclusions/review candidates/checksums; input provenance.

Input provenance хранит URL/hash/bytes/status, но не все raw inputs: GeoIP .dat files, ipverse archive, RIR delegated files и IANA CSV не сохраняются вместе с release. Это ограничивает воспроизводимость конкретного исторического запуска.

### Existing audit data
- company_asn_legal_evidence_v37.tsv: 41 ASN entries; отмечены downstream/customer route risks у крупных access/transit ASN (в частности AS3216 и AS8359), а также mixed holder/affiliate cases AS211517 и AS212066.
- company_asn_legal_evidence_v37_additions.tsv: дополнительные legal-evidence entries.
- priority_prefix_external_spot_checks_v37.tsv: 22 rows с CHECKED_2026-11-10.
- priority_prefix_rpki_invalid_assessment_v37.tsv: 19 ручных assessments, review-only.
- PROJECT_CHECKPOINTS.md: append-only checkpoint journal прошлых audit stages.

## Зафиксированные метрики v37

- RU category: 76 292 CIDR, IPv4 52 618 729 addresses, IPv6 1 192 441 882 017 908 537 250 295 700 258 816 addresses.
- RIR: 5 774 RU ASNs, 385 BY/KZ ASNs, 13 679 RU-registered resource CIDRs.
- Company allowlist 41 ASN; 38 observed in ipverse; 5 336 selected ASNs with ipverse prefixes.
- Selected RU/BY/KZ/company origin layer: 23 564 unique prefixes.
- Global ipverse aggregate: 520 065 prefixes.
- 14 456 output CIDRs not observed in 90-day ipverse; this is NOT_OBSERVED, not unroutable.
- Additional feeds union 39 642 CIDR; 25 180 with 2+ logical groups; after trusted deduplication net new contribution 190 CIDR.
- Blocked destinations: 193 285 approved unique entries; 28 555 review-only rows.

## Итоги аудита

1. Нынешняя RU category — legacy DIRECT RU+BY+KZ+company/affiliate, а не strict geographic RU.
2. RU ASN registration и BGP origin не доказывают, что каждый originated prefix принадлежит оператору или находится в России. Нужна prefix-level holder/control review.
3. Company affiliate exceptions должны быть отдельным слоем от географического RU.
4. 90-day ipverse aggregate не заменяет current full RIB и synchronized VRP.
5. Нет единого canonical prefix ledger с explainable ADD/EXCLUDE/REVIEW и diff.
6. Provenance имеет hashes/size, но не immutable upstream refs и неполный raw snapshot retention.
7. Correlation проверен для Grimbird+Digne, но не для всех feeds.
8. Monolithic workflow затрудняет независимый review source data / policy / builder.

## Ограничения выполнения

- Не менялись production prefix inputs, builder, company ASN allowlist, release assets и geoip_RU.dat.
- Не делались выводы о geolocation/ownership только по ASN country, RIR, IRR, RPKI или BGP origin.
- Не переносились origin/ROA между parent и child NLRI.
- PR #6 остаётся независимым Draft.
- PR #5 и feature branch feature/reachability-full-ru-kz-by не изменялись; отдельные CI/измерения для PR #5 не запускались.

## Следующий шаг

План: docs/GEOIP_RU_SOURCE_IMPROVEMENT_PLAN.md.
Resume: .github/audits/GEOIP_RU_AUDIT_RESUME.md.
Следующий технический этап: versioned source catalog + immutable raw snapshot bundle; далее canonical exact-prefix inventory и полный diff против v37. Только после этого — data PR с доказанными ADD/EXCLUDE.


## Новое наблюдение после CI PR #7 — 2026-11-11

### Validation run #148

- PR: [#7](https://github.com/SpeedeMiner/Geoip-ru-server/pull/7), Draft.
- Workflow run: [#148 / 42975245329](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/42975245329).
- Head: \`c49c8474ca0a35fb436c2a10cb81d897456e9e83\`.
- Итог: failure в шаге **Collect RDAP resource-holder samples and per-origin RPKI status for priority prefixes**.
- Важно: это **не сетевой/API failure**. Шаг завершился до RDAP/RPKI запросов из-за локальной проверки ожидаемой численности.

### Что успешно прошло перед блокировкой

1. Compile audit scripts — success.
2. Все audit unit tests — success.
3. Validate v37 legal-evidence additions TSV — success.
4. Validate consolidated v37 legal-evidence TSV — success.
5. Fetch immutable v37 production inputs — success; release snapshot commit \`d613c5f0ef482f2051cbc37a303b2ac30076d313\`.
6. Generate company-origin and full selected-origin review queues — success.
7. Validate generated queues against v37 quality report — success.

В логах этой сборки зафиксировано:

- ipverse URL: \`https://codeload.github.com/ipverse/as-ip-blocks/tar.gz/refs/heads/master\`;
- archive SHA-256: \`fadde6a3997e55556c94509032b675dde06684f131e596b88c2910ab907b0f79\`;
- archive bytes: 16,268,123;
- company-origin review prefixes: 3,169;
- full selected-origin review prefixes: 23,564;
- company-origin prefixes in selected queue: 3,169;
- all generated queue rows remain \`STATUS=REVIEW\`.

### Точный блокер

\`.github/scripts/build_priority_prefix_evidence.py\` всё ещё требует:

- всего 56 priority prefixes;
- 52 exact MOAS;
- 4 company-only.

Но текущий snapshot дал 53 MOAS; при 4 company-only скрипт сообщил:

\`ERROR: expected 56 company MOAS/company-only priority prefixes, got 57\`.

Ошибка возникает до записи \`priority_prefixes.tsv\` и до любых live RDAP/RPKI запросов. Остальные последующие шаги CI были skipped. Поэтому artifact текущего run #148 не создан, а exact CIDR нового/изменившегося MOAS в этом проходе ещё не установлен.

### Интерпретация и необходимые действия

- Это рассинхронизация hard-coded scope в audit workflow/скриптах с более новым production IPVerse snapshot. Это не доказательство того, что новый prefix географически российский, не подтверждение владельца и не основание менять production output.
- Не менять ожидаемые counts просто с 56 на 57, пока не получен exact CIDR и не проверены origin-set, source snapshot и точная причина изменения MOAS.
- Следующий шаг: воспроизвести priority selection на том же архиве и pinned release inputs, найти точный prefix, сравнить его с предыдущим 56-row audit inventory; затем обновить expected scope/tests только после review конкретной строки.
- До этого priority evidence stage остаётся заблокирован; все новые/неясные строки REVIEW.
- PR #7 остаётся Draft. PR #5 / feature branch не затрагивались. Production builder, prefix inputs, allowlists, release и \`geoip_RU.dat\` не менялись.



## 2026-11-11 — Scope drift resolved and new exact-MOAS candidate reviewed (run #159)

### CI cause and correction

The audit priority selection is defined by source data, not by an approved historical number:
- select every exact prefix with `GLOBAL_BGP_MOAS=yes`;
- select every `INCLUSION_BASIS=COMPANY_ASN_ONLY`;
- keep all selected records in `STATUS=REVIEW`.

The old audit scripts/workflow embedded the historical count `56 = 52 MOAS + 4 company-only` in the evidence collector, triage, worklist and workflow validators. The current pinned v37 input snapshot generated `53 MOAS + 4 company-only = 57`. This was a stale validator assumption, not a production build failure or an external API issue.

PR #7 now derives the expected inventory from the exact company review queue, validates set equality and dynamic origin-pair coverage, and passes that validated inventory through RDAP/RPKI/IRR, triage and worklist. The existing curated external spot-check list stays a separately controlled subset. Tests cover a 53+4 selection and dynamic date handling. No automatic approval or production decision was added.

### Run #159

- PR #7: https://github.com/SpeedeMiner/Geoip-ru-server/pull/7.
- Validation run: https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/42978866087 — **18/18 success** on head `6c0fb4ef2b4f67c8c621365931f289ebf4aefb47`.
- Artifact: `v37-prefix-audit-7`, ID `13836209176`, 645,109 bytes; SHA-256 `2052fbe9284356b7202c2eb2fb55a9bfdb6fcda1f94fe83780b3312ed4801f96`.
- Source queue: 3,169 company-origin rows, 23,564 full selected-origin rows; all REVIEW.
- Priority inventory: 57 exact prefixes, 53 MOAS + 4 company-only.
- RDAP: 171/171 samples successful; RPKI: 111 exact prefix/origin queries (66 valid, 20 invalid_asn, 25 unknown); IRR query statuses 55 OK, one NO_EXACT_ROUTE_OBJECT_IN_QUERY_RESULTS, one NO_OBJECTS_IN_QUERIED_SOURCES.
- All 57 priority, holder, triage and worklist rows remain REVIEW. Worklist contains 57 entries. Archived-invalid reconciliation remains 19 entries, all REVIEW, with current classes 16 EXACT_ORIGIN_SET_CHANGED, 1 EXACT_MOAS_RPKI_STATUS_CHANGED, 1 MORE_SPECIFIC_ONLY_NO_EXACT_VERDICT and 1 EXACT_MOAS_INVALID_ORIGIN_REMAINS_UNCONFIRMED.
- The existing 22 dated external spot checks were preserved. The new prefix was not silently marked checked by the generated priority collector.

### Exact prefix identified: 5.255.192.0/18

The additional priority row is `5.255.192.0/18`:
- ipverse selection marks exact MOAS origins AS13238 and AS208398; AS13238 is the company/selected ASN that placed this exact prefix in the company-origin review queue. Input snapshot SHA-256: `fadde6a3997e55556c94509032b675dde06684f131e596b88c2910ab907b0f79` (16,268,123 bytes; the upstream URL in the v37 release provenance is a floating `refs/heads/master` codeload URL).
- Run #159 RIPE RDAP first/middle/last samples: 3/3 HTTP 200; three distinct child resource objects `5.255.192.0/25`, `5.255.223.248/29`, `5.255.255.0/24`, all country RU and Yandex registrant/maintainer data. This is not an exhaustive holder map for all /18 addresses.
- Run #159 RPKI validation: AS13238 valid and AS208398 valid for the exact /18; both queries HTTP 200 / OK.
- Run #159 RIPE + seven GRS route-object search: one logical exact route object for AS13238/YANDEX-MNT; no exact AS208398 route object in those queried sources. The object was created and last modified 2012-10-31.
- External spot-check on 2026-11-11: IPCTL exact-prefix page reports both origins with last-seen 2026-11-11 and two valid ROAs; Cloudflare Radar identifies AS208398 as TELETECH / Edge Technology Plus d.o.o. Beograd, Serbia; RIPE allocation/WHOIS summaries identify `RU-YANDEX-20120914`, ALLOCATED PA, ORG-YA1 / YANDEX LLC, country RU; WorldIP RIPE RIS-derived pages list this MOAS on 2026-11-06. These are independent asynchronous public references, not a single synchronized full RIB.
- Each exact /18 ROA advertises maxLength /24. RPKI validity is origin authorization, not address-resource ownership or geography. A Serbian ASN origin therefore does not make the RIPE-allocated Yandex /18 a foreign resource.
- The exact /18 route-object mismatch is review-worthy, but the absence of AS208398 in the queried RIPE/GRS object results does not establish global IRR absence or an invalid route. No proof of hijack, route leak, transfer or customer relationship has been established.
- Worklist action: `IRR_BGP_ORIGIN_RECONCILIATION`; external spot-check relation `EXACT_AND_MORE_SPECIFIC`; all status remains REVIEW.

### Files and changes in this stage

- Updated `.github/audits/priority_prefix_external_spot_checks_v37.tsv` from 22 to 23 entries by adding `5.255.192.0/18`, date `CHECKED_2026-11-11`, exact + more-specific scope.
- Updated `.github/scripts/build_priority_prefix_worklist.py` to accept a real ISO `CHECKED_YYYY-MM-DD` date instead of a single hard-coded day. Invalid calendar dates are rejected.
- Added unit tests for a later-date spot check and invalid date.
- Updated `.github/workflows/prefix-audit-validation.yml` to expect the 23 curated prefixes, enforce their per-row check dates and exact scope relations, and validate 17 EXACT_AND_MORE_SPECIFIC / 5 EXACT_ONLY / 1 MORE_SPECIFIC_ONLY.
- Updated the improvement plan with a documented example of the cross-border MOAS/holder distinction.
- No production prefix input, company allowlist, Go builder, DIRECT policy, `geoip_RU.dat`, release tag or release branch was changed.

### Next step

Run full PR #7 CI after the spot-check/worklist changes; inspect the new worklist row and verify all 57 remain REVIEW and all 23 external spot checks have correct dates/scope. Then update resume/checkpoint/PR body with the verified run and artifact. Continue to the wider source catalog + canonical full exact-prefix inventory only after this validation. Do not add or remove `5.255.192.0/18` from production based solely on MOAS, countryCode or RPKI.


## 2026-11-11 — External spot-check ledger expanded and fully validated (run #168)

- PR #7 validation run #168: https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/42980741689; **18/18 success** on HEAD `75ab08369ab70a4f37743912651f4e96aa0f1dc2`.
- Artifact `v37-prefix-audit-7`, ID `13836819042`, 646,543 bytes; SHA-256 `da7a57562822236851d5f715a7dffd57ec4548d7d681803a2295fb247e6d1a0c`. Downloaded and independently verified.
- Unit tests, exact dynamic selection, v37 queue reproduction, 57-prefix RDAP/RPKI/IRR evidence, triage, worklist, archived-invalid reconciliation, checkpoint and YAML all passed.
- Priority/triage/worklist: 57 rows, 53 MOAS + 4 company-only; all 57 remain REVIEW.
- Curated external spot-check ledger: 23 rows. 22 existing rows remain CHECKED_2026-11-10; 5.255.192.0/18 is CHECKED_2026-11-11. Worklist scope: 5 EXACT_ONLY, 17 EXACT_AND_MORE_SPECIFIC, 1 MORE_SPECIFIC_ONLY.
- Worklist confirms 5.255.192.0/18 as review order 4 / P2 / IRR_BGP_ORIGIN_RECONCILIATION; its external spot check is joined correctly, status REVIEW. New date validation accepts valid ISO dates and rejects invalid calendar dates.
- Archived-invalid reconciliation unchanged: 19 rows all REVIEW; classes 16 EXACT_ORIGIN_SET_CHANGED, 1 EXACT_MOAS_RPKI_STATUS_CHANGED, 1 MORE_SPECIFIC_ONLY_NO_EXACT_VERDICT, 1 EXACT_MOAS_INVALID_ORIGIN_REMAINS_UNCONFIRMED.
- The new external evidence does not change the candidate decision: 5.255.192.0/18 is a RU/Yandex resource with a cross-border MOAS (AS13238 + Serbian AS208398), both exact ROAs valid, exact RIPE/GRS route object only AS13238. Keep REVIEW; no production ADD/EXCLUDE.
- Only audit TSV, review scripts/tests, validation workflow and documentation were changed. No production prefix inputs, company allowlist, Go builder policy, geoip_RU.dat, release/tag changed; PR #5/#6 untouched.
- Resume from: update PR #7 body and checkpoint with run #168/artifact, validate the final checkpoint head via push CI, then begin source catalog + immutable snapshot bundle and full canonical exact-prefix inventory/diff. No production data action until evidence-based review.



## 2026-11-11 — Checkpoint-head validation after external spot-check integration (run #171)

- [Run #171](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/42981204736) passed all 18 steps on HEAD `b467babef15dae5d24259771f77849639fd673b5`. This run includes the updated external spot-check ledger, date parser/test, 23-row exact-scope/date gate, plan, journal and checkpoint.
- Artifact `v37-prefix-audit-7`, ID `13837906300`, 646,551 bytes; SHA-256 `9c5aa104d10c7b004b91f23183134a43bf21a1441d5f0371283d59e576796a4a`; downloaded and verified.
- Priority/evidence output: 57 prefixes (53 exact MOAS + 4 company-only); priority, triage and worklist all 57 REVIEW.
- RDAP 171/171 OK; RPKI 111 exact pairs (66 valid, 20 invalid_asn, 25 unknown); IRR 57 queries (55 OK, one no exact object in query results, one no object in queried sources).
- External spot checks: 23 rows, 22 dated 2026-11-10 plus 5.255.192.0/18 dated 2026-11-11. Relation counts 5 exact-only / 17 exact+more-specific / 1 more-specific-only.
- Archived-invalid reconciliation: 19 rows all REVIEW; classes 16/1/1/1. No production changes.
- PR #7 body now documents the plan, scope correction, 5.255.192.0/18 evidence, run #171 and artifact. PR #7 remains Draft and unmerged.
- Resume from: current checkpoint commit needs a push-triggered full CI; after that, the next technical task is immutable source catalog/raw snapshot retention and a complete canonical exact-prefix inventory/diff vs v37. PR #5/#6 remain untouched.



## 2026-11-11 — Final checkpoint-head validation after run #174

- [Run #174](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/42981784990) passed all 18 workflow steps on HEAD `543fb9329dfb127cd6fd82dc2dba393e8cccc23e`.
- Artifact `v37-prefix-audit-7`, ID `13837562711`, size 646,557 bytes; SHA-256 `41f8ada9315b872566eb9deea810bbe10dbab13dc4f429064d56964e70b874cf`. Downloaded and independently verified.
- Artifact checks: 57 priority prefixes = 53 MOAS + 4 company-only; priority, triage and worklist all 57 REVIEW. 23 external spot checks (22 CHECKED_2026-11-10 + 5.255.192.0/18 CHECKED_2026-11-11). Scope relations: 5 EXACT_ONLY, 17 EXACT_AND_MORE_SPECIFIC, 1 MORE_SPECIFIC_ONLY. 19 archived-invalid reconciliation rows all REVIEW.
- New candidate 5.255.192.0/18 remains exact MOAS AS13238 + AS208398, with RU Yandex RIPE allocation and a Serbian origin ASN; both exact ROAs valid, exact RIPE/GRS object only AS13238. It remains REVIEW; no production change.
- PR #7 remains open Draft, mergeable true, no review threads/comments returned. PR #5 and PR #6 untouched.
- No production prefix input, company allowlist, Go builder, DIRECT policy, geoip_RU.dat, tag or release branch changed.
- Next technical stage is source catalog + immutable raw snapshot retention, followed by full canonical exact-prefix inventory and exact-address diff against v37. Do not continue adding audit-only gates in lieu of the data inventory.


## 2026-11-11 — single-snapshot correction and current v37 inventory (run #215)

### Workflow debugging history

- Run #212 failed because the workflow commit adding the ledger validator landed before the ledger file itself; the subsequent ledger commit fixed that ordering.
- Run #213 failed because the inline Python parsed a two-character literal `\\t` as the CSV delimiter. Replaced it with explicit TAB splitting.
- Run #214 passed catalog/ledger/source/provenance/fetch/queue stages and reached canonical inventory, then failed with `geoip_sha: unbound variable` after the old static SHA check was removed. Restored the downstream variable from the verified SHA.
- Run #215 is the successful validation of the combined correction.

### Run #215 immutable snapshot proof

- [Run #215](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43002597856): SUCCESS, HEAD `09cbe1db1cc4de7d50bdda59cca471532364f3fb`.
- Artifact ID `13847281344`, size 6,871,809 bytes, SHA-256 `6e5e4e31f53e46c621b85915239891c7ea1d5acb5bf6bf9c4aabc5c469645239`.
- Release commit root marker and canonical inventory stats both equal `ac2e9a4322c0b7efe293983c88cf5b304771e4c5`.
- Embedded GeoIP SHA equals current release sidecar: `7ece8f277af01ba528b55c5af54f3cbb88224f3f2a65bc0558876992f9676d13`.
- New `v37-canonical-inputs.sha256` contains all 16 fetched canonical input/sidecar digests. RU/PRIVATE exact-prefix and address-union metrics match the quality report from the same pinned release commit.

### Inventory result on the current v37 baseline

- 795,017 exact CIDRs in union inventory; 76,293 RU output CIDRs; 151 PRIVATE CIDRs; 23,564 selected-origin BGP CIDRs; 13,679 RIR RU CIDRs; 520,065 global 90-day BGP CIDRs; 193 accepted additional GeoIP CIDRs; 193,285 approved blocked exclusions; 28,291 blocked review candidates.
- RIR-to-RU-output interval coverage: 99.255239% IPv4 and 98.649940% IPv6.
- Remaining exact RIR RU residual: 360 prefixes (320 IPv4 / 40 IPv6), all REVIEW; unique residual address-space 328,940 IPv4 and `11532729195086697206485771878400` IPv6 addresses.
- Selected-origin BGP interval coverage: 99.982380% IPv4 / 100% IPv6. The 8,658 IPv4 addresses outside RU output are fully covered by PRIVATE or approved BLOCKED policy; unexplained selected-origin address-space residual is zero.
- ipverse exact-origin evidence: 123 observed / 237 not observed / 2 MOAS; exact origins of both MOAS are AS9009=RO and AS209372=US. No RU origin countryCode among observed rows; this is not proof of foreign ownership or physical location.
- Two MOAS: `92.51.48.0/21`, `193.238.192.0/22`; both stay REVIEW/NO_CHANGE in external assessment ledger.

### Existing priority-prefix evidence refreshed in the same run

- 57 priority prefixes: 53 exact MOAS + 4 company-only.
- RDAP: 171/171 sample queries OK; 34 multiple resource objects across sampled addresses; 5 one covering/unclassified object; 18 exact resource objects at all samples.
- RPKI: 111 exact prefix/origin checks: 66 valid, 20 invalid_asn, 25 unknown. Priority triage identifies 19 prefixes with invalid_asn and 12 with unknown.
- IRR: 57 exact-prefix searches across RIPE and seven RIPE GRS sources; 55 OK, one no exact route object in query results, one no objects in queried sources; 42 BGP-vs-IRR origin-set differences.
- 19 archived-invalid reconciliation rows: 18 exact-scope external observations, 1 more-specific-only; all REVIEW.
- These checks cover the 57-prefix priority sample only, not every one of 360 RIR residuals.

### Next action

- Extend exact current RIB/VRP validation to all 123 residuals with ipverse observations, synchronizing capture timestamps and preserving exact NLRI.
- Then sample/validate the 237 residuals not observed in ipverse, without treating absence as route withdrawal.
- Complete raw immutable input retention; current source catalog has 38 validated metadata rows but current v37 release explicitly does not retain raw upstream GeoIP .dat inputs.
- No production ADD/EXCLUDE yet.
