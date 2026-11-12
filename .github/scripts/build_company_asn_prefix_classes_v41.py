#!/usr/bin/env python3
"""Extract exact corporate and shared-infrastructure origin prefixes for GeoIP v41."""
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import re
from pathlib import Path
from typing import Any

ASN_RE = re.compile(r"\bAS(\d+)\b", re.IGNORECASE)
ALLOWED_CLASSES = {"CORE_CORPORATE", "SHARED_INFRA"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_company_registry(path: Path) -> dict[int, dict[str, str]]:
    result: dict[int, dict[str, str]] = {}
    with path.open(encoding="utf-8-sig") as stream:
        for line_no, raw in enumerate(stream, 1):
            line = raw.rstrip("\r\n")
            if not line or line.lstrip().startswith("#"):
                continue
            fields = line.split("\t")
            if len(fields) != 4 or not all(x.strip() for x in fields):
                raise ValueError(f"Malformed company ASN row {line_no}: expected four fields")
            token = fields[0].strip().upper()
            if token.startswith("AS"):
                token = token[2:]
            if not token.isdigit():
                raise ValueError(f"Invalid ASN on registry row {line_no}: {fields[0]!r}")
            asn = int(token)
            if not 0 < asn <= 4294967295:
                raise ValueError(f"ASN out of range on registry row {line_no}: {asn}")
            if asn in result:
                raise ValueError(f"Duplicate company ASN AS{asn}")
            result[asn] = {"group": fields[1].strip(), "entity": fields[2].strip(), "evidence": fields[3].strip()}
    if len(result) < 10:
        raise ValueError(f"Company registry unexpectedly small: {len(result)}")
    return result


def read_policy(path: Path, registry: dict[int, dict[str, str]]) -> dict[int, dict[str, str]]:
    policy: dict[int, dict[str, str]] = {}
    with path.open(encoding="utf-8-sig") as stream:
        header = None
        for line_no, raw in enumerate(stream, 1):
            line = raw.rstrip("\r\n")
            if not line or line.lstrip().startswith("#"):
                continue
            fields = line.split("\t")
            if header is None:
                header = fields
                if header != ["ASN", "EXCEPTION_CLASS", "COMPANY_GROUP", "POLICY_NOTE"]:
                    raise ValueError(f"Unexpected policy TSV header on line {line_no}: {header}")
                continue
            if len(fields) != 4 or not all(x.strip() for x in fields):
                raise ValueError(f"Malformed ASN exception policy row {line_no}")
            token = fields[0].strip().upper()
            if token.startswith("AS"):
                token = token[2:]
            if not token.isdigit():
                raise ValueError(f"Invalid policy ASN on row {line_no}: {fields[0]!r}")
            asn = int(token)
            role = fields[1].strip()
            if role not in ALLOWED_CLASSES:
                raise ValueError(f"Invalid exception class for AS{asn}: {role}")
            if asn in policy:
                raise ValueError(f"Duplicate exception policy for AS{asn}")
            if asn not in registry:
                raise ValueError(f"Policy ASN AS{asn} is absent from the company registry")
            if fields[2].strip() != registry[asn]["group"]:
                raise ValueError(
                    f"Company group mismatch for AS{asn}: policy={fields[2]!r}, registry={registry[asn]['group']!r}"
                )
            policy[asn] = {"class": role, "group": fields[2].strip(), "note": fields[3].strip()}
    if set(policy) != set(registry):
        missing = sorted(set(registry) - set(policy))
        extra = sorted(set(policy) - set(registry))
        raise ValueError(f"ASN registry/policy mismatch; missing={missing}, extra={extra}")
    return policy


def write_prefixes(path: Path, title: str, prefixes: dict[str, set[int]],
                   selected: Path, registry: Path, policy: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(f"# v41 {title}\n")
        stream.write("# Exact selected-origin prefixes from the same pinned ipverse snapshot used by the base builder.\n")
        stream.write(f"# selected_origin_input_sha256={sha256(selected)}\n")
        stream.write(f"# company_registry_sha256={sha256(registry)}\n")
        stream.write(f"# exception_policy_sha256={sha256(policy)}\n")
        for prefix in sorted(prefixes, key=lambda value: (
            ipaddress.ip_network(value).version,
            int(ipaddress.ip_network(value).network_address),
            ipaddress.ip_network(value).prefixlen,
        )):
            origin_label = ",".join(f"AS{asn}" for asn in sorted(prefixes[prefix]))
            stream.write(f"{prefix} # {origin_label}\n")


def build_company_prefix_classes(selected_prefixes: Path, company_registry: Path, policy_file: Path,
                                 all_output: Path, core_output: Path, shared_output: Path) -> dict[str, Any]:
    registry = read_company_registry(company_registry)
    policy = read_policy(policy_file, registry)
    all_prefixes: dict[str, set[int]] = {}
    core_prefixes: dict[str, set[int]] = {}
    shared_prefixes: dict[str, set[int]] = {}

    with selected_prefixes.open(encoding="utf-8-sig") as stream:
        for line_no, raw in enumerate(stream, 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            prefix_text, marker, origins_text = line.partition("#")
            try:
                network = ipaddress.ip_network(prefix_text.strip(), strict=True)
            except ValueError as exc:
                raise ValueError(f"Invalid selected-origin prefix on line {line_no}: {prefix_text!r}") from exc
            if network.prefixlen == 0:
                raise ValueError(f"Default route is not allowed in selected-origin input: line {line_no}")
            if not marker:
                raise ValueError(f"Selected-origin row {line_no} has no origin-ASN provenance")
            origins = {int(value) for value in ASN_RE.findall(origins_text)}
            if not origins:
                raise ValueError(f"Selected-origin row {line_no} has no parseable origin ASN")
            selected = origins & registry.keys()
            if not selected:
                continue
            prefix = str(network)
            if prefix in all_prefixes:
                raise ValueError(f"Duplicate selected-origin prefix row: {prefix}")
            all_prefixes[prefix] = selected
            # A MOAS prefix is CORE if any exact origin is CORE. SHARED_INFRA applies
            # only when no CORE origin exists, preventing a hosting origin from
            # downgrading a prefix also originated by a protected first-party company.
            classes = {policy[asn]["class"] for asn in selected}
            if "CORE_CORPORATE" in classes:
                core_prefixes[prefix] = selected
            else:
                shared_prefixes[prefix] = selected

    if not all_prefixes:
        raise ValueError("No selected prefixes originate from the curated company ASN registry")
    if set(core_prefixes) & set(shared_prefixes):
        raise ValueError("Internal error: CORE and SHARED prefix masks overlap")
    if set(core_prefixes) | set(shared_prefixes) != set(all_prefixes):
        raise ValueError("Internal error: CORE/SHARED masks do not cover all company prefixes")

    write_prefixes(all_output, "all allowlisted company-ASN origin prefixes", all_prefixes,
                   selected_prefixes, company_registry, policy_file)
    write_prefixes(core_output, "CORE_CORPORATE origin prefixes (protected from all approved blocks)", core_prefixes,
                   selected_prefixes, company_registry, policy_file)
    write_prefixes(shared_output, "SHARED_INFRA origin prefixes (protected from resolver-only blocks)", shared_prefixes,
                   selected_prefixes, company_registry, policy_file)

    def metrics(prefixes: dict[str, set[int]]) -> dict[str, int]:
        counts = {4: 0, 6: 0}
        addresses = {4: 0, 6: 0}
        asns: set[int] = set()
        for prefix, origins in prefixes.items():
            net = ipaddress.ip_network(prefix)
            counts[net.version] += 1
            addresses[net.version] += net.num_addresses
            asns.update(origins)
        return {
            "prefixes": len(prefixes),
            "active_origin_asns": len(asns),
            "ipv4_prefixes": counts[4],
            "ipv6_prefixes": counts[6],
            "ipv4_addresses": addresses[4],
            "ipv6_addresses": addresses[6],
        }

    result = {
        "registry_entries": len(registry),
        "policy_entries": len(policy),
        "core": metrics(core_prefixes),
        "shared_infrastructure": metrics(shared_prefixes),
        "all_company_origins": metrics(all_prefixes),
        "selected_origin_sha256": sha256(selected_prefixes),
        "company_registry_sha256": sha256(company_registry),
        "exception_policy_sha256": sha256(policy_file),
        "all_output_sha256": sha256(all_output),
        "core_output_sha256": sha256(core_output),
        "shared_output_sha256": sha256(shared_output),
    }
    print(result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selected-prefixes", type=Path, required=True)
    parser.add_argument("--company-asns", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--core-output", type=Path, required=True)
    parser.add_argument("--shared-output", type=Path, required=True)
    args = parser.parse_args()
    try:
        build_company_prefix_classes(args.selected_prefixes, args.company_asns, args.policy,
                                     args.output, args.core_output, args.shared_output)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"ERROR: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
