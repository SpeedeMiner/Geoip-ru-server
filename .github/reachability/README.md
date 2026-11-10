# RU / KZ / BY reachability diagnostics

This is a **review-only measurement system** for Geoip-ru-server.
It does not edit or publish \`geoip_RU.dat\`.

## Data sources

- **Globalping**: online probes filtered by country, observed ASN and the
  \`eyeball-network\` tag. Each task checks DNS A/AAAA and HTTPS over IPv4/IPv6.
  The tag distinguishes end-user networks from datacenter probes, but does not
  prove that a probe is physically on a residential line. We record it as
  \`eyeball_network_unverified\`.
- **OONI**: recent \`web_connectivity\` measurement metadata for configured
  target domains and RU/KZ/BY. OONI anomalies are review signals only; this
  collector does not convert an anomaly into a confirmed block.
- **RIPE Atlas**: optional one-off TLS certificate measurements. The workflow
  selects a connected probe by both country and address-family ASN, creates
  a bounded number of measurements, and saves returned results or explicit
  pending measurement IDs.

## What “full” means

The inventory exporter reads the actual published \`release/geoip_RU.dat\`
protobuf and exports **every RU and PRIVATE CIDR**, verifying that the file
contains exactly these two categories, no duplicate/non-canonical prefixes,
and no RU/PRIVATE overlap.

It does **not** scan every address in every CIDR. Such a scan would mostly hit
unused addresses and would not establish that a network is blocked. Active
checks are limited to declared, working service hostnames in \`targets.json\`.
The observed DNS answers and HTTPS destination IPs are then matched against
the complete CIDR inventory.

Therefore a prefix without a matched service endpoint is reported as
\`NO_MATCHED_ENDPOINT\`, not as accessible or blocked. This is a full inventory
with endpoint-based observations, not a claim that every IP address was tested.

## Probe selection and limits

Globalping's public probe list is sampled at run time. Tasks are selected as
complete per-provider bundles: DNS A + DNS AAAA + HTTPS IPv4 + HTTPS IPv6 for
one target. The scheduler round-robins across every discovered country/ASN
provider before assigning a second target bundle to any provider. Both provider
order and target choice rotate deterministically by UTC date. This avoids a
continuous slice of a sorted task list starving KZ/BY or later ASNs.

At most 180 Globalping tasks are scheduled per daily run by default (hard
safety maximum 220), with at most five concurrent measurements. The budget is
rounded down to a multiple of four so a provider/target bundle is never split.
The summary records discovered provider pairs, covered/uncovered pairs and
country coverage. Rate limiting stops new submissions and is recorded.

A daily run is a **rotating sample**, not a complete provider-by-target census.
In the latest full run (2026-11-10), the 30-target catalogue produced 45
complete bundles across 38 discovered country/ASN provider pairs (RU 29, KZ 6,
BY 3). All 30 hostnames appeared, but only 32 of the 90 possible
source-country/target combinations were observed that day (RU 23, KZ 6, BY 3).
Thirty-seven provider pairs returned probe result metadata; the remaining pair
had three `NO_PROBE` tasks because no matching IPv4 probe was available.
The UTC rotation changes both provider and target selection over successive
days. Full provider-by-target coverage must therefore be assessed over a
multi-day series of successful runs; do not infer that every provider can reach
every listed target from one daily artifact. The daily schedule becomes active
only after this workflow is merged into the repository's default branch.

The Globalping \`eyeball-network\` tag is not a residential-connection
attestation. The country, ASN and tags returned by the actual test result are
checked before the observation is accepted.

RIPE Atlas is optional. Add the repository Actions secret
\`RIPE_ATLAS_API_KEY\` with measurement-creation permission to enable it.
Without that secret, the output explicitly states that Atlas was skipped.
The per-run Atlas cap is 18 one-off TLS measurements.

OONI is queried modestly by target domain and country for the preceding
seven days. The API is not intended for bulk dataset downloads.

## Result meanings

- \`ACCESSIBLE\`: the selected eyeball-class probe completed HTTPS and received
  an HTTP status. Even a 403/5xx means that an HTTP response was received; it
  does not certify the application is healthy or that no content filtering
  occurred.
- \`DNS_ANSWER\`: an A/AAAA answer was returned by the probe's resolver.
- \`DNS_NXDOMAIN\` / \`DNS_NO_ANSWER\`: DNS observations, not block verdicts.
- \`INCONCLUSIVE\`: timeout, TLS error, reset, or other failed measurement.
- \`WRONG_PROBE_SELECTION\`: the returned probe did not match requested country,
  ASN and eyeball tag.
- \`NO_PROBE\` / \`NO_MATCHING_CONNECTED_PROBE\`: no suitable probe was available.
- \`NO_MATCHED_ENDPOINT\`: no tested service endpoint resolved into that RU
  prefix during the observation set.

**There is deliberately no automatic \`BLOCKED_CONFIRMED\` result.** A timeout
is not proof of blocking. OONI anomalies are reported separately for review.
A future confirmed-block classifier would need repeated measurements, positive
controls, independent probes, source-level evidence and explicit block-page or
DNS-manipulation fingerprints.

## Artifacts

The full workflow uploads:

- \`reachability_inventory.tsv\` — every RU and PRIVATE prefix from the
  published client protobuf;
- \`reachability-output/globalping_measurements.jsonl\` and
  \`globalping_raw.jsonl\` — normalized and raw Globalping responses;
- \`ooni_observations.jsonl\` and \`ooni_raw.jsonl\` — OONI metadata and raw API
  responses;
- \`ripe_atlas_measurements.jsonl\` and \`ripe_atlas_raw.jsonl\` — Atlas IDs,
  status, and retrieved result samples;
- \`reachability_by_provider.tsv\` — observed provider ASN outcomes;
- \`reachability_by_prefix.tsv\` — endpoint matches against RU prefixes;
- \`reachability_candidates.tsv\` — failures and observations requiring review;
- \`reachability_summary.json\` — counts, configuration and coverage metadata.
  The summary includes DNS no-answer totals, IPv4/DNS no-probe counts and their country breakdown, per-country missing-IPv6-probe counts, unique target-country pairs observed versus possible, the country breakdown, and the number of distinct hostnames sampled. Globalping HTTP 422 `no_probes_found` responses are reported as `NO_PROBE` (or `NO_IPV6_PROBE` for HTTPS IPv6), not as an API failure or a reachability verdict. These metrics describe the selected daily sample; they do not imply full provider-by-target coverage in one run.

## Editing the target catalogue

Add one entry per actual, publicly reachable service endpoint:

\`\`\`json
{
  "id": "unique-id",
  "domain": "service.example",
  "role": "service",
  "country_scope": ["RU", "KZ", "BY"],
  "port": 443,
  "path": "/",
  "reference_url": "https://official-or-authoritative-source.example/"
}
\`\`\`

\`country_scope\` means where to test from; it is not an assertion about the
service's physical location or ownership. \`reference_url\` is optional
catalogue provenance: prefer an official operator, regulator or government
reference. Keep control targets separate from services whose reachability is
being studied. Do not use arbitrary addresses or enumerate IPs from the
GeoIP ranges.

The catalogue currently contains 30 hostnames: two controls and 28 service
targets across RU, KZ and BY. The expanded seed covers public administration,
banking/payments, postal services, telecom operators, marketplaces and major
public digital platforms. It is intentionally a pilot, not a comprehensive
inventory of every service or every domain behind those brands. A brand may
use additional hostnames, APIs, CDNs or mobile-app endpoints that are not
represented here.

Before adding a target, verify the exact hostname and its continued relevance.
For production-quality coverage claims, the project owner must approve a
maintained service inventory and include all agreed first-party hostnames and
critical API endpoints. Until then, \`NO_MATCHED_ENDPOINT\` means only
"not observed by this seed catalogue", not inaccessible or blocked.

## CI separation

- \`Reachability validation\` runs syntax checks and deterministic unit tests
  on changes to this directory.
- \`Full reachability RU KZ BY\` is manual or daily.
- The main GeoIP build, GeoIP quality gates, release publishing, PRIVATE
  precedence and the two-category client format are not changed by this
  diagnostic workflow.
