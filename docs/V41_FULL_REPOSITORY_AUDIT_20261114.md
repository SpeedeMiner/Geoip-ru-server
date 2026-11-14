# Аудит Geoip-ru-server v41, 14 ноября 2026 (UTC+05)

## Вывод

В проверенном выпуске не обнаружено повреждения GeoIP или расхождения с sing-box. Пересборка из 37 проверенных входов дала побайтовое совпадение DAT, обоих SRS, итоговой маски исключений и двух архивов. Подтверждены расхождения в политике импорта W1ZARDZ, отслеживании происхождения BGP, исторических блокировках и контракте публикации. Наиболее срочные исправления — сделать исторические снимки самодостаточными и закрыть несогласованность между GitHub Release и веткой release.

Проверенный код — [main 596c93df](https://github.com/SpeedeMiner/Geoip-ru-server/commit/596c93df3b65b36b34ef9a8c5472b9e9ee660691), артефакты — [release 7eef1efc](https://github.com/SpeedeMiner/Geoip-ru-server/commit/7eef1efcaafbdbe259f3aa4e56a07c38979afbfb), [snapshot 43617500418.1](https://github.com/SpeedeMiner/Geoip-ru-server/releases/tag/geoip-v41-snapshot-43617500418.1), [успешная сборка](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43617500418). Аудит охватил 119 файлов main по Git blob ID, рабочий v41, контракт наследуемых v38/v39 и prefix-audit, локальные таблицы управления политикой, архивы, rolling-релиз и выпускную ветку. Код, маршруты, релизы, теги и PR #5 не изменялись. Подтверждена семантика списков, но не фактическая достижимость из абонентских сетей России, Беларуси и Казахстана.

## P1 — влияние на политику DIRECT или воспроизводимость выпуска

### 1. Импорт W1ZARDZ шире, чем заявлено

Политика обещает W1ZARDZ только при пересечении с ресурсами RIR-RU. В сборщике пересечение применяется к защитным маскам DNS, а не к первичному объединению DIRECT. Из W1ZARDZ 10 767 IPv4 вне RIR-RU и 2 575 вне всех RIR RU/BY/KZ находятся в итоговом RU. Большинство имеют другие основания. Ровно **262 IPv4 допущены исключительно W1ZARDZ**, все вне RU/BY/KZ RIR. Это `38.244.136.0/24` и шесть хостов `104.26.6.129`, `104.26.7.129`, `143.20.177.3`, `172.64.150.18`, `172.67.73.25`, `172.67.73.142`. Расчёт выполнен как пересечение финального RU с W1ZARDZ минус объединение v37 и всех остальных положительных слоёв.

Рекомендуется отдельно согласовать ожидаемую границу: строго RIR-RU, RIR RU/BY/KZ либо полный импорт с явными исключениями. Для проверки — фиксированный тест для префикса вне региона и отчёт об уникальном вкладе. Не считать эти IP вредоносными или недоступными только из-за отсутствия регионального RIR.

[Заявленное правило](https://github.com/SpeedeMiner/Geoip-ru-server/blob/596c93df3b65b36b34ef9a8c5472b9e9ee660691/docs/GEOIP_RU_V41_POLICY.md#L7-L14) · [Защитные маски](https://github.com/SpeedeMiner/Geoip-ru-server/blob/596c93df3b65b36b34ef9a8c5472b9e9ee660691/.github/scripts/build_v41_overlay.py#L524-L545) · [Фактическое объединение](https://github.com/SpeedeMiner/Geoip-ru-server/blob/596c93df3b65b36b34ef9a8c5472b9e9ee660691/.github/scripts/build_v41_overlay.py#L767-L770)

### 2. Версионный snapshot не хранит все входы своей маски исключений

Архивы сохраняют routing feeds, Telegram, RIR/IANA и ipverse, но ни assets версионного релиза, ни его Git-дерево не содержат `antifilter-ip.lst`, `antifilter-ipresolve.lst`, `antifilter-subnet.lst`, `antifilter-community.lst`, `refilter-ipsum.lst` и три исторических raw-файла v38. Все восемь есть в **rolling** assets. Первые три участвуют в маршрутизации непосредственно, исторические нужны для атрибуции, Community и Re-filter — только для аудита. `antifilter-ipsum.lst` и нормализованная v38 baseline сохранены в Git-дереве. Хеши отсутствующие исходные байты не заменяют. Текущая пересборка удалась за счёт точных байтов rolling-файлов, сохранённых отдельно. После ротации этот путь не гарантирован. В manifest нет явной ссылки на commit исходного сборщика, хотя текущий SHA восстанавливается из запуска Actions.

Рекомендуется создать версионный архив block-входов с обязательным чтением обратно и проверкой каждого члена. Записывать source commit, run URL и перечень сырых входов в сам snapshot и его manifest.

[Что загружается как версионный релиз](https://github.com/SpeedeMiner/Geoip-ru-server/blob/596c93df3b65b36b34ef9a8c5472b9e9ee660691/.github/scripts/publish_v41_snapshot_release.sh#L6-L29) · [Опубликованные файлы snapshot](https://github.com/SpeedeMiner/Geoip-ru-server/releases/tag/geoip-v41-snapshot-43617500418.1)

### 3. Rolling-тег, assets и release-ветка имеют разные контракты

Assets `latest-geoip-client-v41` сейчас совпадают с опубликованным DAT и SRS. Однако Git-тег стоит на `4338b53b5de528519031c9eca213560f3e99151c`, в Git-дереве которого нет `geoip_RU.dat`. Версионный тег и `release` указывают на `7eef1efc`. GitHub Source code ZIP и checkout по rolling-тегу не дают дерево текущего продукта. Кроме того, ветка `release` переключается **до** отдельной загрузки rolling-assets. Если второй шаг прервётся, raw/CDN и Release могут указывать на разные версии или разойтись по отдельным файлам и checksums. В этом запуске сбоя не было.

Рекомендуется явно обозначить rolling-тег как alias к mutable assets и дать клиентам предпочтительную неизменяемую пару URL+SHA. Для совместимости — генерировать один manifest выпуска, проверять DAT/SRS/checksum через публичные точки после каждого обновления, фиксировать и сигнализировать partial publish, предусмотреть повторную сверку и восстановление. Не обещать атомарное обновление независимо обслуживаемых endpoints.

[Порядок фаз и rolling-тег](https://github.com/SpeedeMiner/Geoip-ru-server/blob/596c93df3b65b36b34ef9a8c5472b9e9ee660691/.github/workflows/geoip-v41.yml#L605-L640) · [Rolling Git-дерево](https://github.com/SpeedeMiner/Geoip-ru-server/tree/4338b53b5de528519031c9eca213560f3e99151c) · [GitHub о source archives](https://docs.github.com/en/repositories/working-with-files/using-files/downloading-source-code-archives)

## P2 — корректность классификации, надёжность и обслуживание

### 4. Исторические исключения не переаттестуются, а источники могут деградировать незаметно

В сборке v38 baseline добавляется **безусловно**, а не только когда пуст текущий ipresolve. В snapshot **7 239 IPv4** из исторической baseline не пересекаются с тремя текущими рабочими фидами или hard-маской. **6 902** остаются в эффективной маске. Это не 6 902 доказанно разблокированных IP и не утверждение, что все они иначе вошли бы в DIRECT. У 746 ручных hard-записей одинаковая дата 2026-11-13. Срока переаттестации нет. Скачанные фиды проверяются преимущественно по наличию строк и формату, не по свежести или дельте каждого источника. Например, host-фид проверяет число строк и хотя бы один валидный уникальный CIDR, а не минимальный размер принятого набора. Текущие 50 727 ip.lst и 154 157 принятых строк ipresolve не показали такой деградации. Review-only HXEHEX, ipsum и прочие источники могут задержать или остановить production даже без вклада в итоговый DAT.

Рекомендуется различать действующие, перенесённые и устаревшие записи, показывать годность доказательств и дельты по источникам, не удалять исторические IP автоматически. Сделать явный degraded-режим диагностических входов, не ослабляя обязательные Telegram/hard-проверки. Ошибочное описание hard-политики исправить отдельно: текущий `ip.lst` весь advisory, таблица исключений для 63 хостов не участвует. Из этих 63 все в опубликованном DIRECT, а 60 по-прежнему есть в текущем ip.lst.

[Импорт baseline и проверки текущих фидов](https://github.com/SpeedeMiner/Geoip-ru-server/blob/596c93df3b65b36b34ef9a8c5472b9e9ee660691/.github/scripts/prepare_blocked_sources_v41.py#L203-L279) · [Историческое описание 63 хостов](https://github.com/SpeedeMiner/Geoip-ru-server/blob/596c93df3b65b36b34ef9a8c5472b9e9ee660691/docs/V41_REVIEWED_IP_LIST_HOSTS.md#L1-L12) · [Antifilter о типах источников](https://antifilter.download/)

### 5. Агрегированный ipverse не является набором точных BGP-анонсов

Выбор origin берёт `aggregated.json`, который, по документации ipverse, схлопывает соседние и перекрывающиеся префиксы. Файлы проекта называют результат «exact BGP prefixes» и используют равенство CIDR в части аудита exact/MOAS и при классификации компании. Префикс может быть синтетическим после агрегации, временным, не отражать текущий longest-prefix match или origin более специфичной сети. Закреплённые Yandex CIDR маркируются отдельно в selected origins, но эта метка не переносится в некоторые производные sidecars. Отсутствие в ipverse у **2 459 302 IPv4 (4,61%)** и **68,39% IPv6 адресного пространства** итогового RU — не доказательство недоступности. Огромная доля IPv6 отражает вес широких аллокаций.

Рекомендуется переименовать метрики в `ipverse aggregate`, а «exact announced prefix», exact MOAS, RPKI и чувствительные спорные исключения подтверждать неагрегированным RIB с датой и коллектором. Отделить pins от observed downstream. Не вычитать автоматически неанонсируемые или широкие региональные аллокации.

[Описание ipverse](https://github.com/ipverse/as-ip-blocks) · [Разбор и provenance выбранных origin](https://github.com/SpeedeMiner/Geoip-ru-server/blob/596c93df3b65b36b34ef9a8c5472b9e9ee660691/.github/scripts/extract_ru_asn_prefixes_v41.py#L196-L261) · [Заголовок производного набора](https://github.com/SpeedeMiner/Geoip-ru-server/blob/596c93df3b65b36b34ef9a8c5472b9e9ee660691/.github/scripts/build_company_asn_prefixes.py#L122-L141)

### 6. Сверка SRS и hard policy разнесена между стадиями, но общий выпускной контракт неполон

Сборочный job сравнивает декомпилированный SRS с DAT и проверяет hard policy. Публикующий job видит SRS только через собственные sidecars, запускает `build_v41_srs.py` без компилятора (это проверка DAT), а наличие hard gate подтверждает текстовым маркером отчёта. Перед переключением ветки скачивает обратно три архива источников, но не публичные DAT и оба SRS. На данном выпуске независимо проверено фактическое равенство, ошибки не обнаружено. В следующем запуске структурное несоответствие файлов может остаться вне повторной проверки. Версионные релизы create-only по workflow, но API для snapshot отдаёт `immutable=false`. GitHub API отметил main и release как `protected=false`, список rulesets пуст.

Рекомендуется единый manifest, связывающий source commit, DAT, SRS, hard-mask и результаты тестов, плюс read-back конечных assets. Протестировать fail/retry на фазах публикации, настроить branch protections и required CI для main, контролировать запись в release отдельно. Сохранять текущий split прав read/write и SHA-пины Actions.

[Выпускные проверки](https://github.com/SpeedeMiner/Geoip-ru-server/blob/596c93df3b65b36b34ef9a8c5472b9e9ee660691/.github/scripts/verify_v41_publication_candidate.sh#L3-L31) · [Проверка публичных архивов](https://github.com/SpeedeMiner/Geoip-ru-server/blob/596c93df3b65b36b34ef9a8c5472b9e9ee660691/.github/scripts/promote_v41_release.sh#L25-L66) · [GitHub immutable releases](https://docs.github.com/en/code-security/concepts/supply-chain-security/immutable-releases)

### 7. Недостаточная переносимость и свежесть входов

RIR-скрипты используют текущую дату и не принимают дату выпуска. Поэтому прямой повтор исторической сборки после 14 дней блокируется даже для исходных опубликованных байтов, и потенциально ложные остановки распространяются на вторичные зеркала. Это полезный контроль для rolling, но не для воспроизведения. ipverse при загрузке проверяется по формату, compressed size и количеству записей, а не по дате конкретного наблюдения или свежести среза относительно предыдущего. Указание современного Git ref для routing feeds проверяет идентичность, а не свежесть контента.

Рекомендуется явный режим replay с датой из проверенного manifest. Оставить fail-closed контроль rolling-свежести и аномалий, но с отдельной обработкой транспортной недоступности и пер-фид статистикой.

[Проверка возраста RIR](https://github.com/SpeedeMiner/Geoip-ru-server/blob/596c93df3b65b36b34ef9a8c5472b9e9ee660691/.github/scripts/build_rir_rukzby_prefixes.py#L48-L64) · [Второй RIR-парсер](https://github.com/SpeedeMiner/Geoip-ru-server/blob/596c93df3b65b36b34ef9a8c5472b9e9ee660691/.github/scripts/build_v41_rir_legacy_inventory.py#L25-L66)

## P3 — метрики, CLI и документация

- **IANA CSV пропускает валидные записи.** Парсер читает всё поле Address Block как один CIDR. Сноска на `192.0.0.0/24 [2]` и список `192.0.0.170/32, 192.0.0.171/32` выпали из нормализованного IANA sidecar. Итоговый PRIVATE сейчас сохранил оба хоста и 254 адреса /24 благодаря другим входам, исключив глобальные `.9` и `.10`. Влияние на опубликованный DAT не обнаружено. Добавить поддержку сносок и нескольких CIDR, не трактовать `N/A` как False автоматически. [Парсер](https://github.com/SpeedeMiner/Geoip-ru-server/blob/596c93df3b65b36b34ef9a8c5472b9e9ee660691/.github/scripts/build_v41_iana_special_prefixes.py#L21-L35) · [IANA IPv4 Special-Purpose Registry](https://www.iana.org/assignments/iana-ipv4-special-registry)
- **Классы завышают объём на этапе сборки.** В stdout функция `metrics()` суммирует размеры перекрывающихся CIDR. Для всего корпоративного набора получается **20 076 544** вместо **19 617 024** уникальных IPv4 (+459 520). Для CORE **482 560** вместо **463 104**. Финальные метрики оверлея используют объединение интервалов и этих ошибок не содержат. [Функция](https://github.com/SpeedeMiner/Geoip-ru-server/blob/596c93df3b65b36b34ef9a8c5472b9e9ee660691/.github/scripts/build_company_asn_prefix_classes_v41.py#L164-L179)
- **CDN purge best effort, одна ошибка прерывает список.** `set -e` прекращает серию после первой ошибки, workflow оставляет выпуск успешным. На рассматриваемом запуске purge прошёл. Рекомендуется пытаться обновить все URL, показывать сводку и предлагать неизменяемые URL для воспроизводимости. [Скрипт](https://github.com/SpeedeMiner/Geoip-ru-server/blob/596c93df3b65b36b34ef9a8c5472b9e9ee660691/.github/scripts/purge_v41_jsdelivr.sh#L1-L17) · [Workflow](https://github.com/SpeedeMiner/Geoip-ru-server/blob/596c93df3b65b36b34ef9a8c5472b9e9ee660691/.github/workflows/geoip-v41.yml#L703-L706)
- **У проекта нет корневых README/LICENSE/NOTICE в проверенной версии.** Release notes упоминают CC BY-SA v2fly и CC BY DB-IP, но нет единого руководства и машиночитаемого инвентаря прав для опубликованных агрегатов/исходников. GitHub metadata на момент проверки не указала лицензию для Hydra. Это основание запросить и записать разрешение, а не вывод о нарушении лицензии. Также main содержит дублирующий root-реестр, который не читает production; сейчас он побайтно равен рабочему .github/data файлу. Убрать возможность тихого расхождения, вывести отдельно legacy «base only» описания Hydra и 63 хостов. [Рабочий источник реестра](https://github.com/SpeedeMiner/Geoip-ru-server/blob/596c93df3b65b36b34ef9a8c5472b9e9ee660691/.github/scripts/download_v41_build_inputs.sh#L4-L11) · [Текущие атрибуции](https://github.com/SpeedeMiner/Geoip-ru-server/blob/596c93df3b65b36b34ef9a8c5472b9e9ee660691/docs/V41_ROLLING_RELEASE_NOTES.md#L41-L49)

## Что проверено

- 164 Python-теста, Go-тесты (15 top-level и subtests) и синтаксис пяти YAML. Production сборка и две задачи опубликованного запуска завершились успешно.
- Повторены RIR/IANA, ASN-экстрактор, классы, блокировки, Go v37, Python v41, проверки base/overlay, hard/Telegram, архивы и SRS. Один из независимых release envelope прогонов сравнил повторную сборку с опубликованным release и получил нулевую дельту при неизменном PRIVATE.
- 32 774 RU CIDR, 53 399 040 IPv4, PRIVATE 151 CIDR. Пересечение RU с PRIVATE, полной официальной маской Telegram, effective block, hard IP и ручными региональными исключениями равно нулю по применимым семействам.
- Corporate v41 — 57 записей, 53 имеют наблюдения в ipverse. Неверные v34 AS30972, AS50952 и AS200676 отсутствуют. AS35022 и AS197482 присутствуют в корпоративной маске. AS207353 и AS31174 поступают по RIR/BGP независимо от корпоративного реестра, фактического пробела в их BGP-входе нет. Никакого массового переноса политик v34 не требуется.
- Относительно исправленного v34 (`82edca0c…`) Full v41 покрывает 49 520 926 из 49 525 599 IPv4 (99,990564%), добавляет 3 878 114 адресов. В v34 остаётся 4 673 IPv4 вне v41. Покрытие IPv6 исправленного v34 составляет 100%, PRIVATE идентичен.
- Полный DAT SHA-256 `5d7e9dd0eb66bd507eb5f695b83441493fb20b2307ef71125de16c8b3809fa7d`. RU SRS `21c54a6b83c7292ec51c8fff33f19e54cc869750cb6e3cea87d7662df87684e0`. PRIVATE SRS `b9ea6381ea61e286298aea76c10cb85a252ff0d20c49d6de3527be1353c107c4`.

## Очередь исправлений

1. Версионный архив отрицательных входов и связь release с source commit. Проверить повтор без обращений к rolling assets.
2. Единый manifest публикации, сверка фактических публичных DAT/SRS и сигнал при рассинхронизации endpoints. Раздельные retry публикации и CDN.
3. Зафиксировать ожидаемое правило W1ZARDZ и тест точной дельты. Затем ревизия 6 902 исторических адресов без автоматического возврата.
4. Развести типы BGP-данных и проверку свежести; добавить корректный IANA CSV и дедупликацию метрик.
