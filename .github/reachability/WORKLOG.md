# Reachability implementation work log

Durable resume point for PR #5. After any conversation/network interruption, read this file and CHECKPOINT.json, query the live PR head and Actions runs, then continue from the first pending phase. Do not restart completed work.

## Current repository state

- Repository: SpeedeMiner/Geoip-ru-server
- PR: https://github.com/SpeedeMiner/Geoip-ru-server/pull/5
- State: OPEN / DRAFT; no automatic merge.
- Branch: feature/reachability-full-ru-kz-by
- Current main: a68e5d6589361814cb1cfedd2af7857e4af806fa; PR branch merge-base remains c71b5eff48f34b363ef2430ba6b5c41603f36126 (29 commits behind current main). The 11 changed files in PR #5 are confined to .github/reachability/** and the two separate diagnostic workflows; no main GeoIP builder, release or client data file is changed.
- Latest validation: run 42873343359 succeeded on commit 6e2ba2b15e49f4af9a6f00615f75a88d75d14f81. Python 27/27 tests, Go formatting, Go tests and Go build passed. The collector summary now computes per-country IPv6 probe gaps and source-country/target sampling metrics.
- Latest full measurement ran on temporary-trigger commit 7acb180836ae1de16687333f5c8a55b2a8b3a0dc; the temporary path-scoped push trigger was removed in commit 533281109e101b81f7b0ff623c011f698e56bc6a. Always query the live PR head on resume; documentation/checkpoint commits advance it.
- The previous validation commit 1b2152760b120218763956a8f7005f3bafa044e8 validated the Belarus reference-source corrections.
- The full-measurement workflow has manual dispatch on this feature branch. Its daily cron becomes active only after the workflow is merged into the repository default branch. The temporary push trigger has been removed.
- Main GeoIP builder, release branch, and published geoip_RU.dat were not modified. The client remains one file with exactly RU and PRIVATE categories.

## Implemented

- Go exporter reads the exact published release/geoip_RU.dat and exports every RU and PRIVATE prefix. It rejects unexpected/duplicate categories, duplicate/non-canonical/default-route CIDRs, malformed entries and RU/PRIVATE overlap.
- Latest inventory from the current published v37 release: 76,231 RU CIDRs + 151 PRIVATE CIDRs = 76,382 rows. The older full run inventory (76,268 RU CIDRs) is superseded.
- Thirty seed hostnames are configured: two control targets plus 28 RU/KZ/BY service endpoints. Every hostname appeared in the expanded full run, but only 30 of 90 possible source-country/target pairs were measured in that daily sample (RU 21, KZ 6, BY 3). The scheduler rotates provider and target selection by UTC date; one artifact is not a complete provider-by-target census. Every newly added target includes a reference_url; the three Belarus government references were corrected to the Embassy of India in Minsk's official useful-links page. This is an expanded pilot, not a comprehensive domain/API inventory.
- Globalping providers are discovered at run time by country + ASN + eyeball-network. Returned probe country, ASN and tags are verified.
- The fair scheduler emits complete four-test bundles (DNS A, DNS AAAA, HTTPS IPv4, HTTPS IPv6), visiting every provider before assigning another target to any provider. Country/provider and target selection rotate by UTC date. Budgets never split bundles.
- OONI web_connectivity observations are collected separately. OONI anomalies remain unconfirmed review signals, not automatic block verdicts.
- Optional RIPE Atlas TLS measurements are skipped explicitly because RIPE_ATLAS_API_KEY is not configured.
- Classification is conservative: HTTP response is observed HTTP reachability; DNS result is separate; timeout/TLS/reset remains inconclusive; missing IPv6 probe is NO_IPV6_PROBE; no automatic BLOCKED_CONFIRMED result exists.
- Reports include raw JSONL, provider TSV, per-provider/prefix TSV, exact provider/IP TSV, all-prefix TSV and summary JSON. Exact addresses are checked against the prefix shown in the row.

## Latest validation

- CI run: [42875324510](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/42875324510)
- Commit tested: `8dd5fd2cb22df18b04944c19782f3aed12566022`
- Result: SUCCESS. Python 27/27 tests passed; Go formatting, Go tests and Go build passed.
- The latest code includes structured summary fields for per-country IPv6 gaps, unique hostnames, observed/possible country-target pairs, per-country pair counts, provider-target bundles, and DNS no-answer count. The DNS no-answer counter was added after the most recent full run; CI validates it, and the next full run will include it in JSON.

## Latest complete measurement run — current published v37 + 30 targets

- Run: [Full reachability RU KZ BY #6](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/42874077069)
- Run ID: `42874077069`; trigger commit: `e6612071a4839e8151c9823bf43d6af84fe643c7`.
- Result: SUCCESS. Inventory checksum, full RU/PRIVATE inventory export, Globalping/OONI collectors and artifact upload all succeeded.
- Artifact: `geoip-ru-reachability-42874077069`, artifact ID `13790094804`, size 1,076,911 bytes, SHA-256 `df2aac10fb88eb6beac6bf728c206b8f2f52f916da20b72e6221e1a57cb384e5`; expires 2026-12-10 18:22:45 UTC.
- Local archive: `/mnt/data/reachability-structured-summary-42874077069.zip`; local SHA-256 independently verified against the GitHub artifact digest.

### Current GeoIP inventory

- Exact published `release/geoip_RU.dat` v37 sidecar checksum passed.
- Complete inventory: 76,231 RU prefixes + 151 PRIVATE prefixes = 76,382 rows.
- The prefix report includes all 76,231 RU prefixes; it is not a scan of every address in those ranges.

### Expanded target and sampling coverage

- 30 hostnames: two controls and 28 service targets.
- All 30 hostnames appeared in this run, but only 30 of 90 possible source-country/target pairs were selected: RU 21, KZ 6, BY 3. The daily UTC rotation must accumulate coverage over later runs; one artifact is not a full three-country test of every hostname.
- 45 complete four-measurement provider/target bundles were observed. No partial bundles.

### Globalping measurement

- Online probes: 5,537.
- Distinct source country/ASN provider pairs observed: 36, all 36 covered; by source country: RU 27, KZ 6, BY 3.
- Returned probe-country-tagged results: RU 114, KZ 18, BY 11.
- 180 tasks; counts from raw measurements: ACCESSIBLE=37, DNS_ANSWER=55, DNS_NO_ANSWER=35, INCONCLUSIVE=16, NO_IPV6_PROBE=37, API_ERROR=0. These sum to all 180 tasks.
- Missing IPv6 probes: 37 total, RU 30, KZ 6, BY 1. These are measurement-coverage gaps, not block evidence.
- Automatically written JSON summary agrees with the raw JSONL for all newly added fields: 30 distinct targets, 30/90 target-country pairs (RU 21, KZ 6, BY 3), 45 provider-target bundles, and IPv6 gaps (RU 30, KZ 6, BY 1).
- The structured JSON from this run predates the additional `globalping_dns_no_answers` field; its value was independently derived as 35 from raw JSONL. The field is now implemented and CI-tested; the next full run will write it directly.

### Prefix and exact-IP report validation

- All 76,231 RU prefixes are present in `reachability_by_prefix.tsv`.
- Prefix status: 23 `ENDPOINT_ACCESSIBLE_OBSERVED`; 17 `DNS_RESOLVED_HTTP_NOT_CONFIRMED`; 4 `DNS_RESOLVED_HTTP_INCONCLUSIVE`; 76,187 `NO_MATCHED_ENDPOINT`.
- Provider reports: 61 provider/prefix rows and 73 provider/exact-IP rows.
- The exact IP sets reconcile by country/ASN/prefix; zero mismatches. All 73 IP addresses belong to their stated CIDRs; zero out-of-prefix addresses.

### OONI and RIPE Atlas

- OONI observations: 987; anomaly-review signals: 19. All 19 have `confirmed=false` and `failure=false`; they remain review-only metadata, not block evidence.
- RIPE Atlas output contains one explicit record: `SKIPPED_API_KEY_NOT_CONFIGURED`.

### Independent structured-summary validation

- Downloaded and inspected the complete ZIP; SHA-256 matched GitHub's digest.
- Parsed `reachability_summary.json` and independently recalculated every new coverage metric from `globalping_measurements.jsonl`; values matched exactly.
- Checked all inventory counts, every RU prefix row, provider-prefix/IP group-key equality, and all 73 exact IPs. No inconsistencies found.
- Temporary full-run push trigger was removed in commit `1cb59cbd216d8fc4b1c217532a62f0c3e54b2f88`. Current workflow has no `push` trigger; manual `workflow_dispatch` and daily schedule remain. The daily schedule becomes active only after merge to the default branch.

## Interpretation limits

- Globalping eyeball-network differentiates end-user-tagged probes from data-centre probes, but does not prove that each probe is a residential/home line. Some returned network names can be hosting/enterprise operators. Treat the country/ASN observations as vantage-point evidence, not a verified list of household subscribers.
- The 30 hostnames are still a pilot. All 30 hostnames appeared in the run, but only 30/90 source-country/target pairs were selected (RU 21, KZ 6, BY 3); the daily rotation must accumulate across later runs. In the latest run, 76,187 RU prefixes had no endpoint match; these remain untested by the current catalogue, not inaccessible or blocked.
- This is endpoint-based evidence for selected services, not a scan of every address in each CIDR.
- 38 missing IPv6 probes are a measurement coverage limitation (RU 31, KZ 6, BY 1), not evidence of IPv6 blocking.
- OONI anomalies are all unconfirmed; do not subtract their IPs from DIRECT.
- The workflow has not changed geoip_RU.dat or the two-category policy.


## Independent artifact QA and follow-up corrections

- Downloaded artifact ZIP reachability-expanded-30-targets.zip (1,077,344 bytes) and verified SHA-256 30d64922b2779139256d355b644b6dba41e1a7152877c19222b1b14cb4fc9512 against GitHub's artifact digest.
- Rechecked all 76,231 RU inventory rows in the prefix report. The 62 provider/prefix rows reconcile exactly with the 71 provider/exact-IP rows by country/ASN/prefix; zero mismatches and zero IPs outside their stated prefix.
- Independent result counts match the summary: ACCESSIBLE 40, DNS_ANSWER 56, DNS_NO_ANSWER 34, INCONCLUSIVE 12, NO_IPV6_PROBE 38, API_ERROR 0. Derived missing-IPv6 split from raw measurements: RU 31, KZ 6, BY 1; this replaces the earlier empty checkpoint subfield.
- The one-day schedule selected 45 complete bundles across 39 provider pairs and covered all 30 hostnames, but selected only 30 of the 90 possible source-country/target pairs (RU 21, KZ 6, BY 3). The remaining combinations require successive UTC-rotated daily runs; the daily schedule activates only after default-branch merge.
- Corrected by-government, by-president, and by-nbrb reference URLs to the Embassy of India in Minsk useful-links page, which explicitly lists those official Belarus government domains. Change committed in 1b2152760b120218763956a8f7005f3bafa044e8; validation run 42871418240 passed.
- Current main is a68e5d6589361814cb1cfedd2af7857e4af806fa; PR #5 remains 29 commits behind it. Do not rewrite history or merge PR automatically. Plan a controlled branch update and rerun validation before owner approval.

## Resume protocol

1. Read WORKLOG.md and CHECKPOINT.json.
2. Query PR #5 and use its current head SHA, not a remembered SHA.
3. Query recent Actions runs on feature/reachability-full-ru-kz-by.
4. Prefer the artifact from the latest successful full run; do not repeat a run whose artifact is still available and relevant.
5. Continue from CHECKPOINT.json current_phase / next_steps. Do not redo reconnaissance, exporter implementation, scheduler or green CI.
6. Work in short units: one focused change, CI, then checkpoint. Do not run full measurement after work-log-only changes.
7. After each meaningful phase, update both files and commit them. Documentation/checkpoint-only commits are excluded from push CI; PR validation runs only on opened/reopened/ready_for_review; the full-measurement workflow remains manual on this branch and daily after merge to default. Keep PR #5 Draft unless the owner explicitly approves final review and merge.

## Structured coverage summary metrics

- The collector adds `globalping_ipv6_probe_unavailable_by_country`, `globalping_distinct_targets_observed`, `globalping_observed_target_country_pairs`, `globalping_possible_target_country_pairs`, `globalping_observed_target_country_pairs_by_country`, `globalping_provider_target_bundles_observed`, and `globalping_dns_no_answers` to `reachability_summary.json`.
- Implementation commit: `e63974c8e48282fdb7402ffa18ea23c4bce36f54`; unit-test commit: `6e2ba2b15e49f4af9a6f00615f75a88d75d14f81`.
- Validation run `42873343359` passed: 27 Python tests, Go formatting, Go tests and Go build. The added unit test checks that repeated tasks do not inflate unique country/target pairs and that missing-IPv6 probe counts use the requested source country.
- Full run `42874077069` verified the first six coverage fields against raw JSONL. The additional `globalping_dns_no_answers` field was committed and CI-tested after that run; its raw-derived value in run `42874077069` was 35, and the next full measurement will emit it directly.

## DNS counter full run in progress

- Run: https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/42876578975
- Trigger commit: `aed7583c69fb5a996ea119ba07f13470d85c6a1c` (`[reachability-once] Verify DNS no-answer summary metric`). This uses the current collector with the `globalping_dns_no_answers` structured summary field and the 30-target catalogue.
- The one-time push trigger has already been removed in commit `00c591e8fd0bbda1ddf9e01574dcc739e302288a`; current workflow has no `push` trigger. The guard for `[reachability-once]` messages is retained.
- Last checked: exact current release download/checksum and RU/PRIVATE inventory export succeeded; combined Globalping/OONI collector step remained `in_progress`; artifact not yet uploaded. Do not launch a duplicate run.
- Resume by checking run `42876578975`, its job and artifacts. After success, download artifact, verify digest, and independently compare `globalping_dns_no_answers` with raw JSONL DNS_NO_ANSWER records.
- Latest completed full run before this is `42874077069` / artifact `13790094804`; it does not yet contain the DNS no-answer summary key.

## Phase status

| Phase | State | Evidence |
|---|---|---|
| Repository reconnaissance | DONE | main and release trees inspected |
| Protobuf inventory exporter | DONE | full run #42861904056 |
| Globalping/OONI/Atlas collector | DONE | artifact #13786625472 |
| Fair provider scheduler | DONE | 38/38 provider pairs covered |
| Provider-prefix and exact-IP reports | DONE | latest v37 artifact: 61 provider/prefix rows, 73 IP rows; exact reconciliation |
| NO_IPV6_PROBE handling | DONE | latest run: 37 classified (RU 30, KZ 6, BY 1); API_ERROR 0 |
| CI validation | DONE | run #42875324510; 27 Python tests + Go checks |
| Full measurement and artifact review against current v37 release | DONE | run #42874077069; artifact #13790094804; SHA verified locally |
| Belarus target-source correction | DONE | three reference URLs corrected; CI #42871418240 passed |
| Daily target-country sampling coverage review | DONE | 30/90 source-country/target pairs in run #42874077069; rotation is multi-day |
| Structured coverage summary metrics | DONE | run #42874077069: first six coverage metrics match raw JSONL; DNS_NO_ANSWER count added in commit b0e5220 and CI-tested |
| OONI review / final policy interpretation | DONE with caveats above | 19 anomalies; all confirmed=false and failure=false |
| Expanded 30-host target catalogue | DONE | 19 new sourced service endpoints; CI #42871418240 and full run #42874077069 passed |
| Final PR review / owner decision | PENDING | PR #5 remains Draft; owner must review target coverage and base-branch lag |

## Invariants

- Never alter geoip_RU.dat from this diagnostic workflow.
- Exactly RU and PRIVATE categories remain in the client file.
- PRIVATE has absolute priority.
- Timeout, reset, TLS failure, DNS error or OONI anomaly alone is never a block verdict.
- eyeball-network does not prove a residential/home connection.
- No policy inference is made for unused IPs in a CIDR.
