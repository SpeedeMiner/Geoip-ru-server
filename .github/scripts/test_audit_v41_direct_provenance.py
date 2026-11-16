import gzip
import hashlib
import ipaddress
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import tarfile

import audit_v41_direct_provenance as audit
from build_v41_overlay import encode_geoip


def nets(*values):
    return set(map(ipaddress.ip_network, values))


class DirectProvenanceAuditTests(unittest.TestCase):
    def test_new_provider_overlap_warning_distinguishes_feed_and_dat_changes(self):
        def family(added, feed):
            return {'candidate':'10', 'added':str(added), 'removed':'0',
                    'provider_snapshot_effect_on_previous_dat':feed}
        report = {'provider_snapshot_fetched_at':'new', 'previous_provider_snapshot_fetched_at':'old',
                  'providers': {'p':{'status':'AVAILABLE', 'families':{
                      '4':family(0, {'added':'2','removed':'0'}), '6':family(0, None)}},
                      'missing':{'status':'UNAVAILABLE', 'families':{}}},
                  'hydra': {'4':{'only_counterfactual':'1'}, '6':{'only_counterfactual':'0'}}}
        self.assertTrue(audit.has_new_provider_overlap(report))
        out = io.StringIO()
        audit.write_summary(report, out)
        self.assertIn('Provider-feed effect on previous DAT: +2/−0', out.getvalue())
        self.assertIn('Provider-feed effect on the previous DAT: unknown', out.getvalue())
        report['providers']['p']['families']['4']['provider_snapshot_effect_on_previous_dat']['added'] = '0'
        self.assertFalse(audit.has_new_provider_overlap(report))
        report['providers']['p']['families']['6']['added'] = '1'
        self.assertTrue(audit.has_new_provider_overlap(report))

    def test_summary_reports_unavailable_provider_and_baseline_as_unknown(self):
        report = {
            'provider_snapshot_fetched_at': '2026-11-15T00:00:00Z',
            'previous_provider_snapshot_fetched_at': None,
            'providers': {'incomplete': {'status':'UNAVAILABLE', 'families':{}}},
            'hydra': {'4':{'only_counterfactual':'1'}, '6':{'only_counterfactual':'0'}},
        }
        out = io.StringIO()
        audit.write_summary(report, out)
        self.assertIn('incomplete: unavailable; overlap is unknown', out.getvalue())
        self.assertIn('feed changes are unknown', out.getvalue())
        self.assertNotIn('incomplete: DIRECT overlap IPv4=0', out.getvalue())

    def test_provider_formats_filter_cloudfront_and_preserve_families(self):
        doc = {'prefixes':[{'ip_prefix':'192.0.2.0/24','service':'EC2'},
                           {'ip_prefix':'198.51.100.0/24','service':'CLOUDFRONT'}],
               'ipv6_prefixes':[{'ipv6_prefix':'2001:db8::/48','service':'CLOUDFRONT'}]}
        spec = {'format':'aws-json','families':[4,6], 'service':'CLOUDFRONT'}
        self.assertEqual(audit.provider_networks(spec,[json.dumps(doc)]),
                         nets('198.51.100.0/24','2001:db8::/48'))
        with self.assertRaises(ValueError):
            audit.provider_networks({'format':'cidr-lines','families':[4,6]}, ['<html>error</html>'])
        with self.assertRaises(ValueError):
            audit.provider_networks({'format':'cidr-lines','families':[4,6]}, ['192.0.2.0/24'])

    def test_split_does_not_assign_whole_aggregate_from_first_address(self):
        scope=[(0,255)]
        layers={'one':[(0,127)],'two':[(128,255)],'moas':[(64,191)]}
        self.assertEqual(list(audit.split_evidence(scope,layers)),[
            (0,63,('one',)),(64,127,('moas','one')),
            (128,191,('moas','two')),(192,255,('two',))])

    def run_report(self, previous, candidate, layers, providers, **kwargs):
        with TemporaryDirectory() as tmp:
            a,b = Path(tmp)/'old.dat', Path(tmp)/'new.dat'
            for path, values in [(a,previous),(b,candidate)]:
                path.write_bytes(encode_geoip({'RU':values,'PRIVATE':nets('10.0.0.0/8','fc00::/7')}))
            return audit.build_report(a,b,providers,layers,set(),**kwargs)

    def test_hydra_only_is_counterfactual_not_just_outside_region(self):
        route = nets('192.0.2.0/24','2001:db8::/48')
        layers = {'v37-base':nets('192.0.2.0/25','2001:db8::/48'),
                  'hydra-direct':route, 'corporate':set()}
        provider = {'p':({'scope':'fixture','owner':'test'},route),
                    'unknown':({'scope':'partial not obtained','owner':'unknown'},None)}
        r=self.run_report(route,route,layers,provider)
        self.assertEqual(r['hydra']['4']['only_counterfactual'],'128')
        self.assertEqual(r['hydra']['4']['outside_regional_corporate'],'256')
        self.assertEqual(r['hydra']['6']['only_counterfactual'],'0')
        self.assertEqual(r['hydra']['6']['outside_regional_corporate'],str(2**80))
        self.assertIsNone(r['providers']['unknown']['overlap'])
        self.assertEqual(len([x for x in r['rows'] if x['family']==4 and x['provider']=='p']),2)
        r=self.run_report(route,route,layers,provider,origins={'origin:AS1':route,'origin:AS2':route})
        self.assertTrue(all({'origin:AS1','origin:AS2'} <= set(x['candidate_evidence']) for x in r['rows']))

    def test_equal_dat_does_not_hide_provider_snapshot_effect(self):
        route=nets('192.0.2.0/24','2001:db8::/48')
        spec={'scope':'test','owner':'test'}
        r=self.run_report(route,route,{'v37-base':route},{'p':(spec,route)},
                          previous_providers={'p':(spec,nets('192.0.2.0/25'))})
        f=r['providers']['p']['families']['4']
        self.assertEqual(f['added'],'0')
        self.assertEqual(f['provider_snapshot_effect_on_previous_dat']['added'],'128')
        self.assertEqual([row['cidr'] for row in r['rows'] if row['status']=='provider-snapshot-new' and row['family']==4], ['192.0.2.128/25'])

    def test_exact_moas_retains_unselected_origin_without_attributing_covering_prefix(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp)
            origins = {'origin:AS10[RIR-RU]': nets('192.0.2.0/24')}
            with tarfile.open(path/'as-ip-blocks.tar.gz', 'w:gz') as archive:
                for asn, v4 in ((10, '192.0.2.0/24'), (11, '192.0.2.0/24'), (12, '192.0.2.0/23')):
                    payload = json.dumps({'asn':asn,'prefixes':{'ipv4':[v4]}}).encode()
                    info = tarfile.TarInfo(f'as/{asn}/aggregated.json')
                    info.size = len(payload)
                    archive.addfile(info,io.BytesIO(payload))
            with patch.object(audit,'verify_archive') as verify:
                self.assertEqual(audit.add_exact_moas_evidence(path,origins),1)
            verify.assert_called_once()
            self.assertEqual(set(origins),{'origin:AS10[RIR-RU]',
                'observed-exact-moas:AS10','observed-exact-moas:AS11'})

    def test_effective_mask_cannot_be_replaced_by_unrelated_ranges(self):
        telegram = '149.154.160.0/20\n2001:b28:f23d::/48\n'
        layers = {label:set() for label in ('rir-RU','rir-BY','rir-KZ',
            'selected-origins','corporate','w1zardz-service-direct','reviewed-operators','user-trusted-prefixes')}
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            hashes={'telegram_official':{'input_sha256':hashlib.sha256(telegram.encode()).hexdigest()}}
            (root/'telegram-official-cidrs.txt').write_text(telegram)
            (root/'geoip_RU_v41_blocked_ip_exclusions.txt').write_text('4.4.4.4/32\n')
            for name in ('geoip_RU_blocked_ip_exact_and_legacy_hard.txt',
                         'geoip_RU_blocked_ipresolve_resolver_only.txt',
                         'geoip_RU_company_asn_core_bgp_prefixes.txt',
                         'geoip_RU_shared_infrastructure_bgp_prefixes.txt','w1zardz-ru-ipv4.txt'):
                (root/name).write_text('8.8.8.8/32\n')
            (root/'geoip_RU_shared_infrastructure_bgp_prefixes.txt').write_text('9.9.9.9/32\n')
            with patch.object(audit.b,'build_service_protection_masks',return_value=(set(),set())):
                with self.assertRaisesRegex(ValueError,'effective exclusions differ'):
                    audit.verified_effective_mask(root,layers,hashes)
                (root/'geoip_RU_v41_blocked_ip_exclusions.txt').write_text(telegram+'8.8.8.8/32\n')
                self.assertEqual(audit.verified_effective_mask(root,layers,hashes),
                    nets('149.154.160.0/20','2001:b28:f23d::/48','8.8.8.8/32'))

    def test_new_and_removed_segments_are_not_blended(self):
        old=nets('192.0.2.0/25','2001:db8::/48')
        new=nets('192.0.2.128/25','2001:db8::/48')
        provider={'p':({'scope':'test','owner':'test'},nets('192.0.2.0/24','2001:db8::/48'))}
        r=self.run_report(old,new,{'v37-base':new},provider)
        self.assertEqual({x['status'] for x in r['rows'] if x['provider']=='p'},{'new','existing','removed'})
        self.assertEqual(r['providers']['p']['families']['4']['removed'],'128')

    def test_wrong_layers_fail_instead_of_reporting_false_attribution(self):
        route=nets('192.0.2.0/24','2001:db8::/48')
        with self.assertRaisesRegex(ValueError,'reconstruct'):
            self.run_report(route,route,{'v37-base':nets('192.0.2.0/25')},{})

    def test_snapshot_hash_mismatch_is_fatal(self):
        catalog={'schema':1,'sources':[]};raw=json.dumps(catalog)
        doc={'schema':1,'catalog':catalog,'catalog_raw':raw,
             'catalog_sha256':hashlib.sha256(raw.encode()).hexdigest(),'status':{},
             'files':{'https://example.invalid':{'sha256':'0'*64,'bytes':1,'payload':'x'}}}
        with TemporaryDirectory() as tmp:
            p=Path(tmp)/'snapshot.gz';p.write_bytes(gzip.compress(json.dumps(doc).encode()))
            with self.assertRaisesRegex(ValueError,'identity'):
                audit.load_snapshot(p)


if __name__ == '__main__':
    unittest.main()
