from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from v41_source_counts import HEADER, read_source_counts


class SourceCountTests(unittest.TestCase):
    def test_counts_fail_closed_on_malformed_duplicate_or_inconsistent_rows(self):
        header = "\t".join(HEADER) + "\n"
        a = "one\t1\t2\t0\t0\t3\n"
        total = "TOTAL\t1\t2\t0\t0\t3\n"
        bad = [a + a + total, a + "broken\t1\n" + total,
               a.replace("\t1\t", "\t-1\t") + total,
               a.replace("\t3\n", "\t4\n") + total,
               a + total.replace("\t2\t", "\t3\t").replace("\t3\n", "\t4\n"), a]
        with TemporaryDirectory() as folder:
            path = Path(folder) / "counts.tsv"
            path.write_text(header + a + total, encoding="utf-8")
            self.assertEqual(set(read_source_counts(path)), {"one", "TOTAL"})
            for body in bad:
                with self.subTest(body=body):
                    path.write_text(header + body, encoding="utf-8")
                    with self.assertRaises(ValueError):
                        read_source_counts(path)
