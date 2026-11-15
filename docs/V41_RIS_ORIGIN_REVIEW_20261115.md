# GeoIP v41 — контрольная точка аудита, 15 ноября 2026 (UTC+05)

Проверка только для аудита. Исходный `main` — [596c93df](https://github.com/SpeedeMiner/Geoip-ru-server/commit/596c93df3b65b36b34ef9a8c5472b9e9ee660691). Проверенный [выпускной снимок](https://github.com/SpeedeMiner/Geoip-ru-server/releases/tag/geoip-v41-snapshot-43617500418.1) — `7eef1efcaafbdbe259f3aa4e56a07c38979afbfb`, [Actions #43617500418](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43617500418). DAT SHA-256 `5d7e9dd0eb66bd507eb5f695b83441493fb20b2307ef71125de16c8b3809fa7d`. Никаких изменений маршрутизации, блокировок, workflows, PR #5, main или release.

## 44 CIDR — сверка ipverse и точных RIS-анонсов

Сопоставлены 23 603 уникальных CIDR из выпущенного `geoip_RU_BY_KZ_asn_bgp_prefixes.txt` (SHA-256 `cffb874ac49a46edba8da522bf9d9a905ff56b72d085150c61521971ceabfca2`) с точными ключами CIDR во всех `aggregated.json` выпуска (архив `d34d00d59ec419fec991d860af290b557a47b8e2f9596688b9bd11b0e4103d02`, проверен по provenance). Восстановлены 44 CIDR с дополнительным невыбранным ASN — 41 IPv4 и 3 IPv6. Это совпадение агрегированных ключей, а не само по себе свидетельство точного анонса или MOAS.

По каждому CIDR сопоставлен нормализованный **точный** `target_prefix` из [RIPEstat BGP State](https://stat.ripe.net/docs/data-api/api-endpoints/bgp-state). Origin — последний однозначный ASN в AS path. Сохранены UTC-время, ASN, количество путей, коллекторы, публичный URL и SHA-256 ответа в [таблице доказательств](V41_RIS_ORIGIN_EVIDENCE_20261115.tsv). По 44/44 CIDR есть пригодный ответ в каждом срезе, неоднозначных терминальных AS path — 0. Срезы — 14 ноября 16:50 UTC, на момент окончания публикации, и 15 ноября 03:59 UTC. Более поздний запрос RIPEstat подменял временем доступности данных и не использован. Число путей RIS не измеряет долю глобальных пользователей или доступность из РФ.

| Результат точного совпадения в RIS | 14.11 16:50 UTC | 15.11 03:59 UTC |
| --- | ---: | ---: |
| Видны выбранный и дополнительный ASN из ipverse | 35 | 36 |
| Виден только выбранный | 4 | 3 |
| Виден дополнительный без выбранного | 2 | 2 |
| Точный анонс не виден | 3 | 3 |

`185.29.56.0/22` — единственная смена группы: `AS60596` добавился к `AS60569` во втором срезе (70 и 291 пути соответственно). `AS208398` виден вместе с `AS13238` на 14 точных CIDR в обоих срезах. Это наблюдение, не основание импортировать весь AS208398. На `178.154.128.0/18` точного анонса не обнаружено даже отдельным запросом. Не объявлять пространство недоступным и не исключать по этому признаку.

### Два случая, где выбранный origin не наблюдается

| CIDR | Выбор сборки | RIS на обоих срезах | Текущая проверка RPKI | RIPE RDAP и покрытие |
| --- | --- | --- | --- | --- |
| `151.249.128.0/17` | `AS42772` (RIR BY, A1) | Только `AS44546`, 342 пути в 23 коллекторах | Обе пары valid по отдельным ROA | `CZ-ALFATELECOM-20120820`, country EU. Все 32 768 IPv4 в RU |
| `195.178.4.0/23` | `AS204720` (RIR RU, CDNETWORKS) | Только `AS44546`, 342 пути в 23 коллекторах | `AS204720 invalid_asn`, `AS44546 valid` | `CZ-ALFATELECOM-20091015`, country NL. Все 512 IPv4 в RU |

Одиночные запросы RIS подтвердили оба результата. RDAP country — атрибут записи, не география пользователей. RPKI — состояние на момент проверки около 06:00 UTC 15 ноября, не исторический статус ROA на момент публикации. [RDAP /17](https://rdap.db.ripe.net/ip/151.249.128.0/17) · [RDAP /23](https://rdap.db.ripe.net/ip/195.178.4.0/23) · [RPKI /17 AS42772](https://stat.ripe.net/data/rpki-validation/data.json?resource=AS42772&prefix=151.249.128.0%2F17) · [RPKI /17 AS44546](https://stat.ripe.net/data/rpki-validation/data.json?resource=AS44546&prefix=151.249.128.0%2F17) · [RPKI /23 AS204720](https://stat.ripe.net/data/rpki-validation/data.json?resource=AS204720&prefix=195.178.4.0%2F23) · [RPKI /23 AS44546](https://stat.ripe.net/data/rpki-validation/data.json?resource=AS44546&prefix=195.178.4.0%2F23).

Оба CIDR целиком присутствуют также в v37 base DAT. В v41 обе точные записи присутствуют в Hydra DIRECT и в `rir-rukzby-selected-origin-protected`. Нет пересечения с региональными RIR-ресурсами или действующими IP, resolver, subnet, hard/effective и Telegram-масками выпуска. Поэтому исправление только BGP-метки не исправит возможную маршрутизацию этих 33 280 IPv4. Наиболее сильное основание для отдельного пересмотра — `195.178.4.0/23`. Следующий шаг — проверить самостоятельное происхождение и смысл записи Hydra и более специфичные назначения, затем сравнить варианты исправления на тех же входах без публикации. До этого не добавлять AS44546 целиком и не вычитать оба CIDR автоматически.

## Точечная сверка 10 ранее отмеченных IPv4

Сверены девять [явно перечисленных legacy-only адресов](https://github.com/SpeedeMiner/Geoip-ru-server/blob/8e86656/docs/V41_LEGACY_HARD_EVIDENCE_AUDIT_20261112.md) и `185.76.151.1` из той же P4 записи с текущим снимком v41. Это не повтор старой 153-строчной матрицы. Все десять есть в v38 baseline, ни один не в PRIVATE или в текущем subnet.lst. Пять адресов только в текущем ip.lst, два в ip.lst и ipresolve.lst. В этом выпуске само присутствие в ip.lst не равнозначно действующему hard-исключению или подтверждённому блоку регулятора.

| IPv4 | В RU | ip.lst | ipresolve.lst | Hard | Effective | Official Telegram |
| --- | --- | --- | --- | --- | --- | --- |
| 46.254.18.79 | да | да | нет | нет | нет | нет |
| 46.254.18.115 | да | нет | нет | нет | нет | нет |
| 81.200.149.9 | да | да | да | нет | нет | нет |
| 88.223.91.1 | нет | нет | нет | нет | да | нет |
| 89.169.161.50 | да | да | нет | нет | нет | нет |
| 111.88.151.77 | да | да | нет | нет | нет | нет |
| 158.160.63.17 | да | да | нет | нет | нет | нет |
| 178.248.234.146 | да | да | да | нет | нет | нет |
| 178.248.236.100 | да | нет | нет | нет | нет | нет |
| 185.76.151.1 | нет | нет | нет | да | да | да |

Итого восемь адресов маршрутизируются DIRECT и семь имеют текущий ip.lst. Два оставшихся в DIRECT без подтверждения текущими ip.lst, ipresolve.lst, subnet.lst или Telegram — `46.254.18.115` и `178.248.236.100`. Для них и `88.223.91.1` нужна адресная сверка с независимо датированным источником, если пересматривается политика. Никаких реальных замеров блокировки или доступности этим проходом не сделано. Для Telegram ничего не менять.

## Состояние изменений по исходному аудиту

PR #35–#40 открыты, не слиты. Для последних head PR #40 завершились успешно сборки v41 и v39, и lint ([v41](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43682934371), [v39](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43682934379), [lint](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43682934373)). Исключение 262 IPv4 из источника W1ZARDZ находится в PR #38, в проверенном production его нет. Остальное по инженерному аудиту — коррекция терминологии и provenance BGP, верификация двух спорных CIDR и вопросы защиты веток, неизменяемости выпусков и документации/атрибуции.

## Fixed-input follow-up — isolate origin and Hydra layers

Rebuilt the v37 Go base and v41 Python overlay on the same released input bytes. Control reproduced the released v37 base, v41 DAT and effective exclusion mask byte for byte. Shadows are not release candidates. In the origin-only experiment, omit exactly the two CIDR rows from the selected-origin input of the base and the v41 regional-origin sidecar, keeping the global observation set unchanged. In the Hydra-only experiment, subtract exactly the same two address ranges from Hydra DIRECT, with PRIVATE and WHITELIST unchanged. The combined experiment applies both isolated input changes. All other inputs are identical.

| Fixed-input test | v37 base loss | Final v41 DIRECT loss |
| --- | ---: | ---: |
| Selected-origin records only | 256 IPv4 (`195.178.4.0/24`) | 0, DAT byte-identical |
| Hydra DIRECT only | 0 | 0, DAT byte-identical |
| Both layers | 256 IPv4 (`195.178.4.0/24`) | 256 IPv4 (`195.178.4.0/24`) |

No additions, no IPv6 or PRIVATE changes. The effective block mask is byte-identical in every case. The combined shadow DAT SHA-256 is `e05e6f02df363e3477fe165c422325ecd3d67994c50f974ac03774846c216f0a`. Baseline DAT, rather than a live-updated input run, is the comparator.

- The published Hydra [202611141017](https://github.com/hydraponique/roscomvpn-geoip/releases/tag/202611141017) text archive and the upstream binary pinned in v41 place both exact CIDRs in `DIRECT`, not `WHITELIST`. Neither address range intersects the three manual CUSTOM lists in the tagged tree. Hydra's build uses both RU/BY geolocation inputs and ASN datasets, with AS204720 explicitly in the configuration. The frozen per-input databases needed to identify the exact Hydra upstream cause are not attested by the text output or config alone. The release tag's Git-tree copy of `release/geoip.dat` does not have the cited release asset's checksum. For this check use the actual asset pinned by the v41 provenance, not the Git-tree copy. [Hydra input config](https://github.com/hydraponique/roscomvpn-geoip/blob/e8fa068fb4927970a8e5677269f0095c57352b6d/config.json)
- `151.249.128.0/17` is in the trusted Loyalsoldier and v2fly BY inputs. Davoyan RU also covers it, independently of the output labels in the ASN sidecar. Preserve until the actual BY service or assignment evidence is reviewed separately.
- `195.178.5.0/24` is in both trusted v2fly and Loyalsoldier RU inputs and in several additional feeds. The adjacent `195.178.4.0/24` is in the Davoyan RU feed but not in those two trusted RU inputs or the Digne/Grimbird/Golukon RU categories of this snapshot. Outside Hydra and selected ASN there is therefore not enough admitting evidence for that half under this replay. Source overlaps are not claims of independent observations. Focus the next address-level assignment and service check on `195.178.4.0/24`; don't exclude the whole /23 or treat the simulated 256-address loss as a publication decision.
