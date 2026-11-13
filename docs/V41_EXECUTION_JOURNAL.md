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
