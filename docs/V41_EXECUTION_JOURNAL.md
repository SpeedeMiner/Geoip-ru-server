# v41 durable execution journal

## 2026-11-12 16:00 +0500 — recovery and branch setup

- Resumed from PR #12 recovery note `docs/V39_PR12_RECOVERY_20261112.md`.
- Verified main `610876b5f5cba4603dbea24c79e4a34ea2aa9792`; release `767031f305b2c26743b71cdd20a66f3575826dd2`.
- PR #12 remains Draft head `a1ef83bba5b4554caa66200498863850033a74c0`. Other open PR #5 remains owned by another agent and is **off-limits**.
- Experimental v40 branch `feature/geoip-direct-rukzby-v40-postrelease-audit` head `a80a48ad37b2490a91f8def2ef4614f7d7e221a1`; not production and not yet CI-validated.
- Confirmed v39 PR #12 candidate workflow #16 `43198572988` SUCCESS, archive artifact ID `13934486909`, GeoIP SHA-256 `b2cb548e01668eaddb85f90db19b5aa1a4af0fcaa0970f9427ba11d8f4e77d30`, RU 164,244 CIDRs. The separate v37 prefix-audit workflow remained FAILURE due to 57 priority rows vs expected 56; never change the constant blindly.

## 2026-11-12 16:10 +0500 — integrated v41 candidate staging

- Created `feature/geoip-direct-rukzby-v41-integration` directly from PR #12 head: all nine PR #12 changes are preserved as ancestry. PR #12 itself was not edited.
- Imported v40 class-aware builder/parser/validator/test sources under **v41-specific paths**; kept the original v39 patched sources and tests unchanged.
- Constructed versioned v41 corporate registry from corrected v39 company ASN entries plus seven additional v40 reviewed ASNs (AS43399, AS15632, AS59840, AS41551, AS201012, AS197482, AS49675) with exact two-class policy mapping; 49 total unique rows. AS209030 was already in corrected v39.
- Integrated v39 service protection and exact RIR-RU selected origin collection into the v41 overlay without using a background BGP connection; the complete origin list comes from the already-pinned ipverse archive in CI.
- Merged with v40 exact-vs-resolver block source layers and PRIVATE precedence; corrected exact-vs-resolver union validation to compare normalized address space rather than literal CIDR row sets.
- v41 workflow now generates `geoip_RU_v41_rir_ru_and_company_origin_prefixes.txt` via the preserved v39 extractor and adds that input to the v41 candidate builder/independent validator; service source inputs are also supplied independently.
- Added `.github/scripts/test_v41_policy_integration.py` for CORE, SHARED, RIR-RU, verified service, IPv6 and pinned-baseline precedence.
- Important: there is a **deliberate** v39/v40 policy conflict resolution: RIR-RU selected origins receive resolver-only protection, not unconditional protection from exact/legacy hard blocked addresses. The standalone corrected v39 code remains in this branch for audit.
- Disabled v41 schedule/push triggers; candidate and manual only. Main, release, tags and existing GitHub Release are unchanged.

## Next checkpoints

1. Open Draft PR for v41, run GitHub Actions candidate, investigate syntax/tests/build failures without touching other branches.
2. Independently check ZIP hashes, manifest, CIDR totals, policy invariants, source-role provenance and actual impact against published v39 and PR #12.
3. Fix any errors on the v41 branch only; document each run and code commit in this journal.
4. Review any remaining false company ASN attribution, especially affiliate-related rows, before considering release.
5. Keep the separate v37 57-versus-56 audit gate explicit; do not weaken or silently ignore it.
6. Only after successful candidate review consider a separate merge/release authorization, including disabling the legacy v39 production workflow before enabling v41 automatic publishing.

## 2026-11-12 — post-interruption resolver provenance recovery, verified v41

- Resumed at Draft PR #13 after successful but misleading candidate run `43210464555` (commit `67646e094e42ae25ee7a2e133398cc807a242b19`). Its manifest had `current_resolver_only_unique=0`, because historical resolver-source snapshots had not been passed to the new preparer.
- Reused SHA-256-verified published v38 release assets:
  - `antifilter-ip.lst` SHA-256 `c9c0656d0188f4afa740d71332b618d42b5606ab27e7561790f47b588781d1cb`;
  - `antifilter-ipresolve.lst` SHA-256 `8d8d11605a299da96006df6303a90b08b4ae25d35c1d1a199708cb83f84cdf44`;
  - `antifilter-subnet.lst` SHA-256 `2554552742bc0da516a321db66b36fa6cece28c4b3c64b66ff6d12320b33bdb6`.
- v38 approved blocked baseline remains pinned to `df909b12b985b23080075821cedc5e2f73b7b1f89abcd9950293b400ce1e4a5d`. Historic resolver entries in this exact baseline are resolver-only **only** when identified as a host IP in old ipresolve, absent from old exact ip.lst and outside old bounded subnet. Ambiguous/unclassified prefixes remain hard. Historical ipresolve can also contain non-host CIDRs (e.g. `185.104.45.0/26`); these were explicitly excluded from host-only reclassification rather than weakening blocks.
- New GitHub Actions build `43213336816` on commit `c787ac889e2a7b5f97d3b6fef158f82b21c7f9da`: **SUCCESS**, 88 Python unit tests passed; Go v37 builder, v41 overlay, independent v41 validation, protobuf read-back, candidate artifact upload all passed; publication steps skipped. ZIP artifact ID `13941149919`.
- Downloaded verified ZIP `geoip-v41-pr13-v38-provenance-fixed-20261112.zip` SHA-256 `c400bc19ae6d232c3bd4b1ac79c6754ca6473255c83e795ab2721bda4e0f7b23`. Result `geoip_RU.dat` 2,097,353 bytes SHA-256 `7d55f2bc59919052222850abd1fd1bba79e4a73d049799367122596a796ab2db`.
- Manifest: approved blocked union 199,640 CIDRs; historical/current hard/exact 57,694 CIDRs; effective resolver-only 80,755 CIDRs; blocked after policy 125,707 CIDRs; direct block exemptions 2,205 IPv4 addresses (CORE 28, SHARED resolver overlap 411; these class measurements overlap other sources and must not simply be added). `ipsum_auto_carved=false`; `PRIVATE` precedence preserved.
- Final v41 RU: 191,353 CIDRs, IPv4 address space **53,100,808**, IPv6 address space **1,205,559,204,658,091,812,677,163,847,516,160**. SHA-256 and categories independently confirmed inside downloaded ZIP.
- Exact protobuf address-space diff against corrected v39 PR #12 run `43198572988`: v41 adds **0** new IPv4 addresses and removes **5,125**; adds/removes **0** IPv6 addresses; `PRIVATE` IPv4/IPv6 identical. All 5,125 removed IPv4 addresses are present in v41 effective blocked-set; no unaccounted subtraction.
- Confirmed current PR #13 still Draft; production `main` SHA `610876b5f5cba4603dbea24c79e4a34ea2aa9792`, `release` SHA `767031f305b2c26743b71cdd20a66f3575826dd2`. PR #5 untouched.
- Separate inherited `Prefix audit validation (v37)` still fails with the previously known 57 vs 56 priority list mismatch. Its upstream quality-report source correction from PR #12 is preserved. This audit was not weakened or silently bypassed; it remains a blocker for full PR green status.
- Before release: review what changed between 56 and 57 priority audit prefixes and independently validate corporate ownership for all 49 policy ASN rows. No production merge or release authorized by this checkpoint.

## 2026-11-12 — post-review reconciliation (v41 branch only)

- Applied `3b953bb`: potential blocked-source impact now uses exact IP intervals and a union of applicable exemptions; avoids double counting when CORE/service/SHARED/RIR-RU masks overlap or already lie in effective blocks.
- Applied `d23846f`: fixed candidate workflow path filters, deduplicated the builder path, and corrected the linked source cross-check document.
- Applied `d5890a3`: synced root company ASN registry with 49 policy entries.
- Prior 88-unit-test result and 57-vs-56 gate failure described earlier refer to historical CI only. Later local review reports 92 unit tests and fixed audit scripts; new branch CI confirmation is required before treating these as GitHub-verified results.
- PR #5 and its branch are off-limits; #6–#9 stay Draft. No production/release/main changes.

## 2026-11-12 — seven-ASN v41 registry expansion (branch-only)

- Reviewed uploaded `Geoip-ru-server-v41-fixed_asn.zip`. Its local archive test suite completed `Ran 92 tests ... OK`; this is local validation, not a new GitHub Actions build confirmation.
- Imported seven origin ASNs from the supplied candidate: CORE `AS200107` (Kaspersky), `AS205638` and `AS12686` (T-Bank), `AS35022` (Gazprombank), `AS47724` (HeadHunter); SHARED `AS197068` and `AS51115` (Qrator/HLL). Qrator ASN evidence link now points to the exact ASN page, not an AS-set.
- Commits: `ff58a6a` (canonical registry), `3d8d912` (two-class ASN policy), `fbb3f19` (root registry). Did not replace the complete repository tree or older v41 workflow with the ZIP.
- Readback from GitHub verifies identical 56 ASN identifiers and rows in canonical/root registry, 56 unique policy identifiers, no duplicates, class counts CORE_CORPORATE=31 and SHARED_INFRA=25.
- Preserve the critical precedence: newly listed Qrator origins are SHARED_INFRA and remain subject to exact and subnet blocks; all five newly listed corporate origins receive CORE exemptions except PRIVATE.
- Previous 49-row v41 baseline contained 26 CORE and 23 SHARED policy rows. The seven additions bring these to 31 and 25 respectively.
- Remaining gate: perform new GitHub Actions candidate build and independently compare output manifests and binary address-space deltas. Earlier artifact hashes and CIDR counts are historical and **must not** be claimed for the expanded registry.
- No main/release/tag/production modifications; PR #5 and its feature branch untouched.

## 2026-11-12 — v41 stalled candidate, interval provenance performance fix

- Run `43223249218`, job `131199970352`, branch head `0b4bf7dd5be3764a04a1c8df8d73523a1c78b050`, remained `in_progress` on step 6, **Build unified DIRECT GeoIP RU+BY+KZ v37 with curated blocked-destination exclusions** since `2026-11-12T13:02:55Z`. At `13:18Z` the same step had run over 15 minutes, versus 4 minutes 6 seconds for the comparable successfully completed v39 run `43223248990` (`13:05:12Z`–`13:09:18Z`). The live job log API returned `BlobNotFound`, so a precise internal subcommand was not directly observable.
- Found deterministic pathological work introduced by earlier v41 provenance report correction: `normalize_interval_union(...)` of all protection masks and `subtract(...)` of blocked masks were repeated **inside** the per-prefix blocked provenance loop. That is avoidable repeated global work for roughly 100k+ source rows.
- Commit `0b05a4a7e161f59077de1fcea1195428b08f1324` precomputes (per family and hard-versus-resolver source class) the final eligible incremental impact interval masks once and uses `intersect_one_range` per row, preserving the same set difference and the existing CORE, SHARED, RIR-RU, verified-service, PRIVATE and blocked-source precedence.
- A new CI run is required to verify both runtime and exact output/manifest results. The commit intentionally supersedes the suspected stalled run via workflow concurrency `cancel-in-progress`.
- No edits to PR #5, main, release, tags, or production. PR #13 remains candidate-only.

## 2026-11-12 — successful v41 56-ASN CI and independent protobuf comparison

- GitHub Actions commit `95b9a05cfb475d7487b01c7a9915d9c5117609c3`: v41 run `43226318672` SUCCESS (artifact `13948845244`); v39 compatibility `43226318922` SUCCESS; v37 prefix audit `43226318733` SUCCESS; v41 lint `43226318862` SUCCESS.
- Downloaded v41 ZIP SHA256 `0fc92ca92e16fc032d219103732ea5d352813dfb7834343582676d5d9cd6af7d`. `geoip_RU.dat` SHA256 `383a70295024d696762839497fb4cb1cc5066443b3ea6cafa3ba84208c0a2536` (2,097,071 bytes) matches its manifest and sha256sum sidecar.
- Protobuf parsed independently; resulting categories are only `RU` (191,326 CIDRs) and `PRIVATE` (151 CIDRs). RU IPv4=53,105,937 addresses; RU IPv6=1,205,559,208,313,203,470,418,269,242,916,864 addresses. PRIVATE coverage identical to historical 49-ASN v41 candidate.
- Approved historical exact/legacy and resolver-only blocked source SHA256 inputs are unchanged, `ipsum_auto_carved=false`. Effective blocked CIDRs=125,703 (prior=125,707), exempted direct IPv4 addresses=2,209 (prior=2,205), CORE exempted direct IPv4=32 (prior=28).
- Exact parsed `RU` address-space comparison with historical v41 candidate artifact `13941149919`: IPv4 +5,385 addresses, -256 addresses, net +5,129. The removed /24 is `187.78.205.0/24`, present in old v37 base but absent from new v37 base, and not in effective blocked mask. IPv6 added=24,206,850,591,189,801,365,405,696 addresses, removed=20,551,738,933,448,695,970,004,992 addresses; net +3,655,111,657,741,105,395,400,704. These deltas **must not** be attributed wholly to the seven ASN changes because v37 base SHA changed `04d7e773...` to `37b121a5...`.
- Seven added ASN identities have exact-origin prefixes in pinned CI BGP observation data: CORE `AS200107` (31), `AS205638` (5), `AS12686` (4), `AS35022` (2), `AS47724` (2); SHARED `AS197068` (15), `AS51115` (8). These counts are raw per-ASN origin-containing selected prefix lines, not necessarily disjoint address-space contributions.
- The v41 provenance performance regression is resolved sufficiently for the end-to-end CI to complete. No production publication was performed; this remains a reviewed Draft candidate. Remaining decision: confirm readiness, compare against a controlled identical base if attribution of every changed IP to ASN policy is required, and obtain explicit merge/release authorization.

## 2026-11-12 — explicit production release authorization and workflow cutover

- User explicitly authorized final v41 release. Current Draft PR #13 remained mergeable/clean at `ed921918` with four successful checks (v41 build `43227878821`, v39 compatibility `43227879095`, v37 audit `43227878957`, v41 source lint `43227878607`).
- v39 production workflow still carried `schedule`, `push(main)` and main-branch release/release-branch publishing, while v41 lacked production triggers; merging without transition would permit competing publishers to force-push `release`.
- Commit `4d26c552` retired v39 schedule/push and explicitly disabled all three v39 main-branch publish/URL steps; kept the old workflow for manual/PR candidate compatibility checks.
- Commit `33cb6a31` enabled v41 schedule at 03:45 UTC daily and push(main); preserved v41 GitHub Release `latest-geoip-client-v41`, force-push of the artifact-only `release` branch, and explicit jsDelivr purges.
- Both workflow modifications are in the SAME v41 PR to avoid a transient dual-publisher state after merging.
- Release gate: validate lint/CI after these trigger changes, transition PR #13 from Draft, merge using expected head SHA, then independently verify v41 GitHub Release and `release` branch hashes. If CI or release fails, record the failure rather than claiming publication.
- Excluded from all operations: PR #5 and `feature/reachability-full-ru-kz-by`; PRs #6–#9 kept Draft.

## 2026-11-13 — publication and source integrity

See [v41 release hardening](V41_RELEASE_HARDENING.md). Routing-policy changes are evaluated separately. PR #5 and its head branch are out of scope.

## 2026-11-13 — v41.1 routing policy candidate

- Branch `policy/v41-1-service-and-regional` is stacked on Draft PR #17 so routing policy and source/publication hardening can be reviewed separately.
- Hard exemptions are restricted to CORE and explicitly sourced /32 or /128 service entries. A service CIDR, an Escapingworm operator whitelist entry, or a W1ZARDZ BY/KZ overlap is resolver-only. The release policy gate reconstructs allowed hard host entries separately from the overlay's mask logic.
- The exact BGP origin sidecar now consumes both RU and BY/KZ RIR ASN registries, with separate hashes. No entry or hard-block exception was added to the curated 56-ASN company registry.
- The active ip.lst classification, historical v38 baseline, review-only /24 behavior, PRIVATE precedence and public asset filenames remain unchanged. No main, release, tags, PR #5 or production changes.
- Same-input replay against the published DAT `576bf92bf1dc57a85ff5292e9dd2519f1400aabc160503721b1ae0a4431fb1eb` produced `b257cc32bb0504de1e0d9bad645b66c759e2572d7a0911897efea330859a32d8`. Independent address-space comparison: IPv4 +696 / −91 (net +605), IPv6 and PRIVATE unchanged. Existing publication envelope permits the delta. The replay admitted 333 active origins from 387 BY/KZ registry ASNs.

## 2026-11-13 — v41.2 historical host candidate

- Branch `policy/v41-2-legacy-host-reclassification` is stacked on PR #18. The existing build prepares block layers after ASN selection and uses both the regional origin and SHARED masks.
- Keep the pinned v38 approved union intact. Move only eligible regional legacy-only IPv4 /32 to resolver-only, with explicit provenance. Any current prefix covering the host vetoes the move. The rule is disabled when a current feed is missing or has tolerated invalid data.
- The original 213-host review queue used a different snapshot and required prior v34 membership. It is not an expected count for this policy or a claim about unblocking.
- Same-input replay versus PR #18 moved 268 IPv4 /32, with exactly 265 additions to DIRECT and no removals (three already DIRECT). IPv6 and PRIVATE unchanged. 259 of the 265 additions are present in the SHA-256-pinned v34 DAT used by the historical audit. The approved-union sidecar is byte-identical. Candidate DAT SHA-256: `53d235e89a9255709efd61df5c5f3c98f291398e1f94be448ee12ec24c5fadfd`.

## 2026-11-13 — v41.3 versioned publication candidate

- Branch `workflow/v41-3-versioned-publication` is stacked on PR #19. No routing policy, source list, production branch, tag or repository setting is changed by this candidate.
- Move the remaining Python heredocs and the publication/source shell logic to files. The workflow shrinks from 1,511 to 640 lines. Five RIR/IANA routing inputs regenerated from the same snapshots were byte-identical.
- Manual `snapshot_version` supports one-time `v41.N` tags. Daily jobs retain their run ID tags. The GitHub snapshot uses a create-only path, and the rolling compatibility release remains unchanged. Tests against a local bare Git remote verify fast-forward, refusal to overwrite a snapshot, and refusal to publish from a stale reference.

## 2026-11-13 — reviewed operator suballocations

- Scope is three exact IPv4 prefixes only, without adding ASN-wide rules, modifying any protection masks, or importing a mutable geofeed into the nightly build. IPv6 evidence stays out of scope.
- `153.52.151.0/24` (RU, AS402931), `179.253.86.0/24` (BY, AS207957), and `178.92.244.0/23` (KZ, AS215294) match the exact country/prefix in operator geofeed and the corresponding RDAP object. RIPE RIS observed exact announcements, and RPKI was valid for each checked pair. Registration and route visibility are not substitutes for application reachability.
- One IPv4 address in each prefix answered all three ICMP requests from each of two probes in RU, BY, and KZ. Globalping measurements: `2EVq8atmcFyKnJyqx00021UoQ` (RU prefix), `2t8jczQpf6IUEvF3v00021UoQ` (BY prefix), and `2YyCXde8KJbrFXlSs00021UoQ` (KZ prefix). No inference is made about all hosts or ports in the three prefixes.
- Expected snapshot delta relative to the published PR #21 DAT: exactly +1,024 IPv4 addresses, no removals, IPv6/PRIVATE and effective hard/resolver policy unchanged. No production publication is part of this candidate.

| Prefix | Operator geofeed | Registration | Current exact route |
|---|---|---|---|
| `153.52.151.0/24` | [ipbnb](https://api.ipbnb.com/geofeed/153.52.151.0.24.txt) | [RDAP](https://rdap.db.ripe.net/ip/153.52.151.0/24) | [RIS](https://stat.ripe.net/data/prefix-overview/data.json?resource=153.52.151.0/24) |
| `179.253.86.0/24` | [SERV.HOST](https://status.serv.host/geofeed/subnet.csv) | [RDAP](https://rdap.db.ripe.net/ip/179.253.86.0/24) | [RIS](https://stat.ripe.net/data/prefix-overview/data.json?resource=179.253.86.0/24) |
| `178.92.244.0/23` | [Lumina](https://luminabroadband.com/geofeed.txt) | [RDAP](https://rdap.db.ripe.net/ip/178.92.244.0/23) | [RIS](https://stat.ripe.net/data/prefix-overview/data.json?resource=178.92.244.0/23) |

## 2026-11-13 — Telegram DIRECT overlap

- The official Telegram [CIDR feed](https://core.telegram.org/resources/cidr.txt) contained nine IPv4 and five IPv6 ranges. The published PR #21 DAT and the initial PR #22 candidate intersected it at exactly `185.76.151.1/32`; the v37 base did not intersect it.
- The pinned HXEHEX `ipwhitelist.txt` emitted this exact host as `hxehex-mobile-hosts`, which qualified as a literal service exception and cut a hole in the already-hard `185.76.151.0/24` range. Filter conflicting HXEHEX entries before classifying service exceptions. Do not modify the upstream snapshot or the separate legacy Telegram ranges.
- All official Telegram IPv4/IPv6 ranges are non-exempt in v41 even if another DIRECT source, a corporate prefix, or a literal service rule overlaps. The strict DAT validator checks the full pinned feed, build CI compares it against the official endpoint, and the publish job checks the downloaded candidate again before pushing refs.
- Expected net change relative to the published PR #21 DAT is the same three operator prefixes (+1,024 IPv4) and removal of exactly `185.76.151.1/32`; IPv6 and PRIVATE are unchanged.

## 2026-11-13 — Moscow IPv6 PoP candidate

- Only `2001:ad0:2000:1::/64` is proposed. The [operator geofeed](https://gf.data.ee/geofeed.csv) lists this exact Moscow subnet. [RDAP](https://rdap.db.ripe.net/ip/2001:ad0:2000:1::/64) identifies the covering Moscow M9 /48; [RIPE RIS](https://stat.ripe.net/data/prefix-overview/data.json?resource=2001:ad0:2000:1::/64) sees the covering /32 from AS3327, with valid RPKI for that /32. Neither parent prefix is added.
- [IPv6 ICMP measurement](https://globalping.io/measurements/2dlik7BCSNn749dkN00021UpP) for `2001:ad0:2000:1::1` received 13/15 responses, including responses from all five RU/BY/KZ probes. This tests one address and does not establish reachability for every host or application.
- HATS /48 entries `2a13:a5c7:25bf::/48` (RU), `2a13:a5c7:2524::/48` (BY), and `2a13:a5c7:257d::/48` (KZ) were confirmed in the [operator geofeed](https://hatsnet.io/geofeed/all.csv?s=ripe_asn) and in exact RDAP objects. RIS saw only AS203314 covering /41s, valid in RPKI for the covering prefixes. None of the three sampled `::1` addresses replied to ICMP from the five probes. This does not establish that the subnets are unreachable. They are not included in this change.
- The reviewed list still gives no block exception or ASN-wide permission. The exact PoP /64 was disjoint from published DIRECT, PRIVATE, approved hard/resolver layers, and the official Telegram list. Expected fixed-input delta is one IPv6 /64 only; no IPv4 removals or additions.

## 2026-11-13 — Regional DIRECT and explicit IP evidence

- Base main `54ac34b`. Separate policy branch supersedes the per-host workaround in drafts #24 and #25 without editing either PR. PR #5, main and release are out of scope.
- Treat both Antifilter DNS feeds and v38 unverified history as advisory. Retain their pinned inputs, approved union and provenance. A current bounded subnet or a separately reviewed direct registry IP record remains hard, including inside CORE, SHARED and literal service hosts. Telegram and PRIVATE precedence remain intact.
- Classify REG.RU AS197695 as SHARED_INFRA without admitting it via the company allowlist alone. Verify exact address-space equality for the selected-origin set before/after. Check both protocol families, eight reviewed hosts, and all removals against hard evidence on fixed inputs.

## 2026-11-13 — Current mirror cross-check for PR #26

- The public official checker did not return records. Do not interpret this as an empty registry or as a check of live reachability. The dated [public registry mirror snapshot](https://registry.ctreserve.de/api/v3/snapshot/) has SHA-256 `893ca06a64e6440e5c627beb7dbb0fb812da7c0a1a3b8ce240ce72b6e468afa3` (uncompressed JSON, Last-Modified 09:18:42 UTC). Its [flat IP endpoint](https://registry.ctreserve.de/api/v3/ips/) was used only as a consistency check (SHA-256 `eae983fe3a34fcd24351a1859ab0bde181782c100fbfd57995102c5e5d12264c`). This is mirror evidence, not a signed operator export or individual live verification against the official checker.
- Compared all 7,990 proposed new IPv4 addresses. The snapshot matched 4,158 with some record, of which 742 have direct IP-only records and 3,531 have a domain/URL record, including 115 in both groups. All 742 are exact /32 entries with empty domains/URLs, status 1 in the current mirror, and decision metadata (746 address-to-record associations, 41 unique record IDs). The flat feed contains all 742 exact addresses. Individual mirror record endpoints did not provide usable detail for the old IDs, so the pinned snapshot is the evidence source.
- Entered only those exact reviewed hosts in the existing hard-evidence table. Do not import the entire mirror, treat hostname/URL matches as direct IP records, or widen matches to surrounding networks. The rest of the regional coverage and original inputs are unchanged.
- [Pinned evidence extract](v41-pr26-direct-ip-evidence-20261113.json) for the exact hosts, with mirror record IDs: 309721, 309722, 309723, 312836, 319687, 319689, 322483, 322484, 323962, 324353, 464136, 550080, 745572, 780178, 788862, 795917, 821792, 858296, 862479, 862480, 1639617, 1939194, 1939195, 1940098, 1940107, 2097494, 2238206, 2257807, 2268787, 2296707, 2311636, 2311682, 2311696, 2318151, 2421508, 2478377, 2689066, 2991346, 3085579, 3591646, 3787019.
- Fixed-input replay expectation versus the published snapshot: IPv4 +7,248 / -6, IPv6 and PRIVATE unchanged. Tilda, REG.RU and the eight earlier service controls should remain in DIRECT. PR #26 stays Draft, and no merge or release is part of this check.

## 2026-11-13 — Separate exact regional admission correction

- Draft PR #26 follow-up. The 99 blocked Leaseweb-origin hosts are in one BY-delegated /22 whose six more-specific DE assignments cover every address. Two RU-delegated prefixes announced by the same origin have exact DE assignment records. See [regional admission policy and RIPE evidence](GEOIP_RU_V41_POLICY.md#reviewed-regional-admission-conflicts).
- Scope is `185.49.68.0/22`, `185.17.120.0/22` and `195.54.32.0/23` only. Keep all RIR/source inputs, the 742 reviewed IP-only exclusions, the effective RKN mask, IPv6, PRIVATE and other AS28753 coverage unchanged.
- Fixed-input replay must show exactly 2,461 IPv4 removed relative to prior PR #26 candidate and IPv4 +7,223 / -2,442 versus the published snapshot, with both IPv6 and PRIVATE unchanged. No merge or production publication in this step.

## 2026-11-13 — Broader regional admission review

- Screened 19,402 observed IPv4 routes overlapping the regional inventory. The most-specific route screen found 993 prefix/region pairs covering 573,952 addresses in the previous draft. Foreign origin metadata alone is insufficient. HOSTKEY AS50867 is a counterexample with RU records and Moscow infrastructure. No bulk or ASN-wide exclusion is applied.
- Checked the first 35 candidates against RIPE RDAP and RIS. Promote only the three independently corroborated exact assignments inside `145.249.0.0/16` in this batch. SY and DE records and matching current origins are documented in the policy. Remaining candidates are unchanged.
- Previous draft head `5b15ef8`. Expected exact delta to its DAT: IPv4 -26,624 only. Preserve 38,912 other addresses in the /16, including all 32,768 addresses in the Kazakhstan /17, plus IPv6, PRIVATE, RIR inventory and all block policy masks. No merge or publication.

## 2026-11-13 — Exact US assignments in RU and KZ parent allocations

- Draft PR #26 head before this check: `3319960`. RIPE RDAP child records and the RIS 2026-11-13T08:00Z view support only `31.204.8.0/21` (RU parent, US-FIXED, AS209372) and `109.238.168.0/21` (KZ parent, IPXO with two covering US /22 assignments, AS26548) in this batch. Both exact routes were seen by 319/319 RIS peers without more-specifics.
- Preserve `31.204.2.0/24` (RU assignment, same origin), `109.238.160.0/21` and all other IPv4 coverage outside the two /21s. Leave `212.124.96.0/19` unchanged: a DE value on the allocation and a CH origin do not settle the relationship to the RU registrant MnogoByte at child level.
- Fixed-input replay expectation: IPv4 -4,096 only relative to the previous draft, and IPv4 +7,223 / -33,162 versus the published DAT. No changes to IPv6, PRIVATE, RIR inventory or hard/resolver/effective block masks. No merge or publication.

## 2026-11-13 — PR #26 release checkpoint

- Exact new regional admission exclusions: `31.204.16.0/21` (US), `31.204.32.0/20` and `31.204.56.0/21` (AU), and `212.124.106.0/24` (US). See the policy for child routes, RDAP and operator geofeed evidence. Keep `31.204.28.0/22`, the rest of MnogoByte and the unresolved review queue unchanged.
- Exact delta to previous candidate `4c0c913`: IPv4 -8,448 only. Prior rolling DAT comparison: +7,223 / -41,610 IPv4, IPv6 and PRIVATE unchanged. The input inventory and block masks must match the previous candidate byte-for-byte.
- Align the rolling release description with the effective v41 policy. Release via the existing main-push workflow only after matching the fixed-input and PR builds. Verify the production workflow, rolling DAT, immutable snapshot and release-branch DAT after publication. Do not touch PR #5.

## 2026-11-13 — Follow-up on exact operator routes and workflow edge cases

- Starting point is the published PR #26 snapshot. Keep the same four reviewed operator rows and give only those exact CIDRs resolver-only protection. The overlay validator and independent hard/publication gate verify the input digest and coverage after PRIVATE, explicit hard blocks and reviewed regional exclusions.
- Geography-only source rows retain existing eligibility. Do not add v2fly/Loyalsoldier to the exemption mask, change operator rows or touch PR #5.
- Normalize upstream BGP and legacy RIR IPv6 host bits at the supplied prefix length and count normalizations. Keep project-maintained policy TSVs strict.
- Pass the BY/KZ ASN inventory into the compatibility-only v39 mask. Fix release-ref working-directory handling and fail before invoking gh when any snapshot asset is missing, unreadable or empty.

## 2026-11-13 — Geography-only cohort follow-up

- The pinned v2fly/Loyalsoldier, v41 block and regional RIR/BGP inputs identify 961 IPv4 and zero IPv6 candidates. The pinned ipverse archive assigns 297 addresses to the two Cloudflare origins AS13335/AS209242, while 63 have no covering route in that archive. No ASN-wide exception or geolocation-source protection is granted.
- In the dated public registry mirror, 649 addresses have an active domain/URL record, 310 have no active match and four have an exact active IP-only record. Two of the latter also match domain/URL records. Keep only the four exact IP tokens as reviewed hard evidence, without inferring that the mirror is official or signed. See [the evidence extract](v41-geo-only-exact-ip-evidence-20261113.json).
- Restore only the 110 addresses previously lost to advisory DNS evidence inside six exact independently reviewed operator ranges. The rest of each of these ranges was already in DIRECT. See [the routing policy evidence](GEOIP_RU_V41_POLICY.md#reviewed-operator-prefixes-and-geography-only-inputs). Do not extend by ASN, BGP aggregate, tenant, geolocation feed, or registry absence alone.
- Hold HOSTKEY and TIME-HOST and other mixed-location rows for individual checks. In particular IHOR geolocated-RU origin space contains assignments in both RU and FI. Leave all unresolved rows unchanged. No PR #5 work or production publication.

## 2026-11-14 — Second exact geography-only review

- Start from PR #27 head `e17846c`. Selected 22 exact RU assignments across HOSTKEY (2), FIRSTSERVER (10), IHOR/PSERVERS (6), TIME-HOST (4). This keeps the existing 32-row operator cap (10 + 22). Prioritize exact corroboration and greater observed DIRECT recovery. See [pinned evidence](v41-geo-only-operator-evidence-20261114.json). No BGP aggregate or ASN-wide exception.
- Expected incremental DIRECT delta: +85 IPv4 (2 + 42 + 17 + 24), no removals, zero IPv6/PRIVATE change. The hard masks and registry evidence remain unchanged. Verify `185.174.138.82/32` stays hard and both RU/FI-conflicting IHOR candidate prefixes remain unapproved.
- Unmodified from the remaining cohort: 762 IPv4. Draft only. No changes to main, the release, or PR #5.

## 2026-11-14 — Bounded expansion of the reviewed operator table

- Start from PR #27 head `84c48c7`. Raise the row ceiling from 32 to 64, test both sides of the boundary, and retain the minimum /23 IPv4 and /64 IPv6 prefix lengths, overlap checks, exact manual scope and both publication validators.
- Add six exact RU FIRSTSERVER assignments and ten IHOR/PSERVERS assignments with matching registry-linked geofeeds and complete same-origin RIS coverage. The three IHOR /23 rows without an exact route are covered by their paired /24 announcements. Expected delta is +19 IPv4 (6 FIRSTSERVER, 13 IHOR), no removals and no changes to IPv6, PRIVATE, hard or regional-exclusion masks. Evidence is [pinned here](v41-geo-only-operator-followup-20261114.json).
- Keep mixed RU/FI IHOR entries unchanged. Also leave `62.3.58.0/24` unchanged: its exact RIS announcement and RU assignment description do not make the RDAP assignment covering .0 through .254 an exact /24. PR #27 stays draft. No production or PR #5 change.

## 2026-11-14 — Fourth exact geography-only review (RU/KZ)

- Start from PR #27 head `95c0360` and recover the 743-address remainder from the pinned v2fly/Loyalsoldier files, previous CI artifact and pinned ipverse archive. Reproduce the previous DAT and effective block sidecar from fixed inputs.
- [Evidence](v41-geo-only-operator-rukz-20261114.json) records 30 verified /24s. Use the 16 existing table slots for the highest observed cohort recovery, breaking ties by numeric network address. Keep the 64-row cap. Approve 15 RU and one KZ exact assignments, with expected DIRECT delta +59 IPv4, no removals, no changes to IPv6, PRIVATE, or higher-priority masks.
- Keep the other 14 verified /24s (14 cohort IPv4 addresses) unmodified. The CY-assigned `194.67.193.0/24` alone accounts for 44 unchanged addresses. Total unresolved or deferred: 684 IPv4. Draft only. No production, release or PR #5 changes.

## 2026-11-14 — Finish PR #27 for production

- Start from verified draft head `1a50c3e` and admit all 14 deferred exact /24s listed in [the evidence file](v41-geo-only-operator-rukz-20261114.json). Raise the reviewed-row ceiling from 64 to 80 for 78 entries. The existing regression tests exercise the accepted and rejected boundaries. No changes to the prefix admission criteria or hard/PRIVATE/Telegram precedence.
- Expected policy-only delta for this final batch: +14 IPv4, no removals and no IPv6 or PRIVATE changes on the same inputs. Keep the other 670 unresolved addresses in the original cohort unchanged. Compare production separately because its upstream BGP and Antifilter sources move.
- Publish through the existing v41 workflow after PR checks. Verify the rolling asset, versioned snapshot, release branch, and their checksums. PR #5 is outside scope.

## 2026-11-14 — Post-release exact operator check

- Start from published DAT `66f3dbe3bcebad386207d026b5e7ebbd7113a1d45d86420996d7dc0742112166`. All 670 addresses left in the original cohort still intersect effective resolver-only policy outside DIRECT.
- [Evidence](v41-geo-only-operator-post-release-20261114.json) verifies eight exact RU prefixes. Admit only `31.76.6.0/24` and `45.90.216.0/23` using the last two slots. The FIRSTSERVER /23 is exactly covered by two AS205090 /24 announcements. Expected fixed-input delta is +4 IPv4 only. No change to hard precedence or the 80-row limit.
- Six other exact prefixes remain documented but unadmitted. Leave the broader FIRSTSERVER /24 over a confirmed /25 and the Dutch 3NT neighbor of the existing KZ exception unchanged. No ASN-wide admission. Draft only.

## 2026-11-14 — Complete the confirmed post-release queue

- Start from draft PR #28 head `80f4810`. Recheck exact RIPE assignments, linked operator geofeeds and RIS for the [six remaining verified routes](v41-geo-only-operator-deferred-confirmation-20261114.json).
- Raise the bounded manual table from 80 to 96 for 86 entries. No changes to exact-prefix eligibility or higher-priority exclusions. Expected fixed-input effect is +6 IPv4 against the prior draft and +10 against the published v41. The other 660 addresses in the original cohort remain unchanged. No publication or PR #5 changes.

## 2026-11-14 — Exact Gcore and EDIS assignment review

- Start from draft PR #28 head `c9cf96f` and the previous fixed-input CI artifact. Add 6 exact assignments from [the evidence](v41-geo-only-operator-gcore-edis-20261114.json) under the existing 96-row bound. Expected policy-only DIRECT delta +11 IPv4 versus the prior candidate, +21 versus published v41.
- Do not extend Gcore protection to the surrounding /22: exact registry objects and geofeed list LU and US for the other /24s, despite the same current RIS origin. Defer RU-labelled ranges lacking a usable registry-linked geofeed or exact routing evidence. No publication or PR #5 changes.

## 2026-11-14 — Exact assignments in mixed-origin networks

- Start from draft PR #28 head `0bdc266`. Verify 7 exact RU assignments in the 649-address remaining DNS-only cohort by RIPE, registry-linked operator geofeeds and RIS. See [prefix evidence and hold decisions](v41-geo-only-operator-mixed-origin-20261114.json).
- The candidate now holds 99 rows under a 112-row bound. Expected +12 IPv4 versus the previous candidate, +33 versus the released DAT on fixed inputs. Hard exclusions, IPv6, PRIVATE and all address space outside the target cohort stay unchanged.
- Keep the foreign Xorek and Nuxt siblings, Finnish PSERVERS assignment and the FIRSTSERVER origin disagreement unmodified. No production or PR #5 changes.

## 2026-11-14 — Registry re-screen on fixed inputs

- Start from draft PR #28 head `5ae27ee`. Reproduced both previous PR artifacts byte-for-byte (DAT and effective mask). The seven preceding assignments restore exactly 12 IPv4 addresses. The draft was +33 IPv4 versus the published DAT.
- The [re-screen](v41-geo-only-operator-ripe-rescreen-20261114.json) recalculates 638 IPv4 and zero IPv6 outside DIRECT in the resolver-only geography cohort. That is one more than the earlier journal tally, not an extra DIRECT delta. Screened all 121 IPv4 /24 buckets via RIPE RDAP and retried errors against the IANA-bootstrap registries.
- Add four exact prefixes supported by RIPE RDAP, registry-linked geofeeds and exact same-origin RIS. The existing 112-row cap is unchanged (103 rows). On identical inputs, only four /32s return to DIRECT, with zero removals and no changes to IPv6, PRIVATE, hard or raw resolver inputs. This is +37 IPv4 versus published v41. Candidate DAT SHA-256 `8311e0072cd51e5ec68cf61541bdd6848ca2d208cf615ebb56b16ba3f712ff76`.
- Next, check the ARIN Kazakhstan reassignments and exact Russian ARIN records found by the fallback separately. Keep registry-only assignments, inaccessible geofeeds and the unresolved FIRSTSERVER origin disagreement unchanged. Draft only. No production, release or PR #5 changes.

## 2026-11-14 — Exact ARIN Kazakhstan reassignments

- Start from draft PR #28 head `eca7b16`. [CI](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43568893438) passed and publication was skipped. The DAT and effective mask matched the local fixed-input replay byte-for-byte.
- [ARIN, 3NT geofeed, RIS and pinned BGP evidence](v41-geo-only-operator-arin-kz-20261114.json) corroborates eight exact AS58061 /24s in Kazakhstan. Admit just these rows, bringing the table to 111 out of 112 without raising the cap. Keep the corroborated /22 and RU registry-only records unchanged.
- Verified fixed-input delta: +20 IPv4 versus the previous draft and +57 versus published v41. No removals, IPv6, PRIVATE or hard-mask changes. 614 IPv4 remain outside DIRECT in the recalculated review cohort. DAT SHA-256 `d163e934c89519e3812552fb2ca842b7498db13e9615672f71d4ed141ee2122b`. Draft only. No production, release or PR #5 changes.

## 2026-11-14 — Close the frozen resolver-only queue

- Reconstructed the exact cohort from the `0cda10e` CI artifact and pinned inputs. Reviewed all 614 IPv4 across 109 buckets, with registry and RIS evidence for every bucket and 126 per-address registry checks for covering or more-specific allocations and non-RIPE fallbacks. [Decision ledger](v41-geo-only-queue-decisions-20261114.tsv) has no unclassified addresses. Its 612 hold decisions are snapshot-specific and make no claim of permanent exclusion or lack of reachability.
- Admit `193.162.143.0/24` (AS205090) only. The two Moscow /25 child assignments cover all 256 addresses and match the linked operator geofeed. Exact RIS BGP state has 379 paths with the same origin and the route is RPKI-valid. Preserve the existing /23 scope rule and 112-row table limit. Separately hold `185.180.230.0/24`: RIS BGP state saw two exact origins, both authorized by ROAs. [Evidence and totals](v41-geo-only-queue-closure-20261114.json).
- Fixed-input DAT changes only `193.162.143.13/32` and `193.162.143.254/32` to DIRECT. This is +2 IPv4 versus the prior PR head and +59 versus published v41, without removals or changes to IPv6, PRIVATE, hard or raw resolver inputs. All 14 official Telegram ranges remain outside DIRECT. Candidate SHA-256 `8d807b8d6069791b2e006bc561c4c69cc1a3172521cde0271c62b9305ce1c391`. No main, release or PR #5 changes.

## 2026-11-14 — Keep prefix audit correct with unobserved pins and new RPKI results

- Both audit queues recognize `AS212066[Yandex][STATIC-DIRECT]` and `AS212066[Yandex+STATIC-DIRECT]`. Extraction reports observed company origins separately from the unique selected company layer, including pins. The audit reads the selected-company metric and also reconciles older reports against exact static-only rows. No selected or global prefix output, DIRECT rule or pin changed.
- The v37 reconciliation seed still requires the same 19 prefixes and all 20 exact prefix/origin pairs, checked against [the archived audit artifact](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43383174561/artifacts/14016919373). Extra `invalid_asn` pairs, including a new origin on a seeded prefix, go to `unseeded_rpki_invalid_review.tsv` as REVIEW. CI requires the exact current-minus-historical pair set. Historical losses, status drift or inconsistent triage still fail.
- Verification uses the PR #28 production snapshot, a copy of its ipverse archive with both AS212066 pins removed, and the historical evidence artifact. No production publication is part of this change.

## 2026-11-14 — Additional-source resolver exclusions after PR #29

- Baseline is main `2ef37c4`, release `c605a38`, [production run 43579021611](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43579021611), DAT SHA-256 `8d807b8d6069791b2e006bc561c4c69cc1a3172521cde0271c62b9305ce1c391`.
- Reconstruct v37 additional-feed eligibility **before** the block carve using the production-pinned Grimbird, Digne, Davoyan and Golukon inputs. Grimbird+Digne count as one logical group. Subtract already-trusted sources and selected ASN coverage to avoid re-opening the previously reviewed geography-only cohort.
- Check only effective resolver-only exclusions outside DIRECT, PRIVATE, hard, Telegram and explicit regional admission exclusions. Require exact independent evidence before changing coverage. Work stays on this branch, outside PR #5 and production. Next checkpoint: record reconstructed address-space totals and exact candidates.
