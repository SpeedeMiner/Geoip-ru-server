# v41 IPv6 non-DNS discovery closeout

## Result

The tested candidate adds ten exact Moscow and Saint Petersburg CITIC backbone /128s. It is an audit fixture, not a release or a recommendation to add the mixed /48, parent /40, or AS3327. The same operator labels another /128 in Almaty. That address is separate from the frozen review and not in the fixture.

- The [decision ledger](v41-ipv6-non-dns-decisions-20261114.tsv) accounts for all 54 original IPv6 geofeed leads and separates the new Almaty control. None was published. The earlier 73,758-address IPv4 cohort is closed.
- The [priority evidence](v41-ipv6-priority-recheck-20261114.json) distinguishes exact operator DNS and geofeed data from covering BGP routes and RPKI authorization. It records why the zGato /56s stay out.
- The [registry and routing reconciliation](v41-ipv6-registry-recheck-20261114.json) closes the missing child traversals for all 63 RIPEstat fallback scopes and gives all 18 regional registry rows explicit hold decisions. An additional pass checks all 3,279 no-frozen-observation CIDRs across 105 query scopes. The exact AS30058 /40 visible to four paths but absent from its broad query remains a hold on the six affected CIDRs.
- The [IPXO follow-up](v41-ipv6-ipxo-followup-20261114.json) verifies that no exact or child registration was returned for the 24 archived candidate /64s. The AS13335 /48 is global shared coverage, not evidence of independent regional routing for those /64s.
- The [CITIC shadow](v41-ipv6-citic-shadow-20261114.json) passed all checks on both control and candidate. Its data-plane delta is +10 exact IPv6, no removals, no IPv4 or PRIVATE changes, and no change to the blocked mask. All 42 non-RU controls, including Almaty, are still out of the shadow.

## Reproduce

Use the fixed build files from [production run 43583581379](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43583581379). Where its uploaded artifact omits an input, obtain the exact source identified by the manifest and input provenance. The earlier run [43579021611](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43579021611) contains reusable inputs where the recorded SHA-256 matches. Use the raw 14-CIDR [official Telegram feed](https://core.telegram.org/resources/cidr.txt) matching the frozen pin, whose SHA-256 is recorded in the shadow evidence. The script rejects differences without normalizing the downloaded file.

Run from the audit branch with the production commit available locally. All modifications to the test fixture, including the row limit, are made only in a temporary copy of production source.

```bash
python3 .github/scripts/replay_v41_citic_shadow.py \
  --source-repo . \
  --artifact /path/to/43583581379-files \
  --upstream /path/to/sha-verified-extra-inputs \
  --telegram /path/to/official-cidr.txt \
  --output /tmp/v41-citic-shadow-20261114
```

Expected DAT SHA-256 is `4517a9b8e4dce647d0c7e43deca49dfed87f687a1cc111a7e006e35fe417495f` for the shadow and `2735053560ebd598cbdcd71ccf858806d4b955a17e2eac512a7baf249d43653a` for the published artifact. The [release readback](v41-ipv6-release-readback-20261114.json) checked the current rolling download, immutable snapshot and release ref.

## Next decision

The ten RU infrastructure /128s are identified and the build delta is reproducible. Before any admission, decide whether this database should include router loopbacks as exact service destinations or continue to require evidence of useful direct reachability for them. The DNS and BGP evidence does not establish that policy, and no reachability measurement was run in this pass. Keep the Almaty control separate and require new exact evidence before reopening the zGato, IPXO, IHOR or other hold groups.
