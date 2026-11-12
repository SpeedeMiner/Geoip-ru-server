# GeoIP v41 independent candidate comparison — 2026-11-12

**Status: built and independently checked; Draft PR, not published.**

## Immutable evidence

- PR: https://github.com/SpeedeMiner/Geoip-ru-server/pull/13
- Branch: `feature/geoip-direct-rukzby-v41-integration`.
- v41 CI: https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43213336816, build commit `c787ac889e2a7b5f97d3b6fef158f82b21c7f9da`, SUCCESS.
- v41 GitHub Actions artifact ID `13941149919`, zip SHA-256 `c400bc19ae6d232c3bd4b1ac79c6754ca6473255c83e795ab2721bda4e0f7b23`.
- `geoip_RU.dat` SHA-256 `7d55f2bc59919052222850abd1fd1bba79e4a73d049799367122596a796ab2db`, size 2,097,353 bytes.
- Corrected v39 comparator: https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43198572988, `geoip_RU.dat` SHA-256 `b2cb548e01668eaddb85f90db19b5aa1a4af0fcaa0970f9427ba11d8f4e77d30`.
- v41 build passed 88 Python tests plus Go builder tests and final independent v41 readback/protobuf verification.

## Effective blocked source classification

| Policy measurement | Manifest count |
| --- | ---: |
| Original approved union | 199,640 CIDRs |
| Hard/exact including unclassified v38 baseline | 57,694 CIDRs |
| Resolver-only after removing hard overlap | 80,755 CIDRs |
| Effective v41 blocked-set | 125,707 CIDRs |
| Total blocked addresses retained in DIRECT by policy | 2,205 IPv4 |
| CORE_CORPORATE subset of exemptions intersecting DIRECT | 28 IPv4 |
| SHARED_INFRA resolver-only subset intersecting DIRECT | 411 IPv4 |

These are *not* mutually exclusive source coverage counts; CIDRs may overlap and collapse to different canonical lengths. Historical resolver-only classification requires exact pinned-v38 host-IP source evidence. Unclassified or wider historic prefix records stay hard. All prior approved block addresses remain in the union.

## Exact address-space difference

Parsed both protobuf binaries to exact CIDR intervals and subtracted their address ranges in both directions, rather than comparing CIDR string counts.

| Category / family | v39 addresses | v41 addresses | Added in v41 | Removed from v39 |
| --- | ---: | ---: | ---: | ---: |
| RU IPv4 | 53,105,933 | 53,100,808 | 0 | 5,125 |
| RU IPv6 | 1,205,559,204,658,091,812,677,163,847,516,160 | 1,205,559,204,658,091,812,677,163,847,516,160 | 0 | 0 |
| PRIVATE IPv4 | 592,708,862 | 592,708,862 | 0 | 0 |
| PRIVATE IPv6 | 4,325,545,831,231,176,725,068,219,651,071,148,031 | 4,325,545,831,231,176,725,068,219,651,071,148,031 | 0 | 0 |

All 5,125 IPv4 addresses removed from v39 DIRECT are covered by the v41 effective block list: **0 unexplained removals**. IPv6/RU/PRIVATE are unchanged in exact address space; differing CIDR row totals are due to canonical splitting, not missing addresses.

## Unresolved release blockers

1. Independent v37 priority-prefix audit still expects exactly 56 prior rows, but current pinned production inputs produce 57. Do not change constants without inspecting exact additional prefix and provenance.
2. Validate attribution and first-party/shared classification for all 49 corporate ASN entries. RIR-RU origin association is not automatic corporate ownership.
3. Candidate and release workflows must not be merged blindly: v41 only accepts PR or manual trigger and does not publish from this branch; the legacy v39 production scheduler must be explicitly retired before any v41 production activation.
4. No tags, GitHub Release assets, CDN content or `main`/`release` changes are authorized by this report.

## Later correction status (2026-11-12)

Historical run `43213336816` genuinely passed 88 Python tests at that commit. The earlier 57-versus-56 audit blocker is reported fixed in the newer candidate, and a local reviewer reports 92 passing tests. Neither statement establishes a successful GitHub Actions run for the latest v41 branch head.

Branch-only corrective commits: `3b953bb` (interval-safe blocked provenance), `d23846f` (workflow paths and link), `d5890a3` (49-row root ASN registry). No changes to the released GeoIP binaries were made by those commits.
