# Точка восстановления — Geoip-ru-server

Обновлено: 2026-11-11 UTC. Audit-only branch: `docs/source-improvement-plan-2026-11`.

## Текущее состояние

- main: `580a25a7a65d957d46d83e827ccbd9308969713e`; production run #35 SUCCESS.
- Текущий v37 immutable release snapshot: commit `ac2e9a4322c0b7efe293983c88cf5b304771e4c5`; tag ref `latest-geoip-client-v37` при последней проверке был `f8015a10105f55a1d86ce2dc687a92ec30d3deb9` (не совпадает с release branch, хранить отдельно).
- `geoip_RU.dat`: 951553 bytes; SHA-256 `7ece8f277af01ba528b55c5af54f3cbb88224f3f2a65bc0558876992f9676d13`.
- PR #7: open Draft; latest validated HEAD `09cbe1db1cc4de7d50bdda59cca471532364f3fb`; latest CI [run #215](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43002597856) SUCCESS.
- Artifact ID `13847281344`, size 6,871,809 bytes; SHA-256 `6e5e4e31f53e46c621b85915239891c7ea1d5acb5bf6bf9c4aabc5c469645239`.
- PR base is `d6fa94a...`; current main is `580a25a...` (one main commit ahead). Не выполнять rebase/merge автоматически.

## Что было исправлено

Run #211 passed on an inconsistent pair of source snapshots: common root marker `ac2e9...` but canonical inventory had old `d613c5...` / GeoIP SHA `c7031007...`. Canonical inventory workflow now uses the release SHA resolved by the first step, verifies GeoIP/provenance sidecars, records per-file hashes in `v37-canonical-inputs.sha256` and compares RU/PRIVATE counters to the quality report from the same commit.

Run #212: ledger file was not yet present at the start of CI.
Run #213: TAB delimiter was overescaped in inline Python.
Run #214: verified GeoIP SHA was not copied into variable expected by builder.
Run #215: combined correction passed.

## Текущий v37 inventory

- 795017 unique exact CIDRs in union.
- RU output 76293 CIDR; PRIVATE 151.
- Selected-origin BGP 23564; RU RIR registered 13679; global 90-day BGP 520065; accepted additional GeoIP 193.
- Approved blocked exclusions 193285; blocked review candidates 28291 (not production exclusions).
- RIR interval coverage by RU output: 99.255239% IPv4 / 98.649940% IPv6.
- Selected-origin BGP interval coverage: 99.982380% IPv4 / 100% IPv6; 8658 IPv4 addresses outside RU output are all covered by PRIVATE or approved BLOCKED policy.
- 360 exact RIR RU residual prefixes (320 IPv4 / 40 IPv6), all REVIEW; residual unique address space = 328940 IPv4 and `11532729195086697206485771878400` IPv6.
- ipverse residual exact-origin: 123 observed, 237 not observed, 2 MOAS. No RU origin countryCode among the 123. 90-day absence is not a withdrawal verdict.
- MOAS: `92.51.48.0/21` and `193.238.192.0/22`; origins AS9009=RO + AS209372=US; both REVIEW/NO_CHANGE.

## Уже выполненные дополнительные проверки

- 57 priority prefixes: 53 exact MOAS + 4 company-only; all REVIEW.
- RDAP: 171/171 sample requests OK; 34 multi-object, 5 covering/unclassified, 18 exact resource at all sampled addresses.
- RPKI: 111 exact prefix/origin pairs; 66 valid, 20 invalid_asn, 25 unknown.
- IRR: 57 exact searches, 55 OK, one no exact object in query results, one no objects in queried RIPE/GRS scope; 42 origin-set differences.
- Archived-invalid reconciliation: 19 rows, all REVIEW (18 exact-scope, 1 more-specific-only).
- External spot-check ledger for the two residual MOAS: `.github/audits/rir_ru_residual_external_assessments_v37.tsv`.

## План следующего прохода

1. Независимый live exact RIB from RouteViews and RIPE RIS for all 123 BGP-observed residual NLRI, including origin, AS_PATH/peer distribution, collectors and timestamps.
2. Fetch same-time VRP snapshot and validate every exact prefix/origin pair; record maxLength per origin.
3. Check RDAP resource-holder hierarchy and exact IRR route objects for residual prefixes, beginning with both MOAS; preserve child/parent NLRI separately.
4. Investigate all 237 not observed in ipverse snapshot; absence is not proof of route withdrawal.
5. Add immutable raw upstream input snapshots (source catalog now has 38 validated metadata rows; raw GeoIP .dat feeds are not retained in release).
6. Build reviewed ADD/EXCLUDE/REVIEW diff with exact CIDR and address-space changes, then propose a separate data-only PR.
7. Design strict-RU output separately; do not alter legacy RU+BY+KZ+company semantics in this audit branch.

## Жёсткие границы

- PR #7 remains Draft; do not mark Ready or merge without explicit owner approval.
- Do not touch PR #5 or branch `feature/reachability-full-ru-kz-by`; no inspection/edit/CI/measurements for it.
- PR #6 remains a separate Draft workstream; don't retarget/merge it here.
- No production prefix files, production builder, company ASN allowlist, DIRECT policy, `geoip_RU.dat`, release, tag or main changes in this audit PR.
- Keep all unresolved candidates REVIEW; do not infer ownership or geography from ASN countryCode.
- Never project exact origin/ROA/IRR state between a parent and child prefix.
- Any merge into main triggers production release workflow, including docs-only changes.
