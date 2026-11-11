#!/usr/bin/env python3
"""Runner-only GNU timeout process-tree preflight; never uses the network or OpenVPN."""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import signal
import subprocess
import sys
import tempfile
import time


def write_record(path: str) -> None:
    pathlib.Path(path).write_text(
        json.dumps({"pid": os.getpid(), "pgid": os.getpgrp(), "sid": os.getsid(0)}) + "\n",
        encoding="utf-8",
    )


def child(path: str) -> int:
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    write_record(path)
    while True:
        time.sleep(1)


def parent(parent_path: str, child_path: str) -> int:
    # Both processes ignore TERM; --kill-after must terminate the whole group.
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    write_record(parent_path)
    proc = subprocess.Popen(
        [sys.executable, str(pathlib.Path(__file__).resolve()), "--child", child_path],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        close_fds=True,
    )
    return proc.wait()


def proc_state(pid: int) -> str | None:
    try:
        raw = pathlib.Path(f"/proc/{pid}/stat").read_text(encoding="ascii")
    except FileNotFoundError:
        return None
    tail = raw[raw.rfind(")") + 2 :].split()
    if len(tail) < 4:
        raise RuntimeError(f"cannot parse /proc/{pid}/stat for pid={pid}")
    return tail[0]


def active(pid: int) -> bool:
    return proc_state(pid) not in {None, "Z", "X"}


def cleanup(records: list[dict[str, int]], sudo: str) -> None:
    own_pgid = os.getpgrp()
    pgids = {r["pgid"] for r in records if r.get("pgid", 0) > 1 and r["pgid"] != own_pgid}
    for pgid in pgids:
        subprocess.run(
            [sudo, "-n", "kill", "-KILL", "--", f"-{pgid}"],
            check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3,
        )
    for record in records:
        pid = record.get("pid", 0)
        if pid > 1:
            subprocess.run(
                [sudo, "-n", "kill", "-KILL", str(pid)],
                check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3,
            )


def run_preflight() -> int:
    sudo, timeout = shutil.which("sudo"), shutil.which("timeout")
    if not sudo or not timeout:
        raise RuntimeError("sudo and GNU timeout must be installed")
    version = subprocess.run(
        [timeout, "--version"], check=True, capture_output=True, text=True, timeout=3
    ).stdout.splitlines()[0]
    print(f"[watchdog-preflight] start {version}; timeout=2s; kill_after=1s", flush=True)

    with tempfile.TemporaryDirectory(prefix="reachability-watchdog-") as tmp:
        root = pathlib.Path(tmp)
        parent_file, child_file = root / "parent.json", root / "child.json"
        command = [
            sudo, "-n", timeout, "--verbose", "--signal=TERM", "--kill-after=1s", "2s",
            sys.executable, str(pathlib.Path(__file__).resolve()),
            "--parent", str(parent_file), str(child_file),
        ]
        proc = subprocess.Popen(
            command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True,
        )
        try:
            output, _ = proc.communicate(timeout=8)
        except subprocess.TimeoutExpired as exc:
            records = [json.loads(p.read_text(encoding="utf-8")) for p in (parent_file, child_file) if p.exists()]
            cleanup(records, sudo)
            try:
                pgid = os.getpgid(proc.pid)
                if pgid != os.getpgrp():
                    os.killpg(pgid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            subprocess.run(
                [sudo, "-n", "kill", "-KILL", str(proc.pid)],
                check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3,
            )
            raise RuntimeError("timeout supervisor exceeded outer 8-second safety bound") from exc

        for line in output.splitlines():
            print(f"[watchdog-preflight] {line}", flush=True)

        deadline = time.monotonic() + 4
        while time.monotonic() < deadline and (not parent_file.exists() or not child_file.exists()):
            time.sleep(0.05)
        if not parent_file.exists() or not child_file.exists():
            records = [json.loads(p.read_text(encoding="utf-8")) for p in (parent_file, child_file) if p.exists()]
            cleanup(records, sudo)
            raise RuntimeError("timed command did not create both process markers")

        parent_record = json.loads(parent_file.read_text(encoding="utf-8"))
        child_record = json.loads(child_file.read_text(encoding="utf-8"))
        records = [parent_record, child_record]
        if parent_record["pgid"] != child_record["pgid"] or parent_record["sid"] != child_record["sid"]:
            cleanup(records, sudo)
            raise RuntimeError("descendant escaped the parent's process group/session")

        deadline = time.monotonic() + 4
        while time.monotonic() < deadline and any(active(r["pid"]) for r in records):
            time.sleep(0.05)
        running = [r["pid"] for r in records if active(r["pid"])]
        if running:
            cleanup(records, sudo)
            raise RuntimeError(f"GNU timeout left descendant processes running: {running}")

        # The exact sudo/coreutils topology may report 124 or signal 9 if the
        # final group KILL also terminates the timeout wrapper. Both are accepted
        # only when TERM and KILL diagnostics exist and every recorded child exited.
        term_seen = "sending signal TERM" in output
        kill_seen = "sending signal KILL" in output
        if proc.returncode not in {124, -9, 137} or not term_seen or not kill_seen:
            raise RuntimeError(
                f"unexpected timeout result rc={proc.returncode}, TERM={term_seen}, KILL={kill_seen}"
            )

        print(
            "[watchdog-preflight] PASS "
            f"timeout_exit={proc.returncode} parent_pid={parent_record['pid']} "
            f"child_pid={child_record['pid']} pgid={parent_record['pgid']} "
            f"parent_state={proc_state(parent_record['pid']) or 'absent'} "
            f"child_state={proc_state(child_record['pid']) or 'absent'} "
            "term_ignored=true kill_after_exercised=true descendants_terminated=true",
            flush=True,
        )
    return 0


def main() -> int:
    if len(sys.argv) == 3 and sys.argv[1] == "--child":
        return child(sys.argv[2])
    if len(sys.argv) == 4 and sys.argv[1] == "--parent":
        return parent(sys.argv[2], sys.argv[3])
    if len(sys.argv) == 1:
        return run_preflight()
    raise SystemExit("usage: runner_watchdog_preflight.py [--child FILE | --parent PARENT.json CHILD.json]")


if __name__ == "__main__":
    raise SystemExit(main())
