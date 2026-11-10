#!/usr/bin/env python3
"""检查本机工具配置与可选进程路径；不访问应用、不创建 agent、不改变授权。"""
from pathlib import Path
import argparse
import ctypes
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tomllib
if __package__:
    from .package_layout import runtime_helper_path
else:
    from package_layout import runtime_helper_path


def check_config(config):
    issues = []
    servers = []
    for name, server in config.get('mcp_servers', {}).items():
        enabled = server.get('enabled', True)
        command, url = server.get('command'), server.get('url')
        # 底层运行时也会解析 disabled 条目的 transport。
        if not command and not url:
            issues.append({'code': 'MCP_TRANSPORT_MISSING', 'server': name})
        resolved = None
        if command:
            resolved = str(Path(command).resolve()) if '/' in command else shutil.which(command)
            if enabled and (not resolved or not os.access(resolved, os.X_OK)):
                issues.append({'code': 'MCP_EXECUTABLE_MISSING', 'server': name, 'command': command})
        servers.append({'name': name, 'enabled': enabled, 'transport': 'stdio' if command else 'http' if url else None,
                        'command': command, 'resolved_command': resolved,
                        'approval_mode': server.get('default_tools_approval_mode', 'default')})
    return issues, servers


def observe_active_cli(pid, configured_cli):
    """读取明确 PID 的内核程序路径；不把环境变量或配置当成现役客户端。"""
    observation = {'pid': pid, 'status': 'UNAVAILABLE', 'session_authenticated': False,
                   'scope': 'kernel_executable_path_and_file_identity_only'}
    if sys.platform != 'darwin' or not 0 < pid <= 2147483647:
        observation['reason'] = 'DARWIN_VALID_PID_REQUIRED'
        return observation
    try:
        proc = ctypes.CDLL('/usr/lib/libproc.dylib', use_errno=True)
        proc.proc_pidpath.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32]
        proc.proc_pidpath.restype = ctypes.c_int

        def snapshot():
            buffer = ctypes.create_string_buffer(4096)
            if proc.proc_pidpath(pid, buffer, len(buffer)) <= 0:
                raise OSError(ctypes.get_errno(), 'proc_pidpath failed')
            path = Path(buffer.value.decode('utf-8'))
            info = path.stat()
            meta = subprocess.run(['/bin/ps', '-p', str(pid), '-o', 'lstart=', '-o', 'uid='],
                                  capture_output=True, text=True, timeout=8)
            if meta.returncode or not meta.stdout.strip():
                raise OSError('Process metadata unavailable')
            return {'kernel_executable': str(path), 'resolved_executable': str(path.resolve()),
                    'file_identity': [info.st_dev, info.st_ino, info.st_size,
                                      info.st_mtime_ns, info.st_ctime_ns],
                    'start_and_uid': meta.stdout.strip()}

        before = snapshot()
        official = configured_cli.stat()
        official_identity = [official.st_dev, official.st_ino, official.st_size,
                             official.st_mtime_ns, official.st_ctime_ns]
        after = snapshot()
        observation.update(after)
        if before != after:
            observation['reason'] = 'PROCESS_CHANGED_DURING_OBSERVATION'
            return observation
        official_after = configured_cli.stat()
        if official_identity != [official_after.st_dev, official_after.st_ino,
                                  official_after.st_size, official_after.st_mtime_ns,
                                  official_after.st_ctime_ns]:
            observation['reason'] = 'CONFIGURED_CLI_CHANGED_DURING_OBSERVATION'
            return observation
        matches = after['file_identity'] == official_identity
        observation['matches_configured_official_cli'] = matches
        observation['status'] = 'MATCHES_CONFIGURED_OFFICIAL_CLI' if matches else 'DIFFERENT_ACTIVE_CLI'
        observation['not_verified'] = ['loaded_process_signature', 'session_identity',
                                       'native_tool_registration', 'model_response', 'application_access']
    except (OSError, UnicodeError, subprocess.TimeoutExpired) as error:
        observation['reason'] = type(error).__name__
        observation['error'] = str(error)
    return observation


def run(config_path, *, cli, package, app_candidates, cache_path=None, startup=False, active_pids=None):
    config_path = Path(config_path)
    cli = Path(cli)
    selected_package = Path(package)
    candidates = [Path(candidate) for candidate in app_candidates]
    cache_path = None if cache_path is None else Path(cache_path)
    result = {'schema': 'codex-toolchain-doctor-v1', 'at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'scope': ['config_parse', 'mcp_transport_and_executable', 'official_cua_paths', 'codex_signature'],
              'not_verified': ['current_native_tool_registry', 'macos_application_access', 'document_state', 'live_R', 'remote_services'],
              'application_calls': 0, 'issues': [], 'observations': {}}
    try:
        raw = config_path.read_bytes()
        config = tomllib.loads(raw.decode('utf-8'))
        result['config_sha256'] = hashlib.sha256(raw).hexdigest()
        issues, servers = check_config(config)
        result['issues'].extend(issues)
        result['observations']['mcp_servers'] = servers
        result['observations']['approval_policy'] = config.get('approval_policy', 'default')
        result['observations']['computer_use_approval'] = config.get('apps', {}).get('computer-use', {}).get('default_tools_approval_mode', 'default')
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as error:
        result['issues'].append({'code': 'CONFIG_PARSE_ERROR', 'error': str(error)})
    runtime = None
    for app in candidates:
        base = app / 'Contents/Resources/cua_node'
        if all((base / relative).is_file() for relative in ['bin/node', 'bin/node_repl', 'lib/node_modules/@oai/cua-repl/bin/cua-repl.mjs']):
            runtime = str(base)
            break
    result['observations']['cua_runtime'] = runtime
    if runtime is None:
        result['issues'].append({'code': 'OFFICIAL_CUA_RUNTIME_MISSING'})
    result['observations']['official_cli'] = str(cli.resolve())
    if selected_package.exists():
        helper = selected_package / 'bin/codex-code-mode-host'
        result['observations']['selected_package_helper'] = {
            'path': str(helper), 'exists': helper.is_file(),
            'scope': 'file_availability_only_not_actual_tool_execution',
        }
        if not helper.is_file():
            result['issues'].append({'code': 'SELECTED_CODEX_HELPER_MISSING', 'path': str(helper)})
        else:
            try:
                actual_helper = runtime_helper_path(selected_package, cli)
                result['observations']['selected_package_helper']['runtime_path'] = str(actual_helper)
            except (OSError, ValueError, RuntimeError) as error:
                result['issues'].append({'code': 'RUNTIME_CODEX_HELPER_UNAVAILABLE', 'error': str(error)})
    else:
        result['issues'].append({'code': 'SELECTED_CODEX_PACKAGE_MISSING', 'path': str(selected_package)})
    try:
        info = cli.stat()
        identity = [str(cli.resolve()), info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns]
        cache = {}
        if cache_path is not None:
            try:
                cache = json.loads(cache_path.read_text())
            except (OSError, ValueError):
                cache = {}
        metadata = subprocess.run(['/usr/bin/codesign', '-dv', '--verbose=4', str(cli)], capture_output=True, text=True, timeout=5)
        team = next((line.split('=', 1)[1] for line in metadata.stderr.splitlines() if line.startswith('TeamIdentifier=')), None)
        if cache.get('identity') == identity and cache.get('verified') is True and team == '2DC432GLL2':
            signature = {'verified': True, 'team_identifier': team, 'scope': 'cached_full_verification_same_file_identity', 'verified_at': cache.get('verified_at')}
        elif startup:
            # 启动时不对大型程序重复全文件扫描；正常 CUA 仍执行自身签名校验。
            signature = {'verified': None, 'team_identifier': team, 'scope': 'metadata_only_full_verification_pending'}
        else:
            verified = subprocess.run(['/usr/bin/codesign', '--verify', '--strict', str(cli)], capture_output=True, text=True, timeout=45)
            after = cli.stat()
            unchanged = identity == [str(cli.resolve()), after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns]
            signature = {'verified': verified.returncode == 0 and unchanged, 'team_identifier': team, 'scope': 'full_codesign_verification'}
            if cache_path is not None and signature['verified'] and team == '2DC432GLL2':
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                value = {'identity': identity, 'verified': True, 'verified_at': result['at']}
                temporary = cache_path.with_name(cache_path.name + f'.{os.getpid()}.tmp')
                with temporary.open('x') as stream:
                    json.dump(value, stream)
                temporary.chmod(0o600)
                os.replace(temporary, cache_path)
        result['observations']['official_cli_signature'] = signature
        if signature['verified'] is False or team != '2DC432GLL2':
            result['issues'].append({'code': 'OFFICIAL_CODEX_SIGNATURE_INVALID'})
    except (OSError, subprocess.TimeoutExpired) as error:
        result['issues'].append({'code': 'SIGNATURE_CHECK_UNAVAILABLE', 'error': str(error)})
    result['observations']['inherited_codex_pid'] = os.environ.get('CMUX_CODEX_PID')
    result['observations']['inherited_thread_id'] = os.environ.get('CODEX_THREAD_ID')
    result['observations']['identity_authenticated'] = False
    if active_pids:
        result['scope'].append('explicit_active_pid_executable_observation')
        active = [observe_active_cli(pid, cli) for pid in dict.fromkeys(active_pids)]
        result['observations']['active_cli_processes'] = active
        for item in active:
            if item['status'] == 'DIFFERENT_ACTIVE_CLI':
                result['issues'].append({'code': 'ACTIVE_CLI_DIFFERS_FROM_CONFIGURED_OFFICIAL',
                                         'pid': item['pid'], 'path': item['kernel_executable']})
            elif item['status'] == 'UNAVAILABLE':
                result['issues'].append({'code': 'ACTIVE_CLI_OBSERVATION_UNAVAILABLE', 'pid': item['pid']})
    result['status'] = 'PASS_CONFIG_ONLY' if not result['issues'] else 'NEEDS_REPAIR'
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--cli', type=Path, required=True)
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--app-candidates', type=Path, nargs='*', required=True,
                        help='显式应用候选；允许空列表，不扫描默认应用目录')
    parser.add_argument('--cache', type=Path, help='可选签名缓存；未指定时不读写缓存')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--startup', action='store_true', help='简短提示；不阻止客户端继续启动')
    parser.add_argument('--active-pid', type=int, action='append',
                        help='可重复：核明确现役PID的内核程序路径；不自动重连或停止进程')
    args = parser.parse_args()
    result = run(args.config, cli=args.cli, package=args.package,
                 app_candidates=args.app_candidates, cache_path=args.cache,
                 startup=args.startup, active_pids=args.active_pid)
    raw = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.output.with_name(args.output.name + f'.{os.getpid()}.tmp')
        with temporary.open('x') as stream:
            stream.write(raw)
        temporary.chmod(0o600)
        os.replace(temporary, args.output)
    if args.startup:
        if result['issues']:
            print('Codex 工具启动检查：' + ', '.join(item['code'] for item in result['issues']) + '。读取 codex-toolchain-recovery 恢复；当前检查没有申请应用权限。')
    else:
        print(raw, end='')
    return 0 if args.startup or not result['issues'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
