# v41 — сверка шести временных /24 перед точечными замерами

Срез RIPE RIS **17 ноября 2026, 00:00 UTC**. Проверено 17 ноября по RIPEstat Prefix Overview, Routing Status, RIPE NCC RPKI Validator и RDAP. Сверка относится к шести прежним /24 из опубликованного `63b8abf`, временно сохранённым в кандидате [PR №56](https://github.com/SpeedeMiner/Geoip-ru-server/pull/56) до 2026-12-17. Это не те 18 CIDR, которые кандидат добавляет относительно релиза. Сервисные адреса и доступность не выводятся из BGP, ROA или страны регистрации.

| Префикс | Исторический ASN в override | Точный origin RIPE RIS и видимость | Свежая RPKI для фактического origin | Точный RDAP |
|---|---|---|---|---|
| `156.224.80.0/24` | AS219216 | [AS401650, 320/321](https://stat.ripe.net/data/routing-status/data.json?resource=156.224.80.0%2F24) | [valid](https://stat.ripe.net/data/rpki-validation/data.json?resource=AS401650&prefix=156.224.80.0%2F24) | [HK, ASSIGNED PA](https://rdap.afrinic.net/rdap/ip/156.224.80.0/24) |
| `156.241.186.0/24` | AS218568 | [AS401650, 320/321](https://stat.ripe.net/data/routing-status/data.json?resource=156.241.186.0%2F24) | [valid](https://stat.ripe.net/data/rpki-validation/data.json?resource=AS401650&prefix=156.241.186.0%2F24) | [HK, ASSIGNED PA](https://rdap.afrinic.net/rdap/ip/156.241.186.0/24) |
| `177.29.246.0/24` | AS39578 | [AS152606, 318/321](https://stat.ripe.net/data/routing-status/data.json?resource=177.29.246.0%2F24) | [valid](https://stat.ripe.net/data/rpki-validation/data.json?resource=AS152606&prefix=177.29.246.0%2F24) | [HK, Novacart-Commerce-llc](https://rdap.db.ripe.net/ip/177.29.246.0/24) |
| `177.122.107.0/24` | AS57227 | [AS152606, 318/321](https://stat.ripe.net/data/routing-status/data.json?resource=177.122.107.0%2F24) | [valid](https://stat.ripe.net/data/rpki-validation/data.json?resource=AS152606&prefix=177.122.107.0%2F24) | [HK, Novacart-Commerce-llc](https://rdap.db.ripe.net/ip/177.122.107.0/24) |
| `177.122.160.0/24` | AS219225 | [AS152606, 318/321](https://stat.ripe.net/data/routing-status/data.json?resource=177.122.160.0%2F24) | [valid](https://stat.ripe.net/data/rpki-validation/data.json?resource=AS152606&prefix=177.122.160.0%2F24) | [HK, Novacart-Commerce-llc](https://rdap.db.ripe.net/ip/177.122.160.0/24) |
| `177.166.21.0/24` | AS219284 | [AS152606, 318/321](https://stat.ripe.net/data/routing-status/data.json?resource=177.166.21.0%2F24) | [valid](https://stat.ripe.net/data/rpki-validation/data.json?resource=AS152606&prefix=177.166.21.0%2F24) | [HK, Novacart-Commerce-llc](https://rdap.db.ripe.net/ip/177.166.21.0/24) |

- **6/6** точных /24 видны в RIS, ни один не анонсируется историческим ASN из override в этом срезе. Ответы RPKI показывают и ROA, авторизующие исторические ASN: это не делает их фактически наблюдаемыми origin. Два новых наблюдаемых origin — [AS401650 (VL)](https://stat.ripe.net/AS401650) и [AS152606 (LINK4 COMMUNICATION)](https://stat.ripe.net/AS152606). Не обобщать вывод на иные префиксы этих AS.
- **0/6** подтверждённых пар «сервисное имя + точный IPv4». Публичный поиск по всем префиксам и наблюдаемым origin не дал официальной сервисной точки с проверяемой привязкой к одному из этих /24. Данные источников — справочные. Адреса из CIDR не подставлялись, подсети не сканировались, VPN не запускался.
- **Следующий проверяемый шаг** — получить публично документированное имя сервиса (либо подтверждённую оператором точку), проверить его точный A, заново сверить origin и измерить из подтверждённой домашней сети РФ. Хранить DNS, TCP, TLS/SNI и HTTP отдельно. Временные overrides и дата пересмотра не меняются; отсутствие точки не означает блокировку.

Для `156.224.80.0/24` найдено косвенное почтовое свидетельство: [TXT SPF NetEase](https://dns.google/resolve?name=wm.spf.netease.com&type=TXT) содержит покрывающий `156.224.80.0/22`. SPF разрешает адресу исходящую отправку, но не публикует IP действующего сервиса. Ни один A-ответ для шести MX из DNS-среза `163.com` и `netease.com` не попал в проверяемый /24. Это не цель для HTTPS или вывод об отсутствии почтового сервиса.

## Отдельное добавление кандидата — 31.204.32.0/20

В [RIS](https://stat.ripe.net/data/routing-status/data.json?resource=31.204.32.0%2F20) одновременно наблюдались агрегат `31.204.32.0/20` от AS9009 (43/321 peers) и два более специфичных маршрута `31.204.32.0/21` и `31.204.40.0/21` от AS213541. Два /21 покрывают весь /20: при наличии этих маршрутов BGP longest-prefix match выбирает их, а не агрегат. [RPKI агрегата AS9009](https://stat.ripe.net/data/rpki-validation/data.json?resource=AS9009&prefix=31.204.32.0%2F20) — `invalid_asn`. Обе пары AS213541 /21 — `valid` ([первый](https://stat.ripe.net/data/rpki-validation/data.json?resource=AS213541&prefix=31.204.32.0%2F21), [второй](https://stat.ripe.net/data/rpki-validation/data.json?resource=AS213541&prefix=31.204.40.0%2F21)). Exact [RIPE RDAP](https://rdap.db.ripe.net/ip/31.204.32.0/20) — `WSAU`, AU.

Вывод: **REVIEW**. Не считать весь /20 сетью M247, географическим RU, подтверждённым CDN или заведомо недоступным. Учитывать, что этот блок пересекается с явным Hydra DIRECT. BGP и RPKI не подтверждают сервисную точку и не меняют маршруты. Перед публикацией рассматривать два /21 отдельно, если будут подтверждены сервисные IP и домашние замеры. Остальные 17 добавленных CIDR — в [отдельной очереди](V41_CANDIDATE_ADDITIONS_REVIEW_20261117.md).

## Статус VPN

[Linux CI reachability](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/44038929934) — проверка на push, не VPN-замер. На момент сверки [PR №5](https://github.com/SpeedeMiner/Geoip-ru-server/pull/5) оставался черновиком, файла `reachability-vpn-gate.yml` в `main` нет. Нынешний ручной workflow описан в [EXACT_PROBE.md](https://github.com/SpeedeMiner/Geoip-ru-server/blob/feature/reachability-full-ru-kz-by/.github/reachability/EXACT_PROBE.md), но готового набора подтверждённых целей для шести /24 нет. Выход волонтёрского VPN, даже если он проверен как российский, не подтверждает домашнюю сеть.

Повтор публичного DNS: A сайта `link4bd.com` (и `www`) находится вне четырёх /24, куда RIS относит AS152606. Справочное имя `888venturesllc.com` и его `www` вернули NXDOMAIN в выбранном публичном резолвере. Точных сервисных пар для всех шести /24 всё ещё 0/6. Не делать вывод о других хостах или маршрутах из одного резолвера.

## Изменение критерия замера

Ручной домашний выход больше не требуется. Для текущего ревью пользователь разрешил считать достаточным проверенный российский выход VPNObratno. [Два контрольных замера](V41_VPNOBRATNO_CONTROL_MEASUREMENT_20261117.md) подтвердили работоспособность метода для IPv4, но их четыре адреса вне этих шести /24. Исторические описания выше фиксируют прежние условия. В текущей очереди 0/6 подтверждённых целей.

## Яндекс DNS через российский VPNObratno — 17 ноября

[Измерены UDP/53 и проверенный по сертификату DoT/853](V41_YANDEX_VPN_DNS_MEASUREMENTS_20261117.md). В 16 различных DNS-only именах нет текущего A внутри шести /24. Историческая привязка `156.224.80.166` дополнительно проверена по шести публичным именам и не воспроизведена. Контрольные HTTPS-адреса CDN77/CDNvideo вне очереди. **0/6**, все остаются на ревью до даты пересмотра. Отсутствие совпадения не означает блокировку и не меняет DIRECT.

## Точечная попытка получить сертификат 156.224.80.166

С двух российских выходов VPNObratno (AS8359, AS6863) `156.224.80.166:443` дал TCP-тайм-аут до TLS. Два контрольных адреса на каждом выходе ответили с валидным TLS и HTTP 200. Сертификат и новые имена не получены. Это оставляет первую историческую зацепку неподтверждённой и не характеризует другие адреса `156.224.80.0/24`. Статус 0/6. [Прогоны и JSON](V41_CERTIFICATE_LEAD_156_224_80_166_20261117.md).

## Повтор через VPNObratno и проверка исходных входов кандидата

В 24 новых DNS-only именах нет A внутри очереди. Единственный исторический PTR и шесть обратных зон повторили NXDOMAIN через три российских ASN. [Отчёт со снимками, артефактами и точными совпадениями](V41_SERVICE_LEADS_SOURCE_TRACE_20261117.md). Закреплённые Hydra и Loyalsoldier не пересекаются с /24. В закреплённом v2fly пять сетей покрываются US, одна DE. Selected sidecar получил шесть меток от самих `[STATIC-DIRECT]`; исходный ipverse исторические origin не подтвердил. Это не повод менять маршруты без актуальной сервисной пары. `2026-12-17` — ручной пересмотр, не автоистечение. **0/6**.
