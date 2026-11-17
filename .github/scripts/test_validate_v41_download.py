from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from validate_v41_download import validate_not_error_page, validate_rir


class DownloadValidationTests(unittest.TestCase):
    def test_invalid_regional_resources_fail_even_when_counts_match(self):
        date = datetime.now(timezone.utc).strftime("%Y%m%d")
        header = f"2|ripencc|1|1|{date}|{date}|+0000\n"
        with TemporaryDirectory() as directory:
            path = Path(directory) / "stats"
            for kind, start, size in (("ipv4", "bad", "256"), ("ipv4", "192.0.2.0", "0"),
                                      ("ipv6", "2001:db8::", "129"), ("ipv6", "192.0.2.0", "24")):
                with self.subTest(kind=kind, start=start, size=size):
                    path.write_text(header + f"ripencc|*|{kind}|*|1|summary\n"
                                    + f"ripencc|RU|{kind}|{start}|{size}|20200101|allocated\n", encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, "invalid regional"):
                        validate_rir(path, "ripencc", minimum_records=1)

    def test_valid_regional_resources_are_accepted(self):
        date = datetime.now(timezone.utc).strftime("%Y%m%d")
        with TemporaryDirectory() as directory:
            path = Path(directory) / "stats"
            for country in ("RU", "BY", "KZ"):
                for kind, start, size in (("ipv4", "192.0.2.0", "256"), ("ipv6", "2001:db8::", "32")):
                    with self.subTest(country=country, kind=kind):
                        path.write_text(f"2|ripencc|1|1|{date}|{date}|+0000\n"
                                        + f"ripencc|*|{kind}|*|1|summary\n"
                                        + f"ripencc|{country}|{kind}|{start}|{size}|20200101|allocated\n", encoding="utf-8")
                        self.assertEqual(validate_rir(path, "ripencc", minimum_records=1), 1)

    def test_extended_rir_format_requires_matching_counts_too(self):
        date = datetime.now(timezone.utc).strftime("%Y%m%d")
        header = f"2.3|lacnic|1|2|{date}|{date}|-0300\n"
        summaries = "lacnic|*|asn|*|1|summary\nlacnic|*|ipv4|*|1|summary\n"
        records = "lacnic|BR|asn|123|1|20200101|assigned|opaque\nlacnic|BR|ipv4|192.0.2.0|256|20200101|allocated|opaque\n"
        with TemporaryDirectory() as directory:
            path = Path(directory) / "stats"
            path.write_text(header + summaries + records, encoding="utf-8")
            self.assertEqual(validate_rir(path, "lacnic", minimum_records=1), 2)
            path.write_text(header + summaries + records.splitlines()[0] + "\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                validate_rir(path, "lacnic", minimum_records=1)

    def test_rir_counts_detect_truncation_and_wrong_summaries(self):
        date = datetime.now(timezone.utc).strftime("%Y%m%d")
        header = f"2|apnic|1|2|{date}|{date}|+1000\n"
        summary = "apnic|*|asn|*|1|summary\napnic|*|ipv4|*|1|summary\n"
        records = "apnic|AU|asn|123|1|20200101|allocated\napnic|AU|ipv4|192.0.2.0|256|20200101|allocated\n"
        with TemporaryDirectory() as directory:
            path = Path(directory) / "stats"
            path.write_text(header + summary + records, encoding="utf-8")
            self.assertEqual(validate_rir(path, "apnic", minimum_records=1), 2)
            path.write_text(header + summary + records.splitlines()[0] + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "declared=2, actual=1"):
                validate_rir(path, "apnic", minimum_records=1)
            path.write_text(header + summary + records.replace("|123|1|", "|123|2|").splitlines()[0] + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "asn_units=2"):
                validate_rir(path, "apnic", minimum_records=1)
            path.write_text(header + summary.replace("ipv4|*|1", "ipv4|*|2") + records, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "summary"):
                validate_rir(path, "apnic", minimum_records=1)

    def test_html_error_page_is_rejected(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "input"
            path.write_bytes(b" \n<!DOCTYPE html><title>upstream error</title>")
            with self.assertRaises(ValueError):
                validate_not_error_page(path)
