---
name: agent-toolchain-recovery
description: Diagnose agent startup, tool discovery, terminal input-mode failures and interrupted tasks while preserving the original session, controller and evidence. Use for an actual tool failure or requested toolchain maintenance.
---

# Agent Toolchain Recovery

Read [the recovery layers](references/recovery-layers.md) and select the smallest check that can distinguish the observed failure.

1. Read the active task checkpoint. Keep the original session, controller, attempt, pending result and granted scope. An installation or environment marker does not establish task identity.
2. Separate executable/configuration availability from actual client loading, transport initialization, application access and task correctness. Inspect available native and deferred tool interfaces before concluding that a tool is missing.
3. Record the exact failed operation and original result. Continue independent authorized work. Resolve an unknown outcome through the original operation's supported readback; do not blindly resubmit it or create a replacement session.
4. Make a repair only at the failed layer within existing authorization. Preserve active clients, drafts, private settings and original evidence. Use supported application and client permission flows.
5. Verify the repaired layer with an actual bounded operation when the task authorizes it. Report skipped or unavailable checks accurately, then continue the original task.

For terminal input-protocol residue, [README.md](README.md#terminal-input-mode-recovery) gives the included Bash/Zsh function. Invoke it only when the affected program has returned control to an interactive shell. Never use a repeating reset, screen clear, input flush or speculative Enter as recovery.

The [manual command and optional Zsh prompt hook](references/terminal-integration.md) use that same function. Keep their existing TTY and prompt conditions. Do not install a hook into a user's shell profile as an incidental source-code check.

The optional [writer observer](references/writer-observation.md) is a library, not a session launcher. Use an explicit private target and Codex home only when the active task calls for this inspection and its native lock contract matches. It briefly takes nonblocking shared advisory locks; it never creates/deletes lock files. Keep returned identifiers and paths private. An idle result grants no recovery authority.

For application or session recovery, use the installed tool's version-specific interface and the original task bindings. This package does not include an updater, session launcher, native identity proof or a generic permission grant. Existing authorization persists; a genuinely new action outside that scope needs its own decision.

Keep public examples synthetic. Reports containing paths, arguments, session identifiers or account settings remain private unless explicitly prepared for publication. Use [source scope](references/source-scope.md) when extending this package.

For source maintenance, run the [synthetic fixture suite](references/validation.md). It exercises temporary files and captured output only; these results do not grant a session resume or establish native client compatibility.
