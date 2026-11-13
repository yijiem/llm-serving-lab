import hashlib
import io
import tarfile
import tempfile
import unittest
from pathlib import Path

from tools.fetch_assets import unpack, verify


class AssetTests(unittest.TestCase):
    def archive(self, root, members):
        path = root / 'fixture.tar.gz'
        with tarfile.open(path, 'w:gz') as output:
            for name, value, kind in members:
                info = tarfile.TarInfo(name)
                if kind == 'file':
                    data = value.encode()
                    info.size = len(data)
                    info.mode = 0o755
                    output.addfile(info, io.BytesIO(data))
                else:
                    info.type = tarfile.SYMTYPE
                    info.linkname = value
                    output.addfile(info)
        return path

    def test_hash_and_size_are_both_required(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'asset'
            path.write_bytes(b'example')
            spec = {'size': 7, 'sha256': hashlib.sha256(b'example').hexdigest()}
            verify(path, spec)
            for bad in (dict(spec, size=8), dict(spec, sha256='0' * 64)):
                with self.assertRaises(ValueError):
                    verify(path, bad)

    def test_relative_library_symlink_chain_and_executable(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = self.archive(root, [('bin/lib.dylib', 'lib.0.dylib', 'link'),
                ('bin/lib.0.dylib', 'lib.0.1.dylib', 'link'),
                ('bin/lib.0.1.dylib', 'library', 'file'), ('bin/llama-server', 'stub', 'file')])
            unpack(archive, root / 'out')
            self.assertEqual((root / 'out/bin/lib.dylib').read_text(), 'library')
            self.assertTrue((root / 'out/bin/llama-server').stat().st_mode & 0o111)

    def test_rejects_path_traversal_and_escaping_links(self):
        for name, target, kind in [('../escape', 'x', 'file'), ('/escape', 'x', 'file'),
                                  ('bin/link', '../../escape', 'link')]:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                archive = self.archive(root, [(name, target, kind)])
                with self.assertRaises(ValueError):
                    unpack(archive, root / 'out')
                self.assertFalse((root / 'escape').exists())

    def test_rejects_symlink_loops_and_dangling_links(self):
        for members in ([('a', 'b', 'link'), ('b', 'a', 'link')], [('a', 'missing', 'link')]):
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                with self.assertRaises(ValueError):
                    unpack(self.archive(root, members), root / 'out')


if __name__ == '__main__':
    unittest.main()
