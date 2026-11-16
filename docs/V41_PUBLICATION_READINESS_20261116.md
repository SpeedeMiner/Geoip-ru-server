# v41 scoped publication hold — review and handoff, 16 Nov 2026

**Review result:** Draft [#53](https://github.com/SpeedeMiner/Geoip-ru-server/pull/53) is independently reviewable at `92fa97e13317db01ca43aad31386d091eb249a2a`, based on `c0d2a01ba1fb5f5c0e48965d614945348083a900`. It does not need #52 or #54 to stop the known candidate. It is not deployed. Reviewing or merging #53 is distinct from approving a new GeoIP dataset.

## What the disposable Git test proves

All runs used real preflight, stage-tag and release-promotion shells from the stated Git commit, the verified Git release baseline and checksum-bound candidate ZIPs. The only reachable Git transport was `file`, and HTTP responses were simulated from the retained Git objects or ZIP. No GitHub release upload, remote branch write, delivery step or jsDelivr purge was performed.

| Case | Preflight | Snapshot tag | Local release ref |
| --- | --- | --- | --- |
| Current main, disputed candidate | PASS | temporarily created | moves in the isolated origin |
| Draft #53, same candidate | HOLD | not created | unchanged |
| Draft #53, same candidate with matching numerical-review SHA | HOLD | not created | unchanged |
| Draft #53, already-published clean DAT/SRS control | PASS | created | moves in the isolated origin |
| Draft #53, malformed review table | error | not created | unchanged |
| Baseline tips differ after preflight but before tag stage | PASS | not created | externally advanced local tip remains |
| Snapshot tag already exists | PASS | pre-existing tag retained | unchanged |
| Baseline moves after tag stage | PASS | staged tag retained | externally advanced local tip remains |
| Corrupt versioned DAT sidecar or upstream input archive | PASS | staged tag retained | unchanged |
| Disputed DAT already present on the baseline, same candidate | PASS | not attempted | unchanged during the test |
| Another writer creates the tag after the existence check | PASS | competing tag retained | unchanged |
| Another writer fast-forwards release after the parent fetch but before the tag-only push | PASS | new tag may be created from the old parent | competing local tip retained; promotion rejects |
| Another writer advances the release after readback, immediately before Git push | PASS | staged tag retained | competing local tip retained |

The last case is intentional comparison semantics. #53 is a **delta hold**, not an invariant checker and not a rollback. It does not repair a disputed binary once an old publisher has already promoted it. A failure after tag creation can leave a snapshot tag while the rolling branch stays unchanged. Confirm versioned assets, `release`, rolling assets, and `cdn` independently after such a failure. The initial push updates only the new tag. Its atomic flag does not cover a separate release ref not being pushed. The later parent check and force-with-lease are the boundaries for rolling promotion; this local race did not test the intervening GitHub Release API call.

## If approving #53 later

1. Keep #52 (broader review) and #54 (read-only CDN diagnostics) separate. Confirm the exact #53 head and its successful CI. GitHub PR builds intentionally skip production publication.
2. Immediately before a merge, recheck `main`, `release`, `cdn`, the current release checksum, and the main workflow queue. An already running or queued older v41 publisher is not protected by #53. A rerun uses its original `GITHUB_SHA` and `GITHUB_REF`. Do not use the old production run as a test of the new guard. If the baseline already moved, inspect its DAT and every public channel before deciding how to correct it.
3. Merging to main itself can trigger v41. Do not also dispatch a duplicate. Observe the exact run and confirm its source commit contains #53. If the retained candidate recurs, expected result is a failed publication preflight with `HOLD` covering 512 added and 1,280 removed watched IPv4 addresses. No new versioned snapshot or GitHub/CDN update is expected on that path. A different upstream input can produce a different result, so read the actual hashes and exact deltas.
4. If a post-tag stage fails, use the last checksum-verified [versioned snapshot](https://github.com/SpeedeMiner/Geoip-ru-server/releases/tag/geoip-v41-snapshot-43747743430.1) for clients while inspecting the other channels. A fallback read-only check is not a rollback and CDN repair does not repair a bad rolling release. Do not move Git refs or overwrite a snapshot based solely on an old workflow log.
5. Only remove a watch row with documented evidence for that direction, or replace this temporary check with an independently reviewed equivalent. The normal size review override is intentionally not a way around #53. Do not infer reachability from v2fly/Loyalsoldier labels or from an observed BGP origin. No proposed change to DIRECT is part of this review.

See [machine-readable results](V41_PUBLICATION_READINESS_EVIDENCE_20261116.json) for all fourteen fixture scenarios. The tests distinguish the guard under review from the existing Git compare-and-swap behavior. The guard changes no stage/promotion script.

## Remaining service-evidence gap

Use a hostname and URL verified as belonging to the relevant public service, and confirm the actual matched DNS address is inside the disputed CIDR. Then collect contemporary results from consenting RU access networks and from a reference. Record the resolver and verified destination IP and preserve TLS hostname validation. A response from an address outside the CIDR is a valid control only. If multiple A records are returned, the existing home probe checks only its first address per family. A report that lists a watched address in DNS but connects to a different IP has not validated reachability to the watched address. Do not infer a residential line from IP/ASN metadata alone or publish the raw subscriber IP in the journal.

The already monitored Curator/HLL AS197068 and AS51115 remain in the published company registry as `SHARED_INFRA`. Draft #52 additionally records AS219306 as shared infrastructure, but that entry is separate from proving present ownership of its historical prefix. The public Curator homepage IP and four previously sampled/historically reported RU-side CDN IPs were present in both DATs. The three sampled reference-side CDN IPv4s were absent from both. This is bounded to the recorded controls and leaves all five disputed CIDRs open.

The [controls-only fixture](V41_RU_ACCESS_CONTROL_TARGETS_20261116.json) validates the existing probe schema. It has no target in a disputed prefix, and no household or VPN probe used it during this pass. The identified operator asset and AdGuard Home's documented update URL both returned HTTP 200 from the execution reference, but their sampled DNS IPv4 addresses did not overlap the five prefixes. The reference HTTPS requests did not establish the destination IP from a direct RU exit.

- [GitHub documentation on reruns](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/re-run-workflows-and-jobs)
- [Current main workflow trigger and queue](https://github.com/SpeedeMiner/Geoip-ru-server/blob/c0d2a01ba1fb5f5c0e48965d614945348083a900/.github/workflows/geoip-v41.yml#L65-L75)
- [Draft #53 check placement](https://github.com/SpeedeMiner/Geoip-ru-server/blob/92fa97e13317db01ca43aad31386d091eb249a2a/.github/scripts/verify_v41_publication_candidate.sh#L47-L56)
- [Existing local-access probe, diagnostic branch](https://github.com/SpeedeMiner/Geoip-ru-server/blob/b293cdf9061fb619c8788050fb699967af4de9e0/.github/reachability/home_probe.py)
