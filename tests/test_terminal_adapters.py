"""終端適配器差量；僅管道、暫存檔案及合成環境標記。"""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'


class TerminalAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='terminal-adapter-fixture-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.scripts = self.root / 'checkout with spaces' / 'scripts'
        self.scripts.mkdir(parents=True)
        for name in ('terminal_modes.sh', 'codex-terminal-recover', 'terminal_prompt_recovery.zsh'):
            shutil.copy2(SCRIPTS / name, self.scripts / name)
        self.env = dict(os.environ, ZDOTDIR=str(self.root / 'empty-zdotdir'), CMUX_SURFACE_ID='synthetic-fixture')
        Path(self.env['ZDOTDIR']).mkdir()

    def shell(self, executable, *args):
        if not Path(executable).is_file():
            self.skipTest(executable + ' unavailable')
        return subprocess.run([executable, *args], stdin=subprocess.DEVNULL, capture_output=True,
                              env=self.env, cwd=self.root, timeout=5)

    def command(self, flag):
        return self.shell('/bin/bash', str(self.scripts / 'codex-terminal-recover'), flag)

    def zsh(self, code, *, interactive=False):
        return self.shell('/bin/zsh', '-fi' if interactive else '-f', '-c', code, 'fixture',
                          str(self.scripts / 'terminal_prompt_recovery.zsh'))

    def test_shell_syntax(self):
        for executable, name in (('/bin/bash', 'codex-terminal-recover'),
                                 ('/bin/zsh', 'terminal_prompt_recovery.zsh')):
            with self.subTest(shell=executable):
                result = self.shell(executable, '-n', str(self.scripts / name))
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_manual_check_is_text_only(self):
        result = self.command('--check')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(b'Terminal recovery:', result.stdout)
        self.assertNotIn(b'\x1b', result.stdout + result.stderr)

    def test_manual_invalid_argument_refused(self):
        result = self.command('--not-an-operation')
        self.assertEqual(result.returncode, 64)
        self.assertIn(b'Usage:', result.stderr)
        self.assertEqual(result.stdout, b'')

    def test_manual_actions_silent_without_tty(self):
        for flag in ('--before-launch', '--shell'):
            with self.subTest(flag=flag):
                result = self.command(flag)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout + result.stderr, b'')

    def test_relocated_zsh_loads_function_silently(self):
        result = self.zsh('source "$1"; whence -w codex_toolchain_reset_terminal_modes')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, b'codex_toolchain_reset_terminal_modes: function\n')
        self.assertEqual(result.stderr, b'')

    def test_repeated_zsh_source_registers_one_prompt_hook(self):
        result = self.zsh('source "$1"; source "$1"; '
                          'print -rl -- "${precmd_functions[@]}"')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines().count(b'_codex_toolchain_prompt_recovery'), 1)
        self.assertNotIn(b'\x1b', result.stdout + result.stderr)

    def test_zsh_prompt_preserves_previous_status(self):
        result = self.zsh('source "$1"; false; _codex_toolchain_prompt_recovery; '
                          'fixture_status=$?; print -r -- "$fixture_status"')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, b'1\n')
        self.assertEqual(result.stderr, b'')

    def test_interactive_zsh_without_tty_does_not_reset(self):
        result = self.zsh('source "$1"; _codex_toolchain_prompt_recovery', interactive=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, b'')
        self.assertNotIn(b'\x1b', result.stderr)


if __name__ == '__main__':
    unittest.main()
