<p align="center"><img src="assets/logo.svg" width="160" height="160" alt="Runtime Recovery Kit logo"></p>

# Runtime Recovery Kit

[繁體中文](README.zh-TW.md) · [Agent entry](AGENTS.md) · [Skill](SKILL.md) · [CI](https://github.com/lzhs1995/runtime-recovery-kit/actions/workflows/checks.yml)

Practical recovery notes for agent startup, tool discovery, terminal input modes and interrupted tasks. Diagnose the failed layer, retain the original task and verify the actual operation after a repair.

This kit contains portable Markdown, a Bash/Zsh terminal function, a manual terminal command, an optional Zsh prompt hook and a Codex writer-lock observation module. It does not bundle Codex, Herdr, a model provider, client configuration or session records. Full package updating, automatic session recovery and the DSH bridge are outside this edition.

## Start

Get the complete repository from [lzhs1995/runtime-recovery-kit](https://github.com/lzhs1995/runtime-recovery-kit). Ask your agent to read `AGENTS.md` and `SKILL.md`; they link the same workflow for Codex, Claude Code, Gemini CLI and other Markdown-capable agents. Automatic discovery differs by client. There is no installer.

The documents are platform independent. The terminal function requires Bash or Zsh and a compatible terminal emulator; the command uses Bash and the optional prompt hook uses Zsh. The observer requires POSIX Python and a Codex version with the matching native lock contract; see [writer observation](references/writer-observation.md). Native Windows is outside these scripts' scope. macOS signing and native applications require separate tools.

## Terminal input-mode recovery

At an interactive shell prompt after the affected program has returned terminal control, run from this directory:

```sh
. ./scripts/terminal_modes.sh
if [ -t 0 ] && [ -t 1 ]; then
    codex_toolchain_reset_terminal_modes
fi
```

Sourcing the file only defines the function. Calling it writes escape sequences to reset mouse, focus, bracketed-paste and keyboard input modes and show the cursor. It does not erase the screen, history or input buffer. Do not run it repeatedly inside a live TUI or inject it into another agent's input. It does not reset all terminal attributes or repair a crashed application.

For the manual command and an optional Zsh prompt integration, read [terminal integration](references/terminal-integration.md). Both adapters load the included function from their own directory; no machine-specific installation path is required. The Zsh hook retains its original interactive TTY and `CMUX_SURFACE_ID` conditions. Its presence marker is not identity authentication.

The [package helper layout library](references/package-layout.md) checks that the helper selected from explicit package and entry paths is the same file as the package helper. This is one extracted client-management function; it does not verify signatures or provide the full client updater.

The [doctor with explicit layout](references/doctor-layout.md) checks supplied configuration, package-helper paths and macOS signatures. It has no implicit installation paths; cache and report files are written only when their paths are selected. `--startup` retains the original nonblocking, potentially pending signature result.

## Diagnose and verify

Read [recovery layers](references/recovery-layers.md) for the shortest check at each layer, and [source scope](references/source-scope.md) for included and deferred modules. Preserve existing task authorization and the original controller, session, attempt and result. Unknown results need reconciliation before retrying.

A configuration file parsing, a tool being installed, a client loading it and a successful task are separate outcomes. Report the observed outcome and the still-unverified boundary. Do not call application access or a completed model stream scientific acceptance.

## Verification

The original function and observer remain byte-for-byte unchanged. Their 11 synthetic tests and fixed-commit CI evidence remain the baseline. Two terminal adapters change only the function source path to a package-relative path. Separate adapter tests cover relocated directories, non-TTY silence, command errors, prompt-hook deduplication and exit-status preservation; see [the fixture boundaries](references/validation.md). These tests use pipes and temporary directories, with no live history, real terminal reset, client, application or model. Run `python3 -B -m unittest discover -s tests -v` from the root.

The [GitHub Actions workflow](https://github.com/lzhs1995/runtime-recovery-kit/actions/workflows/checks.yml) runs the fixture suite on Linux/macOS with Python 3.11/3.14. Follow the workflow link for the actual results of each commit.

No universal agent or native-platform support is claimed. The original modules had no license declaration; this edition adds no new license and redistributes no third-party binary.

## Configured adapter dispatch

The optional [adapter dispatcher](references/agent-dispatch.md) replaces itself with an argv selected from your explicit private configuration. It forwards arguments unchanged and preserves an inherited `HERDR_AGENT` unless an exact label is configured. It launches the configured program; no agent CLI, model, profile or session is bundled.
