from datetime import datetime, timezone
from pathlib import Path
import ipaddress
from tempfile import TemporaryDirectory
import unittest

from validate_v41_download import ANTIFILTER_MINIMUM, validate_antifilter, validate_not_error_page, validate_rir


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


    def test_antifilter_counts_only_distinct_usable_records(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "source.lst"
            path.write_text("# sample\n192.0.2.1\n192.0.2.1/32 # repeated form\n2001:db8::1/128\n", encoding="utf-8-sig")
            self.assertEqual(validate_antifilter(path, "ip", minimum_records=2), (2, 2))
            with self.assertRaisesRegex(ValueError, "only 2 distinct usable"):
                validate_antifilter(path, "ip", minimum_records=3)
            path.write_text("192.0.2.0/24\n192.0.2.0/24\n2001:db8::/112\n198.16.0.0/14\n2001:db8::/48\n")
            self.assertEqual(validate_antifilter(path, "subnet", minimum_records=2), (4, 2))
            with self.assertRaisesRegex(ValueError, "only 2 distinct usable"):
                validate_antifilter(path, "subnet", minimum_records=3)

    def test_antifilter_rejects_format_drift_even_with_usable_rows(self):
        malformed = {
            "ip": ("192.0.2.0/24", "198.51.100.1junk", "fe80::1%eth0", "192.0.2.1/255.255.255.255",
                   '{"error":"rate limit"}', "503 Service Unavailable", "<body>proxy error</body>"),
            "subnet": ("192.0.2.7", "192.0.2.7/24", "0.0.0.0/0", "::/0",
                       "fe80::%eth0/128", "192.0.2.0/255.255.255.0", "IP-CIDR,192.0.2.0/24"),
        }
        with TemporaryDirectory() as directory:
            path = Path(directory) / "source.lst"
            for kind, entries in malformed.items():
                valid = "192.0.2.1" if kind == "ip" else "192.0.2.0/24"
                for entry in entries:
                    with self.subTest(kind=kind, entry=entry):
                        path.write_text(f"{valid}\n{entry}\n")
                        with self.assertRaisesRegex(ValueError, r"source[.]lst:2: expected"):
                            validate_antifilter(path, kind, minimum_records=1)

    def test_antifilter_official_floors_reject_truncated_and_comment_only_feeds(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "source.lst"
            for kind, family in (("ip", "198.18.0.0"), ("subnet", "198.19.0.0")):
                count = ANTIFILTER_MINIMUM[kind]
                start = int(ipaddress.ip_address(family))
                step, suffix = (1, "") if kind == "ip" else (256, "/24")
                rows = [f"{ipaddress.IPv4Address(start + step * i)}{suffix}\n" for i in range(count)]
                with self.subTest(kind=kind):
                    path.write_text("# no usable data\n")
                    with self.assertRaisesRegex(ValueError, "only 0 distinct usable"):
                        validate_antifilter(path, kind)
                    path.write_text("".join(rows[:-1]) + rows[0])
                    with self.assertRaisesRegex(ValueError, f"minimum={count}"):
                        validate_antifilter(path, kind)
                    path.write_text("".join(rows))
                    self.assertEqual(validate_antifilter(path, kind), (count, count))
