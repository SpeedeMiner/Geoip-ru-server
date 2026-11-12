# v41 legacy hard-block evidence audit — 2026-11-12

**Scope:** read-only evidence review against SHA-256-pinned published v34 Light and v41 Server binaries and v41 hard/resolver/effective sidecars. Does not alter DIRECT, production or release. Audit workflow run [43267132482](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43267132482) completed successfully.

## Reconciled review queues

| Metric | Result |
|---|---:|
| Historical hard IPv4 /32, with no current `ip.lst` / `subnet.lst` / Telegram hard source | 7,208 |
| Without **current** resolver-only evidence | 6,747 |
| In v34 DIRECT but missing v41 DIRECT | 239 |
| Those 239 without current resolver evidence | **213** |
| Historical hard not in final effective block mask | **9** |
| Among those 9, actually present in published v41 DIRECT | **9** |

All 9 cases must be reviewed as potential *service-protection overrides*, not auto-restored to effective block masks. Within the 239 dropped v34 addresses, 26 still have current resolver-only evidence; the other 213 have neither current hard nor current resolver feed evidence. Their original v38 hard/unclassified classification alone is insufficient to prove a presently active block. However, absence from newer lists does not prove unblocking.

## Historical hard addresses present in final DIRECT

The entries below were independently matched against published candidate origin and service input files (the source hashes are independently pinned by the published v41 manifest). These are prefix intersections, **not an attribution of the exact host's legal ownership**.

| Exact hard legacy IP | Overlapping explicit protection evidence | Origin evidence | Policy issue |
|---|---|---|---|
| `46.254.18.79/32` | Escapingworm `46.254.18.0/23` | `AS210079` origin `46.254.16.0/21` | Operator-wide verified-service protection defeats old hard IP |
| `46.254.18.115/32` | Escapingworm `46.254.18.0/23` | `AS210079` same selected origin | Same as above |
| `81.200.149.9/32` | Escapingworm `81.200.148.0/22` | `AS9123`, **SHARED_INFRA** (Timeweb) | Shared-hosting hard exception via overlapping service route |
| `88.223.91.1/32` | HXEHEX *exact host* `88.223.91.1/32` | No origin assertion here | Exact service-host override; confirm service legitimacy |
| `89.169.161.50/32` | Kyoresuas `89.169.128.0/18` | `AS200350`, **SHARED_INFRA** (Yandex) | Broad cloud prefix overrides historical hard |
| `111.88.151.77/32` | Kyoresuas `111.88.144.0/20` | `AS200350`, **SHARED_INFRA** (Yandex) | Broad cloud prefix overrides historical hard |
| `158.160.63.17/32` | Kyoresuas `158.160.0.0/16` and Escapingworm `158.160.0.0/16` | `AS200350`, **SHARED_INFRA** (Yandex) | Large shared-service mask overrides historical hard |
| `178.248.234.146/32` | Kyoresuas `178.248.232.0/21` | `AS51115`, **SHARED_INFRA** (Qrator) | Shared CDN hard exception through service rule |
| `178.248.236.100/32` | Kyoresuas `178.248.232.0/21` | `AS51115`, **SHARED_INFRA** (Qrator) | Shared CDN hard exception through service rule |

**Important nuance:** the written SHARED_INFRA policy says exact/legacy hard evidence must still apply, *but* a separate verified-service mask takes priority over hard evidence. The six Timeweb/Yandex/Qrator cases above demonstrate that overlapping verified-service broad prefixes can override hard-blocked IPs on shared infrastructure. This is a **policy interaction requiring review**, not necessarily a software error or proof that those hosts are currently blocked. Automatically tightening this behavior could break intentional service routes.

## Proposed evidence-based release gates (not enabled here)

1. Report every case where an original hard exact `/32` is removed from the effective block set and appears in DIRECT; require separate evidence and an explicit approval for broad shared CDN/service masks.
2. Prioritize the 213 previously DIRECT IPs now excluded exclusively by historical unconfirmed hard evidence; compare with fresh authoritative IP/block evidence or sufficiently strong independent sources before considering re-admission.
3. Distinguish current resolver evidence from *historical resolver labels*: membership in an older resolver list must not count as current support.
4. Retain fail-closed existing production behavior until exceptions are reviewed; review-only output must never modify `geoip_RU.dat` or release branch.

## Reproduction

Run `.github/workflows/audit-v41-legacy-hard.yml` on the Draft PR #16 or manually. The workflow downloads five SHA256-pinned release inputs and runs `.github/scripts/audit_v41_legacy_hard_evidence.py`, then uploads:

- `legacy_hard_review.tsv`: 7,208 addresses with current/historical evidence and policy flags
- `priority_v34_losses.tsv`: 239 addresses, including 213 highest-priority unconfirmed hard records
- `legacy_hard_override_review.tsv`: 9 addresses that bypass the effective mask
- `summary.json`: exact deterministic counters

The workflow is read-only and isolated from the production publishing path. PR #5, production and existing release tags remain unchanged.

## Pinned source-level override verification (second-stage audit)

CI [43269113929](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43269113929) **SUCCESS**, artifact `13966064822`, SHA-256-pinned against the published 2026-11-12 v41 service feeds and CORE/SHARED origin sidecars. The new workflow stage exports `nine_legacy_hard_service_overrides.tsv` and `nine_override_summary.json`, listing most-specific and broadest matching prefixes per source.

- Nine legacy hard /`32` addresses are in final v41 DIRECT even though absent from the effective block set.
- Six intersect SHARED_INFRA and a separate verified-service protection feed; **zero intersect CORE_CORPORATE**.
- Eight of nine are covered by one or more service prefixes /`24` or broader; only `88.223.91.1/32` is covered solely by exact HXEHEX host evidence.
- Coverage by sources: Kyoresuas=5, Escapingworm=4, HXEHEX=1, W1ZARDZ=0. One address `158.160.63.17/32` intersects two service feeds; the coverage counts are **not additive**.
- In Qrator AS51115, `178.248.234.146` and `178.248.236.100` match **most-specific** Kyoresuas /`24` but also the broader Kyoresuas /`21`. Thus merely reporting a /`21` matches hides the more precise source hierarchy.
- Yandex AS200350 includes the broad /`16` `158.160.0.0/16`, /`18` `89.169.128.0/18`, and /`20` `111.88.144.0/20` service matches. Timeweb AS9123 `81.200.149.9/32` matches Escapingworm /`22`.
- Two AS210079 hosts `46.254.18.79/32` and `46.254.18.115/32` match an Escapingworm /`23`, outside CORE and SHARED masks.

**Decision:** keep this as review-only evidence and flag service-mask overlaps with exact legacy hard entries, especially on shared/CDN clouds. The audit establishes *which rules caused the effective exemption*, not whether a historical block is still valid today. An external, dated and address-specific corroboration would be needed before changing either the block exemption or DIRECT. No production inputs were modified.

## Full exact hard IPv4 host regression monitor (2026-11-12)

The earlier nine-host review was restricted to legacy-v38-only hard evidence. The expanded, **read-only** monitor now scans **all 57,612 exact IPv4 /32 hard host entries**, irrespective of legacy or current provenance, and flags addresses satisfying **all four conditions**: inside a SHARED_INFRA origin prefix, within a broad (IPv4 /24 or larger) service protection prefix, present in final v41 DIRECT, and absent from the effective blocked mask.

The first verified broad audit was GitHub Actions [43271570738](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43271570738), SUCCESS; artifact `13966979700`. Results: **50** broad-service SHARED hard exceptions in final DIRECT; **6** previously observed in the historical-only audit, **44 previously untracked** (this does **not** mean newly introduced by the latest production update). **All 44** are present in the published current `antifilter-ip.lst`. Of those, **42** also have legacy-v38 hard provenance; two have only the current hard-source provenance. All 50 are exact /32 addresses from the original hard inputs. Evidence source memberships are not additive.

Top clusters within the 44 untracked cases: `158.160.0.0/16` **17** (Yandex cloud class), `89.169.0.0/16` **5**, `111.88.0.0/16` **4**, `178.248.0.0/16` **4**, and `185.65.0.0/16` **3**. Broad-source memberships across these 44: Kyoresuas **43**, Escapingworm **19**, W1ZARDZ **3**, often overlapping. These are **candidate risk flags**, not proven active regulatory blocks; `antifilter-ip.lst` includes DNS-derived results.

The monitor's six-entry baseline `.github/data/v41_observed_shared_service_hard_exceptions.tsv` is an **observed snapshot, not an approval allowlist**. It permits warnings on any newly detected case outside the original six and reports when a previously observed case disappears; it changes neither final DIRECT nor effective-block policy. Report outputs:
- `all_shared_service_hard_overrides.tsv` includes exact evidence labels, SHARED prefix, matching broad service sources, and whether each match was in the six-entry historical observation baseline
- `shared_service_hard_guard_summary.json` provides current-versus-legacy evidence counters and newly discovered untracked cases
- the GitHub Actions workflow emits a visible `::warning` for untracked cases, without failing production or automatically whitelisting any address

**Priority for next policy review:** verify the 44 current-source hard exceptions against dated IP-specific evidence and confirmed first-party service ownership; avoid removing broad-service masks until their real service consequences are measured. The 213 historically dropped v34-only IPs remain a separate audit queue, also not safe to restore without evidence.

No change to production binaries, main, release, tags, or PR #5 was made by this audit.

## Independent RIS-origin and full SHARED hard shadow impact (2026-11-12)

- **RIPE RISwhois** source documented at https://stat.ripe.net/docs/data-api/api-endpoints/network-info; source output from successful audit CI [43276315363](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43276315363), artifact `13971730399`.
- Every **44/44** current `antifilter-ip.lst` /`32` shared+service-broad DIRECT exception returned an observed prefix and at least one origin AS, with zero lookup failures at `2026-11-12T18:07:08Z`. RIPE RIS observed ASN distribution: **AS200350 31**, **AS51115 11**, **AS210756 1**, **AS215013 1**. RIPE RIS BGP origin evidence does **not** establish service-host ownership or a current regulator block.
- **Whole hard set shadow** (not restricted to /`32` or broad service masks): read-only CI [43276929403](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43276929403), artifact `13971686182`, **SUCCESS**. Exact `published_RU ∩ SHARED ∩ original_hard` address intervals: **59 IPv4** (59 /`32` CIDRs), **0 IPv6**. Of the 59, **53** intersect the current `antifilter-ip.lst`, **57** intersect v38 legacy evidence; source categories overlap. All 59 are present in DIRECT and absent from the effective block list. A hypothetical policy giving all hard entries precedence inside SHARED would remove at most these 59 currently-DIRECT addresses under this specific rule alone; **NO shadow rules were applied**.
- The existing monitor of broad service masks found 50 IPv4, so the exact shadow discovered **9 additional narrowly attributed /`32` exceptions**: `46.148.232.104`, `92.53.96.144`, `176.57.67.92`, `185.129.100.112`, `185.178.208.183`, `185.215.4.10`, `185.215.4.40`, `185.215.4.45`, `185.215.4.66`. These nine are all current-source hard cases; broad-set totals 44 current + 6 historical-only, whole-set totals 53 current + 6 historical-only.
- Exact feed-bytes from archived candidate matched release manifest SHA256 for Kyoresuas IPv4, services JSON, HXEHEX, Escapingworm. Among the additional nine, Kyoresuas offers named exact service-host evidence for `176.57.67.92` (Магнит), `185.129.100.112` (Циан /`32` nested inside feed /`31`), `185.215.4.10` (МТС), `185.215.4.40` (Детский мир), and `185.215.4.45` (ВсеИнструменты.ру). The other four have exact W1ZARDZ /`32` source entries. **Publisher-supplied service names remain claims, not proven IP ownership**.
- New scripts `.github/scripts/audit_v41_current_hard_ris.py` and `.github/scripts/audit_v41_shadow_hard_shared.py` with focused module tests. Both report-only; shadow runs in historical and post-release monitors, RIPE lookups run only in the manually reviewable PR audit. The release workflow itself remains untouched.
- **Policy decision postponed:** verify specific current hard block evidence and service use before changing any of the 59 exact host destinations. In particular, avoid blindly overriding narrow /`32` service exceptions while evaluating broad shared-hosting masks.

The PR is Draft and this is evidence gathering only; no `main`, `release`, binary, tag or PR #5 mutation.

## All 153 hard exceptions: address-specific provenance matrix (2026-11-12)

Source verification: post-release audit [43282279103](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43282279103) **SUCCESS**, artifact `13973212255`, source SHA-256 checked against published v41.

New `.github/scripts/audit_v41_hard_evidence_matrix.py` and tests generate `all_153_hard_exceptions_evidence_matrix.tsv` and `all_hard_evidence_matrix_summary.json` in both read-only audit workflows. The 153 exact addresses are partitioned without double-counting across CORE=19, SHARED=59, OTHER=75; every address has original hard-source provenance.

| Class | Total | Current ip.lst | Current subnet.lst | v38 legacy | Exact service /32 evidence | Broad service /24 or wider |
|---|---:|---:|---:|---:|---:|---:|
| CORE | 19 | 19 | 0 | 18 | 0 | 18 |
| SHARED | 59 | 53 | 0 | 57 | 10 | 50 |
| OTHER | 75 | 65 | 6 | 69 | 33 | 42 |

The review matrix uses **P1=118** (current ip.lst on SHARED/OTHER), **P2=19** (current ip.lst on CORE), **P3=6** (current subnet.lst outside ip.lst), **P4=10** (no current ip.lst/subnet evidence). The P4 group includes nine historical-only addresses and one `runetfreedom-static-telegram` plus historical hard entry `185.76.151.1/32`; P4 **must not be misinterpreted as proof of unblocking**.

Six P3 hosts (all OTHER) are `185.60.216.1`, `185.60.217.1`, `185.60.218.1`, `185.60.219.1`, `185.89.217.1`, `185.104.45.1`; each overlaps HXEHEX service evidence.

The matrix deliberately records `current_regulatory_block_confirmed=NO` and `service_host_ownership_confirmed=NO` for all 153, since direct regulatory evidence and host-level first-party ownership were **not** independently established. It produces routing action `NONE_AUDIT_ONLY`, never modifies the published database or effective blocks. Snapshot baseline warnings remain observational, not approvals.

Detailed session report: `GeoIP_v41_PR16_Hard_Exceptions_Per_IP_Quality_20261112_43282279103.md`. Full CIDR + TSV + JSON are bundled in the CI artifact. No production merge or PR #5 changes.

## P1 service-prefix specificity and review ordering (2026-11-12)

A new read-only, release-hash-verified stage separates **118 P1 exact IPv4 hard addresses** (current `antifilter-ip.lst` and inside SHARED/OTHER DIRECT) by *published service feed specificity*, not by unproven assumptions about actual blocks. Post-release monitor [43284286430](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43284286430) **SUCCESS**, artifact `13974925325`.

| Published service evidence | SHARED_INFRA | OTHER | Total |
|---|---:|---:|---:|
| Broad IPv4 CIDR (/24 or wider), no exact /32 claim | 43 | 40 | **83** |
| Both broad and exact /32 claims | 1 | 0 | **1** |
| Exact service /32 only | 9 | 25 | **34** |
| **Total** | **53** | **65** | **118** |

All 118 remain audit candidates because source list membership does **not** prove an active regulatory block. Exact service /`32` in a public catalogue also does **not** verify first-party service ownership. The ordering **broad-only → mixed → exact-only** guides host-specific manual review effort and **does not change route precedence**.

Added `.github/scripts/audit_v41_p1_service_specificity.py` and four module tests, invoked by both historical and post-release workflows. New outputs `p1_current_hard_service_specificity_review.tsv` and `p1_current_hard_review_summary.json` are complete, reviewed-only, and dynamic for future published releases; the existing class-level set-SHA256 regression monitoring remains independent.

**Next decision gate:** independently dated, host-specific regulator/block evidence and actual service-host attribution. No production routing or effective masks were changed. PR #16 remains Draft; no changes to PR #5.
