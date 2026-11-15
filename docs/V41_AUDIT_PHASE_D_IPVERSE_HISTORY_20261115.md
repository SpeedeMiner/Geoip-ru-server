# v41 audit — 14 daily ipverse observations, 2–15 November 2026 (UTC)

**The upstream history adds ten useful watched-coverage transitions beyond the four-release replay. It does not add ten historical DAT comparisons.** The samples are daily commits from one upstream, not independent BGP collectors. The final DIRECT comparison uses the same published `79bddd4c51a36a8d3c2771e234e5171f574104c8` DAT for every day.

- 14 daily upstream commits, 12 distinct watched prefix and address-union states, 11 of 13 transitions with an address-space change.
- 24 changed ASN/day/family pairs across nine ASN, all IPv4. Nine of the 24 changes belong to AS9198. There was no watched IPv6 address-space change in this window. No prefix parser rejections. The number of ASN/family pairs with no observed valid prefixes varied from 19 to 21. These are coverage unknowns, not absence claims.
- The per-pair counts sum to +21,760 / −12,800 IPv4 observations across days. These are event counts and may count the same address multiple times. On 8 November AS9198 exchanged 1,792 IPv4 addresses in each direction for a net change of zero.
- **All removed observed IPv4 space in this window remains covered by the fixed current DAT.** That does not establish historical DIRECT or continuous reachability.

| Signal | Exact range | Evidence on the fixed current release |
| --- | --- | --- |
| AS35673 Kaspi Bank, −20% on 3 November | `82.115.37.0/24` | Fully covered by KZ RIR and v37 |
| AS49053 Wildberries, −100% of observed IPv4 on 10 November | `185.62.203.0/24` | Fully covered by RU RIR and v37 |
| AS59840 Alfa-Bank legacy origin, −100% of observed IPv4 on 11 November | `185.154.124.0/24` | Fully covered by RU RIR, v37 and current selected AS15632. AS15632 gained the same /24 in the 12 November upstream observation. |

An ASN percentage threshold alone would flag both 100% losses as severe even though the addresses remain DIRECT. Zero net change can also hide sizable turnover. Keep separate advisory signals for observed-family loss, exact attribution change and verified loss from the final DAT. There is still too little final-DAT evidence to select a blocking threshold, especially for IPv6.

## Reproduction

- [Evidence JSON](V41_AUDIT_PHASE_D_IPVERSE_HISTORY_20261115.json.gz), SHA-256 `439513985a7033198bd70931d711a8f7b492f801f0711071ff8534f58e515fea`. It contains all 14 full Git commit and tree IDs, watched source-member digests, exact CIDRs and candidate DAT SHA-256. Read the original [ipverse Git objects](https://github.com/ipverse/as-ip-blocks/commits/master/) from the pinned range `fe4f41d15447c13105f41208a5e4072af590d7cb`–`54c5fec676bc504d44a09e9d45d0fe578795cbff`. For each commit and watched ASN, use `as/<number>/aggregated.json` when present. The member-set digest is SHA-256 of sorted lines `path<TAB>sha256(raw member)<LF>`. Normalize with the v41 ASN audit parser and compare address unions separately by family and ASN.
- Cross-checked all watched raw members for 13, 14 and 15 November against their respective verified historical release archives, not merely their normalized fingerprints. The historic release path and archive SHA for each anchor are in the evidence JSON.
- Confirmed all 24 changed IPv4 rows with a separate enumerated host-set comparison. This is snapshot attribution and file-membership testing, not a service connection test or a replay of older client DNS or routing rules.
