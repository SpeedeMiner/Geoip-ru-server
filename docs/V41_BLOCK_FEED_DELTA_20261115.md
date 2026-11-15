# v41 Antifilter exact-delta checkpoint — 2026-11-15 UTC

Base: `fab8870dd14e0dcad217fd60f5c5b86d3713609a` on `main`.
Only PR CI emits the advisory artifact `v41-block-feed-delta-advisory`.
The active feed-count gate, fallback behavior, DIRECT policy and publication paths are unchanged.

## What the report proves

- Validate the block-input archive against the release manifest and its members against input provenance before comparing any raw feed.
- Compare the normalized IPv4 and IPv6 address space of `ip.lst` and `subnet.lst` with the preceding published release, and `ipresolve.lst` with the newest verified live download in the bounded first-parent release history. Emit exact added/removed CIDRs and counts.
- Treat an empty resolver candidate using the pinned v38 approved fallback as degraded. The optional v38 *raw resolver* comparison against the last live feed is distinct from the effective blocked layers and from a live-candidate delta. Unknown or unverified references are not zero deltas.
- Compare hard, resolver-only, effective and final DIRECT address sets against the preceding release. Compare layer/DIRECT intersections separately. Source freshness remains unknown even when the bytes of a download are verified.
- Record DAT/provenance SHA-256 and the pinned comparison release commit. The default search examines up to six release commits and reports verification gaps explicitly.

## Local evidence

- Replay of published snapshot `geoip-v41-snapshot-43739779700.1` against release `58ca38fef851028b51c19f83c7a24c181eaadf97` identified it as the last verified live download. All three raw feeds were identical. Hard, resolver-only, effective, DIRECT and their reported intersections had zero address changes in both families. The snapshot DAT SHA-256 was `b17fe26ccdcb8d272e6233ec9686a514b309e9d75e75653313a75f329b70fae7`.
- An independent retained copy of the older raw feeds, checked against Git-pinned provenance at `a23b381e4844ed4cb84bf67e1f5984027e68769c`, showed that the historical `ipresolve.lst` SHA-256 changed from `6b29a534c362b7f762caaaa70b9fabee0a06464d7a71f96eeb83a2b99b8c91c2` to `8d8d11605a299da96006df6303a90b08b4ae25d35c1d1a199708cb83f84cdf44`. The same 154,198 rows were present in a different order. The exact address-space delta was zero in both families. The older copy predates manifest-bound archives and is not accepted by the automated history search.
- Regression cases cover replacement at identical counts, equivalent split or reordered prefixes, skipped unverified history, recovery after multiple fallback publications, unavailable and downloaded-empty resolver inputs, archive checksum mismatch, and separate layer/DIRECT intersection deltas.
