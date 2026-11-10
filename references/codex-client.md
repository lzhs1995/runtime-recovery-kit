# Explicit Codex client maintenance

`scripts/codex_client.py` exposes the original signed-package manager through an explicit private layout. It supports official `aarch64-apple-darwin` packages with the recognized Codex CLI/helper layout and OpenAI signing team. Actual verification requires macOS and `/usr/bin/codesign`; update additionally requires `gh` with access to the official release. No binary, account configuration or installation layout is bundled.

## Layout

Supply every field. This is a synthetic example, not an installation recipe or a recommended capacity budget:

```json
{
  "schema": "codex-client-layout-v1",
  "selection_root": "/opt/example-codex/selection",
  "releases_root": "/opt/example-codex/releases",
  "state_root": "/opt/example-codex/state",
  "package_locks": ["/opt/example-codex/package/install.lock"],
  "aliases": {
    "/opt/example-codex/bin/codex": "/opt/example-codex/selection/cli",
    "/opt/example-codex/bin/codex-code-mode-host": "/opt/example-codex/selection/current/bin/codex-code-mode-host"
  },
  "cli": "/opt/example-codex/bin/codex",
  "minimum_free_bytes": 45097156608
}
```

Paths must be absolute and contain no parent traversal. The free-space threshold must be a positive integer, not a boolean; it has no machine default. `releases_root` must exist before applying an update. Supply every package lock used by the installation's cooperating updaters. The selection lock is added automatically. Duplicate locks and aliases overriding the owned `current` or `cli` selectors are rejected.

`cli` is the current executable selected for the adoption same-file check. `aliases` is the exact set the caller authorizes this manager to replace with symlinks; ordinary existing files are refused. Their targets may refer to the owned selectors or to an explicitly configured external launcher. Include the current CLI in that map if it should be maintained. Configuration parsing checks structure; it does not establish path ownership or grant permission to change a machine.

## Commands and effects

Run from the repository root with a private layout file:

```sh
python3 -B scripts/codex_client.py --layout /private/example/client-layout.json config
python3 -B scripts/codex_client.py --layout /private/example/client-layout.json status
python3 -B scripts/codex_client.py --layout /private/example/client-layout.json plan --output /private/example/update-plan.json update 1.2.3
python3 -B scripts/codex_client.py --layout /private/example/client-layout.json plan --output /private/example/adopt-plan.json adopt /opt/example-codex/releases/1.2.3
```

The versions and paths above are examples. Choose the actual authorized version or package explicitly.

| Command | Reads or calls | Writes |
|---|---|---|
| `config` | Parses the supplied layout and prints it. | None. |
| `status` | Verifies the selected package, signatures, runtime helper, version and alias file identity; observes primary/helper processes. The verified CLI is invoked with `--version`. | No installation or report writes by this script. |
| `plan` | Parses the layout and records its exact path, byte count and SHA256 with the requested action. No package, capacity, process, signature or network preflight. | Creates the explicit plan and any missing parent directories; refuses an existing plan file and sets file mode `0600`. |
| `apply` | Verifies the plan SHA256 and exact layout/action binding, then calls the original adopt or update engine. | Locks, receipts, selectors and aliases; update also downloads, installs and conditionally retires the exact previous owned release. |

To apply an authorized plan, copy its complete SHA256 from the plan command's `plan.sha256` output:

```sh
python3 -B scripts/codex_client.py --layout /private/example/client-layout.json apply --plan /private/example/update-plan.json --plan-sha256 PLAN_SHA256_FROM_OUTPUT
```

`PLAN_SHA256_FROM_OUTPUT` must be replaced with the actual 64 hexadecimal digits. A plan binds intent and layout bytes; it is not a successful preflight, a package-content pin, a reservation or a single-use execution receipt. `apply` uses the same layout bytes it verifies. Status never applies repairs or downloads. Status exits `1` when it reports issues and `0` when its selected-package checks are consistent; neither outcome establishes model/tool readiness or session identity.

## Preserved transaction

Adoption verifies the supplied package and requires its executable to be the same file as the configured current CLI. It may normalize aliases while that same executable remains active. Update requires an explicit stable version, obtains the installation locks, refuses active primary clients, compares actual free space with the configured threshold and refuses an existing destination. It obtains the unique official release asset with a SHA256 digest, verifies the archive, extracts through Python's data filter, checks the package signatures and version, and checks processes again before switching.

The switch writes an intent before alias replacement, detects concurrent alias changes and reads back the configured targets. On failure it rolls back only aliases still pointing to its own just-written targets. An uncertain switch or final-receipt failure retains the prepared package. Successful update retires only the previous package directly inside the configured release root after checking for live users and verifying its recorded executable digest. It never kills clients or searches unrelated artifacts for cleanup.

Keep the original receipts and inspect actual selectors after an uncertain result before deciding any next action. Locking relies on cooperating writers; a saved plan and a process observation do not exclude later external changes. Plans, status output and receipts contain installation paths and belong in private task evidence. Synthetic tests establish these code boundaries, not a live installation, successful download, native signature result or session recovery.
