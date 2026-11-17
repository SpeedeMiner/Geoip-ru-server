# v41 durable execution journal

## 2026-11-17 — отдельный PR №57 и завершённая очередь шести /24

- [x] [Черновик PR №57](https://github.com/SpeedeMiner/Geoip-ru-server/pull/57) восстановил только шесть точных /24 в кандидатном DAT. CI v41 и v39 прошли, publish v41 пропущен. Из свежего ZIP к rolling `75fdbb1` +1 536 IPv4, без удалений; IPv6, PRIVATE и эффективная маска не изменились. `31.204.32.0/20` не добавлена. [Точные доказательства](https://github.com/SpeedeMiner/Geoip-ru-server/blob/bbb4434a0c434467356ad3a3c47ec2b1e16068b0/docs/V41_SIX_PREFIX_RETENTION_PR57_20261117.md).
- [x] В независимом повторе тот же DAT воспроизведён локально. Синтетическая жёсткая /32 внутри одного из удерживаемых диапазонов остановила сборку до записи DAT и вывела соответствующий /24. Жёсткие блоки и PRIVATE не обойдены.
- [x] Пятый и шестой /24 прошли двухвыходный замер. Всего 6/6 диапазонов, 5/6 с обоими постконтролями, 3 072 зачтённых TCP/443 тайм-аута до TLS. Сертификатов нет, подтверждённых сервисных пар 0/6. [Итог и ASN](https://github.com/SpeedeMiner/Geoip-ru-server/blob/bbb4434a0c434467356ad3a3c47ec2b1e16068b0/docs/V41_LIVE_CIDR24_177_166_21_20261117.md).
- [ ] Следующее решение — ревью точечного PR №57 отдельно от Hydra и поиск именованных сервисных точек. Тайм-аут не доказывает блокировку, дата ручного пересмотра 17 декабря. Публичные `release 75fdbb1` и `cdn 2edb37e` не менялись. [Handoff](https://github.com/SpeedeMiner/Geoip-ru-server/blob/bbb4434a0c434467356ad3a3c47ec2b1e16068b0/docs/V41_PROJECT_HANDOFF.md).

## 2026-11-17 — изолированное восстановление и четыре измеренных /24

- [x] На закреплённом rolling проверен возврат только шести /24: +1 536 IPv4 без удалений, IPv6, PRIVATE и эффективная маска не изменились. Hydra `31.204.32.0/20` не добавлена. Результат совпал по адресам с replay штатным сборщиком, Linux подтвердил DAT/SRS. [Отчёт о восстановлении](https://github.com/SpeedeMiner/Geoip-ru-server/blob/6c7ddadf27efc3c0df681a91db2a331e5ad42efd/docs/V41_SIX_PREFIX_RECOVERY_PROOF_20261117.md)
- [x] Отдельный контроль покрытия обнаружил все 6 пропусков в rolling и ни одного в пробе, 13 тестов прошли. Старая потеря 1 536 IPv4 была ниже общего порога 267 035. Проверка работает только в диагностической ветке.
- [x] `177.122.107.0/24` засчитан на AS12494 и AS43330. 512 TCP/443 TIMEOUT до TLS; оба постконтроля прошли. Охват двумя ASN — 4/6 (66,7%), сервисные пары — 0/6. [Отчёт о четвёртом замере](https://github.com/SpeedeMiner/Geoip-ru-server/blob/6c7ddadf27efc3c0df681a91db2a331e5ad42efd/docs/V41_LIVE_CIDR24_177_122_107_20261117.md)
- [ ] `177.122.160.0/24` пройден на первом AS12494: 256 TIMEOUT до TLS, после замера тот же выход и HTTP 200. Нужен второй ASN. [Машиночитаемая сводка](https://github.com/SpeedeMiner/Geoip-ru-server/blob/6c7ddadf27efc3c0df681a91db2a331e5ad42efd/docs/v41-cidr24-review-progress-20261117.json)
- [ ] Отдельно решить перенос точечного восстановления и проверки покрытия в production. PR №56 остаётся черновиком. Публичные `release 75fdbb1` и `cdn 2edb37e` не сдвинулись. [Handoff](https://github.com/SpeedeMiner/Geoip-ru-server/blob/6c7ddadf27efc3c0df681a91db2a331e5ad42efd/docs/V41_PROJECT_HANDOFF.md)

## 2026-11-17 — три /24 измерены через VPNObratno

- [x] `177.29.246.0/24` полностью проверен через AS12494 и AS43330. По 256 TCP/443 TIMEOUT до TLS, сертификатов нет. В обоих засчитанных замерах после серии подтверждены тот же выход и контрольный HTTP 200. Яндекс Basic UDP использовался для контрольных имён. [Отчёт и ZIP](https://github.com/SpeedeMiner/Geoip-ru-server/blob/addbbee18c5f0e280f5dbe3e1f828d84a0b3ff49/docs/V41_LIVE_CIDR24_177_29_246_20261117.md).
- [x] Промежуточная попытка AS43330 без подтверждения VPN после серии исключена из сравнения. SHA-256 и CRC трёх ZIP проверены. Два ASN на диапазон — 3/6 (50%), оба постконтроля — 2/6, сервисные пары — 0/6. [Машиночитаемый статус](https://github.com/SpeedeMiner/Geoip-ru-server/blob/addbbee18c5f0e280f5dbe3e1f828d84a0b3ff49/docs/v41-cidr24-review-progress-20261117.json).
- [ ] Следующий диапазон — `177.122.107.0/24`. Тайм-аут не доказывает блокировку. VPN-диагностика не меняла правила DIRECT кандидата и дату ручного пересмотра. [Handoff](https://github.com/SpeedeMiner/Geoip-ru-server/blob/addbbee18c5f0e280f5dbe3e1f828d84a0b3ff49/docs/V41_PROJECT_HANDOFF.md).

- [x] Отдельно [production run 44083585727](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/44083585727), запущенный со старого `main 5134c177`, обновил `release` до `75fdbb1` и `cdn` до `2edb37e`. В новом DAT все 6 спорных /24 вне RU, в кандидате они сохранены. Кандидат против нового rolling: +5 632 IPv4 без удалений, IPv6 и PRIVATE совпадают. [Точная сверка](https://github.com/SpeedeMiner/Geoip-ru-server/blob/8ab46d0eb3163dcebf1a9dfb486255a060a43f2c/docs/V41_LIVE_CIDR24_177_29_246_20261117.md).

## 2026-11-17 — второй /24 измерен с контролем до и после

- [x] `156.241.186.0/24` дважды проверен по TCP/443 через VPNObratno из РФ, AS8749 и AS8359. Все 256 адресов на каждом выходе дали тайм-аут до TLS, пропусков и сертификатов нет. Тот же VPN-выход и HTTPS 200 подтверждены и после каждого прогона. [Отчёт и исходные архивы](https://github.com/SpeedeMiner/Geoip-ru-server/blob/bec7e9ba2d5108fca01b362d2dbcd231f19ac713/docs/V41_LIVE_CIDR24_156_241_186_20261117.md).
- [x] Сверены SHA-256 и строки по IP четырёх архивов двух /24. Охват диапазонов 2/6 (33,3%), проверенный постконтроль на обоих выходах 1/6, сервисные пары 0/6. В опубликованном DAT, базе v37 и кандидате все шесть /24 — точные ключи RU, вне PRIVATE. Пассивные RouteViews и RPKI сохранены отдельно.
- [x] Публичный контактный домен `yemail.live` проверен через российский VPNObratno и Яндекс DNS. A `162.255.119.130` вне очереди, TCP/TLS по имени и адресу не запускались.
- [ ] Следующим в очереди остаётся `177.29.246.0/24`. Тайм-ауты не считаются блокировкой и не меняют DIRECT. Остальные четыре /24 не обходились. Release, CDN и дата пересмотра не менялись.

## 2026-11-17 — первый фактический замер одного IPv4 /24 через VPNObratno

- [x] `156.224.80.0/24` измерен по TCP/443 через два подтверждённых российских ASN, AS12494 и AS8749. SHA-256 обоих ZIP проверен и по IP сверены все 256 пар: только TIMEOUT, ни одного начатого TLS. Контрольный CDNvideo дал валидный TLS и HTTP 200 на обоих выходах перед сбором. [Отчёт и исходные артефакты](https://github.com/SpeedeMiner/Geoip-ru-server/blob/d4e8ac8e75f06f89130c1ac9c2e8393e0d596996/docs/V41_LIVE_CIDR24_156_224_80_20261117.md).
- [x] Добавлен постконтроль VPN для следующей версии. На живом VPN с подставным collector через 78 секунд подтверждены тот же выход и HTTP 200. Публичный /24 в этом интеграционном тесте не обходился.
- [ ] Новых имён из сертификатов нет, очередь остаётся 0/6. Тайм-ауты не подтверждают блокировку. Остальные /24, DIRECT, релиз и CDN в этом проходе не менялись.

## 2026-11-17 — opt-in режим одного IPv4 /24 для сертификатов

- [x] [В отдельной ветке](https://github.com/SpeedeMiner/Geoip-ru-server/blob/1880c15b270539c175d70fed6ae1f271f975c2df/.github/reachability/CERTIFICATE_CIDR24.md) добавлен один явно заданный IPv4 /24 с TCP/443 через подтверждённый российский VPNObratno после контроля Яндекс DNS и HTTPS. SAN сохраняются как зацепки. Сбор ограничен и не меняет DIRECT.
- [x] [CI](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/44073458885) прошёл: четыре Go-теста и 167 Python-тестов. Проверены покрытие 256 числовых адресов на подставном транспорте, частичный результат и TLS на loopback. Реального замера подсети не было, очередь остаётся 0/6. PR №5, DIRECT, релиз и CDN не менялись.

## 2026-11-17 — повторный поиск целей и проверка исходных входов шести /24

- [x] Через Яндекс DNS и три подтверждённых российских выхода VPNObratno проверены 24 новых публичных имени, включая 11 из CT Link4. Ни одного A внутри шести /24. Единственный исторический PTR и NS/SOA шести обратных зон дали NXDOMAIN во всех трёх прогонах. Контроли HTTPS — 6/6 HTTP 200 с валидным TLS. [Отчёт и восемь артефактов](https://github.com/SpeedeMiner/Geoip-ru-server/blob/809615cdaf900050e39008522120e1b3076dcd96/docs/V41_SERVICE_LEADS_SOURCE_TRACE_20261117.md).
- [x] В закреплённом кандидатном артефакте записи static-override и selected-origin для шести сетей происходят из одного `[STATIC-DIRECT]`. Исходный ipverse и RIPE BGP State в 07:59:59 UTC показывают два AS401650 и четыре AS152606, не исторические origin. Hydra и Loyalsoldier не пересекаются с шестью, v2fly покрывает пять US и один DE.
- [ ] 0/6 актуальных сервисных пар. Для замера нужен новый документированный IPv4 или имя с A внутри нужного /24. Дата 17 декабря — ручной пересмотр, не автоматическое удаление. DIRECT, PR №5, релиз и CDN не менялись.

## 2026-11-17 — получение сертификата по точному IP

- [x] `156.224.80.166:443` проверен через VPNObratno из РФ. На AS8359 и AS6863 получен TCP-тайм-аут до TLS, при этом два контрольных CDN-хоста на каждом выходе дали валидный TLS и HTTP 200. [Отчёт и два архива](https://github.com/SpeedeMiner/Geoip-ru-server/blob/4b13dd5abb7a32a40a706371a8ca4616ed041a34/docs/V41_CERTIFICATE_LEAD_156_224_80_166_20261117.md).
- [ ] Сертификат и новое имя не получены, дополнительного DNS для цели не было. Статус очереди 0/6, нужен иной актуальный публичный сервисный IP или имя в нужном /24. Тайм-аут не считается блокировкой. DIRECT, релиз и CDN не менялись.

## 2026-11-17 — Яндекс DNS измерен через российский VPNObratno

- [x] Яндекс DNS Basic `77.88.8.8` ответил по UDP/53 из трёх подтверждённых российских выходов (AS12714, AS6863, AS50512), а по DoT/853 с проверкой сертификата — из AS50512. Отдельный DoH-прогон дал четыре ошибки DNS. [Пять прогонов и проверенные ZIP](https://github.com/SpeedeMiner/Geoip-ru-server/blob/784bd1abf954640d0d9f46ca90df2e459b4c293a/docs/V41_YANDEX_VPN_DNS_MEASUREMENTS_20261117.md).
- [x] 10/10 точечных IPv4-замеров CDN77 и CDNvideo дали TCP, валидный TLS и HTTP 200. Среди четырёх различных IP — два новых адреса CDNvideo, ранее полученные через Яндекс DNS. IPv6-транспорт не измерялся.
- [ ] В 16 различных DNS-only именах, включая перепроверку исторической привязки `156.224.80.166`, нет актуального A внутри [шести спорных /24](https://github.com/SpeedeMiner/Geoip-ru-server/blob/784bd1abf954640d0d9f46ca90df2e459b4c293a/docs/V41_EXACT_REACHABILITY_ORIGIN_REVIEW_20261117.md). Статус целей 0/6. Следующий шаг — подтвердить точное сервисное имя и адрес, затем измерить через тот же VPNObratno. Подсети не сканировались. PR №5, правила DIRECT, релиз и CDN не менялись.

## 2026-11-17 — VPNObratno принят для точечных измерений

- [x] По решению пользователя подтверждённый выход VPNObratno в РФ достаточен для v41. Ручной домашний выход больше не требуется. В отдельной ветке выполнены два прогона с российским выходом AS12714.
- [x] Четыре закреплённые IPv4 двух контрольных CDN-хостов дали TCP, валидный TLS/SNI и HTTP 200. [Отчёт и артефакты](https://github.com/SpeedeMiner/Geoip-ru-server/blob/c56003cc1588d49daf0e3c8738090bf465bd35e8/docs/V41_VPNOBRATNO_CONTROL_MEASUREMENT_20261117.md). IPv6-транспорт не измерялся.
- [ ] Четыре точки вне шести спорных /24. В [очереди](https://github.com/SpeedeMiner/Geoip-ru-server/blob/c56003cc1588d49daf0e3c8738090bf465bd35e8/docs/V41_EXACT_REACHABILITY_ORIGIN_REVIEW_20261117.md) по-прежнему 0/6 подтверждённых сервисных целей. Сначала подтвердить точные адреса, затем использовать тот же VPNObratno. PR №5, правила DIRECT, релиз и CDN не менялись.

## 2026-11-17 — DNS клиентов и аварийный аудит — контрольная точка

- [x] После реальных тайм-аутов на синтетических данных GitHub Actions выгрузил и перечитал четыре partial TSV. [Прогон](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/44045430458) и [архив](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/44045430458/artifacts/14310724163). Внешние сбои не имитировались сетевыми запросами и не превращались в вывод об RPKI.
- [x] [Xray и sing-box](https://github.com/SpeedeMiner/Geoip-ru-server/blob/912ef3201cea298e9c837466176605ebb0eba2e3/docs/V41_CLIENT_DNS_VALIDATION_20261117.md) прошли по 18 сценариев на опубликованном снимке в изолированной loopback-сети. В восьми DNS-сценариях при одинаковом выборе маршрута Xray передал SOCKS имя, sing-box после `resolve` — IP. Это тест клиентов, не домашний замер доступности.
- [x] Четыре текстовые ленты теперь проходят проверку формата, семейства и уникального числа CIDR до принятия. Прошли 337 локальных тестов и [Linux CI v41](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/44046622931). DAT, SRS, маска и JSON дельты совпали с закреплённым кандидатом. `publish` пропущен.
- [x] [Сверка provenance](https://github.com/SpeedeMiner/Geoip-ru-server/blob/912ef3201cea298e9c837466176605ebb0eba2e3/docs/V41_PROVENANCE_READBACK_20261117.md) различает пересечение источников и вклад. Осталось заполнить точные BGP-origin для корпоративного и регионального слоёв. [Рабочий журнал](https://github.com/SpeedeMiner/Geoip-ru-server/blob/912ef3201cea298e9c837466176605ebb0eba2e3/docs/V41_EXECUTION_JOURNAL.md) и [handoff](https://github.com/SpeedeMiner/Geoip-ru-server/blob/912ef3201cea298e9c837466176605ebb0eba2e3/docs/V41_PROJECT_HANDOFF.md) обновлены. PR №5, домашние замеры, правила DIRECT, релиз и CDN не трогали.

## 2026-11-17 — 20-минутный проход — контрольная точка

- [x] В [журнале PR №56](https://github.com/SpeedeMiner/Geoip-ru-server/blob/21e152c9dd834560c3e7eb8e9c65a8a5d8fff389/docs/V41_EXECUTION_JOURNAL.md) и [handoff](https://github.com/SpeedeMiner/Geoip-ru-server/blob/21e152c9dd834560c3e7eb8e9c65a8a5d8fff389/docs/V41_PROJECT_HANDOFF.md) зафиксированы ранние проверки четырёх обязательных входов (две ленты Antifilter и два CSV IANA). Прошли 334 локальных теста и [Linux CI v41](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/44043544968) на `c811a2c`. `publish` пропущен.
- [x] [Все 18 добавленных CIDR](https://github.com/SpeedeMiner/Geoip-ru-server/blob/21e152c9dd834560c3e7eb8e9c65a8a5d8fff389/docs/V41_ADDITIONS_RIS_RDAP_REVIEW_20261117.md) сверены по RIS/RDAP/RPKI. В RIS найдено 12 точных маршрутов и 2 добавления с покрывающим /24. У четырёх не было анонса в проверенном срезе. Статус REVIEW сохраняется. Шесть временных /24 остаются отдельной очередью и по-прежнему не имеют подтверждённых сервисных IP для измерения.
- [x] DAT, оба SRS, маска исключений и JSON дельты текущего кандидата побайтно совпали с прежним кандидатом. Три публичных файла jsDelivr соответствуют опубликованному release `63b8abf`. Релиз, CDN, PR №5 и маршрутизация не изменены. Справочный перечень критичных сервисов расширен с 16 до 23 доменов без добавления сетевых правил.

## 2026-11-17 — актуальная точка продолжения v41

- [x] Рабочий журнал и открытые задачи находятся в [журнале ветки PR №56](https://github.com/SpeedeMiner/Geoip-ru-server/blob/ddc3512ead912c5e4c4b0e7b7104760cb3d9b65f/docs/V41_EXECUTION_JOURNAL.md) и [handoff](https://github.com/SpeedeMiner/Geoip-ru-server/blob/ddc3512ead912c5e4c4b0e7b7104760cb3d9b65f/docs/V41_PROJECT_HANDOFF.md). Проверенный кандидат `f0b0880` ([CI 44035378467](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/44035378467)) не публиковался. DAT `02908f5e90cabb6cb29fdab664f9ae28b5777ad9f78bbda9fa18c824f07e070d`; baseline release `63b8abf`.
- [x] В [сверке точных префиксов](https://github.com/SpeedeMiner/Geoip-ru-server/blob/ddc3512ead912c5e4c4b0e7b7104760cb3d9b65f/docs/V41_EXACT_REACHABILITY_ORIGIN_REVIEW_20261117.md) все шесть временных /24 видны в RIPE RIS с origin, отличными от исторических overrides (2 × AS401650 и 4 × AS152606, все шесть пар RPKI-valid). Вся новая сеть `31.204.32.0/20` покрыта двумя более специфичными /21 от AS213541. Эти данные не доказывают доступность из РФ. Дата пересмотра шести /24 остаётся 2026-12-17.
- [ ] Сервисные пары для шести /24 не подтверждены (0/6), домашний RU-замер не проводился. [VPN CI](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/44038929934) проверял workflow и тесты, не доступность. PR №5 и №56 остаются черновиками.
- [x] В ветке PR №56 добавлено сохранение частичных строк RPKI и IRR в дополнение к RDAP. Все 329 локальных Python-тестов прошли, принудительный тайм-аут трёх фаз оставил читаемые TSV. [Linux-аудит](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/44040988924) и [сборка v41](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/44040988938) прошли, publish пропущен. [Прежний неуспешный прогон](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43946929969) действительно выгрузил [неполный архив](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43946929969/artifacts/14267290520); принудительный сбой новой версии на runner остаётся непроверенным. Этот коммит журнала меняет только документацию; релиз, CDN и правила DIRECT не изменены.

## 2026-11-12 16:00 +0500 — recovery and branch setup

- Resumed from PR #12 recovery note `docs/V39_PR12_RECOVERY_20261112.md`.
- Verified main `610876b5f5cba4603dbea24c79e4a34ea2aa9792`; release `767031f305b2c26743b71cdd20a66f3575826dd2`.
- PR #12 remains Draft head `a1ef83bba5b4554caa66200498863850033a74c0`. Other open PR #5 remains owned by another agent and is **off-limits**.
- Experimental v40 branch `feature/geoip-direct-rukzby-v40-postrelease-audit` head `a80a48ad37b2490a91f8def2ef4614f7d7e221a1`; not production and not yet CI-validated.
- Confirmed v39 PR #12 candidate workflow #16 `43198572988` SUCCESS, archive artifact ID `13934486909`, GeoIP SHA-256 `b2cb548e01668eaddb85f90db19b5aa1a4af0fcaa0970f9427ba11d8f4e77d30`, RU 164,244 CIDRs. The separate v37 prefix-audit workflow remained FAILURE due to 57 priority rows vs expected 56; never change the constant blindly.

## 2026-11-12 16:10 +0500 — integrated v41 candidate staging

- Created `feature/geoip-direct-rukzby-v41-integration` directly from PR #12 head: all nine PR #12 changes are preserved as ancestry. PR #12 itself was not edited.
- Imported v40 class-aware builder/parser/validator/test sources under **v41-specific paths**; kept the original v39 patched sources and tests unchanged.
- Constructed versioned v41 corporate registry from corrected v39 company ASN entries plus seven additional v40 reviewed ASNs (AS43399, AS15632, AS59840, AS41551, AS201012, AS197482, AS49675) with exact two-class policy mapping; 49 total unique rows. AS209030 was already in corrected v39.
- Integrated v39 service protection and exact RIR-RU selected origin collection into the v41 overlay without using a background BGP connection; the complete origin list comes from the already-pinned ipverse archive in CI.
- Merged with v40 exact-vs-resolver block source layers and PRIVATE precedence; corrected exact-vs-resolver union validation to compare normalized address space rather than literal CIDR row sets.
- v41 workflow now generates `geoip_RU_v41_rir_ru_and_company_origin_prefixes.txt` via the preserved v39 extractor and adds that input to the v41 candidate builder/independent validator; service source inputs are also supplied independently.
- Added `.github/scripts/test_v41_policy_integration.py` for CORE, SHARED, RIR-RU, verified service, IPv6 and pinned-baseline precedence.
- Important: there is a **deliberate** v39/v40 policy conflict resolution: RIR-RU selected origins receive resolver-only protection, not unconditional protection from exact/legacy hard blocked addresses. The standalone corrected v39 code remains in this branch for audit.
- Disabled v41 schedule/push triggers; candidate and manual only. Main, release, tags and existing GitHub Release are unchanged.

## Next checkpoints

1. Open Draft PR for v41, run GitHub Actions candidate, investigate syntax/tests/build failures without touching other branches.
2. Independently check ZIP hashes, manifest, CIDR totals, policy invariants, source-role provenance and actual impact against published v39 and PR #12.
3. Fix any errors on the v41 branch only; document each run and code commit in this journal.
4. Review any remaining false company ASN attribution, especially affiliate-related rows, before considering release.
5. Keep the separate v37 57-versus-56 audit gate explicit; do not weaken or silently ignore it.
6. Only after successful candidate review consider a separate merge/release authorization, including disabling the legacy v39 production workflow before enabling v41 automatic publishing.

## 2026-11-12 — post-interruption resolver provenance recovery, verified v41

- Resumed at Draft PR #13 after successful but misleading candidate run `43210464555` (commit `67646e094e42ae25ee7a2e133398cc807a242b19`). Its manifest had `current_resolver_only_unique=0`, because historical resolver-source snapshots had not been passed to the new preparer.
- Reused SHA-256-verified published v38 release assets:
  - `antifilter-ip.lst` SHA-256 `c9c0656d0188f4afa740d71332b618d42b5606ab27e7561790f47b588781d1cb`;
  - `antifilter-ipresolve.lst` SHA-256 `8d8d11605a299da96006df6303a90b08b4ae25d35c1d1a199708cb83f84cdf44`;
  - `antifilter-subnet.lst` SHA-256 `2554552742bc0da516a321db66b36fa6cece28c4b3c64b66ff6d12320b33bdb6`.
- v38 approved blocked baseline remains pinned to `df909b12b985b23080075821cedc5e2f73b7b1f89abcd9950293b400ce1e4a5d`. Historic resolver entries in this exact baseline are resolver-only **only** when identified as a host IP in old ipresolve, absent from old exact ip.lst and outside old bounded subnet. Ambiguous/unclassified prefixes remain hard. Historical ipresolve can also contain non-host CIDRs (e.g. `185.104.45.0/26`); these were explicitly excluded from host-only reclassification rather than weakening blocks.
- New GitHub Actions build `43213336816` on commit `c787ac889e2a7b5f97d3b6fef158f82b21c7f9da`: **SUCCESS**, 88 Python unit tests passed; Go v37 builder, v41 overlay, independent v41 validation, protobuf read-back, candidate artifact upload all passed; publication steps skipped. ZIP artifact ID `13941149919`.
- Downloaded verified ZIP `geoip-v41-pr13-v38-provenance-fixed-20261112.zip` SHA-256 `c400bc19ae6d232c3bd4b1ac79c6754ca6473255c83e795ab2721bda4e0f7b23`. Result `geoip_RU.dat` 2,097,353 bytes SHA-256 `7d55f2bc59919052222850abd1fd1bba79e4a73d049799367122596a796ab2db`.
- Manifest: approved blocked union 199,640 CIDRs; historical/current hard/exact 57,694 CIDRs; effective resolver-only 80,755 CIDRs; blocked after policy 125,707 CIDRs; direct block exemptions 2,205 IPv4 addresses (CORE 28, SHARED resolver overlap 411; these class measurements overlap other sources and must not simply be added). `ipsum_auto_carved=false`; `PRIVATE` precedence preserved.
- Final v41 RU: 191,353 CIDRs, IPv4 address space **53,100,808**, IPv6 address space **1,205,559,204,658,091,812,677,163,847,516,160**. SHA-256 and categories independently confirmed inside downloaded ZIP.
- Exact protobuf address-space diff against corrected v39 PR #12 run `43198572988`: v41 adds **0** new IPv4 addresses and removes **5,125**; adds/removes **0** IPv6 addresses; `PRIVATE` IPv4/IPv6 identical. All 5,125 removed IPv4 addresses are present in v41 effective blocked-set; no unaccounted subtraction.
- Confirmed current PR #13 still Draft; production `main` SHA `610876b5f5cba4603dbea24c79e4a34ea2aa9792`, `release` SHA `767031f305b2c26743b71cdd20a66f3575826dd2`. PR #5 untouched.
- Separate inherited `Prefix audit validation (v37)` still fails with the previously known 57 vs 56 priority list mismatch. Its upstream quality-report source correction from PR #12 is preserved. This audit was not weakened or silently bypassed; it remains a blocker for full PR green status.
- Before release: review what changed between 56 and 57 priority audit prefixes and independently validate corporate ownership for all 49 policy ASN rows. No production merge or release authorized by this checkpoint.

## 2026-11-12 — post-review reconciliation (v41 branch only)

- Applied `3b953bb`: potential blocked-source impact now uses exact IP intervals and a union of applicable exemptions; avoids double counting when CORE/service/SHARED/RIR-RU masks overlap or already lie in effective blocks.
- Applied `d23846f`: fixed candidate workflow path filters, deduplicated the builder path, and corrected the linked source cross-check document.
- Applied `d5890a3`: synced root company ASN registry with 49 policy entries.
- Prior 88-unit-test result and 57-vs-56 gate failure described earlier refer to historical CI only. Later local review reports 92 unit tests and fixed audit scripts; new branch CI confirmation is required before treating these as GitHub-verified results.
- PR #5 and its branch are off-limits; #6–#9 stay Draft. No production/release/main changes.

## 2026-11-12 — seven-ASN v41 registry expansion (branch-only)

- Reviewed uploaded `Geoip-ru-server-v41-fixed_asn.zip`. Its local archive test suite completed `Ran 92 tests ... OK`; this is local validation, not a new GitHub Actions build confirmation.
- Imported seven origin ASNs from the supplied candidate: CORE `AS200107` (Kaspersky), `AS205638` and `AS12686` (T-Bank), `AS35022` (Gazprombank), `AS47724` (HeadHunter); SHARED `AS197068` and `AS51115` (Qrator/HLL). Qrator ASN evidence link now points to the exact ASN page, not an AS-set.
- Commits: `ff58a6a` (canonical registry), `3d8d912` (two-class ASN policy), `fbb3f19` (root registry). Did not replace the complete repository tree or older v41 workflow with the ZIP.
- Readback from GitHub verifies identical 56 ASN identifiers and rows in canonical/root registry, 56 unique policy identifiers, no duplicates, class counts CORE_CORPORATE=31 and SHARED_INFRA=25.
- Preserve the critical precedence: newly listed Qrator origins are SHARED_INFRA and remain subject to exact and subnet blocks; all five newly listed corporate origins receive CORE exemptions except PRIVATE.
- Previous 49-row v41 baseline contained 26 CORE and 23 SHARED policy rows. The seven additions bring these to 31 and 25 respectively.
- Remaining gate: perform new GitHub Actions candidate build and independently compare output manifests and binary address-space deltas. Earlier artifact hashes and CIDR counts are historical and **must not** be claimed for the expanded registry.
- No main/release/tag/production modifications; PR #5 and its feature branch untouched.

## 2026-11-12 — v41 stalled candidate, interval provenance performance fix

- Run `43223249218`, job `131199970352`, branch head `0b4bf7dd5be3764a04a1c8df8d73523a1c78b050`, remained `in_progress` on step 6, **Build unified DIRECT GeoIP RU+BY+KZ v37 with curated blocked-destination exclusions** since `2026-11-12T13:02:55Z`. At `13:18Z` the same step had run over 15 minutes, versus 4 minutes 6 seconds for the comparable successfully completed v39 run `43223248990` (`13:05:12Z`–`13:09:18Z`). The live job log API returned `BlobNotFound`, so a precise internal subcommand was not directly observable.
- Found deterministic pathological work introduced by earlier v41 provenance report correction: `normalize_interval_union(...)` of all protection masks and `subtract(...)` of blocked masks were repeated **inside** the per-prefix blocked provenance loop. That is avoidable repeated global work for roughly 100k+ source rows.
- Commit `0b05a4a7e161f59077de1fcea1195428b08f1324` precomputes (per family and hard-versus-resolver source class) the final eligible incremental impact interval masks once and uses `intersect_one_range` per row, preserving the same set difference and the existing CORE, SHARED, RIR-RU, verified-service, PRIVATE and blocked-source precedence.
- A new CI run is required to verify both runtime and exact output/manifest results. The commit intentionally supersedes the suspected stalled run via workflow concurrency `cancel-in-progress`.
- No edits to PR #5, main, release, tags, or production. PR #13 remains candidate-only.

## 2026-11-12 — successful v41 56-ASN CI and independent protobuf comparison

- GitHub Actions commit `95b9a05cfb475d7487b01c7a9915d9c5117609c3`: v41 run `43226318672` SUCCESS (artifact `13948845244`); v39 compatibility `43226318922` SUCCESS; v37 prefix audit `43226318733` SUCCESS; v41 lint `43226318862` SUCCESS.
- Downloaded v41 ZIP SHA256 `0fc92ca92e16fc032d219103732ea5d352813dfb7834343582676d5d9cd6af7d`. `geoip_RU.dat` SHA256 `383a70295024d696762839497fb4cb1cc5066443b3ea6cafa3ba84208c0a2536` (2,097,071 bytes) matches its manifest and sha256sum sidecar.
- Protobuf parsed independently; resulting categories are only `RU` (191,326 CIDRs) and `PRIVATE` (151 CIDRs). RU IPv4=53,105,937 addresses; RU IPv6=1,205,559,208,313,203,470,418,269,242,916,864 addresses. PRIVATE coverage identical to historical 49-ASN v41 candidate.
- Approved historical exact/legacy and resolver-only blocked source SHA256 inputs are unchanged, `ipsum_auto_carved=false`. Effective blocked CIDRs=125,703 (prior=125,707), exempted direct IPv4 addresses=2,209 (prior=2,205), CORE exempted direct IPv4=32 (prior=28).
- Exact parsed `RU` address-space comparison with historical v41 candidate artifact `13941149919`: IPv4 +5,385 addresses, -256 addresses, net +5,129. The removed /24 is `187.78.205.0/24`, present in old v37 base but absent from new v37 base, and not in effective blocked mask. IPv6 added=24,206,850,591,189,801,365,405,696 addresses, removed=20,551,738,933,448,695,970,004,992 addresses; net +3,655,111,657,741,105,395,400,704. These deltas **must not** be attributed wholly to the seven ASN changes because v37 base SHA changed `04d7e773...` to `37b121a5...`.
- Seven added ASN identities have exact-origin prefixes in pinned CI BGP observation data: CORE `AS200107` (31), `AS205638` (5), `AS12686` (4), `AS35022` (2), `AS47724` (2); SHARED `AS197068` (15), `AS51115` (8). These counts are raw per-ASN origin-containing selected prefix lines, not necessarily disjoint address-space contributions.
- The v41 provenance performance regression is resolved sufficiently for the end-to-end CI to complete. No production publication was performed; this remains a reviewed Draft candidate. Remaining decision: confirm readiness, compare against a controlled identical base if attribution of every changed IP to ASN policy is required, and obtain explicit merge/release authorization.

## 2026-11-12 — explicit production release authorization and workflow cutover

- User explicitly authorized final v41 release. Current Draft PR #13 remained mergeable/clean at `ed921918` with four successful checks (v41 build `43227878821`, v39 compatibility `43227879095`, v37 audit `43227878957`, v41 source lint `43227878607`).
- v39 production workflow still carried `schedule`, `push(main)` and main-branch release/release-branch publishing, while v41 lacked production triggers; merging without transition would permit competing publishers to force-push `release`.
- Commit `4d26c552` retired v39 schedule/push and explicitly disabled all three v39 main-branch publish/URL steps; kept the old workflow for manual/PR candidate compatibility checks.
- Commit `33cb6a31` enabled v41 schedule at 03:45 UTC daily and push(main); preserved v41 GitHub Release `latest-geoip-client-v41`, force-push of the artifact-only `release` branch, and explicit jsDelivr purges.
- Both workflow modifications are in the SAME v41 PR to avoid a transient dual-publisher state after merging.
- Release gate: validate lint/CI after these trigger changes, transition PR #13 from Draft, merge using expected head SHA, then independently verify v41 GitHub Release and `release` branch hashes. If CI or release fails, record the failure rather than claiming publication.
- Excluded from all operations: PR #5 and `feature/reachability-full-ru-kz-by`; PRs #6–#9 kept Draft.

## 2026-11-13 — publication and source integrity

See [v41 release hardening](V41_RELEASE_HARDENING.md). Routing-policy changes are evaluated separately. PR #5 and its head branch are out of scope.

## 2026-11-13 — v41.1 routing policy candidate

- Branch `policy/v41-1-service-and-regional` is stacked on Draft PR #17 so routing policy and source/publication hardening can be reviewed separately.
- Hard exemptions are restricted to CORE and explicitly sourced /32 or /128 service entries. A service CIDR, an Escapingworm operator whitelist entry, or a W1ZARDZ BY/KZ overlap is resolver-only. The release policy gate reconstructs allowed hard host entries separately from the overlay's mask logic.
- The exact BGP origin sidecar now consumes both RU and BY/KZ RIR ASN registries, with separate hashes. No entry or hard-block exception was added to the curated 56-ASN company registry.
- The active ip.lst classification, historical v38 baseline, review-only /24 behavior, PRIVATE precedence and public asset filenames remain unchanged. No main, release, tags, PR #5 or production changes.
- Same-input replay against the published DAT `576bf92bf1dc57a85ff5292e9dd2519f1400aabc160503721b1ae0a4431fb1eb` produced `b257cc32bb0504de1e0d9bad645b66c759e2572d7a0911897efea330859a32d8`. Independent address-space comparison: IPv4 +696 / −91 (net +605), IPv6 and PRIVATE unchanged. Existing publication envelope permits the delta. The replay admitted 333 active origins from 387 BY/KZ registry ASNs.

## 2026-11-13 — v41.2 historical host candidate

- Branch `policy/v41-2-legacy-host-reclassification` is stacked on PR #18. The existing build prepares block layers after ASN selection and uses both the regional origin and SHARED masks.
- Keep the pinned v38 approved union intact. Move only eligible regional legacy-only IPv4 /32 to resolver-only, with explicit provenance. Any current prefix covering the host vetoes the move. The rule is disabled when a current feed is missing or has tolerated invalid data.
- The original 213-host review queue used a different snapshot and required prior v34 membership. It is not an expected count for this policy or a claim about unblocking.
- Same-input replay versus PR #18 moved 268 IPv4 /32, with exactly 265 additions to DIRECT and no removals (three already DIRECT). IPv6 and PRIVATE unchanged. 259 of the 265 additions are present in the SHA-256-pinned v34 DAT used by the historical audit. The approved-union sidecar is byte-identical. Candidate DAT SHA-256: `53d235e89a9255709efd61df5c5f3c98f291398e1f94be448ee12ec24c5fadfd`.

## 2026-11-13 — v41.3 versioned publication candidate

- Branch `workflow/v41-3-versioned-publication` is stacked on PR #19. No routing policy, source list, production branch, tag or repository setting is changed by this candidate.
- Move the remaining Python heredocs and the publication/source shell logic to files. The workflow shrinks from 1,511 to 640 lines. Five RIR/IANA routing inputs regenerated from the same snapshots were byte-identical.
- Manual `snapshot_version` supports one-time `v41.N` tags. Daily jobs retain their run ID tags. The GitHub snapshot uses a create-only path, and the rolling compatibility release remains unchanged. Tests against a local bare Git remote verify fast-forward, refusal to overwrite a snapshot, and refusal to publish from a stale reference.

## 2026-11-13 — reviewed operator suballocations

- Scope is three exact IPv4 prefixes only, without adding ASN-wide rules, modifying any protection masks, or importing a mutable geofeed into the nightly build. IPv6 evidence stays out of scope.
- `153.52.151.0/24` (RU, AS402931), `179.253.86.0/24` (BY, AS207957), and `178.92.244.0/23` (KZ, AS215294) match the exact country/prefix in operator geofeed and the corresponding RDAP object. RIPE RIS observed exact announcements, and RPKI was valid for each checked pair. Registration and route visibility are not substitutes for application reachability.
- One IPv4 address in each prefix answered all three ICMP requests from each of two probes in RU, BY, and KZ. Globalping measurements: `2EVq8atmcFyKnJyqx00021UoQ` (RU prefix), `2t8jczQpf6IUEvF3v00021UoQ` (BY prefix), and `2YyCXde8KJbrFXlSs00021UoQ` (KZ prefix). No inference is made about all hosts or ports in the three prefixes.
- Expected snapshot delta relative to the published PR #21 DAT: exactly +1,024 IPv4 addresses, no removals, IPv6/PRIVATE and effective hard/resolver policy unchanged. No production publication is part of this candidate.

| Prefix | Operator geofeed | Registration | Current exact route |
|---|---|---|---|
| `153.52.151.0/24` | [ipbnb](https://api.ipbnb.com/geofeed/153.52.151.0.24.txt) | [RDAP](https://rdap.db.ripe.net/ip/153.52.151.0/24) | [RIS](https://stat.ripe.net/data/prefix-overview/data.json?resource=153.52.151.0/24) |
| `179.253.86.0/24` | [SERV.HOST](https://status.serv.host/geofeed/subnet.csv) | [RDAP](https://rdap.db.ripe.net/ip/179.253.86.0/24) | [RIS](https://stat.ripe.net/data/prefix-overview/data.json?resource=179.253.86.0/24) |
| `178.92.244.0/23` | [Lumina](https://luminabroadband.com/geofeed.txt) | [RDAP](https://rdap.db.ripe.net/ip/178.92.244.0/23) | [RIS](https://stat.ripe.net/data/prefix-overview/data.json?resource=178.92.244.0/23) |

## 2026-11-13 — Telegram DIRECT overlap

- The official Telegram [CIDR feed](https://core.telegram.org/resources/cidr.txt) contained nine IPv4 and five IPv6 ranges. The published PR #21 DAT and the initial PR #22 candidate intersected it at exactly `185.76.151.1/32`; the v37 base did not intersect it.
- The pinned HXEHEX `ipwhitelist.txt` emitted this exact host as `hxehex-mobile-hosts`, which qualified as a literal service exception and cut a hole in the already-hard `185.76.151.0/24` range. Filter conflicting HXEHEX entries before classifying service exceptions. Do not modify the upstream snapshot or the separate legacy Telegram ranges.
- All official Telegram IPv4/IPv6 ranges are non-exempt in v41 even if another DIRECT source, a corporate prefix, or a literal service rule overlaps. The strict DAT validator checks the full pinned feed, build CI compares it against the official endpoint, and the publish job checks the downloaded candidate again before pushing refs.
- Expected net change relative to the published PR #21 DAT is the same three operator prefixes (+1,024 IPv4) and removal of exactly `185.76.151.1/32`; IPv6 and PRIVATE are unchanged.

## 2026-11-13 — Moscow IPv6 PoP candidate

- Only `2001:ad0:2000:1::/64` is proposed. The [operator geofeed](https://gf.data.ee/geofeed.csv) lists this exact Moscow subnet. [RDAP](https://rdap.db.ripe.net/ip/2001:ad0:2000:1::/64) identifies the covering Moscow M9 /48; [RIPE RIS](https://stat.ripe.net/data/prefix-overview/data.json?resource=2001:ad0:2000:1::/64) sees the covering /32 from AS3327, with valid RPKI for that /32. Neither parent prefix is added.
- [IPv6 ICMP measurement](https://globalping.io/measurements/2dlik7BCSNn749dkN00021UpP) for `2001:ad0:2000:1::1` received 13/15 responses, including responses from all five RU/BY/KZ probes. This tests one address and does not establish reachability for every host or application.
- HATS /48 entries `2a13:a5c7:25bf::/48` (RU), `2a13:a5c7:2524::/48` (BY), and `2a13:a5c7:257d::/48` (KZ) were confirmed in the [operator geofeed](https://hatsnet.io/geofeed/all.csv?s=ripe_asn) and in exact RDAP objects. RIS saw only AS203314 covering /41s, valid in RPKI for the covering prefixes. None of the three sampled `::1` addresses replied to ICMP from the five probes. This does not establish that the subnets are unreachable. They are not included in this change.
- The reviewed list still gives no block exception or ASN-wide permission. The exact PoP /64 was disjoint from published DIRECT, PRIVATE, approved hard/resolver layers, and the official Telegram list. Expected fixed-input delta is one IPv6 /64 only; no IPv4 removals or additions.

## 2026-11-13 — Regional DIRECT and explicit IP evidence

- Base main `54ac34b`. Separate policy branch supersedes the per-host workaround in drafts #24 and #25 without editing either PR. PR #5, main and release are out of scope.
- Treat both Antifilter DNS feeds and v38 unverified history as advisory. Retain their pinned inputs, approved union and provenance. A current bounded subnet or a separately reviewed direct registry IP record remains hard, including inside CORE, SHARED and literal service hosts. Telegram and PRIVATE precedence remain intact.
- Classify REG.RU AS197695 as SHARED_INFRA without admitting it via the company allowlist alone. Verify exact address-space equality for the selected-origin set before/after. Check both protocol families, eight reviewed hosts, and all removals against hard evidence on fixed inputs.

## 2026-11-13 — Current mirror cross-check for PR #26

- The public official checker did not return records. Do not interpret this as an empty registry or as a check of live reachability. The dated [public registry mirror snapshot](https://registry.ctreserve.de/api/v3/snapshot/) has SHA-256 `893ca06a64e6440e5c627beb7dbb0fb812da7c0a1a3b8ce240ce72b6e468afa3` (uncompressed JSON, Last-Modified 09:18:42 UTC). Its [flat IP endpoint](https://registry.ctreserve.de/api/v3/ips/) was used only as a consistency check (SHA-256 `eae983fe3a34fcd24351a1859ab0bde181782c100fbfd57995102c5e5d12264c`). This is mirror evidence, not a signed operator export or individual live verification against the official checker.
- Compared all 7,990 proposed new IPv4 addresses. The snapshot matched 4,158 with some record, of which 742 have direct IP-only records and 3,531 have a domain/URL record, including 115 in both groups. All 742 are exact /32 entries with empty domains/URLs, status 1 in the current mirror, and decision metadata (746 address-to-record associations, 41 unique record IDs). The flat feed contains all 742 exact addresses. Individual mirror record endpoints did not provide usable detail for the old IDs, so the pinned snapshot is the evidence source.
- Entered only those exact reviewed hosts in the existing hard-evidence table. Do not import the entire mirror, treat hostname/URL matches as direct IP records, or widen matches to surrounding networks. The rest of the regional coverage and original inputs are unchanged.
- [Pinned evidence extract](v41-pr26-direct-ip-evidence-20261113.json) for the exact hosts, with mirror record IDs: 309721, 309722, 309723, 312836, 319687, 319689, 322483, 322484, 323962, 324353, 464136, 550080, 745572, 780178, 788862, 795917, 821792, 858296, 862479, 862480, 1639617, 1939194, 1939195, 1940098, 1940107, 2097494, 2238206, 2257807, 2268787, 2296707, 2311636, 2311682, 2311696, 2318151, 2421508, 2478377, 2689066, 2991346, 3085579, 3591646, 3787019.
- Fixed-input replay expectation versus the published snapshot: IPv4 +7,248 / -6, IPv6 and PRIVATE unchanged. Tilda, REG.RU and the eight earlier service controls should remain in DIRECT. PR #26 stays Draft, and no merge or release is part of this check.

## 2026-11-13 — Separate exact regional admission correction

- Draft PR #26 follow-up. The 99 blocked Leaseweb-origin hosts are in one BY-delegated /22 whose six more-specific DE assignments cover every address. Two RU-delegated prefixes announced by the same origin have exact DE assignment records. See [regional admission policy and RIPE evidence](GEOIP_RU_V41_POLICY.md#reviewed-regional-admission-conflicts).
- Scope is `185.49.68.0/22`, `185.17.120.0/22` and `195.54.32.0/23` only. Keep all RIR/source inputs, the 742 reviewed IP-only exclusions, the effective RKN mask, IPv6, PRIVATE and other AS28753 coverage unchanged.
- Fixed-input replay must show exactly 2,461 IPv4 removed relative to prior PR #26 candidate and IPv4 +7,223 / -2,442 versus the published snapshot, with both IPv6 and PRIVATE unchanged. No merge or production publication in this step.

## 2026-11-13 — Broader regional admission review

- Screened 19,402 observed IPv4 routes overlapping the regional inventory. The most-specific route screen found 993 prefix/region pairs covering 573,952 addresses in the previous draft. Foreign origin metadata alone is insufficient. HOSTKEY AS50867 is a counterexample with RU records and Moscow infrastructure. No bulk or ASN-wide exclusion is applied.
- Checked the first 35 candidates against RIPE RDAP and RIS. Promote only the three independently corroborated exact assignments inside `145.249.0.0/16` in this batch. SY and DE records and matching current origins are documented in the policy. Remaining candidates are unchanged.
- Previous draft head `5b15ef8`. Expected exact delta to its DAT: IPv4 -26,624 only. Preserve 38,912 other addresses in the /16, including all 32,768 addresses in the Kazakhstan /17, plus IPv6, PRIVATE, RIR inventory and all block policy masks. No merge or publication.

## 2026-11-13 — Exact US assignments in RU and KZ parent allocations

- Draft PR #26 head before this check: `3319960`. RIPE RDAP child records and the RIS 2026-11-13T08:00Z view support only `31.204.8.0/21` (RU parent, US-FIXED, AS209372) and `109.238.168.0/21` (KZ parent, IPXO with two covering US /22 assignments, AS26548) in this batch. Both exact routes were seen by 319/319 RIS peers without more-specifics.
- Preserve `31.204.2.0/24` (RU assignment, same origin), `109.238.160.0/21` and all other IPv4 coverage outside the two /21s. Leave `212.124.96.0/19` unchanged: a DE value on the allocation and a CH origin do not settle the relationship to the RU registrant MnogoByte at child level.
- Fixed-input replay expectation: IPv4 -4,096 only relative to the previous draft, and IPv4 +7,223 / -33,162 versus the published DAT. No changes to IPv6, PRIVATE, RIR inventory or hard/resolver/effective block masks. No merge or publication.

## 2026-11-13 — PR #26 release checkpoint

- Exact new regional admission exclusions: `31.204.16.0/21` (US), `31.204.32.0/20` and `31.204.56.0/21` (AU), and `212.124.106.0/24` (US). See the policy for child routes, RDAP and operator geofeed evidence. Keep `31.204.28.0/22`, the rest of MnogoByte and the unresolved review queue unchanged.
- Exact delta to previous candidate `4c0c913`: IPv4 -8,448 only. Prior rolling DAT comparison: +7,223 / -41,610 IPv4, IPv6 and PRIVATE unchanged. The input inventory and block masks must match the previous candidate byte-for-byte.
- Align the rolling release description with the effective v41 policy. Release via the existing main-push workflow only after matching the fixed-input and PR builds. Verify the production workflow, rolling DAT, immutable snapshot and release-branch DAT after publication. Do not touch PR #5.

## 2026-11-13 — Follow-up on exact operator routes and workflow edge cases

- Starting point is the published PR #26 snapshot. Keep the same four reviewed operator rows and give only those exact CIDRs resolver-only protection. The overlay validator and independent hard/publication gate verify the input digest and coverage after PRIVATE, explicit hard blocks and reviewed regional exclusions.
- Geography-only source rows retain existing eligibility. Do not add v2fly/Loyalsoldier to the exemption mask, change operator rows or touch PR #5.
- Normalize upstream BGP and legacy RIR IPv6 host bits at the supplied prefix length and count normalizations. Keep project-maintained policy TSVs strict.
- Pass the BY/KZ ASN inventory into the compatibility-only v39 mask. Fix release-ref working-directory handling and fail before invoking gh when any snapshot asset is missing, unreadable or empty.

## 2026-11-13 — Geography-only cohort follow-up

- The pinned v2fly/Loyalsoldier, v41 block and regional RIR/BGP inputs identify 961 IPv4 and zero IPv6 candidates. The pinned ipverse archive assigns 297 addresses to the two Cloudflare origins AS13335/AS209242, while 63 have no covering route in that archive. No ASN-wide exception or geolocation-source protection is granted.
- In the dated public registry mirror, 649 addresses have an active domain/URL record, 310 have no active match and four have an exact active IP-only record. Two of the latter also match domain/URL records. Keep only the four exact IP tokens as reviewed hard evidence, without inferring that the mirror is official or signed. See [the evidence extract](v41-geo-only-exact-ip-evidence-20261113.json).
- Restore only the 110 addresses previously lost to advisory DNS evidence inside six exact independently reviewed operator ranges. The rest of each of these ranges was already in DIRECT. See [the routing policy evidence](GEOIP_RU_V41_POLICY.md#reviewed-operator-prefixes-and-geography-only-inputs). Do not extend by ASN, BGP aggregate, tenant, geolocation feed, or registry absence alone.
- Hold HOSTKEY and TIME-HOST and other mixed-location rows for individual checks. In particular IHOR geolocated-RU origin space contains assignments in both RU and FI. Leave all unresolved rows unchanged. No PR #5 work or production publication.

## 2026-11-14 — Second exact geography-only review

- Start from PR #27 head `e17846c`. Selected 22 exact RU assignments across HOSTKEY (2), FIRSTSERVER (10), IHOR/PSERVERS (6), TIME-HOST (4). This keeps the existing 32-row operator cap (10 + 22). Prioritize exact corroboration and greater observed DIRECT recovery. See [pinned evidence](v41-geo-only-operator-evidence-20261114.json). No BGP aggregate or ASN-wide exception.
- Expected incremental DIRECT delta: +85 IPv4 (2 + 42 + 17 + 24), no removals, zero IPv6/PRIVATE change. The hard masks and registry evidence remain unchanged. Verify `185.174.138.82/32` stays hard and both RU/FI-conflicting IHOR candidate prefixes remain unapproved.
- Unmodified from the remaining cohort: 762 IPv4. Draft only. No changes to main, the release, or PR #5.

## 2026-11-14 — Bounded expansion of the reviewed operator table

- Start from PR #27 head `84c48c7`. Raise the row ceiling from 32 to 64, test both sides of the boundary, and retain the minimum /23 IPv4 and /64 IPv6 prefix lengths, overlap checks, exact manual scope and both publication validators.
- Add six exact RU FIRSTSERVER assignments and ten IHOR/PSERVERS assignments with matching registry-linked geofeeds and complete same-origin RIS coverage. The three IHOR /23 rows without an exact route are covered by their paired /24 announcements. Expected delta is +19 IPv4 (6 FIRSTSERVER, 13 IHOR), no removals and no changes to IPv6, PRIVATE, hard or regional-exclusion masks. Evidence is [pinned here](v41-geo-only-operator-followup-20261114.json).
- Keep mixed RU/FI IHOR entries unchanged. Also leave `62.3.58.0/24` unchanged: its exact RIS announcement and RU assignment description do not make the RDAP assignment covering .0 through .254 an exact /24. PR #27 stays draft. No production or PR #5 change.

## 2026-11-14 — Fourth exact geography-only review (RU/KZ)

- Start from PR #27 head `95c0360` and recover the 743-address remainder from the pinned v2fly/Loyalsoldier files, previous CI artifact and pinned ipverse archive. Reproduce the previous DAT and effective block sidecar from fixed inputs.
- [Evidence](v41-geo-only-operator-rukz-20261114.json) records 30 verified /24s. Use the 16 existing table slots for the highest observed cohort recovery, breaking ties by numeric network address. Keep the 64-row cap. Approve 15 RU and one KZ exact assignments, with expected DIRECT delta +59 IPv4, no removals, no changes to IPv6, PRIVATE, or higher-priority masks.
- Keep the other 14 verified /24s (14 cohort IPv4 addresses) unmodified. The CY-assigned `194.67.193.0/24` alone accounts for 44 unchanged addresses. Total unresolved or deferred: 684 IPv4. Draft only. No production, release or PR #5 changes.

## 2026-11-14 — Finish PR #27 for production

- Start from verified draft head `1a50c3e` and admit all 14 deferred exact /24s listed in [the evidence file](v41-geo-only-operator-rukz-20261114.json). Raise the reviewed-row ceiling from 64 to 80 for 78 entries. The existing regression tests exercise the accepted and rejected boundaries. No changes to the prefix admission criteria or hard/PRIVATE/Telegram precedence.
- Expected policy-only delta for this final batch: +14 IPv4, no removals and no IPv6 or PRIVATE changes on the same inputs. Keep the other 670 unresolved addresses in the original cohort unchanged. Compare production separately because its upstream BGP and Antifilter sources move.
- Publish through the existing v41 workflow after PR checks. Verify the rolling asset, versioned snapshot, release branch, and their checksums. PR #5 is outside scope.

## 2026-11-14 — Post-release exact operator check

- Start from published DAT `66f3dbe3bcebad386207d026b5e7ebbd7113a1d45d86420996d7dc0742112166`. All 670 addresses left in the original cohort still intersect effective resolver-only policy outside DIRECT.
- [Evidence](v41-geo-only-operator-post-release-20261114.json) verifies eight exact RU prefixes. Admit only `31.76.6.0/24` and `45.90.216.0/23` using the last two slots. The FIRSTSERVER /23 is exactly covered by two AS205090 /24 announcements. Expected fixed-input delta is +4 IPv4 only. No change to hard precedence or the 80-row limit.
- Six other exact prefixes remain documented but unadmitted. Leave the broader FIRSTSERVER /24 over a confirmed /25 and the Dutch 3NT neighbor of the existing KZ exception unchanged. No ASN-wide admission. Draft only.

## 2026-11-14 — Complete the confirmed post-release queue

- Start from draft PR #28 head `80f4810`. Recheck exact RIPE assignments, linked operator geofeeds and RIS for the [six remaining verified routes](v41-geo-only-operator-deferred-confirmation-20261114.json).
- Raise the bounded manual table from 80 to 96 for 86 entries. No changes to exact-prefix eligibility or higher-priority exclusions. Expected fixed-input effect is +6 IPv4 against the prior draft and +10 against the published v41. The other 660 addresses in the original cohort remain unchanged. No publication or PR #5 changes.

## 2026-11-14 — Exact Gcore and EDIS assignment review

- Start from draft PR #28 head `c9cf96f` and the previous fixed-input CI artifact. Add 6 exact assignments from [the evidence](v41-geo-only-operator-gcore-edis-20261114.json) under the existing 96-row bound. Expected policy-only DIRECT delta +11 IPv4 versus the prior candidate, +21 versus published v41.
- Do not extend Gcore protection to the surrounding /22: exact registry objects and geofeed list LU and US for the other /24s, despite the same current RIS origin. Defer RU-labelled ranges lacking a usable registry-linked geofeed or exact routing evidence. No publication or PR #5 changes.

## 2026-11-14 — Exact assignments in mixed-origin networks

- Start from draft PR #28 head `0bdc266`. Verify 7 exact RU assignments in the 649-address remaining DNS-only cohort by RIPE, registry-linked operator geofeeds and RIS. See [prefix evidence and hold decisions](v41-geo-only-operator-mixed-origin-20261114.json).
- The candidate now holds 99 rows under a 112-row bound. Expected +12 IPv4 versus the previous candidate, +33 versus the released DAT on fixed inputs. Hard exclusions, IPv6, PRIVATE and all address space outside the target cohort stay unchanged.
- Keep the foreign Xorek and Nuxt siblings, Finnish PSERVERS assignment and the FIRSTSERVER origin disagreement unmodified. No production or PR #5 changes.

## 2026-11-14 — Registry re-screen on fixed inputs

- Start from draft PR #28 head `5ae27ee`. Reproduced both previous PR artifacts byte-for-byte (DAT and effective mask). The seven preceding assignments restore exactly 12 IPv4 addresses. The draft was +33 IPv4 versus the published DAT.
- The [re-screen](v41-geo-only-operator-ripe-rescreen-20261114.json) recalculates 638 IPv4 and zero IPv6 outside DIRECT in the resolver-only geography cohort. That is one more than the earlier journal tally, not an extra DIRECT delta. Screened all 121 IPv4 /24 buckets via RIPE RDAP and retried errors against the IANA-bootstrap registries.
- Add four exact prefixes supported by RIPE RDAP, registry-linked geofeeds and exact same-origin RIS. The existing 112-row cap is unchanged (103 rows). On identical inputs, only four /32s return to DIRECT, with zero removals and no changes to IPv6, PRIVATE, hard or raw resolver inputs. This is +37 IPv4 versus published v41. Candidate DAT SHA-256 `8311e0072cd51e5ec68cf61541bdd6848ca2d208cf615ebb56b16ba3f712ff76`.
- Next, check the ARIN Kazakhstan reassignments and exact Russian ARIN records found by the fallback separately. Keep registry-only assignments, inaccessible geofeeds and the unresolved FIRSTSERVER origin disagreement unchanged. Draft only. No production, release or PR #5 changes.

## 2026-11-14 — Exact ARIN Kazakhstan reassignments

- Start from draft PR #28 head `eca7b16`. [CI](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43568893438) passed and publication was skipped. The DAT and effective mask matched the local fixed-input replay byte-for-byte.
- [ARIN, 3NT geofeed, RIS and pinned BGP evidence](v41-geo-only-operator-arin-kz-20261114.json) corroborates eight exact AS58061 /24s in Kazakhstan. Admit just these rows, bringing the table to 111 out of 112 without raising the cap. Keep the corroborated /22 and RU registry-only records unchanged.
- Verified fixed-input delta: +20 IPv4 versus the previous draft and +57 versus published v41. No removals, IPv6, PRIVATE or hard-mask changes. 614 IPv4 remain outside DIRECT in the recalculated review cohort. DAT SHA-256 `d163e934c89519e3812552fb2ca842b7498db13e9615672f71d4ed141ee2122b`. Draft only. No production, release or PR #5 changes.

## 2026-11-14 — Close the frozen resolver-only queue

- Reconstructed the exact cohort from the `0cda10e` CI artifact and pinned inputs. Reviewed all 614 IPv4 across 109 buckets, with registry and RIS evidence for every bucket and 126 per-address registry checks for covering or more-specific allocations and non-RIPE fallbacks. [Decision ledger](v41-geo-only-queue-decisions-20261114.tsv) has no unclassified addresses. Its 612 hold decisions are snapshot-specific and make no claim of permanent exclusion or lack of reachability.
- Admit `193.162.143.0/24` (AS205090) only. The two Moscow /25 child assignments cover all 256 addresses and match the linked operator geofeed. Exact RIS BGP state has 379 paths with the same origin and the route is RPKI-valid. Preserve the existing /23 scope rule and 112-row table limit. Separately hold `185.180.230.0/24`: RIS BGP state saw two exact origins, both authorized by ROAs. [Evidence and totals](v41-geo-only-queue-closure-20261114.json).
- Fixed-input DAT changes only `193.162.143.13/32` and `193.162.143.254/32` to DIRECT. This is +2 IPv4 versus the prior PR head and +59 versus published v41, without removals or changes to IPv6, PRIVATE, hard or raw resolver inputs. All 14 official Telegram ranges remain outside DIRECT. Candidate SHA-256 `8d807b8d6069791b2e006bc561c4c69cc1a3172521cde0271c62b9305ce1c391`. No main, release or PR #5 changes.

## 2026-11-14 — Keep prefix audit correct with unobserved pins and new RPKI results

- Both audit queues recognize `AS212066[Yandex][STATIC-DIRECT]` and `AS212066[Yandex+STATIC-DIRECT]`. Extraction reports observed company origins separately from the unique selected company layer, including pins. The audit reads the selected-company metric and also reconciles older reports against exact static-only rows. No selected or global prefix output, DIRECT rule or pin changed.
- The v37 reconciliation seed still requires the same 19 prefixes and all 20 exact prefix/origin pairs, checked against [the archived audit artifact](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43383174561/artifacts/14016919373). Extra `invalid_asn` pairs, including a new origin on a seeded prefix, go to `unseeded_rpki_invalid_review.tsv` as REVIEW. CI requires the exact current-minus-historical pair set. Historical losses, status drift or inconsistent triage still fail.
- Verification uses the PR #28 production snapshot, a copy of its ipverse archive with both AS212066 pins removed, and the historical evidence artifact. No production publication is part of this change.

## 2026-11-14 — Restore the independently verified additional-source operator routes

- The [additional-source audit](https://github.com/SpeedeMiner/Geoip-ru-server/blob/062d504a4032b52684808ec6cac3d6a7c2ffaa8d/docs/v41-additional-feed-resolver-audit-43579021611.json) found zero DNS-only loss in the accepted v37 coverage. The [separate one-group discovery queue](https://github.com/SpeedeMiner/Geoip-ru-server/blob/062d504a4032b52684808ec6cac3d6a7c2ffaa8d/docs/v41-additional-one-group-discovery-43579021611.json) is not admitted by feed membership. It supplies only independently confirmed candidates for the existing reviewed-operator table.
- [Exact release evidence](v41-additional-reviewed-operator-release-20261114.json) confirms nine /24 assignments using RIPE, registry-linked operator geofeeds, exact single-origin RPKI-valid RIS and same-origin pinned ipverse (exact or containing announcement). The reviewed table increases from 112 to 121 entries under a 121-row cap, with the existing minimum prefix sizes and non-overlap checks intact.
- Expected fixed-input effect: +15 exact IPv4, zero IPv4 removals, zero IPv6 or PRIVATE changes. The other addresses inside the nine /24s are already DIRECT. Hard, Telegram, raw resolver and admission exclusions stay unchanged. No PR #5 changes.

## 2026-11-14 — Close the v41 release input and readback gaps

- Follow-up to the [full repository audit](https://github.com/SpeedeMiner/Geoip-ru-server/blob/e521e60ea9bbbc7d154e01ae336af3d812ce070a/docs/V41_FULL_REPOSITORY_AUDIT_20261114.md), based on production source `596c93df`.
- The candidate retains all ten current and historical block inputs in a checked versioned archive, including exact optional fallback files. The release manifest links the input provenance and build commit to the actual DAT, SRS, checksums and archives. Snapshot download verification precedes release promotion. Rolling DAT and SRS readback fails on persistent drift after promotion.
- Local integration tests verify fail-closed behavior for a missing block archive, mismatched public SRS, stale rolling output and competing release updates. Scope is build and publication only. W1ZARDZ admission, historical block policy, main, existing releases and PR #5 are not changed by this candidate.

## 2026-11-15 — Classify verified payment, public-service and hosting origins

- Reviewed 22 submitted ASN-to-company mappings against RIPE RDAP and RIS. Only AS8732, AS12768 and AS56330 matched as submitted. Added those three and 29 verified alternatives/related origins to the registry and class policy. No non-observed origins, upstreams or third-party CDN ASNs were newly imported. The [decision record](V41_ASN_COVERAGE_REVIEW_20261115.md) includes the 19 rejected mappings.
- Registry 57 → 89 (24 new CORE, 8 new SHARED). All 32 additions were already selected through RIR-RU. On the published snapshot their 248 aggregated CIDRs are already fully DIRECT. Fixed-input replay retained v37 and v41 DAT, both SRS, PRIVATE and both exclusion masks byte for byte. Selected and global BGP CIDR key sets are unchanged.
- Public DNS/BGP sample: 33 of 34 unique returned IPs already DIRECT. `ruvds.com` resolves in this sample to `186.2.163.33` on third-party AS59692. Keep that /24 and ASN out of the RuVDS company list. No merge, production or release changes, and no changes to #5, #35 or #40.
- Independently checked the missing RuVDS frontend IP in RIPEstat DNS Chain, then verified that the published Geosite-ru-light RU SRS already matches `ruvds.com` and `www.ruvds.com` by suffix. No reason to add a shared third-party /24 for a domain-aware client.

## 2026-11-15 — Verify regional telecom infrastructure origins

- Reviewed 18 submitted operator mappings and three corrected/related origins. Added 16 SHARED_INFRA rows on top of PR #41 (89 → 105). Kept the existing AS12768 and AS56330 entries. Used RIPE registration and observed origins, not AS-set membership. See [operator decisions](V41_OPERATOR_ASN_REVIEW_20261115.md).
- Held AS13116 at ASN level because RIPE records Tele2 Sverige AB. Its three RIS-observed Russian /24s are already fully DIRECT. Replaced wrong InterZet and Novotelecom associations with AS41733 and AS31200, and recorded AS47395 as SCARTEL-AS separately from MegaFon's AS25159. All 16 origins were previously selected through RIR-RU. No changes to PR #5, main or published artifacts.
- Hash-verified replay preserved the v37 and v41 DATs, both SRS files and both block masks byte-for-byte. No added or removed DIRECT addresses. All 371 aggregate CIDR keys for the 16 origins were already covered. 164 Python tests, Go tests and release gates passed locally. Evidence in [per-ASN coverage](V41_OPERATOR_ASN_EVIDENCE_20261115.tsv).

## 2026-11-15 — Verify live PR #41 artifact and AS13116 exact routes

- Compared CI artifact 14150353641 against release `7eef1efc`: +2,304 / −256 RU IPv4, +one RU IPv6 /48, no PRIVATE delta. Restoring the old registry on the same live inputs reproduced CI binaries and block masks byte for byte. Replacing only the release ipverse archive also reproduced CI final DAT/SRS, so final routing drift comes from ipverse, not the PR's registry entries. See [control replay and exact deltas](V41_PR41_LIVE_DELTA_20261115.md).
- All three exact TELE2RU /24s are completely DIRECT in both snapshots, with no block-mask overlap. The RIS snapshot records MOAS for `193.138.149.0/24` (AS48092 and AS13116). No new pins or ASN admission, and no routing change.
- New `2a0b:4e07:63f0::/48` is labelled KP by its exact RDAP and registry-linked geofeed despite an RU origin ASN. Its already-present sibling is IN in the same geofeed. Nine new IPv4 /24s have nonregional exact RDAP labels, requiring corroboration before changing the routing policy. PR #5, main and production are untouched.

## 2026-11-15 — Rehearse precise dual-stack admission exclusions without changing policy

- Reviewed the two AS218750 /48s against exact RDAP, the pinned operator geofeed and RIPE RIS/RPKI. KP/IN are exact assignments, while the parent RIPE delegation is IL and AS218750 is RU. The live /47 comes from ipverse aggregation; RIS shows the two /48s separately. Each is already in the v37 layer wherever it appears in final DIRECT.
- A local shadow replay removing exactly those two /48s changed only the IN /48 on the release inputs and both /48s on CI inputs. IPv4, PRIVATE, block masks and other AS218750 coverage were unchanged. Overlay, hard/PRIVATE, Telegram, delta and DAT/SRS validation passed. See [evidence and implementation boundary](V41_AS218750_IPV6_SHADOW_20261115.md).
- Keep both production routing and PR #41 scope unchanged. If implementing a policy later, do not mislabel the IL resource delegation or use an ASN-wide exception. Existing IPv4 regional-exclusions schema cannot honestly describe this IPv6 case.

## 2026-11-16 16:33 +0500 — Direct by Reachability: утверждённый план

План пользователя сохранён полностью; выполнение и проверки фиксируются ниже.

В основе плана лежит ваша модель «Direct by Reachability» (в DIRECT идут не только сети RU + BY + KZ и локальных корпораций, но и любые зарубежные CDN/узлы, напрямую доступные из РФ без VPN). Поэтому агрессивная чистка глобальных ASN и вырезание корпоративных сетей по DNS исключены как ошибочные, а фокус сделан на защите от «тихих» сбоев апстримов, прозрачности PR-сборок, поасеновом контроле и исключении недоступных из РФ диапазонов.
1. Починка сравнения кандидатов в PR (.github/workflows/geoip-v41.yml:475):
   - Исправить шаг проверки относительных изменений на этапе Pull Request: сравнивать собранного кандидата не с самим собой, а с последним опубликованным релизом.
   - Выводить в PR Summary сводную таблицу диффа: изменение числа IPv4/IPv6 адресов, количества CIDR и разрез по источникам (RIR, корпоративные ASN, Hydra, статические overrides).
2. Усиление проверок загрузчика (download_v41_build_inputs.sh:28):
   - Добавить для каждого обязательного источника валидацию формата и структуры (проверка на валидный JSON/CSV/RIR, отсутствие HTML-заглушек и кодов ошибок в теле ответа).
   - Ввести нижние пороги по размеру/количеству записей для каждого файла. При сбое обязательного апстрима сборка должна жестко падать (fail-closed), не допуская перезаписи релиза неполным или пустым снимком.
3. Вынос статических префиксов из кода в конфиг (extract_ru_asn_prefixes_v41.py:287):
   - Перенести захардкоженные диапазоны (включая Yandex Turkey overrides) из Python-скрипта в версионируемый файл .github/data/v41-static-overrides.tsv с полями: cidr, asn, reason, added_date, review_after.
   - Добавить в лог сборки информационное предупреждение (без блокировки билда), если статический диапазон из файла перестал наблюдаться в текущих таблицах BGP.
4. Замена фильтра «зарубежности» на фильтр «недоступности» для внешних списков:
   - Сохранить допуск категорий Hydra DIRECT/WHITELIST и зарубежных CDN/облаков, если они доступны из РФ.
   - Вычитать из внешних/неподтвержденных списков только диапазоны с доказанной недоступностью на уровне IP:
     - подтвержденные IP-блокировки на стороне ТСПУ/РКН (блокировки по подсети/IP, а не по SNI);
     - подтвержденные входящие геоблокировки (Inbound Geo-block), когда сам сервис режет подключения с российских IP (например, API OpenAI, Anthropic и аналоги).
   - Сохранить защиту build_v41_overlay.py:587: вычитание по недоступности не должно задевать подтвержденное ядро (RU + BY + KZ + корпоративные ASN), чтобы блокировка одного ресурса не уводила в VPN соседние легитимные сервисы на общем IP.
1. Перекрестная сверка BGP-наблюдений (.github/scripts/check_v41_bgp_observations.py):
   - Дополнить данные ipverse (имеющие 90-дневное окно агрегации) сверкой с актуальными таблицами маршрутизации RIPE RIS / RIPEstat раздельно по IPv4 и IPv6.
   - При расхождениях (например, если крупный оператор анонсировал новый блок, которого еще нет в ipverse, или перестал анонсировать старый) формировать отчет для ручного ревью без слепого автодобавления.
2. Аудит и актуализация корпоративных ASN (RU + BY + KZ):
   - Провести ревизию реестра корпоративных ASN на полноту покрытия ключевых банков, телеком-операторов, маркетплейсов, экосистем и облачных провайдеров всех трех стран (включая их аффилированные ASN, зарегистрированные в RIPE на зарубежные юрлица).
3. Версионируемый реестр критичных сервисов (.github/data/v41-service-inventory.tsv):
   - Оформить структурированный маппинг сервисов из белых списков Минцифры и критичных локальных ресурсов (service_name, domains, asn_or_cidr, evidence_type, verified_date).
   - Сервисы, работающие за глобальными общими CDN и не имеющие выделенных IP-блоков, фиксировать в отчете с пометкой о необходимости маршрутизации через доменные правила (geosite / domain выше geoip:ru на стороне клиента).
1. Тегирование происхождения префиксов (Provenance tracking) в build_v41_overlay.py:
   - Сохранять источник каждого диапазона (regional_rir, corp_asn, shared_infra, hydra_verified, static_override) до этапа финального схлопывания CIDR. Это позволит при любом аномальном изменении размера бинарника за секунды увидеть, какой именно входной список дал прирост или падение.
2. Контроль компрессии и веса бинарников (build_v41_overlay.py:365):
   - Сохранить текущую интервальную математику вычитания и агрегацию ipaddress.collapse_addresses.
   - Добавить в метрики сборки замер количества CIDR-записей и итогового размера geoip.dat, geoip_RU.srs и geoip_PRIVATE.srs раздельно по IPv4 и IPv6.
3. Документирование приоритета правил маршрутизации:
   - Зафиксировать в README.md эталонный порядок правил для Xray и sing-box:
     1. Заблокированные домены и сервисы с геоблоком РФ -> PROXY
     2. Локальные/белые домены (включая сервисы из списков Минцифры на общих CDN) -> DIRECT
     3. geoip:private и geoip:ru (содержащий RU+BY+KZ + корпорации + доступные узлы) -> DIRECT
     4. Остальной трафик -> PROXY
1. Поасеновый контроль деградации (validate_v41_publication_bounds.py):
   - Дополнить общие пороги изменения объема всей базы (0,5% IPv4 / 1% IPv6) индивидуальными порогами для ключевых стран (RU, BY, KZ) и критически важных ASN (крупные операторы связи, банки, облака).
   - Если отдельный ключевой ASN или страна теряет более 10% адресного пространства за одну сборку, пайплайн должен блокировать публикацию до ручного подтверждения SHA кандидата.
2. Контрольная матрица доступности (.github/data/v41-routing-fixtures.tsv + validate_v41_routing_matrix.py):
   - Внедрить автоматическую проверку готовых бинарников (.dat и декомпилированного .srs) по эталонным адресам IPv4/IPv6 с учетом модели «Direct by Reachability»:
     - Обязательны в RU (DIRECT): эталонные стабильные блоки госсервисов, национальных DNS, крупных банков и операторов RU/BY/KZ, а также контрольные доступные из РФ узлы из проверенных белых списков.
     - Строго запрещены в RU (PROXY): диапазоны с подтвержденной IP-блокировкой в РФ и диапазоны с жестким геоблоком российских IP (OpenAI, Anthropic и др.).
3. Расширение юнит-тестов интервальной математики (.github/scripts/test_build_v41_overlay.py):
   - Добавить property-based тесты на равенство множеств при вычитании вложенных, смежных и пересекающихся подсетей, полном удалении блока маской и работе с граничными хостами (/32 и /128).

### Ход выполнения

- [x] Сравнение PR-кандидата с опубликованной базой и отчёт реализованы; ожидается проверка в Linux CI.
- [ ] Проверка обязательных апстримов: реализована для ответов с HTML/XML и полноты/свежести пяти RIR; остальные источники и пороги ещё требуют отдельной ревизии.
- [x] Версионируемые статические overrides: извлечение, предупреждения и проверка итогового покрытия в Go и базовом валидаторе используют текущий реестр; жёсткая привязка к двум конкретным префиксам устранена.
- [ ] Фильтр доказанной недоступности реализован и проверен на синтетических данных; реестр доказательств пуст, Linux CI и сетевые проверки ещё не выполнены.
- [ ] Сверка BGP: создан диагностический PR-отчёт RIPE RIS/ipverse для тринадцати ASN; API проверен выборочно, полный аудит корпоративных ASN не выполнен.
- [ ] Реестр критичных сервисов: одиннадцать подтверждённых официальными источниками доменов, без утверждения о принадлежности к спискам Минцифры.
- [ ] Происхождение и метрики: статические overrides добавлены в источник и provenance; добавлены размеры файлов и числа сетей по семействам. Общая атрибуция требует продолжения; байты смешанного бинарника по семействам не разделялись.
- [x] Порядок правил Xray и sing-box описан в README; примеры клиента требуют проверки на конкретной конфигурации.
- [ ] Пороги: добавлен gate для RIR RU/BY/KZ и 26 ASN по исходному пространству с привязкой входов к манифесту; требуются дальнейшее расширение и проверка в Linux CI.
- [ ] Контрольная матрица: два официальных адреса Яндекс DNS, IPv4 и IPv6; нужны BY/KZ, PROXY и замеры доступности из РФ.
- [x] Добавлены детерминированные тесты свойств интервального вычитания и граничных адресов IPv4/IPv6.

### 2026-11-16 — проверка рабочего кандидата

- Исходная папка была пуста; создана отдельная локальная копия GitHub-репозитория. Изменения только в рабочей копии, публикация не выполнялась.
- 32 точечных локальных теста прошли: PR-отчёт, проверка RIR, overrides, BGP-диагностика, пороги, CIDR и метрики. Полная сборка и новые шаги публикации в GitHub Actions ещё не запускались.
- Общий прогон тестов в Windows не прошёл: часть тестов рассчитана на Linux-инструменты и файловые возможности CI. Этот результат нельзя считать проверкой работоспособности Linux-сборки.
- Доступность из РФ не устанавливалась: адреса OpenAI, Anthropic и иных сервисов в новые исключения не добавлялись. Существующие жёсткие исключения и правила защиты resolver-only сохранены.
- Порог 10% сравнивает удалённое пространство отдельно по семействам в **исходных** ASN/RIR наборах; это не эквивалент потери фактического покрытия финального DIRECT.

### 2026-11-16 17:10 +0500 — продолжение Direct by Reachability

- [x] Реализован реестр `v41-reviewed-unreachable.tsv` для подтверждённых IP-уровневых блокировок и входящих IP-геоблоков. Строк пока нет: доступность из РФ и внешние доказательства не выдумывались. Срок проверки записи обязателен; недействительные или просроченные данные останавливают сборку.
- [x] Новая маска вычитает только адреса вне региональных ресурсов и выбранных региональных/корпоративных ASN и проверенных операторов. Прежний приоритет PRIVATE, подтверждённых жёстких блокировок и Telegram сохранён. Проверяются происхождение и хэш реестра.
- [x] Таблицы зарубежных назначений IPv4 и IPv6 переведены в режим справочных свидетельств: они сами по себе не исключают адреса. Это **не** доказывает доступность этих адресов из РФ и не добавляет их без другого источника. Фактический diff со сборкой релиза ещё не выполнен и необходим до публикации.
- [x] На синтетических IPv4/IPv6 данных сборщик и независимый валидатор проверены вместе: сохранение ядра, вычитание вне ядра, приоритет жёсткой блокировки и недопущение подменённого результата.
- [ ] Справочный `v41-service-inventory.tsv` содержит девять официально подтверждённых доменов критичных услуг. Это не подтверждение включения в перечни Минцифры, не проверка доступа из РФ и не автоматический импорт в маршрутизацию. Реестр и источники требуют расширения.
- [ ] `v41-routing-fixtures.tsv` и проверка DAT/декомпилированных SRS добавлены в CI: два официальных адреса Яндекс DNS IPv4/IPv6. Адреса подтверждены оператором, но сетевая доступность не измерялась; BY/KZ и подтверждённых PROXY-примеров пока нет.
- [ ] Добавлен контроль размера 31 обязательного источника относительно прошлого выпуска: падение более чем на 50% блокирует публикацию независимо от подтверждения SHA кандидата. Это дополнительная эвристика, а не исчерпывающая проверка содержимого; проверки каждого формата и пороги по записям ещё не завершены.
- [x] Прошли 75 локальных точечных тестов. Полная Linux CI-сборка, реальные входные снимки, полноценный ASN-аудит и замеры доступности из РФ пока не проверены; релиз не публиковался.
- [ ] Приоритетный контроль расширен с 5 до 19 ASN: по манифестам release commit `63b8abf0ba6c2264724a58ec9a2fb7035c5130a6` все 19 имели IPv4-наблюдения ipverse; у AS41551, AS43399, AS44386 и AS50339 IPv6-наблюдений в этом снимке не было. Это проверка присутствия в одном снимке, не новая независимая проверка владения и не доказательство доступности. Позднее добавлены ещё два ASN банков KZ; полный аудит и мониторинг IPv6 при отсутствии исходной базы остаются открытыми.
- [x] RIPEstat Announced Prefixes для AS212066 доступен из среды выполнения: получен ответ `status=ok`, четыре записи IPv4/IPv6; новый парсер обработал ответ. Это не измерение из сети РФ и не сравнение с закреплённым ipverse-снимком.

### 2026-11-16 — текущий рабочий проход

- [x] Go-сборщик читает статические префиксы из помеченных записей выбранных origins; проверка итогового покрытия и список в отчёте больше не привязаны к конкретным двум адресам. Python-валидатор сопоставляет отчёт с конфигурацией реестра. Встроенная проверка извлекателя использует синтетические сети.
- [x] Для локального тестирования во временный каталог проекта загружен Go 1.26.10; SHA-256 архива сверен с официальным. До и после изменения прошли Go unit tests; self-test извлекателя прошёл на синтетическом списке ASN. Синтаксис двух изменённых shell-скриптов и YAML workflow проверен локально.
- [ ] Реальные сборочные входы и финальные бинарники не скачивались и не анализировались; Linux CI, реальный адресный diff и проверки доступности из РФ не выполнены. Исходные изменения пока находятся только в локальной рабочей копии на базе main `c0d2a01ba1fb5f5c0e48965d614945348083a900`; синхронизация журнала сама по себе не публикует код или релиз.
- [x] По RIPE RDAP подтверждены [AS35673 JSC Kaspi Bank](https://rdap.db.ripe.net/autnum/35673) и [AS39433 Kazakhstan Halyk Bank JSC](https://rdap.db.ripe.net/autnum/39433). RIPE RIS за 2–16 ноября показал соответственно 6 IPv4/2 IPv6 и 3 IPv4/0 IPv6 анонсов; сравнивать эти количества с агрегатами ipverse напрямую нельзя. Оба ASN уже выбирались из KZ RIR в опубликованном снимке. В локальный корпоративный реестр они добавлены с консервативным классом SHARED_INFRA и в приоритетный мониторинг, их номера добавлены в PR-сверку BGP; локальный разбор — `docs/V41_KZ_BANK_ASN_REVIEW_20261116.md`. Нулевую дельту итоговой базы до реального CI не предполагаем.
- [x] В BGP-диагностику добавлены проверка фактического окна RIPEstat и контроль задержки последнего среза. На реальном ответе AS212066 с запрошенным окном 15 ноября 12:00 — 16 ноября 12:00 UTC источник указал конец доступных данных 16 ноября 00:00 UTC; результат нельзя представлять как наблюдение за полные 24 часа. Данные вне ожидаемого окна или старше 48 часов помечаются недоступными, а не потерянными маршрутами.
- [x] Итоговая локальная проверка текущего прохода: 89 выбранных Python-тестов и полный Go unit test сборщика прошли; синтаксический разбор изменённого workflow и двух shell-сценариев прошёл. Синтетическая проверка сборки и независимой валидации включает IPv4 и IPv6. Это не заменяет полный прогон GitHub Actions с настоящими источниками.
- Синхронизация на GitHub ограничена этим журналом; локальные изменения кода, конфигураций и новый локальный отчёт в неё не входят. Для документационного коммита используется `[skip ci]`, поскольку push в main иначе запускает рабочий процесс публикации v41.

### 2026-11-16 — сверка отдельных ASN и продолжение проверок

- [x] Сопоставлены отдельные JSON ipverse commit `e23603237f0e178c026963fea2b36165d1badd75` и RIPE RIS за 15 ноября 00:00 — 16 ноября 00:00 UTC, `min_peers_seeing=1`, для AS35673 и AS39433. Сравнение выполнено по объединению адресного пространства, не по числу строк. Для AS35673 в RIS дополнительно виден `82.115.37.0/24` (256 IPv4), у AS39433 различий IPv4 не выявлено; по IPv6 разницы нет, при этом для AS39433 оба источника не вернули IPv6.
- [ ] [RIPE RDAP](https://rdap.db.ripe.net/ip/82.115.37.0/24) связывает родительское `82.115.36.0/22` с JSC Kaspi Bank; это основание для ручного ревью выявленного расхождения, но не доказательство доступности из РФ или отсутствия /24 в готовой базе. Финальный DAT и большие дампы не читались, автоматически маршруты не добавлены.
- [x] Выявлена и исправлена ошибка проверки RIPEstat: `latest_time` может быть позднее конца исторического запроса, поскольку обозначает последний доступный срез источника. Корректный исторический ответ больше не отклоняется; добавлен регрессионный тест.
- [x] [AS51365 BELINVESTBANK-BY](https://rdap.db.ripe.net/autnum/51365), OJSC Belinvestbank, уже был выбран в региональном слое BY. Для окна 15–16 ноября объединённые IPv4-пространства ipverse и RIPE RIS совпали (256 адресов); IPv6 оба источника в проверенных снимках не вернули. ASN добавлен в локальный корпоративный реестр как SHARED_INFRA и приоритетный мониторинг; фактическая дельта итоговой базы ещё не проверена.
- [x] [AS62170 ASBPSSBERBANK](https://rdap.db.ripe.net/autnum/62170) виден в опубликованном BY-манифесте и индивидуальной записи ipverse. Первоначальные запросы RIPE RIS истекали по тайм-ауту; последующий повторный запрос за 15–16 ноября удался и совпал с ipverse по 256 адресам IPv4, IPv6 в обоих ответах нет. ASN добавлен локально как SHARED_INFRA, в приоритетный контроль и BGP-сверку; доступность из РФ и итоговая дельта не измерялись. Подробности — в локальном, ещё не опубликованном файле `docs/V41_BY_BANK_ASN_REVIEW_20261116.md`.
- [x] В справочный реестр добавлен домен [Беларусбанка](https://belarusbank.by/) по официальному сайту. Принадлежность к спискам Минцифры, отдельные IP-диапазоны и доступность из РФ этим не подтверждаются; правило маршрутизации автоматически не создаётся.
- [x] В приоритетной проверке для семейства без предыдущего базового набора теперь явно выводится `no-baseline`; это не утверждение о наличии покрытия и не автоматический запрет сборки. Прогон 91 выбранного Python-теста завершился без ошибок; Linux CI и реальный diff остаются открытыми.
- [x] Подготовлен необязательный отчёт CI для кандидатов на адресную проверку: для `82.115.37.0/24` он отдельно считает адреса в DIRECT и PRIVATE, связывает результат с SHA-256 кандидата и сохраняет свидетельства. Проверка не меняет маршруты и не заявляет доступность из РФ. Частичное покрытие и запуск команды проверены на синтетической базе; реальный отчёт ещё не сформирован, покрытие опубликованного DAT неизвестно.
- [x] В BGP-сверке отсутствующее поле семейства ipverse больше не принимается за пустой список наблюдений. Ошибочный ответ не должен превращаться в ложное сообщение о потерянных маршрутах; пустой список по-прежнему допустим как явный результат источника.
- [x] В ответах RIPEstat проверяются номер запрошенного ASN и пересечение каждого временного интервала анонса с окном ответа; ошибочный номер или не относящийся к окну интервал не превращаются в отчёт об изменении маршрутов. Проверены тестовые случаи и настоящий малый ответ для AS43601. Формат полей описан в [документации RIPE NCC](https://stat.ripe.net/docs/data-api/api-endpoints/announced-prefixes).
- [x] [AS43601 BCC-AS](https://rdap.db.ripe.net/autnum/43601) зарегистрирован за JSC BankCenterCredit и уже присутствовал в опубликованном KZ-слое. В индивидуальном ipverse-снимке и RIPE RIS за 15–16 ноября одинаковое пространство: две IPv4 /24, IPv6 в обоих ответах отсутствует. ASN добавлен в локальный корпоративный реестр как SHARED_INFRA, контроль потерь и BGP-сверку; [bcc.kz](https://www.bcc.kz/) внесён в справочный реестр сервисов. Это не подтверждает доступность из РФ, отсутствие иных IPv6-маршрутов или нулевую дельту итоговой базы.
- [x] После перечисленных изменений прошли 97 выбранных Python-тестов и `git diff --check`; реальные входы сборки и Linux CI в этом проходе не запускались. Синхронизация этого журнала не публикует локальные исходники.
- [x] Когда фактическое окно RIPEstat короче запрошенного более чем на час, JSON и сводка PR теперь показывают `partial-window`, а не `ok`. Сравнение остаётся справочным; данная метка не означает исчезновение маршрутов и не изменяет DIRECT.
- [x] Проверен [AS43934 KISC-AS](https://rdap.db.ripe.net/autnum/43934): в RIPE указан Казахстанский межбанковский расчётный центр. По [официальному сообщению](https://npck.kz/o-sozdanii-naczionalnoj-platezhnoj-korporaczii-naczionalnogo-banka-respubliki-kazahstan/) в 2023 году он реорганизован в Национальную платёжную корпорацию; актуальное использование именно этого ASN правопреемником не подтверждено. В опубликованном снимке ASN уже выбран через KZ RIR; ipverse и RIPE RIS за 15–16 ноября содержат одинаковые 512 IPv4 адресов, IPv6 в этих ответах нет. Он добавлен локально в реестр как SHARED_INFRA, приоритетный контроль и сверку BGP; выводы о доступности из РФ и фактической дельте релиза по этим данным не делаются. Домен npck.kz внесён отдельно в справочный реестр без привязки к этому ASN.
- [x] [AS44288 BPC-AS](https://rdap.db.ripe.net/autnum/44288), JSC Banks Processing Center, уже выбран в опубликованном BY-слое. Индивидуальный снимок ipverse и RIPE RIS за 15–16 ноября совпадают по 256 адресам IPv4; IPv6 в этих ответах отсутствует. Номер добавлен в локальный реестр как SHARED_INFRA, приоритетный контроль и сверку BGP, без вывода о фактической доступности из РФ или дельте итоговой базы.
- [x] Локальная перепроверка: 99 выбранных Python-тестов прошли; после добавления AS62170 все 112 ASN корпоративного реестра сопоставлены с политикой, две копии реестра совпадают, 26 приоритетных ASN разобраны без ошибок. Изменённый workflow прошёл синтаксический разбор YAML, а два обновлённых shell-шага — проверку синтаксиса. Это не запуск Linux CI и не проверка фактической маршрутизации.

### 2026-11-16 — передача проекта

- [x] Подготовлен [документ передачи с незавершёнными задачами](https://github.com/SpeedeMiner/Geoip-ru-server/blob/handoff/v41-direct-reachability-20261116/docs/V41_PROJECT_HANDOFF.md).
- [x] Рабочие изменения и документ сохранены на отдельной [ветке передачи](https://github.com/SpeedeMiner/Geoip-ru-server/tree/handoff/v41-direct-reachability-20261116), commit `ab60305d3144f431606860305e65cbd8834f352e`. Проверены контрольные суммы 52 сохранённых файлов. Ветка не объединена с main; Linux CI и публикация релиза остаются незавершёнными.

### 2026-11-16 — продолжение после передачи

- [x] Исправлена атрибуция Kyoresuas: дополнение списка сервисов агрегатными файлами больше не меняет исходный набор JSON и не завышает `service_json_prefixes`; объединённое множество маршрутов сохранено. Добавлен тест на раздельные значения метрик и итогового набора.
- [x] Парсер каталога сервисов отклоняет повреждённые категории, записи сервисов, списки ASN/семейств и маршруты по умолчанию вместо частичного принятия некорректной структуры. Проверены синтетические примеры, включая повреждённую запись рядом с валидной.
- [ ] Совместимость более строгого разбора с полным актуальным каталогом не проверена: исходный крупный IP-каталог не читался по ограничению пользователя. Требуется Linux CI с реальными источниками, прежде чем считать проверку готовой к выпуску.
- [x] Прошёл повторный прогон 101 выбранного Python-теста, в том числе интеграционная проверка сборки на синтетических данных. Это не заменяет Linux CI и проверку настоящих источников.
- [x] Проверка таблицы количества записей источников теперь отклоняет ошибочные и повторяющиеся строки, отрицательные/некорректные значения, несовпадение суммы строки и итогов. Синтетические случаи проверены; PR-триггер дополнен новым модулем.
- [x] После изменения прошли 102 выбранных Python-теста и `git diff --check`. Валидность настоящего отчёта сборщика и полный Linux CI ещё требуют подтверждения.
- [x] Открыт [черновик PR №56](https://github.com/SpeedeMiner/Geoip-ru-server/pull/56), запущен Linux CI. Проверка синтаксиса workflow прошла; основная сборка остановилась на несоответствии числа записей LACNIC на нескольких зеркалах ([запуск](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43915386641)). Публикация не выполнялась.
- [ ] Установить причину расхождения LACNIC. [Спецификация APNIC](https://www.apnic.net/about-apnic/corporate-documents/documents/resource-guidelines/rir-statistics-exchange-format/) определяет количество как число строк записей; до выяснения причин проверка не ослаблена. В сообщение об ошибке добавлены безопасные агрегированные числа объявленных и фактически полученных записей по типам; повторный CI должен дать диагностические данные без вывода IP-дампа.
- [ ] Повторный [запуск](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43916207038) показал одинаковый результат на трёх зеркалах: всего заявлено 50216 строк, получено 48502; IPv4 20466/20466, IPv6 13608/13608, ASN 16142/14428. Добавлена диагностика суммы размеров диапазонов ASN, чтобы проверить возможное расхождение методики подсчёта; совпадение зеркал не доказывает полноту и не отменяет fail-closed.
- [x] В [следующем CI](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43916822451) сумма размеров ASN-диапазонов также оказалась равной 14428 на всех трёх зеркалах. Гипотеза о подсчёте отдельных ASN в диапазонах не подтвердилась. Основная сборка заблокирована до установления причины или появления проверенного корректного источника; строгая проверка сохранена, release не публиковался.
- [x] Для той же версии кода синтаксическая проверка v41 и отдельная [сборка v39](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43916822426) прошли; [аудит префиксов v37](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43916821833) ещё ожидает внешние RDAP/RPKI ответы. Успех v39 не означает успешную проверку v41 или полноту LACNIC.

### 2026-11-16 — продолжение после оценки прогресса

- [x] Проверка структуры и минимального числа сервисов Kyoresuas перенесена в начало загрузки, непосредственно после получения закреплённых входов. Это позволит диагностировать каталог до загрузки RIR, не меняя формируемые маршруты. Добавлены синтетические проверки допустимого набора, недостаточного числа сервисов и повреждённой записи; синтаксис загрузчика проверен.
- [ ] Повторить Linux CI и подтвердить, что актуальный полный каталог проходит новую раннюю проверку. Основная сборка остаётся заблокированной расхождением LACNIC; доступность из РФ и полный diff кандидата не определены.
- [x] После изменения прошли 103 выбранных Python-теста и `git diff --check`; синтаксис изменённого shell-загрузчика проверен.
- [x] Для предыдущего коммита автоматический повтор CI не появился. Автоматическая проверка разрешений первоначально отклонила временное закрытие PR №56; после явного разрешения пользователя способ запуска применён, PR вновь открыт.
- [x] Пользователь разрешил временное закрытие и повторное открытие PR; повторный [CI](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43921730034) запущен. Ранняя проверка настоящего каталога Kyoresuas прошла: 90 сервисов и 986 уникальных префиксов; затем сборка остановилась на прежнем расхождении LACNIC. Это не полный CI и не проверка готового DAT.
- [x] После отказа обычного файла добавлена попытка загрузить официальный расширенный формат LACNIC и его зеркала. Для него действуют те же проверки заголовка, свежести, полного числа строк и итогов по типам; синтетический тест подтверждает отказ при усечении. В Linux CI принят официальный расширенный файл с 97706 записями; несоответствующий обычный файл по-прежнему отклоняется.
- [x] После добавления альтернативных адресов прошли 104 выбранных Python-теста и проверка синтаксиса загрузчика; результат для настоящего расширенного источника ещё не известен.
- [x] [Linux CI v41](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43922390417) завершился успешно для commit `19cdbd01ee7ee36679c9f06a9f82c4e607190eb8`. Проверены сборка, политика, DAT и SRS, две текущие контрольные точки и PR-сравнение с release `63b8abf0ba6c2264724a58ec9a2fb7035c5130a6`. Публикационное задание для PR пропущено; релиз не выпускался.
- [x] По сводке CI SHA-256 кандидата `2b52d36c63235031d62410a53ea2ec89f925a33b543f217d44691621ec753af4`; относительно указанного release добавлено 41629 IPv4 и 4835703278458516698824704 IPv6 адресов, удалений по обоим семействам нет, PRIVATE не изменился. Пороги суммарной дельты не превышены; контроль потерь исходных приоритетных наборов не выявил превышения, хотя у ряда IPv6 нет базового набора (`no-baseline`). Это снимок одного запуска, не оценка фактической доступности из РФ и не решение о публикации.
- [x] Справочный CI-отчёт показал, что `82.115.37.0/24` целиком входит в DIRECT кандидата (256 из 256 адресов), PRIVATE не пересекается. Доступность сервиса из РФ не измерялась; маршруты по одному этому результату не добавлялись.
- [ ] В том же запуске BGP-сверка отметила все 13 ASN как `unavailable`; это не исчезновение маршрутов и не успешная независимая сверка. Разобрать причины в диагностическом артефакте и обеспечить повторяемые наблюдения; в этот запуск этап был справочным и не остановил CI.
- [x] Для следующего запуска добавлен вывод типа ошибки BGP в сводку без вывода исходного текста исключения; раздельно отмечается отсутствие ASN в ipverse и ошибка запроса. Прошли 105 выбранных Python-тестов; настоящий повторный BGP-запуск ещё необходим.
