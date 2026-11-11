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


## CI blocker — run #148

- PR #7: https://github.com/SpeedeMiner/Geoip-ru-server/pull/7 (open, Draft).
- Validation: https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/42975245329 — failure at the priority-evidence collector.
- Compile, unit tests, legal-evidence checks, immutable v37 input fetch, generation of company/full selected-origin queues and their quality-report validation all passed.
- Queue counts: 3,169 company-origin prefixes and 23,564 selected-origin prefixes; all REVIEW.
- ipverse snapshot SHA-256: fadde6a3997e55556c94509032b675dde06684f131e596b88c2910ab907b0f79 (16,268,123 bytes); release input commit d613c5f0ef482f2051cbc37a303b2ac30076d313.
- Blocker: the audit script expects 56 priority prefixes (52 MOAS + 4 company-only), but the current snapshot yields 57 (53 MOAS + 4 company-only). Failure occurs before RDAP/RPKI queries; this is not an API/network failure.
- The exact additional MOAS CIDR is not yet recovered from this failed run. Do not guess it or mechanically change the count to 57. No artifact was uploaded because the workflow failed before upload.

## Resume from

Reproduce priority selection using the exact release inputs and the SHA-256-verified ipverse snapshot above. Identify the extra exact prefix, compare it with the previous 56-row audit inventory, inspect each exact origin independently, and only then update scope constants/tests and any curated evidence expectations. Keep all new rows REVIEW. No production prefix, builder, company allowlist, DIRECT output or release change. Do not touch PR #5 or its branch.

