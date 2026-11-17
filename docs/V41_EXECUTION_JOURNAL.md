# v41 — краткий changelog

Журнал описывает изменения кода и политики в `main`. Опубликованные наборы
DAT и SRS определяются отдельно по версионированному снимку GitHub Releases.

- [№56](https://github.com/SpeedeMiner/Geoip-ru-server/pull/56) — закреплены Direct by Reachability, явный вклад Hydra DIRECT/WHITELIST, точные правила допуска и временное сохранение шести IPv4 `/24` с проверкой полного покрытия после исключений. Добавлены проверки маршрутизации в Xray и sing-box.
- [№54](https://github.com/SpeedeMiner/Geoip-ru-server/pull/54) — диагностика jsDelivr раздельно сверяет каталоги, байты доставки и GitHub Release.
- [№52](https://github.com/SpeedeMiner/Geoip-ru-server/pull/52) — усилена валидация зеркал до записи provenance. Отчёты о дельте DIRECT, ASN, Antifilter и provider/Hydra сопоставляются с одной закреплённой базой на PR.
- [№55](https://github.com/SpeedeMiner/Geoip-ru-server/pull/55) — добавлены offline-восстановление входов и сверка клиентских файлов по закреплённому манифесту.

**Ручной пересмотр шести `/24` — 2026-12-17.** Дата не удаляет маршруты автоматически.
[Правила и префиксы](GEOIP_RU_V41_POLICY.md#ручной-пересмотр-шести-24)

[Полный исторический журнал до сокращения](https://github.com/SpeedeMiner/Geoip-ru-server/blob/897cbee88ed22604b328d8d8ab8d5abc18c86ea0/docs/V41_EXECUTION_JOURNAL.md)
