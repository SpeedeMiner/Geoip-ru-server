#!/usr/bin/env python3
"""Read-only DIRECT audit. Provider membership is review evidence, never a route rule."""
import argparse
import csv
from datetime import date, datetime, timezone
import gzip
import hashlib
import ipaddress
import json
from pathlib import Path
import re
import subprocess
import tarfile
from tempfile import TemporaryDirectory
from types import SimpleNamespace

import build_v41_overlay as b
import v41_cdn_ip_advisory as cdn
from validate_v41_publication_bounds import read as read_dat
from v41_direct_admission import CDN_KEY, cdn_networks, read_cdn
from v41_reviewed_unreachable import read_reviewed as read_unreachable
from validate_v41_telegram import read_telegram_feed
from verify_v41_ipverse_archive import verify_archive

CAP = 16 * 1024 * 1024


def digest(data):
    return hashlib.sha256(data).hexdigest()


def provider_networks(spec, payloads):
    nets = set()
    for payload in payloads:
        if spec['format'] == 'cidr-lines':
            tokens = payload.splitlines()
        else:
            doc = json.loads(payload)
            if spec['format'] == 'aws-json':
                rows = [(r, 'ip_prefix', 4) for r in doc['prefixes']]
                rows += [(r, 'ipv6_prefix', 6) for r in doc['ipv6_prefixes']]
                rows = [(r, key, family) for r, key, family in rows
                        if not spec.get('service') or r['service'] == spec['service']]
            elif spec['format'] == 'google-json':
                rows = [(r, 'ipv4Prefix' if 'ipv4Prefix' in r else 'ipv6Prefix',
                         4 if 'ipv4Prefix' in r else 6) for r in doc['prefixes']]
            else:
                raise ValueError('unknown provider format')
            tokens = []
            for row, key, family in rows:
                net = ipaddress.ip_network(row[key], strict=True)
                if net.version != family:
                    raise ValueError('provider family mismatch')
                tokens.append(str(net))
        for token in tokens:
            net = ipaddress.ip_network(token, strict=True)
            if net.prefixlen == 0 or net.version not in spec['families']:
                raise ValueError('unsafe provider prefix')
            nets.add(net)
    if not nets or {n.version for n in nets} != set(spec['families']):
        raise ValueError('empty provider or missing expected family')
    return nets


def check_cdn_spec(spec):
    if (spec['id'], spec['format'], spec.get('role'), spec['urls']) != (
            cdn.SOURCE, cdn.FORMAT, cdn.ROLE, [cdn.URL]):
        raise ValueError('invalid cdn-ip-database catalog entry')


def collect_cdn_database(spec, snapshot, path):
    check_cdn_spec(spec)
    url = spec['urls'][0]
    result = snapshot['cdn_ip_database_collection'] = {'reason': 'DOWNLOAD_ERROR'}
    snapshot['status'][cdn.SOURCE] = 'UNAVAILABLE'
    try:
        response = subprocess.run(['curl', '--fail', '--location', '--silent', '--show-error',
            '--proto', '=https', '--proto-redir', '=https', '--connect-timeout', '10',
            '--max-time', '25', '--max-filesize', str(cdn.MAX_BYTES), '--output', str(path), url],
            capture_output=True, timeout=30)
        if response.returncode:
            return
        with path.open('rb') as stream:
            data = stream.read(cdn.MAX_BYTES + 1)
    except (OSError, subprocess.SubprocessError):
        return
    if not 0 < len(data) <= cdn.MAX_BYTES:
        result['reason'] = 'INVALID_SIZE'
        return
    identity = {'sha256': digest(data), 'bytes': len(data)}
    result.update(identity)
    try:
        payload = data.decode('utf-8')
        cdn.parse_database(payload)
    except (ValueError, RecursionError):
        result['reason'] = 'INVALID_PAYLOAD'
        return
    snapshot['files'][url] = {**identity, 'payload': payload}
    snapshot['status'][cdn.SOURCE] = 'AVAILABLE'
    result['reason'] = None


def collect(catalog, output):
    raw = catalog.read_bytes()
    doc = json.loads(raw)
    if doc.get('schema') != 1:
        raise ValueError('unexpected catalog schema')
    cache = {}
    snapshot = {'schema': 1, 'catalog': doc, 'catalog_sha256': digest(raw),
                'catalog_raw': raw.decode(), 'fetched_at': datetime.now(timezone.utc).isoformat(),
                'files': {}, 'status': {}}
    with TemporaryDirectory() as tmp:
        for spec in doc['sources']:
            if spec['id'] == cdn.SOURCE:
                collect_cdn_database(spec, snapshot, Path(tmp) / 'cdn-ip-database-response')
                continue
            if not spec['urls']:
                snapshot['status'][spec['id']] = 'UNAVAILABLE'
                continue
            for url in spec['urls']:
                if url in cache:
                    continue
                if not url.startswith('https://'):
                    raise ValueError('provider source must use HTTPS')
                path = Path(tmp) / 'response'
                result = subprocess.run(['curl', '--fail', '--location', '--silent', '--show-error',
                    '--proto', '=https', '--proto-redir', '=https', '--connect-timeout', '15',
                    '--max-time', '90', '--retry', '2', '--max-filesize', str(CAP),
                    '--output', str(path), url], capture_output=True)
                if result.returncode:
                    cache[url] = None
                    continue
                data = path.read_bytes()
                if not 0 < len(data) <= CAP:
                    raise ValueError('provider response size invalid')
                cache[url] = data.decode('utf-8')
                snapshot['files'][url] = {'sha256': digest(data), 'bytes': len(data),
                                          'payload': cache[url]}
            if any(cache[url] is None for url in spec['urls']):
                snapshot['status'][spec['id']] = 'UNAVAILABLE'
            else:
                provider_networks(spec, [cache[url] for url in spec['urls']])
                snapshot['status'][spec['id']] = 'AVAILABLE'
    serialized = json.dumps(snapshot, sort_keys=True).encode()
    if len(serialized) > CAP:
        raise ValueError('oversized snapshot')
    output.write_bytes(gzip.compress(serialized, mtime=0))


def load_snapshot(path):
    with gzip.open(path, 'rb') as stream:
        raw = stream.read(CAP + 1)
    if len(raw) > CAP:
        raise ValueError('oversized snapshot')
    doc = json.loads(raw)
    if (doc.get('schema') != 1 or digest(doc['catalog_raw'].encode()) != doc['catalog_sha256']
            or json.loads(doc['catalog_raw']) != doc['catalog']):
        raise ValueError('snapshot catalog mismatch')
    ids = [s['id'] for s in doc['catalog']['sources']]
    if len(ids) != len(set(ids)) or set(doc['status']) != set(ids):
        raise ValueError('duplicate or missing provider status')
    for file in doc['files'].values():
        data = file['payload'].encode()
        if digest(data) != file['sha256'] or len(data) != file['bytes']:
            raise ValueError('snapshot payload identity mismatch')
    providers = {}
    for spec in doc['catalog']['sources']:
        status = doc['status'][spec['id']]
        if status not in {'AVAILABLE', 'UNAVAILABLE'}:
            raise ValueError('invalid provider status')
        if spec['id'] == cdn.SOURCE:
            check_cdn_spec(spec)
            if status == 'UNAVAILABLE':
                providers[cdn.SOURCE] = (spec, None)
                continue
            raw_feed = doc['files'][cdn.URL]
            if not 0 < raw_feed['bytes'] <= cdn.MAX_BYTES:
                raise ValueError('invalid CDN snapshot payload size')
            for name, (nets, normalized) in cdn.parse_database(raw_feed['payload']).items():
                provider_spec = {**spec, 'owner': name, 'advisory_source': cdn.SOURCE,
                                 'ip_families': sorted({net.version for net in nets}),
                                 'normalized_host_bits': normalized}
                providers[f'{cdn.SOURCE}/{name}'] = (provider_spec, nets or None)
            continue
        providers[spec['id']] = (spec, None if status == 'UNAVAILABLE' else
            provider_networks(spec, [doc['files'][u]['payload'] for u in spec['urls']]))
    return doc, providers


def cdn_snapshot_info(snapshot, providers, missing_reason='SOURCE_NOT_CAPTURED'):
    status = snapshot.get('status', {}).get(cdn.SOURCE, 'ADVISORY_MISSING')
    collection = snapshot.get('cdn_ip_database_collection', {})
    identity = (snapshot['files'][cdn.URL] if status == 'AVAILABLE' else collection)
    by_provider = sorted((spec['owner'], spec, nets) for spec, nets in providers.values()
                         if spec.get('advisory_source') == cdn.SOURCE)
    info = {'source': cdn.SOURCE, 'role': cdn.ROLE, 'status': status, 'url': cdn.URL,
            'bytes': identity.get('bytes'), 'sha256': identity.get('sha256'),
            'fetched_at': snapshot.get('fetched_at') if status != 'ADVISORY_MISSING' else None,
            'reason': missing_reason if status == 'ADVISORY_MISSING' else collection.get('reason'),
            'providers': {name: {'status': 'AVAILABLE' if nets else 'UNAVAILABLE',
                                 'ip_families': spec['ip_families'],
                                 'normalized_host_bits': spec['normalized_host_bits']}
                          for name, spec, nets in by_provider}}
    return info


def read_cdn_advisory(path):
    """A missing or damaged advisory snapshot never invalidates the core report."""
    if path is None:
        return cdn_snapshot_info({}, {}), {}
    try:
        snapshot, providers = load_snapshot(path)
        info = cdn_snapshot_info(snapshot, providers)
        index = cdn.provider_scope_index({spec['owner']: nets for spec, nets in providers.values()
                                          if spec.get('advisory_source') == cdn.SOURCE})
        return info, index
    except (OSError, EOFError, ValueError, KeyError, TypeError, AttributeError, RecursionError):
        return cdn_snapshot_info({}, {}, 'SNAPSHOT_UNAVAILABLE_OR_INVALID'), {}


def measure(values):
    return str(b.interval_size(values))


def split_evidence(scope, layers):
    """Split at every evidence boundary, then label entire disjoint segments."""
    events = {}
    for label, ranges in {'__scope__':scope, **layers}.items():
        for lo, hi in ranges:
            events.setdefault(lo, []).append((label, 1))
            events.setdefault(hi + 1, []).append((label, -1))
    active = {}
    previous = None
    for point in sorted(events):
        if previous is not None and previous < point and active.get('__scope__', 0):
            yield previous, point - 1, tuple(sorted(k for k,v in active.items() if v and k != '__scope__'))
        for label, change in events[point]:
            active[label] = active.get(label, 0) + change
            if not active[label]:
                del active[label]
        previous = point


def read_layers(root, base, data, manifest):
    """Reconstruct the actual candidate union; preserve every selected MOAS label."""
    layers = {'v37-base': b.parse_geoip_dat(base)['RU']}
    rir, _ = b.parse_rir_tsv(root / 'geoip_RU_BY_KZ_rir_registered_prefixes.tsv')
    layers.update({'rir-'+cc: ns for cc, ns in rir.items()})
    for label, filename in [('corporate','geoip_RU_company_asn_bgp_prefixes.txt'),
                            ('selected-origins','geoip_RU_v41_rir_ru_and_company_origin_prefixes.txt')]:
        layers[label] = b.parse_cidr_file(root / filename)[0]
    origins = {}
    for line in (root / 'geoip_RU_BY_KZ_asn_bgp_prefixes.txt').read_text().splitlines():
        prefix, sep, labels = line.partition('#')
        if sep and prefix.strip():
            net = ipaddress.ip_network(prefix.strip())
            for label in labels.strip().split(','):
                origins.setdefault('origin:'+label.strip(), set()).add(net)
    for filename in ('v2fly-geoip.dat', 'loyalsoldier-ru.dat', 'loyalsoldier-by.dat',
                     'davoyan-geoip.dat', 'digne-geoip.dat', 'golukon-geoip.dat', 'grimbird-geoip.dat'):
        for category, networks in b.parse_geoip_dat(root / filename).items():
            if category in {'RU', 'BY', 'KZ'}:
                origins['base-input:'+filename+':'+category] = networks
    feed = SimpleNamespace(**{key: root / filename for key, filename in {
        'kyoresuas_v4':'kyoresuas-ru-standard-ipv4.txt','kyoresuas_v6':'kyoresuas-ru-standard-ipv6.txt',
        'kyoresuas_services':'kyoresuas-services.json','w1zardz':'w1zardz-ru-ipv4.txt',
        'escapingworm':'escapingworm-operator-cidr.txt'}.items()})
    service, _, _ = b.load_service_inputs(feed)
    layers.update(service)
    layers.update(b.parse_hydra_direct_whitelist(root / 'hydra-geoip.dat'))
    layers['reviewed-operators'] = set(b.parse_reviewed_operator_prefixes(data / 'v41-reviewed-operator-prefixes.tsv'))
    layers['static-overrides'] = {ipaddress.ip_network(p) for p in b.read_overrides(data / 'v41-static-overrides.tsv')}
    retention_path = (data / 'v41-temporary-release-retention.tsv'
                      if 'temporary_release_retention' in manifest else None)
    layers['temporary-retention'] = set(b.verify_temporary_retention_manifest(retention_path, manifest))
    cdn = read_cdn(data / 'v41-reviewed-reachable-cdn.tsv', as_of=date.fromisoformat(manifest['generated_at'][:10]))
    if manifest[CDN_KEY]['records'] != list(cdn.values()):
        raise ValueError('measured CDN records differ from the bound policy inputs')
    layers['measured-cdn'] = cdn_networks(cdn)
    return layers, origins



def add_exact_moas_evidence(root, origins):
    # Retained ipverse only. Match exact selected prefixes, not covering routes.
    archive_path = root / 'as-ip-blocks.tar.gz'
    verify_archive(root / 'geoip_RU_input_provenance.tsv', archive_path)
    selected = b.union_networks(*(ns for label, ns in origins.items() if label.startswith('origin:')))
    observed = {}
    with tarfile.open(archive_path, 'r|gz') as archive:
        for member in archive:
            if not member.isfile() or not member.name.endswith('/aggregated.json'):
                continue
            if not 0 < member.size <= CAP:
                raise ValueError('invalid ipverse ASN item size')
            with archive.extractfile(member) as stream:
                item = json.load(stream)
            asn = int(item['asn'])
            for version in (4, 6):
                for token in (item.get('prefixes') or {}).get(f'ipv{version}', []) or []:
                    try:
                        net = ipaddress.ip_network(token, strict=False)
                    except ValueError:
                        continue
                    if net.version == version and net in selected:
                        observed.setdefault(net, set()).add(asn)
    for net, asns in observed.items():
        if len(asns) > 1:
            for asn in asns:
                origins.setdefault(f'observed-exact-moas:AS{asn}', set()).add(net)
    return sum(len(asns) > 1 for asns in observed.values())


def verified_effective_mask(root, layers, manifest):
    telegram_path = root/'telegram-official-cidrs.txt'
    if digest(telegram_path.read_bytes()) != manifest['telegram_official']['input_sha256']:
        raise ValueError('Telegram differs from the bound policy input')
    telegram = read_telegram_feed(telegram_path)
    rir = {cc:layers['rir-'+cc] for cc in ('RU','BY','KZ')}
    regional = b.subtract_networks(layers['selected-origins'], layers['corporate'])
    service_exact, service_resolver = b.build_service_protection_masks(
        rir, layers, w1zardz_literal_hosts=b.original_w1zardz_hosts(
            root/'w1zardz-ru-ipv4.txt', layers['w1zardz-service-direct']))
    effective, _ = b.class_aware_effective_block_set(
        b.parse_blocked_base(root/'geoip_RU_blocked_ip_exact_and_legacy_hard.txt'),
        b.parse_blocked_base(root/'geoip_RU_blocked_ipresolve_resolver_only.txt'),
        b.parse_cidr_file(root/'geoip_RU_company_asn_core_bgp_prefixes.txt', allow_hosts=False)[0],
        b.parse_cidr_file(root/'geoip_RU_shared_infrastructure_bgp_prefixes.txt', allow_hosts=False)[0],
        regional | b.union_networks(*rir.values()), service_exact, service_resolver,
        non_exempt=telegram, reviewed_operator_prefixes=layers['reviewed-operators'])
    actual = b.parse_blocked_base(root/'geoip_RU_v41_blocked_ip_exclusions.txt')
    if any(b.intervals(actual,v) != b.intervals(effective,v) for v in (4,6)):
        raise ValueError('effective exclusions differ from the bound policy inputs')
    return effective

def verify_inputs(root, base, candidate, data):
    manifest = json.loads((root/'geoip_RU_v41_manifest.json').read_bytes())
    if digest(candidate.read_bytes()) != manifest['output_sha256']:
        raise ValueError('candidate does not match retained build manifest')
    bindings = {
        'base_v37_geoip':base,
        'hydra_geoip':root/'hydra-geoip.dat',
        'regional_rir_inventory':root/'geoip_RU_BY_KZ_rir_registered_prefixes.tsv',
        'corporate_company_asn_origin_prefixes':root/'geoip_RU_company_asn_bgp_prefixes.txt',
        'corporate_core_prefixes':root/'geoip_RU_company_asn_core_bgp_prefixes.txt',
        'shared_infrastructure_prefixes':root/'geoip_RU_shared_infrastructure_bgp_prefixes.txt',
        'blocked_exact_and_legacy':root/'geoip_RU_blocked_ip_exact_and_legacy_hard.txt',
        'blocked_resolver_only':root/'geoip_RU_blocked_ipresolve_resolver_only.txt',
        'regional_origin_prefixes':root/'geoip_RU_v41_rir_ru_and_company_origin_prefixes.txt',
        'kyoresuas_standard_ipv4':root/'kyoresuas-ru-standard-ipv4.txt',
        'kyoresuas_standard_ipv6':root/'kyoresuas-ru-standard-ipv6.txt',
        'kyoresuas_services_json':root/'kyoresuas-services.json',
        'w1zardz_direct':root/'w1zardz-ru-ipv4.txt',
        'w1zardz_gaming_exclusions':b.W1ZARDZ_EXCLUSIONS,
        'escapingworm_operator_whitelist':root/'escapingworm-operator-cidr.txt',
        'regional_admission_exclusions':data/'v41-regional-admission-exclusions.tsv',
        'reviewed_ipv6_admission_exclusions':data/'v41-reviewed-ipv6-admission-exclusions.tsv',
        'reviewed_operator_prefixes':data/'v41-reviewed-operator-prefixes.tsv',
        'reviewed_unreachable':data/'v41-reviewed-unreachable.tsv',
        CDN_KEY:data/'v41-reviewed-reachable-cdn.tsv',
    }
    for key,path in bindings.items():
        if digest(path.read_bytes()) != manifest['input_sha256'][key]:
            raise ValueError('input differs from retained manifest: '+key)
    if digest((data/'v41-static-overrides.tsv').read_bytes()) != manifest['service_sources']['static-override']['input_sha256']:
        raise ValueError('static DIRECT table differs from the bound policy inputs')
    with (root/'geoip_RU_v41_rir_ru_and_company_origin_prefixes.txt').open(encoding='utf-8') as stream:
        origin_hashes = [line.strip().partition('=')[2] for line in stream
                         if line.startswith('# selected_origin_input_sha256=')]
    if origin_hashes != [digest((root/'geoip_RU_BY_KZ_asn_bgp_prefixes.txt').read_bytes())]:
        raise ValueError('retained regional origin sidecar does not bind the selected ASN evidence')
    provenance = root/'geoip_RU_input_provenance.tsv'
    if digest(provenance.read_bytes()) != manifest['input_provenance_sha256']:
        raise ValueError('input provenance differs from retained manifest')
    names = {'v2fly-geoip.dat','loyalsoldier-ru.dat','loyalsoldier-by.dat',
             'davoyan-geoip.dat','digne-geoip.dat','golukon-geoip.dat','grimbird-geoip.dat'}
    seen = set()
    with provenance.open() as stream:
        for row in csv.DictReader(stream, delimiter='\t'):
            name = row['LOCAL_FILE']
            if name in names:
                if name in seen or row['STATUS'] != 'downloaded' or digest((root/name).read_bytes()) != row['SHA256']:
                    raise ValueError('upstream raw evidence differs from provenance: '+name)
                seen.add(name)
    if seen != names:
        raise ValueError('missing upstream raw provenance: '+','.join(sorted(names-seen)))
    return manifest


def admission_masks(data, layers, manifest):
    geographic = set(b.parse_regional_admission_exclusions(data/'v41-regional-admission-exclusions.tsv'))
    geographic.update(b.read_reviewed_ipv6_admission(data/'v41-reviewed-ipv6-admission-exclusions.tsv'))
    protected = b.union_networks(*(layers[key] for key in (
        'rir-RU', 'rir-BY', 'rir-KZ', 'corporate', 'selected-origins', 'reviewed-operators')))
    cutoff = date.fromisoformat(manifest['generated_at'][:10])
    unreachable = b.reviewed_unreachable_mask(
        read_unreachable(data/'v41-reviewed-unreachable.tsv', as_of=cutoff), protected)
    measured = layers['measured-cdn']
    hydra = b.union_networks(layers['hydra-direct'], layers['hydra-whitelist'])
    return (b.subtract_networks(geographic, measured, hydra) | unreachable,
            b.subtract_networks(geographic, measured) | unreachable)


def build_report(previous, candidate, providers, layers, masks, origins=None, previous_providers=None,
                 *, no_hydra_masks=None):
    reconstructed = b.subtract_networks(b.union_networks(*layers.values()), masks)
    final = b.parse_geoip_dat(candidate)['RU']
    if any(b.intervals(reconstructed, v) != b.intervals(final, v) for v in (4, 6)):
        raise ValueError('candidate layers/masks do not reconstruct final RU exactly')
    no_hydra = b.subtract_networks(b.union_networks(*(ns for label, ns in layers.items()
                                    if not label.startswith('hydra-'))),
                                   masks if no_hydra_masks is None else no_hydra_masks)
    hydra = b.union_networks(*(ns for label, ns in layers.items() if label.startswith('hydra-')))
    regional = b.union_networks(*(ns for label, ns in layers.items()
                                  if label.startswith('rir-') or label in {'corporate','selected-origins'}))
    only = b.subtract_networks(final, no_hydra)
    outside = b.subtract_networks(b.subtract_networks(hydra, masks), regional)
    before, _ = read_dat(previous)
    decoded, _ = read_dat(candidate)
    if any(decoded['RU'][v] != b.intervals(final,v) for v in (4,6)):
        raise ValueError('independent DAT reader disagrees with the audit decoder')
    evidence_by_family = {
        v: {**{name:b.intervals(ns,v) for name,ns in {**layers, **(origins or {})}.items()},
            'hydra-only-counterfactual':b.intervals(only,v),
            'hydra-outside-regional-corporate':b.intervals(outside,v)}
        for v in (4,6)
    }
    known = b.union_networks(*(ns for _,ns in providers.values() if ns is not None))
    providers = {**providers,
        'routing:hydra-only': ({'scope':'Derived counterfactual: final RU minus the identical assembly without Hydra', 'owner':'routing-intent'}, only),
        'routing:hydra-outside-regional-corporate': ({'scope':'Hydra admitted outside regional/corporate layers; other admission sources can exist', 'owner':'routing-intent'}, outside)}
    rows, summary = [], {}
    for provider, (spec, networks) in providers.items():
        info = {'scope': spec['scope'], 'owner': spec['owner'],
                'status': 'UNAVAILABLE' if networks is None else 'AVAILABLE', 'families': {}}
        if 'role' in spec:
            info['role'] = spec['role']
        advisory = spec.get('advisory_source')
        if advisory:
            info['advisory_source'] = advisory
        summary[provider] = info
        if networks is None:
            info['overlap'] = None
            continue
        for version in (4, 6):
            net_iv = b.intervals(networks, version)
            if advisory and not net_iv:
                continue
            old = b.intersect(before['RU'][version], net_iv)
            new = b.intersect(b.intervals(final, version), net_iv)
            states = {'existing': b.intersect(old, new), 'new': b.subtract(new, old),
                      'removed': b.subtract(old, new)}
            info['families'][str(version)] = {'previous': measure(old), 'candidate': measure(new),
                'added': measure(states['new']), 'removed': measure(states['removed'])}
            if provider.startswith('routing:'):
                states = {'candidate': new}
                info['families'][str(version)].update(previous=None, added=None, removed=None)
                info['historical_classification'] = 'UNKNOWN_PREVIOUS_LAYERS'
                info['provider_snapshot_effect'] = 'NOT_APPLICABLE'
            elif previous_providers is None:
                info['provider_snapshot_effect'] = 'NOT_PROVIDED'
            else:
                prior = previous_providers.get(provider)
                previous_networks = None if prior is None else prior[1]
                family_stats = info['families'][str(version)]
                if previous_networks is None:
                    family_stats['provider_snapshot_effect_on_previous_dat'] = None
                else:
                    old_scope = b.intersect(before['RU'][version], b.intervals(previous_networks,version))
                    feed_added, feed_removed = b.subtract(old,old_scope), b.subtract(old_scope,old)
                    family_stats['provider_snapshot_effect_on_previous_dat'] = {
                        'added':measure(feed_added), 'removed':measure(feed_removed)}
                    states.update({'provider-snapshot-new':feed_added, 'provider-snapshot-removed':feed_removed})
            for state, xs in states.items():
                if not xs:
                    continue
                evidence = {name: overlap for name, ranges in evidence_by_family[version].items()
                            if (overlap := b.intersect(xs, ranges))}
                for lo, hi, labels in split_evidence(xs, evidence):
                    for net in sorted(b.networks_from_intervals([(lo, hi)], version),
                                      key=lambda n: (int(n.network_address), n.prefixlen)):
                        rows.append({'provider':provider, 'family':version, 'cidr':str(net),
                            'provider_name':spec['owner'], 'advisory_source':advisory or '',
                            'addresses':str(net.num_addresses), 'status':state,
                            'candidate_evidence':list(labels),
                            'evidence_time':'candidate_inputs_only' if state == 'removed' or state.startswith('provider-snapshot-') else 'candidate',
                            'proposal':'review'})
    return {'schema':1, 'mode':'report-only', 'providers':summary,
        'known_provider_union_overlap':{str(v):measure(b.intersect(b.intervals(final,v),b.intervals(known,v))) for v in (4,6)},
        'hydra':{str(v):{'only_counterfactual':measure(b.intervals(only,v)),
                         'outside_regional_corporate':measure(b.intervals(outside,v))} for v in (4,6)},
        'provider_totals_are_not_additive':True,
        'provenance_semantics':'Admission layers reconstruct final RU exactly; origin and base-input labels are raw evidence, not independent admission rules. Removed rows show candidate evidence only.',
        'rows':rows}


def write_summary(report, stream):
    print('### Scoped provider overlaps and Hydra (advisory)', file=stream)
    print(f"- Pinned release: `{report['previous_release_commit']}`" if report.get('previous_release_commit') else
          '- Pinned release identity: unknown.', file=stream)
    print(f"- Provider snapshot fetched: `{report['provider_snapshot_fetched_at']}`", file=stream)
    previous = report.get('previous_provider_snapshot_fetched_at')
    print(f"- Comparison provider snapshot: `{previous}`" if previous else
          '- Comparison provider snapshot: unavailable; feed changes are unknown.', file=stream)
    if 'cdn_ip_database' in report:
        print('- ' + cdn.status_line(report['cdn_ip_database']), file=stream)
    for name, info in report['providers'].items():
        if name.startswith('routing:') or name == cdn.SOURCE:
            continue
        if info['status'] != 'AVAILABLE':
            if not info.get('advisory_source'):
                print(f'- {name}: unavailable; overlap is unknown.', file=stream)
            continue
        counts = info['families']
        label = f"{info['owner']} ({info['advisory_source']}, advisory)" if info.get('advisory_source') else name
        print(f'- {label}:', file=stream)
        for family in ('4', '6'):
            data = counts.get(family)
            if data is None:
                print(f'  - IPv{family}: unavailable; overlap is unknown.', file=stream)
                continue
            print(f"  - IPv{family}: overlap={data['candidate']} addresses; "
                  f"DIRECT delta +{data['added']}/−{data['removed']}.", file=stream)
            feed_delta = data.get('provider_snapshot_effect_on_previous_dat')
            if feed_delta is None:
                print('    Provider-feed effect on the previous DAT: unknown.', file=stream)
            else:
                print(f"    Provider-feed effect on previous DAT: +{feed_delta['added']}/−{feed_delta['removed']} addresses.", file=stream)
    hydra = report['hydra']
    print(f"- Hydra-only counterfactual: IPv4={hydra['4']['only_counterfactual']}, IPv6={hydra['6']['only_counterfactual']} addresses.", file=stream)
    print('\nHydra-only is the current counterfactual; historical Hydra-only attribution is unknown. Provider scopes overlap and must not be added. Membership is not proof of service ownership, geography or reachability; exact CIDRs are in the artifact.\n', file=stream)


def has_new_provider_overlap(report):
    """Signal review for either DAT changes or provider-feed scope changes."""
    for name, info in report['providers'].items():
        if name.startswith('routing:') or info['status'] != 'AVAILABLE':
            continue
        for data in info['families'].values():
            feed = data.get('provider_snapshot_effect_on_previous_dat')
            if int(data['added']) > 0 or (feed is not None and int(feed['added']) > 0):
                return True
    return False


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--catalog', type=Path)
    p.add_argument('--collect-snapshot', type=Path)
    p.add_argument('--snapshot', type=Path)
    p.add_argument('--previous-snapshot', type=Path)
    p.add_argument('--previous', type=Path)
    p.add_argument('--previous-release', required=False)
    p.add_argument('--previous-checksum', type=Path)
    p.add_argument('--candidate', type=Path)
    p.add_argument('--inputs', type=Path)
    p.add_argument('--base', type=Path)
    p.add_argument('--data', type=Path, default=Path(__file__).resolve().parent.parent/'data')
    p.add_argument('--output', type=Path)
    p.add_argument('--summary', type=Path)
    args = p.parse_args()
    if args.collect_snapshot:
        if not args.catalog:
            p.error('--catalog is required for collection')
        collect(args.catalog, args.collect_snapshot)
        return
    if not all((args.snapshot,args.previous,args.previous_checksum,args.previous_release,
                args.candidate,args.inputs,args.base,args.output)):
        p.error('audit requires --snapshot --previous --previous-checksum --previous-release --candidate --inputs --base --output')
    if not re.fullmatch(r'[0-9a-f]{40}', args.previous_release):
        p.error('--previous-release must be a full commit SHA')
    with args.previous_checksum.open('rb') as stream:
        if stream.read(256) != f"{digest(args.previous.read_bytes())}  geoip_RU.dat\n".encode('ascii'):
            raise ValueError('previous DAT does not match its pinned release checksum')
    snapshot, providers = load_snapshot(args.snapshot)
    previous_doc, previous_providers = load_snapshot(args.previous_snapshot) if args.previous_snapshot else (None, None)
    manifest = verify_inputs(args.inputs, args.base, args.candidate, args.data)
    layers, origins = read_layers(args.inputs, args.base, args.data, manifest)
    private = b.parse_geoip_dat(args.candidate)['PRIVATE']
    moas = add_exact_moas_evidence(args.inputs, origins)
    effective = verified_effective_mask(args.inputs, layers, manifest)
    admission, without_hydra = admission_masks(args.data, layers, manifest)
    report = build_report(args.previous,args.candidate,providers,layers,private|effective|admission,
                          origins,previous_providers,no_hydra_masks=private|effective|without_hydra)
    files = {'provider_snapshot':args.snapshot, 'previous_dat':args.previous,
             'candidate_dat':args.candidate, 'base_dat':args.base, 'previous_dat_checksum':args.previous_checksum}
    if args.previous_snapshot:
        files['previous_provider_snapshot'] = args.previous_snapshot
    used = ['as-ip-blocks.tar.gz', 'geoip_RU_input_provenance.tsv', 'geoip_RU_v41_manifest.json',
            'geoip_RU_BY_KZ_asn_bgp_prefixes.txt', 'geoip_RU_BY_KZ_rir_registered_prefixes.tsv',
            'geoip_RU_company_asn_bgp_prefixes.txt', 'geoip_RU_company_asn_core_bgp_prefixes.txt',
            'geoip_RU_shared_infrastructure_bgp_prefixes.txt', 'geoip_RU_v41_rir_ru_and_company_origin_prefixes.txt',
            'geoip_RU_blocked_ip_exact_and_legacy_hard.txt','geoip_RU_blocked_ipresolve_resolver_only.txt',
            'geoip_RU_v41_blocked_ip_exclusions.txt','telegram-official-cidrs.txt','hydra-geoip.dat',
            'v2fly-geoip.dat','loyalsoldier-ru.dat','loyalsoldier-by.dat','davoyan-geoip.dat',
            'digne-geoip.dat','golukon-geoip.dat','grimbird-geoip.dat','kyoresuas-ru-standard-ipv4.txt',
            'kyoresuas-ru-standard-ipv6.txt','kyoresuas-services.json','w1zardz-ru-ipv4.txt',
            'escapingworm-operator-cidr.txt']
    files.update({f'inputs/{name}':args.inputs/name for name in used})
    for name in ('v41-regional-admission-exclusions.tsv','v41-reviewed-ipv6-admission-exclusions.tsv',
                 'v41-reviewed-operator-prefixes.tsv', 'v41-static-overrides.tsv',
                 'v41-reviewed-reachable-cdn.tsv', 'v41-reviewed-unreachable.tsv'):
        files[f'policy/{name}'] = args.data/name
    if 'temporary_release_retention' in manifest:
        files['policy/v41-temporary-release-retention.tsv'] = args.data/'v41-temporary-release-retention.tsv'
    files['policy/'+b.W1ZARDZ_EXCLUSIONS.name] = b.W1ZARDZ_EXCLUSIONS
    report['input_sha256'] = {k:digest(path.read_bytes()) for k,path in sorted(files.items())}
    report['provider_snapshot_fetched_at'] = snapshot['fetched_at']
    report['previous_release_commit'] = args.previous_release
    report['previous_provider_snapshot_fetched_at'] = previous_doc.get('fetched_at') if previous_doc else None
    report['provider_catalog_sha256'] = snapshot['catalog_sha256']
    report['cdn_ip_database'] = cdn_snapshot_info(snapshot, providers)
    report['observed_exact_moas_prefixes_with_selected_evidence'] = moas
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    with args.output.with_suffix('.tsv').open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=['provider','family','cidr','addresses','status',
            'candidate_evidence','evidence_time','proposal','provider_name','advisory_source'],delimiter='\t')
        writer.writeheader()
        for row in report['rows']:
            writer.writerow({**row,'candidate_evidence':','.join(row['candidate_evidence'])})
    if args.summary:
        with args.summary.open('a', encoding='utf-8') as stream:
            write_summary(report, stream)
        if has_new_provider_overlap(report):
            print('::warning::New scoped provider overlap or provider-feed effect; review the advisory artifact.')


if __name__ == '__main__':
    main()
