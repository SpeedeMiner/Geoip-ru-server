# Reachability implementation work log

Durable resume point for PR #5. After any conversation/network interruption, read this file and CHECKPOINT.json, query the live PR head and Actions runs, then continue from the first pending phase. Do not restart completed work.

## Current repository state

- Repository: SpeedeMiner/Geoip-ru-server
- PR: https://github.com/SpeedeMiner/Geoip-ru-server/pull/5
- State: OPEN / DRAFT; no automatic merge.
- Branch: feature/reachability-full-ru-kz-by
- Base/main: c71b5eff48f34b363ef2430ba6b5c41603f36126
- Last code commit used by final measurement: 0ee7a3434537fbf19bba5c74508ca98c0f4a7d21
- Latest successful validation commit: 854381b06c08267416dc8bf20311e56a549c72bd. Documentation/checkpoint commits may advance branch HEAD; always query the live PR head on resume.
- The full-measurement workflow has manual dispatch on this feature branch. Its daily cron becomes active only after the workflow is merged into the repository default branch. The temporary push trigger has been removed.
- Main GeoIP builder, release branch, and published geoip_RU.dat were not modified. The client remains one file with exactly RU and PRIVATE categories.

## Implemented

- Go exporter reads the exact published release/geoip_RU.dat and exports every RU and PRIVATE prefix. It rejects unexpected/duplicate categories, duplicate/non-canonical/default-route CIDRs, malformed entries and RU/PRIVATE overlap.
- Inventory from the current release: 76,268 RU CIDRs + 151 PRIVATE CIDRs = 76,419 rows.
- Eleven seed hostnames are configured. Each is probed from source networks in RU, KZ and BY. This is not yet a comprehensive target catalogue.
- Globalping providers are discovered at run time by country + ASN + eyeball-network. Returned probe country, ASN and tags are verified.
- The fair scheduler emits complete four-test bundles (DNS A, DNS AAAA, HTTPS IPv4, HTTPS IPv6), visiting every provider before assigning another target to any provider. Country/provider and target selection rotate by UTC date. Budgets never split bundles.
- OONI web_connectivity observations are collected separately. OONI anomalies remain unconfirmed review signals, not automatic block verdicts.
- Optional RIPE Atlas TLS measurements are skipped explicitly because RIPE_ATLAS_API_KEY is not configured.
- Classification is conservative: HTTP response is observed HTTP reachability; DNS result is separate; timeout/TLS/reset remains inconclusive; missing IPv6 probe is NO_IPV6_PROBE; no automatic BLOCKED_CONFIRMED result exists.
- Reports include raw JSONL, provider TSV, per-provider/prefix TSV, exact provider/IP TSV, all-prefix TSV and summary JSON. Exact addresses are checked against the prefix shown in the row.

## Latest validation

- CI run: https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/42863496776
- Commit tested: 854381b06c08267416dc8bf20311e56a549c72bd
- Result: SUCCESS. Python 26/26 tests passed; Go formatting, Go tests and Go build passed.

## Latest complete measurement run

- Run: https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/42861904056
- Measurement code commit: 0ee7a3434537fbf19bba5c74508ca98c0f4a7d21
- Job: 129989972464; all steps succeeded.
- Artifact: geoip-ru-reachability-42861904056
- Artifact ID: 13786625472
- Artifact SHA256: 827d9e7db3af7ed6ec44044189e7a6a0fe6fe1b52f3e4ca5fbaf71efad99950c
- Artifact size: 1,036,807 bytes; expires 2026-12-10 17:10:36 UTC.

### Source coverage

- Globalping online probes: 5,539.
- Provider pairs found and covered: 38/38; none uncovered.
- Provider-pair count by source country: RU 29, KZ 6, BY 3.
- All three source countries were selected.
- 180 tasks = 45 complete target bundles; zero partial bundles; five maximum concurrent measurements.
- Country-tagged returned probe results: BY 15, KZ 18, RU 112. The 35 NO_IPV6_PROBE tasks have no returned probe and are not included in this country counter.

### Globalping outcome totals

| Result | Count | Meaning |
|---|---:|---|
| ACCESSIBLE | 44 | HTTP response received |
| DNS_ANSWER | 57 | A/AAAA answer received |
| DNS_NO_ANSWER | 32 | No DNS address answer; not a block verdict |
| INCONCLUSIVE | 12 | Timeout/TLS/reset/other incomplete measurement |
| NO_IPV6_PROBE | 35 | No matching IPv6 probe for HTTPS IPv6; not tested |
| API_ERROR | 0 | No other Globalping API errors |
| **Total** | **180** | All scheduled tasks accounted for |

- At least one completed HTTPS result was observed from 34 of 38 source provider pairs.
- Provider pairs with at least one DNS answer: 38 of 38.
- The 35 NO_IPV6_PROBE cases are separated explicitly: RU 28, KZ 6, BY 1. No IPv6 HTTPS reachability conclusion can be made for those exact source/provider-target tasks. DNS AAAA is a DNS query, not a substitute for an IPv6 TCP/TLS test.

### Prefix and exact-IP report validation

- reachability_by_provider_prefix.tsv: 64 rows.
- reachability_by_provider_ip.tsv: 77 rows.
- Unique provider/prefix keys: 64; unique provider/IP/prefix keys: 77.
- Every IP listed in a provider/prefix row belongs to that exact prefix.
- The IP sets represented in the provider/prefix table match the provider/IP table exactly; 0 mismatches.
- Every provider/IP address is inside its stated CIDR; 0 out-of-prefix addresses.
- Prefixes with an observed accessible endpoint: 11.
- Prefixes with DNS-only observation (HTTP not confirmed): 4.
- Prefixes with DNS answer plus inconclusive HTTP: 1.
- Prefixes without a configured endpoint match: 76,252 of 76,268. This means not tested by the current 11-hostname catalogue, not inaccessible.
- Exact provider/IP status counts: 34 HTTPS_ACCESSIBLE_OBSERVED, 38 DNS_RESOLVED_HTTPS_NOT_CONFIRMED, 5 DNS_RESOLVED_HTTPS_INCONCLUSIVE.

### OONI and RIPE Atlas

- OONI observations: 478; ANOMALY_REVIEW: 3. All three were from BY AS42772 and each had confirmed=false and failure=false. They remain review signals only.
- Measurement UIDs: 20261109125218.141420_BY_webconnectivity_459b4c7864ddea94 (ya.ru); 20261109014703.627296_BY_webconnectivity_938d2b65cc8555f5 (vk.com); 20261110165014.129448_BY_webconnectivity_68a8329bc60688c7 (vk.com).
- RIPE Atlas was explicitly skipped because RIPE_ATLAS_API_KEY is not configured.

## Interpretation limits

- Globalping eyeball-network differentiates end-user-tagged probes from data-centre probes, but does not prove that each probe is a residential/home line. Some returned network names can be hosting/enterprise operators. Treat the country/ASN observations as vantage-point evidence, not a verified list of household subscribers.
- The 11 hostnames are a pilot. The 76,252 prefixes without a target match remain untested; do not label them accessible or blocked.
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
| Full measurement and artifact review | DONE | run #42861904056 |
| OONI review / final policy interpretation | DONE with caveats above | 3 anomalies all confirmed=false |
| Final PR review / owner decision | PENDING | PR #5 remains Draft |

## Invariants

- Never alter geoip_RU.dat from this diagnostic workflow.
- Exactly RU and PRIVATE categories remain in the client file.
- PRIVATE has absolute priority.
- Timeout, reset, TLS failure, DNS error or OONI anomaly alone is never a block verdict.
- eyeball-network does not prove a residential/home connection.
- No policy inference is made for unused IPs in a CIDR.
