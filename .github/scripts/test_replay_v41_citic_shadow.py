import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import replay_v41_citic_shadow as replay


class CiticShadowFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = json.loads(replay.SHADOW_DOC.read_text())

    def test_exact_fixture_is_ten_unique_ru_hosts(self):
        _, hosts = replay.validate_fixture(self.document)
        self.assertEqual(10, len(hosts))
        self.assertNotIn("2001:ad0:cff::81/128", list(map(str, hosts)))

    def test_rejects_broad_repeated_or_relabelled_entries(self):
        for edits in ({"prefix": "2001:ad0:cff::/48"}, {"prefix": "2001:db8::/128"},
                      {"country": "KZ"}, {"origin_asn": "AS42"}, {"prefix": "2001:ad0:cff::8/128"}):
            with self.subTest(edits=edits):
                d = copy.deepcopy(self.document)
                d["shadow"]["fixture"]["added_table_rows"][0].update(edits)
                with self.assertRaisesRegex(ValueError, "out-of-scope"):
                    replay.validate_fixture(d)

    def test_uses_explicit_paths_as_arguments(self):
        snippet = (
            "python3 .github/scripts/validate_v41_telegram.py \\\n"
            ' --geoip "$V41_OUTPUT_FILE" --official-feed "$RUNNER_TEMP/telegram-cidrs.txt"\n'
        )
        dat, feed = Path("/tmp/test workspace/geoip.dat"), Path("/tmp/test workspace/telegram.txt")
        command = list(replay.workflow_command(snippet, "validate_v41_telegram",
                                                {"V41_OUTPUT_FILE": dat}, feed, Path("/tmp/input.tsv")))
        self.assertEqual(command[3:], ["--geoip", str(dat), "--official-feed", str(feed)])

    def test_exact_independent_delta_rejects_extra_address(self):
        _, hosts = replay.validate_fixture(self.document)
        points = sorted(int(n.network_address) for n in hosts)
        basic = {"PRIVATE": {4: [], 6: []}, "RU": {4: [(1, 2)], 6: [(1, 2)]}}
        target = copy.deepcopy(basic)
        merged = []
        for x in points:
            if merged and x == merged[-1][1] + 1:
                merged[-1] = merged[-1][0], x
            else:
                merged.append((x, x))
        target["RU"][6].extend(merged)
        with patch.object(replay, "read", side_effect=[(basic, replay.BASELINE_SHA), (target, replay.EXPECTED_SHADOW_SHA)]):
            self.assertEqual(len(replay.verify_exact_delta(None, None, hosts)["ipv6_added"]), 10)
        target["RU"][6][-1] = (merged[-1][0], merged[-1][1] + 1)
        with patch.object(replay, "read", side_effect=[(basic, replay.BASELINE_SHA), (target, replay.EXPECTED_SHADOW_SHA)]):
            with self.assertRaisesRegex(ValueError, "broader"):
                replay.verify_exact_delta(None, None, hosts)
