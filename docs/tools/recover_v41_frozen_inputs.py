#!/usr/bin/env python3
"""Recover inputs from a pinned provenance TSV, never accepting drift."""
import argparse
import concurrent.futures
import csv
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
from urllib.parse import urlsplit


def digest(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def recover(provenance, output, caches):
    with provenance.open(encoding="utf-8", newline="") as f:
        records = list(csv.DictReader(f, delimiter="\t"))
    output.mkdir(parents=True, exist_ok=True)
    scratch = output / ".downloads"
    scratch.mkdir(exist_ok=True)
    names = [r["LOCAL_FILE"] for r in records]
    if len(set(names)) != len(names):
        raise ValueError("duplicate provenance filename")

    def one(row):
        name, url, sha = row["LOCAL_FILE"], row["FETCH_URL"], row["SHA256"]
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", name) or name in {".", ".."}:
            raise ValueError(name)
        if row["STATUS"] != "downloaded":
            return {"name": name, "status": "not_downloaded_in_original"}
        u = urlsplit(url)
        if u.scheme != "https" or not u.hostname or u.username or u.password:
            raise ValueError("invalid provenance URL")
        size = int(row["BYTES"])
        if not 0 < size <= 64 * 1024 * 1024 or not re.fullmatch(r"[0-9a-f]{64}", sha):
            raise ValueError("invalid provenance digest or size")
        for src in [output / name] + [d / name for d in caches]:
            if src.is_file() and src.stat().st_size == size and digest(src) == sha:
                if src != output / name:
                    shutil.copyfile(src, output / name)
                return {"name": name, "status": "exact", "source": "cache", "sha256": sha, "size": size}
        temp = scratch / name
        temp.unlink(missing_ok=True)
        p = subprocess.run(["curl", "--fail", "--silent", "--show-error", "--location",
                            "--proto", "=https", "--proto-redir", "=https", "--connect-timeout", "12",
                            "--max-time", "75", "--max-filesize", str(64 * 1024 * 1024),
                            "-o", str(temp), url], text=True, capture_output=True)
        if p.returncode:
            return {"name": name, "status": "unavailable", "curl_exit": p.returncode, "error": p.stderr.strip()}
        have_size, have_sha = temp.stat().st_size, digest(temp)
        if (have_size, have_sha) != (size, sha):
            return {"name": name, "status": "drift", "expected_size": size, "actual_size": have_size,
                    "expected_sha256": sha, "actual_sha256": have_sha}
        temp.replace(output / name)
        return {"name": name, "status": "exact", "source": "provenance_url", "sha256": sha, "size": size}

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        return list(pool.map(one, records))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("provenance", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("cache", type=Path, nargs="*")
    a = p.parse_args()
    print(json.dumps(recover(a.provenance, a.output, a.cache), indent=2))
