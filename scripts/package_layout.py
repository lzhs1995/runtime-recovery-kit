"""Check the selected helper path in a supplied Codex package layout.

This module does not verify signatures, launch a client or select an installation.
The caller supplies the package and entry paths; no private defaults are read.
"""
from pathlib import Path


def runtime_helper_path(package, entry):
    """Resolve the helper where the official client locates it at runtime."""
    package = Path(package).resolve(strict=True)
    entry = Path(entry).resolve(strict=True)
    recognized = {package / 'bin', package / 'codex-resources',
                  package / 'CodexCLI.app/Contents/MacOS'}
    directory = package / 'bin' if entry.parent in recognized else entry.parent
    resource = package / 'codex-resources/codex-code-mode-host'
    candidate = (resource if entry.parent in recognized and resource.is_file()
                 else directory / 'codex-code-mode-host')
    actual = candidate.resolve(strict=True)
    bundled = (package / 'bin/codex-code-mode-host').resolve(strict=True)
    if not actual.is_relative_to(package) or not actual.is_file() or not actual.samefile(bundled):
        raise ValueError('Runtime code-mode helper differs from the verified package helper')
    return actual
