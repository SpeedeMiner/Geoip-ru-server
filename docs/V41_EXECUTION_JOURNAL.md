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
