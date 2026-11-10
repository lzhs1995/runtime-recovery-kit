"""Three existing package-helper cases, using only temporary fixture files."""
import importlib.util
from pathlib import Path
import tempfile
import unittest


spec = importlib.util.spec_from_file_location(
    'package_layout', Path(__file__).resolve().parents[1] / 'scripts/package_layout.py')
layout = importlib.util.module_from_spec(spec)
spec.loader.exec_module(layout)


class PackageLayoutTests(unittest.TestCase):
    def test_runtime_helper_must_be_the_verified_file(self):
        with tempfile.TemporaryDirectory() as t:
            package = Path(t).resolve()
            (package / 'bin').mkdir()
            binary = package / 'codex'
            binary.write_bytes(b'fixture')
            (package / 'bin/codex-code-mode-host').write_bytes(b'verified')
            (package / 'codex-code-mode-host').write_bytes(b'other')
            with self.assertRaisesRegex(ValueError, 'Runtime code-mode helper differs'):
                layout.runtime_helper_path(package, binary)

    def test_standard_and_app_layout_use_bin_helper(self):
        with tempfile.TemporaryDirectory() as t:
            package = Path(t).resolve()
            (package / 'bin').mkdir()
            helper = package / 'bin/codex-code-mode-host'
            helper.write_bytes(b'verified')
            for relative in ['bin/codex', 'CodexCLI.app/Contents/MacOS/codex']:
                binary = package / relative
                binary.parent.mkdir(parents=True, exist_ok=True)
                binary.write_bytes(b'fixture')
                self.assertEqual(layout.runtime_helper_path(package, binary), helper)

    def test_resource_helper_takes_precedence_in_recognized_layout(self):
        with tempfile.TemporaryDirectory() as t:
            package = Path(t).resolve()
            (package / 'bin').mkdir()
            (package / 'codex-resources').mkdir()
            binary = package / 'bin/codex'
            binary.write_bytes(b'fixture')
            helper = package / 'bin/codex-code-mode-host'
            helper.write_bytes(b'verified')
            resource = package / 'codex-resources/codex-code-mode-host'
            resource.write_bytes(b'different host takes precedence')
            with self.assertRaisesRegex(ValueError, 'Runtime code-mode helper differs'):
                layout.runtime_helper_path(package, binary)
            resource.unlink()
            resource.symlink_to(helper)
            self.assertEqual(layout.runtime_helper_path(package, binary), helper)

if __name__ == '__main__':
    unittest.main()
