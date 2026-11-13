#!/usr/bin/env python3
import csv
import ipaddress
import pathlib
import sys

inputs = [pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])]
private_out = pathlib.Path(sys.argv[3])
reachable_out = pathlib.Path(sys.argv[4])
non_global = set()
global_exceptions = set()

for path in inputs:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
    except (OSError, UnicodeError, csv.Error) as exc:
        raise SystemExit(f"Cannot parse IANA registry {path}: {exc}")
    if not rows or "Address Block" not in rows[0] or "Globally Reachable" not in rows[0]:
        raise SystemExit(f"Unexpected IANA CSV schema: {path}")
    for row in rows:
        block = (row.get("Address Block") or "").strip()
        reachable = (row.get("Globally Reachable") or "").strip().split()[0].lower() if (row.get("Globally Reachable") or "").strip() else ""
        if not block or reachable not in {"true", "false"}:
            continue
        try:
            net = ipaddress.ip_network(block, strict=True)
        except ValueError:
            continue
        if net.prefixlen == 0:
            continue
        if reachable == "false":
            non_global.add(str(net))
        else:
            global_exceptions.add(str(net))

def key(value):
    net = ipaddress.ip_network(value)
    return net.version, int(net.network_address), net.prefixlen

if len(non_global) < 20:
    raise SystemExit(f"IANA non-globally-reachable prefix count unexpectedly small: {len(non_global)}")

private_out.write_text(
    "# IANA Special-Purpose entries where Globally Reachable=False\n" +
    "\n".join(sorted(non_global, key=key)) + "\n", encoding="utf-8"
)
reachable_out.write_text(
    "# IANA Special-Purpose entries where Globally Reachable=True; carve-outs from broad special blocks\n" +
    "\n".join(sorted(global_exceptions, key=key)) + "\n", encoding="utf-8"
)
print(f"IANA non-global prefixes: {len(non_global)}")
print(f"IANA global-reachable exception prefixes: {len(global_exceptions)}")
