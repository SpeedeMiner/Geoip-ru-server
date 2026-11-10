# Reachability implementation work log

Durable resume point for PR #5. After any conversation/network interruption, read this file and CHECKPOINT.json, query the live PR head and Actions runs, then continue from the first pending phase. Do not restart completed work.

## Current repository state

- Repository: SpeedeMiner/Geoip-ru-server
- PR: https://github.com/SpeedeMiner/Geoip-ru-server/pull/5
- State: OPEN / DRAFT; no automatic merge.
- Branch: feature/reachability-full-ru-kz-by
- Current main: a68e5d6589361814cb1cfedd2af7857e4af806fa; PR branch merge-base remains c71b5eff48f34b363ef2430ba6b5c41603f36126 (29 commits behind current main). The 11 changed files in PR #5 are confined to .github/reachability/** and the two separate diagnostic workflows; no main GeoIP builder, release or client data file is changed.
- Latest validation: run 42877605801 succeeded on commit c6b86d8b92bac5777c73634d921835fee687573b. Python 28/28 tests, Go formatting, Go tests and Go build passed. This validates the NO_PROBE classification and country counters. The preceding runner-only commit validation (42877511514) failed solely because the earlier test file still contained old expected values; the subsequent paired commit passed.
- Latest full measurement: run 42877815872 succeeded on trigger commit 401830a0bdcef35f20fe67e90fbaef7e72129ca6. The one-time push trigger was removed immediately after launch in commit b1c603a7c36cc714f14ff6634160a78ffc7e2b99. Current workflow has no push trigger; always query live PR head on resume.
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

- CI run: [42877605801](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/42877605801)
- Commit tested: `c6b86d8b92bac5777c73634d921835fee687573b`
- Result: SUCCESS. Python 28/28 tests passed; Go formatting, Go tests and Go build passed.
- Tests cover missing IPv6 probes, missing IPv4/DNS probes, DNS no-answer summary, unique source-country/target pairs and no double-counting of provider-target bundles.

## Latest complete measurement run — current published v37 + 30 targets

- Run: [Full reachability RU KZ BY #8](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/42877815872)
- Run ID: `42877815872`; execution commit: `401830a0bdcef35f20fe67e90fbaef7e72129ca6`.
- Result: SUCCESS. Release protobuf checksum, RU/PRIVATE inventory export, Globalping/OONI collection and artifact upload all passed.
- Artifact: `geoip-ru-reachability-42877815872`, artifact ID `13791344001`, size 1,075,992 bytes, SHA-256 `d4858a2ed63f208fd5146ae06b4fb586410e37db6b90e7232aacdab5ab01a137`; expires 2026-12-10 18:44:29 UTC.
- Local archive: `/mnt/data/reachability-no-probe-fixed-42877815872.zip`; local SHA-256 independently verified against GitHub's artifact digest.

### Current GeoIP inventory

- Exact published `release/geoip_RU.dat` v37 checksum passed in workflow.
- Inventory: 76,231 RU prefixes + 151 PRIVATE prefixes = 76,382 rows.
- `reachability_by_prefix.tsv` contains all 76,231 RU prefixes. It is endpoint evidence, not a scan of every IP in each CIDR.

### Expanded target and sampling coverage

- 30 hostnames: two controls + 28 RU/KZ/BY services.
- All 30 hostnames appeared in this run. Unique source-country/target pairs: 32 of 90 possible; RU 23, KZ 6, BY 3. This remains a rotating daily sample, not a full three-country run for each hostname.
- 45 complete four-measurement provider/target bundles; zero partial bundles.
- 38 provider pairs discovered and covered (RU 29, KZ 6, BY 3). 37 pairs returned actual probe result metadata; one pair contributed tasks classified as NO_PROBE because no matching IPv4 probe existed.

### Globalping measurement

- Online probes: 5,536.
- Results across all 180 tasks: ACCESSIBLE=38, DNS_ANSWER=55, DNS_NO_ANSWER=33, INCONCLUSIVE=16, NO_IPV6_PROBE=35, NO_PROBE=3, API_ERROR=0. Counts sum to 180.
- Three HTTP 422 `no_probes_found` responses for IPv4/DNS are now classified as `NO_PROBE`, all from RU; they are measurement-coverage gaps, not API errors or evidence of filtering.
- Missing IPv6 probes: 35 total; RU 28, KZ 6, BY 1. These are coverage gaps, not IPv6-blocking evidence.
- Summary JSON automatically reports `globalping_dns_no_answers=33`, `globalping_no_probe_count=3`, `globalping_no_probe_by_country={"RU":3}`, and `globalping_ipv6_probe_unavailable_by_country={"RU":28,"KZ":6,"BY":1}`.
- Structured coverage summary: 30 distinct targets; 32/90 source-country/target pairs (RU 23, KZ 6, BY 3); 45 provider-target bundles. All corresponding values match raw JSONL exactly.
- Genuine API errors: zero. `globalping_api_error_reasons` is empty.

### Prefix and exact-IP report validation

- All 76,231 RU prefixes are present in the prefix report.
- Prefix status: 24 `ENDPOINT_ACCESSIBLE_OBSERVED`; 15 `DNS_RESOLVED_HTTP_NOT_CONFIRMED`; 5 `DNS_RESOLVED_HTTP_INCONCLUSIVE`; 76,187 `NO_MATCHED_ENDPOINT`.
- Provider reports: 60 provider/prefix rows and 70 exact provider/IP rows.
- Provider/prefix IP sets reconcile exactly to provider/IP rows by country/ASN/prefix; zero mismatches. All 70 exact IPs belong to their stated CIDRs; zero out-of-prefix addresses.

### OONI and RIPE Atlas

- OONI observations: 987; anomaly-review signals: 19. All 19 have `confirmed=false` and `failure=false`; none is block evidence.
- RIPE Atlas output records an explicit skip because `RIPE_ATLAS_API_KEY` is not configured.

### Independent artifact QA

- Downloaded the complete artifact ZIP and verified SHA-256 against GitHub's artifact digest.
- Recalculated every Globalping result count and new summary metric from `globalping_measurements.jsonl`; all matched exactly.
- Verified inventory counts, all 76,231 RU prefix rows, all 70 IP-to-CIDR constraints, and exact provider-prefix/provider-IP reconciliation. No inconsistencies.
- Current full workflow has no push trigger; manual `workflow_dispatch` and daily schedule remain. The daily schedule activates only after merge into the repository default branch.

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

- `reachability_summary.json` now includes `globalping_dns_no_answers`, `globalping_no_probe_count`, `globalping_no_probe_by_country`, `globalping_ipv6_probe_unavailable_by_country`, distinct target count, observed/possible target-country pair counts, per-country pair counts, and distinct provider-target bundles.
- The latest full run 42877815872 independently confirmed all these fields against raw JSONL.
- HTTP 422 `no_probes_found` is `NO_IPV6_PROBE` only for HTTPS IPv6; other IPv4/DNS cases are `NO_PROBE`. This prevents absent probes from being reported as API errors.
- Latest validation run 42877605801 passed 28 Python tests plus Go formatting/tests/build.

## Phase status

| Phase | State | Evidence |
|---|---|---|
| Repository reconnaissance | DONE | main and release trees inspected |
| Protobuf inventory exporter | DONE | full run #42861904056 |
| Globalping/OONI/Atlas collector | DONE | artifact #13786625472 |
| Fair provider scheduler | DONE | 38/38 provider pairs covered |
| Provider-prefix and exact-IP reports | DONE | latest v37 artifact: 60 provider/prefix rows, 70 IP rows; exact reconciliation |
| NO_IPV6_PROBE handling | DONE | latest run: 37 classified (RU 30, KZ 6, BY 1); API_ERROR 0 |
| CI validation | DONE | run #42875324510; 27 Python tests + Go checks |
| Full measurement and artifact review against current v37 release | DONE | run #42874077069; artifact #13790094804; SHA verified locally |
| Belarus target-source correction | DONE | three reference URLs corrected; CI #42871418240 passed |
| Daily target-country sampling coverage review | DONE | 32/90 source-country/target pairs in run #42877815872; rotation is multi-day |
| Structured coverage summary metrics | DONE | run #42877815872: DNS_NO_ANSWER, NO_PROBE, IPv6 and country/target fields all match raw JSONL |
| OONI review / final policy interpretation | DONE with caveats above | latest 19 anomalies; all confirmed=false and failure=false |
| Expanded 30-host target catalogue | DONE | 19 new sourced service endpoints; latest full run #42877815872 passed |
| Final PR review / owner decision | PENDING | PR #5 remains Draft; owner must review target coverage and base-branch lag |

## Invariants

- Never alter geoip_RU.dat from this diagnostic workflow.
- Exactly RU and PRIVATE categories remain in the client file.
- PRIVATE has absolute priority.
- Timeout, reset, TLS failure, DNS error or OONI anomaly alone is never a block verdict.
- eyeball-network does not prove a residential/home connection.
- No policy inference is made for unused IPs in a CIDR.

### 2026-11-10 — Reconcile final DNS_NO_ANSWER checkpoint counter — DONE

- Re-downloaded the exact full-run artifact `geoip-ru-reachability-42877815872` (artifact ID `13791344001`) and independently verified its ZIP SHA-256: `d4858a2ed63f208fd5146ae06b4fb586410e37db6b90e7232aacdab5ab01a137`.
- Recounted all 180 rows in `globalping_measurements.jsonl`: `DNS_NO_ANSWER=33`, `DNS_ANSWER=55`, `ACCESSIBLE=38`, `INCONCLUSIVE=16`, `NO_IPV6_PROBE=35`, `NO_PROBE=3`; no `API_ERROR` rows.
- `reachability_summary.json` independently reports `globalping_dns_no_answers=33`; this agrees with the raw JSONL. The checkpoint's `dns_no_answer_count_raw_derived=35` was stale documentation (not the artifact value) and is corrected to 33 in the following checkpoint commit.
- No runner, tests, workflow, target catalogue, GeoIP input/output or production files changed. This documentation-only correction does not require another full measurement run or code-validation CI.

### 2026-11-10 — Provider-prefix TSV schema correction and catalogue provenance — IMPLEMENTED / VALIDATION PENDING

- Re-downloaded and independently re-hashed full-run artifact `geoip-ru-reachability-42877815872`; SHA-256 remains `d4858a2ed63f208fd5146ae06b4fb586410e37db6b90e7232aacdab5ab01a137`.
- Artifact inspection found duplicate `INCONCLUSIVE` header columns in `reachability_by_provider_prefix.tsv`. Corrected the field list to one unique schema constant, `PROVIDER_PREFIX_REPORT_FIELDS`, and added a regression test that writes the header and asserts it is unique.
- Updated README's full-run sampling example to the latest artifact: 45 complete bundles, 38 discovered provider pairs (RU 29, KZ 6, BY 3), 32/90 observed source-country/target pairs (RU 23, KZ 6, BY 3), 37 provider pairs with result metadata; three `NO_PROBE` tasks are coverage gaps.
- Completed provenance for all service targets: catalogue remains 30 unique hostnames (2 controls + 28 services), with a non-empty `reference_url` on all 28 service entries and no duplicate domains. Added references for the nine original service targets and strengthened the Gosuslugi, Mail and Belarusbank references.
- Verified from the actual branch files: JSON parses, all 28 service entries have `reference_url`, and all 30 domains are unique.
- Commits: runner schema fix `8776071fffeea3e465e7f2fd95f77dec10a12acf`; TSV regression test `9b03f4c7cc35ff8009b37b1c31d56c95ae6a8499`; README coverage correction `de71375794ccdfe2c114ac1199b417d057f63992`; target provenance commits `4e8071816faf554fe2acd76e153afa1eee74a1c1` and `07f6d90867ef27af4970be74087acb68eb91ee5c`.
- No measurement workflow re-run; no GeoIP protobuf, production builder, allowlist, DIRECT policy, main or release changes.
- Validation note: the push path filter includes `runner.py`, `test_runner.py` and `targets.json`, but the available GitHub connector did not expose push-triggered run records or commit statuses in this session. Do not treat the previous green run #42877605801 as validation of these later code changes.
- Resume from: confirm `Reachability validation` success for current branch head `07f6d90867ef27af4970be74087acb68eb91ee5c` (expected 29 Python tests plus Go formatting/tests/build). Keep PR #5 Draft; no merge or branch rewrite.
