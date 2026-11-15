# v41 audit execution journal

## 2026-11-15 — phase A, checkpoint 1

- Authorized scope: execute the attached audit plan in sequence, using a separate branch and a Draft PR. No production publication, merge or admission-policy change.
- Branch: `audit/v41-phase-a-iterator-oracle`.
- Code baseline: `38f36820f0e10066f7beb7eed97b00ec36c43820`.
- Remote refs rechecked before work: main `38f36820f0e10066f7beb7eed97b00ec36c43820`, release `79bddd4c51a36a8d3c2771e234e5171f574104c8`, cdn `8a226b83c82323c869054ca5b299612ad3a91e2d`.
- Historical snapshot: `geoip-v41-snapshot-43712216767.1`, source code matches the baseline above. Its `geoip_RU_v41_release_manifest.json` binds the DAT, both SRS, provenance and four retained input archives. Earlier comparison snapshot: `geoip-v41-snapshot-43709200004.1`, release commit `a23b381e4844ed4cb84bf67e1f5984027e68769c` (independently pinned in compare-v34-v41.yml).
- Published DAT SHA-256: `b17fe26ccdcb8d272e6233ec9686a514b309e9d75e75653313a75f329b70fae7`; 512533 bytes; 17700 IPv4 and 15111 IPv6 RU CIDRs.
- Published RU SRS SHA-256: `c60b8a1de5d4d67478850d7f72b272044f536d7d592591fbbf75ac50129002b1`.
- Published PRIVATE SRS SHA-256: `b9ea6381ea61e286298aea76c10cb85a252ff0d20c49d6de3527be1353c107c4`.
- Upstream archive SHA-256: `c2b6209c806d3c066ee77854affe5756e34db9d8e3766f00e8a3877354086742`; downloaded and verified during preceding audit.
- Regression first added to the unmodified baseline: 7 tests, 3 failures (including IPv6-only iterator and mixed-family iterator). Log: `FAILED (failures=3)`. Ordinary lists/sets retained IPv6.
- Production patch: materialize `collapse()` input once; no changes to ordering, masks, categories or output encoding.
- New independent interval oracle enumerates small address sets for both families (400 deterministic trials), plus exact large IPv6 subtraction and boundary host cases.
- Python wire compatibility uses the existing independent publication reader; companion Go test uses actual upstream generated v2fly types pinned by go.mod/go.sum (`v5.56.0`, protobuf `v1.36.12`). No new Python dependencies.
- Targeted Python checks: 10 tests PASS after patch. Go tests PASS with isolated Go 1.26.10. The system `/usr/bin/go` is not the compiler; do not use it for replay.
- sing-box 1.13.12 archive downloaded and verified against the workflow SHA-256 `1540533adb3df24f5ad5f14b5c7ca3dbc2401b10a1c1eb278fcadcada47ec6c4`.
- CI: not submitted yet. Fixed-input full replay and manifest verification pending. No claim that the released DAT lost IPv6.
- Next: verify all snapshot assets, rebuild the base/overlay on the same inputs, compare DAT and SRS, then save evidence and open Draft PR. Phase B follows phase A acceptance evidence.
