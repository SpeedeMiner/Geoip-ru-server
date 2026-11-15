#!/usr/bin/env python3
"""Report exact v41 block-feed deltas using manifest-bound inputs. Never gates a release."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import ipaddress
import json
from pathlib import Path
import re
from shutil import copyfile
import subprocess
from tempfile import TemporaryDirectory

from build_v41_overlay import intersect, interval_size, normalize_interval_union, subtract
from bundle_v41_registry_inputs import BLOCK_MEMBERS, MAX_MEMBER, checked_members, sha
from prepare_blocked_sources_v41 import is_host, parse_feed, parse_line, validate_host_feed_counts
from validate_v41_block_feed_counts import FALLBACK, REQUIRED, read_stats
from validate_v41_publication_bounds import read as read_dat
from v41_release_manifest import MANIFEST, verify

PROVENANCE = "geoip_RU_input_provenance.tsv"
ARCHIVE = "v41-block-inputs.tar.gz"
POLICY = "geoip_RU_v41_manifest.json"
DAT = "geoip_RU.dat"
STATS = "geoip_RU_blocked_source_stats.txt"
TAG = "geoip_RU_ipverse_snapshot_tag.txt"
LAYERS = {
    "hard": "geoip_RU_blocked_ip_exact_and_legacy_hard.txt",
    "resolver": "geoip_RU_blocked_ipresolve_resolver_only.txt",
    "effective": "geoip_RU_v41_blocked_ip_exclusions.txt",
}
CHECKSUM = LAYERS["effective"] + ".sha256sum"
RESOLVER = REQUIRED[1]
LIVE_URL = "https://antifilter.download/list/ipresolve.lst"
PINNED_APPROVED = "geoip_RU_v38_approved_blocked_baseline.txt"
PINNED_RESOLVER = "geoip_RU_v38_pinned_antifilter-ipresolve.lst"
TAG_RE = r"(?:v41\.(?:0|[1-9][0-9]{0,5})|geoip-v41-snapshot-[0-9]{1,20}\.[0-9]{1,10})\n"


def space(data, *, strict):
    families = {4: [], 6: []}
    for line in data.decode("utf-8", errors="strict" if strict else "replace").splitlines():
        try:
            net = parse_line(line)
        except ValueError:
            if strict:
                raise
            continue  # Same parsing as the approved raw feed; invalid input counters stay separate.
        if net is not None:
            families[net.version].append((int(net.network_address), int(net.broadcast_address)))
    return {v: normalize_interval_union(families[v]) for v in (4, 6)}


def difference(old, new):
    result = {}
    for v, addr in ((4, ipaddress.IPv4Address), (6, ipaddress.IPv6Address)):
        report = {}
        for name, left, right in (("added", new, old), ("removed", old, new)):
            delta = subtract(left[v], right[v])
            report[name] = {
                "addresses": str(interval_size(delta)),
                "cidrs": [str(n) for lo, hi in delta for n in ipaddress.summarize_address_range(addr(lo), addr(hi))],
            }
        result[f"ipv{v}"] = report
    return result


def verify_raw(root):
    verify(root, root / MANIFEST, (PROVENANCE, ARCHIVE))
    _, members = checked_members(root / PROVENANCE, root / ARCHIVE, members=BLOCK_MEMBERS)
    return {n: bytes(members[n]) for n in (*REQUIRED, PINNED_RESOLVER, PINNED_APPROVED)}


def resolver_identity(root, feeds, *, as_of):
    status, count = read_stats(root / STATS)[RESOLVER]
    with (root / PROVENANCE).open(encoding="utf-8", newline="") as stream:
        rows = [row for row in csv.DictReader(stream, delimiter="\t") if row["LOCAL_FILE"] == RESOLVER]
    if len(rows) != 1 or rows[0]["FETCH_URL"] != LIVE_URL:
        raise ValueError("unexpected resolver feed provenance")
    row, = rows
    if status == FALLBACK:
        if row["STATUS"] != "unavailable" or space(feeds[RESOLVER], strict=True) != {4: [], 6: []}:
            raise ValueError("resolver fallback status does not match archived placeholder")
        return {"status": "DEGRADED_V38_FALLBACK", "fallback_resolver_sha256": sha(feeds[PINNED_RESOLVER]),
                "fallback_approved_baseline_sha256": sha(feeds[PINNED_APPROVED]),
                "fallback_origin": "PINNED_V38_APPROVED_BASELINE", "upstream_freshness": "UNKNOWN"}
    if row["STATUS"] != "downloaded" or not count:
        raise ValueError("AVAILABLE resolver stats without a downloaded feed")
    # Reconcile the approved host count against the retained bytes directly.
    nets, lines, invalid = parse_feed(feeds[RESOLVER].decode("utf-8", errors="replace"), RESOLVER)
    unique = set(nets)
    approved = sum(is_host(ipaddress.ip_network(prefix)) for prefix in unique)
    validate_host_feed_counts(RESOLVER, approved, len(unique), lines, invalid)
    if count != approved:
        raise ValueError("resolver stats disagree with archived host count")
    return {"status": "LIVE_DOWNLOAD", "observed_no_later_than_utc": as_of,
            "raw_sha256": sha(feeds[RESOLVER]), "upstream_freshness": "UNKNOWN"}


def verified_layers(root):
    verify(root, root / MANIFEST, (POLICY, DAT))
    policy = json.loads((root / POLICY).read_bytes())
    direct, dat_sha = read_dat(root / DAT)
    if policy["output_sha256"] != dat_sha or policy["input_provenance_sha256"] != sha((root / PROVENANCE).read_bytes()):
        raise ValueError("policy/DAT/provenance binding mismatch")
    expected = {
        "hard": policy["input_sha256"]["blocked_exact_and_legacy"],
        "resolver": policy["input_sha256"]["blocked_resolver_only"],
    }
    expected["effective"], filename = (root / CHECKSUM).read_text(encoding="ascii").split()
    if filename != LAYERS["effective"]:
        raise ValueError("unexpected effective-block checksum filename")
    result = {"DIRECT": direct["RU"]}
    for name, filename in LAYERS.items():
        p = root / filename
        if not 0 < p.stat().st_size <= 32 * 1024 * 1024:
            raise ValueError(f"invalid layer size: {filename}")
        data = p.read_bytes()
        if sha(data) != expected[name]:
            raise ValueError(f"layer digest mismatch: {filename}")
        result[name] = space(data, strict=True)
    return result


def select_live(history):
    """History is in release-chain order, newest to oldest. Preserve gaps explicitly."""
    inspected = []
    for record in history:
        inspected.append({k: v for k, v in record.items() if k != "feeds"})
        if record["status"] == "LIVE_DOWNLOAD":
            return record, inspected
    return None, inspected


def report(current, previous, last_live, inspected, current_layers, previous_layers, *, report_time):
    feeds = {}
    for name in REQUIRED:
        reference = last_live if name == RESOLVER else previous
        target = current["feeds"][name]
        base = reference["feeds"][name] if reference else None
        live_target = name != RESOLVER or current["status"] == "LIVE_DOWNLOAD"
        row = {
            "raw_sha256": sha(target), "baseline": reference["release_commit"] if reference else None,
            "baseline_raw_sha256": sha(base) if base is not None else None,
            "address_delta": None,
        }
        if not live_target:
            row["verdict"] = "DEGRADED_NO_LIVE_CANDIDATE"
            row["fallback_resolver_sha256"] = current["fallback_resolver_sha256"]
            row["fallback_approved_baseline_sha256"] = current["fallback_approved_baseline_sha256"]
            row["fallback_origin"] = current["fallback_origin"]
            if base is not None:
                row["historical_resolver_vs_last_live"] = difference(
                    space(base, strict=False), space(current["feeds"][PINNED_RESOLVER], strict=False))
        elif base is None:
            row["verdict"] = "NO_VERIFIED_BASELINE"
        else:
            delta = difference(space(base, strict=False), space(target, strict=False))
            changed = any(d["cidrs"] for v in delta.values() for d in v.values())
            row["verdict"] = "ADDRESS_SPACE_CHANGED" if changed else (
                "IDENTICAL" if target == base else "EQUIVALENT_ADDRESS_SPACE")
            row["address_delta"] = delta
        feeds[name] = row
    layer_delta = None
    if previous_layers:
        layer_delta = {"DIRECT": difference(previous_layers["DIRECT"], current_layers["DIRECT"])}
        for name in LAYERS:
            layer_delta[name] = {
                "address_space": difference(previous_layers[name], current_layers[name]),
                "intersection_with_DIRECT": difference(
                    {v: intersect(previous_layers[name][v], previous_layers["DIRECT"][v]) for v in (4, 6)},
                    {v: intersect(current_layers[name][v], current_layers["DIRECT"][v]) for v in (4, 6)}),
            }
    age = None
    if last_live and last_live.get("observed_no_later_than_utc"):
        elapsed = report_time - datetime.fromisoformat(last_live["observed_no_later_than_utc"])
        if elapsed.total_seconds() >= 0:
            age = int(elapsed.total_seconds())
    return {
        "schema": 1, "mode": "REPORT_ONLY", "resolver_candidate_status": current["status"],
        "published_history_checked": inspected, "last_verified_live_release": last_live["release_commit"] if last_live else None,
        "last_live_publication_age_seconds": age, "upstream_freshness": "UNKNOWN",
        "previous_release": previous["release_commit"] if previous else None,
        "newer_history_gaps": any(row["status"] in {"RELEASE_HISTORY_UNAVAILABLE", "UNVERIFIED_RELEASE_INPUT"}
                                  for row in inspected),
        "feeds": feeds, "layers_vs_previous_release": layer_delta,
    }


def git(*args, cwd):
    return subprocess.check_output(["git", *args], cwd=cwd, timeout=60, stderr=subprocess.PIPE)


def get_published(repo, history, ref, folder, *, full, archive_cache=None):
    """Use sidecars from the pinned release commit, archive from its pinned snapshot path."""
    folder.mkdir()
    for name in (PROVENANCE, MANIFEST, STATS, TAG, *((POLICY, DAT, CHECKSUM, *LAYERS.values()) if full else ())):
        (folder / name).write_bytes(git("show", f"{ref}:{name}", cwd=history))
    tag = (folder / TAG).read_text(encoding="ascii")
    if not re.fullmatch(TAG_RE, tag):
        raise ValueError("invalid published snapshot tag")
    if archive_cache is not None:
        # Cache keys are full release SHAs. The retained archive still has to pass
        # both the release manifest and the exact input provenance checks.
        cached = archive_cache / (ref + ".tar.gz")
        if not 0 < cached.stat().st_size <= MAX_MEMBER:
            raise ValueError("invalid cached archive size")
        copyfile(cached, folder / ARCHIVE)
    else:
        command = [
            "curl", "--fail", "--location", "--silent", "--show-error", "--proto", "=https",
            "--proto-redir", "=https", "--connect-timeout", "10", "--max-time", "30",
            "--max-filesize", str(MAX_MEMBER), "--output", str(folder / ARCHIVE),
            f"https://github.com/{repo}/releases/download/{tag.strip()}/{ARCHIVE}",
        ]
        transfer = subprocess.run(command, timeout=35, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        if transfer.returncode:
            raise ValueError(f"published block-input transfer failed (curl {transfer.returncode}): "
                             + transfer.stderr.decode("utf-8", errors="replace").strip()[:120])
    feeds = verify_raw(folder)
    as_of = git("show", "-s", "--format=%cI", ref, "--", cwd=history).decode("ascii").strip()
    record = {"release_commit": ref, "snapshot": tag.strip(), "feeds": feeds,
              **resolver_identity(folder, feeds, as_of=as_of)}
    return record


def audit_history(repo, pinned, candidate, *, depth, now, archive_cache=None):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise ValueError("invalid repository")
    if pinned is not None and not re.fullmatch(r"[0-9a-f]{40}", pinned):
        raise ValueError("invalid previous release commit")
    feeds = verify_raw(candidate)
    current = {"feeds": feeds, **resolver_identity(candidate, feeds, as_of=None)}
    current_layers = verified_layers(candidate)
    rows = []
    previous = previous_layers = None
    with TemporaryDirectory(prefix="v41-block-audit-") as tmp:
        history = Path(tmp)
        try:
            git("init", "-q", cwd=history)
            git("fetch", "-q", "--no-tags", f"--depth={depth}", f"https://github.com/{repo}.git",
                pinned or "refs/heads/release", cwd=history)
            refs = git("rev-list", "--first-parent", "FETCH_HEAD", cwd=history).decode("ascii").splitlines()
            if not refs or pinned is not None and refs[0] != pinned:
                raise ValueError("release history does not start at the requested commit")
        except (OSError, subprocess.SubprocessError):
            refs = []
            rows.append({"release_commit": pinned, "status": "RELEASE_HISTORY_UNAVAILABLE"})
        for index, ref in enumerate(refs):
            folder = history / ("snapshot-" + ref)
            try:
                record = get_published(repo, history, ref, folder, full=index == 0, archive_cache=archive_cache)
            except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
                reason = str(exc) if isinstance(exc, (OSError, ValueError, KeyError, TypeError)) else type(exc).__name__
                rows.append({"release_commit": ref, "status": "UNVERIFIED_RELEASE_INPUT", "reason": reason[:240]})
                continue
            rows.append(record)
            if index == 0:
                previous = record
                try:
                    previous_layers = verified_layers(folder)
                except (OSError, ValueError, KeyError, TypeError) as exc:
                    rows.append({"release_commit": ref, "status": "UNVERIFIED_PREVIOUS_LAYERS", "reason": str(exc)[:240]})
            if record["status"] == "LIVE_DOWNLOAD":
                break
    baseline, inspected = select_live(rows)
    result = report(current, previous, baseline, inspected, current_layers, previous_layers, report_time=now)
    result["candidate_dat_sha256"] = sha((candidate / DAT).read_bytes())
    result["candidate_provenance_sha256"] = sha((candidate / PROVENANCE).read_bytes())
    result["comparison_release_commit"] = refs[0] if refs else pinned
    result["report_utc"] = now.isoformat()
    result["history_limit"] = depth
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repository", required=True)
    p.add_argument("--candidate", type=Path, required=True)
    p.add_argument("--previous-release")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--archive-cache", type=Path, help="use retained archives named by release SHA; still verify all bytes")
    p.add_argument("--history-depth", type=int, choices=range(1, 13), default=6)
    a = p.parse_args()
    try:
        result = audit_history(a.repository, a.previous_release, a.candidate,
                               depth=a.history_depth, now=datetime.now(timezone.utc), archive_cache=a.archive_cache)
        with a.output.open("x", encoding="utf-8") as f:
            json.dump(result, f, sort_keys=True, separators=(",", ":"))
            f.write("\n")
        print("Block-feed report (advisory): " + ", ".join(
            f"{name}={row['verdict']}" for name, row in result["feeds"].items()))
    except (OSError, ValueError, TypeError, KeyError) as exc:
        p.exit(1, f"Unable to write block-feed report: {exc}\n")


if __name__ == "__main__":
    main()
