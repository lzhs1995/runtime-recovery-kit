# Source and scope

The package contains maintenance documentation, two unchanged local modules (a terminal-mode function and a bounded Codex writer-lock observer), two derived terminal adapters, an unchanged helper-layout function, an explicit-layout doctor, a configured adapter dispatcher, a Codex client manager, a startup launcher and a DSH terminal adapter. The terminal adapters change only the function source path. Public source contains no private machine path or session ID and bundles no third-party runtime source.

The client, launcher and DSH integrations take installation paths and runtime choices through explicit private configuration. Machine-specific target lists, session recipes and fixed local wrappers remain private. Public configuration examples do not transfer shared-resource ownership, select a session or authorize an executable change.

Codex, Herdr, DSH and the other agent CLIs are external runtime dependencies of the included adapters, not source or binaries bundled in this candidate. No full provenance or history audit of those upstream projects is claimed.

The local modules had no declared license header. This candidate does not assign a license; that absence is not a finding that the owner cannot publish their own work.

## Included scripts

- `scripts/terminal_modes.sh`: unchanged maintenance function; Bash/Zsh source-only silence and exact emitted bytes were tested through pipes. Actual terminal behavior depends on the terminal emulator and shell state.
- `scripts/resume_check.py`: unchanged, optional POSIX library. Its target and home are supplied privately. Invocation reads a bounded original history header and briefly attempts existing native shared locks. It returns a time-limited observation, not recovery authority. Synthetic temporary-home fixtures cover idle, busy, invalid identity/path and file-mode cases; no live lock inspection ran.
- `scripts/codex-terminal-recover`: derived Bash command. It preserves the original `--check`, non-TTY return, `--before-launch` and explicit `--shell` behavior; `--shell` additionally calls `stty sane` on the caller's TTY.
- `scripts/terminal_prompt_recovery.zsh`: derived, optional Zsh prompt hook. It preserves prompt-only execution, interactive stdin/stdout TTY and cmux marker conditions, prior exit status and hook deduplication.
- `scripts/package_layout.py`: only the original `runtime_helper_path` function and its standard-library import; [the layout contract](package-layout.md) distinguishes file identity from package verification. Three existing synthetic helper cases accompany this extraction.
- `scripts/toolchain_doctor.py`: the local doctor with explicit configuration/CLI/package/application candidates and optional cache/report paths. It retains the original macOS signing, file-identity, helper and explicit-PID checks; [doctor layout](doctor-layout.md) lists its write and verification boundaries.
- `scripts/codex_client.py`: the original signed-package status/adopt/update engine with explicit installation layout and `config`, `status`, `plan`, `apply` CLI boundaries. The helper function is imported from the included `package_layout.py`; no second helper implementation is maintained. [Client maintenance](codex-client.md) describes native checks, download and filesystem effects.
- The optional configured dispatcher launches only the program selected by the caller; no autonomous session recovery, private target list, provider setting, account secret, session record, task receipt or runtime binary is included.

## Private local integrations

The full client and its three original test modules are now included through explicit layout and temporary fixtures. Three helper-only cases remain in the existing `test_package_layout.py`, so the client tests retain the other 22 original cases plus seven layout/plan cases. The startup wrapper and DSH protocol adapter are also included through explicit layouts. Their documented native dependencies and operational boundaries remain; synthetic fixtures do not establish a live installation or model call.

Private target and resume recipes remain private. For their observation step, the public mapping is `resume_check.inspect_writer(target, codex_home=...)` with the caller's original private fields, as documented in [writer observation](writer-observation.md). That library does not reproduce an omitted private launcher, authorize a resume or substitute synthetic IDs for real bindings. Fixed Python/Node launch wrappers have no independently complete recovery capability when their private downstream adapter is absent.

## Extending the package

Start with explicit source/configuration paths and an output mode that emits only public issue codes. Keep inspection, cache/report writes, terminal mutation, session launch and package replacement visibly separate. Make unsupported platforms explicit. Preserve original task bindings and unsuccessful or unknown attempts.

Use synthetic files and temporary directories for new validation. A source-only test must not import a helper whose startup code launches a real client or reads a private target list. Reading these documents is available to many agents; native adapter compatibility still needs separate actual evidence.

## Configured dispatcher increment

`scripts/agent_dispatch.py` supplies the selection, argument forwarding and process replacement behavior of the small original `herdr-agent` wrapper through an explicit private argv map. Provider commands, aliases and fixed profile arguments are configuration choices. Optional exact labels preserve the original distinction between overriding `HERDR_AGENT` and inheriting it. The dispatcher selects an explicitly configured program; the separately included DSH adapter supplies its own protocol behavior. See [the dispatch contract](agent-dispatch.md).

## Explicit-layout launcher increment

`scripts/toolchain_launch.py` derives the behavior of the original 14-line startup wrapper using five configured entry/report paths and the explicit inputs required by the included doctor. The launcher is included alongside the client manager and DSH adapter, with a separate configuration and execution boundary. The original installation paths are not distributed. The [launcher contract](toolchain-launch.md) documents report writes, terminal effects, doctor-only status, nonblocking startup failure and final argv/PID preservation. No automatic session recovery or new runtime compatibility is claimed.

## Explicit-layout DSH increment

`scripts/herdr-dsh.mjs` derives the original 289-line DSH terminal adapter by moving binary/profile/provider/model/reporter/resume inputs to required private layout, with optional child-only DSH_HOME. This adapter is included alongside the client manager and startup launcher; each retains its own operational scope. RpcPeer, AgentStateBridge and the lifecycle from peer construction onward remain byte-identical. The reporter changes only its resume argv parameterization. No SDK source/binary, private profile or model defaults are distributed. [The DSH contract](dsh-adapter.md) records the separate static package/wire versions, name-only handshake, string-length bound and weak reporter completion.
