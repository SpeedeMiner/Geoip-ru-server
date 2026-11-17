#!/usr/bin/env python3
"""Validate the required service catalog before fetching unrelated inputs."""
import argparse
import json
from pathlib import Path

from build_v41_overlay import parse_services_json


def validate(path):
    prefixes, _, service_count, _ = parse_services_json(path)
    if service_count < 50:
        raise ValueError(f"Kyoresuas ru-standard service catalog unexpectedly small: {service_count} services")
    return {"services": service_count, "unique_prefixes": len(prefixes)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(validate(args.file), sort_keys=True))
    except (OSError, ValueError, TypeError, KeyError) as exc:
        parser.exit(1, f"invalid service catalog: {exc}\n")


if __name__ == "__main__":
    main()
