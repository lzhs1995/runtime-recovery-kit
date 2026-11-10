# Explicit doctor layout / 明確的診斷布局

`scripts/toolchain_doctor.py` retains the local doctor's configuration, helper-path and macOS signature checks. Every installation path is supplied explicitly. It imports only the small sibling `package_layout` helper, not the client updater.

From the repository root, provide your own private paths:

```sh
python3 -B scripts/toolchain_doctor.py \
  --config ./private/config.toml \
  --cli ./private/package/bin/codex \
  --package ./private/package \
  --app-candidates ./private/Codex.app
```

`--config`, `--cli`, `--package` and `--app-candidates` are required. `--app-candidates` accepts multiple paths or an explicit empty list; it never searches default application directories. An empty list retains the original `OFFICIAL_CUA_RUNTIME_MISSING` result. The default invocation prints a report but creates no cache or report file.

Two optional paths select the original file-writing behavior:

- `--cache PATH` allows reading and updating that signature cache. Without it, no cache is read or written. A reusable cache must match the CLI's complete file identity and the observed OpenAI signing team. A newly verified cache is written only after successful signature verification, an unchanged before/after file identity and the matching team; it uses the original exclusive temporary-file, mode `0600` and replacement sequence.
- `--output PATH` writes the report at that explicit path using the same temporary-file and mode `0600` protocol. Without it, the report is printed only. Report output is independent of cache selection.

The Python interface is `run(config_path, *, cli, package, app_candidates, cache_path=None, startup=False, active_pids=None)`. It returns the original report structure; it does not create a report file itself. All application candidates are caller-supplied paths. Signature commands use macOS `codesign`; optional `--active-pid` uses the original macOS process-path observation and is never an automatic process scan.

`--startup` preserves the original nonblocking startup behavior: it may reuse a valid explicit cache, otherwise it reads signing metadata without full verification and reports verification as pending. It returns zero even when it prints diagnostic issues, so it must not be treated as repair acceptance or authority to launch a client. This command does not itself launch a client, change permissions, contact an MCP server, access an application, allocate a resource or update a package.

Reports contain caller-supplied paths, configuration details and inherited environment markers. Keep real reports private. Inherited PID/thread markers remain unauthenticated. `PASS_CONFIG_ONLY` does not prove actual client loading, model calls, native tool registration, session identity or application access. The helper-path check is described separately in [package layout](package-layout.md).

此版本保留原 doctor 的設定、helper 同檔案、macOS 簽名及前後檔案身份核對；所有安裝路徑均需明確提供，只匯入同目錄的輕量 helper，不載入完整 updater。四個必填參數為 `--config`、`--cli`、`--package`、`--app-candidates`；應用候選可明確為空，不猜測系統應用目錄。

`--cache` 未指定時完全不讀寫快取，指定後仍須同檔案身份、原 OpenAI team 及原簽名條件；`--output` 未指定時只印報告，指定後才依原 `0600` 暫存檔及替換協議寫報告。兩項互相獨立。`--startup` 沿用原非阻斷行為：沒有合格明確快取時只讀簽名 metadata，完整驗證標為 pending，即使有問題仍回傳零；不能當成恢復驗收。

真實診斷會讀取指定檔案並執行 macOS `codesign`；只有明確指定 PID 才觀測該程序。輸出可能包含私人路徑與繼承標記，應留在私人報告。此候選的驗證只用合成檔案與攔截的原生呼叫，沒有讀現役設定、執行真實 CLI／codesign、應用或網路。

Run only this layout delta / 僅執行本次布局差量：

```sh
python3 -B -m unittest discover -s tests -p test_doctor_layout.py -v
```

The fixtures intercept every native subprocess request and reject unexpected commands. They exercise required arguments, explicit layouts, omitted and selected cache/report paths, the original startup/cache behavior, signing-team and file-identity failures, and the real extracted helper's mismatch result. The existing observer, terminal and helper suites are unchanged by this preparation.
