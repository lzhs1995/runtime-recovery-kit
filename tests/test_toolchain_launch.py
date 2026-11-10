"""Launcher contracts with temporary fake programs and pipes; no live CLI/TTY."""
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest


LAUNCHER = Path(__file__).resolve().parents[1] / 'scripts/toolchain_launch.py'
FAKE = '''import argparse, json, os, pathlib, sys
value = {'kind': KIND, 'pid': os.getpid(), 'argv': sys.argv[1:],
         'cwd': os.getcwd(), 'marker': os.environ.get('HERDR_AGENT'),
         'sentinel': os.environ.get('LAUNCH_FIXTURE_SENTINEL'),
         'no_bytecode': sys.flags.dont_write_bytecode,
         'ignore_environment': sys.flags.ignore_environment}
if KIND == 'doctor':
    parser = argparse.ArgumentParser()
    for name in ('config', 'cli', 'package', 'output'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--app-candidates', nargs='*', required=True)
    parser.add_argument('--cache')
    parser.add_argument('--startup', action='store_true')
    options = parser.parse_args()
    value['options'] = vars(options)
    output = pathlib.Path(options.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(value), encoding='utf-8')
    print('fake-doctor-stdout')
    print('fake-doctor-stderr', file=sys.stderr)
elif KIND == 'cli':
    value['stdin'] = sys.stdin.read()
    print(json.dumps(value, ensure_ascii=False))
with open(os.environ['LAUNCH_FIXTURE_EVENTS'], 'a', encoding='utf-8') as stream:
    stream.write(json.dumps(value) + '\\n')
raise SystemExit(int(os.environ.get('LAUNCH_FIXTURE_' + KIND.upper() + '_EXIT', '0')))
'''


class ToolchainLaunchTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='launcher fixture ')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.events = self.root / 'events.jsonl'
        self.layout_file = self.root / 'private layout.json'
        self.doctor = self.root / 'fake doctor.py'
        self.doctor.write_text("KIND = 'doctor'\n" + FAKE, encoding='utf-8')
        self.cli = self.fake_executable('cli')
        self.helper = self.fake_executable('helper')
        self.layout = {'python': sys.executable, 'doctor': str(self.doctor),
                       'cli': str(self.cli), 'terminal_recover': str(self.helper),
                       'report': str(self.root / 'reports' / 'result.json'),
                       'doctor_config': str(self.root / 'private config.toml'),
                       'package': str(self.root / 'fixture package'), 'app_candidates': []}
        self.write_layout()
        self.env = dict(os.environ, LAUNCH_FIXTURE_EVENTS=str(self.events),
                        LAUNCH_FIXTURE_SENTINEL='inherited-value', HERDR_AGENT='inherited-label',
                        LAUNCH_FIXTURE_CLI_EXIT='0', LAUNCH_FIXTURE_DOCTOR_EXIT='0',
                        LAUNCH_FIXTURE_HELPER_EXIT='0')

    def fake_executable(self, kind):
        script = self.root / ('fake ' + kind + '.py')
        script.write_text('KIND = ' + repr(kind) + '\n' + FAKE, encoding='utf-8')
        entry = self.root / ('fake ' + kind)
        entry.write_text('#!/bin/sh\nexec ' + shlex.quote(sys.executable) +
                         ' -BES ' + shlex.quote(str(script)) + ' "$@"\n', encoding='utf-8')
        entry.chmod(0o700)
        return entry

    def write_layout(self, value=None):
        self.layout_file.write_text(json.dumps(self.layout if value is None else value),
                                    encoding='utf-8')

    def launch(self, *args, ttys=None, raw_args=None):
        if self.events.exists():
            self.events.unlink()
        entry = LAUNCHER
        if ttys is not None:
            entry = self.root / 'mock tty runner.py'
            entry.write_text('import importlib.util, sys\n'
                             'spec = importlib.util.spec_from_file_location("launcher", ' +
                             repr(str(LAUNCHER)) + ')\n'
                             'module = importlib.util.module_from_spec(spec)\n'
                             'spec.loader.exec_module(module)\n'
                             'module.os.isatty = lambda fd: ' + repr(ttys) + '[fd]\n'
                             'raise SystemExit(module.main())\n', encoding='utf-8')
        tail = ['--layout', str(self.layout_file), *args] if raw_args is None else raw_args
        process = subprocess.Popen([sys.executable, '-BES', str(entry), *tail],
                                   cwd=self.root, env=self.env, stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            stdout, stderr = process.communicate('fixture stdin\n', timeout=8)
        except BaseException:
            process.kill()
            process.communicate()
            raise
        events = ([json.loads(line) for line in self.events.read_text().splitlines()]
                  if self.events.exists() else [])
        return process.pid, process.returncode, stdout, stderr, events

    def test_exec_preserves_pid_full_argv_environment_cwd_and_piped_stdin(self):
        self.env['LAUNCH_FIXTURE_CLI_EXIT'] = '23'
        tail = ['', 'two words', '繁體中文', '--', '--layout', 'child-value',
                '$(touch should-not-exist)', '`literal`', '; echo literal', '$HOME']
        pid, code, stdout, stderr, events = self.launch(*tail)
        value = json.loads(stdout)
        self.assertEqual((code, value['pid'], value['argv']), (23, pid, tail))
        self.assertEqual(value['stdin'], 'fixture stdin\n')
        self.assertEqual(value['cwd'], str(self.root))
        self.assertEqual((value['marker'], value['sentinel']),
                         ('inherited-label', 'inherited-value'))
        self.assertEqual([event['kind'] for event in events], ['doctor', 'cli'])
        self.assertEqual(stderr, 'fake-doctor-stderr\nfake-doctor-stdout\n')
        doctor = events[0]
        self.assertEqual((doctor['no_bytecode'], doctor['ignore_environment']), (1, 1))
        self.assertTrue(doctor['options']['startup'])
        self.assertEqual(doctor['options']['app_candidates'], [])
        self.assertIsNone(doctor['options']['cache'])
        self.assertEqual(json.loads(Path(self.layout['report']).read_text()), doctor)
        self.assertFalse((self.root / 'should-not-exist').exists())

    def test_doctor_only_execs_report_writer_and_ignores_tail(self):
        self.layout['cache'] = str(self.root / 'chosen cache.json')
        self.layout['app_candidates'] = [str(self.root / 'app one'), str(self.root / 'app two')]
        self.write_layout()
        self.env['LAUNCH_FIXTURE_DOCTOR_EXIT'] = '7'
        pid, code, stdout, stderr, events = self.launch('--doctor-only', '--unused', '',
                                                     ttys=(True, True))
        self.assertEqual((code, stdout, stderr),
                         (7, 'fake-doctor-stdout\n', 'fake-doctor-stderr\n'))
        self.assertEqual([event['kind'] for event in events], ['doctor'])
        doctor = events[0]
        self.assertEqual(doctor['pid'], pid)
        self.assertEqual((doctor['no_bytecode'], doctor['ignore_environment']), (1, 1))
        self.assertFalse(doctor['options']['startup'])
        self.assertNotIn('--unused', doctor['argv'])
        for key in ('cli', 'package', 'app_candidates', 'cache'):
            self.assertEqual(doctor['options'][key], self.layout[key])
        self.assertEqual(doctor['options']['config'], self.layout['doctor_config'])
        self.assertEqual(json.loads(Path(self.layout['report']).read_text()), doctor)

    def test_later_doctor_only_is_an_ordinary_client_argument(self):
        _, code, stdout, _, events = self.launch('resume', '--doctor-only')
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(stdout)['argv'], ['resume', '--doctor-only'])
        self.assertTrue(events[0]['options']['startup'])

    def test_nonzero_startup_doctor_still_reaches_cli(self):
        self.env['LAUNCH_FIXTURE_DOCTOR_EXIT'] = '17'
        self.env['LAUNCH_FIXTURE_CLI_EXIT'] = '19'
        _, code, stdout, stderr, events = self.launch()
        self.assertEqual(code, 19)
        self.assertEqual(json.loads(stdout)['argv'], [])
        self.assertEqual([event['kind'] for event in events], ['doctor', 'cli'])
        self.assertIn('fake-doctor-stdout', stderr)

    def test_missing_startup_doctor_or_interpreter_still_reaches_cli_without_report(self):
        original = dict(self.layout)
        for key in ('doctor', 'python'):
            with self.subTest(key=key):
                self.layout = dict(original, **{key: str(self.root / 'missing dependency')})
                self.write_layout()
                _, code, stdout, stderr, events = self.launch('literal')
                self.assertEqual(code, 0)
                self.assertEqual(json.loads(stdout)['argv'], ['literal'])
                self.assertEqual([event['kind'] for event in events], ['cli'])
                self.assertTrue(stderr)
                self.assertFalse(Path(self.layout['report']).exists())

    def test_helper_requires_both_ttys_and_runs_before_doctor(self):
        for ttys in ((False, False), (True, False), (False, True), (True, True)):
            with self.subTest(ttys=ttys):
                _, code, _, _, events = self.launch(ttys=ttys)
                expected = ['helper', 'doctor', 'cli'] if all(ttys) else ['doctor', 'cli']
                self.assertEqual((code, [event['kind'] for event in events]), (0, expected))
                if all(ttys):
                    self.assertEqual(events[0]['argv'], ['--before-launch'])

    def test_helper_failure_or_absence_does_not_block_doctor_and_cli(self):
        self.env['LAUNCH_FIXTURE_HELPER_EXIT'] = '13'
        for missing in (False, True):
            with self.subTest(missing=missing):
                if missing:
                    self.layout['terminal_recover'] = str(self.root / 'missing helper')
                    self.write_layout()
                _, code, _, _, events = self.launch(ttys=(True, True))
                self.assertEqual(code, 0)
                self.assertEqual([event['kind'] for event in events][-2:], ['doctor', 'cli'])

    def test_invalid_layout_or_entry_is_rejected_before_dependencies(self):
        invalid = [{}, [], dict(self.layout, python='relative'),
                   dict(self.layout, cli='\0'), dict(self.layout, app_candidates=None),
                   dict(self.layout, app_candidates=['relative']), dict(self.layout, cache=None),
                   dict(self.layout, unknown=True)]
        for value in invalid:
            with self.subTest(value=value):
                self.write_layout(value)
                _, code, stdout, _, events = self.launch()
                self.assertEqual((code, stdout, events), (2, '', []))
        for raw in ('{', '{"python": "x", "python": "y"}'):
            self.layout_file.write_text(raw, encoding='utf-8')
            _, code, stdout, _, events = self.launch()
            self.assertEqual((code, stdout, events), (2, '', []))
        for args in ([], ['--layout'], ['--wrong', str(self.layout_file)]):
            _, code, stdout, _, events = self.launch(raw_args=args)
            self.assertEqual((code, stdout, events), (2, '', []))

    def test_final_exec_failures_keep_shell_style_statuses(self):
        blocked = self.root / 'not executable'
        blocked.write_text('fixture', encoding='utf-8')
        blocked.chmod(0o600)
        original = dict(self.layout)
        for doctor_only in (False, True):
            for path, expected in ((self.root / 'missing executable', 127), (blocked, 126)):
                with self.subTest(doctor_only=doctor_only, expected=expected):
                    key = 'python' if doctor_only else 'cli'
                    self.layout = dict(original, **{key: str(path)})
                    self.write_layout()
                    _, code, stdout, stderr, events = self.launch(
                        *(['--doctor-only'] if doctor_only else []))
                    self.assertEqual((code, stdout), (expected, ''))
                    self.assertIn('exec failed', stderr)
                    self.assertEqual([event['kind'] for event in events],
                                     [] if doctor_only else ['doctor'])


if __name__ == '__main__':
    unittest.main()
