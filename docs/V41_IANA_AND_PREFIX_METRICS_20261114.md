# 2026-11-14 — Fix IANA CSV normalization and ASN address counts

- Independent follow-up to the full v41 audit. The IANA parser now handles comma-separated CIDRs and numeric footnotes. Unknown reachability is not treated as globally unreachable. Classified rows must contain valid canonical prefixes in their expected family.
- Corporate class metrics now measure the union per address family instead of counting overlapping rows twice. Exact prefix/origin records and class precedence are unchanged. Tests exercise both IPv4 and IPv6 overlaps.
- Uses the production baseline `596c93df` separately from PR #35. No direct edits to main, release, W1ZARDZ or PR #5. The frozen inputs restore three IANA IPv4 records that were previously skipped.
