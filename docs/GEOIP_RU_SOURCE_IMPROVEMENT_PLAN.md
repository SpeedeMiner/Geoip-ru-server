# План улучшения исходных данных российской GeoIP-базы

Дата: 2026-11-11 UTC. Baseline: main commit d6fa94a691a9635b72be4e6b941c87d29c802dfa, production v37 run #34.

## 1. Цель

Главная цель — улучшать состав IP-префиксов: находить пропущенные российские диапазоны, выявлять ошибочно включённые иностранные, проверять спорные случаи, вносить только доказанные изменения в source-of-truth и пересобирать базу с объяснимым diff.

Не создавать новые отчётные контуры ради самих отчётов. Каждый этап должен приводить к проверяемому списку exact CIDR-кандидатов, их доказательствам и решению ADD / EXCLUDE / REVIEW.

## 2. Критически важное различие в текущем продукте

Нынешняя категория RU в geoip_RU.dat — **не строго географический список России**. Это единый DIRECT-набор RU+BY+KZ плюс префиксы selected company/affiliate ASN, затем вычитание PRIVATE и утверждённых blocked destinations. В company exceptions есть сети отдельных зарубежных юрлиц (например, Yandex Türkiye / AS212066); два статических DIRECT pin сейчас явно привязаны к этому ASN.

Нельзя незаметно менять семантику этого файла или выдавать его за строго российскую географическую базу.

Предлагаемый путь:
1. Сохранить текущий geoip_RU.dat и его legacy DIRECT контракт до отдельного решения.
2. Параллельно построить строгий географический RU набор (рабочее имя будущего артефакта: geoip_RU_geographic.dat), где BY/KZ и company/affiliate exceptions не смешаны с географическим RU.
3. До подключения нового артефакта к клиентам согласовать его имя, формат, критерии включения и совместимость.

### Не смешивать доказательные измерения

- RIR country — страна регистрации адресного ресурса/ASN, не физическое местоположение сервера.
- ASN organisation — организация, зарегистрировавшая ASN; не доказательство владения каждым origin-prefix.
- BGP origin ASN — источник объявления точного NLRI; не автоматический доказательственный титул на адреса.
- IRR route object — запись маршрутизационной базы; может быть устаревшей, неполной или отсутствовать.
- ROA/RPKI — допустимость exact-prefix + origin ASN; это не геолокация и не подтверждение собственности.
- GeoIP feed — мнение/подборка конкретного поставщика, зависящие от его методики и даты.
- Company/affiliate exception — отдельная DIRECT политика, а не географическая классификация RU.

MOAS, смена origin, RPKI INVALID, отсутствие маршрута в одном агрегате и наличие дочернего маршрута сами по себе не дают основания автоматически добавлять или удалять диапазон.

## 3. Зафиксированный baseline

### Репозиторий и production

| Объект | Состояние |
|---|---|
| Default branch | main |
| Проверенный head | d6fa94a691a9635b72be4e6b941c87d29c802dfa |
| Production tag | latest-geoip-client-v37 |
| Production workflow | run #34, success |
| Run URL | https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/42969783654 |
| Release branch commit после run #34 | d613c5f0ef482f2051cbc37a303b2ac30076d313 |
| geoip_RU.dat | 951 531 bytes |
| SHA-256 | c70310071f7611d5c7ae54d409ae7c8d7b4598bbbbb706cbb44e9f0ca9303904 |

Текущий PR #6 остаётся отдельным Draft. PR #5 и его feature-ветка не используются и не меняются.

### Метрики production v37

По quality report и release artifacts run #34:

- RU category: 76 292 CIDR; IPv4 — 52 618 729 адресов; IPv6 — 1 192 441 882 017 908 537 250 295 700 258 816 адресов.
- В пяти RIR delegated-stat snapshots: 5 774 RU ASN и 385 BY/KZ ASN; RU-registered resource inventory содержит 13 679 CIDR.
- Company allowlist: 41 ASN; 38 имеют prefix records в ipverse snapshot.
- 5 336 выбранных ASN имеют наблюдаемые записи; суммарно по selected RIR-RU/BY/KZ и company origins найдено 23 564 уникальных префикса.
- Глобальный ipverse 90-day aggregate: 520 065 уникальных префиксов.
- 14 456 финальных CIDR не наблюдались в этом агрегате. Это NOT_OBSERVED, не UNROUTABLE.
- 7 235 финальных CIDR не имели address-space overlap с global aggregate; 66 651 не имели exact same-prefix announcement. Это разные измерения.
- Дополнительные GeoIP feeds дали union 39 642 CIDR; 25 180 получили подтверждение минимум от двух логических групп; после дедупликации по trusted layer новый дополнительный вклад — 190 CIDR.
- Blocked destination layer: 193 285 approved unique records; 28 555 community/Re-filter rows остаются review-only.

### Источники текущей сборки

**GeoIP / региональные источники**
- Core: Loyalsoldier RU, Loyalsoldier BY, v2fly RU/BY/KZ.
- Additional RU feeds: Grimbird, Digne, Davoyan, Golukon.
- Candidate-only: Hydra direct/whitelist, Kirill whitelist, HXEHEX, W1ZARDZ.
- Grimbird и Digne уже объединены в одну correlated logical group.

**RIR / IANA / BGP**
- Delegated statistics: AFRINIC, APNIC, ARIN, LACNIC, RIPE NCC.
- IANA IPv4/IPv6 Special-Purpose registries.
- ipverse as-ip-blocks tarball с aggregated.json по ASN, окно наблюдений до 90 дней.
- RU-registered IPv4/IPv6 resources используются как подтверждающий сигнал; BY/KZ ASN inventories участвуют в regional-origin layer.

**Blocked destinations**
- Antifilter ip.lst, ipresolve.lst, subnet.lst.
- Явно настроенные RunetFreedom Telegram prefixes.
- Antifilter community и Re-filter — только review candidates.
- Этот контур не является доказательством географии диапазона и не должен смешиваться с RU inventory.

## 4. Полный обзор репозитория: выводы

Проверены recursive tree main, production workflow, встроенный Go builder, unit tests, release artifacts, source provenance, все Python scripts/tests, prefix audit workflow, audit TSV и checkpoint journal.

### Сильные стороны

1. В build формируется source provenance manifest с URL, SHA-256, byte count и status.
2. RIR snapshots проверяются по формату, дате (не старше 14 дней) и sanity thresholds.
3. GeoIP protobuf парсится через protobuf library; output checksum и protobuf повторно проверяются.
4. Go trie обеспечивает объединение/пересечение/вычитание CIDR и точный подсчёт IPv4/IPv6 address space.
5. PRIVATE имеет приоритет; blocked feeds классифицированы раздельно; широкие subnet carve-outs ограничены.
6. Candidate-only feeds не включаются автоматически и не вычитаются из DIRECT.
7. Для Grimbird+Digne есть защита от двойного подтверждения коррелированными источниками.
8. Exact same-prefix BGP отделён от address-space overlap; есть full/partial/not-observed coverage.
9. Audit scripts разделяют RDAP, IRR, RPKI и BGP; ошибки запросов не маскируются под отрицательные ответы.
10. Priority prefix pipeline удерживает все строки в REVIEW и не переносит child route/ROA на parent NLRI.
11. Action implementations закреплены immutable commit pins; тестируются Python и Go части.

### P0 — точность и смысл IP-списка

- RU category объединяет географические RU, BY, KZ и company/affiliate origin сети; это не строгая география России.
- Импорт origin prefixes всех ASN, зарегистрированных в RU/BY/KZ, повышает полноту, но не доказывает, что каждый prefix принадлежит этому оператору или физически расположен в стране.
- Legal evidence уже фиксирует downstream/customer-route risk у крупных access/transit ASN, в частности AS3216 и AS8359. Prefix-level holder/control должен анализироваться отдельно.
- В company allowlist смешаны российские компании и региональные/зарубежные affiliate exceptions. Их надо держать отдельным policy layer.
- Нет единого canonical exact-prefix ledger, который сводит все feeds/RIR/BGP/RPKI/holder evidence и объясняет решение по каждой сети.
- Нет отдельного управляемого exact-prefix corrections source с причиной, reviewer и expiry. Static pins частично встроены в workflow code.
- Floating upstream refs main/master/release/latest обновляются динамически. Hash фиксирует байты запуска, но provenance не закрепляет git commit/tag/source snapshot ID.
- Не все raw .dat inputs, ipverse archive, RIR и IANA snapshots хранятся рядом с release. Это ухудшает воспроизводимость исторической сборки.

### P1 — полнота маршрутизации и evidence

- ipverse — единый до 90-дневный aggregate, а не синхронизированный full global RIB.
- Для полного инвентаря нужны независимые RIB/collector snapshots (минимум RouteViews и RIPE RIS), timestamp, collector/peer coverage и exact NLRI.
- Отдельные RIPEstat RPKI-запросы полезны, но не образуют единый VRP snapshot, синхронизированный с RIB.
- RDAP first/middle/last samples — сигнал для review, а не исчерпывающая проверка всех suballocation внутри крупного prefix.
- IRR запросы используют RIPE и доступные GRS источники из RIPE metadata; отсутствие exact object не доказывает глобальное отсутствие IRR или BGP.
- Корреляция установлена для Grimbird+Digne, но не для всех дополнительных feeds/форков/зеркал.
- Нужна приоритизация нового address space, а не количественное увеличение источников.

### P2 — поддерживаемость и release safety

- blank.yml содержит около 3 500 строк, включая большой embedded Go builder и shell/Python stages; source definitions, policy и implementation трудно ревьюить независимо.
- Source URLs/ref, category mappings, correlation groups, company exceptions и static prefix pins частично зашиты в workflow.
- CI проверяет schema/sanity/счётчики, но нужен полный address-space diff к предыдущему release с указанием источников и причин.
- Любой push в main запускает production workflow с contents:write, который публикует release и force-updates release branch. Даже merge документационного PR запускает production build.
- На момент baseline main branch protection не включён. Нужно отдельно согласовать review/approval process для production data changes.

## 5. Целевая модель исходных данных

### 5.1 Versioned source catalog

Создать data source catalog (YAML/TSV) с полями:
- source ID, source class, URL, immutable git commit/tag/snapshot ID;
- schema, parser version, IPv4/IPv6 support;
- update frequency, source authority, known limitations;
- correlation group и dependency notes;
- допустимая роль: geo seed, RIR resource, BGP route, company exception, candidate-only, blocked destination;
- SHA-256, size, download timestamp, actual mirror URL и retention policy.

Зеркала одного upstream не считаются независимыми источниками. Mirror fallback должен пройти те же schema/content checks; в provenance записывается фактически использованный URL.

### 5.2 Canonical exact-prefix inventory

Одна строка — один canonical exact CIDR. Рекомендуемые поля:
PREFIX, FAMILY, SOURCE_IDS, SOURCE_GROUPS, RIR_COUNTRY, RIR_REGISTRY, RESOURCE_STATUS, RESOURCE_HOLDER, RESOURCE_HANDLE, ASN_REGISTRANT, BGP_ORIGIN_ASNS, BGP_SNAPSHOT_IDS, BGP_FIRST_SEEN, BGP_LAST_SEEN, RPKI_STATUS_BY_ORIGIN, IRR_EXACT_ORIGINS, GEO_FEED_COUNTRIES, CORRELATION_NOTES, DECISION, DECISION_REASON, EVIDENCE_URLS, REVIEWED_AT, REVIEW_EXPIRY.

Хранить связку prefix → origin ASN → source snapshot. Не сводить доказательства к фразе «ASN российский».

### 5.3 Разделённые статусы кандидатов

- CONFIRMED_RU — достаточно данных, что exact prefix входит в строго географический RU scope.
- RU_REGISTERED_NOT_ROUTED — RU resource по RIR, но активный маршрут не наблюдался; не терять из inventory, отдельно решать inclusion в routable output.
- RU_ORIGIN_REVIEW — маршрут от RU ASN, но holder/control/geographic scope не подтверждён.
- FOREIGN_RESOURCE_REVIEW — признаки иностранного ресурса/субаллокатора; не исключать автоматически.
- MOAS_REVIEW — несколько exact origins, каждый анализируется отдельно.
- STATIC_EXCEPTION — вручную утверждённый pin с основанием и expiry.
- NOT_OBSERVED — отсутствует в конкретном snapshot, с указанием источника и окна.
- REJECTED_WITH_EVIDENCE — исключение с документированной exact-prefix причиной.

До отдельного решения все новые и спорные кандидаты остаются REVIEW.

### 5.4 Curated exact-prefix corrections

Добавить отдельный ручной ledger, не смешанный с company ASN allowlist и blocked list. Поля:
PREFIX, ACTION (ADD/EXCLUDE/REVIEW), SCOPE (STRICT_RU/LEGACY_DIRECT), RESOURCE_HOLDER, ORIGIN_ASNS, EVIDENCE_CLASS, REASON, SOURCE_URLS, APPROVED_BY, APPROVED_AT, EXPIRES_AT.

- Любой ADD/EXCLUDE содержит exact CIDR и evidence URLs.
- Нельзя переносить дочерние route/RPKI данные на parent.
- Static prefix без BGP маркируется STATIC/NOT_OBSERVED, а не как live announcement.
- Временный pin обязан иметь review/expiry date.
- Изменения не применять к legacy output без отдельного policy approval.

## 6. Непосредственный рабочий цикл

### Этап A — immutable baseline и snapshots
1. Зафиксировать main, release, tag, output SHA-256, quality report и input provenance.
2. Сохранить raw snapshot каждого источника, SHA-256, byte count, UTC timestamp, immutable upstream ref и фактический URL зеркала.
3. Не считать floating main/master/latest воспроизводимой версией.

Выход: source snapshot bundle и manifest одного build run.

### Этап B — российские адресные ресурсы
1. Из пяти RIR delegated-stat files получить все RU IPv4/IPv6 resources со status/date; сохранить raw record → CIDR expansion связь.
2. Отдельно сформировать RU ASN registry и RU address-resource inventory.
3. Добавить RDAP/RIR holder/organisation; отличать registrant, maintainer, sponsoring LIR и ASN organisation.
4. Добавить официальные prefix/ASN lists операторов с точным scope источника.

Выход: RU resource inventory без автоматического расширения на все AS-origin prefixes.

### Этап C — BGP/RPKI snapshots
1. Собрать exact NLRI из RouteViews и RIPE RIS.
2. Записать UTC timestamp, dataset/collector, peer coverage, archive SHA-256 и last-seen.
3. Сохранить полный exact origin set для каждого NLRI; MOAS не схлопывать.
4. Для той же временной точки использовать VRP snapshot и проверять каждую пару prefix+origin с maxLength.
5. Parent, child more-specific и covering aggregate — разные NLRI.
6. ipverse использовать как discovery/history layer, не как единственный текущий route verdict.

Выход: exact route inventory и временно согласованный RPKI.

### Этап D — полный diff с текущей базой
Для каждого CIDR сопоставить текущий release, trusted GeoIP feeds, RIR RU resources, RU ASN origins, independent RIB, company exceptions и candidate feeds.

Посчитать CIDR и exact address-space additions/removals/intersections/partial overlaps. Для каждой разницы записать причину: source addition/removal, origin change, RIR update, route withdrawn/not observed, source correlation или policy decision.

Выход: missing_candidates.tsv, foreign_or_misclassified_candidates.tsv, prefix_diff_summary.txt.

### Этап E — review candidates
**ADD:** предпочтительно exact route observation + согласованное RIR/official resource evidence. Для unannounced resource — отдельное документированное основание.
**EXCLUDE:** нужны точные сведения о foreign resource/holder или доказанная ошибка источника. Только иностранный origin/countryCode, отсутствие в 90-day archive или RPKI INVALID недостаточны.
**MOAS:** каждый origin и exact NLRI проверяются отдельно.
**Transit/access ASN:** различать собственную сеть, customer/downstream routes и транзитно переносимые маршруты.
Нерешённые строки остаются REVIEW.

Выход: curated decision ledger с reviewer/date/expiry.

### Этап F — правка source-of-truth и сборка
1. Только подтверждённые решения переносить в управляемый ledger/source input.
2. Сначала строить strict RU output параллельно, не меняя legacy geoip_RU.dat.
3. Тестировать parsers, exact CIDR, nested prefixes, MOAS, RPKI, IPv4/IPv6 и protobuf.
4. Создавать prefix-level additions/removals и address-space diff.
5. Сравнивать с предыдущим release; массовый необъяснённый diff останавливает публикацию.
6. Production publish — после отдельного approval/review.

Выход: новая проверенная база и explainable diff.

### Этап G — постоянный цикл
- Ежедневно: source snapshots + автоматический diff, без автоматического принятия спорных policy решений.
- Еженедельно: разбор новых missing/foreign/MOAS/unknown candidates.
- Внепланово: смена ASN/RIR/RPKI или массовые withdrawals.
- Для ручных решений: expiry/review date.
- После сборки: SHA-256, release assets, branch contents и quality report.

## 7. Очерёдность работ

| Приоритет | Работа | Проверяемый результат |
|---|---|---|
| P0 | Зафиксировать strict RU семантику отдельно от legacy DIRECT | Policy без изменения текущих клиентов |
| P0 | Versioned source catalog + immutable refs + raw snapshots | Можно воспроизвести один build run |
| P0 | Полный exact-prefix inventory и diff к v37 | Все пропуски/излишки как CIDR rows |
| P1 | RouteViews + RIPE RIS + синхронный VRP | Exact origins/RPKI на общий временной интервал |
| P1 | Prefix holder/control review | Нет автоматической экстраполяции ASN registrant |
| P1 | Curated exact-prefix ledger | ADD/EXCLUDE имеют причину/reviewer/expiry |
| P1 | Параллельная strict RU сборка | География не смешана с BY/KZ/affiliate |
| P2 | Вынести builder/parsers/config из workflow heredoc | Независимые модули и тесты |
| P2 | Diff-based release gates + protected branch | Необъяснённые массовые изменения не публикуются |

## 8. Критерий готовности изменения данных

Для каждого production prefix должны быть заполнены exact CIDR, family, scope, resource evidence, holder/registrant, exact origin set и timestamp (если наблюдается), exact RPKI per origin (если применимо), GeoIP feed matches/correlation, причина географического решения, адресный вклад в diff, reviewer/date/expiry. Неопределённость должна сохраняться, а не маскироваться под одобрение.

## 9. Текущий следующий шаг

После этого документационного этапа собрать source catalog и immutable snapshot bundle, затем построить canonical exact-prefix inventory для всех production GeoIP feeds, RIR RU resources и независимых BGP sources. Сравнить с v37 release по exact CIDR и адресу. Только затем готовить data PR с доказанными ADD/EXCLUDE.
