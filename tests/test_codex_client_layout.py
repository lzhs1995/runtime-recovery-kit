"""Layout and plan boundaries; no installed clients, native calls or downloads."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from scripts import codex_client as client


class ClientLayoutTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.layout = client.Layout(self.base / 'selection', self.base / 'releases',
                                    self.base / 'state', (), {}, self.base / 'cli', 1024)
        self.path = self.base / 'layout.json'
        self.path.write_text(json.dumps(self.layout.as_dict()))
        self.plan_path = self.base / 'plan.json'
        for name in ['run', 'processes']:
            patch = mock.patch.object(client, name, side_effect=AssertionError('Unexpected native call'))
            patch.start()
            self.addCleanup(patch.stop)

    def make_update_plan(self):
        plan = client.make_plan(self.path, 'update', version='1.2.3')
        ref = client.write_plan(self.plan_path, plan)
        return plan, ref

    def test_config_and_plan_do_not_inspect_or_change_installation(self):
        output = io.StringIO()
        with mock.patch('sys.argv', ['codex-client', '--layout', str(self.path), 'config']), contextlib.redirect_stdout(output):
            self.assertEqual(client.main(), 0)
        self.assertEqual(json.loads(output.getvalue()), self.layout.as_dict())
        with mock.patch.object(client.shutil, 'disk_usage', side_effect=AssertionError('No capacity preflight in plan')):
            plan, ref = self.make_update_plan()
        self.assertFalse(plan['preflight_performed'])
        self.assertFalse(plan['network_performed'])
        self.assertEqual(ref, client.file_reference(self.plan_path)[0])
        self.assertEqual(sorted(path.name for path in self.base.iterdir()), ['layout.json', 'plan.json'])

    def test_layout_requires_explicit_valid_paths_and_capacity(self):
        original = self.layout.as_dict()
        for invalid in [True, False, 0, -1, 1.5]:
            with self.subTest(capacity=invalid):
                value = dict(original, minimum_free_bytes=invalid)
                self.path.write_text(json.dumps(value))
                with self.assertRaises(ValueError):
                    client.load_layout(self.path)
                with self.assertRaises(ValueError):
                    client.Layout(self.base, self.base, self.base, (), {}, self.base, invalid)
        for value in [dict(original, cli='relative-cli'),
                      {key: value for key, value in original.items() if key != 'state_root'},
                      dict(original, aliases={str(self.layout.selection_root / 'current'): str(self.base / 'other')}),
                      dict(original, package_locks=[str(self.base / 'lock'), str(self.base / 'lock')])]:
            with self.subTest(layout=value):
                self.path.write_text(json.dumps(value))
                with self.assertRaises(ValueError):
                    client.load_layout(self.path)

    def test_capacity_is_compared_before_any_download(self):
        self.layout.releases_root.mkdir()
        with mock.patch.object(client, 'processes', return_value=[]), \
                mock.patch.object(client.shutil, 'disk_usage', return_value=SimpleNamespace(free=1023)):
            with self.assertRaisesRegex(ValueError, '1024 actual free bytes'):
                client.update(self.layout, '1.2.3')
        self.assertFalse(self.layout.state_root.exists())
        self.assertEqual(list(self.layout.releases_root.iterdir()), [])

    def test_apply_dispatches_bound_action_to_original_engine(self):
        _, ref = self.make_update_plan()
        with mock.patch.object(client, 'update', return_value={'fixture': 'update'}) as update:
            self.assertEqual(client.apply_plan(self.path, self.plan_path, ref['sha256']), {'fixture': 'update'})
        self.assertEqual(update.call_args.args[0].as_dict(), self.layout.as_dict())
        self.assertEqual(update.call_args.args[1], '1.2.3')
        adopt_path = self.base / 'adopt-plan.json'
        package = self.base / 'supplied-package'
        plan = client.make_plan(self.path, 'adopt', package=package)
        ref = client.write_plan(adopt_path, plan)
        with mock.patch.object(client, 'switch', return_value={'fixture': 'adopt'}) as switch:
            self.assertEqual(client.apply_plan(self.path, adopt_path, ref['sha256']), {'fixture': 'adopt'})
        self.assertEqual(switch.call_args.args[0].as_dict(), self.layout.as_dict())
        self.assertEqual(switch.call_args.args[1], package)
        self.assertEqual(switch.call_args.kwargs, {'adopt': True})

    def test_changed_plan_or_layout_refuses_before_engine(self):
        plan, ref = self.make_update_plan()
        original_plan = self.plan_path.read_bytes()
        self.plan_path.write_bytes(original_plan + b'\n')
        with mock.patch.object(client, 'update') as update, mock.patch.object(client, 'switch') as switch:
            with self.assertRaisesRegex(ValueError, 'Plan bytes changed'):
                client.apply_plan(self.path, self.plan_path, ref['sha256'])
            self.plan_path.write_bytes(original_plan)
            self.path.write_text(json.dumps(dict(self.layout.as_dict(), minimum_free_bytes=2048)))
            with self.assertRaisesRegex(ValueError, 'Plan layout/action changed'):
                client.apply_plan(self.path, self.plan_path, ref['sha256'])
            update.assert_not_called()
            switch.assert_not_called()

    def test_apply_uses_the_same_layout_bytes_that_it_binds(self):
        _, ref = self.make_update_plan()
        original_reference = client.file_reference

        def reference(path):
            result = original_reference(path)
            if Path(path) == self.path:
                self.path.write_text(json.dumps(dict(self.layout.as_dict(), minimum_free_bytes=9999)))
            return result

        with mock.patch.object(client, 'file_reference', side_effect=reference), \
                mock.patch.object(client, 'update', return_value={'fixture': True}) as update:
            client.apply_plan(self.path, self.plan_path, ref['sha256'])
        self.assertEqual(update.call_args.args[0].minimum_free_bytes, 1024)
        self.assertEqual(json.loads(self.path.read_text())['minimum_free_bytes'], 9999)

    def test_plan_write_preserves_existing_plan(self):
        plan, _ = self.make_update_plan()
        before = self.plan_path.read_bytes()
        with self.assertRaises(FileExistsError):
            client.write_plan(self.plan_path, plan)
        self.assertEqual(self.plan_path.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
