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
