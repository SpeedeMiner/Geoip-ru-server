# Reachability implementation work log

This file is the durable resume point for work on PR #5. Before continuing after any conversation or network interruption, read this file and CHECKPOINT.json, then query the current PR head and Actions runs. Do not restart completed phases.

## Current state

- Repository: SpeedeMiner/Geoip-ru-server
- Pull request: https://github.com/SpeedeMiner/Geoip-ru-server/pull/5
- State: OPEN / DRAFT. Do not merge automatically.
- Working branch: feature/reachability-full-ru-kz-by
- Current branch head at last checkpoint: 62676fb76404b6784b00f89b70c9c53ef289477e
- Base/main: c71b5eff48f34b363ef2430ba6b5c41603f36126
- Main GeoIP workflow, release branch and client geoip_RU.dat were not modified.
- Client contract remains one file and exactly two categories: RU and PRIVATE.

## Completed implementation

1. Repository reconnaissance: examined main build workflow, release branch and published GeoIP protobuf.
2. Added Go inventory exporter under .github/reachability/inventory/. It reads the exact published geoip_RU.dat, requires RU + PRIVATE only, rejects duplicates, invalid/non-canonical/default-route CIDRs and RU/PRIVATE overlap, then writes every prefix to TSV.
3. Added the 11-hostname seed catalogue in targets.json. All targets are measured from RU, KZ and BY source-country scopes. This is a seed, not a comprehensive endpoint inventory.
4. Added Globalping discovery and tests. Probes are selected by country + ASN + eyeball-network; actual country, ASN and tags are verified in the returned result.
5. Added separate DNS A/AAAA and HTTPS IPv4/IPv6 tests.
6. Added a deterministic fair scheduler: one complete four-test bundle per provider+target (DNS A, DNS AAAA, HTTPS IPv4, HTTPS IPv6); every discovered provider is visited before any provider gets a second target bundle; provider and target selection rotate by UTC date; short budgets never split a bundle.
7. Added OONI web_connectivity metadata collection. OONI anomalies are review-only and are not automatically block verdicts.
8. Added optional RIPE Atlas one-off TLS measurements. They are explicitly skipped when RIPE_ATLAS_API_KEY is not configured.
9. Added conservative status classification. An HTTP response is a successful transport observation; DNS answer is distinct from HTTPS; timeout/TLS/reset is inconclusive; no BLOCKED_CONFIRMED classifier exists.
10. Added provider, prefix, exact IP, candidate and raw JSONL evidence outputs. The latest implementation also separates NO_IPV6_PROBE from API_ERROR and ensures an exact-IP list in a prefix row contains only IPs belonging to that prefix.
11. Added independent validation CI and a scheduled/manual full-measurement workflow. The full-measurement workflow is no longer push-triggered; documentation/checkpoint commits do not start costly runs.

## Successful validation

- Latest validation run: https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/42861447947
- Commit: 62676fb76404b6784b00f89b70c9c53ef289477e
- Result: SUCCESS.
- Python: 26 unit tests passed.
- Go: gofmt, go test and go build passed.
- Latest commits also include: no-IPv6-probe classification; per-provider prefix/IP output; prefix-scoped observed IPs; tests for adjacent-prefix isolation.

## First complete fair-scheduler measurement

- Workflow: https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/42859913399
- Commit used by that measurement: 13eac680a0180a0b38409c5be28cfddc313964a4
- Job: 129982946164; all steps succeeded.
- Artifact: geoip-ru-reachability-42859913399
- Artifact ID: 13784433398
- Artifact SHA256: 2fdb12559cdada14a84665b006cec90742dde674823acfd23035a2262d1240df
- Artifact expiry: 2026-12-10 16:59:09 UTC.
- Inventory extracted from actual release/geoip_RU.dat: 76,268 RU CIDRs + 151 PRIVATE CIDRs = 76,419 rows. GeoIP protobuf checksum passed.
- Globalping online probes: 5,531. Discovered source pairs: 36 (RU 27, KZ 6, BY 3).
- Fair scheduler: all 36 of 36 providers covered; 0 uncovered; 180/180 tests; 45 complete target bundles; 0 partial bundles; all RU/KZ/BY present.
- Observations in this run: 43 ACCESSIBLE HTTP responses, 60 DNS_ANSWER, 30 DNS_NO_ANSWER, 10 INCONCLUSIVE, 37 API_ERROR.
- Manual inspection of all 37 API_ERROR rows showed the same Globalping response: HTTP 422 no_probes_found / no matching IPv6 probes available, specifically HTTPS IPv6. These are not connection failures or evidence of blocking. The current code converts this outcome into NO_IPV6_PROBE; a new full run is still needed to verify the classification in the exported artifact.
- Providers with at least one accessible HTTPS result: RU 25/27; KZ 6/6; BY 2/3. These are Globalping eyeball-network probes, not proof that every probe is a real residential subscriber.
- Endpoint-to-RU-prefix association in this run: 12 RU prefixes had an accessible endpoint; four showed DNS-only association in the earlier report. The current code now separately reports DNS + inconclusive HTTPS.
- The 11 target hostnames are only a pilot catalogue. 76,252 of 76,268 RU prefixes had no match to the current endpoint set; NO_MATCHED_ENDPOINT means not tested by current targets, not unreachable.
- OONI: 478 observations; 3 ANOMALY_REVIEW, all from BY AS42772 / A1 and all confirmed=false, failure=false. Measurement UIDs: 20261109125218.141420_BY_webconnectivity_459b4c7864ddea94 (ya.ru, 2026-11-09 12:52:01Z); 20261109014703.627296_BY_webconnectivity_938d2b65cc8555f5 (vk.com, 2026-11-09 01:46:56Z); 20261110165014.129448_BY_webconnectivity_68a8329bc60688c7 (vk.com, 2026-11-10 16:50:03Z). These remain review signals, not block verdicts.
- RIPE Atlas skipped because RIPE_ATLAS_API_KEY was not configured.

## Current next phase

Run the full workflow once more after the newest output/report changes. Verify:
- all discovered provider pairs receive complete bundles, with all three countries selected;
- the 37 former IPv6 API errors now appear as NO_IPV6_PROBE and API_ERROR contains only other API faults;
- reachability_by_provider_prefix.tsv and reachability_by_provider_ip.tsv are present and their observed IPs are correctly scoped to each prefix;
- report counts reconcile to raw Globalping JSONL;
- OONI anomalies stay separate and Atlas skip is explicit.

After successful verification, update CHECKPOINT.json and this file with the new run id, artifact id/hash, metrics, current PR head SHA, and test count. Then do a final PR review. Keep PR #5 Draft until the owner explicitly approves final review/merge.

## Resume protocol after interruption

1. Read .github/reachability/WORKLOG.md and .github/reachability/CHECKPOINT.json.
2. Query PR #5; use its current head SHA, not a remembered SHA.
3. Query recent Actions runs for feature/reachability-full-ru-kz-by.
4. If a successful full run for the current relevant code exists and its artifact is present, inspect that artifact instead of rerunning the measurement.
5. Continue from current_phase in CHECKPOINT.json; do not repeat repository reconnaissance, implementation or already-green CI.
6. Work in short units: one code/report change, CI, then checkpoint. Run full measurements only when runner/targets/measurement behavior changed, not on work-log-only edits.
7. After a completed phase, commit the new state to WORKLOG.md and CHECKPOINT.json.

## Phase table

| Phase | State | Evidence |
|---|---|---|
| Repository reconnaissance | DONE | main and release trees inspected |
| Full protobuf inventory exporter | DONE | run #42859913399 |
| Globalping, OONI, optional Atlas collectors | DONE | artifact #13784433398 |
| Fair provider scheduler | DONE | 36/36 provider pairs covered, 45 complete bundles |
| CI for latest output/classification changes | DONE | run #42861447947, 26 Python tests + Go checks |
| New full run after output changes | TODO / NEXT | manual/scheduled workflow |
| Reconcile provider-IP/prefix report | TODO | awaiting new artifact |
| Final PR review | TODO | PR #5 remains Draft |

## Invariants

- Never modify geoip_RU.dat from this diagnostic workflow.
- Exactly RU and PRIVATE categories remain in the client file.
- PRIVATE has absolute priority.
- No timeout, reset, TLS failure, DNS NXDOMAIN or OONI anomaly becomes a block verdict by itself.
- eyeball-network does not prove a residential/home connection.
- No scan or policy claim is inferred for unused IPs in a CIDR.
