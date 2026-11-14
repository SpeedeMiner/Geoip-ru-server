# v41 additional-source audit and release closeout

## Result

- The released v41 restores 15 exact IPv4 across nine independently reviewed RU operator /24s. It does not add coverage outside those previously missing addresses. IPv6, PRIVATE, hard evidence and official Telegram exclusions are unchanged.
- No resolver-only regression exists in the accepted Grimbird/Digne/Davoyan/Golukon coverage from v37. The 82 IPv4 carved in v37 are already present in the v41 overlay through RIR-RU. The only 1,280 IPv4 removed from v37's post-carve coverage are under the prior confirmed Australian admission exclusion.
- The distinct, initially unconfirmed one-group cohort comprised 811 IPv4. Only 15 passed the independent operator test and were restored. The other 796 have recorded hold decisions. Review evidence is snapshot-specific.

## Published files

- [Release PR #30](https://github.com/SpeedeMiner/Geoip-ru-server/pull/30)
- [Production Actions run](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43583581379)
- [Rolling v41](https://github.com/SpeedeMiner/Geoip-ru-server/releases/tag/latest-geoip-client-v41)
- [Immutable snapshot](https://github.com/SpeedeMiner/Geoip-ru-server/releases/tag/geoip-v41-snapshot-43583581379.1)

`geoip_RU.dat`: 1,738,277 bytes, SHA-256 `2735053560ebd598cbdcd71ccf858806d4b955a17e2eac512a7baf249d43653a`.

`geoip_RU_v41_blocked_ip_exclusions.txt`: SHA-256 `da3949ad119013db9a8237d322c63411234c201079f8506af3e51dc6051b0b6a`.

The PR artifact, production artifact, rolling asset, immutable snapshot and release branch were compared directly. The production [build and publication jobs](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43583581379) succeeded without overrides.

## Continue from here

- See the [execution journal](V41_EXECUTION_JOURNAL.md), [accepted additional-source audit](v41-additional-feed-resolver-audit-43579021611.json), and [per-address decision ledger](v41-additional-one-group-decisions-43579021611.tsv).
- Audit files live only on the dedicated audit branch. Production uses the existing reviewed-operator TSV and workflows. The PR #5 branch was left untouched.
- Do not reopen the resolved accepted-source cohort unless the input fingerprints or actual exclusions change. Prior 796 holds need new exact regional evidence before reconsideration. A source label alone is not sufficient.
