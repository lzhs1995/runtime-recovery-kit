"""Explicit doctor layouts, using synthetic files and intercepted native calls."""
import contextlib
import io
import json
from pathlib import Path
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from scripts import toolchain_doctor as doctor


class DoctorLayoutTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.config = self.base / 'fixture-config.toml'
        self.config.write_text('')
        self.package = self.base / 'fixture-package'
        (self.package / 'bin').mkdir(parents=True)
        self.cli = self.package / 'bin/codex'
        self.cli.write_bytes(b'synthetic CLI; never executed')
        self.helper = self.package / 'bin/codex-code-mode-host'
        self.helper.write_bytes(b'synthetic helper; never executed')
        self.app = self.base / 'Fixture.app'
        runtime = self.app / 'Contents/Resources/cua_node'
        for relative in ['bin/node', 'bin/node_repl',
                         'lib/node_modules/@oai/cua-repl/bin/cua-repl.mjs']:
            path = runtime / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'synthetic runtime; never executed')
        self.cache = self.base / 'chosen-cache/signature.json'
        self.report = self.base / 'chosen-report/doctor.json'
        self.team = '2DC432GLL2'
        self.verify_code = 0
        self.mutate_on_verify = False
        self.calls = []
        native = mock.patch.object(doctor.subprocess, 'run', side_effect=self.native_result)
        native.start()
        self.addCleanup(native.stop)
        environment = mock.patch.object(doctor.os, 'environ', {
            'CMUX_CODEX_PID': 'synthetic-inherited-pid',
            'CODEX_THREAD_ID': 'synthetic-inherited-thread',
        })
        environment.start()
        self.addCleanup(environment.stop)
        observe = mock.patch.object(doctor, 'observe_active_cli',
                                    side_effect=AssertionError('No live PID inspection in fixtures'))
        observe.start()
        self.addCleanup(observe.stop)

    def native_result(self, argv, **kwargs):
        # 所有原生调用均拦截；任何非预期命令直接令测试失败。
        self.assertEqual(argv[0], '/usr/bin/codesign')
        self.assertEqual(argv[-1], str(self.cli))
        self.calls.append(list(argv))
        if argv[1:-1] == ['-dv', '--verbose=4']:
            return SimpleNamespace(returncode=0, stdout='',
                                   stderr=f'TeamIdentifier={self.team}\n')
        self.assertEqual(argv[1:-1], ['--verify', '--strict'])
        if self.mutate_on_verify:
            self.cli.write_bytes(b'changed synthetic CLI during verification')
        return SimpleNamespace(returncode=self.verify_code, stdout='', stderr='')

    def run_doctor(self, **overrides):
        options = dict(cli=self.cli, package=self.package,
                       app_candidates=[self.app])
        options.update(overrides)
        return doctor.run(self.config, **options)

    def argv(self, *extra):
        return ['toolchain_doctor.py', '--config', str(self.config),
                '--cli', str(self.cli), '--package', str(self.package),
                '--app-candidates', str(self.app), *extra]

    def snapshot(self):
        return {str(path.relative_to(self.base)): path.read_bytes()
                for path in self.base.rglob('*') if path.is_file()}

    def test_explicit_cli_layout_without_cache_or_output_writes_nothing(self):
        before = self.snapshot()
        output = io.StringIO()
        with mock.patch.object(doctor.sys, 'argv', self.argv()), contextlib.redirect_stdout(output):
            self.assertEqual(doctor.main(), 0)
        result = json.loads(output.getvalue())
        self.assertEqual(result['status'], 'PASS_CONFIG_ONLY')
        self.assertEqual(result['observations']['official_cli'], str(self.cli))
        self.assertEqual(result['observations']['selected_package_helper']['runtime_path'], str(self.helper))
        self.assertFalse(result['observations']['identity_authenticated'])
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(len(self.calls), 2)

    def test_explicit_cache_and_output_follow_original_private_file_protocol(self):
        output = io.StringIO()
        with mock.patch.object(doctor.sys, 'argv', self.argv('--cache', str(self.cache), '--output', str(self.report))), contextlib.redirect_stdout(output):
            self.assertEqual(doctor.main(), 0)
        result = json.loads(output.getvalue())
        self.assertEqual(json.loads(self.report.read_text()), result)
        self.assertTrue(json.loads(self.cache.read_text())['verified'])
        for path in [self.cache, self.report]:
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertEqual(list(path.parent.glob('*.tmp')), [])

    def test_startup_preserves_pending_cache_and_nonblocking_status(self):
        first = self.run_doctor(startup=True)
        self.assertIsNone(first['observations']['official_cli_signature']['verified'])
        self.assertEqual(len(self.calls), 1)
        self.assertFalse(self.cache.exists())
        self.run_doctor(cache_path=self.cache)
        cached_bytes = self.cache.read_bytes()
        self.calls.clear()
        cached = self.run_doctor(startup=True, cache_path=self.cache)
        self.assertEqual(cached['observations']['official_cli_signature']['scope'],
                         'cached_full_verification_same_file_identity')
        self.assertEqual(self.cache.read_bytes(), cached_bytes)
        self.assertEqual(len(self.calls), 1)
        self.team = 'WRONG_FIXTURE_TEAM'
        self.calls.clear()
        output = io.StringIO()
        with mock.patch.object(doctor.sys, 'argv', self.argv('--startup', '--cache', str(self.cache))), contextlib.redirect_stdout(output):
            self.assertEqual(doctor.main(), 0)
        self.assertIn('OFFICIAL_CODEX_SIGNATURE_INVALID', output.getvalue())
        self.assertEqual(self.cache.read_bytes(), cached_bytes)
        self.assertEqual(len(self.calls), 1)

    def test_invalid_signature_or_changed_file_does_not_create_cache(self):
        for case in ['signature_failure', 'wrong_team', 'changed_file']:
            with self.subTest(case=case):
                self.team = 'WRONG_FIXTURE_TEAM' if case == 'wrong_team' else '2DC432GLL2'
                self.verify_code = 1 if case == 'signature_failure' else 0
                self.mutate_on_verify = case == 'changed_file'
                result = self.run_doctor(cache_path=self.cache)
                self.assertIn('OFFICIAL_CODEX_SIGNATURE_INVALID',
                              [item['code'] for item in result['issues']])
                self.assertFalse(self.cache.exists())

    def test_helper_mismatch_is_reported_through_real_layout_function(self):
        resource = self.package / 'codex-resources/codex-code-mode-host'
        resource.parent.mkdir()
        resource.write_bytes(b'different synthetic helper')
        result = self.run_doctor()
        self.assertIn('RUNTIME_CODEX_HELPER_UNAVAILABLE',
                      [item['code'] for item in result['issues']])
        self.assertFalse(self.cache.exists())

    def test_explicit_empty_app_candidates_does_not_guess_system_apps(self):
        result = self.run_doctor(app_candidates=[])
        self.assertIsNone(result['observations']['cua_runtime'])
        self.assertIn('OFFICIAL_CUA_RUNTIME_MISSING',
                      [item['code'] for item in result['issues']])

    def test_cli_requires_layout_before_any_inspection(self):
        output = io.StringIO()
        with mock.patch.object(doctor.sys, 'argv', ['toolchain_doctor.py']), contextlib.redirect_stderr(output):
            with self.assertRaises(SystemExit) as error:
                doctor.main()
        self.assertEqual(error.exception.code, 2)
        self.assertEqual(self.calls, [])
        for option in ['--config', '--cli', '--package', '--app-candidates']:
            self.assertIn(option, output.getvalue())


    def test_missing_explicit_package_is_reported(self):
        missing = self.base / 'missing-package'
        before = self.snapshot()
        result = self.run_doctor(package=missing)
        self.assertEqual(result['status'], 'NEEDS_REPAIR')
        self.assertIn({'code': 'SELECTED_CODEX_PACKAGE_MISSING', 'path': str(missing)},
                      result['issues'])
        self.assertNotIn('selected_package_helper', result['observations'])
        self.assertEqual(self.snapshot(), before)


if __name__ == '__main__':
    unittest.main()
