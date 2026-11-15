# v41 — сверка НСПК, Москвы, банков, ритейла, медиа и хостинга

Проверка на 15 ноября 2026. База сравнения — снимок [43617500418.1](https://github.com/SpeedeMiner/Geoip-ru-server/releases/tag/geoip-v41-snapshot-43617500418.1), release commit `7eef1efcaafbdbe259f3aa4e56a07c38979afbfb`, DAT SHA-256 `5d7e9dd0eb66bd507eb5f695b83441493fb20b2307ef71125de16c8b3809fa7d`.

**Политика.** Добавляем только зарегистрированные корпоративные или инфраструктурные origin ASN с наблюдавшимися маршрутами. Сверены RIPE RDAP, RIPEstat AS Overview и Announced Prefixes (01–15 ноября UTC), а также производственный манифест ipverse. Исторический бренд, соседство, общий AS-SET и CDN не доказывают принадлежность ASN. Не импортируем peers, upstreams или весь CDN по одному домену. `CORE_CORPORATE` означает зарегистрированный выделенный origin, `SHARED_INFRA` — хостинг, сеть доступа или общая инфраструктура. Для обеих групп сохраняются hard/IP/subnet, Telegram и PRIVATE.

| Запрошенный сегмент | Новые проверенные записи корпоративного реестра |
| --- | --- |
| НСПК, «Мир», СБП | AS50339, AS21292, AS41185 (NSPK-EC), AS41187 (NSPK-SBP), AS60967 (IPPS) |
| Москва | AS8901, ГКУ «Мосгортелеком», инфраструктурный слой |
| RUTUBE | AS207353 Ruform, AS48061 ГПМ Цифровые Технологии (общая инфраструктура группы) |
| Rambler | AS24638, AS42481, AS44696, AS57306, регистрант Rambler Internet Holding |
| ПСБ | AS42231, AS42554, AS42758 |
| Совкомбанк | AS197258, AS209973, AS51136 |
| Райффайзенбанк РФ | AS31174 |
| МКБ | AS202273, AS50464, AS39267 |
| DNS | AS57898 |
| М.Видео | AS52047 |
| Beget | AS198610, AS213533, хостинг |
| RuVDS | AS214822, MT Finance, хостинг |
| Dr.Web | AS49238, AS59446 |
| Акадо / ЭР-Телеком | AS8732, AS12768, AS56330, сети доступа |

Первичные и операторские ссылки: [НСПК и официальные сайты](https://www.nspk.ru/about/official_sites), [RUTUBE в PeeringDB](https://www.peeringdb.com/net/22594), [RUTUBE и юрлицо ГПМ](https://rutube.ru/info/pdn_old/), [реквизиты RuVDS — МТ Финанс](https://ruvds.com/wp-content/uploads/2022/03/ruvds_rub.pdf). Индивидуальные ссылки RIPE RDAP для всех 32 записей находятся в реестре.

## Номера из сообщения, не добавленные под предложенным названием

| ASN | Регистрант или статус |
| --- | --- |
| AS200877 | iSH TRANSIT LTD, не НСПК |
| AS204368 | it NGO GmbH & Co. KG, не НСПК |
| AS49629 | RIPE RDAP не вернул действующий объект, RIPEstat не увидел маршрутов |
| AS196942 | RIPE RDAP не вернул действующий объект, RIPEstat не увидел маршрутов |
| AS8342 | RTComm.RU, не Rambler, уже есть в RIR-RU |
| AS47242 | Host SpA, не Rambler |
| AS39763 | RIPE RDAP не вернул действующий объект, RIPEstat не увидел маршрутов |
| AS200424 | CODEMA, не Совкомбанк |
| AS41624 | Elektronika NS Ltd., не Райффайзенбанк |
| AS41113 | RIPE RDAP не вернул действующий объект, RIPEstat не увидел маршрутов |
| AS200238 | T-Systems International GmbH, не DNS |
| AS51347 | SMS solutions SIA, не М.Видео |
| AS198722 | RDAP — 1310 Limited / TXRX-AS, не Beget, маршруты RIS не наблюдались |
| AS203876 | PLINACRO d.o.o., не RuVDS |
| AS41130 | RIPE RDAP не вернул действующий объект, RIPEstat не увидел маршрутов |
| AS42358 | Ростелеком (INSYS), не Positive Technologies, уже есть в RIR-RU |
| AS44050 | Petersburg Internet Network, не VK, уже есть в RIR-RU |
| AS57736 | Holstebro Kommune, не VK |
| AS208620 | Delen Private Bank NV, не Yandex Cloud |

Для исходных номеров воспроизведение: `https://rdap.db.ripe.net/autnum/<номер>`, `https://stat.ripe.net/data/as-overview/data.json?resource=AS<номер>`, `https://stat.ripe.net/data/announced-prefixes/data.json?resource=AS<номер>`. Отсутствие объекта или наблюдений не означает, что номер никогда не назначался. Положительная связь с заявленной компанией нужна отдельно. Не добавлены неанонсируемые AS43600/AS199463 Совкомбанка и AS197340 ПСБ. AS48347 и AS215346 не переименовываем в RuVDS по соседству или AS-SET. Три действующих и ранее включённых неверно подписанных потенциальных кандидата не вычитаем из общей RIR-RU базы. AS208398 не добавляем целиком по совпадению origin на отдельных анонсах.

## Проверка доступного публичного DNS и итоговой базы

Срез Google Public DNS + RIPEstat Network Info, без измерения HTTP или доступности из RU. Из 34 уникальных ответов A/AAAA на выборке публичных имён 33 уже в опубликованном v41 DIRECT. DNS может зависеть от резолвера, региона и времени. Это не полный перечень API, видеосегментов, платёжных узлов или зависимостей.

- `mos.ru` и `login.mos.ru` — AS8901. `psbank.ru`, `raiffeisen.ru`, `mkb.ru`, `beget.com`, `rambler.ru` также отдали адреса соответствующих проверенных ASN.
- Публичные `nspk.ru`/ `sbp.nspk.ru` в этом срезе — Servicepipe AS201706. Основная страница RUTUBE — Servicepipe и Qrator AS51115. Это не исключает существование собственных сетей и не делает CDN собственностью этих сервисов.
- Проверенные `ptsecurity.com`, `group.ptsecurity.com`, `ptsecurity.ru` уже маршрутизируются DIRECT через Qrator. Независимый собственный origin Positive Technologies не подтверждён, поэтому корпоративную запись не добавляем.
- Проверенные адреса `mail.ru` и `vk.com` уже покрывались AS47764 / AS47541; для `cloud.yandex.ru` наблюдались AS13238 и AS208398, адреса уже DIRECT.
- Исключение из выборки — `ruvds.com → 186.2.163.33`, origin AS59692 IQWeb FZ-LLC. [LACNIC RDAP](https://rdap.lacnic.net/rdap/ip/186.2.163.33) указывает IQWEB-LLC-NET, country BZ. RPKI valid относится к паре ASN/CIDR, не к владению RuVDS и не к географии. AS214822 добавляем как подтверждённую сеть RuVDS, чужой /24 и AS59692 не импортируем. Если нужен прямой маршрут для сайта, следующий шаг — проверить привязку домена и доступность из RU и разобрать доменное правило или точный /32 отдельно.

## Проверка эффекта

Добавлены 32 проверенных ASN (24 CORE, 8 SHARED) к 57, всего 89. Все 32 уже наблюдались через RIR-RU в зафиксированном снимке. Их 248 уникальных агрегированных записей (241 IPv4 и 7 IPv6) целиком покрыты опубликованным DIRECT. IPv4-объединение этих записей — 484 096 адресов. Не приравниваем агрегированные строки ipverse к точным анонсам RIS или к числу уникальных маршрутов.

Полная офлайн-пересборка на входах с SHA-256 из provenance воспроизвела v37 base, итоговый v41 DAT, оба sing-box SRS и исходную/эффективную маски исключений побайтово. Никаких добавленных или удалённых адресов в RU, никаких изменений PRIVATE. Три набора CIDR-ключей (глобальный, выбранный и региональный BGP) не изменились. Слой корпоративных origins вырос с 3 378 до 3 626 CIDR. Прошли 164 Python-теста, Go-тесты, независимый валидатор overlay, проверка hard/PRIVATE, все 14 официальных Telegram CIDR, gate дельты и проверка точного покрытия DAT/SRS через sing-box 1.13.12. Это проверка на фиксированных входах, не обещание нулевой дельты после обновления upstream.

[Таблица покрытия всех 32 ASN](V41_ASN_COVERAGE_EVIDENCE_20261115.tsv) содержит фактические результаты двух разных источников. Число префиксов RIS — за интервал, не точечный RIB. Колонки ipverse относятся строго к опубликованному снимку.

## Повторная проверка маршрута сайта RuVDS

RIPEstat DNS Chain независимо вернул `186.2.163.33` для [ruvds.com](https://stat.ripe.net/data/dns-chain/data.json?resource=ruvds.com) и CNAME на него для [www.ruvds.com](https://stat.ripe.net/data/dns-chain/data.json?resource=www.ruvds.com) в 06:23 UTC. Декомпилирован опубликованный [Geosite-ru-light RU SRS](https://github.com/SpeedeMiner/Geosite-ru-light/releases/tag/latest-optimized), SHA-256 `67a6a2a8c97bcd2bb035c36e080db92909c06698aff1e4147d8e84d0fcf4db96`, совпадает с опубликованной контрольной суммой. В нём уже есть `domain_suffix: ruvds.com`, покрывающий оба имени. При включённом правиле GeoSite RU, срабатывающем раньше общего PROXY, адрес сайта не нужно добавлять в GeoIP. Для клиентского профиля с только IP-маршрутизацией этот хост не покрыт, намеренно. HTTP-доступность из RU этим тестом не измерялась. GeoSite не менялся.
