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
- Constructed versioned v41 corporate registry from corrected v39 company ASN entries plus seven additional v40 reviewed ASNs (AS43399, AS15632, AS59840, AS41551, AS201012, AS197482, AS49675) with exact two-class policy mapping; 48 total unique rows. AS209030 was already in corrected v39.
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
