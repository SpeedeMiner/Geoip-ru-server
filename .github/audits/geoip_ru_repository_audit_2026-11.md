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
