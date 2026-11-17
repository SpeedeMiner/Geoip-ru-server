# v41 mirror validation and pull-request diagnostics

The production DAT/SRS writer, DIRECT membership rules and publication gates
are unchanged. The required-input downloader validates the Telegram feed,
pinned historical inputs and the complete ipverse archive before accepting
their bytes or recording provenance. Existing RIR, IANA and Antifilter checks
are kept. A single UTC date is used for RIR downloads and both inventories.
An invalid mirror falls through to the next configured mirror.

The PR workflow pins one release commit and verifies its DAT checksum. The
exact IPv4/IPv6 delta, Antifilter comparison, watched ASN report and provider
report use that same commit. The new reports are advisory and run on pull
requests only. They are not added to releases or to the three-file CDN branch.

- **Watched ASNs:** distinguishes observed BGP, selected origin attribution and
  actual DIRECT coverage. If a checksum-bound historic archive is unavailable,
  only the candidate is described. Watchlist entries are not routing rules.
- **Provider/Hydra:** compares both DAT files against the same scoped provider
  feed. The counterfactual without Hydra reapplies the geographic review mask
  without granting Hydra's exception. Historical Hydra attribution and provider
  feed drift remain unknown unless the relevant independent inputs are
  available. An earlier provider capture can be supplied explicitly with
  `--previous-snapshot` for local diagnostics. Missing provider feeds mean
  unknown, not zero coverage. A provider overlap is not evidence of service
  reachability or an instruction to include or exclude an IP.

Both reports bind their inputs and output exact ranges for review. No historical
ZIPs or provider snapshots are required in the source tree. Go and Python tests
also exercise the interval helpers and Python DAT encoding against upstream
v2fly protobuf types.
