#!/usr/bin/env python3
"""Compare the verified PR #31 and #32 candidate ZIPs without extraction."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile

ARCHIVE = "as-ip-blocks.tar.gz"
UTC_LINE = re.compile(rb"(?m)^Generated UTC: [0-9T:.+-]+$")


def sha(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def members(z):
    names = [item.filename for item in z.infolist() if not item.is_dir()]
    if len(names) != len(set(names)):
        raise ValueError("duplicate ZIP members")
    result = {}
    for name in names:
        with z.open(name) as f:
            result[name] = (z.getinfo(name).file_size, hashlib.file_digest(f, "sha256").hexdigest())
    return result


def run(a, b, expect_a, expect_b):
    digests = [sha(a), sha(b)]
    if digests != [expect_a, expect_b]:
        raise ValueError("candidate ZIP digest mismatch")
    with zipfile.ZipFile(a) as za, zipfile.ZipFile(b) as zb:
        left, right = members(za), members(zb)
        common = left.keys() & right.keys()
        raw_diff = sorted(name for name in common if left[name] != right[name])
        manifest_a = json.loads(za.read("geoip_RU_v41_manifest.json"))
        manifest_b = json.loads(zb.read("geoip_RU_v41_manifest.json"))
        fields = sorted(k for k in manifest_a.keys() | manifest_b.keys() if manifest_a.get(k) != manifest_b.get(k))
        normalized_diff = []
        for name in raw_diff:
            if name == "geoip_RU_v41_manifest.json":
                different = any(key != "generated_at" for key in fields)
            elif name.endswith(".txt"):
                different = UTC_LINE.sub(b"Generated UTC: <timestamp>", za.read(name)) != UTC_LINE.sub(
                    b"Generated UTC: <timestamp>", zb.read(name))
            else:
                different = True
            if different:
                normalized_diff.append(name)
        return {
            "zip_sha256": {"pr31": digests[0], "pr32": digests[1]},
            "members": {"pr31": len(left), "pr32": len(right), "shared": len(common)},
            "only_pr31": sorted(left.keys() - right.keys()),
            "only_pr32": sorted(right.keys() - left.keys()),
            "byte_identical_shared": len(common) - len(raw_diff),
            "different_shared": raw_diff,
            "different_after_timestamp_normalization": normalized_diff,
            "manifest_changed_fields": fields,
            "geoip_dat": right["geoip_RU.dat"],
            "effective_mask": right["geoip_RU_v41_blocked_ip_exclusions.txt"],
            "ipverse_archive": right[ARCHIVE],
        }


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("pr31", type=Path)
    p.add_argument("pr32", type=Path)
    p.add_argument("pr31_sha256")
    p.add_argument("pr32_sha256")
    args = p.parse_args()
    print(json.dumps(run(args.pr31, args.pr32, args.pr31_sha256, args.pr32_sha256), indent=2))
