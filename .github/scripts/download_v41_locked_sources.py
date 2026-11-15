#!/usr/bin/env python3
"""Fetch only reviewed static GeoIP inputs. Record provenance after verification."""
import argparse
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlsplit


def fetch(lock, provenance, root=Path.cwd()):
    entries = json.loads(lock.read_text(encoding="utf-8"))
    if not isinstance(entries, dict) or not entries:
        raise ValueError("empty source lock")
    for name, spec in entries.items():
        url, expected, size = spec["url"], spec["sha256"], spec["bytes"]
        u = urlsplit(url)
        if (not re.fullmatch(r"[a-zA-Z0-9_.-]+", name) or name in {".", ".."}
                or u.scheme != "https" or u.netloc not in {"github.com", "raw.githubusercontent.com"}
                or u.query or u.fragment
                or not re.fullmatch(r"[0-9a-f]{64}", expected)
                or type(size) is not int or not 0 < size <= 64 * 1024 * 1024):
            raise ValueError(f"invalid source lock entry: {name!r}")
        if u.netloc == "raw.githubusercontent.com":
            immutable = re.fullmatch(r"/[^/]+/[^/]+/[0-9a-f]{40}/.+", u.path)
        else:
            immutable = re.fullmatch(r"/[^/]+/[^/]+/releases/download/(?!latest/)[^/]+/[^/]+", u.path)
        if not immutable:
            raise ValueError(f"unversioned source URL for {name}")
        with tempfile.TemporaryDirectory(dir=root) as tmp:
            part = Path(tmp) / "download"
            subprocess.run(
                ["curl", "--fail", "--location", "--silent", "--show-error",
                 "--proto", "=https", "--proto-redir", "=https",
                 "--connect-timeout", "20", "--max-time", "180",
                 "--retry", "3", "--retry-max-time", "240",
                 "--max-filesize", str(size), "--output", str(part), url],
                check=True,
            )
            actual = hashlib.sha256(part.read_bytes()).hexdigest()
            if part.stat().st_size != size or actual != expected:
                raise ValueError(f"locked source {name} size or SHA-256 mismatch (sha256={actual})")
            part.replace(root / name)
        with provenance.open("a", encoding="utf-8") as f:
            f.write(f"LOCKED {name}\t{name}\t{url}\t{actual}\t{size}\tdownloaded\n")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--lock", type=Path, required=True)
    p.add_argument("--provenance", type=Path, required=True)
    a = p.parse_args()
    fetch(a.lock, a.provenance)
