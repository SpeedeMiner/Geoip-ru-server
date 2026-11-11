# Текущая точка возобновления — Geoip-ru-server

Обновлено: 2026-11-11 UTC.

## Сначала проверить
1. Прочитать docs/GEOIP_RU_SOURCE_IMPROVEMENT_PLAN.md.
2. Прочитать .github/audits/geoip_ru_repository_audit_2026-11.md.
3. Повторно проверить main/release/tag и актуальные workflow runs GitHub; не полагаться на прошлый статус CI.
4. Baseline: main=d6fa94a691a9635b72be4e6b941c87d29c802dfa; production run #34 success; tag latest-geoip-client-v37; release branch=d613c5f0ef482f2051cbc37a303b2ac30076d313.
5. Документационная ветка: docs/source-improvement-plan-2026-11. Production source files не менялись.

## Завершено
- Проверен tracked tree main, production workflow/Go builder/tests, release/source provenance, все audit Python scripts/tests, prefix audit workflow и audit TSV.
- Зафиксированы production metrics, текущие источники, достоинства/риски и staged plan.
- Сформулирована целевая схема: versioned source catalog, canonical exact-prefix inventory, независимые RIB+VRP, explainable prefix/address diff, separate strict RU layer.
- Созданы plan и audit journal; общий PROJECT_CHECKPOINTS должен отражать актуальный resume pointer.

## Следующий технический этап
Создать source catalog и snapshot manifest с immutable upstream commit/tag, timestamp, byte count, SHA-256; сохранить raw inputs. Затем собрать canonical exact-prefix inventory по production GeoIP feeds, RU RIR resources и независимым BGP sources. Сравнить с текущим release по exact CIDR и точному address-space diff. Production prefix list не менять до review candidate diff.

## Границы
- Не менять PR #5 и feature branch feature/reachability-full-ru-kz-by; не запускать для него CI/измерения.
- Не смешивать BY/KZ/affiliate exceptions со strict RU.
- Отсутствие маршрута в 90-day ipverse не доказывает route withdrawal.
- Не переносить BGP/RPKI status между parent и child prefix.
- Нерешённые кандидаты сохранять REVIEW.
- Любой merge в main запускает текущий production build/publish workflow, даже для docs-only PR.


## Последняя завершённая проверка — run #159

- PR #7: https://github.com/SpeedeMiner/Geoip-ru-server/pull/7 (open, Draft).
- Validation run #159: https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/42978866087 — 18/18 success, head 6c0fb4ef2b4f67c8c621365931f289ebf4aefb47.
- Artifact v37-prefix-audit-7, ID 13836209176, SHA-256 2052fbe9284356b7202c2eb2fb55a9bfdb6fcda1f94fe83780b3312ed4801f96, 645,109 bytes.
- Current priority selection: 57 exact CIDRs = 53 MOAS + 4 company-only. Dynamic expected scope is derived from the source review queue; no hard-coded 56/52/4 remains in production audit components/workflow validators.
- RDAP: 171/171 successful first/middle/last samples; RPKI: 111 exact prefix/origin queries (66 valid, 20 invalid_asn, 25 unknown); IRR: 55 OK, one NO_EXACT_ROUTE_OBJECT_IN_QUERY_RESULTS, one NO_OBJECTS_IN_QUERIED_SOURCES.
- All 57 priority, triage and worklist rows remain REVIEW. Archived-invalid reconciliation has 19 REVIEW rows (16 EXACT_ORIGIN_SET_CHANGED, 1 EXACT_MOAS_RPKI_STATUS_CHANGED, 1 MORE_SPECIFIC_ONLY_NO_EXACT_VERDICT, 1 EXACT_MOAS_INVALID_ORIGIN_REMAINS_UNCONFIRMED).
- New exact MOAS candidate: 5.255.192.0/18, origins AS13238 + AS208398. Both exact prefix/origin RPKI validations are valid. RIPE resource allocation is RU-YANDEX-20120914 / YANDEX LLC. Exact RIPE route object is AS13238 only; AS208398 has no exact object among the eight RIPE/GRS sources queried. AS208398 is a Serbian ASN. This is a cross-border origin/IRR discrepancy, not proof that the /18 is foreign. Keep REVIEW and do not change production.
- New spot-check ledger row 5.255.192.0/18 is CHECKED_2026-11-11; exact + more-specific scope. External spot-check total 23 (22 older rows + this candidate). New row remains REVIEW.
- Changed files in the current validation fix: builder/test/workflow dynamic scope from earlier commit; external spot-check TSV, worklist date validator/test, workflow 23-row spot-check gate, plan and audit journal. Production inputs/builder/release unchanged.
- Run #159 validated the earlier dynamic-scope fix. The new worklist/spot-check updates and document/journal updates still need a fresh full CI run.

## Следующий шаг

1. Проверить текущий HEAD/PR7 and latest run.
2. Full CI must pass with 57 priority rows and 23 spot-checks; check candidate worklist row remains NOT_APPROVED/REVIEW and external scope EXACT_AND_MORE_SPECIFIC.
3. Update .github/PROJECT_CHECKPOINTS.md with the new validation run and artifact; update PR body after validation.
4. Continue the main user goal: source catalog + immutable raw snapshots, then the complete canonical exact-prefix inventory and address-space diff against v37. Only after evidence review create data PRs.

