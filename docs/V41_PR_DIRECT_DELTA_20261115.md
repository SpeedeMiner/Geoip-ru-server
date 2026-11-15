# v41 PR DIRECT delta checkpoint — 2026-11-15

The build's absolute DAT check previously called the relative validator with the candidate as both arguments. This change uses an explicit absolute-only mode. Pull-request builds additionally resolve `release` once, read the DAT and its SHA-256 sidecar from that exact Git commit, and verify the candidate DAT and reviewed IPv6 table against the candidate policy manifest.

The advisory `geoip-v41-direct-delta` artifact contains exact IPv4 and IPv6 additions and removals in DIRECT, including reviewed IPv6 policy rows separately from unmatched removals. The summary warns on unmatched IPv6 removals of any size. That signal requests investigation and does not establish that a route was withdrawn or a service failed. A missing or invalid baseline is reported as unavailable, not as a zero delta.

Replay evidence at main `fab8870dd14e0dcad217fd60f5c5b86d3713609a`:

- `79bddd4c` → `58ca38fe`: zero IPv4 and IPv6 DIRECT delta, PRIVATE unchanged. Both DAT files have SHA-256 `b17fe26ccdcb8d272e6233ec9686a514b309e9d75e75653313a75f329b70fae7`.
- `a23b381e` → `47f4d3ee`: −262 IPv4; reviewed removal of four IPv6 /48s and no unmatched IPv6 removal. The compact coverage represents the adjacent `63f0` and `63f1` /48s as one /47, while the report keeps the four original policy rows.
- Fixtures cover an unmatched /128, partial policy overlap, a PRIVATE change, bad baseline checksum, unbound policy evidence and attempted re-admission of a reviewed prefix.

Publication gates, reviewed SHA override semantics and the three-file CDN contract are unchanged. Draft PR #44 remains the broader audit record. A production threshold or a live-origin attribution check is not introduced here.
