#!/usr/bin/env python3
"""Compare every GitHub Release asset with its published metadata and pinned Git."""
import argparse
import concurrent.futures
import hashlib
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import quote

REPO = "SpeedeMiner/Geoip-ru-server"
GIT_SHA = re.compile(r"[0-9a-f]{40}")
NAME = re.compile(r"[A-Za-z0-9_.-]+")
DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
LIMIT = 64 * 1024 * 1024


def fetch(url, path, cap):
    cmd = ["curl", "--fail", "--silent", "--show-error", "--location", "--proto", "=https",
           "--proto-redir", "=https", "--connect-timeout", "10", "--max-time", "55",
           "--retry", "1", "--retry-max-time", "65", "--max-filesize", str(cap), "-o", str(path), url]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode:
        return {"curl_exit": proc.returncode, "error": proc.stderr.strip()}
    size = path.stat().st_size
    with path.open("rb") as f:
        digest = hashlib.file_digest(f, "sha256").hexdigest()
    return {"size": size, "sha256": digest}


def run(inventory, tree, ref, out, workers=8):
    if not GIT_SHA.fullmatch(ref):
        raise ValueError("expected a full pinned Git commit")
    entries = []
    for surface, d in sorted(inventory.items()):
        if surface not in {"rolling", "snapshot"} or not NAME.fullmatch(d["tag"]):
            raise ValueError("invalid release inventory")
        names = [x["name"] for x in d["assets"]]
        if len(set(names)) != len(names):
            raise ValueError("duplicate release asset")
        for item in d["assets"]:
            if not NAME.fullmatch(item["name"]) or item["name"] in {".", ".."}:
                raise ValueError("invalid asset name")
            entries.append((surface, d["tag"], item))
    root = Path(out)
    root.mkdir(parents=True, exist_ok=True)
    for k in ("rolling", "snapshot", "git"):
        (root / k).mkdir(exist_ok=True)
    overlap = {a[2]["name"] for a in entries} & tree.keys()

    def asset_check(triple):
        surface, tag, asset = triple
        n, size = asset["name"], asset["size"]
        if asset["state"] != "uploaded" or not isinstance(size, int) or not 0 < size <= LIMIT or not DIGEST.fullmatch(asset.get("digest") or ""):
            return {"surface": surface, "name": n, "result": "invalid_metadata"}
        expected = f"https://github.com/{REPO}/releases/download/{quote(tag,safe='')}/{quote(n,safe='')}"
        if asset.get("browser_download_url") != expected:
            raise ValueError(f"unexpected public URL for {n}")
        d = fetch(expected, root / surface / n, size)
        good = d.get("size") == size and "sha256:" + d.get("sha256", "") == asset["digest"]
        return {"surface": surface, "name": n, "result": "match" if good else "unavailable_or_mismatch", **d}

    def git_check(name):
        n = tree[name]
        if not 0 < n["size"] <= LIMIT:
            raise ValueError(f"invalid pinned Git file size: {name}")
        path = root / "git" / name
        d = fetch(f"https://raw.githubusercontent.com/{REPO}/{ref}/{quote(name,safe='')}", path, n["size"])
        oid = None
        if "sha256" in d:
            h = hashlib.sha1(usedforsecurity=False)
            h.update(f"blob {d['size']}\0".encode("ascii"))
            with path.open("rb") as f:
                for block in iter(lambda: f.read(1 << 20), b""):
                    h.update(block)
            oid = h.hexdigest()
        ok = oid == n["sha"] and d.get("size") == n["size"]
        return {"name": name, "result": "match" if ok else "unavailable_or_mismatch", "blob_sha1": oid, **d}

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        asset_futures = [pool.submit(asset_check, x) for x in entries]
        git_futures = [pool.submit(git_check, n) for n in sorted(overlap)]
        assets = [f.result() for f in asset_futures]
        raw = {d["name"]: d for d in (f.result() for f in git_futures)}
    for d in assets:
        g = raw.get(d["name"])
        if g is None:
            d["pinned_git"] = "not_in_git_tree"
        elif g["result"] != "match" or d["result"] != "match":
            d["pinned_git"] = "unverified"
        else:
            d["pinned_git"] = "match" if g["sha256"] == d["sha256"] else "mismatch"
    return {"pinned_git_ref": ref, "release_tags": {s: d["tag"] for s, d in inventory.items()},
            "assets": assets, "raw_git": list(raw.values())}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("inventory", type=Path)
    p.add_argument("tree", type=Path)
    p.add_argument("ref")
    p.add_argument("out", type=Path)
    p.add_argument("--workers", type=int, default=8, choices=range(1, 17))
    args = p.parse_args()
    assets = json.loads(args.inventory.read_bytes())
    blobs = json.loads(args.tree.read_bytes())
    evidence = run(assets, blobs, args.ref, args.out, args.workers)
    print(json.dumps(evidence, indent=2))
