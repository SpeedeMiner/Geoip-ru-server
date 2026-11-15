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

## 2026-11-15 — phase A, checkpoint 2: fixed-input replay

- Draft PR: https://github.com/SpeedeMiner/Geoip-ru-server/pull/44 . Initial remote code commit `dc11a7568e8332236273feab16c3d7d7c8f9eaec`, tree `9fffbe0e9c54f38b7e9811fbe191c681f03835fb`.
- All 13 assets bound by the release manifest were verified by byte length and SHA-256, including the four retained input archives. Snapshot HTTP readback was additionally requested for the client files, sidecars, manifests, provenance and quality report. All 10 HTTP readbacks matched the pinned files byte for byte.
- Reconstructed v37 from the retained upstream files, published ASN/RIR sidecars and freshly derived IANA masks. Base SHA-256 `3b196ba746ee67f9b993337e2725887f130a280e4e76e53cb57448bf94d1eb8a` exactly matches the pinned v41 manifest.
- Replayed the original overlay in a detached worktree at `38f3682`, then the patched overlay on the identical base and retained inputs. Compiled and decompiled both SRS for each result with the verified sing-box binary. All three client binaries are byte-identical before/after and equal to the published snapshot. Patch delta: IPv4 +0/-0; IPv6 +0/-0; PRIVATE unchanged. Effective exclusions are byte-identical.
- Independently decoded the retained DAT with v2fly's actual generated Go types and matched both categories, every address and prefix length against the decompiled RU/PRIVATE SRS. This replay test uses `V41_COMPAT_DIRECTORY`; CI always runs the synthetic upstream compatibility test, while retained-artifact replay explicitly supplies the directory.
- Hard/effective exclusions and PRIVATE have zero address-space intersection with final RU in either family. Official Telegram validator passes all 14 prefixes.
- Full local suite: 258 Python tests PASS; Go suite PASS with Go 1.26.10; CDN workflow guard PASS; git diff --check PASS.
- Previous release files were restored from immutable Git commit `a23b381e4844ed4cb84bf67e1f5984027e68769c` and checked against that commit's sidecars. That historical commit does not contain a release-manifest JSON; no fallback to a rolling ref was used. Its DAT SHA-256 is `93f6a3a5ac2551a681e7067df735a6c13c9ebbe7cc50e6d30e4a722dac64e46d`.
- Historical release-to-release delta (NOT caused by this patch): IPv4 +0/-262, IPv6 +0/-4835703278458516698824704. This is distinct from the zero patch delta.
- Machine-readable evidence: [V41_AUDIT_PHASE_A_EVIDENCE_20261115.json](V41_AUDIT_PHASE_A_EVIDENCE_20261115.json). Large IPv6 counts are decimal strings.
- Initial PR CI: v41 https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43718348532 succeeded; all build validation steps succeeded; publish skipped. Lint https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43718348557 succeeded. v39 still running when this checkpoint was written.
- Protected remote refs rechecked after creating the Draft PR and remain at the checkpoint-1 SHAs. The failed unauthenticated git push made no remote update; branch and commits were saved through the connected GitHub API instead.
- Next: save the final artifact decoder check and evidence to the same Draft PR; verify CI for its exact new head. Then proceed to phase B, reporting global-network and Hydra-only intersections without changing admission policy.

### Replay contract

1. Restore the pinned snapshot release manifest, its 13 hashed assets and published sidecars from `79bddd4c51a36a8d3c2771e234e5171f574104c8`. Verify SHA-256/size before use. Restore the four archives without extracting arbitrary archive paths. The JSON evidence contains exact asset digests.
2. Derive the two IANA masks with `build_v41_iana_special_prefixes.py`. Rebuild the v37 base using the argument order in `.github/workflows/geoip-v41.yml` at `38f3682`, substituting only retained file paths. Require the recorded base SHA.
3. Run `build_v41_overlay.py` from baseline and PR on that same base, published input sidecars and unchanged reviewed tables. Use separate output directories and explicit `--manifest` paths when invoking `build_v41_srs.py`.
4. Compare DAT, both SRS and effective exclusions byte for byte. Decompile SRS to `RU.json` and `PRIVATE.json` alongside each DAT, then run `V41_COMPAT_DIRECTORY=/absolute/replay/directory go test -C .github/scripts/geoip-v37-builder -mod=readonly ./...` with Go 1.26.10. Re-run the official Telegram validator on each output.

## 2026-11-15 — phase B, checkpoint 1: read-only audit implementation

- Phase A latest head `ec04c33510e03ad6566208817e94e73f3611189a` is green: v41 run `43718918206`, v39 run `43718918194`, lint run `43718918219`. Protected main/release/cdn refs still match checkpoint 1. PR #44 remains Draft.
- Added the global-network source catalog and a read-only diagnostic script. It captures raw source bytes once per URL (AWS/CloudFront share exactly one response), embeds raw hashes and catalog/scope/status in a bounded gzip snapshot, and verifies the identities during replay.
- Sources: Cloudflare published proxy ranges, AWS public ranges with CloudFront service subset, Google goog/cloud as separate overlapping lists. All five are available in the captured snapshot. Akamai Site Shield and Discord are explicitly UNAVAILABLE for complete client-facing coverage; they never report zero as if verified. The published provider scopes do not imply exhaustive provider ownership.
- Diagnostic script reconstructs final DIRECT from the retained v37 base, regional, selected-origin, company, reviewed operator, service and Hydra layers plus existing final masks. It refuses attribution if that reconstruction differs from the candidate. Counterfactual Hydra-only is the final candidate minus the identical assembly without Hydra; it is separate from Hydra outside regional/company layers.
- Every provider intersection is split at every admission/raw-evidence/MOAS boundary. The raw v2fly/Loyalsoldier and additional-source evidence is labelled separately from actual admission layers. All proposals are review; no route changes are performed.
- DAT deltas use one fixed provider snapshot. An optional previous provider snapshot measures feed-only effects on the same previous DAT. Absent prior feed data stays NOT_PROVIDED. Historical Hydra-only classification stays UNKNOWN_PREVIOUS_LAYERS instead of guessing from current inputs.
- Seven new unit tests PASS; full suite 265 Python tests PASS; Go suite, CDN workflow guard and diff check PASS. Full pinned-input report generation is in progress; an initial overlap-only run reproduced the Cloudflare findings and found Google intersections, with zero overlap in the captured AWS/CloudFront and Google Cloud subsets. These are snapshot-specific observations, not reachability claims.
- Next: finish the full report including both Hydra diagnostic sets, verify all input bindings and arithmetic, retain raw provider snapshot plus JSON/TSV on GitHub, and record exact results. Production DAT/SRS and policy remain unchanged.
