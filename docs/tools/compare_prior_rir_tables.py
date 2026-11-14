"""Test whether the prior raw RIR files regenerate today's archived derived tables."""
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

SRC = Path(sys.argv[1]).resolve()
TARGET = Path(sys.argv[2]).resolve()
SCRIPTS = Path(sys.argv[3]).resolve()
REG = ("afrinic", "apnic", "arin", "lacnic", "ripencc")
NAMES = ["delegated-" + n + ("-extended" if n == "arin" else "") + "-latest" for n in REG]
TRACKED = ["geoip_RU_registered_asns.txt", "geoip_BY_KZ_registered_asns.txt",
           "geoip_RU_rir_registered_prefixes.txt", "geoip_RU_BY_KZ_rir_registered_prefixes.tsv"]


def sha(p):
    with p.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def read_rows(path):
    with path.open(encoding="utf-8", newline="") as f:
        return {r["LOCAL_FILE"]: r for r in csv.DictReader(f, delimiter="\t")}


old = read_rows(SRC / "geoip_RU_input_provenance.tsv")
new = read_rows(TARGET / "geoip_RU_input_provenance.tsv")
raw = {}
for n in NAMES:
    p = SRC / n
    if sha(p) != old[n]["SHA256"] or p.stat().st_size != int(old[n]["BYTES"]):
        raise ValueError(f"previous raw input hash drift: {n}")
    raw[n] = {"prior_sha256": old[n]["SHA256"], "target_sha256": new[n]["SHA256"],
              "exact_target_bytes": old[n]["SHA256"] == new[n]["SHA256"]}
with tempfile.TemporaryDirectory() as d:
    tmp = Path(d)
    legacy = ["build_v41_rir_legacy_inventory.py", *[str(SRC / n) for n in NAMES],
              TRACKED[0], TRACKED[2], "legacy_stats.txt", TRACKED[1]]
    regional = ["build_rir_rukzby_prefixes.py"]
    for reg, n in zip(REG, NAMES):
        regional.extend(("--" + reg, str(SRC / n)))
    regional += ["--output", TRACKED[3], "--stats", "regional_stats.txt"]
    for script, *args in (legacy, regional):
        subprocess.run([sys.executable, str(SCRIPTS / script), *args], cwd=tmp,
                       stdout=subprocess.DEVNULL, check=True)
    derived = {n: {"prior_recomputed_sha256": sha(tmp / n), "target_sha256": sha(TARGET / n),
                   "exact_target_bytes": sha(tmp / n) == sha(TARGET / n)}
               for n in TRACKED}
print(json.dumps({"mode": "prior verified RIR bytes versus exact current derived outputs",
                  "production_raw_recovered": False, "raw": raw, "derived": derived}, indent=2))
