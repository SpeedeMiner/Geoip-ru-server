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


### 2026-11-11 — Add Russian ISP VPN Gate measurement backend — IMPLEMENTED / VALIDATION PENDING

- Revisited the original PR #5 intent: tests should originate from real Russian ISP access networks, not infer "home" access from Globalping's `eyeball-network` tag.
- Added `.github/reachability/vpn_gate.py`. It reads the official VPN Gate CSV API, selects only records whose country code is RU and which have a public IPv4/OpenVPN profile, caps the default pilot at 3 nodes (hard maximum 6), and tests only target catalogue entries whose source-country scope includes RU.
- Added safe OpenVPN profile reconstruction. The downloaded profile is parsed but not executed. A minimal client profile is rebuilt from the API-advertised IP and validated port/protocol plus inline CA/TLS material; arbitrary script, plugin, route, config-file and external-file directives are not copied.
- Added fail-closed tunnel handling: IPv4 OUTPUT allows only the exact VPN transport endpoint and the tunnel interface; host IPv6 OUTPUT is blocked; DNS is temporarily set to 1.1.1.1 only after the tunnel route is installed; no target requests are sent until the actual public egress IP is verified as RU. A non-RU exit is rejected.
- For each confirmed RU exit, the collector records exit IP, country, ASN/prefix/organization metadata and maps the exact exit IP against the published RU/PRIVATE inventory. It emits `vpn_gate_providers.tsv`, `vpn_gate_measurements.jsonl`, `vpn_gate_geoip_candidates.tsv`, `vpn_gate_raw.jsonl` and `vpn_gate_summary.json`. Candidate rows remain review-only and never modify GeoIP data.
- Added `.github/reachability/test_vpn_gate.py` with CSV filtering, unsupported/malformed-profile rejection, remote-IP replacement, and script/plugin stripping tests.
- Added manual-only workflow `.github/workflows/reachability-vpn-gate.yml`. It downloads/verifies the exact published release protobuf, exports full RU/PRIVATE inventory, installs OpenVPN/iptables, and runs a small user-selected pilot. It is not added to the daily schedule and does not require repository secrets.
- Extended `Reachability validation` path filters and syntax checks to include the VPN Gate collector and its tests. Updated the README with workflow usage, privacy considerations and evidence limits.
- Important limit: VPN Gate volunteer ownership plus a RU exit and ISP/ASN metadata do not attest that a node is a household residential line. The output labels the vantage as volunteer-access-network / residential-unverified. Operator and network type must be independently reviewed before changing the RU list.
- No VPN connection or target measurement was launched in this coding session. CI for the new backend is pending; no prior green run validates these new files.
- No changes to `geoip_RU.dat`, production builder, release assets, DIRECT policy, ASN allowlists, `main`, or PR #6. PR #5 remains Draft.
- Code commit before the documentation checkpoint: `2d67db9d360c835dea93752f60bd5a097cab154f`. Expected validation: existing Python 29 + 6 new VPN Gate tests = 35 total, plus existing Go formatting/tests/build.
- Resume from: verify validation on `2d67db9d360c835dea93752f60bd5a097cab154f`; after it passes, launch the manual workflow with 1–3 servers, inspect the artifacts and actual RU exit IP/ASN/ISP attribution, then decide whether to widen coverage.


### 2026-11-11 — VPN Gate kill-switch failure recovery and final test count — DONE / CI PENDING

- Hardened `FirewallGuard`: if setting the fail-closed iptables rules fails partway through `__enter__`, the context manager now restores both saved IPv4 and IPv6 firewall snapshots immediately. This matters because Python does not call `__exit__` when `__enter__` raises.
- Added a regression test that simulates failure while applying the IPv6 rules and verifies that both `iptables-restore` and `ip6tables-restore` are called.
- The VPN Gate test module now contains seven deterministic tests; expected full Python discovery count is 36 (29 existing reachability tests + 7 VPN Gate tests).
- Latest VPN Gate code/test commit for validation: `f8d6770ad3ce8ad1bda34a1fac9211060d5eba60`. Checkpoint commit follows separately; no code was changed after the validation target.
- Live combined commit status currently exposes no checks, and the GitHub connector returns no PR-triggered workflow records for this push commit. Do not mark CI successful without a visible run/result.
- No live VPN connection or target probes were executed. PR #5 remains Draft; PR #6 and all production GeoIP files remain untouched.


### 2026-11-11 — Final VPN Gate safety follow-up — DONE / VALIDATION PENDING

- Firewall restoration failures are now surfaced even when a VPN connection or target test was already failing; a suppressed restore failure could otherwise leave the host's temporary kill-switch active without an explicit report.
- Added the manual VPN Gate workflow file to the validation workflow's path filters, so edits to that workflow also trigger the reachability checks.
- Latest code commit requiring validation: `37ab30a8d8c588c02318071130a162dda8e1ae61`. The workflow path-filter commit is `a2f85a43cf9e295035724190ad5f6b20a73a0926`; the final CI target must include both.
- Expected Python discovery count remains 36; Go formatting/tests/build are also required. No visible green status has been confirmed.


### 2026-11-11 — Strengthen VPN exit verification and diversify ISP sample — IMPLEMENTED / CI PENDING

- Re-reviewed the VPN Gate backend before its first live run. The original exit-IP check accepted the first responding geolocation endpoint; changed it to require two independent IP-metadata services to agree on both exact public IPv4 and country. Fewer than two successful sources or any disagreement rejects that VPN exit before service tests.
- Added origin-ASN diversification: the selector inspects up to 24 of the best-ranked RU VPN Gate candidates via RIPEstat, then selects one candidate per distinct observed origin ASN before selecting a second node from an already-covered ASN. Unknown ASNs are explicitly counted as unverified and do not inflate distinct-ASN coverage.
- Avoids repeating RIPEstat lookups for selected servers by carrying their already inspected origin metadata into the run.
- Added five deterministic tests for two-source IP/country consensus, IP/country disagreement, insufficient metadata sources, one-per-ASN selection, and filling the remaining budget after each ASN has been offered a node. VPN Gate test module now has 12 tests; existing reachability test module has 29; expected full discovery is 41 Python tests.
- README now documents the two-source exit check and ASN-diverse initial sample.
- Latest VPN Gate code/test commit requiring validation: `3b9f9d1dc4d1c7e7558e35fdf184e089991cb907`. README update commit: `4f7560a5b5f0519aa661e3bed856f6c78916b8fa`.
- Current GitHub combined status for the VPN Gate code head returned no checks, and the available workflow-run lookup returned no runs. Do not mark validation successful; no full validation result is visible yet.
- The manual VPN Gate workflow remains unlaunched. No volunteer exit has been connected, no user traffic or credentials were sent, and no production GeoIP files were changed.
- Continue from: obtain a visible successful validation for the 41 Python tests and Go checks; then use the manual-only workflow with one or two exits first, inspect exact exit IP/country/ASN/PTR and firewall/resolver restoration, and only then expand to three. Keep PR #5 Draft and do not touch PR #6.


### 2026-11-11 — Preserve ASN provenance and validate prefix containment — IMPLEMENTED / CI PENDING

- Split ASN attribution into explicit sources for the VPN server and actual VPN exit: IP metadata ASN versus RIPEstat origin ASN. The selected display/origin ASN prefers RIPEstat when available, while both raw values and a conflict flag remain in provider and measurement outputs.
- If the two ASN sources conflict for the VPN exit, add a separate `ASN_CONFLICT` candidate row for manual review. Summary includes server and exit ASN conflict counts. No source is silently discarded.
- Hardened `network_info`: a RIPEstat prefix is kept only if it parses as a CIDR of the right family and contains the exact queried IP. ASN information is retained separately if the returned prefix is absent/mismatched.
- Added two tests for RIPEstat prefix containment and mismatch rejection. VPN Gate test module now has 14 tests; existing reachability tests remain 29; expected Python discovery count is 43.
- Updated README to explain ASN provenance and conflict handling.
- Latest validation-triggering code/test commit: `e1272f0e9b4c3048537a11e91b5d7bddf782012f`; ASN provenance implementation commit: `5668f225362f8e0945b983ffdfcce492c90a5397`; documentation commit: `ba7cee32ecae140a02522c93aceb94a0a64a6f83`.
- No visible CI checks or Actions run result has been returned by the available GitHub connector. Validation remains pending; previous successful CI predates all VPN Gate code.
- No live VPN Gate workflow has been dispatched or executed. No GeoIP builder/input/release/DIRECT/ASN allowlist or PR #6 changes.


### 2026-11-11 — Bound dual-stack VPN measurement runtime — IMPLEMENTED / CI PENDING

- Replaced separate DNS A and AAAA resolver calls with one `getaddrinfo(AF_UNSPEC)` call per target; returned IPv4 and IPv6 answers are split and recorded independently. This halves DNS resolver invocations without allowing host IPv6 transport (the IPv6 firewall policy remains DROP).
- Added two regression tests for successful A+AAAA extraction in one call and shared DNS-error classification.
- VPN Gate test module now has 16 tests; original reachability module has 29; expected combined discovery is 45 Python tests.
- The manual VPN Gate workflow timeout increased from 45 to 120 minutes. This leaves room for up to six sequential exits, candidate ASN lookups, bounded DNS/HTTPS requests and artifact upload even when some requests reach their timeouts.
- Updated README with the dual-stack one-call behavior and workflow timeout.
- Latest validation-triggering Python code/test commit: `09a61810013effee87fc5fdb6d304a3b132a7ba5`; workflow timeout commit: `a3098c15351de5dabc5f286f05024678fe4707fa`; README commit: `ba1371566bd12965940fb5bd05c78813b6b176fd`.
- Validation is still pending; no confirmed CI run or visible check is returned by the GitHub connector. No VPN Gate workflow has been dispatched.


### 2026-11-11 — Confirm VPN Gate CI and launch guarded one-exit pilot — CI PASS / MEASUREMENT RUNNING

- Retrieved the full Actions history through the GitHub REST run collection. Reachability validation Run #99, `42959843669`, completed successfully on `a3098c15351de5dabc5f286f05024678fe4707fa`.
- Inspected job `130323524196` and its logs: `python3 -m unittest discover` reports `Ran 45 tests` and `OK`; the Go step ran `gofmt` (no diff), `go test ./...` and `go build`, all successful. The compare from tested commit to the prior PR head contained only CHECKPOINT.json, README.md and WORKLOG.md, so all measurement code/tests were identical.
- A further `Reachability validation` Run #100, `42960889187`, passed after adding the gated one-shot workflow trigger.
- Found and corrected a GitHub platform constraint: `workflow_dispatch` only receives events while the workflow file exists on the repository default branch. This file is new to draft PR #5, so manual dispatch from the feature branch would not work before merge. To avoid merging or changing main, the workflow now also accepts a push on the feature branch only when the path `.github/reachability/VPN_GATE_RUN_ONCE` changes and the commit message starts with `[vpn-gate-once]`.
- Push-triggered pilot defaults to exactly one server; explicit manual dispatch input continues to default to three (hard cap six). The path filter is only the marker file and there is no schedule. Ordinary pushes cannot enter the measurement job.
- Created the one-shot marker in commit `31be54066923d83e598571e6e29ae5841a98fa49`, commit message `[vpn-gate-once] Run first single-exit Russian ISP pilot`.
- First VPN Gate measurement run: `42960930985`, currently `in_progress`; tool snapshot shows installation of OpenVPN/iptables, Go setup, exact release protobuf download and complete RU/PRIVATE inventory export succeeded. Measurement step (candidate ASN selection, VPN connection, two-source exit verification and endpoint tests) is running; artifact not available yet.
- No production data, main/release, DIRECT policy, ASN allowlists or PR #6 changed. PR #5 remains Draft.
- Resume from: inspect run `42960930985` until complete, review artifact and logs, remove the marker file after the run, then disable the one-shot push path (retain workflow_dispatch for after default-branch integration). Do not launch a second VPN run without reviewing the first artifact.


### 2026-11-11 — Review first VPN Gate pilot artifact — RUN COMPLETE / NO TUNNEL

- VPN Gate run #42960930985 completed with workflow success and uploaded artifact ID 13829435753. Artifact size 287,650 bytes; ZIP SHA-256 7b517cd1db899a766b7b65aba155756d94ada4285bcf75215167a91cc0f183cf.
- The artifact is a **diagnostic failure, not a successful reachability measurement**: one server was attempted, no RU VPN exit tunnel was established, target_measurements=0, and the per-target JSONL is empty. The workflow returns success because it preserves failed-candidate diagnostics and uploads the report.
- VPN Gate directory discovery returned 12 usable RU OpenVPN profiles from 6 origin ASNs. The selected node was vpn971088675, IP 188.242.100.160, origin AS35807 / SkyNet Ltd., prefix 188.242.96.0/19, PTR 188.242.100.160.pool.sknt.ru. IP metadata and RIPEstat agreed on AS35807. The current GeoIP inventory maps this server IP to RU via 188.242.64.0/18; therefore this sample does not reveal a missing RU address.
- The server accepted a TCP connection on port 1439, but OpenVPN reported TLS key negotiation failed to occur within 60 seconds and TLS handshake failed. This is a VPN-relay/TLS-session failure, not evidence of filtering of Yandex/VK or any other target. No target request was sent.
- External cross-check: AS35807 is identified as SkyNet Ltd. / ISP, and the exact /19 is listed as an announced, RPKI-valid network by current public routing/ASN reference pages. Reverse-DNS pool.sknt.ru is consistent with a provider access pool. These are strong access-network indicators, not proof of the volunteer host's exact household connection.
- Exact artifact archive inspected locally at /mnt/data/geoip-ru-vpn-gate-42960930985.zip; the SHA above matches GitHub's artifact digest. The summary shows selected=1, connect_or_verify_failed=1, successful_ru_exits=0, target_measurements=0.
- Corrective implementation added in vpn_gate.py: the candidate selector now returns a capped fallback list (up to six), ordered one candidate per origin ASN before repeated ASN; max_servers now means successful verified RU exits, while max_attempts separately caps connection candidates. The run continues after a failed or non-RU exit and stops when the requested number of RU exits succeeds.
- Added early fail-fast detection for OpenVPN TLS/authentication fatal messages in the live log, so a dead relay does not waste the full timeout before the next candidate is attempted. Updated the manual workflow to expose separate successful-exit and attempt limits; feature-branch one-shot push defaults to 1 successful exit / 3 candidates.
- Added two unit tests for ASN-diverse fallback selection and attempt-budget validation; latest VPN Gate module count is 19 tests (expected combined suite 48). Full validation of this retry implementation is pending.
- Next: wait for Reachability validation on vpn_gate.py/tests, then change the one-shot marker with a new [vpn-gate-once] commit to retry up to three distinct-ASN candidates for one successful RU tunnel. Do not rerun until CI is green.
- Do not alter GeoIP production data based on this sample: the relay IP is already covered by RU CIDR. No main/release, builder, DIRECT, ASN allowlists or PR #6 touched.


### 2026-11-11 — Add bounded VPN Gate fallback after first TLS failure — IMPLEMENTED / CI PASS

- Reviewed first-run artifact `geoip-ru-vpn-gate-42960930985.zip` (artifact 13829435753, 287,650 bytes, SHA-256 `7b517cd1db899a766b7b65aba155756d94ada4285bcf75215167a91cc0f183cf`). It found 12 usable RU profiles across six ASNs and attempted one selected exit only.
- The selected exit was `vpn971088675`, `188.242.100.160`, AS35807 / SkyNet Ltd., route `188.242.96.0/19`, PTR `188.242.100.160.pool.sknt.ru`. The server is already mapped as RU by the published GeoIP inventory via `188.242.64.0/18`; this observation is not a missing-RU-IP candidate. Public references also identify AS35807 as a Russian ISP and list the /19 as RPKI-valid:
  - https://ipapi.is/asn/35807.html
  - https://bgp.he.net/AS35807
  - https://ipinfo.io/AS35807/188.242.96.0/19
- TCP connected to the relay's advertised port 1439. OpenVPN then reported TLS key negotiation timeout after 60 seconds. No TUN default route was installed, no exit-IP metadata could be verified, and no DNS/HTTPS target request was sent. Workflow conclusion SUCCESS means the diagnostic artifact uploaded; it does **not** mean the VPN measurement or service checks succeeded.
- Implemented bounded retry: `select_diverse_servers` now prepares up to six attempts in ASN-diverse round-robin order. `--max-servers` counts successful verified RU exits; `--max-attempts` separately limits candidate connections. The loop continues after connection/TLS failure or non-RU exit and stops when the requested number of verified RU exits is reached.
- Added live-log fail-fast detection for TLS negotiation, TLS handshake and authentication failure markers. This avoids sleeping through the entire timeout when OpenVPN has already reported a fatal session failure.
- Workflow exposes separate max-success and max-attempt values; the branch one-shot defaults to one successful RU exit and three connection candidates. The hard cap remains six for both. No recurring VPN schedule was added.
- Regression suite additions: fallback ordering across distinct ASNs, attempt budget validation, and fail-fast TLS log detection. Latest VPN Gate test module has 19 tests; existing reachability module has 29; total expected 48.
- CI validation Run #103 `42962158410` succeeded on `f8ecc2c894a2ea290b95bb2c1ab242a2a62ec5ce`; logs report `Ran 48 tests`, `OK`, plus gofmt, go test and go build all successful.
- Retry is ready; no second measurement has yet been launched. Next one-shot marker commit must carry `[vpn-gate-once]` and will try up to three candidates to achieve one successful RU exit.
- No production GeoIP mutation, main/release change, DIRECT/ASN allowlist change or PR #6 change.


### 2026-11-11 — Review second VPN Gate pilot; add pinned DoH fallback and truthful run status — IMPLEMENTED / CI PENDING

- Second VPN Gate run #42962715822 completed and uploaded artifact 13830405759 (288,476 bytes; SHA-256 `6b85e2788c5690925d7b9355f610a39e9d32f1b9c0818ad427b03069aa3806aa`).
- It discovered 9 usable RU OpenVPN profiles across 6 origin ASNs, inspected 9, and attempted the top 3 across distinct ASNs:
  1. `5.143.110.119`, AS12389 / PJSC Rostelecom Far East Region, prefix `5.143.108.0/22`: OpenVPN log reached `Initialization Sequence Completed` (tunnel established), but subsequent two-source exit metadata verification failed because system resolver lookups for `ipapi.co` and `ipinfo.io` returned temporary DNS failures. No service target requests followed.
  2. `94.31.243.156`, AS12668 / LLC KOMTEHCENTR FTTB Customers, prefix `94.31.243.0/24`: TCP connected; no IPv4 VPN route/tunnel established within 60 seconds.
  3. `176.194.228.49`, AS12714 / Net By Net Holding LLC, prefix `176.194.224.0/19`: TCP connected; no IPv4 VPN route/tunnel established within 60 seconds.
- All three VPN Gate server IPs already map to RU in the published GeoIP inventory. No exit IP was verified and `target_measurements=0`. The workflow incorrectly concluded success because it treated report upload as job success; a successful GitHub run did not mean successful VPN reachability.
- Implemented a pinned DNS-over-HTTPS fallback for post-tunnel metadata and target resolution. It queries Cloudflare at pinned IP 1.1.1.1 and Google at pinned IP 8.8.8.8, preserving DoH hostname SNI/certificate validation. If system DNS fails, HTTPS metadata and target HEAD requests retry with DNS-resolved pinned destination IPs while preserving original hostname SNI/cert checks; DNS and HTTPS remain routed through the VPN firewall's tun interface.
- Added two code safety/operational improvements: OpenVPN auth file is chmod 0600 (removes the observed permissive-file warning), and failed connection diagnostic tails retain up to 60 lines rather than only 12, so TLS failure reasons are not truncated away.
- Measurement semantics are now strict: the Python runner returns exit code 2 unless it reaches the requested count of independently verified RU exits. The workflow uses `continue-on-error` only to preserve diagnostic artifact upload with `if: always()`, then a final gate step marks the job failed if the measurement step failed. Artifact upload itself is warning-only if measurement failed before creating files.
- Added tests for DoH record filtering, system DNS fallback for A/AAAA, pinned HTTPS fallback for IP metadata, pinned SNI HEAD fallback for targets, and strict zero-exit measurement status. VPN Gate test module now has 24 tests; existing reachability module has 29; expected total 53.
- Latest validation-triggering code/test commit: `515863b7029274ba6c65c683e9fc863066a8fefc`; workflow failure-status enforcement commit: `24dded8bc779c30b3bdaa908d1c9574eebb25e34`; latest test commit: `2bcf42cd017db678da21604d89a5c6e57403e346`; README doc commit: `b03d1a365234b354eea5098cb0cd341b1a081a81`.
- No new VPN run is launched until CI validates these changes. The previous two pilot reports remain diagnostic only and show zero completed target measurements.
- No production GeoIP mutation, builder/release/main changes, DIRECT/ASN allowlist changes or PR #6 changes.


### 2026-11-11 — Pinned DoH fallback and strict measurement-status CI — VALIDATED

- Reachability validation Run #106 `42964285730` passed on `515863b7029274ba6c65c683e9fc863066a8fefc`. Full job log confirms `Ran 53 tests`, `OK`, followed by successful gofmt, go test and go build.
- A preceding test-triggered run #104 `42964242183` failed because the new measurement-status test was committed just before its helper function. The next code commit `515863b...` added the helper and run #106 validates the complete 53-test tree. This transient failure is resolved; do not report run #104 as the final status.
- Workflow enforcement change `24dded8bc779c30b3bdaa908d1c9574eebb25e34` also passed CI run #105 `42964127601`: measurement step is continue-on-error only to allow artifact upload; upload runs always; a final gate fails the job when the requested verified RU exit count was not reached.
- DoH implementation commit `3fb0617a4ea7c03ff0f1f2b6832b543213cea13b`, tests `723a0cf43d8d849c6d4902f9ce3046dce85c7215`, test/status commit `2bcf42cd017db678da21604d89a5c6e57403e346`, helper implementation `515863b7029274ba6c65c683e9fc863066a8fefc`, workflow `24dded8bc779c30b3bdaa908d1c9574eebb25e34`.
- Latest VPN Gate test module count is 24; existing reachability module count 29; total 53.
- New validation covers: pinned Cloudflare/Google DoH JSON parsing, A/AAAA fallback after NSS errors, pinned metadata HTTPS fallback, pinned target HTTPS HEAD with SNI/certificate verification, and non-zero exit status if no requested RU exit is verified.
- Auth file permissions are now 0600, OpenVPN diagnostic tail is 60 lines, and DNS fallback does not route requests via the runner's pre-VPN resolver.
- The next pilot may now be retried. If no RU exit succeeds, expected workflow conclusion is **failure**, with diagnostics still uploaded. A failed measurement must not be called a successful reachability test.


### 2026-11-11 — Third VPN Gate pilot launched with pinned DoH and strict failure status

- Third one-shot marker update commit: `73c5fc37146bbd843d97510af3ee0c97bf069630`, message `[vpn-gate-once] Retry Russian VPN pilot with pinned DoH fallback`.
- Live run: `42964869207`, URL https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/42964869207.
- This run tests the new pinned DoH resolver and pinned TLS/SNI HTTPS fallback after tunnel establishment. Requested one successful verified RU exit; maximum three candidate attempts across origin ASNs.
- New workflow behavior: measurement failure does not suppress artifact upload; a final workflow gate reports job failure if no verified RU exit is achieved.
- Validation before launch: Run #106 `42964285730` passed 53 Python tests plus Go formatting/tests/build.
- Run currently in progress; do not infer a result until the job and artifact are available.

### 2026-11-11 — Harden resolver isolation and keep HTTPS fallback IPv4-only — IMPLEMENTED / CI PENDING

- Rechecked the second VPN Gate pilot artifact from run #42962715822 (geoip-ru-vpn-gate-42962715822, artifact 13830405759, 288,476 bytes, SHA-256 6b85e2788c5690925d7b9355f610a39e9d32f1b9c0818ad427b03069aa3806aa). The report confirms 3 candidate attempts, 0 verified RU exits and 0 target measurements. Run-level job success was only artifact-upload success; the measurement script had not yet enforced a failing conclusion in that version.
- Removed the global /etc/resolv.conf rewrite from ResolverGuard. It is now a no-op scope marker; system NSS is left untouched. Existing fail-closed firewall rules prevent direct non-tunnel egress, and system DNS failures use IP-pinned DoH fallbacks.
- Restricted pinned HTTPS fallback for metadata and target HEAD requests to A records only. AAAA records remain independently collected as DNS evidence, but this backend has no IPv6 tunnel and host IPv6 egress remains blocked. An IPv6-only hostname now yields a clear inconclusive HTTPS result rather than an impossible IPv6 connection attempt.
- Added three regression tests: no global resolver file access, metadata fallback does not dial an IPv6-only host, and target HTTPS fallback does not attempt AAAA-only transport. VPN Gate test module now has 27 tests; the existing reachability module has 29; expected combined total is 56.
- Code commit: 01de6ed726c379811df0155c3db8534683a90009; tests commit: 110510c53551534f7dd216c8391ecf7ec3a61720; README commit: 00d398768c333beb6fac156985b21c5376c73784.
- Validation is pending for the 56-test code head. The last confirmed green validation (Run #103, 48 Python tests) predates the DoH fallback and this resolver/IPv4-only hardening; do not reuse it as validation for the latest code.
- Next: verify the new 56-test CI result; only then trigger the guarded one-shot pilot (one verified RU exit, at most three candidates), inspect the report/log and firewall restoration, then remove VPN_GATE_RUN_ONCE and the temporary feature-branch push trigger. Keep PR #5 Draft and preserve all production data/policy.
- No changes to geoip_RU.dat, production builder, release assets, DIRECT policy, ASN allowlists, main/release, or PR #6.


### 2026-11-11 — Review third pilot; preserve safe TLS profile compatibility fields — IMPLEMENTED / CI PENDING

- Third VPN Gate run #42964869207 completed with **failure** as intended by the strict workflow gate; it uploaded artifact 13830503498 (288,200 bytes; SHA-256 95569ff6f48cb9a1acb6a6fc5c9ce989e8be8402b5d8b6a452ae5a340a4710e3).
- It found 12 usable RU profiles across six origin ASNs and attempted three independent candidates:
  1. 188.242.100.160, AS35807 / SkyNet Ltd., prefix 188.242.96.0/19: TCP connection established on 1439, but no TUN route within 60 seconds.
  2. 178.185.24.224, AS12389 / OJSC Sibirtelecom, prefix 178.185.0.0/18: TCP connection established on 1529, but no TUN route within 60 seconds.
  3. 94.253.101.177, AS21453 / Flex broadband users, prefix 94.253.96.0/19: UDP remote selected, but no TUN route within 60 seconds.
- All three server endpoint IPs are already mapped as RU in the published inventory. No confirmed RU VPN egress, no target DNS/HTTPS requests, zero target measurements and no candidate exit IPs. Pinned DoH fallback was not exercised in this run because no VPN tunnel was established. The intended strict gate worked: diagnostic artifact uploaded, final workflow step failed.
- Inspected profile reconstruction. The runner previously copied CA/TLS key material, cipher, auth, and key-direction, but could drop other benign TLS compatibility directives from VPN Gate profiles. Extended the strict allowlist to preserve TLS min/max, TLS cipher/ciphersuites, TLS certificate profile, remote certificate EKU/KU, optional verify-x509-name, and inline tls-crypt-v2. remote-cert-eku and X509 name values are quoted safely.
- External TLS key file directives are now rejected rather than silently dropped. Arbitrary script/plugin/route directives remain excluded. Sanitized profile feature flags (block presence and selected TLS settings only, no key material) are recorded in raw diagnostics.
- OpenVPN verbosity raised to 4, and TLS failure detection now recognizes TLS Error: and VERIFY ERROR: in addition to the previous fatal markers. This gives better diagnostics on the next candidate set.
- Latest validation-triggering code/test commits: safe TLS options b89e4d3ab719a3216a52288317094869198b6b78, profile feature metadata 02dc6f65bf117338b55dae44f6af9f75c92bdbfb, quoting/verbosity fix f9636ff56d4e5fc47e8ad80b102651fc4aa6e7a6, external-key/TLS log detection 700d31cd548505d259e38af07366a3ef6eb46231, external-key regression test fed2a525ad80f22a50415766b6b32bbb0af8b3b6, README e02f7adfb17c84f7cf5f747a61a79453d27dea7e.
- VPN Gate test module now contains 29 tests; existing reachability test module contains 29; expected combined Python suite is 58. CI is pending for the latest TLS compatibility changes.
- Next: confirm CI; if green, consider one final bounded six-candidate run across six origin ASNs because the current dynamic CSV list has 12 profiles / 6 ASNs and three attempts have produced no stable TUN. Do not increase beyond six. If none connects, stop using VPN Gate as the sole measurement transport and add a locally supplied residential probe or another provider with documented exit availability.
- No production GeoIP changes, builder/release/main changes, DIRECT/ASN allowlist changes or PR #6 changes.


### 2026-11-11 — Final six-candidate pilot launched — RUNNING

- CI Run #? (Actions run `42966905885`, commit `11f5f74242feeee1a8d460fba243a91afb95b8be`) passed; job log shows `Ran 58 tests`, `OK`, plus successful gofmt, go test and go build.
- Feature-branch one-shot workflow fallback now allows up to six connection candidates for the final pilot (manual workflow_dispatch keeps its explicit default of three). Requested successful RU exit count remains one; hard cap six.
- One-shot marker commit: `74e855a830a1498302465d442e469d94af7e6471`, commit message `[vpn-gate-once] Final bounded six-ASN Russian VPN Gate pilot`.
- Final pilot Actions run: `42967015227`, URL https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/42967015227.
- At checkpoint update, the runner setup, Go install, exact release protobuf download/checksum and full inventory export are all complete. Measurement step started at `2026-11-11T05:38:41Z` and is still in progress. No artifact or completion result has been observed yet.
- Do not start another VPN run. After run completion, inspect the uploaded artifact, then remove the marker and disable the temporary feature-branch push trigger.


### 2026-11-11 — Final six-candidate VPN Gate pilot reviewed; one-shot trigger removed — COMPLETE / SOURCE LIMITATION

- Final VPN Gate run #42967015227 completed with **failure** at the strict measurement gate and uploaded artifact 13831409076. Artifact size 288,403 bytes; SHA-256 0121a497d2b2b19aad12b97d796ca7c6a730755b5a83267b7205a34d04b4e692.
- Although the run was allowed up to six candidate attempts, the live official VPN Gate CSV contained only three usable Russian OpenVPN profiles across two origin ASNs. All three were attempted:
  1. 188.242.100.160, AS35807 / SkyNet Ltd., prefix 188.242.96.0/19, TCP port 1439: TCP connected; TLS key negotiation timed out at 60s and TLS handshake failed.
  2. 94.159.74.210, AS49531 / NetCom-R LLC, prefix 94.159.74.0/23, UDP port 42581: no TUN/default route within 60s.
  3. 188.243.233.40, AS35807 / SkyNet Ltd., prefix 188.243.232.0/22, TCP port 1241: no TUN/default route within 60s.
- Final summary: usable RU profiles 3; inspected 3; distinct ASNs 2; attempted candidates 3; verified RU exits 0; target measurements 0; GeoIP candidates 0. All three VPN server endpoint IPs were already classified RU by the published inventory. No missing CIDR or service-access verdict was found.
- The DoH fallback and the extended TLS profile reconstruction were not exercised against a successful tunnel in the final run. Their unit tests pass, but their live behavior remains unverified because none of the volunteer relays established a TUN route. The first earlier retry had reached Initialization Sequence Completed on a Rostelecom node but DNS/NSS failed before exit verification; that was not a confirmed RU egress and yielded zero service measurements.
- Conclusion: VPN Gate is currently too unstable/unavailable in this environment to serve as the sole residential measurement backend. The 4 live pilots produced zero completed endpoint measurement rows. This is not evidence that the tested sites are blocked, and it is not evidence that GeoIP ranges are missing.
- Removed the one-shot marker file .github/reachability/VPN_GATE_RUN_ONCE and removed the temporary feature-branch push trigger from reachability-vpn-gate.yml. The workflow is manual-only (workflow_dispatch), with no daily schedule and no automatic push execution. Manual dispatch on GitHub becomes available when the workflow is integrated into the default branch; PR #5 remains Draft.
- Validation after trigger removal: Reachability validation run 42967694579 succeeded on commit 678534d57b01bb797669c81305a4239fc8ea5435. Its log reports 58 Python tests OK and successful gofmt, go test ./... and go build. The only later branch change is marker-file deletion (commit 908c0366c2abe1bc15eb3305f3a77c2314250d02); no executable code changed after the validated tree.
- Recommended direction for the original goal: use one or more explicitly consented, user-controlled probes physically connected to real Russian household ISP networks (small outbound-only agent on a router/PC), plus RIPE Atlas/other documented probes where actual ASN/operator can be independently validated. Keep Globalping/VPN Gate as supplementary evidence only; do not label a VPN exit as residential on country/ISP metadata alone.
- No changes to production builder, geoip_RU.dat, release assets, DIRECT policy, ASN allowlists, main/release or PR #6.
- Resume from: if the owner continues PR #5, build the voluntary home-network probe agent/API and a small operator-validated pilot; otherwise leave this PR as review-only auxiliary tooling. No more VPN Gate runs should be launched without new evidence of stable relay availability.


### 2026-11-11 — Final six-candidate VPN Gate result and cleanup — COMPLETE / SOURCE LIMITATION

- Final bounded run #42967015227 ended with **failure** at the final measurement gate; artifact 13831409076 uploaded and inspected. ZIP SHA-256: 0121a497d2b2b19aad12b97d796ca7c6a730755b5a83267b7205a34d04b4e692.
- The official VPN Gate API returned only three usable RU profiles at run time, from two origin ASNs, so the six-attempt budget could not be filled. All three available profiles were attempted:
  1. 188.242.100.160 — AS35807 / SkyNet Ltd., 188.242.96.0/19, TCP:1439. TCP connection succeeded; TLS key negotiation timed out at 60s and TLS handshake failed.
  2. 94.159.74.210 — AS49531 / NetCom-R LLC, 94.159.74.0/23, UDP:42581. No TUN/default route within 60s.
  3. 188.243.233.40 — AS35807 / SkyNet Ltd., 188.243.232.0/22, TCP:1241. No TUN/default route within 60s.
- Artifact summary: profiles=3, candidate ASNs=2, attempted=3, successful verified RU exits=0, target measurements=0, GeoIP candidates=0. All three VPN server endpoint IPs were already classified RU by prefixes in the current inventory. No new missing RU CIDR was identified.
- The DoH fallback and allowlisted TLS compatibility options still lack a successful live tunnel in which to be exercised. Unit tests cover them, but four live pilot runs never produced an RU egress plus target measurements. No target service is marked blocked or accessible from these data.
- Conclusion: VPN Gate is not currently reliable enough in this environment to act as the primary measurement path for Russian household ISPs. It is a volunteer relay pool, and the live API returned just three usable profiles on the final sample. Do not keep increasing retry budgets beyond six.
- Cleanup completed: removed .github/reachability/VPN_GATE_RUN_ONCE (commit 908c0366c2abe1bc15eb3305f3a77c2314250d02); removed the temporary push trigger from .github/workflows/reachability-vpn-gate.yml (commit 678534d57b01bb797669c81305a4239fc8ea5435). The VPN Gate workflow is now manual-only with workflow_dispatch, no push trigger and no schedule. Manual dispatch requires that the workflow be integrated on the repository default branch; PR #5 is still Draft, so it is not presently manually dispatchable from the branch.
- Validation after cleanup: Reachability validation run #42967694579 succeeded on commit 678534d57b01bb797669c81305a4239fc8ea5435. Its log reports 58 Python tests OK plus gofmt, go test ./... and go build successful. Comparing the validation commit to current HEAD 5204c5215d983be518fd5024199549b3473cff91 shows only README/WORKLOG changes and deletion of the one-shot marker; no executable code or workflow changes after the green validation.
- PR #5 remains OPEN / DRAFT. The feature-branch diff is 14 diagnostic/reachability files and three supporting workflows, all within .github/reachability and .github/workflows/reachability-*; no production builder/input/release/client file changed. PR #6 untouched.
- Recommended next implementation for the original intent: a small outbound-only, explicitly consented probe agent installed on actual household routers/PCs (or a documented provider with verifiable household-network ASN/operator), returning only measured DNS/HTTPS observations to the collector. Validate operator and access type independently; don't infer residential status from country/ISP metadata alone.
- No production GeoIP database, builder, release assets, DIRECT policy, ASN allowlists, main/release or PR #6 changes.
- Resume from this point only if the owner wants the residential probe agent or another verified provider; do not launch more VPN Gate retries without new evidence of stable relay availability.

### 2026-11-11 — Complete opt-in home probe and local GeoIP report importer — CI PASS

- VPN Gate work is closed for now: four bounded live pilots produced zero verified RU exits and zero target measurement rows. The temporary one-shot marker and push trigger were removed; do not launch further VPN Gate runs without evidence of a stable relay pool.
- Reviewed the opt-in local home probe added in commit 4089334e4b63a6264798f010757d1626a1b2e4ea. It runs on a consenting owner's actual ISP connection, performs system DNS A/AAAA and at most one HTTPS HEAD per family per selected hostname, writes only local reports, and does not inspect user traffic or collect credentials.
- Hardened the probe: proxy environment variables now cause a hard stop (there is no allow-proxy bypass); a two-source-confirmed country mismatch stops before any target requests; an existing non-empty output directory is never overwritten; metadata country codes must be valid two-letter codes; target catalogue default resolves relative to the script; source and summary reports carry schema_version=1.
- Each target measurement now records the exact first DNS address used for its IPv4/IPv6 HTTPS HEAD attempt. This prevents a later importer from falsely associating the transport result with a different address in the DNS RRset.
- Added .github/reachability/home_probe_ingest.py, a local-only importer that validates report version, two distinct metadata providers agreeing on one global source IP and required country, proxy absence, current target IDs/domains/roles, DNS address family/globality and tested HTTPS destination. It maps the source IP and DNS destination answers against a complete RU/PRIVATE inventory.
- The importer writes home_probe_provider.tsv, home_probe_observations.tsv, home_probe_candidates.tsv and home_probe_ingest_summary.json. Only the exact verified source IP outside RU inventory becomes a HOME_PROBE_SOURCE_IP review lead; no CIDR is inferred or added automatically. DNS destination observations are kept separate from the volunteer's source ISP.
- Updated README with local one-shot commands and inventory/import procedure. No report uploads automatically; reports include a public egress IP and should be shared only with the network owner's approval. Residential status remains unverified until operator/origin ASN/access type are independently confirmed.
- Added regression coverage for proxy refusal, wrong-country stop, output overwrite protection, report schema/source validation, exact HTTPS-tested IP, malformed/private/unknown target data, and exact-IP-only candidate creation. Current suite: 84 Python tests (29 runner + 29 VPN Gate + 14 home probe + 12 importer).
- Latest validation: Run #42971505831 (`https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/42971505831`) passed on commit e729971d11c39389015bfeca43cc6e39ff90fed5. Job log confirms Ran 84 tests; `gofmt`, `go test ./...` and `go build` all succeeded.
- Intermediate validation failures Run #42971350185/#42971305643 were caused by two safety tests using a nonexistent `targets.json` fixture. Their fixtures were corrected; Run #42971505831 is the validated head.
- No live home-network probe has been run; this code is ready for an explicitly consenting volunteer on a Russian household ISP. Begin with `--max-targets 3`, then use the complete RU target catalogue after the smoke test if the volunteer agrees.
- PR #5 remains OPEN / DRAFT. Changes remain limited to .github/reachability and .github/workflows/reachability-*; no production builder, geoip_RU.dat, release assets, DIRECT policy, ASN allowlists, main/release or PR #6 changes.

### 2026-11-11 — Tighten home-report importer country scope and evidence consistency — CI PASS

- Re-reviewed the local home-report importer after the first 84-test validated version. Found that the importer accepted a DNS_ANSWER row without the HTTPS attempt the probe is designed to make, and accepted a successful HTTPS response when DNS was marked as no-answer; both are now rejected.
- RU candidate policy is now country-scoped: a source egress IP outside the RU/PRIVATE inventory becomes a HOME_PROBE_SOURCE_IP candidate only when the report is explicitly attributed to RU. A KZ/BY source address may still be mapped as outside the RU inventory for context but never becomes a missing-RU-prefix candidate.
- Added cross-file consistency checks: summary source-attribution status, source ASN candidates and organizations must match the source report; each provider observation must agree on public source IP and country; ASN/organization lists must match provider metadata; source summary target-role counts must match measurement rows.
- Expanded importer tests for KZ source non-candidate behavior, missing/mismatched DNS-to-HTTPS attempt, ASN and organization provenance, source-attribution summary and role-count consistency. Current Python suite: 90 tests (29 runner + 29 VPN Gate + 14 home probe + 18 importer).
- Intermediate CI runs #42973628572, #42973694255, #42973767203 and #42973799457 failed while these new tests/fixtures were being added. Diagnosed causes: missing summary fixture fields, an escaped JSONL newline that wrote literal backslash-n, and a two-character TSV delimiter in the KZ test. All are corrected; latest CI Run #136 `42974036482` passes on commit `4879ac5e3a513c75c79cb3e19178a53fa9e7242a`.
- Run #42974036482 full log confirms `Ran 90 tests`, `OK`, and successful `gofmt`, `go test ./...` and `go build`.
- No live home-network probe has yet been run. Do not launch another VPN Gate pilot. The only remaining measurement evidence gap is one or more explicitly consented, directly connected household ISP reports from actual RU operators; review exact public source IP, origin ASN, access class and DNS/HTTPS observations independently.
- PR #5 remains OPEN / DRAFT. No production builder, `geoip_RU.dat`, release asset, DIRECT, ASN allowlist, main/release or PR #6 changes.


### 2026-11-11 — Add direct VPNObratno profile discovery and connection variants — CI PASS

- Revisited the four earlier VPN Gate pilots against the actual VPNObratno page. Those runs discovered nodes via the official VPN Gate CSV API; they did not exercise VPNObratno's directly linked IP UDP, UDP, IP TCP and TCP profile variants.
- Confirmed that the current VPNObratno Russia listing exposes .ovpn links under https://vpnobratno.info/servers/<listed-host>/<listed-host>_<mode>_<transport>.ovpn. The site says its nodes are operated by Russian VPN Gate users through different Russian ISPs; this is not proof that every node is a household broadband line.
- Added a VPNObratno HTML-link parser that accepts only HTTPS links on the exact vpnobratno.info origin and the expected vpnNNN.opengw.net directory/filename pattern. Query strings, fragments, other origins, mismatched hostnames and unsupported profile suffixes are rejected.
- Added direct profile retrieval and validation. IP UDP/IP TCP remotes must be public IPv4 literals present in the listed hostname's current DNS answers; UDP/TCP remotes must match that exact hostname. The profile's actual transport must match its listing variant. Existing strict OpenVPN reconstruction still drops scripts, plugins, route directives and external key files; downloaded profile directives are never executed.
- VPNObratno variants are recorded per provider and measurement row (SOURCE, PROFILE_VARIANT, PROFILE_URL). Variants of one node are separate connection attempts but do not count as distinct providers; origin ASN diversity remains based on RIPEstat/IP metadata. Repeated profile entries for the same server IP now reuse the cached origin lookup.
- Added --source vpnobratno|vpngate, defaulting to VPNObratno. Updated the manual-only workflow to expose the source selector and use VPNObratno by default. The previous official CSV API remains an explicit fallback. No schedule or feature-branch push trigger was enabled.
- Added five regression tests for same-origin profile link filtering, variant ordering, hostname/IP matching, direct profile download, and protocol mismatch rejection.
- Latest validation: GitHub Actions run #42977158414 (https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/42977158414) succeeded on code/workflow commit 3fb7646d2005a7787bf715b680ec5683b1365818. Full job log confirms Ran 95 tests, OK; gofmt, go test ./... and go build also passed.
- Intermediate validation runs #42976990895 and #42977081461 caught over-escaped URL regexes and an incorrect test expectation for the deliberate no-usable-profiles error. These were corrected; runs #42977032588, #42977100251 and #42977158414 passed for the corresponding corrected commits. Final validation is the 95-test run above.
- No live connection using VPNObratno's linked profile variants has been run. The four earlier failed tunnel pilots remain evidence only about their specific official-API profiles at that time; they do not establish that the newly supported profile variants fail. No target access or blocking conclusion is available until a verified RU tunnel yields target measurement rows.
- GitHub workflow_dispatch for a workflow introduced only on a Draft PR is not available until the workflow exists on the default branch. The workflow remains manual-only; do not restore the one-shot push trigger or schedule merely to bypass that constraint.
- PR #5 remains OPEN / DRAFT. Changes are limited to .github/reachability/ and .github/workflows/reachability-*; no production builder, release/geoip_RU.dat, release assets, DIRECT policy, ASN allowlists, main/release or PR #6 were touched.


### 2026-11-11 — Tune the first VPNObratno pilot to exercise bounded profile fallback — CI PASS

- Reviewed the current VPNObratno listing and confirmed the published OpenVPN links include per-node UDP and IP UDP variants, with TCP and IP TCP on some nodes; several nodes expose fewer variants than others.
- Found a configuration issue in the first manual pilot defaults: it requested three successful RU exits while allowing only three profile attempts. That left no practical retry budget for alternative profile variants.
- Changed the collector CLI defaults to one verified RU exit and up to six total profile attempts. The source remains VPNObratno by default; the official VPN Gate CSV API remains selectable as fallback. The hard cap remains six attempts and six successful exits.
- Changed workflow_dispatch defaults to one successful RU exit / six profile attempts. This is still manual-only; no schedule or push trigger was added.
- Added a regression test that invokes the CLI with only the required inventory path and verifies source=vpnobratno, max_servers=1, max_attempts=6.
- Updated README to explain the one-exit/six-profile pilot budget.
- This is a configuration and deterministic-test improvement only. It does not establish a working tunnel or any target accessibility result. Do not infer a residential line from VPNObratno's listing.
- Latest validation: GitHub Actions run #42979907101 (https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/42979907101) passed on code/workflow commit 0961e543b723dd90c14a4c3c5ed5cad931d0cc88. Full logs confirm Ran 96 tests, OK; gofmt, go test ./... and go build also passed. A concurrent earlier attempt #42979881032 was cancelled by the newer validation run; it is not the final result.
- PR #5 remains OPEN / DRAFT. No production builder, release database/assets, DIRECT policy, ASN allowlists, main/release or PR #6 were touched.


### 2026-11-11 — Harden VPNObratno profile downloads against cross-origin redirects — CI PASS

- Re-audited the direct VPNObratno fetch path. The HTML parser already accepted only profile links on the exact HTTPS origin, but the generic urllib downloader could follow a server-side redirect to another hostname.
- Added a dedicated downloader for the VPNObratno listing and linked profiles. It disables configured proxies, accepts HTTPS only on the exact vpnobratno.info origin/default port, rejects userinfo and non-default ports, permits redirects only within that origin, and checks the final response URL again.
- The VPNObratno discovery routine now uses this constrained fetcher by default. The official VPN Gate API backend keeps its separate existing fetch behavior.
- Added four regression tests for cross-origin/insecure redirect rejection, exact same-origin redirect acceptance, rejection of untrusted initial URLs before network access, and the discovery default fetcher.
- Latest validation: GitHub Actions run #42981728009 (https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/42981728009) succeeded on code/test commit 5b2d74a8b2653d16248e965abfaa0a05f0d3d344. Full job logs confirm Ran 100 tests, OK; gofmt, go test ./... and go build also passed. The intermediate attempt #42981701144 was cancelled by the newer validation run.
- Reviewed the remaining VPNObratno protocol documentation. SSTP is offered on some nodes; the site documents L2TP/IPsec for selected nodes. Neither has yet been wired into the collector: the copy-button endpoint metadata/port is not yet verified as a machine-readable source, and a PPP/IPsec tunnel requires explicit interface, route and firewall lifecycle checks. Do not guess the SSTP port or invent an L2TP endpoint. Continue with the four validated OpenVPN variants until those prerequisites are proven.
- No live tunnel using the newly supported VPNObratno OpenVPN profiles has yet been run. The 100-test CI result verifies deterministic discovery, validation and the fetch safety policy, not live tunnel connectivity or target reachability.
- PR #5 remains OPEN / DRAFT. No production builder, release database/assets, DIRECT policy, ASN allowlists, main/release or PR #6 were touched.


### 2026-11-11 — Bound and diversify VPNObratno profile discovery — CI PASS

- Reviewed the current VPNObratno Russia listing (the live page showed approximately ten server entries and up to four OpenVPN profile links per entry). A single run previously downloaded every linked profile before the separate six-connection-attempt limit was applied.
- Added a hard cap of 24 VPNObratno profile downloads per discovery run. The summary reports total links found, download limit, profiles considered, links omitted by the cap and whether the cap was reached. The cap is separate from the six actual VPN connection attempts.
- Changed profile ordering to interleave variants across hostnames: preferred IP UDP profiles from all listed servers first, then DDNS UDP, IP TCP and DDNS TCP. A bounded discovery sample therefore covers more distinct server hostnames before downloading alternate profiles for the first hosts.
- Added three tests for cross-host variant interleaving, bounded profile downloads/omitted-link accounting, and rejection of an invalid or over-hard-cap discovery limit.
- The first validation attempt #42983239336 caught a fixture method being called from a test class without that helper. The corrected attempt #42983387247 exposed the same call at its second occurrence; the fixture was then made self-contained. Final run #42983494770 (https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/42983494770) succeeded on test commit 6e408c3852d3fbfe8b9ebd4f5689533f08e51fbe: full logs confirm Ran 103 tests, OK, plus successful gofmt, go test ./... and go build.
- The live page snapshot is time-varying. The 24-link cap and metadata prevent excessive downloads and make truncation visible; no inference is made about servers beyond the fetched sample. A run with a truncated sample cannot claim complete server/provider discovery.
- No VPN connection was attempted. CI verifies selection order and bounded downloads, not actual tunnel availability or household/residential status.
- PR #5 remains OPEN / DRAFT. No production builder, release database/assets, DIRECT policy, ASN allowlists, main/release or PR #6 were touched.

### 2026-11-11 — Bound VPNObratno response reads by resource — CI PASS

- Re-audited the profile download path after the 24-link discovery cap. The previous downloader used an 8,000,000-byte read limit for both the HTML listing and each .ovpn profile, then applied the 64,000-byte profile check only after the response had already been read.
- Added explicit resource limits: 2,000,000 bytes for the listing and 64,000 bytes per profile. The shared fetch helper validates every requested limit against a hard 8,000,000-byte ceiling and reads only max_bytes + 1; an over-limit body is rejected immediately after the single extra byte proves it oversized.
- Discovery now passes the smaller limit for each resource. The existing post-fetch profile-size check remains as defense in depth for custom/test fetchers.
- Added regression coverage for exact-limit acceptance, limit-plus-one rejection, enforcement of the hard ceiling before opening a connection, and correct listing/profile limit forwarding. Existing mocked discovery fetchers were updated to accept the explicit limit.
- Validation run #42986373320 (https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/42986373320) succeeded on code commit 7dd4eb483e6fba9143c5664210625b1e7dfdd23c. Full job logs confirm Ran 104 tests, OK; gofmt, go test ./... and go build passed.
- This hardens transfer-size/resource bounds only. No VPN connection was attempted, no target was tested through a VPNObratno exit, and no residential/home-network status was established.
- PR #5 remains OPEN / DRAFT. Production GeoIP builder/data, release assets, DIRECT policy, ASN allowlists, main/release and PR #6 remain untouched.


### 2026-11-11 — VPNObratno live-run preflight blocked by default-branch workflow gate

- The owner requested a live VPN connection and continuation. Rechecked PR #5 head (8c950350bca4f85309c9dd36e6e5cc6ad5e5a403), current Draft/open state and the default branch.
- Confirmed the workflow file .github/workflows/reachability-vpn-gate.yml exists on feature/reachability-full-ru-kz-by but is absent from main. The current main workflow tree contains only .github/workflows/blank.yml and .github/workflows/prefix-audit-validation.yml.
- The VPN workflow remains strictly workflow_dispatch only. GitHub requires the manually dispatched workflow file to exist on the default branch before it can run against a selected branch (official docs: https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow). The available GitHub integration exposes repository/Actions reads and reruns, but no workflow-dispatch action.
- No VPN job was started; there is no run ID or artifact for this request. This is a dispatch gate, not a VPN connection failure and not evidence about RU site access.
- Did not merge PR #5, modify main, add a push/schedule/repository-dispatch workaround, or touch PR #6 / production files. PR #5 remains OPEN / DRAFT.
- To execute the requested live test, the owner must explicitly authorize placing the workflow on main (through PR approval/integration or a separately scoped workflow-only change) and provide a supported manual dispatch path. Preserve the pilot defaults: one independently verified RU exit, up to six profile attempts, 24-profile discovery cap; require two-source public-IP/country consensus before sending target requests.


### 2026-11-11 — Publish only the VPN workflow file to main; live dispatch pending

- The owner explicitly approved adding only .github/workflows/reachability-vpn-gate.yml to default branch main, without merging PR #5. Copied the already reviewed workflow blob from PR #5 into a new tree based on main and committed it as 580a25a7a65d957d46d83e827ccbd9308969713e. Commit inspection shows exactly one changed file: .github/workflows/reachability-vpn-gate.yml (123 additions, no deletions). PR #5 remains OPEN / DRAFT.
- This makes the manual workflow visible from the default branch. The actual runner code and support files remain on feature/reachability-full-ru-kz-by; manual launch must choose that branch under "Use workflow from", source=vpnobratno, max successful exits=1, max profile attempts=6.
- The available GitHub integration has no workflow-dispatch action and the runtime has no GitHub CLI. No workflow_dispatch event was sent; no VPN job ID or VPN artifact exists yet. The Actions workflow page is https://github.com/SpeedeMiner/Geoip-ru-server/actions/workflows/reachability-vpn-gate.yml.
- Operational side effect discovered after the main push: the pre-existing .github/workflows/blank.yml Build Unified GeoIP DIRECT RU+BY+KZ CLIENT v37 workflow ran automatically on main commit 580a25a7a65d957d46d83e827ccbd9308969713e. Run #42989906746 completed successfully; job steps included "Publish GitHub Release" and "Publish release branch". The release branch was force-updated from the previous abbreviated ref d613c5f… to ac2e9a4322c0b7efe293983c88cf5b304771e4c5, and v37 release assets were refreshed (geoip_RU.dat asset size 951,553 bytes). A byte-for-byte comparison with the preceding geoip_RU.dat was not established. This was an indirect side effect of pushing to main; no production build inputs/workflow files or GeoIP source code were intentionally changed. Do not attempt to rewrite release data or roll back the release branch without separate owner authorization.
- No VPN connection or target request has yet been performed. The next step is a manual workflow_dispatch against feature/reachability-full-ru-kz-by, then inspect two-provider exit-IP/country consensus before target tests.


### 2026-11-11 — VPNObratno manual dispatch cancelled before diagnostics were uploaded

- Successfully dispatched workflow run #42993670031 (https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/42993670031) using `workflow_dispatch` against `feature/reachability-full-ru-kz-by`, commit `70f7108f0916b2a2d0a671810e9da5d2526548d6`, with `source=vpnobratno`, `max_vpn_gate_servers=1` and `max_vpn_gate_attempts=6`.
- GitHub confirmed the setup steps completed: runner setup, checkout, OpenVPN/iptables installation, Go setup, exact published GeoIP protobuf download/checksum, and export of RU/PRIVATE prefixes.
- The step `Run capped VPNObratno / VPN Gate Russian-exit measurements` entered `in_progress`. Live UI inspection showed only the shell prologue `Run set -euo pipefail`; no candidate/tunnel output was visible before the run was cancelled. REST metadata confirms run conclusion `cancelled` at 2026-11-11T09:22:46Z. The browser UI labelled it as manually cancelled by `@SpeedeMiner`; the REST actor fields identify the triggering account only and do not independently identify who issued the cancellation.
- The `Upload VPN Gate reports` step remained pending, the final failure-gate step did not run, and the workflow run exposes no artifacts. The job log archive endpoint also returned BlobNotFound after cancellation.
- This attempt therefore produced no usable live VPNObratno connection result: verified RU exits and target measurements are **NOT MEASURED**, not zero and not evidence of blocking. The earlier four VPN Gate CSV pilot results remain separate and are not evidence about these linked VPNObratno profiles.
- Do not automatically dispatch a replacement after this cancellation. First establish whether the cancellation was intentional or obtain explicit authorization for another attempt. Preserve the one verified RU exit / six-profile-attempt budget and the two-source exit-IP/country gate.
- PR #5 remains OPEN / DRAFT. No production builder/data, release assets/branch, DIRECT policy, ASN allowlists or PR #6 were changed by this dispatch.


### 2026-11-11 — Investigated the VPNObratto pilot cancellation attribution

- The repository owner explicitly stated they did not cancel workflow run #42993670031.
- The GitHub REST run object reports `actor` and `triggering_actor` for the workflow dispatch; it does not provide a `cancelled_by` field. Those account fields identify the run initiator and are not evidence of who cancelled it. The live browser UI's attribution to `@SpeedeMiner` was therefore misread; do not repeat it as a fact.
- Browser automation chronology: dispatch session 09:14:43–09:18:31 UTC; read-only live-log inspection 09:20:49–09:22:03 UTC; GitHub run `updated_at` / cancellation at 09:22:46 UTC; follow-up read-only inspection started 09:22:55 UTC. No browser session was active at the recorded cancellation time. No explicit GitHub workflow-cancel command was invoked by this assistant.
- The confirmed fact is only that GitHub ended run #42993670031 with conclusion `cancelled`. The cancellation actor/cause remains **UNKNOWN**. The prior WORKLOG sentence quoting the UI attribution is superseded by this correction.
- The owner still expects the requested live pilot to proceed. Resume with a new manually dispatched run, preserving the same feature branch and limits (VPNObratno, one verified RU exit, at most six profile connection attempts). Do not change workflow triggers or production files to work around the cancellation.


### 2026-11-11 — Shorten VPNObratto tunnel wait to 5 seconds and expose live progress — CI PASS

- The owner reviewed run #42996316782 and observed the live command still had `--connect-timeout 60` after more than 12 minutes without visible phase progress. That run was dispatched on earlier commit `435587a28778119e40d0bfdd6e45d7104ac4fe48`; its command line and runtime cannot be changed after start.
- Reduced the VPN route-establishment wait from 60 to **5 seconds per profile** in both the CLI default and the manual workflow. The CLI accepts 5–180 seconds and rejects smaller values. Maximum attempts remains six; this gives at most 30 seconds of explicit `wait_for_tunnel` route-wait budget across six attempts, excluding setup, discovery, ASN lookup and metadata requests.
- Kept the separate DNS/HTTPS request timeout at 12 seconds. The 5-second value only bounds waiting for an IPv4 TUN route after an OpenVPN process starts; it does not bound listing/profile downloads or RIPEstat/IP-metadata lookups. A slow volunteer relay may now be rejected earlier, which is an intentional speed-versus-tolerance tradeoff, not a blocking verdict.
- Added flushed progress messages for VPNObratto listing, each profile download/result, each candidate origin-ASN lookup, candidate selection, each OpenVPN attempt and successful route installation. Future GitHub Actions logs should identify which phase is taking time rather than showing only the shell prologue until the final summary.
- Added tests asserting the CLI default is five seconds and an explicit `--connect-timeout 5` is accepted.
- Validation run #42999166787 (https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/42999166787) passed **105 Python tests**, Python compilation/JSON validation, `gofmt`, Go tests and Go build. The earlier code-only validation run #42998594313 and workflow test validation #42998719121 also completed successfully.
- The in-progress run #42996316782 is unchanged: it checked out commit `435587a`, was launched with `--connect-timeout 60`, and remained `in_progress` at the latest status check. It had not reached report upload and had no artifacts at that check. This run must not be described as using the new five-second timeout.
- Keep PR #5 OPEN / DRAFT. No production builder, GeoIP database, release branch/assets, DIRECT policy, ASN allowlists or PR #6 were modified.


### 2026-11-11 — Updated live pilot #7 confirms five-second timeout and phase progress

- Run #42996316782 (#6), which was still active in the last earlier check, later ended with conclusion `cancelled` at 2026-11-11T09:58:48Z. Its measurement step was cancelled, artifact upload failed, no artifact exists and no target measurement result was produced.
- Cancellation attribution remains **UNKNOWN**. The REST run object exposes dispatch actor fields, not a cancellation actor. The last read-only monitor for #6 finished at 09:47:25Z; the next browser session (for dispatching #7) started at 09:59:34Z, after the cancellation. No explicit GitHub workflow-cancel command was invoked by this assistant. Do not attribute this cancellation to the owner.
- Dispatched run #43000272971 (#7) with `source=vpnobratno`, `max_vpn_gate_servers=1`, `max_vpn_gate_attempts=6`, feature branch `feature/reachability-full-ru-kz-by`, and commit `12d0f98f9b5e5d18518e3a517d8858f69f6f426c`.
- Live GitHub Actions log inspection confirms the updated code is running with `connect_timeout=5s`. Discovery completed with 24 usable profiles; origin ASN selection inspected 24 profile records and selected six profiles across six distinct ASNs. The first OpenVPN attempt is `vpn266997445.opengw.net`, variant `IP_UDP`, server IP `217.144.174.117`, attempt 1/6.
- At the latest live-log snapshot, the first connection attempt had not yet reported a TUN route. Independent exit IP/country verification had not started and no target DNS/HTTPS request had been sent. This is an in-progress attempt, not a negative reachability result.
- Validation on the same feature-branch code commit #42999166787 passed 105 Python tests, Python compilation/JSON validation, `gofmt`, `go test ./...` and `go build`.
- Keep PR #5 OPEN / DRAFT. No production builder, GeoIP data, release branch/assets, DIRECT policy, ASN allowlists or PR #6 were modified.


### 2026-11-11 — Root cause analysis for the apparently stalled run #7

- At 10:27 UTC the owner reported that run #7's live log had not advanced beyond:
  `phase=origin_asn_selection completed selected_profiles=6 distinct_asns=6`
  `openvpn_attempt=1/6 ... connect_timeout=5s`
- The exact source at the run's checkout commit `12d0f98f9b5e5d18518e3a517d8858f69f6f426c` shows `openvpn_attempt` is emitted **before** server IP metadata, origin metadata fallback and reverse-DNS PTR lookup. OpenVPN is spawned only after those preflight operations. Therefore the 5-second `wait_for_tunnel` limit had not necessarily started when that log line appeared.
- Critically, the old `resolve_ptr()` used `socket.gethostbyaddr()` without any timeout. This call can block in the system resolver indefinitely. That is the strongest code-supported explanation for the unchanged attempt marker, although the old run does not have intermediate preflight log markers and its exact blocked syscall cannot be proven from the available live log.
- Also, the old run's server metadata and RIPEstat calls occur before OpenVPN is spawned (metadata calls are bounded individually but can add latency); the attempt marker did not distinguish any of those phases. The prior progress reporting treated that marker as proof that the OpenVPN 5-second timer had begun; this interpretation was wrong.
- Fixed on the feature branch after run #7 was dispatched: `resolve_ptr()` now uses `getent hosts` with a hard 3-second subprocess timeout and fails open to an empty PTR string. Added flushed phase messages for server IP metadata, PTR lookup, OpenVPN process starting/started, tunnel route wait started, per-attempt failure and completion. This makes the preflight and actual tunnel wait independently visible.
- Added three PTR tests: successful lookup uses the configured 3-second timeout, resolver timeout is non-fatal, and absence of `getent` skips the lookup. Latest validation run #43002007469 (https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43002007469) passed **108 Python tests**, Python compilation and JSON validation, `gofmt`, Go tests and Go build.
- Current run #43000272971 (#7) remains `in_progress` on its original checkout commit `12d0f98`, not the fixed commit `b58a9ef`. Its last REST update was 10:02:55 UTC; the measurement step is still `in_progress`, report upload is pending and no artifacts exist. The code fixes do not retroactively alter a running job.
- I did not send a GitHub cancel request: the connected GitHub API actions do not expose a cancel-run operation, and clicking Cancel in the saved browser session would act under the repository owner's GitHub identity, making attribution ambiguous. Given the owner previously disputed a cancellation attribution, I should have immediately explained this blocker and requested explicit approval rather than continuing passive polling.
- Do not interpret lack of progress as a target reachability result. No confirmed RU tunnel, independent exit IP/country verification or target probe has been recorded for run #7.

### 2026-11-11 — Explicitly cancel stalled run #7 and resume on fixed revision

- The owner explicitly authorized cancellation and continuation in this conversation. I used the saved authenticated GitHub browser session to request cancellation of run #43000272971 (#7). GitHub displayed “You have successfully requested the workflow to be canceled”; the REST run object later reached `status=completed`, `conclusion=cancelled`, `updated_at=2026-11-11T10:38:43Z`. This was an assistant-submitted cancellation under the owner's explicit authorization; it must not be misattributed to an unsolicited action by the owner.
- The prior paragraph in this WORKLOG saying “I did not send a GitHub cancel request” described the state before the owner's approval and is superseded for run #7 by this entry.
- Root-cause review: run #7 checked out `12d0f98f9b5e5d18518e3a517d8858f69f6f426c`. At that revision, `resolve_ptr()` called `socket.gethostbyaddr(address)` without any timeout. The `openvpn_attempt` log marker occurs before server metadata, RIPEstat origin lookup and PTR resolution; OpenVPN is spawned only after those preflight steps. Thus `connect_timeout=5s` had not necessarily started when that marker appeared. An unbounded PTR resolver call is the strongest code-supported cause; because the old revision lacked per-phase logs and its log archive was unavailable, the exact blocked call cannot be proven from runtime evidence.
- The fix is committed in `b58a9ef02acfe90a2210b7a055a113db97bbf33d`: replace blocking `socket.gethostbyaddr` with `getent hosts` under a hard 3-second subprocess timeout; log server metadata start/completion, PTR start/completion, OpenVPN process start, tunnel-route wait and per-attempt result. CI #43002007469 passed **108 Python tests**, Python compilation/JSON validation, `gofmt`, `go test ./...` and `go build`.
- Run #8 was dispatched once after run #7 reached its terminal cancelled state: [run #43005642411](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43005642411), workflow run #8, branch `feature/reachability-full-ru-kz-by`, checkout SHA `b05db19acec8ba622041606b55fa41f79c771848` (two documentation/checkpoint commits after the validated code commit `b58a9ef`), inputs `source=vpnobratno`, `max_vpn_gate_servers=1`, `max_vpn_gate_attempts=6`, `connect_timeout=5s`, `request_timeout=12s`.
- At the latest check, run #8 had completed setup, checkout, OpenVPN tool installation, Go setup, published GeoIP checksum verification and RU/PRIVATE inventory export. The measurement step was `in_progress`; report upload was still pending. No verified RU exit, exit-IP/country consensus, or target measurement is yet confirmed. Do not infer a tunnel result from the GitHub job status alone.
- GitHub's job-log archive endpoint did not expose a downloadable log archive while the job was running. Continue tracking via the run/job status and fetch the diagnostic artifact after the job reaches a terminal state.
- PR #5 remains OPEN / DRAFT. PR #6, the production builder, `geoip_RU.dat`, release assets/branch, DIRECT policy and ASN allowlists remain untouched by this cancellation/fix/run sequence.

### 2026-11-11 — Remove optional metadata from the tunnel critical path; run #8 outcome

- Run #8 [43005642411](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43005642411) was cancelled with the owner's authorization after live log inspection showed no progress beyond the third candidate's PTR preflight for more than seven minutes. GitHub's final REST status is `completed / cancelled` at 2026-11-11T10:54:28Z.
- The live logs showed that attempts 1 and 2 actually spawned OpenVPN and both failed with the exact bounded result `OpenVPN tunnel did not install an IPv4 default route within 5s`. Candidate 3 reached `server_ptr_lookup=started` but had not spawned OpenVPN when the run was cancelled. No candidate produced a verified RU tunnel; no target DNS/HTTPS requests were sent; no diagnostic artifact was uploaded.
- The previous fix made PTR best-effort with `getent` timeout 3s, but live output still showed the third preflight lingering at PTR. Since server-side IP organization and PTR enrichment are not required for a tunnel attempt, the workflow no longer performs those calls in the connection critical path. It reuses the RIPEstat origin ASN/prefix cached during candidate selection; `SERVER_ORG` and `SERVER_PTR` may be blank. The two-source public exit-IP/country consensus check after tunnel establishment is unchanged.
- Added three tests for using cached origin metadata, missing cache and rejecting a prefix that does not contain the server IP. The obsolete PTR lookup tests/function were removed from the critical runtime path.
- Added hard workflow guardrails: the VPN measurement step now has `timeout-minutes: 10`, and the enclosing job `timeout-minutes: 20`; diagnostic upload remains an `always()` step.
- CI run [43007678277](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43007678277) on commit `0946a77171bcd7c69ecf62ab5ec3907e3e1f19d7` passed **108 Python tests** plus Python compile/JSON validation, `gofmt`, `go test ./...` and `go build`.
- The current code, tests, workflow timeout and README note are committed in PR #5. Next step is one fresh manual pilot from the current feature-branch tip, still `vpnobratno`, one verified RU exit target, at most six profile attempts, and a 5-second TUN-route wait.
- PR #5 remains OPEN / DRAFT. PR #6 and all production builder/data/release/DIRECT/ASN-policy files remain untouched.

### 2026-11-11 — Run #9 dispatched after removing optional preflight enrichment

- After the 108-test CI pass, the manual VPNObratto workflow was dispatched once as [run #43008159447](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43008159447) from feature branch commit `24fd242b0dce540132b0346df17030b5b00e6d3c`.
- Inputs: `source=vpnobratno`, `max_vpn_gate_servers=1`, `max_vpn_gate_attempts=6`; OpenVPN TUN-route wait remains `5s`. The manual workflow now caps the measurement step at 10 minutes and the job at 20 minutes.
- Before this dispatch, run #8 was confirmed terminal `cancelled`; no VPN workflow was queued or in progress.
- At dispatch, setup, checkout, VPN tooling, Go setup, published GeoIP checksum verification and RU/PRIVATE inventory export all passed. The measurement step is `in_progress`; no verified RU exit or target measurements are confirmed yet.
- The code no longer performs server IP-organization or reverse-PTR lookups in the per-attempt preflight; it reuses the RIPEstat origin ASN/prefix cached during candidate selection. Those optional metadata fields may be empty; post-tunnel two-source exit IP/country verification is unchanged.
- PR #5 remains OPEN / DRAFT; no changes to PR #6 or production builder/data/release/DIRECT/ASN policy.

### 2026-11-11 — Run #9 established a RU tunnel; report persistence bug fixed

- Run [#43008159447](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43008159447) checked out commit `24fd242b0dce540132b0346df17030b5b00e6d3c` and selected `vpn175354437.opengw.net`, IP `95.26.213.75`, variant `IP_UDP`.
- Live logs confirm `tunnel_result=route_installed` only about 3 seconds after process start, within the configured 5-second route wait.
- Control-flow reconstruction from the exact source and traceback confirms the post-tunnel `ip_metadata()` call completed and the returned `country` was `RU`: otherwise execution could not have reached `test_target()`. That function requires two independent metadata services to agree on exact public IP and country before returning. Therefore a two-source RU egress consensus was reached; however, the exact exit IPv4/ASN was not persisted because the later report-row construction crashed.
- The first target is `control-example` / `example.com`. The traceback occurs in `row.update()` after `test_target(target, ...)` returned, so the first control DNS A/AAAA and HTTPS HEAD test was invoked. Its actual DNS/HTTP outcomes are not present in any artifact and cannot be recovered.
- Root cause: the optional per-server IP/PTR enrichment was correctly removed, but one remaining row field still read deleted local `server_meta["org"]`. This raised `NameError` at line 1432 before any measurement/provider/summary files were written. Run #9 ended in failure; uploaded artifact ID `13849950456` (SHA-256 `d5c65ba51d9b29264fe520b5e2346f07d455b5d3b2f65422b1629b400d95b490`) contains only `reachability_inventory.tsv`, not VPN result reports.
- Fixed by adding `server_measurement_report_fields()`, which preserves cached server ASN metadata and intentionally sets `SERVER_ORG=""` without requiring removed per-server enrichment. Added regression test `test_measurement_report_fields_do_not_require_skipped_server_enrichment`.
- Code fix commit: `fdf3b14ad48f3d060d43fdd843d068fd8d7b6b5d`. Regression-test commit / current head at test dispatch: `7557204f751735cc71e3b8d2aa46131960ae611e`. CI runs #43010330356 and #43010335180 were started for the code and test commits respectively; wait for the latest commit's run to pass before another VPN dispatch.
- Interpretation: this is the first actual successful VPNObratno OpenVPN tunnel and RU exit-country consensus in this pilot series. It is **not** yet a usable target-reachability result because DNS/HTTPS statuses and the exit IP were not saved. The VPN exit's residential/home access classification also remains unverified.
- PR #5 remains OPEN / DRAFT. PR #6 and production builder, GeoIP database, release branch/assets, DIRECT policy and ASN allowlists remain untouched.

### 2026-11-11 — Run #10 cancelled after slow serial ASN preflight; bounded selector fix validated

- Manual VPNObratto run [#43012803707](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43012803707) was dispatched once from feature-branch HEAD `89ddd9c346dd062c900ec2610d2f55a28ac91a72`, with `source=vpnobratno`, one requested verified RU exit and at most six connection attempts.
- Preparation succeeded: exact published GeoIP artifact/checksum was downloaded and verified; the RU/PRIVATE inventory was exported; VPNObratto discovery found 36 links and 24 usable profile variants across the configured download cap.
- Live logs entered `phase=origin_asn_selection` with 24 candidates. The last visible lookup marker remained `origin_asn_lookup=10/24 host=vpn765560917.opengw.net` for more than six minutes. There was no `phase=origin_asn_selection completed`, no selected-profile list and no `openvpn_attempt`, process-start, route-wait, RU-exit-consensus or target-test marker.
- Run #10 was cancelled under the earlier explicit authorization to stop stalled VPN runs in this workstream, and GitHub confirmed `You have successfully requested the workflow to be canceled`. REST later confirmed run `completed / cancelled` at `2026-11-11T11:50:00Z`; job ID `130496358155` is `completed / cancelled`. No artifacts were uploaded. This run therefore produced **zero OpenVPN attempts, zero verified RU exits and zero target measurements**; it is not reachability evidence about any target or Russian ISP.
- Code review located the slow path: candidate selection called `network_info()` serially for up to 24 profile records. That helper uses the general metadata fetcher, whose system-DNS request may fall back to pinned DoH and multiple address attempts. Its socket timeout does not provide a reliable hard wall-clock bound for a resolver stall. The exact blocked syscall in run #10 cannot be proven from the live log.
- Fix committed in `31c88963af00fece984e00ae77ff548fc54207d3`: added a selection-only `selection_network_info()` helper. It uses IPv4 `curl` with `--connect-timeout 2`, `--max-time 5`, and an outer subprocess timeout of 7 seconds; failed/slow lookups leave ASN unverified and do not block selection. The existing post-tunnel `network_info()` / pinned fallback path remains unchanged, so two-provider public exit-IP/country consensus and RIPEstat exit metadata checks are not weakened.
- The selector now emits a flushed `origin_asn_lookup_result=i/n ... asn=... status=ok|unavailable` marker after each candidate lookup, in addition to the existing start marker.
- Added three tests covering successful bounded curl parsing, subprocess timeout, and failed HTTP request; updated ASN-diversity unit tests to mock the selection-specific helper.
- Validation [#43015247219](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43015247219) on current head `069bbee351f2b6f2b3dcc2adf7b1c3806d8ca224` passed **112 Python tests**, Python compilation/JSON validation, `gofmt`, `go test ./...` and `go build`.
- Next: confirm no active VPN run, then dispatch one run #11 from the current feature-branch tip. Check that all 24 selection lookups emit a result marker and that OpenVPN starts; download and reconcile the artifact before making any target-access conclusion.
- PR #5 remains OPEN / DRAFT. PR #6, production builder, `geoip_RU.dat`, release assets/branch, DIRECT policy and ASN allowlists remain untouched.

### 2026-11-11 — Run #11 stopped in origin-ASN scan; selector now stops once diversity budget is met

- Manual VPNObratto run [#43016153615](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43016153615) used feature-branch commit `5d530c423b61d571c4271671f9e912c55ad2167e`, with one requested verified RU exit and up to six connection attempts.
- Setup, GeoIP checksum verification and RU/PRIVATE inventory export succeeded. Discovery found 36 listing links and downloaded 24 usable OpenVPN profile variants.
- A live log snapshot showed 14 completed `origin_asn_lookup_result` records, followed by `origin_asn_lookup=15/24 host=vpn712485771.opengw.net` at `2026-11-11T11:57:45Z`. No result marker for candidate 15, no selection-complete line, no OpenVPN attempt, no route wait, no exit consensus and no target request were visible in the latest snapshot.
- At the later REST check the measurement job was still `in_progress` well beyond the configured 10-minute measurement-step timeout. The owner had previously explicitly authorized cancellation of stalled VPN runs in this workstream. I requested cancellation of this exact run; GitHub displayed `You have successfully requested the workflow to be canceled`. REST confirmed run `completed / cancelled` at `2026-11-11T12:22:06Z`, job ID `130507629391` also `completed / cancelled`. No artifacts were uploaded.
- Run #11 had **zero OpenVPN connection attempts, zero verified RU exits and zero target measurements**. This is a preflight execution failure and provides no evidence about target accessibility or blocking.
- The earlier inspection snapshot that mentioned 24 selected profiles and eight distinct ASNs was internally inconsistent with the configured `max_attempts=6` and the rows shown. It is superseded: 24 is the number of profile candidates inspected/downloaded, not the number selected for OpenVPN. The best-grounded live snapshot confirms 14 completed lookups plus candidate 15 started; the first eight results already contained six distinct ASNs (42116, 12389, 3216, 41789, 41733, 20485).
- Code review confirms the selector continued scanning all 24 candidates even after it had already accumulated enough distinct ASNs to fill the six-attempt budget. The per-request 7-second guard added before run #11 is present in the checked-out code, but the exact lower-level cause of the stalled candidate-15 operation is not proven from the available running logs.
- Fix committed on the feature branch in `fb70d8e62611ed03e4d29d3816862b5f6acebecb`: stop the scan as soon as the number of distinct verified origin ASNs reaches `max_attempts`; emit `origin_asn_selection_early_stop reason=distinct_asn_budget_reached ...` before constructing the diverse fallback order. For the observed run's first 8 results, this would have avoided the later candidate-15 lookup entirely.
- Added two tests in `6fd95321be3f43f236812470f02fa2f3df279450`: stop immediately once six distinct ASNs fill a six-attempt budget, and continue scanning when the number of distinct ASNs is still below the attempt budget.
- First validation [#43020108512](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43020108512) ran 114 tests and exposed a reporting-metric bug: after early stop the selector still reported the full input candidate count (10) instead of records actually inspected (6). Corrected by incrementing `candidate_servers_inspected` inside the loop and returning that counter. Follow-up validation [#43020242265](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43020242265) passed **114 Python tests**, Python compilation/JSON validation, `gofmt`, `go test ./...` and `go build`.
- PR #5 remains OPEN / DRAFT. PR #6, production builder, `geoip_RU.dat`, release assets/branch, DIRECT policy and ASN allowlists remain untouched.

- Run #12 should verify early-stop behavior against the live source list. In run #11's first eight completed ASN results, six unique ASNs had already been reached; the new code should emit `origin_asn_selection_early_stop` at candidate 8/24 and then report exactly six selected attempt candidates, rather than examining the remaining 16.

### 2026-11-11 — Run #12 stalled before OpenVPN; remove all pre-tunnel ASN network calls

- Manual run [#43020619690](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43020619690) used feature-branch commit `ab8b3a6866bfd6cf63e50e683147373ed7362a6b`. Setup, published GeoIP checksum and RU/PRIVATE inventory export succeeded; VPNObratto discovery downloaded 24 usable profiles.
- The latest reliable raw log snapshot remained at `origin_asn_lookup=7/24 host=vpn213212697.opengw.net` timestamped `2026-11-11T12:29:09Z`. No matching lookup result, selection-complete marker or OpenVPN attempt was present in the subsequent raw-log inspection. Other screenshot-level summaries from the browser were mutually inconsistent (they claimed a completed phase/OpenVPN/US exit while the raw log still ended at candidate 7); those interpretations were not used as evidence.
- The measurement step remained `in_progress` for more than 15 minutes despite the configured 10-minute step timeout. Under the prior explicit authorization to cancel stalled VPN runs, I requested cancellation of this exact run. GitHub confirmed `You have successfully requested the workflow to be canceled`; REST later confirmed `completed / cancelled` at `2026-11-11T12:48:43Z`. There are no artifacts. Run #12 therefore has **zero verified RU exits and zero persisted target measurement rows**; no service-access verdict can be drawn.
- Code inspection showed that the selector still depended on serial RIPEstat lookups before any OpenVPN process could start. A 7-second curl/subprocess guard was not sufficient in the live environment to keep the runner progressing, and the exact kernel/network wait point is not proven by the available logs.
- Removed that network dependency entirely from the pre-tunnel critical path. New `select_server_host_diverse_candidates()` groups variants by server hostname, selects one best profile per distinct hostname before trying another variant of the same host, and stops after the configured attempt budget of distinct hosts. The selected server ASN/prefix/org fields remain explicitly unverified/empty; this is an honest metadata limitation and does not weaken the required post-tunnel two-source public exit IPv4/country consensus or post-tunnel exit ASN enrichment.
- Progress markers now identify each host candidate, the distinct-host early stop and completed selection, rather than implying that origin ASNs were queried. Selection metadata records `server_asn_lookups=0`, `selected_distinct_asns=0`, and `distinct_candidate_server_hosts`.
- Added an external GNU `timeout --signal=TERM --kill-after=5s 9m` around the `sudo python3` measurement process. This is an additional process-group guard inside the existing 10-minute step and 20-minute job limits, leaving time for the `if: always()` artifact-upload step.
- Updated README to explain that pre-tunnel ASN enrichment is skipped, the hostname diversity policy, and the hard timeout. Added/updated unit tests to verify hostname-diverse selection, variant fallback ordering, early stop after the attempt budget, continued scan when hostnames repeat, and no call to network metadata before OpenVPN.
- Validation [#43023729793](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43023729793) on code/test/workflow commit `99d22570e8b299b9b98755f3eb8304d94c1a7d8c` passed **111 Python tests**, Python compilation/JSON validation, `gofmt`, `go test ./...` and `go build`. The later README-only commit is documentation-only.
- Next: confirm no VPN workflow run is queued or in progress, then dispatch one fresh manual VPNObratto pilot from the latest branch tip. Verify the selector finishes immediately without RIPEstat requests, exactly six distinct hosts are selected, OpenVPN starts, and the external 9-minute guard does not prevent artifact upload.
- PR #5 remains OPEN / DRAFT. PR #6, production builder, `geoip_RU.dat`, release assets/branch, DIRECT policy and ASN allowlists remain untouched.

### 2026-11-11 — Run #13 stalled during profile discovery; IP-mode DNS removed and timeout supervisor moved under sudo

- Manual run [#43024357603](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43024357603) used feature-branch commit 2927d14ec0ae9f5d7eacbc777a869237b59bb08d. Setup, published GeoIP checksum validation and RU/PRIVATE inventory export succeeded.
- VPNObratto profile listing returned 34 links. The run downloaded/validated 24 variants. The last reliable visible log line was profile_download=24/24 host=vpn753108762.opengw.net variant=ip_tcp; no corresponding profile_download_result=24/24, no phase=discovery completed, no host selection, no OpenVPN attempt, and no target request followed in the observed logs.
- Code inspection found that after each IP-literal profile was fetched and parsed, discovery synchronously called socket.getaddrinfo(listed_hostname) to compare the profile IP with DNS. This resolver had no hard timeout. It was called for every IP-mode profile and is the strongest identified blocking candidate; the precise system-level wait point cannot be proven from the truncated live logs.
- The run's workflow step and job remained in progress beyond the intended timeout. The external command was timeout ... sudo python3; the timeout supervisor was unprivileged while its Python child was launched as root. The owner had previously authorized stopping stalled runs. I requested cancellation of this exact run; GitHub confirmed the request. REST later confirmed run completed / cancelled at 2026-11-11T13:11:16Z. Job ID 130535170844 was completed/cancelled; no artifact was uploaded. Run #13 therefore provides zero verified RU exits and zero persisted target measurements.
- Fix commit bf9a1843724b986876712583b7525fba6ba0db7f: IP-mode profiles now take their global IPv4 literal directly from the .ovpn file linked under the exact same-origin listing path; this is recorded as profile_literal_same_origin_no_dns and is explicitly not independently DNS-correlated. DDNS mode still requires its remote hostname to match the listed hostname, but resolves it with getent ahostsv4 in a child process capped at 3 seconds.
- Discovery now stops profile downloads as soon as it has the required number of distinct usable server hostnames (the manual pilot passes max_unique_hosts=args.max_attempts, normally 6). With VPNObratto's interleaved ordering, the normal pilot should need only six IP_UDP profile downloads instead of downloading all 24 variants.
- Added tests covering no-DNS IP profile validation, bounded DDNS resolution and DNS timeout, and early discovery stop after six distinct IP-profile hostnames. The first validation [#43029409348](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43029409348) exposed a typo in the hostname regex escape; corrected in commit d0ae2a93cb4915d795cfe63b626c6d0351d0fc6e.
- Workflow timeout fix: command is now sudo timeout --signal=TERM --kill-after=5s 8m python3 ..., so the timeout supervisor runs as root and owns the measurement process. The GitHub measurement step remains 10 minutes and job remains 20 minutes, leaving time for if: always() report upload.
- README updated to disclose IP-profile trust boundary, bounded DDNS fallback, six-distinct-host discovery and the root-owned timeout.
- Validation [#43029686079](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43029686079) on commit d0ae2a93cb4915d795cfe63b626c6d0351d0fc6e passed 114 Python tests, Python compilation/JSON validation, gofmt, go test ./... and go build.
- Next: verify run #13 is terminal and no VPN workflow is active, then dispatch one manual VPNObratto pilot from the latest feature-branch tip. Expected early path: six profile fetches, profile_discovery_early_stop, discovery/host-selection completion, and first OpenVPN process. Do not classify any target until a completed artifact has been downloaded and reconciled.
- PR #5 remains OPEN / DRAFT. PR #6, production builder, geoip_RU.dat, release assets/branch, DIRECT policy and ASN allowlists remain untouched.

### 2026-11-11 — Run #14 progress and per-profile wall-clock download guard

- Manual run [#43030660328](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43030660328) is checked out at commit `20e6db7e6035c6af705b81bd4c8776a7cf9417f3` (the fixes added after dispatch do not apply to this run). Setup, exact published GeoIP download/checksum and RU/PRIVATE inventory export are all completed successfully.
- Live log inspection captured at approximately `2026-11-11T13:40:14Z` showed:
  - `runner_guard_timeout=8m kill_after=5s running_as_root=true`
  - listing completed with `links=32 download_cap=24 host_target=6`
  - profile downloads 1–5 all completed with `result=usable`, `unique_hosts=1..5`
  - download 6 started for `vpn689600419.opengw.net` / `ip_udp`; its result marker was not yet visible.
  - no `profile_discovery_early_stop`, discovery completion, hostname selection, OpenVPN attempt, tunnel/exit verification or target DNS/HTTPS result was visible in that snapshot.
- Last GitHub REST check at `2026-11-11T13:55:57Z` still showed run `in_progress`, job ID `130556541550` `in_progress` in step 7 (measurement); step 8 `Upload VPN Gate reports` remained pending; no artifacts existed. The step's configured 8-minute root-owned timeout and 10-minute GitHub timeout have both appeared insufficient to advance this run. A later live-log refresh/cancel could not be performed because the authenticated TinyFish browser workflow was rejected for insufficient wallet balance (-$0.15). GitHub REST access remains available, but no GitHub connector action for workflow cancellation is exposed.
- At this checkpoint the **confirmed evidence state for run #14** is five usable profile variants and a sixth fetch started; zero confirmed OpenVPN attempts, zero verified RU exits and zero persisted target measurements. Treat the sixth fetch and all later phases as unknown until fresh live logs or the final job/artifact are available.
- Additional diagnosis/fix committed at `390d43bd22ba42e4fa9cd352e74fcac49e80e7ed` and `e1d41236b2dcf48176ea29c49ea946d8175edf3d`: the prior urllib socket timeout bounded inactivity, not necessarily total response wall time. Added `call_with_wall_clock_timeout()` using a process-level SIGALRM deadline. Profile listing now has a 20-second total deadline; each profile HTTP fetch has a 15-second total deadline (12-second socket timeout). New flushed boundaries identify fetch start/completion, profile validation completion and server-IP resolution start/completion. Timeout errors are caught as an individual skipped profile so discovery can proceed to the next candidate.
- Added two tests for the wall-clock helper: callback result propagation and interruption of a slow operation. Validation [#43033708075](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43033708075) on commit `e1d41236b2dcf48176ea29c49ea946d8175edf3d` passed **116 Python tests**, Python compile/JSON validation, `gofmt`, `go test ./...` and `go build`.
- Next: use GitHub REST to wait for run #14 to become terminal and check artifact upload. A fresh browser/live-log check or targeted cancellation is blocked until TinyFish wallet is topped up. Do not start run #15 while #14 remains active. Once run #14 is terminal, run #15 should use the latest feature-branch head with the new 15-second per-fetch wall-clock guard and extra stage markers.
- PR #5 remains OPEN / DRAFT. PR #6, production builder, `geoip_RU.dat`, release assets/branch, DIRECT policy and ASN allowlists remain untouched.


### 2026-11-11 — Run #15 stopped before VPN setup because Ubuntu apt mirror DNS failed; runner pinned to Ubuntu 24.04

- Manual run [#43035301161](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43035301161) used branch `feature/reachability-full-ru-kz-by`, commit `6992b4cb337e447f1d14d27fd37a99ee655b8a23`, and the intended VPNObratno one-exit / six-attempt parameters.
- GitHub Actions runner was Ubuntu 26.04 (`resolute`), because GitHub's November 2026 `ubuntu-latest` rollout had moved to 26.04. The setup log shows DNS resolution failures for `azure.archive.ubuntu.com`, `archive.ubuntu.com` and `security.ubuntu.com`; `apt-get update` had only partial indexes and `apt-get install openvpn` failed with exit code 100 while resolving `security.ubuntu.com`.
- Run #15 ended `completed / failure` at `2026-11-11T14:12:09Z`. Checkout succeeded; the tool-install step failed; Go setup, GeoIP download/checksum, inventory export and VPN measurement steps were skipped. Artifact upload step succeeded but the artifact list was empty. This run confirms **zero OpenVPN attempts, zero verified RU exits and zero target DNS/HTTPS measurements**. The failure is runner package-install/DNS infrastructure, not VPN relay or target reachability evidence.
- Fix committed as `05c0d0431990e97851628f7b87ef0b29b0f8763c` (`Pin VPN reachability runner to Ubuntu 24.04`) on the feature branch only:
  - VPN workflow now pins `runs-on: ubuntu-24.04`, avoiding surprise migration to Ubuntu 26.04 via `ubuntu-latest`.
  - Tool-install step has a 5-minute timeout, checks whether OpenVPN is preinstalled, sets apt HTTP/HTTPS timeouts to 20 seconds, retries transient acquisitions three times, uses `APT::Update::Error-Mode=any` to fail on partial apt index refresh, and emits flushed stage markers.
  - GeoIP builder/output, release branch/assets, DIRECT policy and ASN allowlists are unchanged.
- Validation path `.github/workflows/reachability-validation.yml` includes the VPN workflow path on pushes to this feature branch, so the workflow-file change should trigger CI. The latest prior code validation remains [#43033708075](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43033708075): 116 Python tests plus Python compile/JSON, gofmt, Go tests and build. Workflow validation [#43037445995](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43037445995) on the workflow-change commit passed. Job log confirms 116 Python tests (OK), Python compile/JSON validation, gofmt, Go tests and build. This validates the current branch code and GitHub workflow syntax/acceptance; apt mirror connectivity on the next VPN runner remains to be verified by a fresh manual dispatch.
- Next: verify the validation run for commit `05c0d0431990e97851628f7b87ef0b29b0f8763c` passes. Then the owner can manually dispatch the next VPN run from `feature/reachability-full-ru-kz-by` with `source=vpnobratno`, `max_vpn_gate_servers=1`, `max_vpn_gate_attempts=6`. Do not start overlapping VPN runs. Expected first visible setup markers are `apt_update_started`, `apt_update_completed`, and `apt_install_completed`; only after them should the measurement phases be interpreted.
- PR #5 remains OPEN / DRAFT. PR #6 and production GeoIP/release paths remain untouched.

- Follow-up validation [#43037445995](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43037445995), job `130579946393`, completed `success` at `2026-11-11T14:20:14Z` on the workflow-change commit `05c0d0431990e97851628f7b87ef0b29b0f8763c`. The full job log confirms `Ran 116 tests` / `OK`, plus `py_compile`/JSON validation, `gofmt`, `go test ./...` and `go build`.
- Next manual dispatch is run #16, from latest branch `feature/reachability-full-ru-kz-by` (current head includes workflow fix + worklog/checkpoint), using `source=vpnobratno`, one verified RU exit and six maximum profile attempts. Run only after confirming no VPN workflow is active. Do not count it successful until output artifact has a verified RU exit and target DNS/HTTPS rows.


### 2026-11-11 — Bootstrap Ubuntu apt mirror DNS independently of runner NSS — IMPLEMENTED / VALIDATION PENDING

- Manual VPN run #16 (43038105495) ran on Ubuntu 24.04.5 / image ubuntu-24.04 version 20261101.360.1, runner region westus2, and failed before Go, inventory export, or VPN measurement. The full job log confirms packages.microsoft.com resolved while azure.archive.ubuntu.com, archive.ubuntu.com and security.ubuntu.com repeatedly failed DNS; the five-minute install step timed out. No artifact or target measurement was produced.
- Changing from ubuntu-latest to ubuntu-24.04 therefore did not address the root problem: the hosted runner's normal DNS path could not resolve Ubuntu mirror names.
- Reuse the existing PinnedHTTPSConnection / doh_query implementation, which connects to Cloudflare (1.1.1.1) and Google (8.8.8.8) by literal IP and validates TLS against the resolver hostname.
- Added install_ubuntu_apt_host_overrides(). It resolves all three Ubuntu mirror hostnames over pinned HTTPS DoH, accepts only public IPv4 answers, writes one clearly delimited temporary override block to the ephemeral runner's /etc/hosts, and rejects partial results or malformed existing markers. It does not alter /etc/resolv.conf; normal apt repository TLS and signed Release/package verification remain enabled.
- The setup step now runs the bootstrap under a 45-second root-owned timeout, verifies the names with getent, caps apt update/install wall time, and has a six-minute step limit. If pinned DoH itself is unavailable, the job should fail quickly with per-host diagnostics instead of spending five minutes waiting on apt.
- Added unit tests for public-IPv4 filtering, expected mirror mapping, idempotent block replacement, rejection of partial resolution and malformed existing markers.
- Run #16 had zero OpenVPN attempts, zero verified RU exits, zero target DNS/HTTPS rows and no artifacts. This is an environment/setup failure, not evidence about VPN or target reachability.
- Validation will be recorded only after the branch's Reachability validation workflow runs against the resulting code commit.


### 2026-11-11 — Record apt DNS bootstrap CI and current pending head — IN PROGRESS

- Validation run 43043009808 checked out implementation commit d8e679ae7080407e31042a195c545453b05ab9c7. Its only job completed successfully: the Python/JSON validation step and Go formatting, tests and build all passed. The Python suite reported 119 tests.
- GitHub's workflow-run summary still reported status in_progress when checked, although its sole job and all job steps were completed with conclusion success. Do not relabel the run itself as completed until the run endpoint confirms it.
- A follow-up test-only commit b6d5ffcd20dd8e488d6e9c2563f7fda781a5c20d corrected newline literals in the new hosts-file tests so they exercise real line boundaries. Its validation run 43043473870 was created but remained pending with no job listed at the latest check (2026-11-11 14:57:17 UTC).
- The apt DNS bootstrap code and workflow have deterministic CI coverage, but the live pinned-DoH access from GitHub's westus2 runner is not yet verified. The next manual run must show mirror_doh_lookup_completed for all three Ubuntu hostnames, mirror_hosts_override_installed, all three mirror_getent_verified markers, apt_update_completed and apt_install_completed before proceeding to VPN discovery.
- No new VPN workflow was dispatched. Run #16 (43038105495) ended before measurement with no artifact. PR #5 remains OPEN / DRAFT and current branch head is b6d5ffcd20dd8e488d6e9c2563f7fda781a5c20d.


### 2026-11-11 — Pinned-DoH apt bootstrap CI on latest code — DONE

- Latest-head validation: [run 43043473870](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43043473870), job 130603794526, commit tested b6d5ffcd20dd8e488d6e9c2563f7fda781a5c20d. Workflow and job conclusions are SUCCESS.
- Decoded job log: 119 Python tests ran in 0.120s; unittest result OK. The combined validation step succeeded, including Python compilation/JSON validation and Go formatting, go test ./... and go build.
- The 3 new apt DNS bootstrap regression tests all pass: public IPv4 host mapping/idempotence, no partial /etc/hosts write after lookup failure, and malformed marker rejection.
- Documentation/checkpoint-only commits 230b795316989647548df33cb7a50bf0a481b513 and 4712e1a538e102214c9c6e590970b0d946c88676 follow the validated code commit. They do not change code/workflow paths used by the validation workflow.
- PR #5 current head before this checkpoint update: 4712e1a538e102214c9c6e590970b0d946c88676; PR remains OPEN / DRAFT / not merged.
- Important limitation: CI tests mock DoH responses. They do not prove live pinned-DoH connectivity from runner region westus2. Next manual run #17 must prove mirror_doh_lookup_completed for all three mirror hosts, mirror_hosts_override_installed, apt_dns_bootstrap_completed, three mirror_getent_verified markers, apt_update_completed, and apt_install_completed before VPN setup can be counted.


### 2026-11-11 — Fix root-owned Python bytecode cache after apt bootstrap — IMPLEMENTED / VALIDATION PENDING

- Manual VPN run #17: [43045491865](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43045491865), job 130608225246, execution commit 5080c99a1738bdfce151a12b6ee62caa60593a16, runner Ubuntu 24.04.5 in centralus.
- The pinned-DoH apt bootstrap succeeded end-to-end: all three Ubuntu mirror names were resolved, `getent` checks passed, apt update fetched 13.1 MB, and OpenVPN 2.6.19 plus iptables were installed. The published GeoIP protobuf checksum passed. The exporter produced 76,293 RU + 151 PRIVATE = 76,444 inventory rows.
- Measurement then failed immediately at `python3 -m py_compile` with `[Errno 13] Permission denied: '.github/reachability/__pycache__/runner.cpython-312.pyc...'`. The inline bootstrap imported `vpn_gate` under `sudo`, creating a root-owned `__pycache__` directory; the following compile ran as the normal runner user.
- Downloaded artifact `geoip-ru-vpn-gate-43045491865` (ID 13865929395, 284,687 bytes) and independently verified SHA-256 `56192f146a354011e8ca4a22cf50fb9c51ef4d2efba36959f307d11fc4505b2c` against GitHub. It contains only `reachability_inventory.tsv` (2,501,267 bytes); there are no VPN result files. Thus no profile attempts, verified RU exits or target rows were produced.
- Fixed the bootstrap interpreter invocation to `python3 -B`. This disables bytecode-cache writes during the privileged import, preventing a root-owned `__pycache__` from being left behind for the unprivileged measurement step. No change to VPN measurement behavior or production GeoIP files.
- CI validation is pending for this workflow change. Do not describe run #17 as VPN failure; it is a local filesystem-permission failure before any VPN process ran.


### 2026-11-11 — Validate root bytecode-cache prevention — DONE

- Validation run [43045809575](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43045809575) passed for workflow change c939bef92a0d9e9a8c2b8379d8184cb4fb414608: 119 Python tests and Go format/tests/build all succeeded.
- Added a regression test that asserts the privileged apt bootstrap invokes `python3 -B`; this protects against reintroducing root-owned `__pycache__` entries.
- Latest-head validation [43045941300](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43045941300), job 130609765536, commit 5874b6a5c1b8a679c47ffa3261132575909a67cd: SUCCESS. The suite reports 120 Python tests, result OK; Go formatting, `go test ./...` and `go build` succeeded.
- The privileged Python import now uses `-B`; the live run #17 proved the DoH/apt setup path, while the new workflow change has green CI. A subsequent live manual run is still needed to confirm the full setup plus actual VPN attempts.
- Current PR #5 head 5874b6a5c1b8a679c47ffa3261132575909a67cd; PR remains OPEN / DRAFT / not merged.

### 2026-11-11 — Run #18 watchdog diagnosis, pinned VPNObratno HTTPS, and Run #19 socket ownership — DONE / READY FOR RUN #20

- Run #18 [43046237142](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43046237142), job 130610810591, executed commit 0708194fb6966e31222b149ba1bf609bf3ec6454. Setup, apt DNS bootstrap, OpenVPN install, GeoIP checksum and inventory export all succeeded (76,293 RU + 151 PRIVATE = 76,444 prefixes). Its measurement step remained active beyond its intended 8-minute process limit; the last user-provided log showed profile 6 starting but not completing. The run was later cancelled. No OpenVPN attempt, verified RU exit, target DNS/HTTPS row or artifact was produced.
- Diagnosis: fetch_vpnobratno_bytes() still used the system resolver in urllib. It was replaced with pinned-DoH IPv4 resolution and direct TLS to the resolved address via PinnedHTTPSConnection, retaining hostname SNI/certificate validation, same-origin-only redirects, response-size caps and a 20-second outer wall-clock guard.
- Added independent workflow watchdog layers: 7-minute process timeout, 9-minute measurement-step timeout and 12-minute job timeout, leaving time for artifact upload and cleanup.
- Run #19 [43051544044](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43051544044), job 130629735896, executed commit 4c251f1fc710f082a97d02038a070893d195ddbf. The live apt DoH bootstrap, apt update/install, OpenVPN installation, GeoIP checksum and exporter all succeeded; inventory again contained 76,293 RU + 151 PRIVATE = 76,444 prefixes.
- Run #19 reached phase=profile_listing and failed immediately in the new pinned HTTPS reader with VPNObratto HTTPS socket closed before response completed. This was an implementation bug, not a VPN/provider failure: Python HTTPConnection.getresponse() transfers socket ownership to HTTPResponse and clears connection.sock. The code had incorrectly treated that normal ownership transfer as a closed socket. No profile was downloaded, no OpenVPN attempt occurred, no verified RU exit or target measurement row was produced. Artifact ID 13870180568 (284,687 bytes; SHA-256 d1b1dd4a63bf01b82529c4c26cb226b243156a319c753f20472db7a54a52aa28) was uploaded; only the inventory TSV was available at failure.
- Fixed socket handling in commit a9967f52b4bd3d7a50638ad9ce63d685d57b84a9: set the absolute remaining read timeout while HTTPConnection still owns the socket, before getresponse(); after ownership transfer let HTTPResponse perform reads. The overall 20-second SIGALRM wall-clock wrapper remains the total deadline, including slow-drip responses. Updated the fake HTTP connection regression test to emulate this ownership transfer.
- Latest-head validation [43051897730](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43051897730), job 130630977611, tested a9967f52b4bd3d7a50638ad9ce63d685d57b84a9 and completed SUCCESS: 121 Python tests (OK), Go formatting, go test ./... and go build all passed.
- PR #5 remains OPEN / DRAFT / not merged. Next: owner manually dispatches Run #20 on feature/reachability-full-ru-kz-by, source vpnobratno, one successful verified RU exit, six maximum attempts. Inspect profile listing/download, server selection, all OpenVPN attempts, dual-source RU exit consensus, and target reports. Keep the PR draft and do not touch PR #6 or production GeoIP outputs.


### 2026-11-11 — VPNObratno manual run #20: discovery reached sixth profile — IN PROGRESS

- Manual run [#20](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43053531258), job `130636812894`, was dispatched from `feature/reachability-full-ru-kz-by` at execution commit `e339340436f6d17a31494c16f2a7c0f22a82e165`. Inputs: `source=vpnobratto` (workflow option value: `vpnobratto`), `max_vpn_gate_servers=1`, `max_vpn_gate_attempts=6`.
- GitHub REST snapshot at 2026-11-11T16:01:18Z: workflow and job were `in_progress`; measurement step 7 had started at `15:58:36Z`; setup, checkout, tool installation, Go setup, published GeoIP download/checksum and RU/PRIVATE inventory export steps all had conclusion `success`. Artifact upload was pending and the artifact list was empty at this snapshot.
- Owner-provided live log excerpt (message timestamp `16:00:20Z`) confirms:
  - VPNObratto listing fetched successfully (`21,587` bytes); 29 profile links were found, with download cap 24 and six distinct hosts targeted.
  - Profiles 1–5 completed fetch, profile validation and server-IP resolution successfully. All five were usable `IP_UDP` profiles for five distinct server hostnames.
  - Profile 6 started fetching over pinned-DoH HTTPS. Its completion/result marker was not included in the supplied excerpt.
- No later stage marker is present in that excerpt. Therefore the last user-visible evidence confirms five usable profiles and profile 6 fetch started; server selection, OpenVPN process creation, tunnel route, independent RU exit-IP/country consensus and target DNS/HTTPS rows are **not confirmed by this snapshot**. Since later job logs were not yet downloadable from GitHub REST while the job remained active, phases after the supplied excerpt are unknown; do not treat them as zero or infer failure.
- A fresh GitHub REST check still showed the measurement step `in_progress`, upload pending, and no artifacts. The job-log download endpoint returned `BlobNotFound` while the job was active; retrieve full logs and artifacts after the run reaches a terminal state.
- The profile fetch uses a 20-second total wall-clock guard; the collector itself is supervised by `timeout ... 7m` with a 5-second kill grace. The workflow measurement step has a 9-minute timeout and the job a 12-minute timeout. The nominal seven-minute watchdog point is about `16:05:36Z`, based on measurement-step start `15:58:36Z` (the command begins shortly after the step starts).
- No target service should be classified `BLOCKED` from discovery/network timeouts. VPNObratto nodes are user-operated VPN relays; a verified Russian exit still does not prove household/residential ISP access.
- Next: wait for run #20 to become terminal, retrieve and reconcile its complete logs and artifact, and only then decide whether another bounded manual run is justified. Do not dispatch an overlapping run. PR #5 remains OPEN / DRAFT; do not merge or mark ready, and do not touch PR #6, production GeoIP outputs, DIRECT policy or ASN allowlists.


- **Timeout overrun follow-up (2026-11-11T16:12:01Z UTC):** Owner reported the last visible marker was still `profile_fetch_started=6/24 wall_timeout=20s transport=pinned_doh_https` 13m11s after run start. A fresh GitHub REST read at 2026-11-11T16:12:01Z still returned run #20 and job `130636812894` as `in_progress`; measurement step 7 (started `15:58:36Z`) remained `in_progress`, artifact upload remained `pending`, and the run artifact list was empty. Job start was `15:57:52Z`.
- All configured ceilings had elapsed by this snapshot: the collector watchdog's nominal TERM point was `16:05:36Z` (7 minutes after step start) with KILL grace through about `16:05:41Z`; the 9-minute step ceiling was about `16:07:36Z`; the 12-minute job ceiling was about `16:09:52Z`. The GitHub API had not transitioned the job/run or exposed a completed log archive.
- The job-log endpoint continued returning `BlobNotFound` while GitHub reported the job active. No artifact was available to inspect. This confirms an Actions/runner timeout overrun, but the precise cause (measurement process still running vs runner/controller status stale) is **not established** from available REST data. Do not attribute it to VPNObratno, the target sites or a block.
- The connected GitHub tool surface exposes read-only run/job/log/artifact operations but no workflow cancellation action. Owner action required: use **Cancel workflow** on the run page to request cancellation. Do not dispatch another VPN workflow until this run is terminal; after cancellation/completion, retrieve logs/artifact and record exact terminal conclusion and evidence. Keep PR #5 OPEN / DRAFT and all production/PR #6 boundaries unchanged.


### 2026-11-11 — VPNObratno run #20 cancelled after timeout overrun — NO ARTIFACT / NO VERIFIABLE MEASUREMENT

- Run [#20](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43053531258), job `130636812894`, executed commit `e339340436f6d17a31494c16f2a7c0f22a82e165`. GitHub's latest REST state at 2026-11-11T16:15:33Z UTC: workflow `completed / cancelled`, updated at `16:14:53Z`; job `completed / cancelled`.
- Setup, checkout, OpenVPN/iptables installation, Go setup, published GeoIP checksum and RU/PRIVATE inventory export were all `success`.
- The job summary still showed the measurement step as `in_progress` and artifact-upload step as `pending` inside the cancelled job. The workflow artifact list was empty. The job-log download endpoint returned `BlobNotFound` after cancellation.
- The latest owner-provided measurement log line remained `profile_fetch_started=6/24 wall_timeout=20s transport=pinned_doh_https`. Earlier confirmed discovery evidence: listing 21,587 bytes, 29 supported links, first five profiles fetched/validated/resolved, five distinct usable server hosts; sixth profile fetch started. No later profile result or discovery completion was supplied.
- Therefore the final evidence available confirms **five usable profiles and a sixth fetch started**, but does not establish whether later discovery or OpenVPN activity occurred. No verified RU tunnel exit or target DNS/HTTPS result is available. Do not infer target blocking, and do not claim residential/home ISP coverage.
- The run exceeded its nominal 7m collector timeout + 5s kill grace, 9m step timeout and 12m job timeout before GitHub marked it cancelled. Exact cause of the overrun and cancellation actor are unknown because terminal logs/artifacts were unavailable. Do not attribute the issue to VPNObratno or target-site behavior.
- Next: investigate runner/watchdog behavior and improve observability/termination before another manual VPN dispatch. Do not overlap runs. Keep PR #5 OPEN / DRAFT; no production GeoIP, DIRECT policy, ASN allowlist or PR #6 changes.

### 2026-11-11 — Bound pinned DoH reads by one absolute deadline — IMPLEMENTED / VALIDATED

- Source-level review found that `doh_query()` used `HTTPResponse.read(1_000_000)` with a socket inactivity timeout. A slow-drip response could keep that single read active by periodically sending data, so the configured socket timeout did not impose a total wall-clock budget. A second timeout-propagation gap was also present: `TimeoutError` raised by the outer SIGALRM guard is an `OSError` subclass, so the broad resolver-fallback handler could catch it and continue to another resolver after the outer alarm had fired.
- Updated `doh_query()` to use one monotonic absolute deadline across the pinned Cloudflare/Google resolver attempts. The response is consumed with bounded `read1()` chunks; the remaining deadline is applied to the transferred HTTPResponse socket before each read. The 1,000,000-byte response cap and TLS/SNI pinning remain intact.
- Added a deterministic slow-drip regression test that advances a fake monotonic clock while returning small chunks and verifies that the DoH operation stops at its absolute deadline rather than trying the second resolver after the budget is exhausted. This path is directly relevant to VPNObratto profile downloads: `fetch_vpnobratto_bytes()` calls `doh_query()` with at most a four-second resolver timeout, while the enclosing profile fetch has a 20-second wall-clock guard.
- The test file contains two historical definitions of several test classes; Python uses the later definition. The active later `VPNGateDoHTests` class was synchronized with the first class so the new slow-drip test and fake socket fixture actually execute.
- Validation: [Reachability validation run #196](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43059474634), job `130657776704`, tested commit `7d075bda9a5c06e5ad9283f825f8c90e61cbc622`. The job and workflow both completed **SUCCESS** in 10 seconds: **122 Python tests passed**, gofmt passed, `go test ./...` passed and `go build` passed.
- The new absolute monotonic deadline is checked before each resolver and each response chunk, so even if a socket timeout or outer SIGALRM is caught by the fallback handler, the expired budget prevents another resolver attempt. This closes the discovered slow-drip and swallowed-SIGALRM fallback path.
- The old code path is a plausible explanation for a profile fetch stalling after `profile_fetch_started=6/24`: the DoH timeout could be swallowed by the fallback handler and followed by another slow-drip resolver. It is not proven because Run #20's terminal logs are unavailable, and it does not explain why the separate 7-minute GNU process timeout and GitHub step/job deadlines also failed to end the run.
- This is a verified application-level timeout improvement, but it does **not** prove that it caused or fully explains Run #20's 13-minute overrun. Run #20's terminal logs/artifacts remain unavailable, so whether the runner lost contact, the process survived termination, or the GitHub status was stale is still unknown.
- No VPN measurement was dispatched. Run #21 remains blocked pending separate runner/watchdog termination analysis. PR #5 remains OPEN / DRAFT; no production GeoIP, DIRECT policy, ASN allowlist, main/release or PR #6 changes were made.

### 2026-11-11 — Explicit outer-SIGALRM fallback regression — VALIDATED

- Added a second regression test for the exact exception interaction: simulate a `TimeoutError("wall-clock deadline")` during a DoH response read, advance the monotonic clock beyond the query deadline, and assert that the resolver fallback does not start a second connection.
- The test file has duplicate historical `VPNGateDoHTests` definitions; both definitions were synchronized so the active later class includes the test. The test is included in the executed suite.
- Latest validation [run #198](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43059875117), job `130659190333`, tested commit `9e2df8920fab45f293bd0faeb47f4459530a9e1d` and completed **SUCCESS** in 13 seconds: **123 Python tests passed**, gofmt passed, `go test ./...` passed and `go build` passed.
- Run #21 remains undispatched. The new test validates the application-level timeout propagation hole, but does not prove that the independent GNU timeout / GitHub Runner / job-timeout overrun seen in Run #20 is resolved.


### 2026-11-11 — Runner watchdog process-group preflight on ubuntu-24.04 — VALIDATED

#### Continuity recovery and source-of-truth review

- Resumed from the feature branch and re-read the current `.github/reachability/WORKLOG.md`, `.github/reachability/CHECKPOINT.json`, `.github/workflows/reachability-vpn-gate.yml`, and PR #5 metadata before making changes.
- The pre-session code/checkpoint anchor was `9e2df8920fab45f293bd0faeb47f4459530a9e1d` (latest green validation #198) plus documentation checkpoints. Run #20's exact record remains: run `43053531258`, job `130636812894`, cancelled, no terminal log archive/artifact, five VPNObratto profiles confirmed usable and sixth fetch started. No subsequent OpenVPN/verified-exit/target result can be inferred.
- Reconfirmed the independent DoH absolute-deadline fix and both regression tests. This fixes an application-level timeout hole but is not proven to have caused Run #20 or explain the outer runner/job timeout overrun.

#### Local process-tree experiment

- Created an isolated parent/child Python process pair. Both explicitly ignore SIGTERM; the child inherits the parent's process group and writes its PID/PGID/session marker.
- Ran GNU `timeout --verbose --signal=TERM --kill-after=1s 2s` under `sudo`. On the local environment (GNU coreutils 9.7), logs showed TERM then KILL; the wrapper returned `-9` because final process-group KILL may also terminate the timeout wrapper. Both recorded child processes reached zombie/non-running state, proving the process group no longer had active parent/child tasks.
- This local result was only a development check; the same scenario was then implemented as a runner preflight because local behavior alone is not evidence about GitHub-hosted Ubuntu.

#### Added runner watchdog preflight

- Added `.github/reachability/runner_watchdog_preflight.py` in commit `3ae66f2616b0154b804a46fa345a0e72b4af6307`.
- The helper is network-free and does not invoke OpenVPN. It verifies `sudo -n timeout` can supervise a TERM-resistant Python parent and descendant, waits for the forced KILL escalation, confirms the descendants share the process group/session, and checks both recorded PIDs are absent or non-running zombies. It has an outer 8-second bound and emergency process cleanup.
- The test intentionally accepts timeout exit `124`, `-9` or `137` only when both TERM and KILL diagnostics are present and every recorded process is no longer active. On this runner topology, killing the whole process group can also kill the timeout wrapper, so `-9` is not alone considered failure or success.

#### Integrated the check into PR validation

- Updated `.github/workflows/reachability-validation.yml` in commits `8e06142cc6f7db34774daebc9a9ad6b3c9579a16` and `212e11f2f33a07a3c1630bbc51f5cb2b3d80b9a5`.
- Validation now uses `ubuntu-24.04`, matching the manual VPN workflow image. A separate step runs the watchdog preflight with a one-minute step timeout. The helper is included in Python compilation and both push/PR path filters.
- Latest source/workflow commit for this validation: `212e11f2f33a07a3c1630bbc51f5cb2b3d80b9a5`.

#### GitHub-hosted runner evidence — PASS

- Validation run [#200](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43062327051), job `130667948305`, tested commit `212e11f2f33a07a3c1630bbc51f5cb2b3d80b9a5`. GitHub reports **SUCCESS**, total duration 24 seconds.
- Exact runtime log from the Ubuntu 24.04 runner reports GNU coreutils 9.4:
  - `[watchdog-preflight] start timeout (GNU coreutils) 9.4; timeout=2s; kill_after=1s`
  - `/usr/bin/timeout: sending signal TERM to command '/usr/bin/python3'`
  - `/usr/bin/timeout: sending signal KILL to command '/usr/bin/python3'`
  - `PASS timeout_exit=-9 parent_pid=2388 child_pid=2389 pgid=2387 parent_state=absent child_state=absent term_ignored=true kill_after_exercised=true descendants_terminated=true`
- The whole validation job also reports: 123 Python tests passed; Python compile/JSON validation passed; Go formatting, `go test ./...` and `go build` passed.
- This is direct evidence that the GNU timeout/process-group mechanism used by the workflow terminates a TERM-resistant child tree on the same Ubuntu image. The helper uses a synthetic process tree, not an OpenVPN session and not a live network connection.

#### OpenVPN process-tree source review

- Reviewed the current `vpn_gate.py`: OpenVPN is started with `subprocess.Popen(["openvpn", "--config", str(config_path), "--verb", "3"], ...)` without `start_new_session`, `setsid` or detached session parameters. It inherits the Python supervisor's process group.
- `build_safe_openvpn_config()` reconstructs a minimal allowlisted configuration and does not add OpenVPN's `daemon` directive or arbitrary user profile scripts/plugins. The profile's untrusted daemon/script/plugin settings are not copied.
- Normal shutdown explicitly calls `terminate()`, waits up to 8 seconds, then calls `kill()` and waits up to 5 seconds. If the outer timeout forcibly kills the Python process before its finally block, the validated process-group KILL should include its inherited OpenVPN child as well.
- Conclusion: the previously unverified GNU timeout process-tree cleanup path is now demonstrated on the target hosted runner, and source review did not find a detached OpenVPN child path. This does **not** prove that GitHub's controller/runner status reporting or job timeout cancellation cannot become stale; Run #20's outer Actions status overrun remains an unknown runner/platform-state issue.

#### State and next action

- Run #21 was **not** dispatched. No live VPN connection or target measurement was started during this session.
- Added `.github/reachability/RESUME.md` as a read-first navigation/continuity guide. New sessions should read it, then the last dated WORKLOG entry and CHECKPOINT, and query the live PR head/runs.
- PR #5 remains OPEN / DRAFT. No production GeoIP builder/data, release assets, DIRECT policy, ASN allowlists, main/release, PR #6 or other PR branches were changed.
- Next: re-query current PR head and confirm no active VPN run. With Run #200 green and OpenVPN process-group containment reviewed, one short manual VPNObratto pilot is now eligible for consideration: request one verified RU exit, at most six profile attempts, and persist phase checkpoints/logs. A verified RU exit still does not prove residential household access. Do not classify targets from an unverified exit or incomplete artifact.
