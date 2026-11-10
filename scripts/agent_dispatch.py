"""Replace this process with one explicitly configured adapter; no CLI defaults."""
import json
import os
from pathlib import Path
import sys


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate configuration key')
        result[key] = value
    return result


def load_config(path):
    config = json.loads(Path(path).read_text(encoding='utf-8'),
                        object_pairs_hook=_unique_object)
    if not isinstance(config, dict) or set(config) - {'adapters', 'herdr_agent'}:
        raise ValueError('expected adapters and optional herdr_agent mappings')
    adapters = config.get('adapters')
    markers = config.get('herdr_agent', {})
    if not isinstance(adapters, dict) or not adapters or not isinstance(markers, dict):
        raise ValueError('adapter mappings must be nonempty objects')
    for key, argv in adapters.items():
        if not key or '\0' in key or not isinstance(argv, list) or not argv:
            raise ValueError('each adapter needs a key and a nonempty argv array')
        if not all(isinstance(arg, str) and '\0' not in arg for arg in argv) or not argv[0]:
            raise ValueError('argv must contain strings and a nonempty executable')
    for key, marker in markers.items():
        if key not in adapters or not isinstance(marker, str) or not marker or '\0' in marker:
            raise ValueError('herdr_agent must map existing adapter keys to nonempty labels')
    return adapters, markers


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) < 3 or args[0] != '--config':
        print('Usage: agent_dispatch.py --config FILE ADAPTER [arguments...]', file=sys.stderr)
        return 2
    try:
        adapters, markers = load_config(args[1])
        key = args[2]
        if key not in adapters:
            raise ValueError('unknown adapter')
    except (OSError, ValueError, TypeError) as error:
        print('dispatcher: ' + str(error), file=sys.stderr)
        return 2
    # 缺少标签时保留继承环境，对应原 dispatcher 未设置标记的分支。
    environment = dict(os.environ)
    if key in markers:
        environment['HERDR_AGENT'] = markers[key]
    command = adapters[key] + args[3:]
    try:
        os.execvpe(command[0], command, environment)
    except FileNotFoundError:
        print('dispatcher: executable not found', file=sys.stderr)
        return 127
    except OSError as error:
        print('dispatcher: cannot execute: ' + str(error), file=sys.stderr)
        return 126


if __name__ == '__main__':
    raise SystemExit(main())
