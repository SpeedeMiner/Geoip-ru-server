# v41 audit — observed IPv6 changes in 20 published release commits

Reviewed the full retained first-parent `release` history from `0ef5d68d` to `79bddd4c` (13–15 November 2026, UTC). The 20 commits have 12 distinct DAT hashes but only **five distinct IPv6 DIRECT address sets**. Four of 19 adjacent transitions change IPv6 DIRECT. IPv6 PRIVATE is unchanged in all 19 transitions.

| Published transition | Exact IPv6 DIRECT delta | Evidence |
| --- | --- | --- |
| `7c5112ec` → `2ef8fb66` | +`2001:ad0:2000:1::/64` | The exact AS3327 /64 first appears in the manifest-bound reviewed operator table. ipverse already contained the wider /32 on both sides. Neither the wider /32 nor the /48 was added by this transition. |
| `f90d9939` → `1192d658` | −`2a0b:4e07:63f0::/48`; −`2a10:ccc1:1338::/47` | The old selected origins and base covered both. The AS218750 and AS213461 ranges both disappear from ipverse and the selected-origin input. Hydra is byte-identical and covers neither range. No overlap with the new hard/effective masks, PRIVATE, reviewed operator table or regional RIR inventory. This is consistent with upstream origin loss, not a controlled rebuild. |
| `7eef1efc` → `a23b381e` | +`2a0b:4e07:63f0::/48` | The parent /47 returns to AS218750 in the retained ipverse archive and selected-origin inventory. The new v37 base covers the /48. Hydra changed elsewhere but covers none of this /48 in either build. |
| `a23b381e` → `47f4d3ee` | −`2a0b:4e07:6300::/48`, −`2a0b:4e07:6310::/48`, −`2a0b:4e07:63f0::/47` | Exact address union of the **four** reviewed AS218750 /48 exclusions. The /47 is just the canonical encoding of the adjacent `63f0` and `63f1` /48s. The archive, base and Hydra bytes are unchanged and selected-origin coverage remains. Both neighboring /48s, `6301` and `63ff`, are fully retained. |

The first loss of `63f0::/48` and its later approved removal are not two independent examples of unexplained deterioration: it returned between them, then was removed for a distinct policy reason. The final IPv6 DAT still covers the Moscow `2001:ad0:2000:1::/64` and both protected neighbors. AS213461's observed IPv6 family loss is a separate case outside the 59-ASN watchlist used in the earlier historical audit. Its observed IPv4 `185.162.235.0/24` remains in all three dated ipverse observations. Absence in ipverse is not proof of a live BGP withdrawal, endpoint unreachability, or current location.

## Verification and limits

- [Exact machine evidence](V41_AUDIT_PHASE_D_IPV6_RELEASE_HISTORY_20261115.json.gz), SHA-256 `e730cf083c56d1e59e1265315a42986a17baffc81d270d041c0b2f4d9c8036de`. Includes all 20 release commit IDs, DAT, ipverse and Hydra hashes, plus exact before/after intersections per changed IPv6 CIDR. Each DAT matches the manifest and checksum at its pinned release commit. There are no live source substitutions.
- Rechecked all 19 RU and PRIVATE comparisons with a second DAT decoder and independent IPv6 endpoint sweep. Hard, effective, RIR, selected-origin and reviewed operator bytes used for attribution were matched to retained digests. For the reviewed IPv6 exclusion, also verified the table's hash and exact manifest rows. For the three targeted ASNs the archive-member hashes and exact matching aggregated prefixes are recorded.
- The successor v37 base DAT for `1192d658` was not retained locally under its expected SHA-256 `2b83b50081362fe0035c10fe256506219f1b8f283fdc1794633819b6fad88cbf`. That layer is explicitly unknown there. Do not substitute the later base DAT or claim a complete same-input A/B reconstruction.
- Keep IPv6 reporting in CIDRs and exact address space with treatment of reviewed exceptions separate. A generic threshold based on the largest previous change would mix one approved change with a coincident upstream change. Do not promote it to a blocking threshold from this sample.

Related evidence: [reviewed IPv6 exclusions](V41_IPV6_ADMISSION_JOURNAL_20261115.md), [Moscow /64 admission](V41_EXECUTION_JOURNAL.md#2026-11-13--moscow-ipv6-pop-candidate), and [14-day watched ASN history](V41_AUDIT_PHASE_D_IPVERSE_HISTORY_20261115.md).
