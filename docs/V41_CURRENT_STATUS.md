# GeoIP v41 — актуальная точка продолжения

Снимок по состоянию на 15.11.2026, 23:58 UTC+05. При продолжении сверять ветки, PR и Actions с GitHub. Это не история всех PR и не разрешение на новые слияния или публикацию.

## Слияние №35–42 завершено

Все восемь PR отмечены GitHub как **Merged**. [PR №43](https://github.com/SpeedeMiner/Geoip-ru-server/pull/43) слил пакет в `main` в 17:04 UTC+05. Коммит пакета `75a0a40` подтверждён в first-parent истории `main`. Для дочерних PR ниже указан коммит слияния из карточки GitHub. Общий SHA для нескольких PR закономерен и не означает отдельного слияния каждого PR после №43.

| PR | Статус | Коммит слияния или HEAD открытого PR | Что сделано |
| --- | --- | --- | --- |
| [№35](https://github.com/SpeedeMiner/Geoip-ru-server/pull/35) | Слит в `main` | [`67fb23b`](https://github.com/SpeedeMiner/Geoip-ru-server/commit/67fb23b7ae73b4e65bff9573a9424357fdd78176) | Архив блокирующих входов и проверка публичных файлов |
| [№36](https://github.com/SpeedeMiner/Geoip-ru-server/pull/36) | Слит в `main` | [`67fb23b`](https://github.com/SpeedeMiner/Geoip-ru-server/commit/67fb23b7ae73b4e65bff9573a9424357fdd78176) | Нормализация и дедупликация IANA |
| [№37](https://github.com/SpeedeMiner/Geoip-ru-server/pull/37) | Слит в `main` | [`67fb23b`](https://github.com/SpeedeMiner/Geoip-ru-server/commit/67fb23b7ae73b4e65bff9573a9424357fdd78176) | Воспроизведение RIR на исходную дату UTC |
| [№38](https://github.com/SpeedeMiner/Geoip-ru-server/pull/38) | Слит в `main` | [`67fb23b`](https://github.com/SpeedeMiner/Geoip-ru-server/commit/67fb23b7ae73b4e65bff9573a9424357fdd78176) | Исключение семи игровых маршрутов только из W1ZARDZ |
| [№39](https://github.com/SpeedeMiner/Geoip-ru-server/pull/39) | Слит в `main` | [`bc41b4e`](https://github.com/SpeedeMiner/Geoip-ru-server/commit/bc41b4e212868e400599a2e91e7e712cc54fb19b) | Клиентский канал jsDelivr только для DAT/SRS |
| [№40](https://github.com/SpeedeMiner/Geoip-ru-server/pull/40) | Слит в `main` | [`67fb23b`](https://github.com/SpeedeMiner/Geoip-ru-server/commit/67fb23b7ae73b4e65bff9573a9424357fdd78176) | Контроль блокирующих фидов и изоляция некорректной диагностики |
| [№41](https://github.com/SpeedeMiner/Geoip-ru-server/pull/41) | Слит в `main` | [`67fb23b`](https://github.com/SpeedeMiner/Geoip-ru-server/commit/67fb23b7ae73b4e65bff9573a9424357fdd78176) | Классификация 48 проверенных сервисных и операторских ASN |
| [№42](https://github.com/SpeedeMiner/Geoip-ru-server/pull/42) | Слит в `main` | [`67fb23b`](https://github.com/SpeedeMiner/Geoip-ru-server/commit/67fb23b7ae73b4e65bff9573a9424357fdd78176) | Четыре точечных IPv6-исключения AS218750 |
| [№43](https://github.com/SpeedeMiner/Geoip-ru-server/pull/43) | Слит в `main` | [`75a0a40`](https://github.com/SpeedeMiner/Geoip-ru-server/commit/75a0a4086cedab43f21e3c0b5da3a476f6dbe3df) | Пакетное слияние №35–42 |
| [№44](https://github.com/SpeedeMiner/Geoip-ru-server/pull/44) | Открыт, Draft | `b6086be` (HEAD) | Аудит A/B, доказательства по CDN и Hydra |
| [№45](https://github.com/SpeedeMiner/Geoip-ru-server/pull/45) | Слит в `main` | [`fab8870`](https://github.com/SpeedeMiner/Geoip-ru-server/commit/fab8870dd14e0dcad217fd60f5c5b86d3713609a) | Сохранение IPv6 при обработке одноразового итератора |
| [№46](https://github.com/SpeedeMiner/Geoip-ru-server/pull/46) | Открыт | `9f6153b` (HEAD) | Точная дельта DIRECT относительно закреплённого release |
| [№47](https://github.com/SpeedeMiner/Geoip-ru-server/pull/47) | Открыт | `6ff13cc` (HEAD) | Проверка содержимого зеркал до принятия |
| [№48](https://github.com/SpeedeMiner/Geoip-ru-server/pull/48) | Слит в `main` | [`c0d2a01`](https://github.com/SpeedeMiner/Geoip-ru-server/commit/c0d2a01ba1fb5f5c0e48965d614945348083a900) | Точная дельта Antifilter и последний проверенный живой ipresolve |

Старыми открытыми черновиками №15, №18, №19, №24 и №25 больше не считать. [№15](https://github.com/SpeedeMiner/Geoip-ru-server/pull/15) слит в `38f3682`. [№18](https://github.com/SpeedeMiner/Geoip-ru-server/pull/18), [№19](https://github.com/SpeedeMiner/Geoip-ru-server/pull/19), [№24](https://github.com/SpeedeMiner/Geoip-ru-server/pull/24) и [№25](https://github.com/SpeedeMiner/Geoip-ru-server/pull/25) закрыты без слияния этих PR. PR №5 и его ветка остаются отдельным потоком, без изменений из этой работы.

## Проверенные ветки и публикация

| Ref | SHA на момент проверки |
| --- | --- |
| `main` | `c0d2a01ba1fb5f5c0e48965d614945348083a900` |
| `release` | `e20cf733a13d92040134895ebd580b7c9060fa3b` |
| `cdn` | `8a226b83c82323c869054ca5b299612ad3a91e2d` |

После merge №48 штатный push-workflow [43747743430](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43747743430) успешно собрал и опубликовал [снимок `geoip-v41-snapshot-43747743430.1`](https://github.com/SpeedeMiner/Geoip-ru-server/releases/tag/geoip-v41-snapshot-43747743430.1). Тег указывает на `e20cf73`, манифест привязан к исходному `c0d2a01`. Отдельный ручной релиз не запускался. В логе публикации `CDN status: verified` и `CDN binaries unchanged`. Git-ветка `cdn` не сдвинулась, так как бинарники совпали. Состав дерева `cdn` и байты трёх файлов отдельно сверены по Git.

| Файл | Байт | SHA-256 в `release` и `cdn` |
| --- | ---: | --- |
| `geoip_RU.dat` | 512533 | `b17fe26ccdcb8d272e6233ec9686a514b309e9d75e75653313a75f329b70fae7` |
| `geoip_RU.srs` | 128392 | `c60b8a1de5d4d67478850d7f72b272044f536d7d592591fbbf75ac50129002b1` |
| `geoip_PRIVATE.srs` | 228 | `b9ea6381ea61e286298aea76c10cb85a252ff0d20c49d6de3527be1353c107c4` |

## Доказательства и следующий шаг

- [Пакет №35–42 на закреплённых входах](V41_PR35_42_FIXED_INPUT_INTEGRATION_20261115.json) и [сверка с CI №43](V41_PR43_CI_INTEGRATION_20261115.json). Дрейф Hydra между отдельными PR-кандидатами и точечные IPv6-исключения №42 — разные изменения.
- [Проверка Antifilter №48](V41_BLOCK_FEED_DELTA_20261115.md) и [Actions](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43746592388). Нулевая дельта была получена относительно прежнего `58ca38fe` в том PR run, а не относительно последующего релиза `e20cf73`. Подтверждённое живое скачивание не доказывает свежесть у источника. Отчёт запускается только для PR и не меняет release gate.
- Подробности ранних проходов остаются в [журнале v41](V41_EXECUTION_JOURNAL.md), [журнале CDN](V41_CDN_PUBLICATION_JOURNAL_20261115.md) и [журнале IPv6](V41_IPV6_ADMISSION_JOURNAL_20261115.md). Старые отметки Open/Draft в датированных записях — состояние на момент соответствующего прохода.
- Продолжать с текущих `main`, `release`, `cdn` и открытых №44, №46, №47. Перед следующим слиянием отдельно проверить актуальные HEAD, CI и пересечение задач с уже слитым №48. Не повторять слияние №35–42. В клиентский jsDelivr `@cdn` по-прежнему входят только три бинарника.
