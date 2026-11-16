# Review queue: five removed IPv4 prefixes

Snapshot comparison only; generated 2026-11-16. This is not a live BGP or RPKI verdict. Each row is an exact /24 that was in published DIRECT and is absent from the candidate DIRECT. The full old and new ipverse archives were scanned for exact /24 occurrences; covering announcements, current route validity and actual operator/service control require independent evidence. Country fields of delegated allocations are not geolocation.

| Prefix | Previous selected origin | Candidate snapshot exact origin | Old ASN registry | Allocation tag | Decision |
|---|---|---|---|---|---|
| 177.29.253.0/24 | AS219306 CURATOR-CDN | AS137410 | RIPE RU | RIPE VG allocation | OPEN: user requested CURATOR-CDN coverage; verify present service control and route before deciding whether to pin |
| 177.122.229.0/24 | AS219216 | AS137410 | RIPE RU | RIPE VG allocation | OPEN: verify current service/control and RPKI |
| 177.122.241.0/24 | AS218568 | AS137410 | RIPE RU | RIPE VG allocation | OPEN: verify current service/control and RPKI |
| 177.166.74.0/24 | AS219262 | AS137410 | RIPE RU | RIPE VG allocation | OPEN: verify current service/control and RPKI |
| 177.166.78.0/24 | AS219238 | AS137410 | RIPE RU | RIPE VG allocation | OPEN: verify current service/control and RPKI |

- [Previous production run and retained candidate](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43747743430): DAT SHA-256 `b17fe26ccdcb8d272e6233ec9686a514b309e9d75e75653313a75f329b70fae7`; ipverse SHA-256 `5d3b254a78d4fbbd225d6e18b317a9a29e799f418a6f7b57dbe617b1d1beeb41`.
- [Candidate run and retained artifact](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43809352866): DAT SHA-256 `3161fdd5eda4d9c2f962a3c8d1bd0c187e5cab9260284a13679b289a9a6d0855`; ipverse SHA-256 `84af740b9546cf54448ff0782f5ddc15d458e15b0d2409fcff8de3d5733baa34`.
- ipverse observations can span a rolling observation window and do not establish a time-specific BGP RIB. A changed observation does not prove a hijack, a legitimate transfer, geographic movement, loss of service, or that the earlier prefix is permanently assigned to an ASN. No static pin or policy removal has been made.
- On 2026-11-16 attempts to retrieve live RIPEstat RPKI validation, RIPE database and Cloudflare RPKI validity directly did not return accessible data in the available research environment. RPKI for each prefix and origin is therefore UNKNOWN, not invalid or not-found. The RIPEstat data query should be rerun with the prefix, origin and timestamp once available. Collect independent operator evidence before deciding to add the CURATOR-CDN network back.
