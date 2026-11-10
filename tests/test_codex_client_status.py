"""A stale registration must not hide a broken client or a moved launch alias."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from scripts import codex_client as client


class StatusTests(unittest.TestCase):
    def setUp(self):
        for name in ['run', 'processes']:
            patch = mock.patch.object(client, name, side_effect=AssertionError('Unexpected real native/network call'))
            patch.start()
            self.addCleanup(patch.stop)

    @contextlib.contextmanager
    def installed(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.ExitStack() as stack:
            base = Path(directory).resolve()
            package = base / 'package'
            package.mkdir()
            binary = package / 'codex'
            binary.write_bytes(b'fixture')
            helper = package / 'helper'
            helper.write_bytes(b'helper fixture')
            root = base / 'selection'
            root.mkdir()
            (root / 'current').symlink_to(package)
            (root / 'cli').symlink_to(binary)
            alias = base / 'codex'
            alias.symlink_to(root / 'cli')
            verified = {'package': str(package), 'binary': str(binary), 'version': '1.0.0',
                        'sha256': client.digest(binary),
                        'helper': {'path': str(helper), 'sha256': client.digest(helper)}}
            (root / 'authorized-client.json').write_text(json.dumps(verified))
            self.layout = client.Layout(root, base / 'releases', base / 'state', (),
                                        {alias: root / 'cli'}, binary, 1024)
            self.layout_path = base / 'layout.json'
            self.layout_path.write_text(json.dumps(self.layout.as_dict()))
            stack.enter_context(mock.patch.object(client, 'processes', return_value=[]))
            verify = stack.enter_context(mock.patch.object(client, 'verify_package', return_value=verified))
            yield root, alias, verified, verify

    def test_matching_selection_is_success(self):
        with self.installed(), mock.patch('sys.argv', ['codex-client', '--layout', str(self.layout_path), 'status']), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(client.main(), 0)
            self.assertEqual(json.loads(output.getvalue())['status'], 'SELECTED_CLIENT_CONSISTENT')

    def test_alias_drift_fails_even_with_no_running_processes(self):
        with self.installed() as (root, alias, _, _):
            foreign = root / 'foreign-client'
            foreign.write_text('different executable')
            alias.unlink()
            alias.symlink_to(foreign)
            with mock.patch('sys.argv', ['codex-client', '--layout', str(self.layout_path), 'status']), contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(client.main(), 1)
            result = json.loads(out.getvalue())
            self.assertEqual(result['unexpected_primary_processes'], [])
            self.assertIn('CLIENT_ALIAS_MISMATCH', [i['code'] for i in result['issues']])
            self.assertTrue(alias.samefile(foreign), 'Status must not repair aliases implicitly')

    def test_stable_cli_selector_drift_is_detected(self):
        with self.installed() as (root, _, _, _):
            (root / 'cli').unlink()
            (root / 'cli').symlink_to(root / 'missing')
            result = client.status(self.layout)
            paths = {issue.get('path') for issue in result['issues']}
            self.assertIn(str(root / 'cli'), paths)

    def test_missing_helper_fails_package_verification(self):
        with self.installed() as (_, _, _, verify):
            verify.side_effect = FileNotFoundError('code-mode helper missing')
            result = client.status(self.layout)
            self.assertEqual(result['status'], 'NEEDS_REPAIR')
            self.assertIn('SELECTED_PACKAGE_VERIFICATION_FAILED', [i['code'] for i in result['issues']])

    def test_changed_signed_package_does_not_match_stale_record(self):
        with self.installed() as (_, _, verified, verify):
            verify.return_value = {**verified, 'sha256': 'different-signed-binary'}
            self.assertIn('SELECTED_PACKAGE_RECORD_MISMATCH',
                          [i['code'] for i in client.status(self.layout)['issues']])

    def test_unknown_live_client_fails(self):
        with self.installed(), mock.patch.object(client, 'processes', return_value=[
                {'pid': 123, 'path': '/another/codex'}]):
            self.assertIn('UNEXPECTED_PRIMARY_PROCESSES', [i['code'] for i in client.status(self.layout)['issues']])

    def test_invalid_record_is_reported_without_repair(self):
        with self.installed() as (root, _, _, _):
            (root / 'authorized-client.json').write_text('[]')
            self.assertIn('CLIENT_RECORD_UNAVAILABLE', [i['code'] for i in client.status(self.layout)['issues']])
            self.assertEqual((root / 'authorized-client.json').read_text(), '[]')

    def test_helper_alias_drift_is_not_hidden_by_valid_package(self):
        with self.installed() as (root, alias, verified, _):
            helper_alias = root.parent / 'codex-code-mode-host'
            old = root / 'old-helper'
            old.write_bytes(b'old helper')
            helper_alias.symlink_to(old)
            with mock.patch.dict(self.layout.aliases, {helper_alias: root / 'current/bin/codex-code-mode-host'}):
                result = client.status(self.layout)
                self.assertEqual(result['status'], 'NEEDS_REPAIR')
                self.assertIn(str(helper_alias), [x.get('path') for x in result['issues']])
                self.assertTrue(helper_alias.samefile(old))
                helper_alias.unlink()
                helper_alias.symlink_to(verified['helper']['path'])
                self.assertEqual(client.status(self.layout)['status'], 'SELECTED_CLIENT_CONSISTENT')

    def test_running_old_helpers_are_visible_without_killing_them(self):
        with self.installed() as (_, _, verified, _):
            old = {'pid': 44, 'path': '/previous/bin/codex-code-mode-host'}
            current = {'pid': 45, 'path': verified['binary']}
            with mock.patch.object(client, 'processes', side_effect=lambda include_helpers=False: [current, old] if include_helpers else [current]):
                result = client.status(self.layout)
            self.assertEqual(result['status'], 'SELECTED_CLIENT_CONSISTENT')
            self.assertEqual(result['legacy_helper_processes'], [old])
            self.assertEqual(result['helper_migration'], 'LEGACY_HELPERS_ACTIVE')

    def test_live_adoption_corrects_helper_alias_preserving_old_file(self):
        with self.installed() as (root, alias, verified, _):
            package = Path(verified['package'])
            (package / 'bin').mkdir()
            (package / 'bin/codex-code-mode-host').symlink_to(verified['helper']['path'])
            helper_alias = root.parent / 'codex-code-mode-host'
            old = root / 'old-helper'
            old.write_bytes(b'active old helper')
            helper_alias.symlink_to(old)
            with mock.patch.dict(self.layout.aliases, {helper_alias: root / 'current/bin/codex-code-mode-host'}), \
                 mock.patch.object(self.layout, 'state_root', root / 'state'), \
                 mock.patch.object(self.layout, 'package_locks', []), \
                 mock.patch.object(self.layout, 'cli', Path(verified['binary'])), \
                 mock.patch.object(client, 'processes', return_value=[{'pid': 44, 'path': str(old)}]):
                with old.open('rb') as active_handle:
                    result = client.switch(self.layout, package, adopt=True)
                    self.assertEqual(active_handle.read(), b'active old helper')
            self.assertEqual(result['status'], 'SELECTED_AND_READBACK')
            self.assertTrue(helper_alias.samefile(verified['helper']['path']))
            self.assertTrue(alias.samefile(verified['binary']))
            self.assertEqual(old.read_bytes(), b'active old helper')


if __name__ == '__main__':
    unittest.main()
