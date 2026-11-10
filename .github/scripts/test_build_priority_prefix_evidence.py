import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from build_priority_prefix_evidence import (
    build_evidence,
    fetch_rdap_sample,
    fetch_rpki_origin,
    parse_bootstrap,
    parse_rdap_object,
    rdap_base_for_address,
    rdap_relation,
    sample_addresses,
    select_priority_rows,
)


class FakeResponse:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return b'{"test":"bootstrap-bytes"}'


def make_row(prefix, company_asn, origins, moas, basis):
    return {
        "PREFIX": prefix,
        "FAMILY": f"IPv{__import__('ipaddress').ip_network(prefix).version}",
        "ADDRESS_COUNT": str(__import__("ipaddress").ip_network(prefix).num_addresses),
        "COMPANY_ASNS": company_asn,
        "COMPANY_GROUPS": "Example",
        "LEGAL_ENTITIES": "Example LLC",
        "GLOBAL_BGP_ORIGIN_ASNS": origins,
        "GLOBAL_BGP_ORIGIN_COUNTRY_CODES": "",
        "GLOBAL_BGP_MOAS": moas,
        "INCLUSION_BASIS": basis,
        "GLOBAL_BGP_OBSERVATION": "OBSERVED",
        "STATUS": "REVIEW",
        "BGP_SNAPSHOT_SHA256": "a" * 64,
        "BGP_SNAPSHOT_URL": "https://example.invalid/archive.tar.gz",
    }


class PriorityPrefixEvidenceTests(unittest.TestCase):
    def test_priority_selector_keeps_moas_and_company_only_only(self):
        rows = [
            make_row("198.51.100.0/24", "AS64500", "AS64500,AS64496", "yes", "REGIONAL_RIR_ASN_ORIGIN+COMPANY_ASN"),
            make_row("198.51.101.0/24", "AS64500", "AS64500", "no", "COMPANY_ASN_ONLY"),
            make_row("198.51.102.0/24", "AS64500", "AS64500,AS64497", "no", "REGIONAL_RIR_ASN_ORIGIN+COMPANY_ASN"),
        ]
        selected = select_priority_rows(rows)
        self.assertEqual([row["PREFIX"] for row in selected],
                         ["198.51.100.0/24", "198.51.101.0/24"])
        self.assertEqual(selected[0]["PRIORITY_REASON"], "EXACT_MOAS")
        self.assertEqual(selected[1]["PRIORITY_REASON"], "COMPANY_ONLY")
        self.assertTrue(all(row["STATUS"] == "REVIEW" for row in selected))

    def test_sample_addresses_are_first_midpoint_last_and_deduplicated(self):
        self.assertEqual(
            sample_addresses("192.0.2.0/30"),
            ["192.0.2.0", "192.0.2.1", "192.0.2.3"],
        )
        self.assertEqual(sample_addresses("192.0.2.1/32"), ["192.0.2.1"])
        self.assertEqual(sample_addresses("2001:db8::/126"),
                         ["2001:db8::", "2001:db8::1", "2001:db8::3"])

    def test_iana_bootstrap_longest_prefix_match(self):
        payload = {
            "services": [
                [["198.0.0.0/8"], ["https://rdap.parent.example/"]],
                [["198.51.100.0/24"], ["https://rdap.child.example/"]],
            ]
        }
        entries = parse_bootstrap(4, payload)
        self.assertEqual(
            rdap_base_for_address("198.51.100.7", entries),
            "https://rdap.child.example/",
        )
        self.assertEqual(
            rdap_base_for_address("198.51.101.7", entries),
            "https://rdap.parent.example/",
        )

    def test_rdap_resource_relationships_are_explicit(self):
        payload = {
            "objectClassName": "ip network",
            "handle": "NET-EXAMPLE",
            "name": "Example LLC",
            "type": "ASSIGNED PA",
            "country": "RU",
            "startAddress": "198.51.100.0",
            "endAddress": "198.51.100.255",
            "cidr0_cidrs": [{"v4prefix": "198.51.100.0", "length": 24}],
            "entities": [
                {
                    "handle": "ORG-EXAMPLE",
                    "roles": ["registrant"],
                    "vcardArray": [
                        "vcard",
                        [
                            ["version", {}, "text", "4.0"],
                            ["fn", {}, "text", "Example Registrant"],
                            ["org", {}, "text", "Example LLC"],
                        ],
                    ],
                }
            ],
        }
        parsed = parse_rdap_object(payload)
        self.assertEqual(parsed["NAME"], "Example LLC")
        self.assertEqual(parsed["COUNTRY"], "RU")
        self.assertEqual(parsed["REGISTRANT_ENTITIES"], "Example LLC")
        self.assertEqual(rdap_relation("198.51.100.0/24", parsed), "EXACT_PREFIX_MATCH")
        self.assertEqual(rdap_relation("198.51.100.0/25", parsed), "COVERING_RESOURCE")
        self.assertEqual(rdap_relation("198.51.100.0/24", {
            **parsed, "REGISTERED_CIDRS": "198.51.100.0/25"
        }), "MORE_SPECIFIC_RESOURCE_AT_SAMPLE")

    def test_rpki_errors_are_not_converted_to_unknown(self):
        with patch(
            "build_priority_prefix_evidence.request_json",
            return_value=(429, None, "HTTP_429"),
        ):
            row = fetch_rpki_origin("198.51.100.0/24", "AS64500")
        self.assertEqual(row["QUERY_STATUS"], "HTTP_429")
        self.assertEqual(row["RPKI_STATUS"], "")

    def test_full_build_records_all_56_priority_prefixes_and_query_errors(self):
        rows = []
        for index in range(52):
            prefix = f"198.51.{index}.0/24"
            rows.append(make_row(
                prefix, "AS64500", "AS64500,AS64496", "yes",
                "REGIONAL_RIR_ASN_ORIGIN+COMPANY_ASN",
            ))
        for index in range(4):
            prefix = f"203.0.113.{index * 64}/26"
            rows.append(make_row(prefix, "AS212066", "AS212066", "no", "COMPANY_ASN_ONLY"))

        bootstrap4 = {
            "services": [[["0.0.0.0/0"], ["https://rdap.test/"]]]
        }
        bootstrap6 = {
            "services": [[["::/0"], ["https://rdap.test/"]]]
        }
        def fake_request_json(url, timeout=30, retries=3):
            if url == "https://data.iana.org/rdap/ipv4.json":
                return 200, bootstrap4, ""
            if url == "https://data.iana.org/rdap/ipv6.json":
                return 200, bootstrap6, ""
            if "/data/rpki-validation/data.json?" in url:
                return 200, {"data": {"status": "valid", "description": "ROA authorises this origin"}}, ""
            if "/ip/" in url:
                address = url.rsplit("/ip/", 1)[1]
                ip = __import__("ipaddress").ip_address(address)
                prefix = f"{ip}/{ip.max_prefixlen}"
                key = "v4prefix" if ip.version == 4 else "v6prefix"
                return 200, {
                    "objectClassName": "ip network",
                    "handle": "TEST-NET",
                    "name": "Example LLC",
                    "country": "US",
                    "startAddress": str(ip),
                    "endAddress": str(ip),
                    "cidr0_cidrs": [{key: str(ip), "length": ip.max_prefixlen}],
                    "entities": [],
                }, ""
            return 500, None, "HTTP_500"

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            company_review = root / "company.tsv"
            headers = list(rows[0])
            with company_review.open("w", encoding="utf-8", newline="") as handle:
                handle.write("# synthetic fixture\n")
                writer = csv.DictWriter(handle, fieldnames=headers, delimiter="\t", lineterminator="\n")
                writer.writeheader()
                writer.writerows(rows)
            output = root / "out"

            with patch("build_priority_prefix_evidence.request_json", side_effect=fake_request_json), \
                 patch("build_priority_prefix_evidence.urllib.request.urlopen", return_value=FakeResponse()):
                result = build_evidence(company_review, output, max_workers=4)

            self.assertEqual(result["priority_prefixes"], 56)
            self.assertEqual(result["moas_prefixes"], 52)
            self.assertEqual(result["company_only_prefixes"], 4)
            self.assertEqual(result["rdap_samples"], 168)
            self.assertEqual(result["rpki_origin_checks"], 108)
            self.assertEqual(result["rpki_statuses"], {"valid": 108})

            with (output / "priority_prefixes.tsv").open(encoding="utf-8", newline="") as handle:
                priority = list(csv.DictReader(handle, delimiter="\t"))
            with (output / "rdap_samples.tsv").open(encoding="utf-8", newline="") as handle:
                rdap = list(csv.DictReader(handle, delimiter="\t"))
            with (output / "rpki_by_origin.tsv").open(encoding="utf-8", newline="") as handle:
                rpki = list(csv.DictReader(handle, delimiter="\t"))
            with (output / "prefix_holder_review_summary.tsv").open(encoding="utf-8", newline="") as handle:
                holder_summary = list(csv.DictReader(handle, delimiter="\t"))
            self.assertEqual(len(priority), 56)
            self.assertEqual(len(rdap), 168)
            self.assertEqual(len(rpki), 108)
            self.assertEqual(len(holder_summary), 56)
            self.assertTrue(all(row["STATUS"] == "REVIEW" for row in priority))
            self.assertTrue(all(row["STATUS"] == "REVIEW" for row in holder_summary))
            self.assertTrue(all(row["QUERY_STATUS"] == "OK" for row in rdap))
            self.assertTrue(all(row["RPKI_STATUS"] == "valid" for row in rpki))
            self.assertTrue((output / "priority_prefix_evidence_README.txt").is_file())


if __name__ == "__main__":
    unittest.main()
