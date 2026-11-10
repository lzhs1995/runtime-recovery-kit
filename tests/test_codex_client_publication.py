"""A failed receipt must never delete the already selected executable."""
import contextlib
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from scripts import codex_client as client


class PublicationTests(unittest.TestCase):
    def setUp(self):
        for name in ['run', 'processes']:
            patch = mock.patch.object(client, name, side_effect=AssertionError('Unexpected real native/network call'))
            patch.start()
            self.addCleanup(patch.stop)

    def exercise_update(self, fail_receipt):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            selection = base / 'selection'
            releases = base / 'releases'
            selection.mkdir()
            releases.mkdir()
            old = releases / '0.0.1'
            old.mkdir()
            (old / 'codex').write_bytes(b'old fixture')
            (selection / 'current').symlink_to(old)
            (selection / 'cli').symlink_to(old / 'codex')
            alias = base / 'codex'
            alias.symlink_to(selection / 'cli')
            (selection / 'authorized-client.json').write_text(json.dumps({
                'package': str(old), 'binary': str(old / 'codex'),
                'sha256': client.digest(old / 'codex')}))
            archive = b'archive fixture'

            def verify(package):
                package = Path(package).resolve()
                return {'package': str(package), 'binary': str(package / 'codex'),
                        'version': '0.0.2', 'sha256': client.digest(package / 'codex')}

            def run(argv, timeout=30):
                if argv[1] == 'api':
                    return SimpleNamespace(stdout=json.dumps({'assets': [{
                        'name': 'codex-package-aarch64-apple-darwin.tar.gz',
                        'digest': 'sha256:' + hashlib.sha256(archive).hexdigest()}]}))
                if argv[1:3] == ['release', 'download']:
                    directory = Path(argv[argv.index('--dir') + 1])
                    (directory / 'codex-package-aarch64-apple-darwin.tar.gz').write_bytes(archive)
                    return SimpleNamespace(stdout='')
                raise AssertionError(argv)

            def unpack(archive_path, destination):
                destination.mkdir()
                (destination / 'codex').write_bytes(b'new fixture')
                return destination

            original_write = client.atomic_json

            def write(path, value):
                if fail_receipt and path.name.startswith('client-switch-') and value.get('status') == 'SELECTED_AND_READBACK':
                    raise OSError('injected final receipt failure')
                return original_write(path, value)

            self.layout = client.Layout(selection, releases, base / 'state', (),
                                        {alias: selection / 'cli'}, alias, 1024)
            with contextlib.ExitStack() as patches:
                for name, value in {
                    'selection_root': selection, 'state_root': base / 'state', 'releases_root': releases,
                    'aliases': {alias: selection / 'cli'}, 'package_locks': [],
                    'processes': lambda **kwargs: [], 'verify_package': verify,
                    'run': run, 'unpack': unpack, 'atomic_json': write,
                }.items():
                    patches.enter_context(mock.patch.object(
                        self.layout if name in {'selection_root', 'state_root', 'releases_root', 'aliases', 'package_locks'} else client,
                        name, value))
                patches.enter_context(mock.patch.object(client.shutil, 'disk_usage', return_value=SimpleNamespace(free=100 * 1024**3)))
                if fail_receipt:
                    with self.assertRaisesRegex(OSError, 'injected final receipt'):
                        client.update(self.layout, '0.0.2')
                else:
                    client.update(self.layout, '0.0.2')
            self.assertTrue(alias.is_file())
            self.assertEqual(alias.read_bytes(), b'new fixture')
            self.assertTrue((releases / '0.0.2').is_dir())
            self.assertEqual(old.exists(), fail_receipt)

    def test_successful_update_retires_previous_package(self):
        self.exercise_update(False)

    def test_final_receipt_failure_retains_published_candidate(self):
        self.exercise_update(True)


if __name__ == '__main__':
    unittest.main()
