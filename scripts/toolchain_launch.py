#!/usr/bin/env python3
"""按显式私有布局运行启动检查，最终 exec 调用者指定的 CLI。"""
import errno
import json
import os
from pathlib import Path
import signal
import subprocess
import sys


REQUIRED = {'python', 'doctor', 'report', 'terminal_recover', 'cli',
            'doctor_config', 'package', 'app_candidates'}
USAGE = 'Usage: toolchain_launch.py --layout PRIVATE_JSON [original CLI arguments...]'


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate layout key')
        result[key] = value
    return result


def explicit_path(value):
    return isinstance(value, str) and '\0' not in value and Path(value).is_absolute()


def load_layout(path):
    value = json.loads(Path(path).read_text(encoding='utf-8'),
                       object_pairs_hook=unique_object)
    if not isinstance(value, dict) or not REQUIRED <= value.keys():
        raise ValueError('required layout fields are missing')
    if value.keys() - REQUIRED - {'cache'}:
        raise ValueError('unknown layout field')
    for key in (REQUIRED - {'app_candidates'}) | ({'cache'} & value.keys()):
        if not explicit_path(value[key]):
            raise ValueError(key + ' must be an explicit absolute path')
    apps = value['app_candidates']
    if not isinstance(apps, list) or not all(explicit_path(app) for app in apps):
        raise ValueError('app_candidates must be an explicit array of absolute paths')
    # 只校验配置形状；缺失 doctor 仍须保留原启动失败后继续的语义。
    return value


def doctor_argv(layout, startup=False):
    command = [layout['python'], '-BE', layout['doctor'],
               '--config', layout['doctor_config'], '--cli', layout['cli'],
               '--package', layout['package'], '--app-candidates',
               *layout['app_candidates'], '--output', layout['report']]
    if 'cache' in layout:
        command.extend(['--cache', layout['cache']])
    if startup:
        command.append('--startup')
    return command


def replace_process(command):
    # 与 subprocess 的默认 restore_signals 一致，撤销 Python 自设的忽略信号。
    for name in ('SIGPIPE', 'SIGXFZ', 'SIGXFSZ'):
        if hasattr(signal, name):
            signal.signal(getattr(signal, name), signal.SIG_DFL)
    try:
        os.execv(command[0], command)
    except OSError as error:
        print('toolchain-launch: exec failed: ' + str(error), file=sys.stderr, flush=True)
        return 127 if error.errno == errno.ENOENT else 126


def run_startup(command, *, to_stderr=False):
    try:
        if to_stderr:
            subprocess.run(command, check=False, stdout=sys.stderr, stderr=sys.stderr)
        else:
            subprocess.run(command, check=False)
    except OSError as error:
        print('toolchain-launch: startup step unavailable: ' + str(error),
              file=sys.stderr, flush=True)


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) < 2 or args[0] != '--layout':
        print(USAGE, file=sys.stderr)
        return 2
    try:
        layout = load_layout(args[1])
    except (OSError, ValueError) as error:
        print('toolchain-launch: invalid layout: ' + str(error), file=sys.stderr)
        return 2
    original_args = args[2:]
    if original_args[:1] == ['--doctor-only']:
        # 原分支忽略其余 CLI 参数，由 doctor 本身写报告并返回状态。
        return replace_process(doctor_argv(layout))
    if os.isatty(0) and os.isatty(1):
        run_startup([layout['terminal_recover'], '--before-launch'])
    run_startup(doctor_argv(layout, startup=True), to_stderr=True)
    return replace_process([layout['cli'], *original_args])


if __name__ == '__main__':
    raise SystemExit(main())
