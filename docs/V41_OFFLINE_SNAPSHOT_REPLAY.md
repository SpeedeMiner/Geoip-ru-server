# Verify the inputs and client output of an offline v41 replay

Use `.github/scripts/verify_v41_snapshot_replay.py` with Python 3.10+ on Linux
and a local Git installation. It does not fetch files, build a release, or
publish anything. It verifies **local** snapshot inputs and the six local
client files. It does not approve the routes contained in those files or
validate a fresh report against the text of a historical audit.

## Verify and restore the build inputs

1. Resolve the versioned snapshot tag to the independently trusted release
   commit. Get the release manifest from that pinned Git commit and verify
   that its SHA-256 matches the manifest in the versioned release download.
   A hash supplied only by the same download is not an independent pin.
2. Download the four archives and provenance TSV to a local directory
   (`$INPUTS`). Use the exact file names below. Do not use rolling aliases
   such as `latest` or `release` as input identities.

   - `as-ip-blocks.tar.gz`
   - `v41-registry-inputs.tar.gz`
   - `v41-upstream-inputs.tar.gz`
   - `v41-block-inputs.tar.gz`
   - `geoip_RU_input_provenance.tsv`

3. Run from a checkout containing the tool. Supply a local repository
   (`$SOURCE_REPO`) holding the original source commit listed in the pinned
   manifest. Supply a **new** destination outside both input and source
   directories, with an existing parent.

```bash
python3 .github/scripts/verify_v41_snapshot_replay.py \
  --manifest "$MANIFEST" --manifest-sha256 "$MANIFEST_SHA256" \
  restore-inputs --inputs "$INPUTS" --source-repo "$SOURCE_REPO" --output "$WORK"
```

The tool checks the current v41 manifest schema, verifies all five input
sizes and digests, and reuses the existing archive/provenance validators. It
gets the upstream catalog from the exact local Git object even if the working
tree differs. It refuses Git transports, existing destinations and duplicate
output names across archives. On success, stdout is JSON with the exact
source and restored file names. The public production snapshot
`geoip-v41-snapshot-43747743430.1` restores 38 files. Its pinned release
commit is `e20cf733a13d92040134895ebd580b7c9060fa3b`, source commit is
`c0d2a01ba1fb5f5c0e48965d614945348083a900` and exact manifest SHA-256 is
`628a40ddce0118c47dce1b1e9a1b2028868caeb88a69946e837e6d4cac2c6d19`.

## Compare a local replay against the pinned client files

Build using the historical source commit, its pinned toolchain, and the
original UTC date for the RIR reference checks. This tool does not run the
historical source or binaries itself. For the published example the date
was 2026-11-15. See the
[historical build workflow](https://github.com/SpeedeMiner/Geoip-ru-server/blob/c0d2a01ba1fb5f5c0e48965d614945348083a900/.github/workflows/geoip-v41.yml)
and the [reconstruction procedure](https://github.com/SpeedeMiner/Geoip-ru-server/blob/bfc1e1608b48235f9b8ab776eb02030329d39963/docs/V41_PUBLIC_SNAPSHOT_RECONSTRUCTION_20261116.md).

```bash
python3 .github/scripts/verify_v41_snapshot_replay.py \
  --manifest "$MANIFEST" --manifest-sha256 "$MANIFEST_SHA256" \
  compare-client --replay "$WORK"
```

The comparison prints one JSON row per file with expected and observed
size and SHA-256, or a read error. Schema 1 covers the historical DAT and two
SRS files with their checksums. Schema 2 also requires the RU MRS and its
checksum and rejects PRIVATE MRS. To regenerate MRS when replaying a schema 2
snapshot, use the pinned compilers and CLI in the [MRS compatibility guide](V41_MIHOMO_MRS_COMPATIBILITY.md).
Exit 0 means all required files match. Exit 1 means at least one client file did
not match or could not be read. Exit 2 means invalid manifest, malformed
invocation, or unsuccessful restore. Failure does not replace existing
files. A fresh quality report and policy manifest can have different
generation timestamps even when all client files match.
