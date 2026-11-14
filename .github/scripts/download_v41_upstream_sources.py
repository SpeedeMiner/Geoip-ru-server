#!/usr/bin/env python3
"""Resolve published data upstream once per build, verify and record the exact bytes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory
from urllib.parse import quote

CAP = 64 * 1024 * 1024
PART = re.compile(r"[A-Za-z0-9_.-]+")
SHA1 = re.compile(r"[0-9a-f]{40}")
SHA256 = re.compile(r"[0-9a-f]{64}")
API = "https://api.github.com/repos/"


def safe_path(value):
    return isinstance(value, str) and all(
        PART.fullmatch(p) and p not in (".", "..") for p in value.split("/")
    )


def download(url, output, cap, *, metadata=False):
    cmd = ["curl", "--fail", "--location", "--silent", "--show-error",
           "--proto", "=https", "--proto-redir", "=https", "--connect-timeout", "20",
           "--max-time", "150", "--retry", "3", "--retry-all-errors",
           "--retry-max-time", "180", "--max-filesize", str(cap)]
    token = os.environ.get("GH_TOKEN") if metadata else None
    if token:
        # Header via stdin, never printed or sent to the raw/asset origin.
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", token):
            raise ValueError("invalid GitHub API token format")
        cmd += ["--header", "@-"]
    subprocess.run([*cmd, "--output", str(output), url],
                   input=f"Authorization: Bearer {token}\n".encode() if token else None,
                   check=True)
    if not 0 < output.stat().st_size <= cap:
        raise ValueError(f"empty or oversized response: {url}")


def resolve(group, get):
    repo, files = group["repository"], group["files"]
    if not safe_path(repo) or repo.count("/") != 1 or not isinstance(files, dict) or not files:
        raise ValueError("invalid source repository or files")
    if any(not safe_path(k) or "/" in k or not safe_path(v) for k, v in files.items()):
        raise ValueError(f"invalid source path in {repo}")
    if set(group) == {"repository", "branch", "files"} and safe_path(group["branch"]):
        branch = get(f"{API}{repo}/branches/{quote(group['branch'], safe='')}")
        commit = branch["commit"]["sha"]
        root = branch["commit"]["commit"]["tree"]["sha"]
        if not SHA1.fullmatch(commit) or not SHA1.fullmatch(root):
            raise ValueError(f"invalid Git commit/tree in {repo}")
        cache = {}

        def entry(tree, path):
            for i, component in enumerate(path.split("/")):
                if tree not in cache:
                    listing = get(f"{API}{repo}/git/trees/{tree}")
                    if listing.get("truncated") or listing.get("sha") != tree:
                        raise ValueError(f"unusable Git tree in {repo}")
                    cache[tree] = {x["path"]: x for x in listing["tree"]}
                x = cache[tree][component]
                if i + 1 == len(path.split("/")):
                    return x
                if x["type"] != "tree" or not SHA1.fullmatch(x["sha"]):
                    raise ValueError(f"not a Git directory: {repo}/{path}")
                tree = x["sha"]

        for local, path in files.items():
            x = entry(root, path)
            if x["type"] != "blob" or x["mode"] not in {"100644", "100755"} or not SHA1.fullmatch(x["sha"]):
                raise ValueError(f"not an ordinary Git blob: {repo}/{path}")
            yield local, f"https://raw.githubusercontent.com/{repo}/{commit}/{path}", x["size"], x["sha"], None
    elif set(group) == {"repository", "release", "files"} and group["release"] == "latest":
        release = get(f"{API}{repo}/releases/latest")
        tag = release["tag_name"]
        if not safe_path(tag) or tag == "latest" or release["draft"] or release["prerelease"]:
            raise ValueError(f"invalid stable release in {repo}")
        assets = {x["name"]: x for x in release["assets"]}
        for local, path in files.items():
            x = assets[path]
            url = f"https://github.com/{repo}/releases/download/{quote(tag, safe='')}/{path}"
            digest = x.get("digest", "")
            if (x["browser_download_url"] != url or x["state"] != "uploaded"
                    or not isinstance(digest, str) or not digest.startswith("sha256:")
                    or not SHA256.fullmatch(digest[7:])):
                raise ValueError(f"no verifiable release asset in {repo}: {path}")
            yield local, url, x["size"], None, digest[7:]
    else:
        raise ValueError(f"invalid upstream selector in {repo}")


def fetch(catalog, provenance, root=Path("."), *, transfer=download):
    groups = json.loads(catalog.read_text(encoding="utf-8"))
    if not isinstance(groups, list) or not groups:
        raise ValueError("empty upstream catalog")
    seen = set()
    with TemporaryDirectory(dir=root) as directory:
        staging = Path(directory)
        def get(url):
            path = staging / "metadata.json"
            transfer(url, path, 4 * 1024 * 1024, metadata=True)
            return json.loads(path.read_bytes())

        rows = []
        for group in groups:
            for name, url, size, git_hash, release_hash in resolve(group, get):
                if name in seen or type(size) is not int or not 0 < size <= CAP:
                    raise ValueError(f"duplicate or invalid source: {name}")
                seen.add(name)
                part = staging / name
                transfer(url, part, size)
                data = part.read_bytes()
                actual = hashlib.sha256(data).hexdigest()
                if (len(data) != size or (release_hash and actual != release_hash)
                        or (git_hash and hashlib.sha1(f"blob {size}\0".encode() + data).hexdigest() != git_hash)):
                    raise ValueError(f"upstream identity mismatch: {name} ({url})")
                rows.append(f"ROLLING {name}\t{name}\t{url}\t{actual}\t{size}\tdownloaded\n")
                print(f"{name}: {size} bytes sha256={actual} {url}", flush=True)
        # This independent upstream sidecar must match the DAT from the same release.
        if {"v2fly-geoip.dat", "v2fly-geoip.dat.sha256sum"} <= seen:
            sidecar = (staging / "v2fly-geoip.dat.sha256sum").read_text(encoding="ascii").split()
            if (len(sidecar) != 2 or sidecar[1] not in ("geoip.dat", "*geoip.dat")
                    or sidecar[0] != hashlib.sha256((staging / "v2fly-geoip.dat").read_bytes()).hexdigest()):
                raise ValueError("v2fly checksum sidecar does not match its GeoIP DAT")
        for name in sorted(seen):
            (staging / name).replace(root / name)
        with provenance.open("a", encoding="utf-8") as out:
            out.writelines(rows)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--catalog", type=Path, required=True)
    p.add_argument("--provenance", type=Path, required=True)
    p.add_argument("--root", type=Path, default=Path("."))
    a = p.parse_args()
    fetch(a.catalog, a.provenance, a.root)
