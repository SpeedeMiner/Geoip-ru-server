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


## Последняя завершённая проверка — run #174

- PR #7: https://github.com/SpeedeMiner/Geoip-ru-server/pull/7 (open, Draft), branch docs/source-improvement-plan-2026-11.
- Full CI run #174: https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/42981784990 — **18/18 SUCCESS** on HEAD 543fb9329dfb127cd6fd82dc2dba393e8cccc23e.
- Artifact v37-prefix-audit-7, ID 13837562711, 646,557 bytes, SHA-256 41f8ada9315b872566eb9deea810bbe10dbab13dc4f429064d56964e70b874cf; downloaded and verified independently.
- 57 exact priority prefixes (53 MOAS + 4 company-only); all priority/triage/worklist rows REVIEW. RDAP 171/171 OK; RPKI 111 exact prefix/origin checks (66 valid, 20 invalid_asn, 25 unknown); IRR 57 queries.
- 23 external spot checks (22 from 2026-11-10 and 5.255.192.0/18 from 2026-11-11). Worklist scope relations 5 EXACT_ONLY / 17 EXACT_AND_MORE_SPECIFIC / 1 MORE_SPECIFIC_ONLY.
- 19 archived-invalid reconciliation rows, all REVIEW (classes 16/1/1/1).
- 5.255.192.0/18 remains REVIEW: MOAS AS13238 + AS208398; RU-YANDEX-20120914 / YANDEX LLC resource; 3 RDAP samples only; both exact ROAs valid (maxLength /24); exact RIPE/GRS object AS13238 only; AS208398 Serbian ASN. Treat as cross-border origin/IRR discrepancy, not proof of a foreign resource or transfer.
- No production data, builder, allowlist, DIRECT, geoip_RU.dat, release/tag changed. PR #5/#6 untouched.

## Следующий шаг

1. Validate the checkpoint commit created after run #174 with push-triggered CI.
2. Confirm PR #7 stays open/Draft.
3. Continue the actual data task: build a versioned source catalog and immutable raw input snapshot bundle; then generate the complete canonical exact-prefix inventory from all production GeoIP feeds, RU RIR resources and independent BGP sources, and diff exact CIDRs plus address-space totals against v37.
4. Keep uncertain prefixes REVIEW. No production ADD/EXCLUDE until prefix-level evidence is reviewed.
