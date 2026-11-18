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

## Third-party CDN database

[`cdn-ip-database`](https://github.com/mansourjabin/cdn-ip-database) is listed in
`v41-audit-global-networks.json`, not in the required `v41-upstream-sources.json`.
The PR workflow captures `data/resolved_ips.json` once and shares the provider
snapshot across the three reports. The snapshot binds the source URL, fetch
time, byte size and SHA-256. Successful captures also preserve the exact
UTF-8 payload. The collector bounds the download size and time.

- `v41-pr-direct-delta.json` reports exact additions and removals intersecting
  each provider's reported IPv4/IPv6 scopes. Both DATs are compared against the
  same capture, so these counts are DIRECT changes, not provider-feed changes.
- `v41-prefix-candidates.json` reports provider intersections with the entire
  reviewed CIDR, independently of how much of it is in DIRECT.
- `v41-direct-provenance.json` and its TSV distinguish third-party
  `cdn-ip-database/<provider>` scopes from official Cloudflare, AWS and Google
  scopes. The third-party Akamai scope does not replace the existing official
  Akamai entry.

Empty `ips` lists and unreported families mean unknown coverage. A download or
payload error is `UNAVAILABLE`. A missing, legacy or unreadable local snapshot
is `ADVISORY_MISSING` for the CDN appendix. Valid captures can have no matching
scopes, which is different from missing evidence. Individual CIDRs with host
bits are normalized for reporting, with the input-to-network mapping retained.
Literal IPs are reported as exact `/32` or `/128` hosts. The feed's ASN values
are not used to expand any scope.

Provider ranges may overlap and are not additive. A reported intersection
does not establish reachability, ownership, or a reason to change a route.
No CDN database file or overlap result reaches DAT/SRS assembly, masks,
release publication or the CDN branch.
