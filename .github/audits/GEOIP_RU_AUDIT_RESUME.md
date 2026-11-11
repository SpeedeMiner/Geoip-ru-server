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


## Последняя завершённая проверка — run #171

- PR #7: https://github.com/SpeedeMiner/Geoip-ru-server/pull/7 (open, Draft), branch docs/source-improvement-plan-2026-11.
- CI run #171: https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/42981204736 — **18/18 SUCCESS** on HEAD b467babef15dae5d24259771f77849639fd673b5.
- Artifact v37-prefix-audit-7, ID 13837906300, 646,551 bytes, SHA-256 9c5aa104d10c7b004b91f23183134a43bf21a1441d5f0371283d59e576796a4a; downloaded and independently verified.
- Priority inventory: 57 exact prefixes = 53 MOAS + 4 company-only; all 57 priority, triage and worklist rows remain REVIEW.
- RDAP 171/171 sample queries OK; RPKI 111 exact prefix/origin pairs (66 valid, 20 invalid_asn, 25 unknown); IRR 57 searches (55 OK, one no exact route object in results, one no object returned in queried sources).
- External spot-check ledger has 23 rows: 22 CHECKED_2026-11-10 plus 5.255.192.0/18 CHECKED_2026-11-11. Worklist verifies 5 EXACT_ONLY / 17 EXACT_AND_MORE_SPECIFIC / 1 MORE_SPECIFIC_ONLY.
- 5.255.192.0/18: MOAS AS13238 + AS208398; RIPE resource is RU-YANDEX-20120914 / YANDEX LLC; three RDAP samples show RU Yandex subresources; both exact ROAs valid with maxLength /24; exact RIPE/GRS route object only AS13238, while AS208398 is registered in Serbia. This is a cross-border origin / IRR mismatch, not proof the resource is foreign. Keep REVIEW, no production action.
- Archived-invalid reconciliation: 19 rows all REVIEW; classes 16/1/1/1.
- Run #171 verifies all latest spot-check/worklist/checkpoint changes. PR #7 description is updated; source changes remain review-only.

## Следующий шаг

1. Verify the new push-trigger run for the checkpoint commit recorded after run #171.
2. Confirm latest PR #7 remains open/Draft and no production files were changed.
3. Start next technical stage: versioned source catalog + immutable raw snapshots; then canonical exact-prefix inventory across every production GeoIP feed, RU RIR resource and independent BGP source, followed by full exact-CIDR and address-space diff against v37.
4. Keep ambiguous cases REVIEW; do not change production prefixes until evidence-based review. PR #5 and PR #6 remain untouched.

