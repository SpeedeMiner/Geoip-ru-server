# Reachability implementation work log

Durable resume point for PR #5. After any conversation/network interruption, read this file and CHECKPOINT.json, query the live PR head and Actions runs, then continue from the first pending phase. Do not restart completed work.

## Current repository state

- Repository: SpeedeMiner/Geoip-ru-server
- PR: https://github.com/SpeedeMiner/Geoip-ru-server/pull/5
- State: OPEN / DRAFT; no automatic merge.
- Branch: feature/reachability-full-ru-kz-by
- Current main: a68e5d6589361814cb1cfedd2af7857e4af806fa; PR branch merge-base remains c71b5eff48f34b363ef2430ba6b5c41603f36126 (29 commits behind, 72 commits ahead; current diff is isolated to the 11 reachability files)
- Latest validation commit: 42d6297dd1918c0b5380228036e3489e5df05266. Latest full-measurement run executed on temporary-trigger commit 7acb180836ae1de16687333f5c8a55b2a8b3a0dc; the temporary path-scoped push trigger was removed in commit 533281109e101b81f7b0ff623c011f698e56bc6a. Current branch head after cleanup: 533281109e101b81f7b0ff623c011f698e56bc6a.
- Latest successful validation commit: 854381b06c08267416dc8bf20311e56a549c72bd. Documentation/checkpoint commits may advance branch HEAD; always query the live PR head on resume.
- The full-measurement workflow has manual dispatch on this feature branch. Its daily cron becomes active only after the workflow is merged into the repository default branch. The temporary push trigger has been removed.
- Main GeoIP builder, release branch, and published geoip_RU.dat were not modified. The client remains one file with exactly RU and PRIVATE categories.

## Implemented

- Go exporter reads the exact published release/geoip_RU.dat and exports every RU and PRIVATE prefix. It rejects unexpected/duplicate categories, duplicate/non-canonical/default-route CIDRs, malformed entries and RU/PRIVATE overlap.
- Latest inventory from the current published v37 release: 76,231 RU CIDRs + 151 PRIVATE CIDRs = 76,382 rows. The older full run inventory (76,268 RU CIDRs) is superseded.
- Thirty seed hostnames are configured: two control targets plus 28 RU/KZ/BY service endpoints. Each is probed from all configured RU/KZ/BY source networks. Every newly added target includes an optional reference_url to an official, regulator or government source. This is an expanded pilot, not a comprehensive domain/API inventory.
- Globalping providers are discovered at run time by country + ASN + eyeball-network. Returned probe country, ASN and tags are verified.
- The fair scheduler emits complete four-test bundles (DNS A, DNS AAAA, HTTPS IPv4, HTTPS IPv6), visiting every provider before assigning another target to any provider. Country/provider and target selection rotate by UTC date. Budgets never split bundles.
- OONI web_connectivity observations are collected separately. OONI anomalies remain unconfirmed review signals, not automatic block verdicts.
- Optional RIPE Atlas TLS measurements are skipped explicitly because RIPE_ATLAS_API_KEY is not configured.
- Classification is conservative: HTTP response is observed HTTP reachability; DNS result is separate; timeout/TLS/reset remains inconclusive; missing IPv6 probe is NO_IPV6_PROBE; no automatic BLOCKED_CONFIRMED result exists.
- Reports include raw JSONL, provider TSV, per-provider/prefix TSV, exact provider/IP TSV, all-prefix TSV and summary JSON. Exact addresses are checked against the prefix shown in the row.

## Latest validation

- CI run: [run #71](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/42867134580)
- Commit tested: `42d6297dd1918c0b5380228036e3489e5df05266`
- Result: SUCCESS. Python 26/26 tests passed; Go formatting, Go tests and Go build passed. This validates the expanded 30-target JSON catalogue and the current collector/exporter code.

## Latest complete measurement run — current published v37 + 30 targets

- Run: [Full reachability RU KZ BY #5](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/42867329770)
- Run ID: `42867329770`; executed on commit `7acb180836ae1de16687333f5c8a55b2a8b3a0dc`.
- Measurement code and target catalogue: 30 hostnames; temporary branch-only push trigger was path-scoped to `targets.json` and `reachability-full.yml`, then removed. Current branch head after removing it: `533281109e101b81f7b0ff623c011f698e56bc6a`.
- Artifact: `geoip-ru-reachability-42867329770`, artifact ID `13787468458`, size 1,077,344 bytes, SHA-256 `30d64922b2779139256d355b644b6dba41e1a7152877c19222b1b14cb4fc9512`; expires 2026-12-10 17:42:29 UTC.

### Current GeoIP inventory

- Downloaded the exact current published `release/geoip_RU.dat` and verified the sidecar checksum.
- Complete inventory: 76,231 RU prefixes + 151 PRIVATE prefixes = 76,382 rows. All CIDRs are canonical and unique; RU/PRIVATE do not overlap.
- Current v37 release protobuf: 950,909 bytes; SHA-256 `cbe460b3c352dcf33f055e488f15e15caccfb6487e71e0e3ea81d508cda9bad1`.

### Expanded target catalogue

- 30 hostnames: two control targets and 28 service targets.
- Added 19 service targets: RU (`gosuslugi.ru`, `government.ru`, `cbr.ru`, `mail.ru`, `wildberries.ru`, `avito.ru`, `dzen.ru`, `rutube.ru`); KZ (`gov.kz`, `halykbank.kz`, `qazpost.kz`, `kcell.kz`, `tele2.kz`); BY (`government.by`, `president.gov.by`, `pravo.by`, `belarusbank.by`, `kufar.by`, `nbrb.by`).
- Each added hostname has a `reference_url` pointing to an official operator, government or regulator source. The list remains a seed catalogue, not a complete brand/API/mobile-app hostname inventory.

### Globalping measurement

- Online probes: 5,536; distinct country/ASN provider pairs found: 39; covered 39/39; uncovered 0. Pair distribution: RU 30, KZ 6, BY 3.
- 180 tasks = 45 complete four-measurement bundles, zero partial bundles, five max concurrent measurements.
- Results: ACCESSIBLE=40, DNS_ANSWER=56, DNS_NO_ANSWER=34, INCONCLUSIVE=12, NO_IPV6_PROBE=38, API_ERROR=0.
- Returned probe-country-tagged results: RU 113, KZ 18, BY 11. NO_IPV6_PROBE means no suitable IPv6 probe was found; it is not an IPv6 blocking result.

### Prefix and exact-IP report validation

- All 76,231 RU prefixes are present in `reachability_by_prefix.tsv`.
- Prefix status: 28 `ENDPOINT_ACCESSIBLE_OBSERVED`; 14 `DNS_RESOLVED_HTTP_NOT_CONFIRMED`; 2 `DNS_RESOLVED_HTTP_INCONCLUSIVE`; 76,187 `NO_MATCHED_ENDPOINT`.
- Provider reports: 62 provider/prefix rows and 71 provider/exact-IP rows. The aggregated provider/prefix IP sets reconcile exactly to the provider/IP table when grouped by country/ASN/prefix; zero mismatches.
- All 71 provider/IP addresses are inside their stated canonical prefix.
- Observations matched 44 RU prefixes (some prefixes have multiple target IDs). The remaining 76,187 are not matched by this 30-host pilot; do not label them accessible or blocked.

### OONI and RIPE Atlas

- OONI observations: 987; anomaly-review signals: 19; confirmed=true: 0; failure=true: 0.
- Anomaly distribution: 12 repeated `kufar.by` records from RU AS39028; 1 `kufar.by` from BY AS61272; 2 `vk.com` from BY AS42772; 1 `ya.ru` from BY AS42772; 1 `dzen.ru` from RU AS35807; 2 `rutube.ru` from BY AS42772/AS12406. All 19 have `confirmed=false` and `failure=false`; they remain metadata-only review signals.
- RIPE Atlas was explicitly skipped because `RIPE_ATLAS_API_KEY` is not configured.

## Interpretation limits

- Globalping eyeball-network differentiates end-user-tagged probes from data-centre probes, but does not prove that each probe is a residential/home line. Some returned network names can be hosting/enterprise operators. Treat the country/ASN observations as vantage-point evidence, not a verified list of household subscribers.
- The 30 hostnames are still a pilot. In the latest run, 76,187 RU prefixes had no endpoint match; these remain untested by the current catalogue, not inaccessible or blocked.
- This is endpoint-based evidence for selected services, not a scan of every address in each CIDR.
- 35 missing IPv6 probes are a measurement coverage limitation, not evidence of IPv6 blocking.
- OONI anomalies are all unconfirmed; do not subtract their IPs from DIRECT.
- The workflow has not changed geoip_RU.dat or the two-category policy.

## Resume protocol

1. Read WORKLOG.md and CHECKPOINT.json.
2. Query PR #5 and use its current head SHA, not a remembered SHA.
3. Query recent Actions runs on feature/reachability-full-ru-kz-by.
4. Prefer the artifact from the latest successful full run; do not repeat a run whose artifact is still available and relevant.
5. Continue from CHECKPOINT.json current_phase / next_steps. Do not redo reconnaissance, exporter implementation, scheduler or green CI.
6. Work in short units: one focused change, CI, then checkpoint. Do not run full measurement after work-log-only changes.
7. After each meaningful phase, update both files and commit them. Documentation/checkpoint-only commits are excluded from push CI; PR validation runs only on opened/reopened/ready_for_review; the full-measurement workflow remains manual on this branch and daily after merge to default. Keep PR #5 Draft unless the owner explicitly approves final review and merge.

## Phase status

| Phase | State | Evidence |
|---|---|---|
| Repository reconnaissance | DONE | main and release trees inspected |
| Protobuf inventory exporter | DONE | full run #42861904056 |
| Globalping/OONI/Atlas collector | DONE | artifact #13786625472 |
| Fair provider scheduler | DONE | 38/38 provider pairs covered |
| Provider-prefix and exact-IP reports | DONE | 64 prefix rows, 77 IP rows, exact reconciliation |
| NO_IPV6_PROBE handling | DONE | 35 classified; API_ERROR 0 |
| CI validation | DONE | run #42863496776; 26 Python tests + Go checks |
| Full measurement and artifact review against current v37 release | DONE | run #42867329770; artifact #13787468458 |
| OONI review / final policy interpretation | DONE with caveats above | 19 anomalies; all confirmed=false and failure=false |
| Expanded 30-host target catalogue | DONE | 19 new sourced service endpoints; CI #71 and full run #5 passed |
| Final PR review / owner decision | PENDING | PR #5 remains Draft; owner must review target coverage and base-branch lag |

## Invariants

- Never alter geoip_RU.dat from this diagnostic workflow.
- Exactly RU and PRIVATE categories remain in the client file.
- PRIVATE has absolute priority.
- Timeout, reset, TLS failure, DNS error or OONI anomaly alone is never a block verdict.
- eyeball-network does not prove a residential/home connection.
- No policy inference is made for unused IPs in a CIDR.
