# Source and scope

The candidate consists of new, generic maintenance documentation and two unchanged local modules: a terminal-mode function and a bounded Codex writer-lock observer. Neither source contains a private machine path or session ID. They use shell built-ins or Python standard-library modules and import no third-party source.

The audited local recovery collection also contains package checks and update logic, client launchers and Herdr/DSH adapters. Those files are not included here. Some already accept environment configuration; others still mix machine paths, private session policy, shared-resource contracts and executable mutation. A generic edition should pass those through an explicit configuration contract while preserving the original safeguards.

Codex, Herdr, DSH and the other agent CLIs are external runtime dependencies of those deferred adapters, not source or binaries bundled in this candidate. No full provenance or history audit of those upstream projects is claimed.

The local modules had no declared license header. This candidate does not assign a license; that absence is not a finding that the owner cannot publish their own work.

## Included scripts

- `scripts/terminal_modes.sh`: unchanged maintenance function; Bash/Zsh source-only silence and exact emitted bytes were tested through pipes. Actual terminal behavior depends on the terminal emulator and shell state.
- `scripts/resume_check.py`: unchanged, optional POSIX library. Its target and home are supplied privately. Invocation reads a bounded original history header and briefly attempts existing native shared locks. It returns a time-limited observation, not recovery authority. Synthetic temporary-home fixtures cover idle, busy, invalid identity/path and file-mode cases; no live lock inspection ran.
- No launcher, updater, private target list, provider setting, account secret, session record, task receipt or runtime binary is included.

## Extending the package

Start with explicit source/configuration paths and an output mode that emits only public issue codes. Keep inspection, cache/report writes, terminal mutation, session launch and package replacement visibly separate. Make unsupported platforms explicit. Preserve original task bindings and unsuccessful or unknown attempts.

Use synthetic files and temporary directories for new validation. A source-only test must not import a helper whose startup code launches a real client or reads a private target list. Reading these documents is available to many agents; native adapter compatibility still needs separate actual evidence.
