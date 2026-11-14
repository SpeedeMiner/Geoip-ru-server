#!/usr/bin/env python3
"""Reconcile v37 additional-feed eligibility and isolate v41 resolver-only losses.

Pass the complete v41 build artifact directory and a directory containing
the seven locked upstream DATs under their LOCAL_FILE names.
This diagnostic never changes admission, source lists, or production output.
"""
import argparse
import csv
import hashlib
from ipaddress import ip_network
import json
from pathlib import Path

from build_v41_overlay import (
    intersect, interval_size, intervals, networks_from_intervals,
    normalize_interval_union, parse_cidr_file, parse_geoip_dat,
    parse_regional_admission_exclusions, parse_rir_tsv, subtract,
)
from validate_v41_telegram import PINNED_FEED, read_telegram_feed

SOURCES = {
    "grimbird": "grimbird-geoip.dat", "digne": "digne-geoip.dat",
    "davoyan": "davoyan-geoip.dat", "golukon": "golukon-geoip.dat",
    "v2fly": "v2fly-geoip.dat", "loyalsoldier": "loyalsoldier-ru.dat",
    "loyalsoldier-by": "loyalsoldier-by.dat",
}
GROUPS = (("grimbird", "digne"), ("davoyan",), ("golukon",))


def category_allowed(source, tag):
    tag = tag.lower().strip()
    if source == "grimbird":
        return tag == "ru" or (tag.startswith("ru-") and not any(
            token in tag for token in ("direct", "whitelist", "wl-")
        ))
    if source == "digne":
        return tag in {"ru", "ru-ip"}
    if source == "v2fly":
        return tag in {"ru", "by", "kz"}
    return tag == ("by" if source == "loyalsoldier-by" else "ru")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_cidrs(path):
    return parse_cidr_file(path)[0]


def additional_eligibility(f, m):
    groups = [normalize_interval_union(*(f[k] for k in group)) for group in GROUPS]
    all_additional = normalize_interval_union(*groups)
    two = normalize_interval_union(intersect(groups[0], groups[1]),
                                   intersect(groups[0], groups[2]), intersect(groups[1], groups[2]))
    trusted = normalize_interval_union(f["v2fly"], f["loyalsoldier"], f["loyalsoldier-by"])
    eligible = normalize_interval_union(two, intersect(all_additional, m["asn"]),
                                        intersect(all_additional, m["rir_ru"]))
    eligible = subtract(eligible, normalize_interval_union(trusted, m["private"], m["asn"]))
    return all_additional, two, eligible


def resolver_only_loss(eligible, m):
    selected = intersect(intersect(eligible, m["resolver"]), m["effective"])
    return subtract(selected, normalize_interval_union(m["private"], m["hard"], m["admission"], m["direct"]))


def source_labels(path):
    rows = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        prefix, _, comment = line.partition("#")
        label = comment.strip().removeprefix("sources=")
        rows[ip_network(prefix.strip())] = label.split(",") if label else []
    return rows


def calculate(artifact, source_dir, admission_file, telegram_file):
    provenance = artifact / "geoip_RU_input_provenance.tsv"
    with provenance.open(encoding="utf-8", newline="") as stream:
        index = {r["LOCAL_FILE"]: r for r in csv.DictReader(stream, delimiter="\t")}
    feeds, feed_sha = {}, {}
    for name, file in SOURCES.items():
        path = source_dir / file
        row = index[file]
        if path.stat().st_size != int(row["BYTES"]) or sha(path) != row["SHA256"]:
            raise ValueError(f"Locked source mismatch: {file}")
        feed_sha[name] = row["SHA256"]
        feeds[name] = {net for tag, nets in parse_geoip_dat(path).items()
                       if category_allowed(name, tag) for net in nets}
        if not feeds[name] or any(n.prefixlen < (8 if n.version == 4 else 24) for n in feeds[name]):
            raise ValueError(f"Missing or overly broad accepted categories in {file}")

    final = parse_geoip_dat(artifact / "geoip_RU.dat")
    base = parse_geoip_dat(artifact / "geoip_RU_v37_base.dat")
    if set(final) != {"RU", "PRIVATE"} or set(base) != {"RU", "PRIVATE"} or any(
        intervals(final["PRIVATE"], v) != intervals(base["PRIVATE"], v) for v in (4, 6)
    ):
        raise ValueError("Unexpected category or PRIVATE drift")
    manifest = json.loads((artifact / "geoip_RU_v41_manifest.json").read_text())
    hashes = manifest["input_sha256"]
    paths = {
        "base_v37_geoip": artifact / "geoip_RU_v37_base.dat",
        "v37_blocked_base": artifact / "geoip_RU_blocked_ip_exclusions.txt",
        "blocked_exact_and_legacy": artifact / "geoip_RU_blocked_ip_exact_and_legacy_hard.txt",
        "blocked_resolver_only": artifact / "geoip_RU_blocked_ipresolve_resolver_only.txt",
        "regional_rir_inventory": artifact / "geoip_RU_BY_KZ_rir_registered_prefixes.tsv",
        "regional_admission_exclusions": admission_file,
    }
    if any(sha(path) != hashes[k] for k, path in paths.items()):
        raise ValueError("Production input digest mismatch")
    dat_sha = sha(artifact / "geoip_RU.dat")
    if dat_sha != manifest["output_sha256"]:
        raise ValueError("Final DAT does not match its manifest")
    effective_path = artifact / "geoip_RU_v41_blocked_ip_exclusions.txt"
    for path, digest in ((artifact / "geoip_RU.dat", dat_sha), (effective_path, sha(effective_path)),
                         (provenance, sha(provenance))):
        if path.with_name(path.name + ".sha256sum").read_text().split()[0] != digest:
            raise ValueError(f"Published checksum mismatch: {path}")

    v37_asn = read_cidrs(artifact / "geoip_RU_BY_KZ_asn_bgp_prefixes.txt")
    v37_rir = read_cidrs(artifact / "geoip_RU_rir_registered_prefixes.txt")
    full_rir, _ = parse_rir_tsv(paths["regional_rir_inventory"])
    full_rir = set().union(*full_rir.values())
    masks = {
        "asn": v37_asn, "rir_ru": v37_rir, "rir_regional": full_rir,
        "private": final["PRIVATE"], "direct": final["RU"], "base": base["RU"],
        "approved": read_cidrs(paths["v37_blocked_base"]),
        "hard": read_cidrs(paths["blocked_exact_and_legacy"]) | read_telegram_feed(telegram_file),
        "resolver": read_cidrs(paths["blocked_resolver_only"]),
        "effective": read_cidrs(effective_path),
        "admission": set(parse_regional_admission_exclusions(admission_file)),
    }
    with (artifact / "geoip_RU_v37_additional_provenance.tsv").open(encoding="utf-8", newline="") as stream:
        accepted = {ip_network(r["PREFIX"]) for r in csv.DictReader(stream, delimiter="\t")}

    additions = {}
    with (artifact / "geoip_RU_v41_prefix_provenance.tsv").open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream, delimiter="\t"):
            additions.setdefault(row["source_id"], set()).add(ip_network(row["prefix"]))
    admission_ids = {
        "all-company-asn-origins", "rir-rukzby-selected-origin-protected", "rir-resource-RU",
        "rir-resource-BY", "rir-resource-KZ", "hydra-direct", "hydra-whitelist",
        "reviewed-operator-prefixes", "kyoresuas-standard", "hxehex-mobile-hosts",
        "w1zardz-service-direct", "operator-whitelist",
    }
    protection_ids = {
        "core-company-asn-origins", "shared-infrastructure-asn-origins",
        "rir-rukzby-selected-origin-protected", "rir-resource-RU", "rir-resource-BY",
        "rir-resource-KZ", "reviewed-operator-prefixes", "verified-service-resolver-protected",
        "verified-service-exact-hosts",
    }
    if not (admission_ids | protection_ids) <= additions.keys():
        raise ValueError("Missing v41 provenance source")
    resolver_labels = source_labels(paths["blocked_resolver_only"])
    totals, candidates, restored_rows, removed_rows = {}, [], [], []
    for v in (4, 6):
        f = {k: intervals(nets, v) for k, nets in feeds.items()}
        m = {k: intervals(nets, v) for k, nets in masks.items()}
        all_additional, two, eligible = additional_eligibility(f, m)
        post_carve = subtract(eligible, m["approved"])
        if post_carve != intervals(accepted, v) or subtract(post_carve, m["base"]):
            raise ValueError(f"Reconstructed additional eligibility does not match published v37 evidence (IPv{v})")
        raw_lost = intersect(eligible, m["approved"])
        resolver_lost = resolver_only_loss(eligible, m)
        if intersect(resolver_lost, raw_lost) != resolver_lost:
            raise ValueError(f"Effective resolver exclusions diverge from the v37 approved union (IPv{v})")
        lost_after_v37 = subtract(post_carve, m["direct"])
        explained_after_v37 = normalize_interval_union(m["admission"], m["hard"], m["effective"])
        if subtract(lost_after_v37, explained_after_v37):
            raise ValueError(f"Unexplained v41 loss after v37 (IPv{v})")
        for net in sorted(networks_from_intervals(lost_after_v37, v)):
            exact = intervals({net}, v)
            removed_rows.append({
                "prefix": str(net), "addresses": net.num_addresses,
                "covering_admission_exclusions": [
                    str(exclusion) for exclusion in sorted(n for n in masks["admission"] if n.version == v)
                    if exclusion.overlaps(net)
                ],
                "hard_or_telegram_addresses": interval_size(intersect(exact, m["hard"])),
                "effective_resolver_addresses": interval_size(
                    intersect(subtract(exact, m["hard"]), m["effective"])),
            })
        hard = intersect(raw_lost, m["hard"])
        already_direct = intersect(raw_lost, m["direct"])
        admission = intersect(raw_lost, m["admission"])
        remainder = subtract(raw_lost, normalize_interval_union(resolver_lost, hard, already_direct, admission))
        totals[f"ipv{v}"] = {k: interval_size(val) for k, val in (
            ("source_union", all_additional), ("two_group", subtract(two, m["private"])),
            ("eligible_before_v37_carve", eligible), ("accepted_after_v37_carve", post_carve),
            ("lost_to_v37_approved_union", raw_lost), ("hard_or_telegram", hard),
            ("already_restored_in_v41", already_direct), ("regional_admission_exclusion", admission),
            ("effective_resolver_only_loss", resolver_lost), ("other", remainder),
            ("accepted_after_v37_missing_in_v41", lost_after_v37),
            ("accepted_after_v37_hard_or_telegram", intersect(lost_after_v37, m["hard"])),
            ("accepted_after_v37_admission_exclusion", intersect(lost_after_v37, m["admission"])),
            ("accepted_after_v37_effective_resolver", intersect(subtract(lost_after_v37, m["hard"]), m["effective"])),
        )}
        if already_direct:
            scoped = {key: intersect(intervals(additions[key], v), already_direct)
                      for key in admission_ids | protection_ids}
            for net in sorted(networks_from_intervals(already_direct, v)):
                exact = intervals({net}, v)
                feed_hits = {key: interval_size(intersect(exact, value))
                             for key, value in f.items() if key in {s for group in GROUPS for s in group}}
                admission_hits = {key: interval_size(intersect(exact, scoped[key]))
                                  for key in sorted(admission_ids) if intersect(exact, scoped[key])}
                protection_hits = {key: interval_size(intersect(exact, scoped[key]))
                                   for key in sorted(protection_ids) if intersect(exact, scoped[key])}
                if subtract(exact, normalize_interval_union(*(scoped[key] for key in admission_ids))):
                    raise ValueError(f"No v41 re-admission source for {net}")
                if subtract(exact, normalize_interval_union(*(scoped[key] for key in protection_ids))):
                    raise ValueError(f"No v41 resolver protection source for {net}")
                labels = sorted({label for prefix, values in resolver_labels.items()
                                 if prefix.version == net.version and prefix.overlaps(net) for label in values})
                restored_rows.append({
                    "prefix": str(net), "addresses": net.num_addresses,
                    "source_overlap_addresses": feed_hits,
                    "resolver_evidence_labels": labels,
                    "readmission_overlap_addresses": admission_hits,
                    "resolver_protection_overlap_addresses": protection_hits,
                })
        for net in sorted(networks_from_intervals(resolver_lost, v)):
            exact = intervals({net}, v)
            candidates.append({
                "prefix": str(net), "addresses": net.num_addresses,
                "source_overlap_addresses": {
                    k: interval_size(intersect(exact, f[k])) for group in GROUPS for k in group
                },
                "two_group_addresses": interval_size(intersect(exact, two)),
                "rir_ru_addresses": interval_size(intersect(exact, m["rir_ru"])),
                "regional_rir_addresses": interval_size(intersect(exact, m["rir_regional"])),
            })
    return {"dat_sha256": dat_sha, "effective_mask_sha256": sha(effective_path),
            "input_provenance_sha256": sha(provenance), "locked_dat_sha256": feed_sha,
            "totals": totals, "restored": restored_rows, "removed_after_v37": removed_rows,
            "candidates": candidates}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--admission", type=Path, required=True)
    parser.add_argument("--telegram", type=Path, default=PINNED_FEED)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = calculate(args.artifact, args.source_dir, args.admission, args.telegram)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["totals"], indent=2))


if __name__ == "__main__":
    main()
