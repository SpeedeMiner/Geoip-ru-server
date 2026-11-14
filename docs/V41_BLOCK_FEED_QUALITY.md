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
DIRECT. Archive and downloader contracts are unchanged. Loss of transport
for currently mandatory diagnostic downloads, including Antifilter
`ipsum.lst` and the catalog-hosted HXEHEX files, is not handled by this
patch. HXEHEX CIDR ingestion in the legacy v37 diagnostic path is unchanged.
