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


def get_commit(repo: str, branch: str) -> str:
    ref = f"refs/heads/{branch}"
    result = subprocess.run(
        ["git", "ls-remote", "--exit-code", "--refs", f"https://github.com/{repo}.git", ref],
        capture_output=True, text=True, timeout=30, check=True,
    )
    commit, response_ref = result.stdout.strip().split("\t")
    if not SHA_RE.fullmatch(commit) or response_ref != ref:
        raise ValueError(f"unexpected response for {ref}")
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


def audit(repo: str, commit: str, hosts: tuple[str, ...], fetch: Fetch = fetch_https,
          *, release_commit: str | None = None) -> dict:
    if not REPO_RE.fullmatch(repo) or not SHA_RE.fullmatch(commit):
        raise ValueError("expected owner/repository and a full cdn commit SHA")
    if release_commit is not None and not SHA_RE.fullmatch(release_commit):
        raise ValueError("expected a full release commit SHA")
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

    result = {
        "repo": repo,
        "cdn_commit": commit,
        "inventory": ["tree", "flat"],
        "verified_hosts": ["raw.githubusercontent.com", *hosts],
        "files": {name: {"bytes": size, "sha256": digest.hex()}
                  for name, (size, digest) in tree.items()},
    }
    if release_commit is not None:
        release_base = f"https://raw.githubusercontent.com/{repo}/{release_commit}"

        def verify_release(name):
            data = fetch(f"{release_base}/{name}", ASSET_SIZE)
            digest = hashlib.sha256(data)
            if (len(data), digest.digest()) != tree[name]:
                raise ValueError(f"promoted release bytes differ from CDN: {name}")
            expected = f"{digest.hexdigest()}  {name}\n".encode()
            if fetch(f"{release_base}/{name}.sha256sum", 512) != expected:
                raise ValueError(f"promoted release checksum differs: {name}")

        with ThreadPoolExecutor(max_workers=3) as pool:
            list(pool.map(verify_release, FILES))
        result["release_commit"] = release_commit
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default="SpeedeMiner/Geoip-ru-server")
    parser.add_argument("--cdn-sha", help="full expected CDN commit; default: current origin/cdn")
    parser.add_argument("--edges", action="store_true", help="also read Fastly and Gcore endpoints")
    parser.add_argument("--compare-release", action="store_true",
                        help="require the current promoted release and checksums to match")
    args = parser.parse_args()
    if not REPO_RE.fullmatch(args.repo):
        parser.error("--repo must be owner/repository")
    try:
        commit = args.cdn_sha or get_commit(args.repo, "cdn")
        release = get_commit(args.repo, "release") if args.compare_release else None
        result = audit(args.repo, commit, EDGES if args.edges else CANONICAL, release_commit=release)
        if args.compare_release:
            # Moving refs are not a pass, even for internally consistent bytes.
            if (get_commit(args.repo, "release") != release
                    or get_commit(args.repo, "cdn") != commit):
                raise ValueError("release or CDN branch moved during audit; rerun the check")
    except (KeyError, TypeError, OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"GeoIP CDN audit failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
