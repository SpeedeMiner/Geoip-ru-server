# v41 reviewed Antifilter ip.lst hosts

The production default remains hard for current `antifilter-ip.lst` entries. This narrowly scoped rule classifies that source as resolver-only for the exact IPv4 /32 entries in `.github/data/v41-reviewed-ip-list-hosts.txt`. It does not introduce absent hosts, remove other hard labels, bypass an effective hard covering prefix or change the approved union. It does not disable the existing PRIVATE, resolver-mask or hard-block precedence.

## Evidence and limits

- [Antifilter Download](https://antifilter.download/) documents `ip.lst` as DNS-derived.
- Reviewed against the named v41.3 release and GitHub Actions run 43397060646, artifact 14022958658. Published DAT SHA-256: `53d235e89a9255709efd61df5c5f3c98f291398e1f94be448ee12ec24c5fadfd`.
- The 63 hosts matched exact /32 entries in `reestr_resolved4.txt` at [bol-van/rulist f9ea970](https://github.com/bol-van/rulist/tree/f9ea9704544590bf0aff817acc73b7e00261a849). SHA-256: `e4944997ffe85c58af4976899f3c7e35f0ea8904cf9abeeb2f8ec3a197d04a6f`.
- None of the 63 matched the pinned `ipban4` snapshot, the checked public Antifilter.network IP snapshot or the checked Digne category, even by covering CIDR in the two IP lists. They are not asserted to be reachable or absent from an authoritative current registry. No BGP `65444:210` snapshot was obtained.
- The 23 hosts with a conflicting exact IP signal, including the earlier seven, are excluded from the reviewed file. The other 113 of the 176-host scenario are also excluded.
- Expected fixed-input delta relative to v41.3 is +63/−0 IPv4 in DIRECT with no IPv6 or PRIVATE change. 61 of these IPv4 addresses were already DIRECT in the pinned v34 reference. Expected DAT SHA-256: `bba99f4950140789a3863b2aff4ecade5e0b4d040c13eb5ac3b5bdf927d73315`.
