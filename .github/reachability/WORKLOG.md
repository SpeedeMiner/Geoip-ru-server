# Reachability implementation work log

This file is the durable resume point for work on PR #5. Update it after each
completed phase. Read this file and \`CHECKPOINT.json\` before continuing after
a conversation or network interruption.

## Current state — 2026-11-10 16:52 UTC

- Repository: \`SpeedeMiner/Geoip-ru-server\`
- PR: https://github.com/SpeedeMiner/Geoip-ru-server/pull/5
- State: **OPEN / DRAFT**; do not merge automatically.
- Working branch: \`feature/reachability-full-ru-kz-by\`
- PR head observed: \`1aa449c570b34fb506c9926a25e104fea093f272\`
- PR base observed: \`c71b5eff48f34b363ef2430ba6b5c41603f36126\`
- Main GeoIP builder and published client file are not changed by this branch.

## Completed phases

### Phase 1 — repository reconnaissance
- Confirmed current project architecture: Go builder in \`.github/workflows/blank.yml\`; client output is published on \`release\`.
- Confirmed release branch has the actual \`geoip_RU.dat\`, not only source-prefix subsets.
- Confirmed the client schema remains exactly \`RU\` and \`PRIVATE\`.

### Phase 2 — implementation
- Added strict protobuf inventory exporter under \`.github/reachability/inventory/\`.
- Exporter reads the published protobuf and requires exactly RU + PRIVATE; rejects duplicate categories/prefixes, non-canonical/default-route prefixes, malformed CIDRs and RU/PRIVATE overlap.
- Added target catalogue \`targets.json\` (11 seed hostnames; all tested from all RU/KZ/BY source countries).
- Added Globalping runner: DNS A/AAAA and HTTPS IPv4/IPv6; dynamic country + ASN + eyeball-network probe selection; returned probe country/ASN/tags checked.
- Added OONI recent \`web_connectivity\` metadata collection. OONI anomalies remain review-only.
- Added optional RIPE Atlas one-off TLS measurements. Atlas is skipped without \`RIPE_ATLAS_API_KEY\`.
- Added conservative classifications: HTTP response is transport-reachable; DNS answer is not HTTPS success; timeout/TLS/reset is inconclusive; no automatic blocked verdict.
- Added output reports and raw JSONL artifacts.
- Added deterministic tests for address-to-prefix mapping, PRIVATE priority, probe verification, DNS/HTTP classifications, schedule rotation and inventory checks.
- Added separate validation and full-measurement workflows. The latter is scheduled daily and can be started manually.

### Phase 3 — CI
- Reachability validation passed on the PR head:
  https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/42856736740
- The successful validation includes Python syntax + JSON validation, 16 Python unit tests at the latest run, Go formatting, Go tests and Go build. If test count is changed later, record the new count here.
- Earlier failures were corrected before the successful run:
  - Go formatting in test source;
  - dependency checksum generation by \`go mod tidy\`;
  - RIPE Atlas status parsing and probe filters;
  - CIDR lookup scalability.

### Phase 4 — first full measurement run
- Run: https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/42856671346
- Commit tested: \`58feded4d0b0b87a9b1671bf5c7b64ffa9e2c133\`
- Job: \`129971465746\`; all steps succeeded.
- Artifact: \`geoip-ru-reachability-42856671346\`
- Artifact ID: \`13782748149\`; expires 2026-12-10 16:41 UTC.
- Artifact SHA256: \`4eb6253566ff5d577ab84311122e4e002ab665494943dcc1535f4ca77e16899c\`
- Exported full inventory from actual \`geoip_RU.dat\`: 76,268 RU CIDRs + 151 PRIVATE CIDRs = 76,419 rows; protobuf SHA256 was verified before export.
- Globalping saw 5,499 online probes and found 37 country/ASN provider pairs tagged \`eyeball-network\`.
- 180 of 1,628 planned tasks completed (daily budget 180; max parallelism 5).
- Initial measurement result totals in the artifact:
  - 38 \`ACCESSIBLE\` HTTPS results;
  - 62 \`DNS_ANSWER\`;
  - 28 \`DNS_NO_ANSWER\`;
  - 25 \`INCONCLUSIVE\`;
  - 27 \`API_ERROR\` (primarily no matching IPv6 probes).
- OONI returned 476 observations: 2 \`ANOMALY_REVIEW\`, 474 \`NO_ANOMALY_RECORDED\`.
- RIPE Atlas was skipped: repository secret \`RIPE_ATLAS_API_KEY\` was not configured.
- Initial prefix association showed 12 prefixes with an accessible endpoint and 4 with DNS-only observation, but these counts are not suitable for policy conclusions yet.

## Important finding / current blocker

The first Globalping scheduler sorted all tasks by country and ASN, then selected one
continuous slice of the sorted list. In this initial run it resulted in successful
measurements being concentrated in only three RU ASNs (AS25513, AS29226 and AS31357);
the KZ/BY source-country probes were not adequately represented. This is a scheduler
bias, not evidence that KZ/BY providers cannot reach the targets.

**Next work must fix task selection to be stratified across all discovered
(country, ASN) providers in every daily run.** Prefer a balanced scheme that gives
every provider at least one complete target bundle (DNS A/AAAA + HTTPS IPv4/IPv6)
before allocating second bundles to any provider. Rotate target choice and provider
priority deterministically by UTC date. Keep the run budget and concurrency caps.

After the fair scheduler lands:
1. Add unit tests proving all represented countries are selected and no provider
   is starved when budget is at least four tasks per provider.
2. Re-run CI.
3. Re-run full measurement and inspect provider coverage from RU, KZ and BY.
4. Review OONI anomalies using the exact raw measurement links; do not treat the
   two anomalies as confirmed blocks.
5. Configure \`RIPE_ATLAS_API_KEY\` only if the repository owner wants Atlas
   measurements; until then, keep Atlas explicitly skipped.
6. Update this log and checkpoint after each phase.

## Resume protocol after a connection interruption

1. Read \`.github/reachability/WORKLOG.md\` and \`.github/reachability/CHECKPOINT.json\`.
2. Query PR #5 and record its current head SHA; never assume the old SHA is current.
3. Query recent Actions runs for branch \`feature/reachability-full-ru-kz-by\`.
4. If the most recent relevant run is completed successfully and its artifact exists,
   download/inspect that artifact instead of repeating the run.
5. Continue from the first unchecked item in \`CHECKPOINT.json\`; do not rebuild
   the original implementation from scratch.
6. After a phase is completed, commit an update to this work log and checkpoint.
7. Keep work in short phases: one focused code change, its CI result, then a
   checkpoint commit. Do not combine a long sequence of unrelated changes.

## Phase history

| Phase | Status | Evidence |
|---|---|---|
| Repository inspection | DONE | main tree + release tree inspected |
| Inventory exporter | DONE | full workflow run #42856671346 |
| Globalping/OONI/Atlas collectors | DONE, first-run observations obtained | artifact #13782748149 |
| CI validation | DONE | run #42856736740 passed |
| Balanced provider scheduling | TODO | current blocker |
| Repeat full measurement after scheduler fix | TODO | — |
| Interpret coverage and OONI anomalies | TODO | — |
| PR final review | TODO | PR #5 remains Draft |
