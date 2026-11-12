# v41 audit — Yandex Cloud 17 exact P1 broad-only hosts (2026-11-13)

**Read-only independent evidence docket.** CI release asset: [post-release monitor #43286790758](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43286790758); earlier RIPE RIS origin audit [#43276315363](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43276315363). All source assets were checked by the pinned-release audit. No changes to GeoIP, routing policy, release, or production.

## Main finding: Yandex corporate service versus Yandex multi-tenant cloud

**Official cloud evidence:** [Yandex Cloud — Public IP address ranges](https://yandex.cloud/ru/docs/vpc/concepts/ips) (last updated **2026-10-02**) explicitly lists **`158.160.0.0/16`** among Virtual Private Cloud public IPv4 networks. It states that these networks support resources belonging to **different services and customers**, including virtual machines, databases, NAT instances, and load balancers. Therefore neither an `AS200350` BGP origin nor a Kyoresuas «Яндекс» catalogue record at `/16` proves that an **individual IP is a first-party Yandex service host**. Do not silently treat a cloud customer IP as a verified first-party host.

**Independent routing evidence:** archived RIPE RIS audit observed **all 17** exact hosts announced with covering prefix `158.160.0.0/16` and origin `AS200350`. The RIPE/route registry corroborates the origin (see [ipregistry](https://ipregistry.co/AS200350/158.160.0.0/16)), not the customer of each IP.

**Block-source limitations:** [Antifilter documentation](https://antifilter.network/ip) describes `ip.lst` as a mixture of registry-list mirrors **and DNS resolution of blocked domains**; `ip.lst` presence does not by itself verify a current official IP-specific ban. Among the 17, **16** also retain v38 historical hard provenance and **one** has current-only source evidence; all 17 are current `antifilter-ip.lst`.

## Exact address review queue

| Exact IP | RIS BGP origin / covering route | Existing hard evidence | Broad DIRECT protection | Decision |
|---|---|---|---|---|
| `158.160.13.236/32` | AS200350 — `158.160.0.0/16` | current `antifilter-ip.lst` | Kyoresuas «Яндекс» + Escapingworm `/16` | UNRESOLVED |
| `158.160.94.242/32` | AS200350 — `158.160.0.0/16` | current `antifilter-ip.lst` | Kyoresuas «Яндекс» + Escapingworm `/16` | UNRESOLVED |
| `158.160.109.94/32` | AS200350 — `158.160.0.0/16` | current `antifilter-ip.lst` | Kyoresuas «Яндекс» + Escapingworm `/16` | UNRESOLVED |
| `158.160.116.191/32` | AS200350 — `158.160.0.0/16` | current `antifilter-ip.lst` | Kyoresuas «Яндекс» + Escapingworm `/16` | UNRESOLVED |
| `158.160.116.199/32` | AS200350 — `158.160.0.0/16` | current `antifilter-ip.lst` | Kyoresuas «Яндекс» + Escapingworm `/16` | UNRESOLVED |
| `158.160.139.27/32` | AS200350 — `158.160.0.0/16` | current `antifilter-ip.lst` | Kyoresuas «Яндекс» + Escapingworm `/16` | UNRESOLVED |
| `158.160.140.116/32` | AS200350 — `158.160.0.0/16` | current `antifilter-ip.lst` | Kyoresuas «Яндекс» + Escapingworm `/16` | UNRESOLVED |
| `158.160.142.52/32` | AS200350 — `158.160.0.0/16` | current `antifilter-ip.lst` | Kyoresuas «Яндекс» + Escapingworm `/16` | UNRESOLVED |
| `158.160.145.13/32` | AS200350 — `158.160.0.0/16` | current `antifilter-ip.lst` | Kyoresuas «Яндекс» + Escapingworm `/16` | UNRESOLVED |
| `158.160.171.31/32` | AS200350 — `158.160.0.0/16` | current `antifilter-ip.lst` | Kyoresuas «Яндекс» + Escapingworm `/16` | UNRESOLVED |
| `158.160.189.160/32` | AS200350 — `158.160.0.0/16` | current `antifilter-ip.lst` | Kyoresuas «Яндекс» + Escapingworm `/16` | UNRESOLVED |
| `158.160.204.146/32` | AS200350 — `158.160.0.0/16` | current `antifilter-ip.lst` | Kyoresuas «Яндекс» + Escapingworm `/16` | UNRESOLVED |
| `158.160.217.206/32` | AS200350 — `158.160.0.0/16` | current `antifilter-ip.lst` | Kyoresuas «Яндекс» + Escapingworm `/16` | UNRESOLVED |
| `158.160.225.86/32` | AS200350 — `158.160.0.0/16` | current `antifilter-ip.lst` | Kyoresuas «Яндекс» + Escapingworm `/16` | UNRESOLVED |
| `158.160.227.3/32` | AS200350 — `158.160.0.0/16` | current `antifilter-ip.lst` | Kyoresuas «Яндекс» + Escapingworm `/16` | UNRESOLVED |
| `158.160.230.192/32` | AS200350 — `158.160.0.0/16` | current `antifilter-ip.lst` | Kyoresuas «Яндекс» + Escapingworm `/16` | UNRESOLVED |
| `158.160.230.238/32` | AS200350 — `158.160.0.0/16` | current `antifilter-ip.lst` | Kyoresuas «Яндекс» + Escapingworm `/16` | UNRESOLVED |

**Distribution:** 17 exact IPs in **11 distinct `/20`** and **15 distinct `/24`** bins. `158.160.224.0/20`: 4; `158.160.128.0/20`: 3; `158.160.112.0/20`: 2. The largest `/24` bins contain only two reviewed IPs each (`158.160.116.0/24`, `158.160.230.0/24`). These are indexing groups, not blocked prefixes.

## Required proof for IP-specific decisions

1. Independently verifiable, dated evidence of a **current IP-specific** block (not only current `ip.lst` membership or DNS resolution from a blocked domain).
2. Evidence of the **actual service/customer and endpoint** using that exact address at the relevant date; a public cloud ASN and a generic catalogue «Яндекс» label are insufficient.
3. Collateral-impact assessment: shared VPC address, NAT, and load-balancing use may make blanket prefix actions harmful to unrelated clients.
4. Reviewer-signed resolution for each `/32` only. Until that evidence exists, mark **UNRESOLVED** and change neither DIRECT nor blocked masks.

**Policy proposal for a separate future review, not applied:** distinguish dedicated Yandex first-party services from `AS200350` SHARED Cloud customer space when assigning protection precedence. This requires positive per-service evidence and tests; it is not authorization to block an entire `/16`.

PR #16 remains **Draft**, dedicated to audit only. PR #5, main, release and production unaffected.
