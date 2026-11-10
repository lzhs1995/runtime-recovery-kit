# Source and scope

The package contains generic maintenance documentation, two unchanged local modules (a terminal-mode function and a bounded Codex writer-lock observer), two derived terminal adapters, and one unchanged helper-layout function extracted from the local client-management module. The adapters replace only their fixed function source path with the package-relative path. Public source contains no private machine path or session ID and bundles no third-party runtime source.

The audited local recovery collection also contains package checks and update logic, client launchers and Herdr/DSH adapters. Those files are not included here. Some already accept environment configuration; others still mix machine paths, private session policy, shared-resource contracts and executable mutation. A generic edition should pass those through an explicit configuration contract while preserving the original safeguards.

Codex, Herdr, DSH and the other agent CLIs are external runtime dependencies of those deferred adapters, not source or binaries bundled in this candidate. No full provenance or history audit of those upstream projects is claimed.

The local modules had no declared license header. This candidate does not assign a license; that absence is not a finding that the owner cannot publish their own work.

## Included scripts

- `scripts/terminal_modes.sh`: unchanged maintenance function; Bash/Zsh source-only silence and exact emitted bytes were tested through pipes. Actual terminal behavior depends on the terminal emulator and shell state.
- `scripts/resume_check.py`: unchanged, optional POSIX library. Its target and home are supplied privately. Invocation reads a bounded original history header and briefly attempts existing native shared locks. It returns a time-limited observation, not recovery authority. Synthetic temporary-home fixtures cover idle, busy, invalid identity/path and file-mode cases; no live lock inspection ran.
- `scripts/codex-terminal-recover`: derived Bash command. It preserves the original `--check`, non-TTY return, `--before-launch` and explicit `--shell` behavior; `--shell` additionally calls `stty sane` on the caller's TTY.
- `scripts/terminal_prompt_recovery.zsh`: derived, optional Zsh prompt hook. It preserves prompt-only execution, interactive stdin/stdout TTY and cmux marker conditions, prior exit status and hook deduplication.
- `scripts/package_layout.py`: only the original `runtime_helper_path` function and its standard-library import; [the layout contract](package-layout.md) distinguishes file identity from package verification. Three existing synthetic helper cases accompany this extraction.
- No session launcher, updater, private target list, provider setting, account secret, session record, task receipt or runtime binary is included.

## Deferred local integrations

Apart from the one helper-layout function and three extracted cases above, package inspection/update logic and the full three test modules remain outside this increment; they need an explicit layout and report contract, with original signature, process-use, locking and rollback safeguards. This partial extraction does not complete either original module or the eight deferred tools. A startup wrapper depending on those tools is likewise deferred. A model-session dispatcher and its DSH protocol adapter need their own explicit executable and protocol contract; they are not read-only diagnostics.

Private target and resume recipes remain private. For their observation step, the public mapping is `resume_check.inspect_writer(target, codex_home=...)` with the caller's original private fields, as documented in [writer observation](writer-observation.md). That library does not reproduce an omitted private launcher, authorize a resume or substitute synthetic IDs for real bindings. Fixed Python/Node launch wrappers have no independently complete recovery capability when their private downstream adapter is absent.

## Extending the package

Start with explicit source/configuration paths and an output mode that emits only public issue codes. Keep inspection, cache/report writes, terminal mutation, session launch and package replacement visibly separate. Make unsupported platforms explicit. Preserve original task bindings and unsuccessful or unknown attempts.

Use synthetic files and temporary directories for new validation. A source-only test must not import a helper whose startup code launches a real client or reads a private target list. Reading these documents is available to many agents; native adapter compatibility still needs separate actual evidence.
