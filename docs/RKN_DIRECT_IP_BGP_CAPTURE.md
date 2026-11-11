# Capturing direct RKN IP-block evidence from Antifilter.network BGP

**Purpose:** optional future capture of an independent, timestamped snapshot to distinguish community `65444:210` direct-block records from the wider host-IP list. BGP registration is not a v38 release prerequisite. The current no-BGP public-list fallback is documented in `docs/V38_PUBLIC_RKN_SOURCE_CROSSCHECK.md`. This document does not authorize any immediate change to the v38 block set.

## Community semantics

Antifilter.network documents these standard BGP communities:

- `65444:200`: its unsummarized host-IP list.
- `65444:210`: the subset it classifies as directly blocked by Roskomnadzor, announced together with `65444:200`.
- `65444:300`: `/24` summary; the service explicitly says it is not recommended for ordinary use.

The v38 audit should retain only routes carrying `65444:210`. Do not infer direct blocking merely from `65444:200`.

This is a third-party BGP classification, not a direct official RKN API.

## Subscription

1. On the stable VPS that will establish the BGP session, open [Antifilter BGP registration](https://antifilter.network/bgp).
2. Register that VPS's public IP and local ASN `64999`. The registration form is CAPTCHA-protected and must be submitted manually.
3. Select the exact-host announcement that includes communities `65444:200` and `65444:210`. Do not select the `/24` summary.
4. Use the peer IP and ASN displayed by the registration page at the time of setup. The current page lists `45.148.244.55`, AS `65444`, and recommends hold time `240` seconds. The FAQ contains an older peer IP, so do not copy that stale example blindly.
5. Allow the BGP session to establish and record the capture timestamp, local public IP, BIRD version, session state, received route count and peer details.

## Isolated BIRD 2 configuration

Use a separate BIRD routing table. This imports only matching routes into BIRD's own RIB; do not add a `protocol kernel` exporter and do not export routes to any peer.

Replace `203.0.113.10` with the registered server's public IPv4 address and adjust the local source address if the server is multi-homed.

```bird
router id 203.0.113.10;

ipv4 table antifilter_direct4;
ipv6 table antifilter_direct6;

filter keep_antifilter_direct_rkn {
    if (65444, 210) ~ bgp_community then accept;
    reject;
}

protocol bgp antifilter_direct {
    local as 64999;
    neighbor 45.148.244.55 as 65444;
    multihop;
    hold time 240;

    ipv4 {
        table antifilter_direct4;
        import filter keep_antifilter_direct_rkn;
        import limit 150000 action block;
        export none;
    };

    ipv6 {
        table antifilter_direct6;
        import filter keep_antifilter_direct_rkn;
        import limit 150000 action block;
        export none;
    };
}
```

Check syntax before starting:

```sh
bird -p -c /etc/bird/bird.conf
systemctl restart bird
birdc show protocols all antifilter_direct
birdc show route table antifilter_direct4 protocol antifilter_direct all
birdc show route table antifilter_direct6 protocol antifilter_direct all
```

Save the two full route-table outputs with UTC timestamps. The `all` option is important because it prints route attributes, including BGP communities. Confirm that every imported route carries `65444:210`, that the session is established, and that the route limit was not hit. Keep the original raw outputs immutable and calculate SHA-256 checksums.

## How to reconcile it with v38

1. `65444:210` route overlaps current v38 blocked set: retain PROXY; record direct-block evidence.
2. `65444:210` route is absent from current v38 blocked set: candidate to add to PROXY after exact-prefix validation and PRIVATE precedence.
3. Current `ip.lst` / `ipresolve.lst` host is absent from the complete `65444:210` snapshot but present in `65444:200` only: classify as DNS/resolver candidate, not confirmed direct IP block. Find the originating blocked domain and move that domain into a separate domain-level PROXY list; do not immediately make the whole IP DIRECT.
4. If an IP also belongs to a v38 DIRECT service feed, preserve the collision row. A direct IP-layer block still wins over service DIRECT; resolver-only evidence must be reviewed at the domain layer.
5. Never use absence from one BGP snapshot as proof of safety. Record capture time, full-route coverage and whether all configured AFI/SAFI address families were received.

## Release gate

No `geoip_RU.dat`, blocked-prefix input, production builder, `main`, release tag or CDN asset should change as part of data capture. The resulting BGP snapshot is audit evidence only. Any actual change to v38 must be a separately reviewed diff with per-prefix provenance, exact IPv4/IPv6 address-space impact, PRIVATE overlap and service-collision impact.
