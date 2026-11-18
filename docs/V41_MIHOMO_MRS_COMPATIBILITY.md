# Совместимость mihomo MRS с v41

## Экспорт RU и блокировка PRIVATE

`geoip_RU.mrs` (`ipcidr`) собирается из `RU` в Full DAT. Конвейер
декомпилирует MRS и RU SRS и сравнивает объединения IPv4- и IPv6-интервалов
всех трёх представлений. Расхождение останавливает сборку и публикацию.

| Файл | GitHub Release | jsDelivr |
| --- | --- | --- |
| `geoip_RU.mrs` | [MRS](https://github.com/SpeedeMiner/Geoip-ru-server/releases/download/latest-geoip-client-v41/geoip_RU.mrs) | [MRS](https://cdn.jsdelivr.net/gh/SpeedeMiner/Geoip-ru-server@cdn/geoip_RU.mrs) |
| `geoip_RU.mrs.sha256sum` | [SHA-256](https://github.com/SpeedeMiner/Geoip-ru-server/releases/download/latest-geoip-client-v41/geoip_RU.mrs.sha256sum) | [SHA-256](https://cdn.jsdelivr.net/gh/SpeedeMiner/Geoip-ru-server@cdn/geoip_RU.mrs.sha256sum) |

Для подключения см. [пример mihomo в README](../README.md#4-порядок-правил-в-xray-sing-box-и-mihomo).
Правило `GEOIP,PRIVATE,DIRECT,no-resolve` использует `PRIVATE` из штатного
DAT MetaCubeX при `geodata-mode: true`. Его покрытие не обязано совпадать с
v41 `PRIVATE`. Не подставляйте v41 DAT как `geox-url.geoip` в этой версии
mihomo: при загрузке GeoIP-базы проверяется наличие `CN`.

Проверены официальные Linux amd64 сборки `v1.19.34` и `alpha-2be2f08`.
На DAT из [снимка v41](https://github.com/SpeedeMiner/Geoip-ru-server/releases/tag/geoip-v41-snapshot-44242803054.1)
с SHA-256 `7e1d3221f1938260d83f0676cf13739a6fda9ef7647e6d1d1b867a3fcbd407db`
обратная конвертация `RU` сохранила IPv4/IPv6-покрытие. Обе сборки
восстановили `::ffff:0:0/96` из категории `PRIVATE` как `0.0.0.0/0`.
Дельта относительно DAT и декомпилированного sing-box `PRIVATE` составила
**+3 702 258 434 адреса IPv4 и −4 294 967 296 адресов IPv6**.

Проблема не ограничивается отображением текста. [Двоичный загрузчик mihomo](https://github.com/MetaCubeX/mihomo/blob/v1.19.34/component/cidr/ipcidr_set_bin.go)
применяет `Unmap()` к обеим границам IPv4-mapped IPv6-диапазона при чтении
MRS v1. Этот же путь использует [стратегия `ipcidr`](https://github.com/MetaCubeX/mihomo/blob/v1.19.34/rules/provider/ipcidr_strategy.go)
при загрузке rule-provider. Представление MRS v1 не различает IPv4 и
соответствующие IPv4-mapped IPv6 границы. Исключение префикса из экспорта
или трактовка подмены как эквивалентности нарушит точное покрытие v41.

Штатный сборщик не имеет режима `PRIVATE`. Регрессионный тест повторяет
ошибку на отдельной временной фикстуре без создания `geoip_PRIVATE.mrs`.
Сборщик и релизный манифест отклоняют оба имени `geoip_PRIVATE.mrs` и
`geoip_PRIVATE.mrs.sha256sum`; в списках публикации их нет. График,
правила отбора, DAT и оба SRS не меняются.

## Локальная проверка на Linux amd64

Возьмите `geoip_RU.dat`, `geoip_RU.srs` и `geoip_RU_v41_manifest.json` из
одного снимка. Укажите их пути в `DAT`, `RU_SRS` и `POLICY_MANIFEST`.
Загрузчик сверяет SHA-256 обоих официальных архивов до распаковки,
а сборщик дополнительно проверяет SHA-256 распакованного mihomo.

```bash
set -euo pipefail
tools="$(mktemp -d)"
output="$(mktemp -d)"
source .github/scripts/install_v41_rule_compilers.sh
install_v41_sing_box "$tools"
install_v41_mihomo "$tools"
V41_TEST_MIHOMO="$tools/mihomo" V41_TEST_SING_BOX="$tools/sing-box" python3 -m unittest discover \
  -s .github/scripts -p 'test_build_v41_mrs.py' -v
python3 .github/scripts/build_v41_mrs.py --mihomo "$tools/mihomo" --sing-box "$tools/sing-box" \
  --full "$DAT" --ru-srs "$RU_SRS" --manifest "$POLICY_MANIFEST" --output "$output"
(cd "$output" && sha256sum -c geoip_RU.mrs.sha256sum)
```

Фактический синтаксис обратной конвертации в проверенной версии —
`mihomo convert-ruleset ipcidr mrs input.mrs output.txt`. С флагом
`--verify-only` сборщик заново проверяет уже существующий MRS и его
контрольную сумму, ничего не пересобирая.
