# GeoIP DIRECT RU + BY + KZ v41

## 1. Назначение и Direct by Reachability

Проект автоматически собирает IPv4/IPv6-базу для раздельного туннелирования. `geoip_RU.dat` содержит две категории для Xray/V2Ray — `RU` и `PRIVATE`. Из того же DAT собираются два SRS для sing-box и один MRS (`RU`) для mihomo.

**`RU` — категория маршрутизации, а не геолокация.** В неё входят сети RU/BY/KZ, выбранные анонсы региональных, корпоративных и облачных ASN, а также явно разрешённые сервисные маршруты. Для отдельного CDN-узла политика допускает только проверенный IP с подтверждением провайдера и положительным замером прямой доступности из российской сети. Чужие страновые категории целиком не импортируются. RIR, BGP, GeoIP и upstream-списки отражают разные виды свидетельств, поэтому попадание в `RU` не означает, что каждый адрес измерен из РФ или что на общем IP доступны все домены.

| Файл | GitHub Release | jsDelivr | SHA-256 |
| --- | --- | --- | --- |
| `geoip_RU.dat` · Xray/V2Ray | [DAT](https://github.com/SpeedeMiner/Geoip-ru-server/releases/download/latest-geoip-client-v41/geoip_RU.dat) | [DAT](https://cdn.jsdelivr.net/gh/SpeedeMiner/Geoip-ru-server@cdn/geoip_RU.dat) | [Контрольная сумма](https://github.com/SpeedeMiner/Geoip-ru-server/releases/download/latest-geoip-client-v41/geoip_RU.dat.sha256sum) |
| `geoip_RU.srs` · sing-box RU | [SRS](https://github.com/SpeedeMiner/Geoip-ru-server/releases/download/latest-geoip-client-v41/geoip_RU.srs) | [SRS](https://cdn.jsdelivr.net/gh/SpeedeMiner/Geoip-ru-server@cdn/geoip_RU.srs) | [Контрольная сумма](https://github.com/SpeedeMiner/Geoip-ru-server/releases/download/latest-geoip-client-v41/geoip_RU.srs.sha256sum) |
| `geoip_PRIVATE.srs` · sing-box PRIVATE | [SRS](https://github.com/SpeedeMiner/Geoip-ru-server/releases/download/latest-geoip-client-v41/geoip_PRIVATE.srs) | [SRS](https://cdn.jsdelivr.net/gh/SpeedeMiner/Geoip-ru-server@cdn/geoip_PRIVATE.srs) | [Контрольная сумма](https://github.com/SpeedeMiner/Geoip-ru-server/releases/download/latest-geoip-client-v41/geoip_PRIVATE.srs.sha256sum) |
| `geoip_RU.mrs` · mihomo RU | [MRS](https://github.com/SpeedeMiner/Geoip-ru-server/releases/download/latest-geoip-client-v41/geoip_RU.mrs) | [MRS](https://cdn.jsdelivr.net/gh/SpeedeMiner/Geoip-ru-server@cdn/geoip_RU.mrs) | [SHA-256 GitHub](https://github.com/SpeedeMiner/Geoip-ru-server/releases/download/latest-geoip-client-v41/geoip_RU.mrs.sha256sum) · [SHA-256 CDN](https://cdn.jsdelivr.net/gh/SpeedeMiner/Geoip-ru-server@cdn/geoip_RU.mrs.sha256sum) |

В `@cdn` размещаются четыре бинарника и контрольная сумма RU MRS. MRS будет доступен с первого успешного выпуска после включения этой сборки. Для воспроизводимой проверки берите файлы и `.sha256sum` из одного версионированного [снимка GitHub Releases](https://github.com/SpeedeMiner/Geoip-ru-server/releases), затем выполните в каталоге загрузки:

```bash
sha256sum -c geoip_RU.dat.sha256sum geoip_RU.srs.sha256sum geoip_PRIVATE.srs.sha256sum geoip_RU.mrs.sha256sum
```

**`geoip_PRIVATE.mrs` не создаётся и не публикуется.** Проверенная версия mihomo заменяет IPv6-префикс `::ffff:0:0/96` из `PRIVATE` на `0.0.0.0/0`. Для `PRIVATE` в mihomo используйте категорию из штатной GeoIP-базы MetaCubeX. [Проверка совместимости и воспроизведение](docs/V41_MIHOMO_MRS_COMPATIBILITY.md)

## 2. Источники данных и кураторский вклад

[Каталог GitHub-источников](.github/data/v41-upstream-sources.json) определяет репозитории и файлы. Для каждого источника сборка разрешает один commit или релиз, проверяет размер и идентичность Git blob или digest release asset. SHA-256 принятых байтов и точный URL фиксируются в provenance. У v2fly дополнительно сверяется опубликованный sidecar.

| Источник | Вклад | Проверка |
| --- | --- | --- |
| AFRINIC, APNIC, ARIN, LACNIC, RIPE NCC | Делегированные ресурсы IPv4/IPv6 и списки ASN RU/BY/KZ. Регистрация ресурса не доказывает местоположение сервера. | Реестр, дата UTC, количество строк и сводки по семействам. Некорректное зеркало отклоняется. |
| ipverse/as-ip-blocks | Анонсы IPv4/IPv6 выбранных региональных и корпоративных origin ASN. Общий набор BGP используется для сверки, а сам по себе не допускает префиксы в DIRECT. | Проверка gzip/tar и записей ASN перед приёмом зеркала. Точный архив привязан к provenance по размеру и SHA-256. |
| [Реестр корпоративных ASN](.github/data/geoip_RU_company_asns.tsv) и [политика классов](.github/data/geoip_RU_company_asn_policy.tsv) | Origin IPv4/IPv6 от кураторских ASN независимо от `countryCode` в ipverse. Классы `CORE_CORPORATE` и `SHARED_INFRA` сохраняются отдельно. | Проверка ASN и происхождения по выбранным анонсам. Маски классов не пересекаются по точным префиксам и вместе покрывают реестр корпоративных префиксов. |
| v2fly и Loyalsoldier | База v37. У v2fly используются `RU`, `BY`, `KZ`, у Loyalsoldier — `RU`, `BY`, `PRIVATE`. Оба семейства адресов. | Проверка protobuf, допустимых категорий и CIDR. |
| GrimbirdUsers, DigneZzZ, Davoyan, Golukon | Дополнительные RU-префиксы IPv4/IPv6. Требуется подтверждение независимыми группами, выбранным origin ASN либо RIR-RU. Grimbird и Digne считаются одной группой. | Проверка DAT и пересечений адресного пространства. Вклад считаётся поверх уже принятой базы. |
| Hydra (roscomvpn-geoip) | Явные категории `DIRECT` и `WHITELIST`, IPv4/IPv6. Это намерение маршрутизации, а не география и не исключение из блокировок. | Проверка DAT, точного вклада и сохранения допустимого покрытия после исключений. |
| Kyoresuas Standard, W1ZARDZ, Escapingworm | Сервисные маршруты. Kyoresuas даёт IPv4/IPv6, W1ZARDZ — IPv4, Escapingworm — явно настроенный операторский CIDR-список. | Схема `services.json`, семейства агрегатов и CIDR. [Исключения W1ZARDZ](.github/data/v41-w1zardz-gaming-exclusions.txt) действуют только на его вклад. |
| HXEHEX и Kirilllavrov | HXEHEX CIDR и IP-списки и `WHITELIST` из DAT Kirilllavrov используются для сравнения, без самостоятельного допуска в DIRECT. | Проверка источника и формата. Недоступность HXEHEX фиксируется отдельно и не меняет маршруты. |
| IANA Special-Purpose и встроенные диапазоны | `PRIVATE` для IPv4/IPv6 вместе с Loyalsoldier. Исключения `Globally Reachable=True` вычитаются из широких специальных сетей. | Проверка схемы CSV, семейств и полноты обоих реестров IANA. |
| Antifilter `ip.lst`, `ipresolve.lst`, `subnet.lst` и закреплённая история v38 | Точные хосты IPv4/IPv6 и ограниченные подсети. Данные DNS и история без отдельного подтверждения относятся к resolver-only. Подходящие подсети из `subnet.lst` поступают в жёсткую маску. | Проверка формата и минимального числа записей, SHA-256 истории, сравнение с предыдущим релизом. При пустом `ipresolve.lst` сохраняется закреплённая база v38. |
| Antifilter `ipsum.lst`, community и Re-filter | Подсказки для ревью. `ipsum.lst` агрегирует IPv4 по /24. Этот слой не вычитается автоматически. | Нормализация, счётчики и явный статус отсутствующих данных. |
| Telegram и [подтверждённые IP-записи РКН](.github/data/v41-reviewed-rkn-ip-records.tsv) | Жёсткие исключения. Для Telegram используются закреплённые маршруты и полный официальный IPv4/IPv6 CIDR-фид. | Схема и диапазоны, независимая проверка отсутствия пересечений с итоговым `RU`. |
| [Операторские префиксы](.github/data/v41-reviewed-operator-prefixes.tsv), [статические overrides](.github/data/v41-static-overrides.tsv), [временно сохраняемые /24](.github/data/v41-temporary-release-retention.tsv) | Точные кураторские дополнения, а не импорт целого ASN или доказательство свежего BGP. У overrides есть `added_date` и `review_after`, у сохранений — SHA прежнего релиза и `review_on`. | Проверка каноничности и уникальности CIDR, полей и дат. Для временно сохраняемых /24 проверяется полное итоговое покрытие после исключений. |
| [Проверенные CDN-хосты](.github/data/v41-reviewed-reachable-cdn.tsv), [IP-недоступность](.github/data/v41-reviewed-unreachable.tsv) и конфликты [IPv4](.github/data/v41-regional-admission-exclusions.tsv) / [IPv6](.github/data/v41-reviewed-ipv6-admission-exclusions.tsv) | Точечные правила допуска или исключения. CDN допускается только как /32 или /128. Для доступности и недоступности нужны доказательства и срок пересмотра. | Проверка типа и границ записи, источников доказательств, дат и привязки к манифесту. |
| RIPE RIS и [каталог глобальных провайдеров](.github/data/v41-audit-global-networks.json) | Сверка BGP и пересечений IPv4/IPv6 с провайдерскими сетями. | Только диагностический слой. Отсутствующий фид означает «неизвестно», а не нулевое пересечение. |

Вклад источников пересекается, поэтому объёмы покрытия нельзя складывать. Кураторская работа — это выбор origin ASN, классификация источников и проверка точных исключений и дополнений. [Реестр критичных сервисов](.github/data/v41-service-inventory.tsv) справочный и сам не создаёт правил.

## 3. Исключения и защита слоёв

- **`PRIVATE` имеет приоритет.** Его адресное пространство вычитается из `RU`. Отдельной маски всех публичных DNS-резолверов в сборщике нет. Маршрут до конкретного публичного резолвера задаётся отдельно в клиенте. `resolver-only` здесь относится к адресам заблокированных доменов, полученным через DNS, а не к IP самих резолверов.
- **Жёсткие исключения** действуют даже на защищённые маршруты. Это официальный Telegram, проверенные прямые IP-записи и ограниченные записи `subnet.lst` не шире /16 для IPv4 и /112 для IPv6. Произвольные широкие записи и агрегаты `ipsum.lst` остаются для ревью.
- **DNS-сигнал не равен IP-блокировке.** Из мягкой маски вычитается покрытие региональных ресурсов и выбранных origin ASN RU/BY/KZ, обоих классов корпоративной инфраструктуры, проверенных операторских префиксов и отдельных сервисных масок. Так один заблокированный домен не отправляет через VPN легитимные сервисы на том же адресе.
- **Географические конфликты и недоступность различаются.** Точное подтверждённое иностранное назначение не считается региональным DIRECT, но тот же адрес может пройти через независимое правило Hydra или как измеренный CDN-хост. Маска проверенной IP-недоступности действует вне защищённого ядра. Ошибка DNS, отказ для отдельного SNI или отсутствие анонса сами по себе не доказывают IP-блокировку.


**Шесть исторических IPv4 `/24` подлежат ручному пересмотру 2026-12-17.** Они временно остаются в `RU` по [точному реестру сохранения](.github/data/v41-temporary-release-retention.tsv). Это не доказательство текущего анонса, доступности из РФ или основание расширить допуск. Сохранение не отменяет приоритет `PRIVATE`, эффективной маски блокировок и правил допуска. Если после их применения хотя бы часть любого из шести диапазонов отсутствует в `RU`, кандидат не проходит проверку. Дата не удаляет префиксы автоматически. [Политика v41 и список шести диапазонов](docs/GEOIP_RU_V41_POLICY.md#ручной-пересмотр-шести-24)

## 4. Порядок правил в Xray, sing-box и mihomo

Сверху вниз: **домены, которым нужен PROXY → проверенные домены DIRECT → `PRIVATE` и `RU` через DIRECT → остальное через PROXY**. На одном CDN-адресе могут находиться и заблокированный домен, и разрешённый сервис. Поэтому при наличии имени доменное правило (`geosite:` или `domain`) должно сработать до `geoip:ru` или IP rule-set. Если приложение отдаёт только IP, остаётся IP-правило. Этот репозиторий не поставляет списки GeoSite.

В примерах замените домены `.example` своими и используйте соответствующие теги существующих outbound `proxy` и `direct`.

**Xray.** Поместите `geoip_RU.dat` в каталог assets. Фрагмент `routing` использует внешний DAT. Если файлом assets `geoip.dat` уже является эта сборка, можно вместо `ext:...` использовать `geoip:private` и `geoip:ru`. Для совпадения по IP при запросе с доменным именем нужен рабочий DNS. При `IPOnDemand` и отсутствии совпадений `proxy` должен быть первым outbound.

```json
{
  "routing": {
    "domainStrategy": "IPOnDemand",
    "rules": [
      {"type": "field", "domain": ["domain:blocked.example"], "outboundTag": "proxy"},
      {"type": "field", "domain": ["domain:local.example"], "outboundTag": "direct"},
      {"type": "field", "ip": ["ext:geoip_RU.dat:private"], "outboundTag": "direct"},
      {"type": "field", "ip": ["ext:geoip_RU.dat:ru"], "outboundTag": "direct"}
    ]
  }
}
```

**sing-box.** Скачайте оба SRS, укажите их пути и существующий тег DNS-сервера `dns-for-routing`. Действие `resolve` после доменных правил позволяет применить IP rule-set к разрешённому адресу.

```json
{
  "route": {
    "final": "proxy",
    "rules": [
      {"domain_suffix": ["blocked.example"], "action": "route", "outbound": "proxy"},
      {"domain_suffix": ["local.example"], "action": "route", "outbound": "direct"},
      {"action": "resolve", "server": "dns-for-routing"},
      {"rule_set": ["private"], "action": "route", "outbound": "direct"},
      {"rule_set": ["ru"], "action": "route", "outbound": "direct"}
    ],
    "rule_set": [
      {"type": "local", "tag": "private", "format": "binary", "path": "geoip_PRIVATE.srs"},
      {"type": "local", "tag": "ru", "format": "binary", "path": "geoip_RU.srs"}
    ]
  }
}
```

**mihomo.** Подключите RU MRS как `rule-provider`, а `PRIVATE` возьмите из штатного `geoip.dat` MetaCubeX в режиме `geodata-mode`. Не заменяйте этот DAT файлом v41 `geoip_RU.dat`: он не содержит `CN`, который mihomo проверяет при загрузке базы. Покрытие штатного `PRIVATE` может отличаться от v41. Существующие доменные правила ставьте выше этих правил, а `PROXY` замените именем своей группы. При `no-resolve` правило `PRIVATE` проверяет только уже известный IP, не вызывая DNS.

```yaml
geodata-mode: true
geox-url:
  geoip: https://github.com/MetaCubeX/meta-rules-dat/releases/download/latest/geoip.dat

rule-providers:
  geoip-ru:
    type: http
    behavior: ipcidr
    format: mrs
    url: https://cdn.jsdelivr.net/gh/SpeedeMiner/Geoip-ru-server@cdn/geoip_RU.mrs
    path: ./rule-providers/geoip_RU.mrs
    interval: 86400

rules:
  - GEOIP,PRIVATE,DIRECT,no-resolve
  - RULE-SET,geoip-ru,DIRECT
  - MATCH,PROXY
```

## 5. Сборка, контроль качества и CLI

[Workflow v41](.github/workflows/geoip-v41.yml) проверяет зеркала до записи provenance, извлекает origin ASN и собирает базу v37 на Go. [Overlay v41](.github/scripts/build_v41_overlay.py) объединяет и вычитает адресные интервалы отдельно для IPv4 и IPv6, затем сворачивает результат обратно в CIDR. Независимые проверки читают выходной protobuf, проверяют `PRIVATE`, жёсткие исключения, Telegram и потери покрытия приоритетных ASN.

[Компилятор SRS](.github/scripts/build_v41_srs.py) декомпилирует rule-set и сверяет IPv4/IPv6-покрытие с DAT. На PR [сквозной тест](.github/scripts/check_v41_client_dns_local.py) запускает Xray и sing-box в изолированной сети. Он проверяет литеральные IP, DNS, приоритет доменных правил и выбор outbound. Отчёты ASN и provider/Hydra для PR используют тот же закреплённый предыдущий release, что и точная дельта, и не меняют допуск маршрутов. Публикация — отдельная стадия после валидации кандидата.

[Сборщик MRS](.github/scripts/build_v41_mrs.py) использует официальный mihomo с закреплённым SHA-256. В сборке и перед публикацией он сверяет восстановленные IPv4- и IPv6-интервалы RU с DAT и декомпилированным RU SRS. Отчёт размеров включает MRS и его контрольную сумму.

| Утилита | Запуск и результат |
| --- | --- |
| [Предпубликационная проверка](.github/scripts/verify_v41_publication_candidate.sh) | В CI запускается как `bash ../.github/scripts/verify_v41_publication_candidate.sh` из `candidate/` с переменными workflow. CLI-флагов у обёртки нет. Проверяет манифест, SHA-256, архивы, Telegram, пороги и входы против закреплённого `release`. Ничего не публикует. |
| [Пороги публикации](.github/scripts/validate_v41_publication_bounds.py) | `python3 .github/scripts/validate_v41_publication_bounds.py --candidate "$CANDIDATE_DAT" --reference "$RELEASE_DAT"`. Убедитесь, что эталонный DAT совпадает со своим SHA-256. |
| [Точная дельта DIRECT](.github/scripts/report_v41_pr_delta.py) | `--candidate`, `--reference`, `--reference-checksum`, `--candidate-manifest`, `--reviewed-ipv6`, `--current-metrics`, `--previous-metrics`, `--revision`, `--summary`, `--exact-output`. `--revision` — полный SHA эталонного release. Отчёт разделяет добавления и удаления по семействам и фиксирует изменения `PRIVATE`. |
| [Обзор покрытия по ASN](.github/scripts/audit_v41_asn_regressions.py) | `--watchlist`, `--candidate`, `--output`. Для сравнения с прошлым снимком используются `--previous` и `--previous-release`. Отчёт различает наблюдаемые анонсы, выбранный origin и фактическую потерю DIRECT. |
| [Проверка jsDelivr](.github/scripts/audit_v41_cdn_public.py) | `python3 .github/scripts/audit_v41_cdn_public.py --diagnose-planes --edges --verify-snapshot`. Сверяет каталоги по закреплённому SHA и по rolling-ветке, фактические байты CDN и файлы GitHub Release, включая версионированный снимок. При расхождении возвращает ненулевой код. Не публикует и не сбрасывает кеш. |

**Offline-сверка.** Возьмите манифест `geoip_RU_v41_release_manifest.json` из закреплённого релизного коммита и независимо проверьте его SHA-256. `INPUTS` должен содержать `as-ip-blocks.tar.gz`, `v41-registry-inputs.tar.gz`, `v41-upstream-inputs.tar.gz`, `v41-block-inputs.tar.gz` и `geoip_RU_input_provenance.tsv` из того же снимка. `SOURCE_REPO` — локальный репозиторий с исходным коммитом из манифеста. `WORK` — новый каталог вне обоих входных каталогов.

```bash
python3 .github/scripts/verify_v41_snapshot_replay.py \
  --manifest "$MANIFEST" --manifest-sha256 "$MANIFEST_SHA256" \
  restore-inputs --inputs "$INPUTS" --source-repo "$SOURCE_REPO" --output "$WORK"

# После отдельной локальной сборки из восстановленных входов:
python3 .github/scripts/verify_v41_snapshot_replay.py \
  --manifest "$MANIFEST" --manifest-sha256 "$MANIFEST_SHA256" \
  compare-client --replay "$WORK"
```

Утилита проверяет архивы и provenance, восстанавливает исходные файлы и сверяет клиентские бинарники и суммы по схеме снимка. Схема 2 требует RU MRS и его контрольную сумму, схема 1 поддерживает прежние снимки без MRS. Утилита не скачивает данные, не запускает сборку и не публикует результат. [Подробная инструкция](docs/V41_OFFLINE_SNAPSHOT_REPLAY.md)
