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

## Russian ISP access-network measurements via VPNObratno / VPN Gate

The original Globalping collector remains a separate, supplementary vantage-point source.
Its `eyeball-network` tag is not proof of a residential line.

A second, **manual-only** workflow, `Russian ISP VPN Gate reachability`, now
uses `vpnobratno.info/russia_server_list.html` as its default discovery source.
The site describes its entries as VPN Gate nodes operated by Russian users on
different Russian Internet providers. The page publishes several OpenVPN
profiles per node. The collector downloads only linked `.ovpn` files from
the exact `vpnobratno.info` origin and recognises these variants:

- `IP UDP` — preferred first, pins the literal profile address to the listed server hostname;
- `UDP` — hostname-based UDP fallback;
- `IP TCP` — literal-IP TCP fallback;
- `TCP` — hostname-based TCP fallback.

The profile variants are **connection alternatives for one server**, not
independent providers. They are ordered IP UDP, UDP, IP TCP, TCP within a
server. Provider diversity is measured by the server IP's independently
looked-up origin ASN; another profile for the same server cannot increase the
distinct-provider count.

Before a profile can be attempted, the collector checks that its filename
matches the server hostname and variant shown in the listing, that the profile
remote agrees with the listed hostname (or that an IP-literal remote is in the
hostname's current public DNS answers), and that the configured transport
matches the advertised variant. Profiles are parsed but never executed
directly: the client is rebuilt from the existing strict allowlist, pins the
remote IP, and drops untrusted scripts, plugins, route directives and external
key files. Each successful tunnel must still pass the two-source public exit
IP/country check before any target is contacted.

The workflow has a manual `source` selector:
- `vpnobratno` (default): page discovery and the linked profile variants above;
- `vpngate`: the official VPN Gate CSV API as a fallback source.

The conservative first-pilot defaults are **one successful RU exit** and up
to **six profile attempts** (hard cap six). This allows alternate IP UDP/UDP/
IP TCP/TCP profiles to be tried without requiring three separate exits. Failed
TLS or authentication handshakes are detected from the live OpenVPN log and
stop that attempt early.
The collector prefers one candidate per distinct origin ASN before trying
another profile from an already represented ASN. It stops as soon as the
requested number of verified RU exits succeeds. The manual job timeout is
120 minutes. A and AAAA answers are collected in one resolver call per target.
Manual dispatch becomes available after this workflow is integrated into the
repository default branch. It remains manual-only: no daily schedule or
feature-branch push trigger is enabled.

The artifacts include `vpn_gate_providers.tsv`,
`vpn_gate_measurements.jsonl`, `vpn_gate_geoip_candidates.tsv`,
`vpn_gate_raw.jsonl` and `vpn_gate_summary.json`. Provider and measurement
rows retain the discovery source, profile variant and profile URL so a result
can be traced to the exact connection method used.

**Important evidence limit:** VPNObratno says its servers belong to Russian
VPN Gate users and use services from Russian Internet providers. That is useful
for finding access-network vantage points, but it does not prove that every
node is a household broadband line. We record the source as
`RESIDENTIAL_OR_OTHER_ACCESS_NETWORK_UNVERIFIED` and validate the actual
exit IP, country and origin ASN independently. Do not call these confirmed
residential measurements unless the access type is independently established.

#### What the four earlier live pilots did—and did not—test (2026-11-11)

The four previous bounded pilots used the official VPN Gate CSV API, not the
new direct VPNObratno profile-link discovery or its IP UDP/IP TCP variants.
They produced zero verified RU exits and zero completed target-measurement
rows. Those failures show that the small sample of API-returned profiles
available during those attempts did not establish a usable tunnel; they do not
prove that every currently listed VPNObratno profile is unusable, and they do
not indicate that target services are blocked or GeoIP ranges are missing.

The new VPNObratno discovery and profile-validation path has unit-test
coverage, but **no live connection through these newly discovered variants
has been run yet**. Do not describe it as a successful live measurement until
a manual workflow run records a verified RU exit and actual target rows.

### VPN exit verification and provider diversity

Before sending any service request through a volunteer node, the runner now requires
two independent public IP-metadata services to agree on the exact exit IPv4 address
and country. A disagreement or fewer than two usable responses rejects that node.
The actual exit ASN/prefix is then enriched separately from RIPEstat. ASN values
from IP metadata and RIPEstat are recorded in separate columns; a mismatch is
flagged for review rather than silently choosing one. A returned RIPEstat prefix
is retained only if it contains the queried IP address.

The collector inspects up to 24 profile candidates for origin ASN and
prefers one candidate per distinct observed ASN before selecting another
profile from the same ASN. If RIPEstat cannot establish an ASN, the candidate is marked
ASN-unverified and is not counted as provider diversity.

After the tunnel is up, system DNS/NSS failures are handled with a fallback
DNS-over-HTTPS client pinned to public resolver IPs (Cloudflare 1.1.1.1 and
Google 8.8.8.8). The DoH request keeps TLS SNI/certificate verification for the
resolver hostname; metadata HTTPS and target HEAD requests can also use
DoH-resolved, IP-pinned connections while preserving the original hostname for
TLS validation. These requests therefore remain on the VPN tunnel and do not
fall back to the runner's direct DNS path. The runner does not rewrite
`/etc/resolv.conf` or any other host resolver configuration: system NSS is
left untouched, and the pinned DoH path handles resolver failures. HTTPS
fallback is IPv4-only because the VPN tunnel and kill-switch intentionally
block host IPv6 egress; AAAA answers are still collected and reported as DNS
evidence, but no IPv6 HTTPS attempt is made.

A run that cannot establish its requested number of verified RU exits returns a
non-zero measurement status. The workflow still uploads diagnostic artifacts
using an always-run upload step, then marks the job failed. A green job therefore
requires the requested count of confirmed RU egresses, not just successful
artifact upload.

The OpenVPN client is rebuilt rather than running the volunteer-provided profile.
Alongside the pinned remote and inline CA/key blocks, it preserves only
allowlisted TLS compatibility settings present in the profile (TLS min/max,
TLS cipher/ciphersuites, certificate profile, EKU/KU and optional certificate
name verification). Inline `tls-auth`, `tls-crypt` and `tls-crypt-v2` blocks
are retained. Profiles that refer to external TLS key files are rejected.
Scripts, plugins, external config files and route directives are never copied.
Sanitized profile-feature flags (not key material) are included in the raw
diagnostic report to help compare failed volunteer relays.

## Opt-in home ISP probe

VPN Gate did not provide a stable tunnel in the live pilots. For the original
goal—testing from a genuine Russian household ISP—the alternative is a small
probe that the network owner runs locally on a PC or router connected directly
to that ISP.

The local-only script is `.github/reachability/home_probe.py`. It:

- requires an explicit `--consent` flag before any endpoint checks;
- refuses to run when HTTP(S)/ALL proxy environment variables are configured; disable VPN/proxy software as well (the script does not try to change system routing);
- obtains the public egress IP from two independent metadata services and records ASN/organization when available;
- stops before target requests when both metadata sources confirm a country different from `--required-country`; if metadata is unavailable, observations can still be saved but remain unattributed;
- uses the host's normal DNS resolver for A/AAAA so DNS behavior remains part of the ISP measurement;
- sends at most one HTTPS HEAD request per family (IPv4 and IPv6), to the first observed address in that family, preserving TLS SNI and certificate validation; the exact tested address is recorded;
- writes a versioned `home_probe_source.json`, `home_probe_measurements.jsonl` and `home_probe_summary.json` locally; it never uploads data automatically;
- refuses to overwrite a non-empty output directory.

From the repository root, on the actual home connection:

```bash
python3 .github/reachability/home_probe.py --required-country RU --consent --max-targets 3 --output-dir home-probe-output
```

On Windows, use `py -3` instead of `python3`. Remove `--max-targets 3`
to measure all RU-scoped catalogue targets (currently up to 30 hostnames).
Use a new output-directory name for every run so earlier evidence is preserved.

The report contains the public egress IP and DNS answers; review it before
sharing it. It intentionally does not collect local/private IPs, MAC addresses,
hostnames, browsing history, cookies or credentials. A two-source country/IP
match is supporting attribution, not proof of a household subscription:
combine it with operator/ASN validation and the fact that the owner ran the
probe directly on that ISP. A report with unavailable metadata is retained as
raw endpoint evidence but cannot be imported as a confirmed RU source-network
observation. The source egress IP is personal network metadata; share the report
only with the network owner's approval.

### Importing a volunteer report for GeoIP review

The separate `.github/reachability/home_probe_ingest.py` tool maps the
volunteer's source IP and every observed DNS answer against a complete RU and
PRIVATE prefix inventory. First generate the inventory from the exact
published protobuf in this checkout:

```bash
cd .github/reachability/inventory
GOTOOLCHAIN=local go run . ../../../release/geoip_RU.dat ../../../reachability_inventory.tsv
cd ../../..
```

Then validate and import the locally reviewed report:

```bash
python3 .github/reachability/home_probe_ingest.py \
  --report-dir home-probe-output \
  --inventory reachability_inventory.tsv \
  --required-country RU \
  --output-dir home-probe-ingest-output
```

The importer requires a versioned report, two distinct metadata providers
agreeing on one public egress IP and RU country, no proxy environment, and
matching target IDs/domains from the current catalogue. It rejects malformed,
private, wrong-family, duplicate or unverified DNS addresses and checks that
the recorded HTTPS-tested address is the first DNS answer actually selected.
It writes `home_probe_provider.tsv`, `home_probe_observations.tsv`,
`home_probe_candidates.tsv` and `home_probe_ingest_summary.json` locally;
it does not upload data or edit `geoip_RU.dat`.

Only an exact source IP attributed to RU and outside RU inventory becomes a
`HOME_PROBE_SOURCE_IP` review candidate. KZ/BY reports can be imported and
mapped for context, but they never create missing-RU-prefix candidates. The
importer also rejects inconsistent source ASN/organization summaries and
mismatched DNS/HTTPS evidence (for example, DNS answers without the expected
HEAD attempt). It does not infer a CIDR from a single IP. DNS destination
addresses are reported separately and must not be confused with the
volunteer's source ISP range. The access-network class remains
`RESIDENTIAL_OR_OTHER_ACCESS_NETWORK_UNVERIFIED` until the operator, origin
ASN and access type are independently confirmed.

A useful pilot needs consenting volunteers on several different Russian
operators and, ideally, regions. One machine measures only its own current
connection; it does not represent every customer of an ISP.

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
