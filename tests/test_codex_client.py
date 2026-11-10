import importlib.util
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import tarfile
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from scripts import codex_client as client


class ClientTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        base = Path(temporary.name).resolve()
        self.layout = client.Layout(base / 'selection', base / 'releases', base / 'state',
                                    (), {}, base / 'cli', 1024)
        for name in ['run', 'processes']:
            patch = mock.patch.object(client, name, side_effect=AssertionError('Unexpected real native/network call'))
            patch.start()
            self.addCleanup(patch.stop)

    def test_root_executable_requires_its_adjacent_helper(self):
        with tempfile.TemporaryDirectory() as t:
            package = Path(t).resolve()
            (package / 'bin').mkdir()
            binary = package / 'codex-aarch64-apple-darwin'
            binary.write_bytes(b'fixture')
            (package / 'bin/codex').symlink_to(binary)
            helper = package / 'bin/codex-code-mode-host'
            helper.write_bytes(b'fixture helper')
            (package / 'codex-resources').mkdir()
            (package / 'codex-path').mkdir()
            (package / 'codex-package.json').write_text(json.dumps({
                'target': 'aarch64-apple-darwin', 'entrypoint': 'bin/codex', 'version': '1.0.0',
                'resourcesDir': 'codex-resources', 'pathDir': 'codex-path'}))
            with mock.patch.object(client, 'run') as run:
                with self.assertRaises(FileNotFoundError):
                    client.verify_package(package)
                run.assert_not_called()
            (package / 'codex-code-mode-host').symlink_to(helper)
            self.assertEqual(client.runtime_helper_path(package, binary), helper)




    def test_missing_helper_rejected_before_cli_execution(self):
        with tempfile.TemporaryDirectory() as t:
            package = Path(t).resolve()
            (package / 'bin').mkdir()
            (package / 'bin/codex').write_bytes(b'CLI-only fixture')
            (package / 'codex-package.json').write_text(json.dumps({
                'target': 'aarch64-apple-darwin', 'entrypoint': 'bin/codex', 'version': '1.0.0'}))
            with mock.patch.object(client, 'run') as run:
                with self.assertRaises(FileNotFoundError):
                    client.verify_package(package)
                run.assert_not_called()

    def test_update_refuses_live_sessions_before_any_download(self):
        with mock.patch.object(client, 'processes', return_value=[{'pid': 123, 'path': '/real/codex'}]), \
             mock.patch.object(client, 'locks', side_effect=contextlib.nullcontext), \
             mock.patch.object(client, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'Codex is running'):
                client.update(self.layout, '0.166.0')
            run.assert_not_called()

    def test_archive_parent_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t).resolve()
            archive = root / 'bad.tar.gz'
            with tarfile.open(archive, 'w:gz') as tf:
                info = tarfile.TarInfo('../outside')
                info.size = 1
                tf.addfile(info, io.BytesIO(b'x'))
            with self.assertRaises(tarfile.OutsideDestinationError):
                client.unpack(archive, root / 'out')
            self.assertFalse((root / 'outside').exists())

    def test_archive_escaping_link_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t).resolve()
            archive = root / 'bad.tar.gz'
            with tarfile.open(archive, 'w:gz') as tf:
                info = tarfile.TarInfo('escape')
                info.type = tarfile.SYMTYPE
                info.linkname = '../../outside'
                tf.addfile(info)
            with self.assertRaises(tarfile.LinkOutsideDestinationError):
                client.unpack(archive, root / 'out')

    def test_existing_file_never_overwritten_as_alias(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / 'codex'
            p.write_text('user data')
            with self.assertRaisesRegex(ValueError, 'non-symlink'):
                client.replace_link(p, '/somewhere')
            self.assertEqual(p.read_text(), 'user data')

    def test_switch_failure_restores_owned_aliases(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t).resolve()
            package = root / 'new'
            (package / 'bin').mkdir(parents=True)
            (package / 'bin/codex').write_text('fixture')
            selection = root / 'selection'
            selection.mkdir()
            (selection / 'current').symlink_to('/previous-package')
            (selection / 'cli').symlink_to('/previous-cli')
            alias = root / 'codex'
            alias.symlink_to('/previous-alias')
            old_replace = client.replace_link

            def failing_replace(p, target):
                if p == alias:
                    raise OSError('injected I/O failure')
                return old_replace(p, target)

            verified = {'package': str(package), 'binary': str(package / 'bin/codex'),
                        'version': '1.0.0', 'sha256': 'fixture'}
            with mock.patch.object(self.layout, 'selection_root', selection), \
                 mock.patch.object(self.layout, 'state_root', root / 'state'), \
                 mock.patch.object(self.layout, 'package_locks', []), \
                 mock.patch.object(self.layout, 'aliases', {alias: selection / 'cli'}), \
                 mock.patch.object(client, 'verify_package', return_value=verified), \
                 mock.patch.object(client, 'processes', return_value=[]), \
                 mock.patch.object(client, 'replace_link', side_effect=failing_replace):
                with self.assertRaisesRegex(OSError, 'injected'):
                    client.switch(self.layout, package)
            self.assertEqual(os.readlink(selection / 'current'), '/previous-package')
            self.assertEqual(os.readlink(selection / 'cli'), '/previous-cli')
            self.assertEqual(os.readlink(alias), '/previous-alias')
            record = json.loads(next((root / 'state').glob('client-switch-*.json')).read_text())
            self.assertEqual(record['status'], 'FAILED_OWN_ALIASES_ROLLED_BACK')

    def test_successful_switch_selects_one_binary_for_aliases(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t).resolve()
            package = root / 'new'
            (package / 'bin').mkdir(parents=True)
            (package / 'bin/codex').write_text('fixture')
            selection = root / 'selection'
            alias = root / 'codex'
            package_alias = root / 'managed/current'
            verified = {'package': str(package), 'binary': str(package / 'bin/codex'),
                        'version': '1.0.0', 'sha256': 'fixture'}
            with mock.patch.object(self.layout, 'selection_root', selection), \
                 mock.patch.object(self.layout, 'state_root', root / 'state'), \
                 mock.patch.object(self.layout, 'package_locks', []), \
                 mock.patch.object(self.layout, 'aliases', {alias: selection / 'cli', package_alias: selection / 'current'}), \
                 mock.patch.object(client, 'verify_package', return_value=verified), \
                 mock.patch.object(client, 'processes', return_value=[]):
                result = client.switch(self.layout, package)
            self.assertEqual(result['status'], 'SELECTED_AND_READBACK')
            self.assertTrue(alias.samefile(package / 'bin/codex'))
            self.assertEqual(package_alias.resolve(), package)

    def test_competing_update_refused_before_download(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t).resolve()
            with mock.patch.object(self.layout, 'selection_root', root), \
                 mock.patch.object(self.layout, 'package_locks', []), \
                 mock.patch.object(client, 'run') as run:
                with client.locks(self.layout):
                    with self.assertRaises(BlockingIOError):
                        client.update(self.layout, '1.2.3')
                run.assert_not_called()

    def test_offline_update_selects_new_package_then_retires_previous(self):
        # Exercise download-to-retirement locally. Signature/network verification
        # is replaced by fixtures, so this is not a live signed-release upgrade.
        with tempfile.TemporaryDirectory() as t:
            root = Path(t).resolve()
            releases = root / 'releases'
            old = releases / '1.0.0'
            (old / 'bin').mkdir(parents=True)
            (old / 'bin/codex').write_bytes(b'old binary fixture')
            (old / 'bin/codex-code-mode-host').write_bytes(b'old helper fixture')
            selection = root / 'selection'
            selection.mkdir()
            alias = root / 'codex'
            helper_alias = root / 'codex-code-mode-host'
            (selection / 'current').symlink_to(old)
            (selection / 'cli').symlink_to(old / 'bin/codex')
            alias.symlink_to(selection / 'cli')
            helper_alias.symlink_to(selection / 'current/bin/codex-code-mode-host')
            old_record = {'package': str(old), 'binary': str(old / 'bin/codex'),
                          'version': '1.0.0', 'sha256': client.digest(old / 'bin/codex'),
                          'helper': {'path': str(old / 'bin/codex-code-mode-host')}}
            (selection / 'authorized-client.json').write_text(json.dumps(old_record))
            archive = root / 'release.tar.gz'
            with tarfile.open(archive, 'w:gz') as tf:
                for name, data in [('package/codex-package.json', b'{"version":"1.0.1"}'),
                                   ('package/bin/codex', b'new binary fixture'),
                                   ('package/bin/codex-code-mode-host', b'new helper fixture')]:
                    info = tarfile.TarInfo(name)
                    info.size = len(data)
                    tf.addfile(info, io.BytesIO(data))

            def fake_run(argv, timeout=30):
                if argv[:2] == ['gh', 'api']:
                    return SimpleNamespace(stdout=json.dumps({'assets': [{
                        'name': 'codex-package-aarch64-apple-darwin.tar.gz',
                        'digest': 'sha256:' + client.digest(archive)}]}))
                self.assertEqual(argv[:3], ['gh', 'release', 'download'])
                shutil.copyfile(archive, Path(argv[-1]) / 'codex-package-aarch64-apple-darwin.tar.gz')
                return SimpleNamespace(stdout='')

            def fake_verify(package):
                return {'package': str(package), 'binary': str(package / 'bin/codex'),
                        'version': '1.0.1', 'sha256': client.digest(package / 'bin/codex'),
                        'helper': {'path': str(package / 'bin/codex-code-mode-host')}}

            with mock.patch.object(self.layout, 'selection_root', selection), \
                 mock.patch.object(self.layout, 'releases_root', releases), \
                 mock.patch.object(self.layout, 'state_root', root / 'state'), \
                 mock.patch.object(self.layout, 'package_locks', []), \
                 mock.patch.object(self.layout, 'aliases', {alias: selection / 'cli',
                     helper_alias: selection / 'current/bin/codex-code-mode-host'}), \
                 mock.patch.object(client, 'processes', return_value=[]), \
                 mock.patch.object(client.shutil, 'disk_usage', return_value=SimpleNamespace(free=50 * 1024**3)), \
                 mock.patch.object(client, 'run', side_effect=fake_run), \
                 mock.patch.object(client, 'verify_package', side_effect=fake_verify):
                result = client.update(self.layout, '1.0.1')
            self.assertEqual(result['status'], 'SELECTED_AND_READBACK')
            self.assertFalse(old.exists())
            self.assertEqual([p.name for p in releases.iterdir()], ['1.0.1'])
            self.assertEqual(alias.read_bytes(), b'new binary fixture')
            self.assertEqual(helper_alias.read_bytes(), b'new helper fixture')
            self.assertEqual(json.loads((selection / 'authorized-client.json').read_text())['version'], '1.0.1')


if __name__ == '__main__':
    unittest.main()
