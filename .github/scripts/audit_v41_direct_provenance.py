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
from tempfile import TemporaryDirectory
from types import SimpleNamespace

import build_v41_overlay as b
from validate_v41_publication_bounds import read as read_dat

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
    output.write_bytes(gzip.compress(json.dumps(snapshot, sort_keys=True).encode(), mtime=0))


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


def verify_inputs(root, base, candidate, data):
    manifest = json.loads((root/'geoip_RU_v41_manifest.json').read_bytes())
    if digest(candidate.read_bytes()) != manifest['output_sha256']:
        raise ValueError('candidate does not match retained build manifest')
    bindings = {
        'base_v37_geoip':base,
        'hydra_geoip':root/'hydra-geoip.dat',
        'regional_rir_inventory':root/'geoip_RU_BY_KZ_rir_registered_prefixes.tsv',
        'corporate_company_asn_origin_prefixes':root/'geoip_RU_company_asn_bgp_prefixes.txt',
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
    with provenance.open() as stream:
        for row in csv.DictReader(stream, delimiter='\t'):
            if row['LOCAL_FILE'] in {'v2fly-geoip.dat','loyalsoldier-ru.dat','loyalsoldier-by.dat',
                    'davoyan-geoip.dat','digne-geoip.dat','golukon-geoip.dat','grimbird-geoip.dat'}:
                if digest((root/row['LOCAL_FILE']).read_bytes()) != row['SHA256']:
                    raise ValueError('upstream raw evidence differs from provenance')


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
    read_dat(candidate)  # Strict independent decoding and PRIVATE/default-route bounds.
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
                info['families'][str(version)]['provider_snapshot_effect_on_previous_dat'] = (
                    None if previous_networks is None else {
                    'added': measure(b.subtract(old, b.intersect(before['RU'][version], b.intervals(previous_networks, version)))),
                    'removed': measure(b.subtract(b.intersect(before['RU'][version], b.intervals(previous_networks, version)), old))})
            evidence = {name: b.intervals(ns, version) for name, ns in {**layers, **(origins or {})}.items()}
            evidence['hydra-only-counterfactual'] = b.intervals(only, version)
            evidence['hydra-outside-regional-corporate'] = b.intervals(outside, version)
            for state, xs in states.items():
                for lo, hi, labels in split_evidence(xs, evidence):
                    for net in sorted(b.networks_from_intervals([(lo, hi)], version),
                                      key=lambda n: (int(n.network_address), n.prefixlen)):
                        rows.append({'provider':provider, 'family':version, 'cidr':str(net),
                            'addresses':str(net.num_addresses), 'status':state,
                            'candidate_evidence':list(labels),
                            'evidence_time':'candidate_inputs_only' if state == 'removed' else 'candidate',
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
    verify_inputs(args.inputs, args.base, args.candidate, args.data)
    layers, origins = read_layers(args.inputs, args.base, args.data)
    private = b.parse_geoip_dat(args.candidate)['PRIVATE']
    effective = b.parse_cidr_file(args.inputs/'geoip_RU_v41_blocked_ip_exclusions.txt')[0]
    admission = set(b.parse_regional_admission_exclusions(args.data/'v41-regional-admission-exclusions.tsv'))
    admission.update(b.read_reviewed_ipv6_admission(args.data/'v41-reviewed-ipv6-admission-exclusions.tsv'))
    report = build_report(args.previous,args.candidate,providers,layers,private|effective|admission,origins,previous_providers)
    files = [args.snapshot,args.previous,args.candidate,args.base]
    if args.previous_snapshot:
        files.append(args.previous_snapshot)
    files += sorted(x for x in args.inputs.iterdir() if x.is_file() and (x.suffix in {'.txt','.tsv','.json','.dat'}))
    files += sorted(args.data.glob('v41-*exclusions*'))
    files += [args.data/'v41-reviewed-operator-prefixes.tsv', b.W1ZARDZ_EXCLUSIONS]
    report['input_sha256'] = {str(x):digest(x.read_bytes()) for x in files}
    report['provider_snapshot_fetched_at'] = snapshot['fetched_at']
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    with args.output.with_suffix('.tsv').open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=['provider','family','cidr','addresses','status','candidate_evidence','evidence_time','proposal'],delimiter='\t')
        writer.writeheader()
        for row in report['rows']:
            writer.writerow({**row,'candidate_evidence':','.join(row['candidate_evidence'])})


if __name__ == '__main__':
    main()
