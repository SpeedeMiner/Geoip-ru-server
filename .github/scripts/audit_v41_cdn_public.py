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
TAG_RE = re.compile(r"v41\.(?:0|[1-9][0-9]{0,5})|geoip-v41-snapshot-[0-9]{1,20}\.[0-9]{1,10}")
SNAPSHOT_MARKER = "geoip_RU_ipverse_snapshot_tag.txt"
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


def validated_snapshot_tag(tag: str) -> str:
    if not TAG_RE.fullmatch(tag):
        raise ValueError("expected a versioned v41 snapshot tag, not the rolling alias")
    return tag


def get_tag_commit(repo: str, tag: str) -> str:
    ref = "refs/tags/" + validated_snapshot_tag(tag)
    response = subprocess.run(
        ["git", "ls-remote", "--exit-code", f"https://github.com/{repo}.git", ref, ref + "^{}"],
        capture_output=True, text=True, timeout=30, check=True,
    )
    result = {}
    for line in response.stdout.splitlines():
        commit, response_ref = line.split("\t")
        if not SHA_RE.fullmatch(commit) or response_ref not in {ref, ref + "^{}"} or response_ref in result:
            raise ValueError(f"unexpected response for {ref}")
        result[response_ref] = commit
    if ref not in result:
        raise ValueError(f"missing tag ref {ref}")
    return result.get(ref + "^{}", result[ref])


def checked_snapshot_tag(repo: str, release: str, expected: str | None,
                         fetch: Fetch | None = None) -> str:
    fetch = fetch or fetch_https
    marker_url = f"https://raw.githubusercontent.com/{repo}/{release}/{SNAPSHOT_MARKER}"
    raw = fetch(marker_url, 128)
    tag = validated_snapshot_tag(raw.removesuffix(b"\n").decode("ascii"))
    if raw != f"{tag}\n".encode("ascii"):
        raise ValueError("noncanonical release snapshot marker")
    if expected is not None and tag != expected:
        raise ValueError("release snapshot marker does not match expected tag")
    if get_tag_commit(repo, tag) != release:
        raise ValueError("versioned snapshot tag does not point to promoted release")
    return tag


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


def validate_release_links(content: str, repo: str) -> None:
    """Require exactly the supported client links for this repo in public copy."""
    cdn_host = r"[a-z0-9-]+\.jsdelivr\.net"
    prefix = rf"https://{cdn_host}/gh/{re.escape(repo)}"
    links = re.findall(rf'{prefix}(?=[@/])[^"<>\s)]+', content, flags=re.IGNORECASE)
    expected = {f"https://cdn.jsdelivr.net/gh/{repo}@cdn/{name}" for name in FILES}
    if len(links) != len(expected) or set(links) != expected:
        raise ValueError("public client links must contain exactly the three canonical @cdn URLs")


def fetch_https(url: str, limit: int) -> bytes:
    request = Request(url, headers={"User-Agent": "GeoIP-v41 CDN audit / SpeedeMiner/Geoip-ru-server"})
    with urlopen(request, timeout=20) as response:
        if response.status != 200 or not response.url.startswith("https://"):
            raise ValueError(f"expected HTTPS 200 for {url}")
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError(f"response exceeds audit limit: {url}")
    return data



def verify_release_assets(
    repo: str, release: str, sources: tuple[tuple[str, str], ...], *,
    expect: dict[str, tuple[int, bytes]] | None = None,
    fetch: Fetch = fetch_https,
) -> dict[str, dict]:
    """Verify pinned Raw and the requested GitHub download locations."""
    release_base = f"https://raw.githubusercontent.com/{repo}/{release}"

    def verify(name):
        data = fetch(f"{release_base}/{name}", ASSET_SIZE)
        if not data:
            raise ValueError(f"empty promoted release file: {name}")
        digest = hashlib.sha256(data)
        if expect is not None and (len(data), digest.digest()) != expect[name]:
            raise ValueError(f"promoted release bytes differ from CDN: {name}")
        expected = f"{digest.hexdigest()}  {name}\n".encode()
        if fetch(f"{release_base}/{name}.sha256sum", 512) != expected:
            raise ValueError(f"promoted release checksum differs: {name}")
        for base, description in sources:
            if fetch(f"{base}/{name}", ASSET_SIZE) != data:
                raise ValueError(f"{description} bytes differ: {name}")
            if fetch(f"{base}/{name}.sha256sum", 512) != expected:
                raise ValueError(f"{description} checksum differs: {name}")
        return name, {"bytes": len(data), "sha256": digest.hexdigest()}

    with ThreadPoolExecutor(max_workers=3) as pool:
        return dict(pool.map(verify, FILES))


def versioned_download(repo: str, tag: str) -> tuple[str, str]:
    return (f"https://github.com/{repo}/releases/download/{validated_snapshot_tag(tag)}",
            "versioned GitHub snapshot")


def audit_fallback(repo: str, release: str, tag: str, fetch: Fetch = fetch_https) -> dict:
    if not REPO_RE.fullmatch(repo) or not SHA_RE.fullmatch(release):
        raise ValueError("expected owner/repository and a full release commit SHA")
    files = verify_release_assets(repo, release, (versioned_download(repo, tag),), fetch=fetch)
    return {"repo": repo, "release_commit": release, "versioned_snapshot_verified": tag,
            "files": files, "scope": "versioned GitHub fallback only"}

def audit(repo: str, commit: str, hosts: tuple[str, ...], fetch: Fetch = fetch_https,
          *, release_commit: str | None = None, versioned_tag: str | None = None) -> dict:
    if not REPO_RE.fullmatch(repo) or not SHA_RE.fullmatch(commit):
        raise ValueError("expected owner/repository and a full cdn commit SHA")
    if release_commit is not None and not SHA_RE.fullmatch(release_commit):
        raise ValueError("expected a full release commit SHA")
    if versioned_tag is not None:
        validated_snapshot_tag(versioned_tag)
        if release_commit is None:
            raise ValueError("versioned fallback requires a promoted release commit")
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
        downloads = ((f"https://github.com/{repo}/releases/download/latest-geoip-client-v41",
                      "rolling GitHub Release"),)
        if versioned_tag is not None:
            downloads += (versioned_download(repo, versioned_tag),)
        verify_release_assets(repo, release_commit, downloads, expect=tree, fetch=fetch)
        result["release_commit"] = release_commit
        result["rolling_release_verified"] = True
        if versioned_tag is not None:
            result["versioned_snapshot_verified"] = versioned_tag
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default="SpeedeMiner/Geoip-ru-server")
    parser.add_argument("--cdn-sha", help="full expected CDN commit; default: current origin/cdn")
    parser.add_argument("--release-sha", help="full expected release commit; implies --compare-release")
    parser.add_argument("--edges", action="store_true", help="also read Fastly and Gcore endpoints")
    parser.add_argument("--compare-release", action="store_true",
                        help="require the current promoted release and checksums to match")
    parser.add_argument("--verify-snapshot", action="store_true",
                        help="verify the versioned fallback from the promoted release marker")
    parser.add_argument("--snapshot-tag", help="full expected snapshot tag; implies --verify-snapshot")
    parser.add_argument("--fallback-only", action="store_true",
                        help="verify GitHub's versioned fallback without querying any CDN or rolling asset")
    args = parser.parse_args()
    if not REPO_RE.fullmatch(args.repo):
        parser.error("--repo must be owner/repository")
    for option, sha in (("--cdn-sha", args.cdn_sha), ("--release-sha", args.release_sha)):
        if sha is not None and not SHA_RE.fullmatch(sha):
            parser.error(f"{option} must be a full commit SHA")
    if args.snapshot_tag is not None and not TAG_RE.fullmatch(args.snapshot_tag):
        parser.error("--snapshot-tag must be a versioned v41 snapshot tag")
    if args.fallback_only and (args.cdn_sha is not None or args.edges):
        parser.error("--fallback-only does not accept CDN options")
    verify_snapshot = args.verify_snapshot or args.snapshot_tag is not None or args.fallback_only
    compare_release = args.compare_release or args.release_sha is not None or verify_snapshot
    try:
        commit = None if args.fallback_only else args.cdn_sha or get_commit(args.repo, "cdn")
        release = get_commit(args.repo, "release") if compare_release else None
        if args.release_sha is not None and args.release_sha != release:
            raise ValueError("current release does not match expected release SHA")
        tag = checked_snapshot_tag(args.repo, release, args.snapshot_tag) if verify_snapshot else None
        if args.fallback_only:
            result = audit_fallback(args.repo, release, tag)
        else:
            refs = {"release_commit": release}
            if tag is not None:
                refs["versioned_tag"] = tag
            result = audit(args.repo, commit, EDGES if args.edges else CANONICAL, **refs)
        if compare_release:
            # Moving refs are not a pass, even for internally consistent bytes.
            if (get_commit(args.repo, "release") != release
                    or (not args.fallback_only and get_commit(args.repo, "cdn") != commit)):
                raise ValueError("release or CDN branch moved during audit; rerun the check")
        if tag is not None and get_tag_commit(args.repo, tag) != release:
            raise ValueError("versioned snapshot tag moved during audit; rerun the check")
    except (KeyError, TypeError, OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"GeoIP CDN audit failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
