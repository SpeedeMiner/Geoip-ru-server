# v39 public RKN-source fallback and corporate-ASN exclusion policy

**Snapshot date:** 2026-11-11 UTC  
**Purpose:** use existing public lists and databases without registering a BGP session or owning a public IP/VPS.  
**Scope:** independent source comparison; no claim of Antifilter community `65444:210` membership.

## Decision

BGP registration is **not a prerequisite for building or releasing v39**. The candidate retains the already approved exact-host and bounded-subnet block inputs. Public sources provide corroboration and gap discovery, but cannot reproduce the attributes of Antifilter's private-AS customer BGP feed.

No public-source aggregate is automatically expanded into a block prefix. Do not treat `ipresolve`, community lists, `ipsum` /24s, cloud/CDN prefixes, or a merged GeoIP list as equivalent to `65444:210`.

## 1. Primary v39 inputs retained

The existing v39 build continues to use its approved Antifilter Download inputs:

- `ip.lst` — individual host address records from the third-party feed.
- `ipresolve.lst` — resolver-derived address candidates; shared addresses can host unrelated services.
- `subnet.lst` — separate network records subject to the existing bounded-prefix policy.
- `ipsum.lst` — summary of individual blocked addresses into IPv4 /24s; review-only due to collateral impact.

These are third-party RKN-derived feed outputs, not a direct official RKN API. v39 does not widen its approved carve-outs from the summary feed.

## 2. Independent split-list cross-check: bol-van/rulist

Repository: [bol-van/rulist](https://github.com/bol-van/rulist)  
Pinned commit: `f9ea9704544590bf0aff817acc73b7e00261a849`  
Commit timestamp: `2026-11-08T07:21:01Z`  
The commit is unsigned. The repository describes itself as blocked IP/host lists in Russia but has no detailed source-methodology README. Treat it as an independent maintainer dataset, not official RKN evidence.

Pinned file identities:

| File | Git blob SHA-1 | Records |
|---|---|---:|
| `reestr_ipban4.txt` | `86af73f171da2b9980efe15e8d8a4fe7e96f2d16` | 71,044 |
| `reestr_resolved4.txt` | `db29de1aad7349ef3fa0de014d7e03068c40541d` | 33,293 |

The `ipban4` file has 61,984 exact IPv4 host entries (/32 after canonicalization) and 9,060 CIDR entries. The repository exposes `resolved4` separately, allowing IP-ban-labelled and DNS-resolved evidence to be checked independently. This naming separation is useful but does not prove the author's extraction is identical to community `65444:210`.

### Exact-host candidate reconciliation

The PR #8 Lib4u/Jirnobruh review set contains 360 unique IPv4 host candidates remaining outside v39 RU, PRIVATE and the approved blocked inputs. Against the pinned `rulist` snapshot:

| Evidence | Candidate IP matches | Interpretation |
|---|---:|---|
| `reestr_ipban4.txt` | 17 | Covered by 11 source CIDR records; 0 of these hits is an exact /32 source row |
| `reestr_resolved4.txt` | 9 | Resolver-derived corroboration; 8 also occur in the ipban4-covered subset |
| Unique candidates in either file | 18 | 342 of 360 have no match in these two files |

The 17 ipban4 overlaps are **prefix containment**, not 17 exact host records. Matching CIDRs include shared cloud/CDN ranges, so they are not blindly inserted into the v39 blocked set. The 9 resolved4 hits are not direct-IP evidence. All 360 remain `REVIEW_ONLY_NO_AUTO_PROMOTION`; none is promoted to RU and none causes a new broad PROXY carve-out.

## 3. RIPE/RDAP enrichment

PR #8 [run 23](https://github.com/SpeedeMiner/Geoip-ru-server/actions/runs/43067107469) completed unit tests, candidate build, enrichment and artifact upload.

- Artifact `vpn-route-candidates-23`, id `13876667699`, ZIP SHA-256 `b97e52992b5f5943426afbdcf79311d63b50f8e2956ea9a066a3ab934d8c7d3e`.
- Enrichment manifest output SHA-256 `810f1af045dca8ac5f70ba8a459a2de4af669f18559dc20b77edf8ea13fb612f`.
- Immutable input SHA-256 `159ab81a1444fa94daea8fe9e2c1d48b4c618d0b69b67b6d5dca9efcf1b4d392`.
- 360/360 candidates had a route observed; 67 origin ASNs and 152 distinct route prefixes were observed.
- 318 prefix-origin pairs had RPKI `valid`; 42 were `unknown`. Unknown is not invalid; valid is not proof of ownership or exclusive service use.
- Provider signals included Amazon AWS, Cloudflare, Microsoft Azure, Alibaba Cloud, Akamai/Linode, Leaseweb, Google Cloud and OVH.
- RDAP returned no usable holder data for the 152 prefix/IP queries (148 API-status failures and 4 request errors). Network-info query timestamps were absent in the output TSV. This is not a complete WHOIS/RDAP audit.

The artifact is review-only and did not modify v39 production inputs.

## 4. Other ready-made datasets

### runetfreedom/russia-blocked-geoip

[Repository](https://github.com/runetfreedom/russia-blocked-geoip) publishes GeoIP, text, MMDB and proxy-rule formats with a six-hour refresh claim. Its README says `ru-blocked` uses Antifilter Download `ipresolve.lst` and `subnet.lst`; `ru-blocked-community` uses the community Antifilter feed and Telegram IPv6; `re-filter` contains Re-filter `ipsum.lst`. These outputs are convenient format-normalized cross-checks, but share source lineage with v39. Do not count them as independent votes.

### eduard256/russia-blocked-ips

[Repository](https://github.com/eduard256/russia-blocked-ips) aggregates roughly 146 sources and updates every six hours. Its manifest observed on 2026-11-11 reported 49,285 CIDRs and included RKN-style lists, Re-filter, bol-van/rulist, Telegram, GitHub metadata, Apple iCloud, Zoom and multiple cloud/CDN/provider datasets. The manifest also reported the rublacklist API source as `error`. Its merged `ip.txt` is a broad routing/blocking aggregate, not a precise RKN direct-IP list. Use for discovery and differential coverage only; never bulk-carve it from DIRECT.

### BlockedIn API

[API documentation](https://blockedin.org/en/article/api/) describes `/api/v3/ips/` as IP addresses currently in the registry, updated every three hours, with a daily registry snapshot. The endpoint was not retrievable in this research session (HTTP 403), so no bytes, digest or prefix count were captured. This remains unverified, not a v39 input.

### jinndi/geoip-ru

[jinndi/geoip-ru](https://github.com/jinndi/geoip-ru) publishes separate clean/blocked lists and describes inputs as Loyalsoldier RU GeoIP plus Antifilter and Re-filter. It is useful for format comparison but correlated with the same upstream datasets.

## 5. Limits and v39 release decision

Public lists can cross-check host observations, flag possible missing PROXY entries, reveal source lineage and stale/erroring feeds, and enrich candidates with public ASN/route/RPKI context. They cannot reproduce private-AS community `65444:210`, prove exclusive service use, or prove absence from a list means safe DIRECT.

1. Keep the existing approved blocked set and PRIVATE-first precedence.
2. Keep `ipsum.lst`, community Antifilter, Re-filter aggregate output, broad aggregators and all 360 new host-IP candidates in review-only roles unless a separate exact-prefix decision is made.
3. Do not expand /24, /22 or other shared prefixes solely because a service hostname resolves into them.
4. Do not wait for or claim a BGP snapshot. Registration and community 210 capture are optional future enrichment, not a v39 release dependency.
5. Rebuild and validate the current PR #9 head before release. BGP absence is a limitation, not a zero-count or inferred clean bill.

## Source references

- [Antifilter Download](https://antifilter.download/)
- [Antifilter.network BGP](https://antifilter.network/bgp) and [FAQ](https://antifilter.network/faq)
- [bol-van/rulist pinned commit](https://github.com/bol-van/rulist/tree/f9ea9704544590bf0aff817acc73b7e00261a849)
- [runetfreedom/russia-blocked-geoip](https://github.com/runetfreedom/russia-blocked-geoip)
- [eduard256/russia-blocked-ips](https://github.com/eduard256/russia-blocked-ips)
- [BlockedIn API](https://blockedin.org/en/article/api/)
- [jinndi/geoip-ru](https://github.com/jinndi/geoip-ru)


## 6. v39 corporate company-ASN precedence

v39 does not make the Antifilter public lists broader. It changes the precedence of the approved blocked set: exact company-origin prefixes are subtracted from the effective block set before DIRECT is carved. The company-origin prefix list is generated from the same selected-origin prefix snapshot and `geoip_RU_company_asns.txt`; both input hashes are preserved. This avoids exempting a whole ASN or provider based solely on its name.

The effective set is `approved_blocked - company_origin_prefixes`. All other exact-host and bounded-subnet blocked addresses continue to be carved. PRIVATE remains higher priority. `ipsum.lst` remains review-only.
