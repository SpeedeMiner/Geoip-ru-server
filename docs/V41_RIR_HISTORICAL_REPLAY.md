# Replaying the v41 RIR inventories

The v41 build reads five daily delegated-stat snapshots in two different
inventory generators. Their freshness window is still inclusive: up to 14
days old, or dated up to one day ahead. The workflow still downloads the
current snapshots and uses a single current UTC date for both generators.
It does not accept a historical date from workflow inputs.

For an offline historical replay, use the exact registry bytes from the
**versioned** snapshot and the UTC freshness reference from either of its
`geoip_RU_rir_stats.txt` or `geoip_RU_BY_KZ_rir_stats.txt` reports.
If the new `Freshness reference UTC date` field is absent, use the UTC date of
the original legacy RIR report's `Generated UTC` timestamp as the best
available reference. Do not derive this date from the input headers or use the
rolling release's reports for a different snapshot.

After checking the versioned SHA-256 and restoring the archived files with the
existing registry bundle tool, run both commands from the source checkout:

```sh
registry_dir=restored-registry-inputs
reference=2026-11-14 # Example only. Use the original build's UTC reference.

python3 .github/scripts/build_v41_rir_legacy_inventory.py \
  "$registry_dir/delegated-afrinic-latest" "$registry_dir/delegated-apnic-latest" \
  "$registry_dir/delegated-arin-extended-latest" "$registry_dir/delegated-lacnic-latest" \
  "$registry_dir/delegated-ripencc-latest" geoip_RU_registered_asns.txt \
  geoip_RU_rir_registered_prefixes.txt geoip_RU_rir_stats.txt geoip_BY_KZ_registered_asns.txt \
  --as-of "$reference"

python3 .github/scripts/build_rir_rukzby_prefixes.py \
  --afrinic "$registry_dir/delegated-afrinic-latest" --apnic "$registry_dir/delegated-apnic-latest" \
  --arin "$registry_dir/delegated-arin-extended-latest" --lacnic "$registry_dir/delegated-lacnic-latest" \
  --ripencc "$registry_dir/delegated-ripencc-latest" \
  --output geoip_RU_BY_KZ_rir_registered_prefixes.tsv --stats geoip_RU_BY_KZ_rir_stats.txt \
  --as-of "$reference"
```

The option is not an age-check bypass. Every file still has to pass the same
window relative to that reference. A future reference is rejected. New audit
reports carry both the actual generation timestamp and the freshness reference.
The option only addresses RIR age validation. The source revision, other
archived inputs and original build tools are still required to reproduce a
complete routing build.
