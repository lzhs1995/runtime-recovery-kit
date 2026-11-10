"""Dispatcher contracts using temporary fake executables; no real agent launch."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


DISPATCHER = Path(__file__).resolve().parents[1] / 'scripts/agent_dispatch.py'
FAKE = '''import json, os, sys
print(json.dumps({'pid': os.getpid(), 'argv': sys.argv[1:],
                  'marker': os.environ.get('HERDR_AGENT'),
                  'sentinel': os.environ.get('DISPATCH_FIXTURE_SENTINEL'),
                  'cwd': os.getcwd()}, ensure_ascii=False))
raise SystemExit(int(os.environ.get('DISPATCH_FIXTURE_EXIT', '0')))
'''


class AgentDispatchTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='dispatcher-fixture-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.fake = self.root / 'fake adapter.py'
        self.fake.write_text(FAKE, encoding='utf-8')
        self.config = self.root / 'private config.json'
        self.prefix = [sys.executable, '-BES', str(self.fake), 'fixed prefix']
        self.write_config({'adapters': {'alpha': self.prefix, 'alias': self.prefix,
                                        'inherit': self.prefix},
                           'herdr_agent': {'alpha': 'exact-label', 'alias': 'exact-label'}})
        self.env = dict(os.environ, HERDR_AGENT='inherited-label',
                        DISPATCH_FIXTURE_SENTINEL='unchanged', DISPATCH_FIXTURE_EXIT='0')

    def write_config(self, value):
        self.config.write_text(json.dumps(value), encoding='utf-8')

    def run_dispatch(self, *args):
        process = subprocess.Popen([sys.executable, '-BES', str(DISPATCHER), *args],
                                   cwd=self.root, env=self.env, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            stdout, stderr = process.communicate(timeout=5)
        except BaseException:
            process.kill()
            process.communicate()
            raise
        return process.pid, process.returncode, stdout, stderr

    def selected(self, key, *args):
        return self.run_dispatch('--config', str(self.config), key, *args)

    def test_exec_preserves_pid_exact_argv_cwd_and_exit(self):
        self.env['DISPATCH_FIXTURE_EXIT'] = '23'
        tail = ['', 'two words', '繁體中文', '--', '--config', 'child-value',
                '$(touch should-not-exist)', '`literal`', '; echo literal', '$HOME', '"quoted"']
        pid, code, stdout, stderr = self.selected('alpha', *tail)
        value = json.loads(stdout)
        self.assertEqual(code, 23)
        self.assertEqual(value['pid'], pid)
        self.assertEqual(value['argv'], ['fixed prefix', *tail])
        self.assertEqual(value['cwd'], str(self.root))
        self.assertEqual(value['marker'], 'exact-label')
        self.assertEqual(value['sentinel'], 'unchanged')
        self.assertEqual(stderr, '')
        self.assertFalse((self.root / 'should-not-exist').exists())

    def test_explicit_alias_uses_same_command_and_marker(self):
        for key in ('alpha', 'alias'):
            with self.subTest(key=key):
                _, code, stdout, stderr = self.selected(key, '--literal')
                value = json.loads(stdout)
                self.assertEqual(code, 0)
                self.assertEqual(value['argv'], ['fixed prefix', '--literal'])
                self.assertEqual(value['marker'], 'exact-label')
                self.assertEqual(stderr, '')

    def test_missing_marker_inherits_existing_or_absent_value(self):
        for expected in ('inherited-label', None):
            if expected is None:
                self.env.pop('HERDR_AGENT', None)
            with self.subTest(expected=expected):
                _, code, stdout, stderr = self.selected('inherit')
                self.assertEqual(code, 0)
                self.assertEqual(json.loads(stdout)['marker'], expected)
                self.assertEqual(stderr, '')

    def test_no_marker_mapping_preserves_environment(self):
        self.write_config({'adapters': {'alpha': self.prefix}})
        _, code, stdout, stderr = self.selected('alpha')
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(stdout)['marker'], 'inherited-label')
        self.assertEqual(stderr, '')

    def test_unknown_or_missing_selector_exits_two_without_exec(self):
        cases = [(), ('--config', str(self.config)),
                 ('--config', str(self.config), 'unknown')]
        for args in cases:
            with self.subTest(args=args):
                _, code, stdout, stderr = self.run_dispatch(*args)
                self.assertEqual(code, 2)
                self.assertEqual(stdout, '')
                self.assertTrue(stderr)

    def test_invalid_config_is_rejected_before_exec(self):
        invalid = [None, {}, {'adapters': {'alpha': 'not an argv array'}},
                   {'adapters': {'alpha': []}}, {'adapters': {'alpha': ['']}},
                   {'adapters': {'alpha': [sys.executable, '\0']}},
                   {'adapters': {'alpha': self.prefix}, 'herdr_agent': {'alpha': True}},
                   {'adapters': {'alpha': self.prefix}, 'herdr_agent': {'unknown': 'label'}},
                   {'adapters': {'alpha': self.prefix}, 'unknown_setting': True}]
        for value in invalid:
            with self.subTest(value=value):
                self.write_config(value)
                _, code, stdout, _ = self.selected('alpha')
                self.assertEqual(code, 2)
                self.assertEqual(stdout, '')
        for raw in ('{', '{"adapters": {}, "adapters": {}}'):
            self.config.write_text(raw, encoding='utf-8')
            _, code, stdout, _ = self.selected('alpha')
            self.assertEqual(code, 2)
            self.assertEqual(stdout, '')

    def test_missing_or_nonexecutable_command_keeps_shell_error_codes(self):
        blocked = self.root / 'not executable'
        blocked.write_text('fixture', encoding='utf-8')
        blocked.chmod(0o600)
        for executable, expected in ((self.root / 'missing-executable', 127), (blocked, 126)):
            with self.subTest(expected=expected):
                self.write_config({'adapters': {'alpha': [str(executable)]}})
                _, code, stdout, stderr = self.selected('alpha')
                self.assertEqual(code, expected)
                self.assertEqual(stdout, '')
                self.assertTrue(stderr)


if __name__ == '__main__':
    unittest.main()
