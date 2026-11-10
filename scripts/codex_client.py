#!/usr/bin/env python3
"""Explicit Codex client layout with the original signed-package transaction."""
import argparse
import contextlib
import ctypes
from dataclasses import dataclass
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile

if __package__:
    from .package_layout import runtime_helper_path
else:
    from package_layout import runtime_helper_path

TEAM = '2DC432GLL2'


@dataclass
class Layout:
    selection_root: Path
    releases_root: Path
    state_root: Path
    package_locks: tuple
    aliases: dict
    cli: Path
    minimum_free_bytes: int

    def __post_init__(self):
        if type(self.minimum_free_bytes) is not int or self.minimum_free_bytes <= 0:
            raise ValueError('minimum_free_bytes must be a positive integer, not bool')

    def as_dict(self):
        return {'schema': 'codex-client-layout-v1',
                'selection_root': str(self.selection_root),
                'releases_root': str(self.releases_root),
                'state_root': str(self.state_root),
                'package_locks': [str(path) for path in self.package_locks],
                'aliases': {str(path): str(target) for path, target in self.aliases.items()},
                'cli': str(self.cli), 'minimum_free_bytes': self.minimum_free_bytes}


def absolute_path(value):
    if not isinstance(value, str) or not value or not Path(value).is_absolute() or '..' in Path(value).parts:
        raise ValueError('An explicit absolute path without parent traversal is required')
    return Path(value)


def parse_layout(value):
    fields = {'schema', 'selection_root', 'releases_root', 'state_root',
              'package_locks', 'aliases', 'cli', 'minimum_free_bytes'}
    if type(value) is not dict or set(value) != fields or value['schema'] != 'codex-client-layout-v1':
        raise ValueError('Exact codex-client-layout-v1 configuration required')
    if type(value['minimum_free_bytes']) is not int or value['minimum_free_bytes'] <= 0:
        raise ValueError('minimum_free_bytes must be a positive integer, not bool')
    root = absolute_path(value['selection_root'])
    if type(value['package_locks']) is not list or type(value['aliases']) is not dict:
        raise ValueError('Explicit package lock list and alias mapping required')
    locks = tuple(absolute_path(item) for item in value['package_locks'])
    if len(set(locks)) != len(locks) or root / 'client.lock' in locks:
        raise ValueError('Duplicate package/selection locks are not allowed')
    aliases = {absolute_path(alias): absolute_path(target) for alias, target in value['aliases'].items()}
    if root / 'current' in aliases or root / 'cli' in aliases:
        raise ValueError('Aliases cannot override the owned current/cli selectors')
    return Layout(root, absolute_path(value['releases_root']), absolute_path(value['state_root']),
                  locks, aliases, absolute_path(value['cli']), value['minimum_free_bytes'])


def load_layout(path):
    return parse_layout(json.loads(Path(path).read_bytes()))


def verified_alias_target(layout, alias, target, verified):
    if target == layout.selection_root / 'current':
        return verified.get('package')
    if target == layout.selection_root / 'cli':
        return verified.get('binary')
    if alias.name == 'codex-code-mode-host':
        return verified.get('helper', {}).get('path')
    return str(target)

def digest(p):
    with Path(p).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def run(argv, timeout=30):
    return subprocess.run(list(map(str, argv)), capture_output=True, text=True,
                          timeout=timeout, check=True)

def processes(include_helpers=False):
    lib = ctypes.CDLL('/usr/lib/libproc.dylib', use_errno=True)
    lib.proc_pidpath.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32]
    rows = []
    for line in run(['/bin/ps', '-axo', 'pid=,comm=']).stdout.splitlines():
        fields = line.strip().split(None, 1)
        if len(fields) != 2 or 'codex' not in fields[1].lower():
            continue
        pid = int(fields[0])
        buf = ctypes.create_string_buffer(4096)
        if lib.proc_pidpath(pid, buf, len(buf)) > 0:
            path = Path(buf.value.decode())
            if include_helpers or path.name == 'codex' or path.name.startswith('codex-aarch64-'):
                rows.append({'pid': pid, 'path': str(path)})
    return rows

def verify_package(package):
    package = Path(package).resolve(strict=True)
    meta = json.loads((package / 'codex-package.json').read_text())
    if meta.get('target') != 'aarch64-apple-darwin' or meta.get('entrypoint') != 'bin/codex':
        raise ValueError('Unsupported official package layout')
    entry = (package / 'bin/codex').resolve(strict=True)
    if not entry.is_relative_to(package):
        raise ValueError('CLI target escapes package')
    helper = (package / 'bin/codex-code-mode-host').resolve(strict=True)
    if not helper.is_relative_to(package) or not helper.is_file():
        raise ValueError('Code-mode helper missing or escapes package')
    for field in ('resourcesDir', 'pathDir'):
        directory = (package / meta[field]).resolve(strict=True)
        if not directory.is_relative_to(package) or not directory.is_dir():
            raise ValueError(f'Invalid package directory: {field}')
    # Current releases can use Apple's signed app-bundle entrypoint. Never
    # execute an unverified wrapper to discover where it points.
    app = package / 'CodexCLI.app'
    if app.is_dir():
        run(['/usr/bin/codesign', '--verify', '--strict', app], 60)
        bundled = (app / 'Contents/MacOS/codex').resolve(strict=True)
        if not bundled.is_relative_to(package):
            raise ValueError('App binary escapes package')
        entry = bundled
    runtime_helper_path(package, entry)
    run(['/usr/bin/codesign', '--verify', '--strict', entry], 60)
    info = run(['/usr/bin/codesign', '-dv', '--verbose=4', entry]).stderr
    if f'TeamIdentifier={TEAM}' not in info.splitlines():
        raise ValueError('CLI does not carry the required OpenAI signature')
    run(['/usr/bin/codesign', '--verify', '--strict', helper], 60)
    helper_info = run(['/usr/bin/codesign', '-dv', '--verbose=4', helper]).stderr
    if f'TeamIdentifier={TEAM}' not in helper_info.splitlines():
        raise ValueError('Code-mode helper does not carry the required OpenAI signature')
    version = run([entry, '--version']).stdout.strip()
    if version != 'codex-cli ' + meta['version']:
        raise ValueError('Package and executable versions disagree')
    return {'package': str(package), 'binary': str(entry), 'version': meta['version'],
            'sha256': digest(entry), 'team_identifier': TEAM,
            'helper': {'path': str(helper), 'sha256': digest(helper)}}

def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f'.{os.getpid()}.tmp')
    with tmp.open('x') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    tmp.chmod(0o600)
    os.replace(tmp, path)

def replace_link(path, target):
    if path.exists() and not path.is_symlink():
        raise ValueError(f'Refusing to replace non-symlink: {path}')
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f'.{os.getpid()}.tmp')
    tmp.symlink_to(target)
    os.replace(tmp, path)

@contextlib.contextmanager
def locks(layout):
    with contextlib.ExitStack() as stack:
        for path in [layout.selection_root / 'client.lock', *layout.package_locks]:
            path.parent.mkdir(parents=True, exist_ok=True)
            stream = stack.enter_context(path.open('a'))
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield

def switch(layout, package, *, adopt=False, _locked=False):
    verified = verify_package(package)
    with (contextlib.nullcontext() if _locked else locks(layout)):
        # Updates require all real CLI processes to have exited; adoption retains
        # the current executable bytes and therefore may normalize aliases live.
        if not adopt and processes():
            raise ValueError('Codex is still running; exit clients normally before updating')
        targets = {layout.selection_root / 'current': Path(verified['package']), layout.selection_root / 'cli': Path(verified['binary']), **layout.aliases}
        before = {}
        for p in targets:
            if p.exists() and not p.is_symlink():
                raise ValueError(f'Not an alias: {p}')
            before[str(p)] = os.readlink(p) if p.is_symlink() else None
        if adopt:
            current_cli = layout.cli.resolve(strict=True)
            if not current_cli.samefile(verified['binary']):
                raise ValueError('Adoption must retain the already selected CLI')
        receipt = {'at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                   'action': 'adopt' if adopt else 'update', 'before': before,
                   'selected': verified, 'status': 'INTENT'}
        rp = layout.state_root / ('client-switch-' + str(os.getpid()) + '.json')
        atomic_json(rp, receipt)
        changed = []
        try:
            for path, target in targets.items():
                expected = before[str(path)]
                if (os.readlink(path) if path.is_symlink() else None) != expected:
                    raise ValueError(f'Concurrent alias change: {path}')
                replace_link(path, target)
                changed.append(path)
            for path, configured in layout.aliases.items():
                target = path.resolve(strict=True)
                expected = verified_alias_target(layout, path, configured, verified)
                if expected is None or not target.samefile(expected):
                    raise ValueError(f'Client package alias mismatch: {path}')
            atomic_json(layout.selection_root / 'authorized-client.json', verified)
            receipt['status'] = 'SELECTED_AND_READBACK'
        except Exception:
            # Roll back only aliases still pointing to our just-written target.
            for path in reversed(changed):
                if path.is_symlink() and os.readlink(path) == str(targets[path]):
                    old = before[str(path)]
                    replace_link(path, old) if old is not None else path.unlink()
            receipt['status'] = 'FAILED_OWN_ALIASES_ROLLED_BACK'
            atomic_json(rp, receipt)
            raise
        atomic_json(rp, receipt)
        return receipt

def unpack(archive, destination):
    with tarfile.open(archive, 'r:gz') as tf:
        # Python's data filter rejects absolute/traversing paths, links outside
        # destination and special devices; never use fully_trusted here.
        tf.extractall(destination, filter='data')
    packages = [p.parent for p in destination.rglob('codex-package.json')]
    if len(packages) != 1:
        raise ValueError('Expected exactly one complete Codex package')
    return packages[0]

def update(layout, version):
    if not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise ValueError('Use an explicit stable version X.Y.Z')
    # Serialize the whole installation, including destination creation and old
    # package retirement. Releasing this lock after selection allowed concurrent
    # updaters to retire one another's selected package.
    with locks(layout):
        return update_locked(layout, version)

def update_locked(layout, version):
    if processes():
        raise ValueError('Codex is running; update from a separate shell after normal exits')
    if shutil.disk_usage(layout.releases_root).free < layout.minimum_free_bytes:
        raise ValueError(f'Need at least {layout.minimum_free_bytes} actual free bytes')
    if (layout.releases_root / version).exists():
        raise ValueError('Target release already exists; inspect it instead of overwriting')
    old = json.loads((layout.selection_root / 'authorized-client.json').read_text())
    release = json.loads(run(['gh', 'api', f'repos/openai/codex/releases/tags/rust-v{version}']).stdout)
    asset_name = 'codex-package-aarch64-apple-darwin.tar.gz'
    assets = [a for a in release['assets'] if a['name'] == asset_name]
    if len(assets) != 1 or not assets[0].get('digest', '').startswith('sha256:'):
        raise ValueError('Official release lacks a unique package with SHA256 digest')
    with tempfile.TemporaryDirectory(prefix='.codex-update-', dir=layout.releases_root) as temp:
        stage = Path(temp)
        run(['gh', 'release', 'download', f'rust-v{version}', '--repo', 'openai/codex',
             '--pattern', asset_name, '--dir', stage], 600)
        archive = stage / asset_name
        if digest(archive) != assets[0]['digest'].split(':', 1)[1]:
            raise ValueError('Official archive SHA256 mismatch')
        package = unpack(archive, stage / 'unpacked')
        candidate = verify_package(package)
        if candidate['version'] != version:
            raise ValueError('Downloaded version mismatch')
        destination = layout.releases_root / version
        if processes():
            raise ValueError('A Codex process started during preparation; nothing switched')
        shutil.move(str(package), destination)
        # switch may have committed before its final receipt write fails.
        # Preserve the prepared package on every uncertain switch outcome;
        # reconcile actual aliases/receipts before any later cleanup.
        receipt = switch(layout, destination, _locked=True)
    # Retire only the previous installed package, and only without live users.
    # Old research/runtime artifacts elsewhere are never traversed or deleted.
    previous = Path(old['package'])
    if previous.parent != layout.releases_root or previous == destination:
        raise ValueError('Unexpected old package; no pruning performed')
    active = processes(include_helpers=True)
    if any(Path(p['path']).is_relative_to(previous) for p in active):
        raise ValueError('Old package acquired a live process; retained for reconciliation')
    if digest(Path(old['binary'])) != old['sha256']:
        raise ValueError('Old package changed; retained for reconciliation')
    shutil.rmtree(previous)
    return receipt

def status(layout):
    """Verify the selected package and launch aliases, without changing them."""
    issues = []
    selected = {}
    try:
        selected = json.loads((layout.selection_root / 'authorized-client.json').read_text())
        if not isinstance(selected, dict):
            raise ValueError('Authorized client record must be an object')
    except (OSError, ValueError) as error:
        selected = {}
        issues.append({'code': 'CLIENT_RECORD_UNAVAILABLE', 'error': str(error)})

    verified = None
    try:
        verified = verify_package(layout.selection_root / 'current')
        if verified != selected:
            issues.append({'code': 'SELECTED_PACKAGE_RECORD_MISMATCH'})
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        issues.append({'code': 'SELECTED_PACKAGE_VERIFICATION_FAILED', 'error': str(error)})

    expected = {layout.selection_root / 'current': selected.get('package'),
                layout.selection_root / 'cli': selected.get('binary')}
    for alias, target in layout.aliases.items():
        expected[alias] = verified_alias_target(layout, alias, target, selected)
    aliases = {}
    for alias, target in expected.items():
        try:
            actual = alias.resolve(strict=True)
            aliases[str(alias)] = str(actual)
            if not alias.is_symlink() or target is None or not actual.samefile(target):
                issues.append({'code': 'CLIENT_ALIAS_MISMATCH', 'path': str(alias),
                               'expected': target, 'actual': str(actual)})
        except (OSError, RuntimeError) as error:
            aliases[str(alias)] = None
            issues.append({'code': 'CLIENT_ALIAS_UNAVAILABLE', 'path': str(alias),
                           'error': str(error)})

    running = processes()
    unexpected = [p for p in running if p['path'] != selected.get('binary')]
    if unexpected:
        issues.append({'code': 'UNEXPECTED_PRIMARY_PROCESSES', 'processes': unexpected})
    helpers = [p for p in processes(include_helpers=True)
               if Path(p['path']).name == 'codex-code-mode-host']
    legacy_helpers = [p for p in helpers if p['path'] != selected.get('helper', {}).get('path')]
    return {'status': 'SELECTED_CLIENT_CONSISTENT' if not issues else 'NEEDS_REPAIR',
            'scope': 'selected_signed_package_cli_and_helper_aliases_and_observed_primary_processes',
            'not_verified': ['all_filesystem_installations', 'session_identity',
                             'actual_model_or_tool_calls', 'future_updates',
                             'migration_of_already_running_helpers'],
            'selected': selected, 'verified_package': verified, 'aliases': aliases,
            'processes': running, 'unexpected_primary_processes': unexpected,
            'helper_processes': helpers, 'legacy_helper_processes': legacy_helpers,
            'helper_migration': 'LEGACY_HELPERS_ACTIVE' if legacy_helpers else 'NO_LEGACY_HELPERS_OBSERVED',
            'issues': issues}

def file_reference(path):
    path = Path(path).resolve(strict=True)
    body = path.read_bytes()
    return {'path': str(path), 'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}, body


def plan_value(layout_ref, action, *, package=None, version=None):
    if action == 'adopt' and package is not None and version is None:
        arguments = {'package': str(absolute_path(str(package)))}
    elif action == 'update' and package is None and isinstance(version, str) and re.fullmatch(r'\d+\.\d+\.\d+', version):
        arguments = {'version': version}
    else:
        raise ValueError('One explicit adopt package or stable update version is required')
    return {'schema': 'codex-client-plan-v1', 'layout': layout_ref,
            'action': action, 'arguments': arguments,
            'preflight_performed': False, 'network_performed': False}


def make_plan(layout_path, action, *, package=None, version=None):
    layout_ref, body = file_reference(layout_path)
    parse_layout(json.loads(body))
    return plan_value(layout_ref, action, package=package, version=version)


def apply_plan(layout_path, plan_path, plan_sha256):
    if not isinstance(plan_sha256, str) or not re.fullmatch('[0-9a-f]{64}', plan_sha256):
        raise ValueError('Exact plan SHA256 required')
    ref, body = file_reference(plan_path)
    if ref['sha256'] != plan_sha256:
        raise ValueError('Plan bytes changed')
    plan = json.loads(body)
    if type(plan) is not dict or set(plan) != {'schema', 'layout', 'action', 'arguments', 'preflight_performed', 'network_performed'}:
        raise ValueError('Exact plan schema required')
    arguments = plan['arguments']
    if type(arguments) is not dict:
        raise ValueError('Exact plan arguments required')
    layout_ref, layout_body = file_reference(layout_path)
    layout = parse_layout(json.loads(layout_body))
    expected = plan_value(layout_ref, plan['action'], **arguments)
    if plan != expected:
        raise ValueError('Plan layout/action changed; no preflight is implied by a plan')
    if plan['action'] == 'adopt':
        return switch(layout, Path(arguments['package']), adopt=True)
    return update(layout, arguments['version'])


def write_plan(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        os.fchmod(stream.fileno(), 0o600)
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    return file_reference(path)[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--layout', type=Path, required=True)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('config')
    sub.add_parser('status')
    plan_parser = sub.add_parser('plan', help='Bind an action; no native preflight or download')
    plan_parser.add_argument('--output', type=Path, required=True)
    actions = plan_parser.add_subparsers(dest='action', required=True)
    adopt = actions.add_parser('adopt')
    adopt.add_argument('package', type=Path)
    upgrade = actions.add_parser('update')
    upgrade.add_argument('version')
    apply_parser = sub.add_parser('apply', help='Run the original checks and transaction')
    apply_parser.add_argument('--plan', type=Path, required=True)
    apply_parser.add_argument('--plan-sha256', required=True)
    args = parser.parse_args()
    if args.command == 'config':
        value = load_layout(args.layout).as_dict()
    elif args.command == 'status':
        value = status(load_layout(args.layout))
    elif args.command == 'plan':
        value = make_plan(args.layout, args.action, package=getattr(args, 'package', None),
                          version=getattr(args, 'version', None))
        value = {'plan': write_plan(args.output, value), 'preflight_performed': False,
                 'network_performed': False}
    else:
        value = apply_plan(args.layout, args.plan, args.plan_sha256)
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return 1 if args.command == 'status' and value['issues'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
