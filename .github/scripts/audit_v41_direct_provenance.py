#!/usr/bin/env python3
"""Read-only DIRECT audit. Provider membership is review evidence, never a route rule."""
import argparse
import csv
from datetime import datetime, timezone
import gzip
import hashlib
import ipaddress
import json
from pathlib import Path
import subprocess
import tarfile
from tempfile import TemporaryDirectory
from types import SimpleNamespace

import build_v41_overlay as b
from validate_v41_publication_bounds import read as read_dat
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
        providers[spec['id']] = (spec, None if status == 'UNAVAILABLE' else
            provider_networks(spec, [doc['files'][u]['payload'] for u in spec['urls']]))
    return doc, providers


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


def read_layers(root, base, data):
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
    }
    for key,path in bindings.items():
        if digest(path.read_bytes()) != manifest['input_sha256'][key]:
            raise ValueError('input differs from retained manifest: '+key)
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


def build_report(previous, candidate, providers, layers, masks, origins=None, previous_providers=None):
    reconstructed = b.subtract_networks(b.union_networks(*layers.values()), masks)
    final = b.parse_geoip_dat(candidate)['RU']
    if any(b.intervals(reconstructed, v) != b.intervals(final, v) for v in (4, 6)):
        raise ValueError('candidate layers/masks do not reconstruct final RU exactly')
    no_hydra = b.subtract_networks(b.union_networks(*(ns for label, ns in layers.items()
                                    if not label.startswith('hydra-'))), masks)
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
        summary[provider] = info
        if networks is None:
            info['overlap'] = None
            continue
        for version in (4, 6):
            net_iv = b.intervals(networks, version)
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


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--catalog', type=Path)
    p.add_argument('--collect-snapshot', type=Path)
    p.add_argument('--snapshot', type=Path)
    p.add_argument('--previous-snapshot', type=Path)
    p.add_argument('--previous', type=Path)
    p.add_argument('--candidate', type=Path)
    p.add_argument('--inputs', type=Path)
    p.add_argument('--base', type=Path)
    p.add_argument('--data', type=Path, default=Path(__file__).resolve().parent.parent/'data')
    p.add_argument('--output', type=Path)
    args = p.parse_args()
    if args.collect_snapshot:
        if not args.catalog:
            p.error('--catalog is required for collection')
        collect(args.catalog, args.collect_snapshot)
        return
    if not all((args.snapshot,args.previous,args.candidate,args.inputs,args.base,args.output)):
        p.error('audit requires --snapshot --previous --candidate --inputs --base --output')
    snapshot, providers = load_snapshot(args.snapshot)
    previous_providers = load_snapshot(args.previous_snapshot)[1] if args.previous_snapshot else None
    manifest = verify_inputs(args.inputs, args.base, args.candidate, args.data)
    layers, origins = read_layers(args.inputs, args.base, args.data)
    private = b.parse_geoip_dat(args.candidate)['PRIVATE']
    moas = add_exact_moas_evidence(args.inputs, origins)
    effective = verified_effective_mask(args.inputs, layers, manifest)
    admission = set(b.parse_regional_admission_exclusions(args.data/'v41-regional-admission-exclusions.tsv'))
    admission.update(b.read_reviewed_ipv6_admission(args.data/'v41-reviewed-ipv6-admission-exclusions.tsv'))
    report = build_report(args.previous,args.candidate,providers,layers,private|effective|admission,origins,previous_providers)
    files = {'provider_snapshot':args.snapshot, 'previous_dat':args.previous,
             'candidate_dat':args.candidate, 'base_dat':args.base}
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
                 'v41-reviewed-operator-prefixes.tsv'):
        files[f'policy/{name}'] = args.data/name
    files['policy/'+b.W1ZARDZ_EXCLUSIONS.name] = b.W1ZARDZ_EXCLUSIONS
    report['input_sha256'] = {k:digest(path.read_bytes()) for k,path in sorted(files.items())}
    report['provider_snapshot_fetched_at'] = snapshot['fetched_at']
    report['provider_catalog_sha256'] = snapshot['catalog_sha256']
    report['observed_exact_moas_prefixes_with_selected_evidence'] = moas
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    with args.output.with_suffix('.tsv').open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=['provider','family','cidr','addresses','status','candidate_evidence','evidence_time','proposal'],delimiter='\t')
        writer.writeheader()
        for row in report['rows']:
            writer.writerow({**row,'candidate_evidence':','.join(row['candidate_evidence'])})


if __name__ == '__main__':
    main()
