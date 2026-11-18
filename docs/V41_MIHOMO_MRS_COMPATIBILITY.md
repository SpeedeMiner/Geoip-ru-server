# Совместимость mihomo MRS с v41

## Блокер публикации

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

Пока официальный бинарник не проходит этот тест на неизменённом DAT,
публикация обоих MRS, ссылки на них и изменения схемы релизного манифеста
отложены. Workflow, штатный график, DAT и SRS не меняются.

## Локальная проверка на Linux amd64

Возьмите `geoip_RU.dat` и `geoip_RU_v41_manifest.json` из одного снимка.
Скрипт сверяет исходный DAT с манифестом, берёт из него только канонические
`RU` и `PRIVATE` и записывает выходные файлы с контрольными суммами лишь при
совпадении обоих семейств в обеих категориях. Рабочий каталог для результатов
лучше создать заново, чтобы не смешивать их с файлами предыдущих запусков.

```bash
set -euo pipefail
tools="$(mktemp -d)"
output="$(mktemp -d)"
archive=mihomo-linux-amd64-compatible-v1.19.34.gz
curl --proto '=https' --proto-redir '=https' --fail --location \
  "https://github.com/MetaCubeX/mihomo/releases/download/v1.19.34/$archive" \
  --output "$tools/$archive"
printf '%s  %s\n' 2763f5b414527f7baf6dc57e3f82f3ab561eedf34bfd7c2f2cde1f7e592efe06 \
  "$tools/$archive" | sha256sum -c -
gzip -dc "$tools/$archive" > "$tools/mihomo"
chmod 0755 "$tools/mihomo"
V41_TEST_MIHOMO="$tools/mihomo" python3 -m unittest discover \
  -s .github/scripts -p 'test_build_v41_mrs.py' -v
python3 .github/scripts/build_v41_mrs.py --mihomo "$tools/mihomo" \
  --full "$DAT" --manifest "$POLICY_MANIFEST" --output "$output"
```

На опубликованном v41 последний вызов завершится с ошибкой покрытия и не
запишет ни одного MRS или `.sha256sum`. Фактический синтаксис обратной
конвертации в проверенной версии — `mihomo convert-ruleset ipcidr mrs input.mrs output.txt`.
