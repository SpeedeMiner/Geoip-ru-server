import gzip
import io
import pathlib
import tarfile
import tempfile
import unittest

from bundle_v41_registry_inputs import HEADER, MANIFEST, MEMBERS, create, restore, sha, verify


class RegistryBundleTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = pathlib.Path(temp.name)
        self.src = self.root / "src"
        self.src.mkdir()
        self.archive = self.root / "original.tar.gz"
        self.prov = self.root / "provenance.tsv"
        rows = ["\t".join(HEADER)]
        for name in MEMBERS:
            data = (name + "\n").encode()
            (self.src / name).write_bytes(data)
            rows.append(f"fixture\t{name}\thttps://example.invalid/{name}\t{sha(data)}\t{len(data)}\tdownloaded")
        self.prov.write_text("\n".join(rows) + "\n")

    def build(self):
        return create(self.prov, self.src, self.archive)

    def test_deterministic_round_trip(self):
        e = self.build()
        other = self.root / "repeated.tar.gz"
        for p in self.src.iterdir():
            p.touch()
        self.assertEqual(create(self.prov, self.src, other), e)
        self.assertEqual(other.read_bytes(), self.archive.read_bytes())
        out = self.root / "out"
        self.assertEqual(restore(self.prov, self.archive, out), e)
        self.assertEqual(sorted(p.name for p in out.iterdir()), sorted(MEMBERS))
        for name in MEMBERS:
            self.assertEqual((out / name).read_bytes(), (self.src / name).read_bytes())

    def test_existing_output_is_never_overwritten(self):
        self.build()
        original = self.archive.read_bytes()
        with self.assertRaises(FileExistsError):
            self.build()
        self.assertEqual(self.archive.read_bytes(), original)
        out = self.root / "out"
        out.mkdir()
        (out / MEMBERS[0]).write_bytes(b"keep")
        with self.assertRaises(FileExistsError):
            restore(self.prov, self.archive, out)
        self.assertEqual((out / MEMBERS[0]).read_bytes(), b"keep")

    def test_same_size_source_drift_is_rejected(self):
        f = self.src / MEMBERS[0]
        f.write_bytes(b"x" + f.read_bytes()[1:])
        with self.assertRaisesRegex(ValueError, "input mismatch"):
            self.build()
        self.assertFalse(self.archive.exists())

    def test_missing_source_is_rejected(self):
        (self.src / MEMBERS[-1]).unlink()
        with self.assertRaisesRegex(ValueError, "not a plain"):
            self.build()
        self.assertFalse(self.archive.exists())

    def test_truncated_gzip_and_extra_gzip_member_are_rejected(self):
        self.build()
        raw = self.archive.read_bytes()
        for modified in (raw[:-5], raw + gzip.compress(b"extra", mtime=0)):
            self.archive.write_bytes(modified)
            with self.assertRaisesRegex(ValueError, "gzip envelope"):
                verify(self.prov, self.archive)

    def test_valid_gzip_with_wrong_member_bytes_is_rejected(self):
        self.build()
        raw = gzip.decompress(self.archive.read_bytes())
        data = (self.src / MEMBERS[0]).read_bytes()
        self.archive.write_bytes(gzip.compress(raw.replace(data, b"X" + data[1:], 1), mtime=0))
        out = self.root / "out"
        with self.assertRaisesRegex(ValueError, "member digest"):
            restore(self.prov, self.archive, out)
        self.assertFalse(out.exists())

    def test_tagged_provenance_mismatch_is_rejected(self):
        self.build()
        self.prov.write_text(self.prov.read_text().replace("example.invalid", "another.invalid"))
        with self.assertRaisesRegex(ValueError, "member digest"):
            verify(self.prov, self.archive)

    def test_tar_extra_bytes_are_rejected(self):
        self.build()
        data = gzip.decompress(self.archive.read_bytes())
        self.archive.write_bytes(gzip.compress(data[:-1] + b"X", mtime=0))
        with self.assertRaisesRegex(ValueError, "tar terminator"):
            verify(self.prov, self.archive)

    def test_path_and_link_members_are_rejected(self):
        self.build()
        raw = self.archive.read_bytes()
        for target, symbolic in (("../outside", False), (MEMBERS[0], True)):
            b = io.BytesIO()
            with tarfile.open(fileobj=b, mode="w") as t:
                with tarfile.open(fileobj=io.BytesIO(gzip.decompress(raw))) as old:
                    info = old.getmember(MANIFEST)
                    t.addfile(info, old.extractfile(info))
                m = tarfile.TarInfo(target)
                m.mode = 0o644
                if symbolic:
                    m.type, m.linkname = tarfile.SYMTYPE, "/tmp"
                t.addfile(m, None)
            self.archive.write_bytes(gzip.compress(b.getvalue(), mtime=0))
            with self.assertRaisesRegex(ValueError, "unexpected archive member"):
                verify(self.prov, self.archive)


if __name__ == "__main__":
    unittest.main()
