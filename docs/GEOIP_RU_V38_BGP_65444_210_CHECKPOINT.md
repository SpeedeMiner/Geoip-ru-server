# Antifilter.network BGP snapshot checkpoint — community 65444:210

**Checkpoint date:** 2026-11-11 UTC  
**Project branch:** `feature/geoip-direct-rukzby-v38`  
**PR:** #9 — Build v38 unified RU+BY+KZ DIRECT GeoIP with RKN-only carve-outs  
**Branch base before this checkpoint:** `a19e4de1d7a550f15fbc6960a81e924225fc1437`  
**Build state:** v38 candidate build already passed; do not rebuild it merely to resume this task.

## 1. Resume point and objective

Resume at acquisition of a timestamped Antifilter.network BGP RIB snapshot filtered to standard community `65444:210`.

The objective is to distinguish the provider's classification of directly blocked IP addresses from the wider unsummarized host-IP list. This snapshot is review evidence only. It does not authorize changing the v38 blocked set, DIRECT output, production builder, release assets, or policy.

## 2. Confirmed community semantics

The Antifilter.network BGP page and FAQ were checked on 2026-11-11:

- `65444:200`: unsummarized host-IP list.
- `65444:210`: subset classified by Antifilter.network as directly blocked by Roskomnadzor; announced together with `65444:200`.
- `65444:300`: /24 summary; not suitable for this exact-IP audit and must not be substituted.

The provider page currently shows the selected `65444:200, 65444:210` bundle as 100,366 prefixes / 196,360 addresses. This is a combined display count and must **not** be attributed to community 210 alone. The FAQ distinguishes the two communities: 200 is the wider unsummarized host-IP set; 210 is the unsummarized subset classified as directly blocked and is announced together with 200. The same FAQ documents additional summarized communities (100–107 and 110); do not silently substitute those for the required exact-host 200/210 bundle.

Source pages (checked 2026-11-11):
- https://antifilter.network/bgp
- https://antifilter.network/faq
- https://bgp.he.net/AS65444

**Public BGP visibility limitation:** AS65444 is marked as a private-use ASN reserved under RFC 6996 by public BGP lookup services. Public RIPE RIS / HE / bgp.tools queries therefore cannot be used to reconstruct the Antifilter customer feed or prove membership of an exact prefix in community 65444:210. They may provide unrelated supplemental origin/holder context for candidate IPs, but only the registered peer session to the Antifilter service can provide the community-bearing route attributes. The number of prefixes shown on the public registration page is not a route snapshot.

The feed is a third-party classification, not a direct official RKN API. The repository policy and source registry already express this limitation.

## 3. Current peer and registration facts

The current registration page advertises:
- Neighbor: `45.148.244.55`
- Remote ASN: `65444`
- Local ASN requested by the service: `64999`
- Recommended BGP hold time: `240` seconds

The registration form is CAPTCHA-protected. A stable VPS public IPv4 and local ASN `64999` must be registered manually, selecting the exact-host announcement that includes communities 200 and 210. Do not select the /24 summary. Use the peer details shown by the registration page at the time of registration; do not copy stale peer data from older examples.

**Registration state:** NOT VERIFIED in this checkpoint.  
**BGP session state:** NOT ESTABLISHED / NOT OBSERVED.  
**Route count for community 210:** NOT MEASURED.  
**Raw route snapshot:** NOT CAPTURED.  
These are unknown/unavailable states, not zero routes.

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
- Confirmed the v38 policy already specifies isolated BIRD capture and explicitly freezes the approved blocked set until a timestamped snapshot is captured and validated.
- Confirmed PR #9 branch HEAD before this checkpoint: `a19e4de1d7a550f15fbc6960a81e924225fc1437`.
- Confirmed that commit's PR workflow run #71 (`43050025980`) completed successfully.
- Verified current Antifilter.network page/FAQ community semantics and current peer details.
- Checked public AS65444 visibility and confirmed its private-use ASN status; public collectors cannot substitute for the actual 65444 customer session.
- No v38 build was rerun. No production branch, release, tag, GeoIP binary, DIRECT policy, blocked set, or other PR was changed.

## 7. Next action / blocker

**Next action:** complete the manual CAPTCHA-protected registration for the stable VPS, using local ASN `64999`, and record the registration confirmation and current peer details. Then establish the isolated BIRD session and capture the complete timestamped IPv4/IPv6 RIB.

No snapshot can honestly be reported until the registered BGP session has been observed as established and the route tables have been exported and hashed. If registration is not yet complete, the next operator input required is the registered VPS/public-IP confirmation and the peer details shown after registration.

## 8. Non-negotiable safety boundary

This checkpoint is evidence acquisition only. Do not change `geoip_RU.dat`, the production builder, blocked inputs, v38 manifest, `main`, `release`, tags, CDN assets, or the release workflow as part of capture. Keep PR #9 Draft. Keep PRs #5–#8 separate and untouched. No merge or production publish is requested.
