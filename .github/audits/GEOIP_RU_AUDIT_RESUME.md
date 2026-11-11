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


## Последняя завершённая проверка — run #168

- PR #7: https://github.com/SpeedeMiner/Geoip-ru-server/pull/7 (open, Draft), branch docs/source-improvement-plan-2026-11.
- CI: https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/42980741689 — 18/18 SUCCESS on HEAD 75ab08369ab70a4f37743912651f4e96aa0f1dc2.
- Artifact: v37-prefix-audit-7, ID 13836819042, 646,543 bytes, SHA-256 da7a57562822236851d5f715a7dffd57ec4548d7d681803a2295fb247e6d1a0c. Downloaded and verified.
- Priority inventory: 57 exact prefixes = 53 MOAS + 4 company-only; 57 priority, triage and worklist rows all REVIEW.
- RDAP: 171/171 samples OK. RPKI: 111 exact-prefix/origin pairs (66 valid, 20 invalid_asn, 25 unknown). IRR: 57 queries (55 OK, one no exact route object in query results, one no object in queried sources).
- Archived-invalid reconciliation: 19 rows, all REVIEW; classes 16 EXACT_ORIGIN_SET_CHANGED, 1 EXACT_MOAS_RPKI_STATUS_CHANGED, 1 MORE_SPECIFIC_ONLY_NO_EXACT_VERDICT, 1 EXACT_MOAS_INVALID_ORIGIN_REMAINS_UNCONFIRMED.
- External spot-check ledger: 23 rows total: 22 CHECKED_2026-11-10 plus 5.255.192.0/18 CHECKED_2026-11-11. Worklist validates exact scope counts: 5 EXACT_ONLY, 17 EXACT_AND_MORE_SPECIFIC, 1 MORE_SPECIFIC_ONLY.
- 5.255.192.0/18: exact MOAS AS13238 + AS208398. RIPE resource allocation is RU-YANDEX-20120914/YANDEX LLC; three RDAP samples are all RU/Yandex child resources, but are not exhaustive. Both exact RPKI pairs valid (maxLength /24); exact RIPE/GRS route object found for AS13238 only; AS208398 registered in Serbia. This is a cross-border route/IRR discrepancy, not proof the IP resource is foreign. Worklist status REVIEW; no production action.
- Audit changes are limited to review scripts/tests/workflow/TSV/docs. Production builder, prefix inputs, company allowlist, DIRECT, geoip_RU.dat, tags/releases unchanged. PR #5 and PR #6 untouched.

## Следующий шаг

1. Update PR #7 body and .github/PROJECT_CHECKPOINTS.md with run #168 and artifact.
2. Validate the checkpoint-updated HEAD with push-trigger CI; make sure it completes 18/18.
3. Next substantive data task: create versioned source catalog + immutable raw snapshot bundle, then a canonical exact-prefix inventory across all production GeoIP feeds, RU RIR resources and independent BGP snapshots. Diff exact CIDRs and address-space totals vs v37.
4. Keep all candidates REVIEW; do not add/remove production prefixes until individual resource/origin evidence has been reviewed. Do not touch PR #5 or PR #6.

