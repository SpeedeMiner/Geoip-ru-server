# GeoIP v41 reconstruction from the public versioned snapshot

This is an offline reconstruction and diagnosis handoff, not a publication workflow. It does not assume a versioned release is immutable at the service layer. Pin its Git commit and manifest SHA-256 as well as the tag name.

| Identity | Verified value |
| --- | --- |
| Release tag | `geoip-v41-snapshot-43747743430.1` |
| Release data commit | `e20cf733a13d92040134895ebd580b7c9060fa3b` |
| Builder source commit | `c0d2a01ba1fb5f5c0e48965d614945348083a900` |
| Original UTC reference date for RIR freshness | `2026-11-15` |
| Exact published release manifest SHA-256 | `628a40ddce0118c47dce1b1e9a1b2028868caeb88a69946e837e6d4cac2c6d19` |
| Published DAT SHA-256 | `b17fe26ccdcb8d272e6233ec9686a514b309e9d75e75653313a75f329b70fae7` |
| Known disputed DAT SHA-256 | `3161fdd5eda4d9c2f962a3c8d1bd0c187e5cab9260284a13679b289a9a6d0855` |
| Draft #53 SHA / table SHA-256 | `92fa97e13317db01ca43aad31386d091eb249a2a` / `aeb438051a38f079a8e98c12fe51c8c328767d6671cb887ab8f3a0ea15a75fff` |

## Download, verify, restore

1. Use the [versioned GitHub snapshot](https://github.com/SpeedeMiner/Geoip-ru-server/releases/tag/geoip-v41-snapshot-43747743430.1). Verify that the Git tag resolves to the release commit in the table. Read the manifest from that commit on GitHub Raw and from the versioned release URL. Require both to match the fixed digest.
2. Download all four archives and `geoip_RU_input_provenance.tsv`. Require exact sizes and hashes from the fixed manifest. Download the original client binaries and audit files separately for comparison only. Do not feed previously generated outputs into the reconstruction.
3. With the exact source checkout, restore the three internal bundles with the checked-in verifier. Each command takes a new output directory. Verify the ipverse archive separately. The commands below assume `SRC` and `INPUTS` are absolute paths and they have already passed steps 1–2.

```bash
set -euo pipefail
test -d "$SRC/.github/scripts"
test -d "$INPUTS"
WORK="$(mktemp -d)"
restore="$SRC/.github/scripts/bundle_v41_registry_inputs.py"
provenance="$INPUTS/geoip_RU_input_provenance.tsv"

python3 "$restore" restore "$provenance" "$INPUTS/v41-registry-inputs.tar.gz" "$WORK/registries"
python3 "$restore" --upstream-catalog "$SRC/.github/data/v41-upstream-sources.json" \
  restore "$provenance" "$INPUTS/v41-upstream-inputs.tar.gz" "$WORK/upstream"
python3 "$restore" --block-inputs \
  restore "$provenance" "$INPUTS/v41-block-inputs.tar.gz" "$WORK/block"
python3 "$SRC/.github/scripts/verify_v41_ipverse_archive.py" \
  --provenance "$provenance" --archive "$INPUTS/as-ip-blocks.tar.gz"
```

4. Copy the restored regular files into a new work directory, refusing duplicate names. Add only the verified ipverse archive and provenance. The snapshot yields 38 files before generated sidecars. Supply `.github` from the pinned source checkout, never from a later branch head. Compile the v37 builder with the pinned Go toolchain after `go mod verify`, `go test -mod=readonly ./...`, and `go build -mod=readonly -buildvcs=false`. Go 1.26.10 linux/amd64 archive SHA-256 is `ccfe7ae822d2c2f41f4fe7c956199967a4dac22d0ee0d2b2bfdb440aab3b20c5`. Module identities are pinned by `go.sum`.
5. Follow the build job from the [exact source workflow](https://github.com/SpeedeMiner/Geoip-ru-server/blob/c0d2a01ba1fb5f5c0e48965d614945348083a900/.github/workflows/geoip-v41.yml). From the download script, only recreate the company registry sidecar and the generated RIR/IANA inventories. Pass `--as-of 2026-11-15` to both RIR scripts for this historical reconstruction. Run the named ASN extract, block preparation, offline Go/overlay build, independent build/Telegram/IPv6 checks, and archive creation steps. Do **not** run the rolling feeds download step, independent release publication script against remote branches, or any publish job.
6. Compile and decompile the two SRS files using sing-box 1.13.12 linux/amd64 from the [pinned release](https://github.com/SagerNet/sing-box/releases/tag/v1.13.12). Check archive SHA-256 `1540533adb3df24f5ad5f14b5c7ca3dbc2401b10a1c1eb278fcadcada47ec6c4` before use. The DAT, both SRS, sidecars and all retained input hashes should match. The only two asset differences in this reconstruction are the normal generation timestamps in `geoip_RU_quality_report.txt` and `geoip_RU_v41_manifest.json`. Consequently a freshly generated release manifest also differs. A separate comparison-only projection using the original two timestamps reproduced all assets and the old release manifest. Never use that projection to present fresh audits as historical, or to publish a new release.

## Compare a currently served DAT with the fixed reference

The [validator in Draft #53](https://github.com/SpeedeMiner/Geoip-ru-server/blob/92fa97e13317db01ca43aad31386d091eb249a2a/.github/scripts/validate_v41_publication_review.py) accepts a local candidate, reference and table. Point it at a verified copy of the **fixed** clean DAT above for forensic comparison rather than fetching a mutable baseline in the same command. The production draft still compares against the current rolling release, which is correct for its narrower purpose.

- A SHA matching the verified snapshot identifies that exact artifact.
- A SHA matching the known disputed fingerprint identifies the exact observed candidate. Reference comparison also reports the five losses and two watched additions.
- Any other SHA remains unclassified until its provenance, full deltas, and publication state have been checked. `PASS` means no directional change covered by the seven rows, not approval. A different DAT that adds only one unrelated IP is a verified example of `PASS` plus unknown identity. A different DAT that loses an overlapping /25 is a verified example of `HOLD`. An unreadable DAT is an error.
- Compare the client downloads, pinned Git ref and catalog separately. An old jsDelivr metadata digest does not imply wrong bytes on all verified file downloads. This procedure neither purges caches nor changes routing.

The reverse direction was tested against a disposable repository whose rolling ref contained the disputed DAT, including a rehearsal with freshly generated audit files and a new local run identity. The successful rehearsal did not depend on substituting the two historical timestamps. The recovered clean files passed #53's preflight and the local stages of tag and Git ref promotion using simulated versioned downloads. This did not exercise the GitHub Release API, hosted runner permissions, the rolling download update, or CDN repair. The existing versioned download and its checksums remain the verified fallback. Make no production recovery decision based solely on the local exercise.

[Reconstruction and fingerprint evidence](V41_PUBLIC_SNAPSHOT_RECONSTRUCTION_EVIDENCE_20261116.json) · [Publication-readiness handoff](V41_PUBLICATION_READINESS_20261116.md).
