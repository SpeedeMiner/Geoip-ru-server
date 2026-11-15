#!/usr/bin/env python3
"""Read-only inventory and byte audit of the three GeoIP v41 CDN files."""

import argparse
import base64
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import re
import subprocess
import sys
from urllib.request import Request, urlopen

FILES = ("geoip_RU.dat", "geoip_RU.srs", "geoip_PRIVATE.srs")
CANONICAL = ("cdn.jsdelivr.net",)
EDGES = (*CANONICAL, "fastly.jsdelivr.net", "gcore.jsdelivr.net")
REPO_RE = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
SHA_RE = re.compile(r"[0-9a-f]{40}")
ASSET_SIZE = 8 * 1024 * 1024
INDEX_SIZE = 64 * 1024
Fetch = Callable[[str, int], bytes]


def get_cdn_commit(repo: str) -> str:
    result = subprocess.run(
        ["git", "ls-remote", "--exit-code", "--refs", f"https://github.com/{repo}.git",
         "refs/heads/cdn"],
        capture_output=True, text=True, timeout=30, check=True,
    )
    commit, ref = result.stdout.strip().split("\t")
    if not SHA_RE.fullmatch(commit) or ref != "refs/heads/cdn":
        raise ValueError("unexpected response for refs/heads/cdn")
    return commit


def parse_inventory(payload: bytes, *, flat: bool) -> dict[str, tuple[int, bytes]]:
    rows = json.loads(payload)["files"]
    names = {"/" + name if flat else name: name for name in FILES}
    result = {}
    for row in rows:
        external_name = row["name"]
        if external_name not in names or names[external_name] in result:
            raise ValueError("unexpected or duplicate member in jsDelivr inventory")
        if not flat and row.get("type") != "file":
            raise ValueError(f"jsDelivr inventory member is not a file: {external_name}")
        size = row["size"]
        digest = base64.b64decode(row["hash"], validate=True)
        if type(size) is not int or not 0 < size <= ASSET_SIZE or len(digest) != 32:
            raise ValueError(f"invalid size or SHA-256 in jsDelivr inventory: {external_name}")
        result[names[external_name]] = (size, digest)
    if set(result) != set(FILES):
        raise ValueError("jsDelivr inventory is missing a client file")
    return result


def fetch_https(url: str, limit: int) -> bytes:
    request = Request(url, headers={"User-Agent": "GeoIP-v41 CDN audit / SpeedeMiner/Geoip-ru-server"})
    with urlopen(request, timeout=20) as response:
        if response.status != 200 or not response.url.startswith("https://"):
            raise ValueError(f"expected HTTPS 200 for {url}")
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError(f"response exceeds audit limit: {url}")
    return data


def audit(repo: str, commit: str, hosts: tuple[str, ...], fetch: Fetch = fetch_https) -> dict:
    if not REPO_RE.fullmatch(repo) or not SHA_RE.fullmatch(commit):
        raise ValueError("expected owner/repository and a full cdn commit SHA")
    if not hosts or not set(hosts).issubset(EDGES):
        raise ValueError("expected supported jsDelivr endpoints")
    index = f"https://data.jsdelivr.com/v1/package/gh/{repo}@cdn"
    tree = parse_inventory(fetch(index, INDEX_SIZE), flat=False)
    flat = parse_inventory(fetch(index + "/flat", INDEX_SIZE), flat=True)
    if tree != flat:
        raise ValueError("tree and flat jsDelivr inventories disagree")

    checks = {
        (name, "raw.githubusercontent.com"):
            f"https://raw.githubusercontent.com/{repo}/{commit}/{name}" for name in FILES
    }
    checks.update({(name, host): f"https://{host}/gh/{repo}@cdn/{name}"
                   for name in FILES for host in hosts})

    def verify(key):
        name, source = key
        data = fetch(checks[key], ASSET_SIZE)
        actual = (len(data), hashlib.sha256(data).digest())
        if actual != tree[name]:
            raise ValueError(f"size or SHA-256 mismatch for {name} at {source}")

    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(verify, checks))

    return {
        "repo": repo,
        "cdn_commit": commit,
        "inventory": ["tree", "flat"],
        "verified_hosts": ["raw.githubusercontent.com", *hosts],
        "files": {name: {"bytes": size, "sha256": digest.hex()}
                  for name, (size, digest) in tree.items()},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default="SpeedeMiner/Geoip-ru-server")
    parser.add_argument("--cdn-sha", help="full expected CDN commit; default: current origin/cdn")
    parser.add_argument("--edges", action="store_true", help="also read Fastly and Gcore endpoints")
    args = parser.parse_args()
    if not REPO_RE.fullmatch(args.repo):
        parser.error("--repo must be owner/repository")
    try:
        commit = args.cdn_sha or get_cdn_commit(args.repo)
        result = audit(args.repo, commit, EDGES if args.edges else CANONICAL)
    except (KeyError, TypeError, OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"GeoIP CDN audit failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
