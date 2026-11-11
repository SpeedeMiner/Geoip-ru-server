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

### Run #21 — GITHUB JOB STILL IN PROGRESS AFTER ALL DEADLINES; NO TERMINAL LOGS OR ARTIFACT

- Run: [#21 / 43065501624](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43065501624), job [130679257182](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43065501624/job/130679257182).
- Manual dispatch actor: `SpeedeMiner`; branch `feature/reachability-full-ru-kz-by`; checked-out commit: `5a1badef9e19a71c44cd4b1fa42748f4d688e90f`.
- Started 2026-11-11 17:10:12 UTC; measurement step started 17:10:40 UTC; runner `ubuntu-24.04`.
- Setup/install, Go setup, exact published GeoIP download/checksum and RU/PRIVATE inventory export all completed successfully.
- VPNObratto listing: 22,381 bytes; 32 profile links, download cap 24, six-host target. Five IP_UDP profiles fetched, validated and resolved to five distinct server IPs. Sixth profile fetch started with pinned-DoH HTTPS and a 20-second wall deadline.
- Latest owner-visible marker (sent 17:11:10 UTC): `profile_fetch_started=6/24 wall_timeout=20s transport=pinned_doh_https`.
- Confirmed addresses from profiles 1–5: `185.112.224.250`, `94.159.74.210`, `92.124.94.110`, `2.61.109.142`, `93.157.20.218`.
- Last owner-visible marker: profile 6 fetch started at the end of the supplied excerpt; no later marker has been supplied. Repeated GitHub REST checks through 17:16:11 UTC and the Actions run page still showed the run/job/measurement step as `in_progress`, upload pending, and no artifacts. Run `updated_at` remained `17:10:17Z`; the live job page rendered `Loading`, and the decoded job-log endpoint returned `BlobNotFound`. This is an observability/stale-status warning, not proof that the process is still executing or has failed. No OpenVPN process start, installed tunnel route, verified RU exit or target row is confirmed by available evidence.
- Workflow limits on the checked-out commit: 7-minute GNU process watchdog + 5-second KILL grace, 9-minute measurement step, 12-minute job; 5-second OpenVPN route wait per candidate.
- Workflow default inputs are one verified RU exit and six profile attempts. GitHub's run metadata does not echo submitted form inputs; distinguish configured defaults from a confirmed input payload.
- Do not cancel or overlap this run. Re-query status and retrieve full logs/artifacts after terminal state. The absence of an active log archive is not evidence of measurement failure.
- Current PR branch head may advance through documentation-only updates while the active run continues. The running job remains pinned to checkout SHA `5a1bade...`; always distinguish run SHA from current PR head.

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

- **Run #21 is already in progress.** Continue monitoring only this run; do not dispatch or queue another VPN workflow while it is active, and do not cancel it merely because live log retrieval is unavailable.
- The earlier attempt by this assistant to open the GitHub dispatch form was refused before browser start due to insufficient browser-automation service wallet. That historical refusal did not create a GitHub run. The owner subsequently started Run #21 manually; do not describe the pilot as blocked or undispatched now.
- On terminal state, retrieve the complete job logs and artifact, verify artifact SHA/digest, and reconcile the summary, provider rows, measurement rows and raw diagnostics. If no verified RU exit was established, no target verdict is supported.
- For Run #21, record profile fetch/download results; discovery completion/selection; OpenVPN process start/exit; route installed; two-source public exit IP/country agreement; exit ASN/prefix; each target DNS A/AAAA and HTTPS result; artifact presence/digest.
- After the terminal inspection, append the full evidence and limitations to WORKLOG and update CHECKPOINT. Do not overwrite historical run records.
- For that pilot, separately record: profile discovery/download results; OpenVPN process start/exit; route installed; two-source public exit IP/country agreement; exit ASN/prefix; each target DNS A/AAAA and HTTPS result; artifact presence and digest. No verified RU exit means no target verdict.
- After the pilot reaches terminal state, append the full evidence and limitations to WORKLOG and update CHECKPOINT. Do not overwrite historical run records.

## Continuity rules

- Append dated session notes to WORKLOG; do not rewrite history.
- Update CHECKPOINT after each meaningful phase and preserve previous run records.
- Every session should record exact commit SHA, workflow run/job IDs, test counts, artifact status, and explicit negative evidence.
- Documentation-only commits do not require repeating a VPN measurement.
- This project is evidence collection only; candidates remain review-only and never modify production GeoIP automatically.
