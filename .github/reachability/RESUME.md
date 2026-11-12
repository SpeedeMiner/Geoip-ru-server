# PR #5 — session recovery notes (READ FIRST)

**Purpose:** resume work after a chat/session interruption without repeating completed research or measurements. This file is a navigation summary; the append-only detailed history is in `.github/reachability/WORKLOG.md`, and the machine-readable state is in `.github/reachability/CHECKPOINT.json`.

## Scope and hard boundaries

- Repository: `SpeedeMiner/Geoip-ru-server`
- Pull request: [#5 — Add Russian ISP and RU/KZ/BY reachability evidence pipeline](https://github.com/SpeedeMiner/Geoip-ru-server/pull/5)
- Working branch: `feature/reachability-full-ru-kz-by`
- PR #5 must remain **OPEN / DRAFT**. Do not mark ready, merge, or rebase without explicit owner approval.
- Do not modify `main`, `release`, production GeoIP builder/data, `geoip_RU.dat`, release assets, DIRECT policy, ASN allowlists, PR #6 or other PR branches.
- Do not launch overlapping VPN runs. Run #21, #22 and #23 are all terminal `completed / cancelled`; there is no active VPN run from these attempts. Run #23 has no artifact or recoverable terminal log archive.
- A RU VPN exit does not prove that the relay is a residential/household ISP line. Never label it residential without independent evidence.
- DNS/HTTPS timeouts, TLS failures, missing probes, runner failures and missing artifacts are not evidence of target blocking.

## Start here on every resume

1. Read this file.
2. Read the last dated entry at the end of `.github/reachability/WORKLOG.md` (append-only).
3. Parse `.github/reachability/CHECKPOINT.json`; use `current_phase`, `next_steps`, `latest_validation_run216` and `run23_result` as the current state summary.
4. Query the live PR #5 head and latest Actions runs. Never use a remembered SHA as the current branch head.
5. Continue only from the first pending item. Do not repeat a finished VPN/CI phase.

The first “Current repository state” section near the top of WORKLOG is historical and may be stale; prefer its newest dated entries plus CHECKPOINT.

## Historical live pilot — Run #22 (TERMINAL: 12-MINUTE JOB LIMIT EXCEEDED)

- Run [#22 / 43072239130](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43072239130); job [130702892228](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43072239130/job/130702892228).
- Started 2026-11-11 17:51:55 UTC; job 17:51:58 UTC; measurement step 7 started 17:52:18 UTC. Checkout SHA `447bdf6083b3d69b0fbdcf0e126cc27a0ee3db71`.
- Owner supplied annotation at 18:09:45 UTC: **“The job has exceeded the maximum execution time of 12m0s.”** GitHub run API says `completed / cancelled`, updated 18:08:59 UTC; job API says `completed / cancelled`, completed 18:08:58 UTC. The nominal 12-minute deadline was 18:03:58 UTC; it was a platform-enforced timeout, not evidence of manual cancellation.
- Step summary remains stale/inconsistent after terminal completion: measurement step 7 `in_progress`; artifact upload step 8 `pending`; failure gate step 9 `pending`. Artifact list is empty. The post-terminal log endpoint returned Azure `BlobNotFound` at 18:10:06 UTC. No terminal log archive or artifact is available.
- Listing HTTP 200 / 23,641 bytes / 35 links. Five profiles downloaded and validated with full worker lifecycle:
  - `vpn712640336.opengw.net` → `92.124.94.110`, 10,006 bytes.
  - `vpn847521830.opengw.net` → `2.61.109.142`, 10,005 bytes.
  - `vpn856084155.opengw.net` → `93.157.20.218`, 10,006 bytes.
  - `vpn144814701.opengw.net` → `94.31.243.156`, 10,006 bytes.
  - `vpn953719594.opengw.net` → `5.143.32.148`, 10,005 bytes.
- Sixth profile `vpn950792227.opengw.net`, worker PID `3220`, completed DoH, pinned TCP/TLS to `93.127.223.115`, HTTP 200; supplied log shows body reads only to 3,830 bytes. No fetch-completed, validation, server-IP resolution or usable-profile marker is visible.
- **Leading but unproven cause:** the last visible `body_read_completed` marker is printed/flushed before `record_vpnobratno_progress()`. In the Run #22 checkout, the manifest writer then read/rewrote JSON, flushed a temporary file, called synchronous `os.fsync()`, and finally `os.replace()`. If the supplied paste is complete, the next code operation after the final marker was manifest persistence, making per-event `fsync` a focused suspect. A worker and parent timeout-handler both wrote the manifest through that old path; a blocking/uninterruptible filesystem call could explain why expected worker/outer termination markers did not appear. This remains a hypothesis, not a proven root cause; the pasted log may be partial and no terminal archive exists.
- **Mitigation landed after Run #22's pinned SHA:** code commit `d15de0f6c879e5b3f692bbdbb15d725f12c0785b` removes per-event `fsync`, retains temp-file flush + same-directory atomic `os.replace()`, and adds `progress_manifest_*` markers for mkdir/read/temp-write/atomic-replace. Regression commit `d9f2fff136fdc919730b99bf43c810f0ff23d96d` verifies atomic readable manifest writes without per-event `fsync`.
- Validation [Run #211](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43074433130), job `130710450443`, commit `d9f2fff...`: **SUCCESS**, 128 Python tests; hosted ubuntu-24.04 GNU timeout process-tree preflight, Go formatting, `go test ./...`, and `go build` passed.
- Confirmed OpenVPN attempts 0; tunnel routes 0; verified RU exits 0; target measurement rows 0. This is absence of results, not proof that a target is blocked.
- No new VPN run was dispatched after Run #22. Use the updated branch and inspect `progress_manifest_*` markers / uploaded manifest in the next explicitly initiated live pilot.

## Current branch engineering state — MANIFEST I/O MITIGATION VALIDATED

- Manifest I/O hardening code commit: `d15de0f6c879e5b3f692bbdbb15d725f12c0785b`.
- Regression-test commit: `d9f2fff136fdc919730b99bf43c810f0ff23d96d`.
- Latest validation: [Run #211](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43074433130), job `130710450443`, SUCCESS at 18:05:58 UTC.
- Full result: **128 Python tests passed**; hosted `ubuntu-24.04` GNU timeout process-tree preflight passed; Go formatting, `go test ./...` and `go build` passed.
- Production VPNObratto listing/profile fetches execute in a forked worker; parent wall-clock deadline is 20 seconds, while network budgets remain 15 seconds for listing / 12 seconds for profiles. Parent does TERM→KILL→join/reap; early worker exit is recorded separately from timeout.
- New manifest writer emits flushed `progress_manifest_*` markers for parent mkdir, manifest read, temp write and atomic replace. It flushes the temp file and uses same-directory `os.replace()`, deliberately omitting per-phase `os.fsync()` to avoid blocking kernel I/O on every marker.
- Manifest path is `reachability-output/vpn_gate_vpnobratto_progress.json`, included by the existing artifact glob `reachability-output/vpn_gate_*`; no profile body/key material is stored.
- Test coverage includes successful worker+manifest, TERM-resistant worker KILL/reap, early child exit classification, production discovery worker routing, and atomic manifest write without fsync.
- Run #22 uses the pre-mitigation checkout `447bdf...`; it is not evidence that the new no-fsync manifest writer fails.
- A fresh live pilot against the current branch is still required; do not treat Run #211's hermetic CI tests as live VPN verification.

## Current measurement state

### Run #21 — TERMINAL: GITHUB MAXIMUM 12-MINUTE JOB TIME EXCEEDED; NO ARTIFACT / TERMINAL LOGS

- Run: [#21 / 43065501624](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43065501624), job [130679257182](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43065501624/job/130679257182).
- Dispatch actor: `SpeedeMiner`; branch `feature/reachability-full-ru-kz-by`; checked-out SHA `5a1badef9e19a71c44cd4b1fa42748f4d688e90f`; runner `ubuntu-24.04`.
- Started 2026-11-11 17:10:12 UTC; job started 17:10:16 UTC; measurement step started 17:10:40 UTC.
- Owner supplied terminal GitHub Actions annotation at 17:28:19 UTC: **“The job has exceeded the maximum execution time of 12m0s.”**
- GitHub run API at 17:28:39 UTC: `status=completed`, `conclusion=cancelled`, `updated_at=2026-11-11T17:27:17Z`, attempt 1. Job API: `completed / cancelled`. Interpret this cancellation as GitHub's max-execution-time enforcement, not manual cancellation by the dispatch actor. The actor field identifies who triggered the workflow, not who cancelled it.
- The job step-summary API is stale/inconsistent even after terminal job state: measurement step 7 remains `in_progress`, artifact upload step 8 `pending`, and failure gate step 9 `pending`. No artifact exists. Fetching decoded job logs after completion still returns Azure `BlobNotFound`; there is no terminal log archive available for forensic inspection.
- Setup, checkout, tool installation, Go setup, exact published GeoIP checksum verification and RU/PRIVATE inventory export all succeeded.
- Owner's last live log excerpt: VPNObratto listing was 22,381 bytes, with 32 profile links (download cap 24, target six unique hosts); profiles 1–5 were fetched/validated/resolved and yielded five distinct hosts. The sixth fetch began with `profile_fetch_started=6/24 wall_timeout=20s transport=pinned_doh_https`. No completion marker for profile 6 was received.
- Confirmed profile server IPs from profiles 1–5: `185.112.224.250`, `94.159.74.210`, `92.124.94.110`, `2.61.109.142`, `93.157.20.218`.
- Evidence counts: five usable profiles; profile 6 started but completion unknown; confirmed OpenVPN attempts 0; confirmed verified RU exits 0; confirmed target measurement rows 0. These zeros mean **no results confirmed in the available evidence**, not a measured finding of zero site reachability.
- Timing limits on the run checkout: GNU watchdog 7 minutes + 5-second KILL grace; measurement step timeout 9 minutes; job timeout 12 minutes. The owner annotation confirms the outer job maximum was reached. The precise inner stall location and why there is no terminal log/artifact remain unresolved. The successful synthetic process-group watchdog preflight in Run #200 only proves the tested process topology on ubuntu-24.04; it does not diagnose this live run's inner stall.
- No verified RU exit or target DNS/HTTPS requests are confirmed. Do not classify any target as blocked. A RU VPN exit would not, by itself, prove residential household access.
- **No automatic rerun or replacement VPN run was started.** Before another attempt, inspect and improve the VPN measurement workflow's per-stage bounded execution and durable diagnostic persistence so that a stalled profile-fetch phase cannot leave the run without an inspectable terminal result.
- PR #5 remains OPEN / DRAFT; no production GeoIP builder/data, DIRECT policy, ASN allowlists, `main`, `release`, PR #6 or other branches were changed.

### Run #20 — cancelled, no usable result

- Run: [#20](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43053531258), job `130636812894`.
- Execution commit: `e339340436f6d17a31494c16f2a7c0f22a82e165`.
- Workflow status: `completed / cancelled`; updated 2026-11-11 16:14:53 UTC.
- Last owner-visible marker: `profile_fetch_started=6/24 wall_timeout=20s transport=pinned_doh_https`.
- Five profiles had been fetched/validated; sixth started. No terminal logs or artifact were available. The available evidence does not establish whether later discovery/OpenVPN stages ran.
- No confirmed RU tunnel exit or persisted target DNS/HTTPS result is available. Do not classify targets as blocked or claim this was a VPN/provider failure.
- Configured watchdogs (7-minute GNU timeout + 5-second KILL grace, 9-minute measurement step, 12-minute job) were all exceeded in GitHub status. The exact cause of the overall Actions status overrun remains unknown.

### Application-level DoH timeout fix — validated, causality unproven

- Source change: `562fb02e568443a0a1aab629c8762ca41d9980b9`.
- Regression/test class synchronization: `9e2df8920fab45f293bd0faeb47f4459530a9e1d`.
- One monotonic absolute deadline across both pinned resolvers; bounded `read1()` chunks; remaining socket timeout refreshed before every read; prevent an outer SIGALRM `TimeoutError` from triggering a second resolver attempt.
- Tests cover slow-drip response and outer SIGALRM fallback.
- Validation before watchdog changes: [Run #198](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43059875117), 123 Python tests plus Go formatting, `go test ./...` and `go build` passed.
- This closes the source-level unbounded DoH read path, which is a plausible contributor to a stalled VPNObratto profile fetch. It is **not proven** to have caused Run #20 and does not explain the separate process/step/job timeout overrun.

## Runner process-group watchdog preflight — DONE / GREEN

Added `.github/reachability/runner_watchdog_preflight.py`, a network-free runner test. It starts a parent and child Python process in the same process group; both ignore SIGTERM. GNU `timeout` must log TERM, wait one second, log KILL, and the test then verifies both recorded processes are absent or non-running zombies. An outer 8-second safety cap and explicit cleanup protect a runner if the test itself malfunctions.

Workflow integration: `.github/workflows/reachability-validation.yml` now runs on `ubuntu-24.04` (matching the manual VPN workflow image), runs the watchdog preflight in its own 1-minute-limited step, and includes the helper in py_compile and both push/PR path filters.

- Helper commit: `3ae66f2616b0154b804a46fa345a0e72b4af6307`.
- Workflow integration/final correction commit: `212e11f2f33a07a3c1630bbc51f5cb2b3d80b9a5` (intermediate workflow commit: `8e06142cc6f7db34774daebc9a9ad6b3c9579a16`).
- Runner validation: [Run #200](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43062327051), job `130667948305`, commit `212e11f2f33a07a3c1630bbc51f5cb2b3d80b9a5`, SUCCESS, 24 seconds.
- Log evidence from ubuntu-24.04 / GNU coreutils 9.4:
  - timeout logged `sending signal TERM`;
  - timeout logged `sending signal KILL`;
  - `timeout_exit=-9` (accepted because the final process-group KILL can also terminate the timeout wrapper);
  - parent and child were both `absent` after termination;
  - `term_ignored=true kill_after_exercised=true descendants_terminated=true`.
- Complete validation also passed: 123 Python tests, Go formatting, `go test ./...`, `go build`.
- This specifically proves process-group termination for a TERM-resistant parent/child on the same ubuntu-24.04 runner image. It does **not** prove GitHub controller/runner status reporting or job-cancellation status cannot become stale, so Run #20's full overrun diagnosis is not closed.

### OpenVPN process containment source review

- `vpn_gate.py` starts OpenVPN using `subprocess.Popen(["openvpn", "--config", ...])` without `start_new_session`, `setsid` or detached process settings. It inherits the Python process group.
- The generated safe config is rebuilt from an allowlist and does not include the `daemon` directive or arbitrary scripts/plugins.
- Normal-path cleanup calls terminate → wait(8s) → kill → wait(5s). If Python is forcibly killed, GNU timeout's validated process-group KILL is expected to include OpenVPN and its inherited descendants.
- Thus the demonstrated process-tree cleanup gap is now addressed for the exact sudo/GNU-timeout group topology used by the workflow. The independent GitHub runner/controller state-overrun question remains an observability/runner-platform limitation.




## Latest state — Run #24 live result and follow-up fixes (2026-11-11 20:12 UTC)

### Live VPN evidence — Run #24 (SUCCESS, but partial target scan)

- [Run #24 / 43093976146](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43093976146), job 130777962108, checkout `bb8620877ce40af49127b17f1a901e8e289af78e`, completed success. Artifact ID 13890192682 is available [here](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43093976146/artifacts/13890192682).
- One VPNObratno IP_UDP profile connected: `vpn350936845.opengw.net`, public exit `217.25.228.130`, RU, ASN 6856, organisation AO IK Informsvyaz-Chernozemye. Route installed and exit metadata verified. Exit matches existing GeoIP RU prefix 217.25.224.0/21; no candidate.
- 28/30 target rows; all 28 resolved A records. 25 HTTPS HTTP_RESPONSE and 3 INCONCLUSIVE. Statuses: 200×11, 301×2, 302×3, 307×3, 308×2, 403×1, 418×1, 503×2. Inconclusive: government.ru timeout (28s), gov.kz certificate hostname mismatch, belarusbank.by timeout (~19.5s).
- Targets not attempted due the 90-second attempt deadline: by-kufar / kufar.by and by-nbrb / nbrb.by.
- Run #24 was marked green only because one requested RU exit was obtained; the old exit code did not require all targets to be attempted. Interpret it as successful tunnel + RU exit with partial target measurements, not as a complete target scan.
- All five reports were persisted, upload succeeded (657,579 bytes), namespace cleanup had cleanup_failed=0. The progress manifest had blank workflow identity fields because sudo stripped GITHUB_SHA/GITHUB_RUN_ID/GITHUB_RUN_ATTEMPT.
- Volunteer VPN/ASN data do not establish a residential/home ISP. HTTP 403/418/503 are transport responses, not proof of blocking.

### Latest code changes after Run #24

- Current code head before this documentation commit: `ef84c890a79f93d006d98ddf833d3c9261c1553f`.
- `73bd2cb`: attempt budget 120 seconds, structured target-scan summary including untested IDs, run identity passed through sudo and recorded in summary.
- `dab7399`: unit test updated for sudo env.
- `ef84c89`: partial target scan no longer returns success; artifacts upload first, then final gate fails if target_scan_status is PARTIAL. Per-target INCONCLUSIVE remains a recorded observation and does not by itself make the scan incomplete.
- CI runs #218, #219 and #220 are queued for the intermediate/current commits. Do not claim these changes are validated until a run completes successfully.

### Next steps

- Validate latest code commit `ef84c890a79f93d006d98ddf833d3c9261c1553f`; fix any test failure.
- Only after validation passes, run one manual VPNObratno pilot with one RU exit requested and six profile attempts. Confirm that progress manifest includes workflow_run_id, workflow_run_attempt and execution_sha.
- Check `target_scan_status=COMPLETE`, `targets_not_tested_count=0`, and ensure rows exist for all declared targets, including by-kufar and by-nbrb. If partial, artifact must still upload but the workflow must fail.
- Keep conclusions conservative: timeout, TLS mismatch, 403/418/503 or unattempted targets are not block verdicts; VPN Gate does not attest residential access.
- PR #5 remains OPEN / DRAFT, base main. Preserve production GeoIP builder/data, DIRECT policy, ASN allowlists, main, release and PR #6.

## Continuity rules

- Append dated session notes to WORKLOG; do not rewrite history.
- Update CHECKPOINT after each meaningful phase and preserve previous run records.
- Every session should record exact commit SHA, workflow run/job IDs, test counts, artifact status, and explicit negative evidence.
- Documentation-only commits do not require repeating a VPN measurement.
- This project is evidence collection only; candidates remain review-only and never modify production GeoIP automatically.


## Latest state — Run #221 CI green and fail-closed default hardened (2026-11-12 06:18 UTC)

### Current code and validation

- Current validated code commit: `f2255d194f10c2f1222a0c7b29b36e6a241da6bc`.
- Follow-up hardening: `measurement_exit_code()` in `.github/reachability/vpn_gate.py` now defaults `target_scan_status` to `NOT_STARTED_NO_VERIFIED_RU_EXIT`, not `COMPLETE`. A caller that omits the scan status therefore fails closed even if the requested number of RU exits was reached.
- Regression test updated: omission of the scan status with one or two successful RU exits is non-zero; explicit `COMPLETE` remains success. `PARTIAL` and `NOT_STARTED_NO_VERIFIED_RU_EXIT` remain failures.
- Validation [Run #221 / 43167224578](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43167224578), job `131011801617`, completed **SUCCESS** on commit `f2255d1...` at 2026-11-12 06:18:51 UTC.
- Python: **142/142 tests passed** in 1.455 seconds. GNU timeout process-tree preflight passed (TERM then KILL; parent and child absent). Go formatting, `go test ./...` and `go build` passed.
- Run #221 is CI-only. It did not start OpenVPN or perform a target scan.

### Old queued runs

- Earlier Runs #218 / `43095995983`, #219 / `43096100580`, and #220 / `43096310463` remain reported as `queued`; their Jobs API returned `total_count=0` for each, so no runner/job was provisioned and no tests ran there.
- A fresh push of the latest code created Run #221, which completed successfully. Use #221 as the latest validation for the current code; do not describe #218–#220 as failing tests.
- The chronology matters: #218–#220 entered the queue at 20:25:45–20:28:58 UTC, while GitHub's official status page first reported Actions degradation at 20:48 UTC and backlog fully processed at 21:21 UTC. The incident therefore cannot explain why the jobs were not provisioned initially; it may have overlapped the later wait, but there is no proof it caused these exact runs to remain queued. Root cause remains unknown.

### Next action

- No live VPN run has been dispatched after Run #24. A manual VPNObratno pilot is still the next measurement step, but it should be launched only after explicit owner authorization.
- For that pilot, request one verified RU exit with up to six profile attempts. Confirm the artifact includes non-empty `workflow_run_id`, `workflow_run_attempt`, `execution_sha`, and all 30 target IDs; require `target_scan_status=COMPLETE` and `targets_not_tested_count=0`.
- If target scan remains partial, reports must upload before the final gate fails. Timeouts, TLS mismatch, HTTP 403/418/503 and omitted targets are not block evidence; VPNObratno volunteer nodes are not proof of residential household access.
- PR #5 remains **OPEN / DRAFT**. Do not merge or change production GeoIP data, builder, DIRECT, ASN allowlists, `main`, `release` or PR #6.
