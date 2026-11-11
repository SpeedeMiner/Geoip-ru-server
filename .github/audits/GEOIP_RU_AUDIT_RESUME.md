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
