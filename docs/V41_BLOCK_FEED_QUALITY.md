# v41 block-feed quality checks

This gate changes when a build can be published, not how an accepted route
is classified. It does not add or remove historical exclusions.

| Source | Required check |
| --- | --- |
| Antifilter `ip.lst` | At least 1,000 unique accepted host addresses. Duplicate lines or parsed non-host rows do not count. |
| Antifilter `ipresolve.lst` | Same host minimum for a nonempty result. A truly empty input or the existing download-failure placeholder has an explicit pinned-v38 fallback status. A small nonempty response is rejected instead. |
| Antifilter `subnet.lst` | Must contain at least one unique prefix admitted by the existing IPv4 /16 and IPv6 /112 size limits. Review-only larger blocks do not count. |
| Pinned v38 baseline | At least 1,000 unique entries. The original SHA-256 checks and existing bounds still apply. |

Before staging the next snapshot tag, the publisher fetches the prior
`geoip_RU_blocked_source_stats.txt` from the same pinned `release` commit
used for the DAT comparison. An increase or decrease of more than 50% in
the count of approved unique prefixes of an individual live feed stops
publication and prints the old and new counts. The cutoff catches large
count changes, not all content replacements, silent publisher staleness or
changes in address-space size within the accepted subnet bounds.

The existing resolver fallback does not count as a zero-block verdict.
The comparison logs the fallback separately and does not compare an
available resolver feed with an unusable prior count. After independent
review of the actual source contents, a manual run may use
`reviewed_block_feeds_sha256` with the digest reported by the failed check.
That digest binds both the statistics file and all three current raw inputs.
This only authorizes the relative count change. Absolute feed floors, the
separate DAT delta, hard-mask and Telegram checks are not overridden.

Community and Re-filter remain review-only and record degraded status if
no usable rows are present. A downloaded but unusable HXEHEX **host**
file or Antifilter `ipsum.lst` is excluded from diagnostic calculations
and explicitly marked as degraded. Neither can exempt or remove an IP from
DIRECT.

If Antifilter `ipsum.lst` or either HXEHEX file cannot be downloaded, the
build records `diagnostic-unavailable` and consumes a deterministic
comment-only placeholder. This status is accepted only for these three
specific inputs. Rolling-source archives bind the exact placeholder bytes
to that provenance. HXEHEX metadata or blob identity mismatches are not
silently treated as outages. Required routing inputs keep their existing
checks. Triggering fallback does not add or remove DIRECT addresses.

Publication also compares the SHA-256 of each of the three live block feeds
against the previous release's input provenance, when it is available.
Unchanged and changed bytes are reported independently of count changes
and never block publication. An unchanged hash can be entirely legitimate,
and a changed hash need not reflect a new upstream snapshot. Resolver
fallback, and missing or unusable prior data, are not live baselines.
