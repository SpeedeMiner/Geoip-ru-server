# Project execution journal — Geoip-ru-server

**Purpose:** durable cross-chat recovery record. Read this file before continuing project work. Append dated entries; do not rewrite or discard earlier checkpoints.
**Repository:** `SpeedeMiner/Geoip-ru-server`
**Last reviewed:** 2026-11-11 17:15 UTC (Asia/Almaty UTC+5)
**Journal branch:** `experiment/vpn-route-candidate-build-2026-11` (PR #8; review-only source research branch).

## 0. Hard safety boundaries

- Do not inspect, edit, test, dispatch workflows for, rebase, merge, or otherwise touch PR #5 or `feature/reachability-full-ru-kz-by`. Another agent owns it.
- PR #6, #7, #8 and #9 must remain OPEN / DRAFT. Do not mark Ready, merge, or enable auto-merge.
- Do not modify `main`, `release`, production `geoip_RU.dat`, production builder inputs, release assets, release tags, or CDN state.
- Keep work split across the existing PR branches. Do not bulk-promote candidate source data into v38.
- Final client semantics: two categories only (`RU`, `PRIVATE`). `RU` is the legacy unified DIRECT bucket for RU+BY+KZ registered resources and approved named regional services; it is not a strict physical-geolocation list. `PRIVATE` precedence is absolute. Explicitly approved RKN PROXY carve-outs override service DIRECT.
- The owner waived separate license verification as a project gate. Preserve immutable source pins and attribution; publisher tiers/correlated feeds are not independent votes.
- A CI artifact, RIPE/RDAP result, RIR registration, or hostname mapping is evidence for review, not automatic permission to add/remove IP space.

## 1. Latest verified repository state

### PR inventory

| PR | State | Branch | HEAD | Scope |
|---|---|---|---|---|
| #6 | OPEN / DRAFT | `audit/exact-origin-followup-2026-11` | `9014b18a2f7bf4de9d4493d19b50f399b57b0e3e` | Exact-NLRI / RPKI evidence, review-only |
| #7 | OPEN / DRAFT | `docs/source-improvement-plan-2026-11` | `3f3dbb51c999b0de833ebda233e7b02f8c082b35` | Source inventory and prefix-audit plan, audit-only |
| #8 | OPEN / DRAFT | `experiment/vpn-route-candidate-build-2026-11` | `f9d6ec1f36199bae6c9de9502ec43ee91eb99d9a` | Pinned VPN source comparison and v38 hostname/IP review |
| #9 | OPEN / DRAFT | `feature/geoip-direct-rukzby-v38` | `926185d897eea8a370cf939144da3d32641943c1` | v38 candidate plus Antifilter BGP direct-block evidence procedure |

Latest metadata check confirms all four PRs are open, draft=true, merged=false, base=main. All four branch names are present. PR #6 and #7 HEADs were unchanged; PR #8 and #9 HEADs above include the work in this journal.

Production refs at latest verification:
- `main`: `580a25a7a65d957d46d83e827ccbd9308969713e`
- `release`: `d780450dda69416257b890d98fbc43620a0555e8`
- Both were re-read from GitHub after the current PR work; neither was advanced by these commits.
- No production tags, release assets or CDN were changed.

Do not query PR #5 for status. Its status is intentionally outside this journal's refresh scope.

## 2. Immutable v38 baseline — do not rebuild just to repeat success

PR #9 candidate build run #71: `43050025980`.
Artifact ID: `13868718366`; artifact name: `geoip-direct-rukzby-v38-candidate`.
Downloaded ZIP: `pr9-run71-v38-candidate.zip`; ZIP SHA-256: `47a64b8aa513542c012f630878135d51cee40f8565cc177987b16e54ceda348a`.
Final protobuf SHA-256: `445c2cb66e3840e61aff8cf5c53ab151ab4951189d2da462f13a9264a43ac515`.
Protobuf size: 2,191,510 bytes.

Decoded v38 quality report confirms:
- RU: 200,765 CIDRs; IPv4 address union 53,095,212; IPv6 address union 1,204,925,358,834,572,963,424,937,397,190,656.
- PRIVATE: 151 CIDRs; PRIVATE IPv4 union 592,708,862; IPv6 union 4,325,545,831,231,176,725,068,219,651,071,148,031.
- Exactly two output categories: RU and PRIVATE.
- Exact v37→v38 addition after PRIVATE and approved blocked precedence: +476,099 IPv4 and +12,483,475,607,738,606,560,012,522,225,664 IPv6.
- Existing approved v37 blocked set has 193,285 unique CIDRs. `ipsum.lst` /24 summary remains review-only; no `/24` auto-carve.

Do not run the main v38 build merely to reproduce these numbers. Only run a new candidate build when a separately reviewed source/policy change actually requires it. PR validation may build candidate artifacts but must skip all production release/push/CDN steps.

## 3. PR #8 hostname→IP candidate audit

Input artifact: PR #8 run #16 `43051888120`, artifact ID `13869656430`.
Downloaded ZIP: `pr8-run16-candidates.zip`; SHA-256 `940828a10486181ef8467c785ddc27e5ebab497692e0b3349c1891a2df4aa44f`.
Primary source sidecar inside ZIP: `candidate_amnezia_host_ip_observations.tsv`.
v38 comparison is against the decoded PR #9 run #71 protobuf and actual v38 approved blocked inputs, not only the old v37 baseline.

Reconciled exact-host counts:
- Unique Lib4u + Jirnobruh IPv4 host observations: 2,089.
- Already in v38 RU/DIRECT: 1,535.
- Overlap with v38 approved blocked inputs: 194.
- Remaining exact-host candidates outside v38 RU, PRIVATE and approved blocked set: 360 unique IPv4 `/32` values.
- Source split among the 360: Lib4u only 315; Jirnobruh only 25; both feeds 20. These add exactly to 360.
- All 360 are REVIEW, not production input.

Candidate review file:
- `review/v38_pr8_new_host_ip_candidates_20261111.tsv.gz`
- Compressed SHA-256: `159ab81a1444fa94daea8fe9e2c1d48b4c618d0b69b67b6d5dca9efcf1b4d392`.
- Decompressed TSV SHA-256: `00cf82af9c2883c5d051a8a08d212d20de5f39ff63bba68e0ac1bc40e960f0e0`.
- 360 rows; every IP has canonical exact `/32`; input loader rejects duplicate/private/non-global/non-canonical IPs and any overlap with v38 RU/PRIVATE/approved blocks.

Hostname distribution from the candidate TSV (the `hostnames` field is semicolon-separated; preserve that delimiter when analysing):
- 275 distinct hostnames.
- 117 candidate IPs map to more than one hostname.
- Maximum hostnames mapped to one candidate IP: 31.
- Kaspersky/KSN group: 129 hostnames associated with 113 candidate IPs.
- HiWiFi/Xiaomi group: 3 hostnames / 59 associated IPs.
- AWS/CloudFront: 1 hostname / 39 associated IPs.
- `.ru`/`.рф` suffix group: 22 hostnames / 37 associated IPs; the other 323 candidate IPs have no `.ru`/`.рф` hostname mapping in this snapshot.
- The most repeated hostnames include `hiwifi.com` (47 IPs), `kp-configs-smart-tv.s3.eu-central-1.amazonaws.com` (39), `ksn-file-geo.kaspersky-labs.com` (22), `ksn-file.geoksn.kaspersky.com` (21), `ksn-url-geo.kaspersky-labs.com` (21), and `ksn-crypto-url-geo.kaspersky-labs.com` (20).

Interpretation: hostname/IP sidecars are source-snapshot observations, not proof of current DNS answers, legal ownership or exclusive IP use. Shared cloud/CDN/hosting, multiple hostnames per IP, MOAS, RPKI invalid/unknown, absent exact IRR, or unavailable RDAP all remain explicit review items. No automatic promotion is allowed.

## 4. PR #8 implementation added

Commits on PR #8 branch:
- `93a660e527f1d14c6744738100c1e734e65ef153` — added review-only enrichment tooling, tests, fixed input and initial review documentation.
- `160987daca5df823983e4ed50d56c6221f0c8d67` — corrected malformed test source discovered by reading the GitHub blob; the fixed test content was re-fetched and verified.
- `f9d6ec1f36199bae6c9de9502ec43ee91eb99d9a` — added hostname distribution documentation.

Files added:
- `tools/review_v38_host_ip_candidates.py` — small loader for the compressed implementation.
- `tools/review_v38_host_ip_candidates.py.gz` — compressed RIPEstat/RDAP review implementation.
- `tools/tests/test_review_v38_host_ip_candidates.py` — focused tests.
- `review/v38_pr8_new_host_ip_candidates_20261111.tsv.gz` — immutable 360-row review input.
- `docs/V38_HOST_IP_CANDIDATE_REVIEW.md` — review method/limits.
- `docs/V38_HOST_IP_HOSTNAME_DISTRIBUTION.md` — source hostname distribution.

Workflow `.github/workflows/vpn-route-candidate-build.yml` now:
1. Runs existing candidate-source unit tests.
2. Builds the pinned candidate source artifact.
3. Runs v38 host-IP enrichment with max 4 workers.
4. Uploads candidate artifacts only; it has contents:read, no production write step.

Enrichment queries public RIPEstat `network-info` for each exact IP; `routing-status` for each distinct RIS prefix; `as-overview` for origin holder labels; `rpki-validation` for every exact prefix/origin pair; and IANA RDAP bootstrap followed by one authoritative RIR RDAP lookup per covering prefix (or individual IP if no RIS prefix). Raw response bodies, HTTP status, URL, capture time and body SHA-256 are preserved in `raw_lookup_responses.jsonl.gz`; normalized rows and `manifest.json` include source query timestamps, counts and errors. API failures/no RIS prefix are coverage limitations, never evidence that an IP is unused or safe.

Important limitations:
- RIPE RIS `network-info` uses RISwhois 8-hour dumps; `routing-status` has its own latest RIS collection time.
- Public RIPE data do not prove Antifilter `65444:210` membership.
- RPKI `unknown` is not `invalid`; an exact IRR object is not proof of legal holder/service exclusivity; RDAP registrant data is not proof that an IP is dedicated to one hostname.
- Shared provider flags are conservative review hints only, not automatic rejection or approval.

### CI history

- Run #18 `43064874646` on commit `160987d...` completed `cancelled` after the enrichment step was cancelled when a later commit landed on the same branch (`cancel-in-progress`). `Run unit tests` and `Build pinned VPN route candidates` succeeded. Enrichment did not produce a complete artifact. This is not a test failure or evidence of no results.
- Run #19 `43065567757` on branch head `f9d6ec1...` is the current replacement run. At last check it was `in_progress`: unit tests SUCCESS; pinned candidate build SUCCESS; v38 exact-host enrichment IN PROGRESS; artifact upload pending; no artifact yet. Do not claim enrichment success until run completes and artifact/manifest are inspected.
- PR #8 remains Draft. Workflow is candidate-only; no production branches/assets affected.

## 5. PR #9 Antifilter `65444:210` BGP task

Current BGP registration page was freshly checked on 2026-11-11:
- IPv4 peer: `45.148.244.55`.
- IPv6 peer: `2001:41d0:701:1100::1db1`.
- Remote ASN: `65444`.
- Local ASN to set at the service: `64999`.
- Recommended BGP hold timer: 240 seconds.
- The current page displays 100,367 prefixes / 196,363 addresses for the combined community selection `65444:200, 65444:210`. This is the combined bundle count, not the count of community 210 alone.
- The current FAQ says lists update hourly.

Community semantics from the current FAQ:
- `65444:200`: individual IP addresses as listed by RKN without summarization.
- `65444:210`: IP addresses directly blocked by Roskomnadzor without summarization; supplied together with community 200.
- `65444:300`: `/24` summary from ipsum.lst, compatibility-only/not recommended.
- Communities 100/110 and 101–107 are different aggregated selections; they are not substitutes for exact-host communities 200/210.

AS65444 is in the private-use ASN range 64512–65534 (RFC 6996). Public BGP route collectors / HE looking glass therefore cannot reconstruct the customer community feed or prove exact 65444:210 membership. They can provide supplemental route-holder context for the 360 hostname candidates only. The exact community evidence must come from the registered session with Antifilter.

Capture state:
- Manual registration/CAPTCHA on the user's stable VPS: NOT VERIFIED.
- BGP session established: NOT OBSERVED.
- IPv4/IPv6 full route tables captured: NO.
- Count for community 65444:210: NOT MEASURED (unknown, not zero).
- Raw BGP snapshot + SHA-256: NOT AVAILABLE.

Safety: capture only in isolated BIRD 2 tables; import filter accepts only `(65444,210)`; no kernel protocol/FIB exporter; export none. Preserve session state, local public IP/ASN, BIRD version, UTC times, AFI/SAFI completeness, received/imported counts, unmodified `birdc show route ... all` text including communities, and SHA-256. A combined 200/210 peer bundle must not be treated as if all its routes have community 210; verify each route attribute.

Current PR #9 docs:
- `docs/RKN_DIRECT_IP_BGP_CAPTURE.md` — BIRD 2 configuration and capture commands.
- `docs/GEOIP_RU_V38_BGP_65444_210_CHECKPOINT.md` — checkpoint updated to note AS65444 private-use / public collector limitation.
- Latest PR #9 HEAD: `926185d897eea8a370cf939144da3d32641943c1`.
- v38 was not rebuilt. No blocked inputs, production builder or client data changed.

Once a real snapshot is provided, parse only routes that actually carry `(65444,210)`, reconcile exact prefixes/address intervals against the v38 approved blocked set, PRIVATE, and the 223 prior service-DIRECT collision queue. Direct-IP-block evidence wins at the exact affected IP/prefix. `65444:200`-only observations are resolver/list candidates; prefer domain-level handling. Absence from one snapshot is not proof of safety.

## 6. Other candidate-source status

- PVD Dog: 1,029 IPv4 `/24` candidates; not hostname→IP data. In v38 comparison: 667 `/24` fully within DIRECT; 244 partially represented or carved; 118 with no v38 DIRECT coverage. After subtracting v38 RU, PRIVATE and approved blocks, 26,689 IPv4 addresses remain outside current policy. Keep review-only; do not import all `/24`s.
- Kyoresuas Lite/Standard/Full, W1ZARDZ, HXEHEX exact host IP and Escapingworm do not justify new additions beyond v38 in the current analysis. Kyoresuas Full is a country-zone composite correlated with ipdeny, not independent service proof.
- HXEHEX broad CIDR whitelist is a large candidate-only feed and must not be bulk imported.
- PR #7 currently audits v37. Future update to v38 must be a separately scoped audit-only follow-up; watch workflow path triggers because merging docs to main can still trigger production build. Do not modify main.
- PR #6's 19 archived-invalid reconciliation rows and 56 priority rows remain REVIEW. RPKI or resource registration alone does not automatically approve/remove origin ASN entries.

## 7. Recovery instructions for the next chat

Before doing anything:
1. Read this journal from the latest HEAD of `experiment/vpn-route-candidate-build-2026-11`.
2. Re-check PRs #6–#9 metadata/draft/head SHA and only the four named branches. Do not query or inspect PR #5 or its branch.
3. Re-check `main` and `release` SHAs; stop if either unexpectedly changed and do not attempt to update them.
4. Check Actions run #19 `43065567757`. If still running, inspect exact current step. If completed, download its artifact, verify ZIP SHA-256, inspect `manifest.json`, `v38_pr8_host_ip_live_enrichment.tsv`, and `raw_lookup_responses.jsonl.gz`. Reconcile all 360 rows; report missing/error rows distinctly. No row may be auto-promoted.
5. Append a new dated entry below with run ID, head SHA, status, artifact ID/name/bytes/hash, input/output hashes, counts, failures and decision. Update the concise current-state table above only after a completed verified result.
6. Continue BGP task only after the owner supplies evidence that the CAPTCHA-protected VPS registration was completed and its session is available. Do not infer registration from chat or use public collectors as a substitute.
7. Keep PR #6–#9 Draft. No merge, Ready, production publish, release, tag or CDN action.

## 8. Append-only activity log

### 2026-11-11 — handoff recovery and PR verification

- Located and fully read Library handoff `Geoip_RU_v38_handoff_20261111_2105.md` (13,431 bytes, 136 lines). It records run #71 baseline, PR states, 360 host candidates, BGP requirements and all safety limits.
- Re-checked PR #6–#9 by GitHub PR metadata: all OPEN, DRAFT, unmerged; branches/head SHAs recorded in section 1.
- Re-checked presence of the four PR branches. PR #5/its branch were not queried.
- Re-read `main` SHA `580a25a...` and `release` SHA `d780450...`; no changes made.
- Downloaded PR #8 run #16 and PR #9 run #71 artifacts; independently checked ZIP SHA-256 values against handoff. Unzipped only to the active container for analysis.
- Reconciled 360 exact host candidates against the actual v38 protobuf and v38 approved blocked set. Source split: 315 Lib4u-only / 25 Jirnobruh-only / 20 both.
- Added PR #8 enrichment tool, test suite, compressed immutable candidate input, initial review docs and workflow step. Fixed test syntax after reading actual GitHub blob. Added hostname distribution documentation.
- Added PR #9 checkpoint clarification: AS65444 is private-use; public collectors do not replace the real customer peer session.
- Current PR #8 replacement run #19 is still `in_progress` at last check; unit tests and candidate build passed, enrichment is ongoing, no artifact available yet.
- Current Antifilter page/FAQ rechecked: exact peer IPv4 and IPv6, local ASN, hold timer, community semantics, combined 200/210 counts and hourly refresh. Public page counts are dynamic and must be timestamped; they are not an individual 210 count.
- No real BGP session or route snapshot exists. The manual registration state remains unverified.
- No changes to production refs, assets, tags, release/CDN. PRs #6–#9 remain Draft. PR #5 remains untouched.

### Next checkpoint placeholder

Append the next dated continuation here. Record exactly what was read, what was changed, GitHub commit SHA, Actions run/artifact, raw-data hashes, and any blocker. Do not overwrite prior evidence.