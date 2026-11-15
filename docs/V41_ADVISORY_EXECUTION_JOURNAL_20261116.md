# v41 ASN, provider and Hydra advisory journal

## 2026-11-16 — isolated advisory extraction

- Base `c0d2a01ba1fb5f5c0e48965d614945348083a900`; source of the previously
  reviewed diagnostics is PR #44 head `b6086bee21eb49ad6bddf1874fdb9023847abbc8`.
  The mirror and DIRECT-delta integrations are separate PR #50; this branch
  does not replace #44 or PR #5.
- Extracted the 59-ASN watchlist, normalized observation classifier, priority
  ASN report, scoped provider/Hydra provenance report and their regression tests.
  The production extractor and advisory share the same classifier. No ASN,
  network, block policy, release gate, publisher or CDN file is added or
  removed. New CI steps are PR-only, continue on error and upload audit data
  only as an Actions artifact; provider feed failures remain unknown.
- The previous provider capture dated 2026-11-15 13:46 UTC is retained with
  SHA-256 `e643e891fd2fe25da71c1fe2bcb379703dbd6995e4609ec22c271716e031f189`.
  Current scoped provider input was captured at 2026-11-15 19:13:41 UTC,
  SHA-256 `cb7e2432a6b339ab0bdf9ac6386d0bb188fea241762bc07bc10b533524f2c55a`,
  in [provider snapshot](V41_ADVISORY_PROVIDER_SNAPSHOT_20261116.json.gz).
  Both snapshots distinguish feed-scope changes from DAT changes. AWS,
  Cloudflare and Google scopes were available; Akamai and Discord are unknown.
- The release-identity-bound comparison uses the checked [production candidate
  43747743430](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43747743430)
  and release `e20cf733a13d92040134895ebd580b7c9060fa3b`. DAT SHA-256
  `b17fe26ccdcb8d272e6233ec9686a514b309e9d75e75653313a75f329b70fae7`;
  retained ipverse SHA-256
  `5d3b254a78d4fbbd225d6e18b317a9a29e799f418a6f7b57dbe617b1d1beeb41`.
- [ASN report](V41_ADVISORY_ASN_EVIDENCE_20261116.json.gz) gzip SHA-256
  `78cb9b268fbac8b938d283d98195c7e258aed3bbc893815faa876ae713db0fec`.
  All 118 watched ASN/family pairs were compared against the same retained
  release, with zero actual final-DIRECT losses and zero attribution-loss pairs.
  Twenty-one absent observations remain unconfirmed, not evidence of an outage.
- [Provider and Hydra report](V41_ADVISORY_PROVIDER_EVIDENCE_20261116.json.gz)
  gzip SHA-256 `07fb9c8dc799b55aa6ff18cc5409337c1ca694fdff37eae8e6208d5dfecbcc26`.
  It contains 11,124 split evidence rows. With the same DAT, there were no
  normalized provider-scope changes affecting that DAT between the two captures.
  Cloudflare proxy overlap is 3,584 IPv4; Google-owned scoped overlap is 7,789
  IPv4. Hydra-only counterfactual is 410,576 IPv4. These overlapping scopes
  must not be summed or interpreted as geographic, ownership or reachability
  proof. The report records IPv6 exactly and does not infer an earlier Hydra-only
  contribution from the current layers.
- On the same retained ipverse and registries, the refactored extractor's
  selected prefixes, global prefix inventory and both ASN manifests are
  byte-identical to the published files. Locally 285 Python tests, workflow
  guard, workflow YAML parsing and diff checks passed. New summary tests
  ensure missing baselines and unavailable providers are not reported as zero.
- PR #50 on exact head `139e9ddd9d550a5f2dde74d29ef54e633cbd5c53` passed
  v41/v39/prefix audit/lint, and the validated CI candidate's DAT, both SRS,
  effective exclusions and provenance matched the pinned production release.
  Its fixed-input replay also rebuilt the original v37 base byte-for-byte
  (`3b196ba746ee67f9b993337e2725887f130a280e4e76e53cb57448bf94d1eb8a`).
  Production publication was skipped for the PR.
- Next: verify exact-head GitHub CI and the uploaded advisory artifacts, then
  test composition with PR #50 and recheck main and release before any merge.
  Never treat an unavailable comparison, unpublished candidate or changed
  source snapshot as a verified zero delta.
