"""Synthetic POSIX fixtures only; no native session, live history or real TTY."""
from contextlib import contextmanager
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import tempfile
import unittest
import uuid

sys.dont_write_bytecode = True
if os.name != "posix":
    raise unittest.SkipTest("These optional scripts require POSIX")

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("recovery_fixture_module", ROOT / "scripts/resume_check.py")
OBSERVER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(OBSERVER)


@contextmanager
def fixture_exclusive_lock(path):
    """A short-lived child owns only the explicitly supplied synthetic lock."""
    code = (
        "import fcntl,sys\n"
        "with open(sys.argv[1], 'rb') as stream:\n"
        "    fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)\n"
        "    print('locked', flush=True)\n"
        "    sys.stdin.read(1)\n"
    )
    child = subprocess.Popen(
        [sys.executable, "-BES", "-c", code, str(path)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True,
    )
    try:
        ready, _, _ = select.select([child.stdout], [], [], 10)
        if not ready or child.stdout.readline() != "locked\n":
            raise AssertionError("Synthetic lock holder did not become ready")
        yield
    finally:
        try:
            child.communicate("x", timeout=5)
        except subprocess.TimeoutExpired:
            child.terminate()
            child.communicate(timeout=5)
        for stream in (child.stdin, child.stdout, child.stderr):
            if stream and not stream.closed:
                stream.close()


class WriterObservationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="recovery-fixture-")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        self.home = self.base / "synthetic-codex-home"
        self.locks = self.home / "thread-writer-locks"
        self.locks.mkdir(parents=True, mode=0o700)
        self.coord = self.locks / ".coordination.lock"
        self.write(self.coord, b"")
        self.sid = str(uuid.uuid4())
        self.history = self.home / "sessions" / "synthetic.jsonl"
        self.write(self.history, self.header(self.sid))
        self.writer = self.locks / (self.sid + ".lock")
        self.target = {"agent": "codex", "sid": self.sid, "history": str(self.history)}

    @staticmethod
    def header(sid):
        return (json.dumps({"type": "session_meta", "payload": {"id": sid}}) + "\n").encode()

    @staticmethod
    def write(path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        path.chmod(0o600)

    def snapshot(self):
        result = {}
        for path in sorted(self.base.rglob("*")):
            name = path.relative_to(self.base).as_posix()
            if path.is_symlink():
                result[name] = ("symlink", os.readlink(path))
            elif path.is_file():
                info = path.stat()
                result[name] = ("file", info.st_mode, info.st_ino, info.st_size,
                                info.st_mtime_ns, hashlib.sha256(path.read_bytes()).hexdigest())
            else:
                result[name] = ("directory", path.stat().st_mode)
        return result

    def observe(self, state, reason=None):
        # Every call supplies the synthetic home; the real CODEX_HOME is unused.
        self.assertTrue(self.home.is_relative_to(self.base))
        self.assertTrue(Path(self.target["history"]).is_relative_to(self.base))
        before = self.snapshot()
        result = OBSERVER.inspect_writer(dict(self.target), codex_home=self.home)
        self.assertEqual(result["state"], state)
        if reason is not None:
            self.assertEqual(result["reason"], reason)
        self.assertIs(result["recovery_authorized"], False)
        self.assertEqual(result["file_writes"], 0)
        self.assertEqual(result["agent_launches"], 0)
        self.assertEqual(before, self.snapshot())
        return result

    def test_idle_missing_and_existing_unheld_writer(self):
        self.observe("IDLE_AT_CHECK", "no_thread_lock_under_coordination")
        self.write(self.writer, b"")
        self.observe("IDLE_AT_CHECK", "thread_lock_not_held_at_check")

    def test_writer_held_by_synthetic_child(self):
        self.write(self.writer, b"")
        with fixture_exclusive_lock(self.writer):
            self.observe("IN_USE", "native_thread_writer_lock_held")

    def test_coordination_held_by_synthetic_child(self):
        with fixture_exclusive_lock(self.coord):
            self.observe("UNKNOWN", "native_coordination_busy")

    def test_wrong_and_incomplete_history_headers(self):
        self.write(self.history, self.header(str(uuid.uuid4())))
        self.observe("UNKNOWN", "original_history_header_sid_mismatch")
        self.write(self.history, b"x" * (OBSERVER.MAX_HEADER + 1))
        self.observe("UNKNOWN", "original_history_header_incomplete")

    def test_symlink_history_is_not_canonical(self):
        link = self.history.with_name("linked-history.jsonl")
        link.symlink_to(self.history)
        self.target["history"] = str(link)
        self.observe("UNKNOWN", "original_history_outside_current_home")

    def test_symlink_writer_is_rejected(self):
        other = self.base / "synthetic-lock-target"
        self.write(other, b"")
        self.writer.symlink_to(other)
        self.observe("UNKNOWN")

    def test_group_writable_coordination_is_rejected(self):
        self.coord.chmod(0o660)
        self.observe("UNKNOWN", "native_lock_not_regular_owned_single_link")

    def test_history_outside_supplied_home_is_rejected(self):
        other = self.base / "outside-home" / "synthetic.jsonl"
        self.write(other, self.header(self.sid))
        self.target["history"] = str(other)
        self.observe("UNKNOWN", "original_history_outside_current_home")

    def test_historical_hardlink_does_not_invent_a_writer(self):
        os.link(self.history, self.history.with_name("synthetic-backup.jsonl"))
        self.observe("IDLE_AT_CHECK", "no_thread_lock_under_coordination")


class TerminalFunctionTests(unittest.TestCase):
    def run_shells(self, invoke):
        shells = [path for path in ("/bin/bash", "/bin/zsh") if Path(path).is_file()]
        self.assertTrue(shells, "At least one supported shell is needed")
        for shell in shells:
            with self.subTest(shell=Path(shell).name, invoke=invoke):
                flags = ["--noprofile", "--norc"] if shell.endswith("bash") else ["-f"]
                code = 'if [ -t 0 ] || [ -t 1 ]; then exit 99; fi\n. "$1"\n'
                if invoke:
                    code += "codex_toolchain_reset_terminal_modes\n"
                env = dict(os.environ)
                env.pop("BASH_ENV", None)
                env.pop("ENV", None)
                child = subprocess.run(
                    [shell, *flags, "-c", code, "synthetic-terminal-fixture",
                     str(ROOT / "scripts/terminal_modes.sh")],
                    stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE, env=env, timeout=10,
                )
                self.assertEqual(child.returncode, 0, child.stderr.decode(errors="replace"))
                self.assertEqual(child.stderr, b"")
                yield child.stdout

    def test_source_only_defines_function(self):
        for output in self.run_shells(False):
            self.assertEqual(output, b"")

    def test_exact_reset_bytes_are_captured_only_in_a_pipe(self):
        disabled = (9, 1000, 1002, 1003, 1005, 1006, 1015, 1016, 1004, 2004)
        expected = b"".join(f"\x1b[?{code}l".encode() for code in disabled)
        expected += b"\x1b[?25h\x1b[>m\x1b[<8u"
        for output in self.run_shells(True):
            self.assertEqual(output, expected)
            self.assertNotIn(b"\x1bc", output)
            self.assertNotIn(b"\x1b[2J", output)


if __name__ == "__main__":
    unittest.main()
