# PR #5 — session recovery notes (READ FIRST)

**Purpose:** resume work after a chat/session interruption without repeating completed research or measurements. This file is a navigation summary; the append-only detailed history is in `.github/reachability/WORKLOG.md`, and the machine-readable state is in `.github/reachability/CHECKPOINT.json`.

## Scope and hard boundaries

- Repository: `SpeedeMiner/Geoip-ru-server`
- Pull request: [#5 — Add Russian ISP and RU/KZ/BY reachability evidence pipeline](https://github.com/SpeedeMiner/Geoip-ru-server/pull/5)
- Working branch: `feature/reachability-full-ru-kz-by`
- PR #5 must remain **OPEN / DRAFT**. Do not mark ready, merge, or rebase without explicit owner approval.
- Do not modify `main`, `release`, production GeoIP builder/data, `geoip_RU.dat`, release assets, DIRECT policy, ASN allowlists, PR #6 or other PR branches.
- Do not launch overlapping VPN runs. **Run #21 is currently in progress**; monitor it to a terminal state before any further VPN dispatch.
- A RU VPN exit does not prove that the relay is a residential/household ISP line. Never label it residential without independent evidence.
- DNS/HTTPS timeouts, TLS failures, missing probes, runner failures and missing artifacts are not evidence of target blocking.

## Start here on every resume

1. Read this file.
2. Read the last dated entry at the end of `.github/reachability/WORKLOG.md` (append-only).
3. Parse `.github/reachability/CHECKPOINT.json`; use `current_phase`, `next_steps`, `runner_timeout_preflight`, `run21_result` and `run20_result` as the state summary.
4. Query the live PR #5 head and latest Actions runs. Never use a remembered SHA as the current branch head.
5. Continue only from the first pending item. Do not repeat a finished VPN/CI phase.

The first “Current repository state” section near the top of WORKLOG is historical and may be stale; prefer its newest dated entries plus CHECKPOINT.

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

## Next steps

- Run #21 is terminal. GitHub confirmed that its job exceeded the maximum execution time of 12 minutes; the run/job API reports `completed / cancelled`. This is a platform-enforced timeout, not evidence of a manual owner cancellation.
- No terminal log archive or artifact is available. The last confirmed measurement marker remains the start of profile 6 fetch. Do not infer an OpenVPN attempt, a verified RU exit, or target reachability.
- Diagnose the inner stall using the source at the run's pinned SHA `5a1badef9e19a71c44cd4b1fa42748f4d688e90f`. Review each operation after the profile-fetch boundary for a hard total wall-clock bound, and ensure phase progress and diagnostic output survive a killed measurement step. The 7-minute GNU guard, 9-minute step timeout and successful synthetic watchdog preflight did not prevent this run reaching the outer 12-minute job ceiling.
- Do not automatically rerun VPNObratno. A replacement pilot should follow only after the next bounded-stage/diagnostic changes are validated; use one exit and a small profile cap, then inspect the run to terminal state. No overlapping VPN run exists now.
- Keep PR #5 OPEN / DRAFT. Do not modify production GeoIP data/builders, DIRECT policy, ASN allowlists, `main`, `release`, PR #6 or other branches.

## Continuity rules

- Append dated session notes to WORKLOG; do not rewrite history.
- Update CHECKPOINT after each meaningful phase and preserve previous run records.
- Every session should record exact commit SHA, workflow run/job IDs, test counts, artifact status, and explicit negative evidence.
- Documentation-only commits do not require repeating a VPN measurement.
- This project is evidence collection only; candidates remain review-only and never modify production GeoIP automatically.
