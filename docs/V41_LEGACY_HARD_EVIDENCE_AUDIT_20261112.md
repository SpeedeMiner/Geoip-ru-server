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
