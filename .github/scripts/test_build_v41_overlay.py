import ipaddress
import json
import random
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

import build_v41_overlay as builder
from build_v41_overlay import class_aware_effective_block_set, collapse, subtract_networks


def nets(*values):
    return {ipaddress.ip_network(value) for value in values}


class ServiceProvenanceTests(unittest.TestCase):
    def test_malformed_service_catalog_is_not_partially_accepted(self):
        valid = {'name': 'fixture', 'tier': 'standard', 'ipv4': ['192.0.2.0/24'], 'ipv6': [], 'asns': []}
        invalid = [None, {'name': 'bad', 'tier': 'standard', 'ipv4': '198.51.100.0/24'},
                   {'name': 'bad', 'tier': 'standard', 'asns': 'AS123'},
                   {'name': 'bad', 'tier': 'standard', 'ipv4': ['0.0.0.0/0']}]
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'services.json'
            for row in invalid:
                path.write_text(json.dumps({'categories': [{'id': 'test', 'services': [valid, row]}]}), encoding='utf-8')
                with self.subTest(row=row), self.assertRaises(ValueError):
                    builder.parse_services_json(path)
            path.write_text(json.dumps({'categories': [{'id': 'test', 'services': [valid]}]}), encoding='utf-8')
            self.assertEqual(builder.parse_services_json(path)[0], nets('192.0.2.0/24'))

    def test_aggregate_prefixes_do_not_inflate_json_only_metric(self):
        args = SimpleNamespace(kyoresuas_services=Path('services.json'), kyoresuas_v4=Path('v4'),
                               kyoresuas_v6=Path('v6'), w1zardz=Path('w1'), escapingworm=Path('esc'))
        json_only = nets('192.0.2.0/24')
        feeds = {'v4': nets('198.51.100.0/24'), 'v6': nets('2001:db8::/48'),
                 'w1': nets('203.0.113.0/24'), 'esc': nets('203.0.113.0/24')}
        stats = {'raw_rows': 1, 'valid_rows': 1, 'invalid_rows': 0}
        with patch.object(builder, 'parse_services_json', return_value=(json_only, [], 50, None)), \
                patch.object(builder, 'parse_cidr_file', side_effect=lambda p, allow_hosts: (feeds[p.name], dict(stats))), \
                patch.object(builder, 'read_w1zardz_exclusions', return_value=set()), \
                patch.object(builder, 'filter_w1zardz_routes', side_effect=lambda n, e: (n, set())), \
                patch.object(builder, 'sha256', return_value='a' * 64), \
                patch.object(builder.Path, 'read_bytes', return_value=b'fixture'):
            sources, metrics, rows = builder.load_service_inputs(args)
        self.assertEqual(len(json_only), 1)
        self.assertEqual(len(sources['kyoresuas-standard']), 3)
        self.assertEqual(metrics['kyoresuas-standard']['service_json_prefixes'], 1)
        self.assertEqual(metrics['kyoresuas-standard']['aggregate_only_prefixes'], 2)


class CollapseIterableTests(unittest.TestCase):
    def test_one_shot_iterator_preserves_both_host_families(self):
        values = [ipaddress.ip_network("192.0.2.1/32"),
                  ipaddress.ip_network("2001:db8::1/128")]
        self.assertEqual(collapse(iter(values)), values)

    def test_iterables_have_same_canonical_result(self):
        cases = [
            ([], []),
            (["2001:db8::1/128"], ["2001:db8::1/128"]),
            (["192.0.2.1/32"], ["192.0.2.1/32"]),
            (["2001:db8::1/128", "192.0.2.1/32", "192.0.2.0/32",
              "192.0.2.1/32", "2001:db8::/128"],
             ["192.0.2.0/31", "2001:db8::/127"]),
        ]
        for source, expected in cases:
            for factory in (list, tuple, set, iter):
                with self.subTest(source=source, factory=factory.__name__):
                    values = [ipaddress.ip_network(value) for value in source]
                    self.assertEqual(collapse(factory(values)),
                                     [ipaddress.ip_network(value) for value in expected])


class IntervalSubtractionProperties(unittest.TestCase):
    def test_random_small_spaces_equal_independent_address_sets(self):
        rng = random.Random(41641)
        for base in (ipaddress.ip_network("192.0.2.0/24"), ipaddress.ip_network("2001:db8::/120")):
            maxbits = base.max_prefixlen
            def sample():
                address = ipaddress.ip_address(int(base.network_address) + rng.randrange(256))
                return ipaddress.ip_network((address, rng.randint(maxbits - 8, maxbits)), strict=False)
            for _ in range(100):
                source = {sample() for _ in range(rng.randint(0, 8))}
                masks = {sample() for _ in range(rng.randint(0, 8))}
                expected = {address for net in source for address in net} - {address for net in masks for address in net}
                result = subtract_networks(source, masks)
                actual = {address for net in result for address in net}
                self.assertEqual(actual, expected)
                self.assertEqual(sum(net.num_addresses for net in result), len(actual))

    def test_host_boundaries_and_complete_removal(self):
        for parent, first, last in (("192.0.2.0/24", "192.0.2.0/32", "192.0.2.255/32"),
                                    ("2001:db8::/120", "2001:db8::/128", "2001:db8::ff/128")):
            source = nets(parent)
            result = subtract_networks(source, nets(first, last))
            self.assertEqual(sum(net.num_addresses for net in result), 254)
            self.assertFalse(any(ipaddress.ip_network(first).network_address in net for net in result))
            self.assertFalse(any(ipaddress.ip_network(last).network_address in net for net in result))
            self.assertEqual(subtract_networks(source, source), set())


class ClassAwareBlockPrecedenceTests(unittest.TestCase):
    def test_core_corporate_is_exempt_from_resolver_but_not_hard_ip_evidence(self):
        exact = nets("198.51.100.0/24")
        resolved = nets("203.0.113.0/24")
        core = nets("198.51.100.128/25", "203.0.113.128/25")
        shared = set()
        effective, resolver_only = class_aware_effective_block_set(exact, resolved, core, shared)
        self.assertEqual(effective, nets("198.51.100.0/24", "203.0.113.0/25"))
        self.assertEqual(resolver_only, resolved)

    def test_shared_infrastructure_is_exempt_only_from_resolver_only_entries(self):
        exact = nets("198.51.100.0/24")
        resolved = nets("203.0.113.0/24")
        shared = nets("203.0.113.128/25")
        effective, resolver_only = class_aware_effective_block_set(exact, resolved, set(), shared)
        self.assertEqual(effective, nets("198.51.100.0/24", "203.0.113.0/25"))
        self.assertEqual(resolver_only, resolved)

    def test_exact_block_wins_when_same_ip_is_also_in_ipresolve(self):
        exact = nets("203.0.113.0/24")
        resolved = nets("203.0.113.0/24")
        shared = nets("203.0.113.0/24")
        effective, resolver_only = class_aware_effective_block_set(exact, resolved, set(), shared)
        self.assertEqual(effective, exact)
        self.assertEqual(resolver_only, set())

    def test_explicit_subnet_remains_hard_for_shared_infrastructure(self):
        legacy = nets("192.0.2.0/24")
        current_resolved = nets("203.0.113.0/24")
        shared = nets("192.0.2.0/24", "203.0.113.0/24")
        effective, resolver_only = class_aware_effective_block_set(legacy, current_resolved, set(), shared)
        self.assertEqual(effective, legacy)
        self.assertEqual(resolver_only, current_resolved)

    def test_overlapping_class_masks_fail_closed(self):
        shared = nets("198.51.100.0/24")
        with self.assertRaises(ValueError):
            class_aware_effective_block_set(set(), set(), shared, shared)


if __name__ == "__main__":
    unittest.main()
