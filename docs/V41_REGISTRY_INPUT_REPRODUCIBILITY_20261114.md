# v41 original registry inputs and reproducibility

## What is already reproducible

The November 14 audit downloaded 59 rolling assets and four versioned
assets. All 63 match the Release API's sizes and SHA-256 values. The
50 distinct files in the pinned Git tree independently match their Git
blob IDs and the same-name rolling files.

The draft #31 and #32 source tree also rebuilt the current production
v37 base and v41 output from Go 1.26.10 and frozen inputs. The results
are exact for all 26 checked files, including the v37/v41 binaries,
effective block mask and provenance sidecars. The run reused the
published, exact **derived** RIR tables, not four unavailable raw
delegated-stat snapshots. It independently rebuilt IANA tables,
ipverse selection, company classes and the block inputs.

The four unavailable raw files are not interchangeable with the older
snapshots. The older inputs regenerate the same regional RIR table,
RU prefix table and BY/KZ ASN registry, but the RU ASN registry differs
by three additions and two removals in the current release. This is a
registry change, not by itself a routing-coverage claim.

## Optional follow-up, separate from PR #32

The production Actions ZIP for run 43587602958 does not contain the
five original RIR files or the two IANA CSVs. PR #32 fixes the exact
ipverse retention path but does not retain those seven inputs.

The audit prototype `docs/tools/bundle_v41_registry_inputs.py` verifies
the same seven names, raw size and SHA-256 against the original build's
provenance. It creates a deterministic gzip tar on the same compression
runtime and verifies the archive before restoring only those seven files
to a new directory. It never writes to Git refs or GitHub Releases.

```sh
python3 docs/tools/bundle_v41_registry_inputs.py create \
  geoip_RU_input_provenance.tsv original-registry-inputs v41-registry-inputs.tar.gz
python3 docs/tools/bundle_v41_registry_inputs.py verify \
  geoip_RU_input_provenance.tsv v41-registry-inputs.tar.gz
python3 docs/tools/bundle_v41_registry_inputs.py restore \
  geoip_RU_input_provenance.tsv v41-registry-inputs.tar.gz restored-registry-inputs
python3 -m unittest discover -s docs/tools -p 'test_bundle_v41_registry_inputs.py'
```

This prototype produced a 4,811,374-byte archive from an older verified
28,412,425-byte corpus. Two independent creates produced identical
bytes, restoration reproduced every input, and checking the old archive
against the current provenance correctly failed. Neither the bundle nor
that earlier provenance is a substitute for the current production inputs.

If long-term raw rebuildability becomes a release requirement, add a
dedicated build-time bundle for the seven registry inputs. Keep the
first integration in candidate CI and measure storage before choosing
retention. The existing 30-day candidate retention helps with immediate
reproduction but does not guarantee a future historical replay. A
versioned snapshot asset is the durable option. Keep it out of rolling
Git history and rolling download URLs. A future reader should check
the hash and size from the exact release commit and verify the original
file-level provenance after extraction. Avoid making new registry
archives a prerequisite for existing legacy releases or changing
published tags.

Treat this as a separate scoped change after #32. The production
workflow, routing data and both drafts remain untouched by this audit.
