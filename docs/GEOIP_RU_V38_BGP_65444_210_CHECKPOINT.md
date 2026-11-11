# Antifilter.network BGP snapshot checkpoint — community 65444:210

**Checkpoint date:** 2026-11-11 UTC  
**Project branch:** `feature/geoip-direct-rukzby-v38`  
**PR:** #9 — Build v38 unified RU+BY+KZ DIRECT GeoIP with RKN-only carve-outs  
**Branch base before this checkpoint:** `a19e4de1d7a550f15fbc6960a81e924225fc1437`  
**Build state:** v38 candidate build already passed; do not rebuild it merely to resume this task.

## 1. Resume point and objective

Continue the v38 source audit without registering a BGP session. The alternative is a pinned public-list cross-check using existing Antifilter inputs, the separate `bol-van/rulist` `reestr_ipban4.txt` and `reestr_resolved4.txt` snapshots, and prebuilt secondary GeoIP lists.

The BGP route snapshot would provide stronger community-level evidence, but registration is not required to build or release v38. No membership in community `65444:210` is claimed or inferred. Current approved blocked inputs remain unchanged unless a separate exact-prefix review authorizes a change.

## 2. Confirmed community semantics

The Antifilter.network BGP page and FAQ were checked on 2026-11-11:

- `65444:200`: unsummarized host-IP list.
- `65444:210`: subset classified by Antifilter.network as directly blocked by Roskomnadzor; announced together with `65444:200`.
- `65444:300`: /24 summary; not suitable for this exact-IP audit and must not be substituted.

The provider page currently shows the selected `65444:200, 65444:210` bundle as 100,367 prefixes / 196,363 addresses (observed 2026-11-11, current page fetch). This is a combined display count and must **not** be attributed to community 210 alone. The FAQ says the lists refresh hourly, so counts should always be timestamped. The FAQ distinguishes the two communities: 200 is the wider unsummarized host-IP set; 210 is the unsummarized subset classified as directly blocked and is announced together with 200. The same FAQ documents additional summarized communities (100–107 and 110); do not silently substitute those for the required exact-host 200/210 bundle.

Source pages (checked 2026-11-11):
- https://antifilter.network/bgp
- https://antifilter.network/faq
- https://bgp.he.net/AS65444

**Public BGP visibility limitation:** AS65444 is marked as a private-use ASN reserved under RFC 6996 by public BGP lookup services. Public RIPE RIS / HE / bgp.tools queries therefore cannot be used to reconstruct the Antifilter customer feed or prove membership of an exact prefix in community 65444:210. They may provide unrelated supplemental origin/holder context for candidate IPs, but only the registered peer session to the Antifilter service can provide the community-bearing route attributes. The number of prefixes shown on the public registration page is not a route snapshot.

The feed is a third-party classification, not a direct official RKN API. The repository policy and source registry already express this limitation.

## 3. Optional BGP path (not a release dependency)

The Antifilter registration page previously checked advertised:
- Neighbor: `45.148.244.55`
- Remote ASN: `65444`
- Suggested local ASN: `64999`
- Recommended BGP hold time: `240` seconds

These are reference facts only. The CAPTCHA-protected registration flow requires a stable public endpoint; this project will **not** depend on the user obtaining a VPS or public IP for v38. Public BGP collectors cannot reconstruct private-AS community attributes. The no-BGP replacement is the pinned public-list cross-check in `docs/V38_PUBLIC_RKN_SOURCE_CROSSCHECK.md`.

**Registration state:** NOT VERIFIED / NOT REQUIRED FOR V38 RELEASE.  
**BGP session state:** NOT ESTABLISHED / NOT OBSERVED.  
**Community 65444:210 route count:** NOT MEASURED.  
**Raw BGP route snapshot:** NOT CAPTURED.  
These are unknown/unavailable states, not zero routes. No exact community membership is inferred from public list overlap.

## 4. Safe capture design

Use BIRD 2 with isolated IPv4 and IPv6 tables. Import only routes carrying `(65444,210)`. Do not install a kernel protocol/exporter, do not add routes to the OS FIB, and do not export to any peer.

The full configuration and operational commands are in `docs/GEOIP_RU_V38_POLICY.md`, section 4, and the original capture procedure introduced by commit `a19e4de1d7a550f15fbc6960a81e924225fc1437`.

Capture must preserve:
- UTC start/end timestamps;
- registered local public IP and local ASN;
- BIRD version;
- peer IP/ASN and protocol/session state;
- IPv4 and IPv6 received/imported route counts;
- whether import limits or any AFI/SAFI coverage limits were reached;
- complete `birdc show route ... all` outputs including BGP attributes/communities;
- SHA-256 for each raw output and a manifest tying hashes to capture metadata.

Before accepting the snapshot, independently verify that every retained route carries community `65444:210`. Keep the unfiltered/session-level diagnostics separately where available, but never mix `65444:200`-only routes into the direct-block set. Capture the selected announcement bundle exactly as registered and preserve the attributes as delivered by the peer; do not infer that every route in the combined 200/210 group is tagged 210.

## 5. Reconciliation after capture

Compare exact canonical prefixes and address intervals against:
1. the v38 approved blocked set derived from the existing Antifilter Download exact-host inputs and bounded subnet policy;
2. the v38 DIRECT prefix provenance, including RIR and named-service sources;
3. PRIVATE precedence and IANA global-reachability exceptions.

Required review classes:
- community-210 prefix already blocked in v38;
- community-210 prefix not blocked in v38 (candidate for review, not automatic addition);
- current ip.lst/ipresolve.lst host absent from the complete community-210 snapshot but present in community 200 only (resolver/host candidate; do not infer safe DIRECT);
- overlap with v38 service-DIRECT provenance (collision requiring explicit block-vs-service review);
- invalid, malformed, noncanonical, duplicate, aggregate/covered, or otherwise ambiguous route evidence.

Absence from one snapshot is not proof that a prefix is safe for DIRECT. Preserve exact route attributes and source timestamps. Domain-only restrictions remain domain-level work and must not be expanded to shared-IP CIDRs.

## 6. Work performed in this checkpoint

- Re-read `docs/GEOIP_RU_V38_POLICY.md` and `docs/GEOIP_RU_V38_SOURCE_REGISTRY.tsv` on the v38 feature branch.
- Confirmed that isolated BIRD capture remains documented as an optional future evidence path; the no-BGP public-list cross-check is the active v38 fallback and BGP is not a release gate.
- Confirmed PR #9 branch HEAD before this checkpoint: `a19e4de1d7a550f15fbc6960a81e924225fc1437`.
- Confirmed that commit's PR workflow run #71 (`43050025980`) completed successfully.
- Verified current Antifilter.network page/FAQ community semantics and current peer details.
- Checked public AS65444 visibility and confirmed its private-use ASN status; public collectors cannot substitute for the actual 65444 customer session.
- The user explicitly requested v38 be brought to release. No production branch, release, tag, GeoIP binary or CDN asset has been changed by this feature-branch work.

## 7. No-BGP fallback and current release decision

BGP registration is **not a blocker**. The public fallback and exact comparison are maintained in `docs/V38_PUBLIC_RKN_SOURCE_CROSSCHECK.md`.

Pinned `bol-van/rulist` commit `f9ea9704544590bf0aff817acc73b7e00261a849` (2026-11-08T07:21:01Z) separates `reestr_ipban4.txt` from `reestr_resolved4.txt`. In the 360 Lib4u/Jirnobruh residual candidates, 17 IPs are contained by 11 ipban4 CIDRs (none is an exact /32 source row); 9 are in resolved4, with 8 overlapping ipban4. All 360 stay REVIEW because matches include shared cloud/CDN prefixes and do not reproduce community 65444:210.

PR #8 run #23 (43067107469) completed unit tests, candidate build, all 360 RIPE enrichment rows and artifact upload successfully. All 360 candidates have a route observed; 318 have RPKI valid and 42 unknown. RDAP did not provide usable holder results. Full hashes and source caveats are in the public cross-check document.

**Release position:** v38 uses the existing approved exact-host and bounded-subnet inputs; no BGP registration or snapshot is required for release. Do not expand /24, /22 or cloud/CDN ranges from an aggregate. Keep unresolved host-IP candidates outside DIRECT until a distinct exact-prefix decision is supported.

## 8. Safety boundary

The user has now explicitly requested that v38 be brought to release. This supersedes the earlier hold on PR #9 only. Do not modify PR #5 or branch `feature/reachability-full-ru-kz-by`; do not change, ready or merge PRs #6–#8. Do not include their changes in PR #9. The only production publication permitted by this updated instruction is the v38 release resulting from PR #9, after its current candidate build succeeds and the resulting artifact is verified. The release workflow must publish from `main` only.

## 9. Cross-chat recovery journal

The detailed append-only project history and current PR #6–#9 inventory are maintained in [`docs/PROJECT_EXECUTION_JOURNAL.md`](https://github.com/SpeedeMiner/Geoip-ru-server/blob/experiment/vpn-route-candidate-build-2026-11/docs/PROJECT_EXECUTION_JOURNAL.md) on the PR #8 review branch. Read that journal before continuing in a new chat. Its latest recorded PR #8 run #19 state must be refreshed from GitHub Actions before relying on it.
