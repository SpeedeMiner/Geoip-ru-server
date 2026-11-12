# v41 P1 — AS8342 exact-host manual evidence docket (2026-11-12)

**Scope:** eighteen current `antifilter-ip.lst` exact IPv4 hosts with W1ZARDZ broad-only DIRECT protection under `81.177.128.0/20`. These are **18 host addresses**, **not** eighteen fully blocked subnetworks, and the surrounding `81.177.128.0/19` is **not approved** for wholesale exclusion.

## Independent corroboration and limitations

- RIPE RIS snapshot in PR #16 audit already observed `AS8342` origin and covering `81.177.128.0/19` for the 18 exact hosts. This corroborates BGP origin, **not** current RKN blocks or owner of a particular hosted site.
- BGP cross-check: https://bgp.he.net/AS8342 and https://ipregistry.co/AS8342/81.177.128.0/19 support the announced covering network and network operator **JSC RTComm.RU**. The underlying hosting company may differ from the BGP AS registrant.
- IPinfo snapshot https://ipinfo.io/81.177.135.38 reports hostname `srv34-h-st.jino.ru`, Avguro Technologies shared hosting and approximately **1,537** hosted domains. Its page's June 2026 observation is **not** current November 2026 verification.
- IPinfo snapshot https://ipinfo.io/81.177.139.64 reports hostname `srv73-h-st.jino.ru`, Avguro Technologies shared hosting and approximately **1,099** hosted domains (June 2026 page observation). Neither source proves that any *specific* listed domain is under an active IP block.
- Published Antifilter https://antifilter.network/ip explicitly notes sources include RKN list mirrors **and DNS lookups of blocked domains**; https://antifilter.download/ describes the separate DNS-derived lists. Therefore `antifilter-ip.lst` provenance is not equivalent to a signed, dated, official RKN IP-specific notice.
- The 18 `w1zardz-service-direct` matches are aggregate provider policy signals, not evidence that all 18 hosts belong exclusively to one specific first-party service.

## Exact host verification docket

| Exact host | BGP observed origin | DIRECT protection | Independent host-level evidence | Routing decision |
|---|---|---|---|---|
| `81.177.135.2/32` | AS8342 | W1ZARDZ broad-only | No separately verified host-level tenancy | UNRESOLVED |
| `81.177.135.38/32` | AS8342 | W1ZARDZ broad-only | IPinfo: ~1,537 hosted domains; Jino/Avguro | UNRESOLVED |
| `81.177.135.51/32` | AS8342 | W1ZARDZ broad-only | No separately verified host-level tenancy | UNRESOLVED |
| `81.177.135.125/32` | AS8342 | W1ZARDZ broad-only | No separately verified host-level tenancy | UNRESOLVED |
| `81.177.135.126/32` | AS8342 | W1ZARDZ broad-only | No separately verified host-level tenancy | UNRESOLVED |
| `81.177.135.185/32` | AS8342 | W1ZARDZ broad-only | No separately verified host-level tenancy | UNRESOLVED |
| `81.177.135.211/32` | AS8342 | W1ZARDZ broad-only | No separately verified host-level tenancy | UNRESOLVED |
| `81.177.136.113/32` | AS8342 | W1ZARDZ broad-only | No separately verified host-level tenancy | UNRESOLVED |
| `81.177.139.64/32` | AS8342 | W1ZARDZ broad-only | IPinfo: ~1,099 hosted domains; Jino/Avguro | UNRESOLVED |
| `81.177.139.151/32` | AS8342 | W1ZARDZ broad-only | No separately verified host-level tenancy | UNRESOLVED |
| `81.177.139.247/32` | AS8342 | W1ZARDZ broad-only | No separately verified host-level tenancy | UNRESOLVED |
| `81.177.140.28/32` | AS8342 | W1ZARDZ broad-only | No separately verified host-level tenancy | UNRESOLVED |
| `81.177.140.54/32` | AS8342 | W1ZARDZ broad-only | No separately verified host-level tenancy | UNRESOLVED |
| `81.177.140.147/32` | AS8342 | W1ZARDZ broad-only | No separately verified host-level tenancy | UNRESOLVED |
| `81.177.140.201/32` | AS8342 | W1ZARDZ broad-only | No separately verified host-level tenancy | UNRESOLVED |
| `81.177.141.15/32` | AS8342 | W1ZARDZ broad-only | No separately verified host-level tenancy | UNRESOLVED |
| `81.177.143.54/32` | AS8342 | W1ZARDZ broad-only | No separately verified host-level tenancy | UNRESOLVED |
| `81.177.143.55/32` | AS8342 | W1ZARDZ broad-only | No separately verified host-level tenancy | UNRESOLVED |

All 18 have current `ip.lst` evidence, no additional narrow service /`32` match in the previous P1 audit, and are assigned **P1_BROAD_ONLY**. `UNRESOLVED` signifies **no routing action authorized**.

## Required evidence before deciding any one address

1. Date-stamped IP-level evidence that the **particular IP** is an active blocked destination; do not infer from the IP resolving from a blocked domain or appearing in `ip.lst`.
2. Independent contemporaneous hosted-domain/hostname or service confirmation for the same IP, particularly where shared-hosting indicates other legitimate websites may be collateral damage.
3. Exact /`32` impact review: compare routing for the IP and neighboring IPs; never carve the whole /`19` or /`20` because the folder groups 18 hosts.
4. A recorded explicit per-host decision and reviewer. Missing/ambiguous evidence leaves existing production policy unchanged.

**Status:** evidence docket only. No first-party service or live block adjudication was performed; all 18 remain **UNRESOLVED**. This is not a proposed allowlist/blocklist change. Source facts from 2026-11-12 reproducible CI and external pages cited above.

Production `main`, `release`, tags, and PR #5 remain untouched.
