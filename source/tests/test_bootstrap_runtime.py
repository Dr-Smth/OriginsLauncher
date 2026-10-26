"""Small archive fixtures exercise bootstrap containment without running Wine."""
import io
import importlib.util
import hashlib
from pathlib import Path
import plistlib
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1] / "bootstrap_runtime.py"
spec = importlib.util.spec_from_file_location("bootstrap_runtime", MODULE)
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)


def fixture(entries):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        for name, target in entries:
            info = tarfile.TarInfo(name)
            if target is None:
                info.size = 1
                archive.addfile(info, io.BytesIO(b"x"))
            else:
                info.type = tarfile.SYMTYPE
                info.linkname = target
                archive.addfile(info)
    buffer.seek(0)
    return tarfile.open(fileobj=buffer, mode="r:")


class Containment(unittest.TestCase):
    def check_bad(self, entries):
        with fixture(entries) as archive, self.assertRaises(b.BootstrapError):
            b.safe_members(archive, "root")

    def test_parent_and_absolute_paths(self):
        for path in ("root/../../outside", "/root/file", "elsewhere/file"):
            self.check_bad([(path, None)])

    def test_escaping_and_absolute_links(self):
        for target in ("../../outside", "/tmp/outside"):
            self.check_bad([("root/sub/link", target)])

    def test_link_ancestor_cannot_receive_file(self):
        self.check_bad([("root/link", "elsewhere"), ("root/link/file", None)])

    def test_link_chain_uses_real_resolution(self):
        # Lexically root/a/../outside is inside; following a -> root/.
        # before the .. would leave the root.
        self.check_bad([("root/a", "."), ("root/link", "a/../outside")])

    def test_cycles(self):
        self.check_bad([("root/a", "b"), ("root/b", "a")])

    def test_case_collisions(self):
        self.check_bad([("root/file", None), ("root/FILE", None)])

    def test_safe_relative_framework_links(self):
        with fixture([("root/Versions/A/lib", None),
                      ("root/Versions/Current", "A"),
                      ("root/lib", "Versions/Current/lib")]) as archive:
            self.assertEqual(len(b.safe_members(archive, "root")), 3)


class Publication(unittest.TestCase):
    @unittest.skipUnless(sys.platform == "darwin", "uses macOS renamex_np")
    def test_tiny_end_to_end_bootstrap_without_running_runtime(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            cache = root / "cache"
            cache.mkdir()
            assets = []
            examples = [
                ("Template.app", {"Contents/Info.plist": plistlib.dumps({}),
                                  "Contents/SharedSupport/renderer/d9vk/version": b"fixture",
                                  "Contents/MacOS/Sikarugir": b"not executable"}),
                ("wswine.bundle", {"bin/wine": b"not executable", "bin/wineserver": b"not executable"}),
            ]
            for top, files in examples:
                path = cache / (top + ".tar.xz")
                with tarfile.open(path, "w:xz") as archive:
                    for name, content in files.items():
                        member = tarfile.TarInfo(f"{top}/{name}")
                        member.size = len(content)
                        member.mode = 0o644
                        archive.addfile(member, io.BytesIO(content))
                assets.append({"name": path.name, "root": top, "url": "https://invalid.example/unused",
                               "bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
            with patch.object(b, "ASSETS", tuple(assets)):
                result = b.bootstrap(root / "project", cache)
                destination = Path(result["runtime"])
                self.assertEqual(result["status"], "created")
                self.assertEqual((destination / "Contents/SharedSupport/wine/bin/wine").read_bytes(), b"not executable")
                self.assertFalse((destination / "Contents/SharedSupport/prefix").exists())
                self.assertEqual(b.bootstrap(root / "project", cache)["status"], "preserved")
            self.assertFalse(list(cache.glob("dao-runtime-stage-*")))

    def test_existing_runtime_is_untouched_before_cache_access(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            runtime = project / "runtime/DAO Runtime.app"
            runtime.mkdir(parents=True)
            marker = runtime / "saved-game"
            marker.write_bytes(b"preserve")
            result = b.bootstrap(project, project / "never-created-cache")
            self.assertEqual(result["status"], "preserved")
            self.assertEqual(marker.read_bytes(), b"preserve")
            self.assertFalse((project / "never-created-cache").exists())

    @unittest.skipUnless(sys.platform == "darwin", "uses macOS renamex_np")
    def test_atomic_publication_never_replaces_existing_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, destination = root / "source", root / "destination"
            source.mkdir()
            (source / "new").touch()
            destination.mkdir()
            with self.assertRaises(FileExistsError):
                b.publish_exclusively(source, destination)
            self.assertTrue((source / "new").exists())
            self.assertEqual(list(destination.iterdir()), [])
            destination.rmdir()
            b.publish_exclusively(source, destination)
            self.assertTrue((destination / "new").exists())

    def test_configuration_uses_final_paths_without_creating_prefix(self):
        with tempfile.TemporaryDirectory() as temp:
            app = Path(temp) / "staged.app"
            (app / "Contents").mkdir(parents=True)
            info = app / "Contents/Info.plist"
            info.write_bytes(plistlib.dumps({"D9VK": 0, "Symlinks In User Folder": 1}))
            final = Path(temp) / "published.app"
            b.configure_runtime(app, final)
            value = plistlib.loads(info.read_bytes())
            self.assertEqual(value["D9VK"], 1)
            self.assertEqual(value["Symlinks In User Folder"], 0)
            self.assertTrue(value["Symlink My Documents"].startswith(str(final)))
            self.assertFalse((app / "Contents/SharedSupport/prefix").exists())


if __name__ == "__main__":
    unittest.main()
