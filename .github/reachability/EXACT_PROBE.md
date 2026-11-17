# Exact IPv4 VPN measurements

The manual `Russian ISP VPN Gate reachability` workflow has two modes:
`exact_ipv4` (default) and `domains` (the previous service-domain catalogue).
The workflow runs the probe only inside the existing isolated VPN namespace,
after independently verifying that the actual tunnel exit is in Russia. A
volunteer VPN exit is **not proof of a household access network**; independently
verify the access type before treating a run as home-network evidence.

In `exact_ipv4`, provide `exact_targets_json` as a JSON array of 1–6 explicit
endpoints. Each item requires `id`, `ip`, and canonical `prefix`, and may have
`domain` and integer `port` (default 443). Replace the placeholders with an
identified public service IP and its real prefix; no address is derived from a
CIDR and the workflow does not scan address ranges.

```json
[{"id":"review-1","ip":"<identified-public-ipv4>","prefix":"<its-canonical-prefix>","domain":"<service-hostname>","port":443}]
```

Omit `domain` for a TCP-only observation. When a hostname is supplied, the
probe records DNS A/AAAA answers and whether A includes the exact IP, then
opens one TCP connection to that IP, verifies TLS with the supplied hostname as
SNI and certificate name, and sends `HEAD /` on the same connection. It does
not follow redirects or disable certificate validation. A DNS mismatch is
recorded independently; an HTTP response, including 403 or 5xx, proves only
that a response was received, not that the service is healthy. A TCP timeout,
connection refusal, TLS failure or HTTP failure is inconclusive and does not
prove censorship. DNS answers do not prove that the full prefix is reachable.

The isolated tunnel currently supports IPv4 transport only. IPv6 endpoints
are rejected before connecting; AAAA DNS answers are informational and IPv6
transport is reported as not tested. TLS uses Python's default SSL stack, not
Chrome uTLS fingerprinting. Results are review-only; no CIDR is automatically
added or removed, and no release data is changed. A complete run means all
declared targets were attempted, not that each was reachable. The report can
include the public exit IP and source ASN; inspect artifacts before sharing.

For the six pending /24 networks in the v41 handoff, first establish a real
service endpoint for each. Blank or invalid input fails before a VPN is opened;
absence of a known endpoint should remain untested rather than be filled with
a guessed IP.
