#!/usr/bin/env python3
"""Read GitHub v41 publication state without modifying Git refs or Release assets."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sys
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import HTTPRedirectHandler, Request, build_opener

REPO = "SpeedeMiner/Geoip-ru-server"
ROLLING = "latest-geoip-client-v41"
ARCHIVE = "as-ip-blocks.tar.gz"
MARKER = "geoip_RU_ipverse_snapshot_tag.txt"
PROVENANCE = "geoip_RU_input_provenance.tsv"
DAT = "geoip_RU.dat"
DAT_CHECKSUM = "geoip_RU.dat.sha256sum"
MANIFEST = "geoip_RU_v41_manifest.json"
QUALITY = "geoip_RU_quality_report.txt"
BLOCK_CHECKSUM = "geoip_RU_v41_blocked_ip_exclusions.txt.sha256sum"
SHA = re.compile(r"[0-9a-f]{64}")
OID = re.compile(r"[0-9a-f]{40}")
TAG = re.compile(r"(?:v41\.(?:0|[1-9][0-9]{0,5})|geoip-v41-snapshot-[0-9]{1,20}\.[0-9]{1,10})")
REPO_NAME = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
HEADER = ["SOURCE", "LOCAL_FILE", "FETCH_URL", "SHA256", "BYTES", "STATUS"]
TEXT_LIMIT = 1024 * 1024


def digest(data):
    return {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()}


class HttpsOnly(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not newurl.startswith("https://"):
            raise ValueError("non-HTTPS redirect in readback")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


HTTP = build_opener(HttpsOnly())


def get(url, *, optional=False, cap=4 * TEXT_LIMIT):
    req = Request(url, headers={"User-Agent": "geoip-v41-readback/1"})
    try:
        with HTTP.open(req, timeout=20) as response:
            if not response.geturl().startswith("https://"):
                raise ValueError("non-HTTPS readback")
            data = response.read(cap + 1)
    except HTTPError as err:
        if optional and err.code == 404:
            return None
        raise
    if len(data) > cap:
        raise ValueError("response exceeds readback limit")
    return data


class GitHub:
    def __init__(self, repo):
        if not REPO_NAME.fullmatch(repo):
            raise ValueError("invalid GitHub repository name")
        self.repo = repo
        self.api = f"https://api.github.com/repos/{repo}"
        self.raw = f"https://raw.githubusercontent.com/{repo}"

    def json(self, path, *, optional=False):
        raw = get(self.api + path, optional=optional)
        return json.loads(raw) if raw is not None else None

    def ref(self, path, *, optional=False):
        obj = self.json("/git/ref/" + path, optional=optional)
        if obj is None:
            return None
        ref = obj["object"]
        if ref["type"] != "commit" or not OID.fullmatch(ref["sha"]):
            raise ValueError(f"{path} is not a direct commit ref")
        return ref["sha"]

    def tag(self, tag):
        return self.ref("tags/" + quote(tag, safe=""), optional=True)

    def tip(self):
        return self.ref("heads/release")

    def parents(self, sha):
        return [parent["sha"] for parent in self.json("/git/commits/" + sha)["parents"]]

    def raw_file(self, sha, name, *, optional=False):
        return get(f"{self.raw}/{sha}/{name}", optional=optional, cap=TEXT_LIMIT)

    def release(self, tag):
        return self.json("/releases/tags/" + quote(tag, safe=""), optional=True)

    def download(self, tag, name, size):
        return get(f"https://github.com/{self.repo}/releases/download/{quote(tag, safe='')}/{name}", cap=size)


def provenance_record(raw):
    records = csv.DictReader(io.StringIO(raw.decode("utf-8"), newline=""), delimiter="\t")
    if records.fieldnames != HEADER:
        raise ValueError("unexpected provenance TSV header")
    hits = [r for r in records if r["LOCAL_FILE"] == ARCHIVE]
    if len(hits) != 1 or None in hits[0]:
        raise ValueError("expected one complete ipverse provenance row")
    row = hits[0]
    sha, size = row["SHA256"], row["BYTES"]
    if (row["STATUS"] != "downloaded" or not SHA.fullmatch(sha or "")
            or not re.fullmatch(r"[0-9]{1,8}", size or "") or not 5_000_000 <= int(size) <= 64 * TEXT_LIMIT):
        raise ValueError("invalid retained archive provenance")
    return {"sha256": sha, "size": int(size)}


def expected_files(gh, sha):
    dat_sum = gh.raw_file(sha, DAT_CHECKSUM)
    match = re.fullmatch(rb"([0-9a-f]{64})  geoip_RU\.dat\n", dat_sum)
    if not match:
        raise ValueError("invalid GeoIP checksum sidecar")
    dat_sha = match.group(1).decode("ascii")
    manifest = gh.raw_file(sha, MANIFEST)
    obj = json.loads(manifest)
    size = obj["output_bytes"]
    if obj["output_sha256"] != dat_sha or type(size) is not int or not 0 < size <= 8 * TEXT_LIMIT:
        raise ValueError("DAT checksum and manifest disagree")
    provenance = gh.raw_file(sha, PROVENANCE)
    files = {
        DAT: {"size": size, "sha256": dat_sha},
        DAT_CHECKSUM: digest(dat_sum),
        MANIFEST: digest(manifest),
        QUALITY: digest(gh.raw_file(sha, QUALITY)),
    }
    return files, provenance


def inspect_assets(release, expected):
    if release is None:
        return {"state": "no_published_release", "assets": {}}
    if release.get("draft"):
        return {"state": "draft", "assets": {}}
    by_name = {}
    for asset in release["assets"]:
        by_name.setdefault(asset["name"], []).append(asset)
    details = {}
    for name, spec in expected.items():
        found = by_name.get(name, [])
        if not found:
            state = "missing"
        elif len(found) > 1:
            state = "ambiguous"
        else:
            asset = found[0]
            if asset.get("state") != "uploaded":
                state = "not_uploaded"
            elif asset.get("size") != spec["size"]:
                state = "size_mismatch"
            elif not asset.get("digest"):
                state = "digest_unavailable"
            elif asset["digest"] != f"sha256:{spec['sha256']}":
                state = "digest_mismatch"
            else:
                state = "metadata_match"
        details[name] = state
    state = "metadata_match" if set(details.values()) == {"metadata_match"} else "incomplete_or_mismatch"
    return {"state": state, "assets": details, "id": release["id"], "immutable": release.get("immutable")}


def verify_downloads(gh, tag, result, expected, names):
    checks = {}
    if result["state"] != "metadata_match":
        return checks
    for name in names:
        try:
            actual = digest(gh.download(tag, name, expected[name]["size"]))
            checks[name] = "verified" if actual == expected[name] else "mismatch"
        except (OSError, ValueError) as err:
            checks[name] = f"unavailable: {err}"
    return checks


def matches(result, require_downloads):
    if result["state"] != "metadata_match":
        return False
    if not require_downloads:
        return True
    downloads = result["downloads"]
    return downloads.keys() == result["assets"].keys() and set(downloads.values()) == {"verified"}


def readback(gh, tag, download=False):
    tip = gh.tip()
    snapshot = gh.tag(tag)
    expected, provenance = expected_files(gh, tip)
    rolling_expected = {**expected, PROVENANCE: digest(provenance),
                        BLOCK_CHECKSUM: digest(gh.raw_file(tip, BLOCK_CHECKSUM))}
    rolling = inspect_assets(gh.release(ROLLING), rolling_expected)
    out = {"release_sha": tip, "snapshot_tag": tag, "snapshot_sha": snapshot,
           "verification": "metadata_and_downloads" if download else "metadata_only",
           "rolling": rolling}
    if download:
        rolling["downloads"] = verify_downloads(gh, ROLLING, rolling, rolling_expected, rolling_expected)
    if snapshot is None:
        out["phase"] = "no_snapshot_tag"
    else:
        parents = gh.parents(snapshot)
        target_files, target_provenance = (expected, provenance) if snapshot == tip else expected_files(gh, snapshot)
        marker = gh.raw_file(snapshot, MARKER, optional=True)
        out["tagged_parents"] = parents
        out["ipverse_provenance"] = provenance_record(target_provenance)
        if marker is None:
            out["phase"] = "legacy_snapshot"
        elif marker != (tag + "\n").encode("ascii"):
            out["phase"] = "invalid_snapshot_marker"
        else:
            target_files = {**target_files, ARCHIVE: out["ipverse_provenance"]}
        saved = inspect_assets(gh.release(tag), target_files)
        out["snapshot"] = saved
        if download:
            saved["downloads"] = verify_downloads(gh, tag, saved, target_files, target_files)
        if "phase" not in out:
            snap_ok = matches(saved, download)
            roll_ok = matches(rolling, download)
            if snapshot == tip:
                if not snap_ok:
                    out["phase"] = "promoted_snapshot_needs_investigation"
                else:
                    out["phase"] = "promoted_rolling_matches" if roll_ok else "promoted_rolling_incomplete_or_stale"
            elif parents == [tip]:
                if not snap_ok:
                    out["phase"] = "staged_snapshot_not_public_or_incomplete"
                else:
                    out["phase"] = "snapshot_verified_not_promoted" if download else "snapshot_metadata_matches_not_promoted"
            else:
                out["phase"] = "snapshot_not_current_release_or_direct_child"
    if gh.tip() != tip or gh.tag(tag) != snapshot:
        out["phase"] = "refs_changed_during_readback"
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("tag", help="exact v41 versioned snapshot tag")
    p.add_argument("--repo", default=REPO)
    p.add_argument("--verify-downloads", action="store_true", help="hash all tracked public asset downloads in addition to asset metadata")
    args = p.parse_args()
    if not TAG.fullmatch(args.tag):
        p.error("expected a v41 versioned snapshot tag")
    try:
        out = readback(GitHub(args.repo), args.tag, args.verify_downloads)
    except (OSError, ValueError, KeyError, TypeError) as err:
        print(f"Readback failed: {err}", file=sys.stderr)
        return 2
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
