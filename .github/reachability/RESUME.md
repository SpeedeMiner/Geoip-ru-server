# PR #5 — session recovery notes (READ FIRST)

**Purpose:** resume work after a chat/session interruption without repeating completed research or measurements. This file is a navigation summary; the append-only detailed history is in `.github/reachability/WORKLOG.md`, and the machine-readable state is in `.github/reachability/CHECKPOINT.json`.

## Scope and hard boundaries

- Repository: `SpeedeMiner/Geoip-ru-server`
- Pull request: [#5 — Add Russian ISP and RU/KZ/BY reachability evidence pipeline](https://github.com/SpeedeMiner/Geoip-ru-server/pull/5)
- Working branch: `feature/reachability-full-ru-kz-by`
- PR #5 must remain **OPEN / DRAFT**. Do not mark ready, merge, or rebase without explicit owner approval.
- Do not modify `main`, `release`, production GeoIP builder/data, `geoip_RU.dat`, release assets, DIRECT policy, ASN allowlists, PR #6 or other PR branches.
- Do not launch overlapping VPN runs. Run #21 is terminal (`completed / cancelled` by GitHub's maximum 12-minute execution-time limit). **Run #22 is the current live pilot; do not dispatch a second run while it remains active.**
- A RU VPN exit does not prove that the relay is a residential/household ISP line. Never label it residential without independent evidence.
- DNS/HTTPS timeouts, TLS failures, missing probes, runner failures and missing artifacts are not evidence of target blocking.

## Start here on every resume

1. Read this file.
2. Read the last dated entry at the end of `.github/reachability/WORKLOG.md` (append-only).
3. Parse `.github/reachability/CHECKPOINT.json`; use `current_phase`, `next_steps`, `runner_timeout_preflight`, `run21_result` and `run20_result` as the state summary.
4. Query the live PR #5 head and latest Actions runs. Never use a remembered SHA as the current branch head.
5. Continue only from the first pending item. Do not repeat a finished VPN/CI phase.

The first “Current repository state” section near the top of WORKLOG is historical and may be stale; prefer its newest dated entries plus CHECKPOINT.

## Latest live pilot — Run #22 (GITHUB JOB NON-TERMINAL AFTER 12-MINUTE CEILING)

- Run [#22 / 43072239130](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43072239130); job [130702892228](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43072239130/job/130702892228).
- Started 2026-11-11 17:51:55 UTC; job 17:51:58 UTC; measurement step 7 started 17:52:18 UTC. Branch `feature/reachability-full-ru-kz-by`, checkout SHA `447bdf6083b3d69b0fbdcf0e126cc27a0ee3db71`.
- The checkout differs from validated code SHA `c49dece293541d46b6af14282b382459164315d7` only by documentation changes; it has the same isolated worker before the new manifest-fsync mitigation.
- Setup steps 1–6 all succeeded. Listing HTTP 200 / 23,641 bytes / 35 links. Five profiles downloaded and validated:
  - `vpn712640336.opengw.net` → `92.124.94.110`
  - `vpn847521830.opengw.net` → `2.61.109.142`
  - `vpn856084155.opengw.net` → `93.157.20.218`
  - `vpn144814701.opengw.net` → `94.31.243.156`
  - `vpn953719594.opengw.net` → `5.143.32.148`
- Sixth profile `vpn950792227.opengw.net`, worker PID `3220`, completed DoH, pinned TCP/TLS to `93.127.223.115`, HTTP 200; supplied log shows body reads to 3,830 bytes. Last supplied trace is `body_read_completed ... chunk_bytes=1369 total_bytes=3830`; no later profile fetch-completed / validation / server-IP resolution result is available.
- GitHub REST snapshot at 18:07:30 UTC: run/job/step 7 still `in_progress`; report upload step 8 `pending`; no artifact; job log endpoint `BlobNotFound`; run `updated_at` stale at 17:51:59 UTC. This is 3m32s beyond the 12-minute job limit (18:03:58 UTC); measurement step deadline (18:01:18 UTC) and GNU watchdog + 5s grace (~17:59:23 UTC) also passed.
- The supplied log ends at a trace marker that is printed before `record_vpnobratno_progress()`. The previous implementation then read/rewrote the JSON manifest, flushed and called `os.fsync()` before `os.replace()`. This is a high-priority but unproven suspect if the pasted log is complete; the paste may be partial and GitHub live logs are unavailable.
- Follow-up source commit `d15de0f6c879e5b3f692bbdbb15d725f12c0785b` now removes per-phase `fsync` (keeps temp-file flush + same-directory atomic replace) and emits manifest stages for mkdir/read/temp-write/replace. Regression commit `d9f2fff136fdc919730b99bf43c810f0ff23d96d` verifies that phase writes never call `os.fsync`.
- Validation [Run #211](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43074433130), job `130710450443`, commit `d9f2fff...`: **SUCCESS**, 128 Python tests, watchdog process-tree preflight, Go formatting/tests/build all passed. These commits do not affect Run #22's pinned checkout.
- No confirmed OpenVPN attempt, route installed, RU public exit or target measurements. Do not attribute target blocks or a VPNObratno service fault.
- Do not cancel or overlap Run #22. After terminal state, retrieve complete logs and `reachability-output/vpn_gate_vpnobratto_progress.json`.

## Current branch engineering state — FETCH WORKER ISOLATION VALIDATED

- Latest code-tested commit: `c49dece293541d46b6af14282b382459164315d7`.
- Latest validation: [Run #209](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43071264599), job `130699445722`, SUCCESS on `ubuntu-24.04`.
- Full result: **127 Python tests passed**; hosted runner process-group watchdog preflight passed; `gofmt`, `go test ./...` and `go build` passed.
- Production VPNObratto listing/profile fetches now execute in a forked worker. The parent enforces a monotonic 20-second wall deadline independently of 15-second listing / 12-second profile network budgets; it sends TERM, waits 0.5s, sends KILL if necessary, then joins/reaps.
- The worker emits flushed phase markers for DoH, TCP, TLS, HTTP request/headers, each response-body read and connection close. It atomically updates `reachability-output/vpn_gate_vpnobratto_progress.json`, which matches the existing `reachability-output/vpn_gate_*` artifact upload glob. The manifest stores run/commit identifiers and phase/timing metadata, not profile contents or keys.
- Tests cover successful result+manifest, a TERM-resistant worker killed/reaped by the parent, early worker exit classified separately from timeout, and default production discovery using the worker.
- README runtime documentation was updated in commit `863f0c5251cbab17a85ac150735dff7f37fcdd30`. Latest subsequent commits are documentation-only.
- Run #207's one failing test was a test helper signature mismatch (the worker correctly passed named `timeout`/`max_bytes` arguments); fixed before Run #208/#209. Run #208 passed 127 tests; Run #209 passed the final code after cleanup-finalizer hardening.
- No new VPN measurement was run. Run #21 remains the last live pilot; its exact inner stall is unproven because GitHub provided neither terminal logs nor an artifact.

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

## Next steps

- **Run #22 (43072239130) is still non-terminal in GitHub**; the last snapshot at 18:07:30 UTC showed it 212 seconds beyond its 12-minute job limit, step 7 in_progress, upload pending, no artifact and logs BlobNotFound. Do not launch another VPN workflow.
- Inspect the terminal status and artifact/logs for Run #22. Five profiles are complete; profile 6 only has DoH/TCP/TLS/HTTP 200 and partial response-body evidence. No OpenVPN attempt, tunnel route, verified RU exit or target rows have been confirmed.
- New manifest-fsync mitigation has passed [Run #211](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43074433130): 128 Python tests, hosted runner watchdog preflight, Go checks all green. Code commit `d15de0f...`; regression test commit `d9f2fff...`. Run #22 uses the prior checkout and is unaffected.
- On the next pilot after Run #22 is terminal, use this updated code; inspect the new `progress_manifest_*operation=...` markers to distinguish mkdir/read/temp-write/atomic-replace stalls, and inspect the uploaded per-profile manifest.
- Keep PR #5 OPEN / DRAFT and preserve production GeoIP/DIRECT/ASN policy, `main`, `release` and PR #6.


## Continuity rules

- Append dated session notes to WORKLOG; do not rewrite history.
- Update CHECKPOINT after each meaningful phase and preserve previous run records.
- Every session should record exact commit SHA, workflow run/job IDs, test counts, artifact status, and explicit negative evidence.
- Documentation-only commits do not require repeating a VPN measurement.
- This project is evidence collection only; candidates remain review-only and never modify production GeoIP automatically.
