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

## Editing the target catalogue

Add one entry per actual, publicly reachable service endpoint:

\`\`\`json
{
  "id": "unique-id",
  "domain": "service.example",
  "role": "service",
  "country_scope": ["RU", "KZ", "BY"],
  "port": 443,
  "path": "/"
}
\`\`\`

\`country_scope\` means where to test from; it is not an assertion about the
service's physical location or ownership. Keep control targets separate from
services whose reachability is being studied. Do not use arbitrary addresses
or enumerate IPs from the GeoIP ranges.

The current catalogue is a seed set of controls and RU/KZ/BY service
endpoints. It must be extended with the project's agreed real-world target
inventory before anyone interprets the results as complete service coverage.

## CI separation

- \`Reachability validation\` runs syntax checks and deterministic unit tests
  on changes to this directory.
- \`Full reachability RU KZ BY\` is manual or daily.
- The main GeoIP build, GeoIP quality gates, release publishing, PRIVATE
  precedence and the two-category client format are not changed by this
  diagnostic workflow.
