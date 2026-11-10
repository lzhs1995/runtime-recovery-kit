# Explicit-layout launcher / 明確布局啟動器

The optional `scripts/toolchain_launch.py` moves the five installation-specific
entries of the original 14-line startup wrapper into private caller configuration.
It retains the original doctor-only branch, terminal condition, nonblocking
startup check and final process replacement. It launches the configured CLI and
asks the doctor to write a report; it is not a read-only command or an installer.

## Configuration and use

Use POSIX Python 3.11 or newer. Supply your own Python interpreter and CLI, the
included [doctor](doctor-layout.md), and the included Bash
[terminal recovery command](terminal-integration.md). Keep the terminal command
beside its `terminal_modes.sh` library and the doctor beside `package_layout.py`.
The supplied doctor requires macOS signing tools for its signing checks; using
the launcher on another POSIX system does not make those checks available.
Native Windows, bundled client binaries and automatic installation are outside
this launcher's scope.

Create a private JSON file with explicit absolute paths. These example paths
are placeholders, not an installation layout or provider selection:

```json
{
  "python": "/example/bin/python3",
  "doctor": "/example/runtime-recovery-kit/scripts/toolchain_doctor.py",
  "report": "/example/private/reports/startup.json",
  "terminal_recover": "/example/runtime-recovery-kit/scripts/codex-terminal-recover",
  "cli": "/example/bin/client",
  "doctor_config": "/example/private/client.toml",
  "package": "/example/client-package",
  "app_candidates": []
}
```

Every field above is required. `app_candidates` is an explicit array of absolute
application paths, and may be empty. An optional `cache` field selects an absolute
signature-cache path; omitting it means no cache path is passed to the doctor.
Unknown or duplicate fields, relative paths and invalid JSON are rejected with
exit 2 before any configured program runs. Paths are not expanded or searched
through `PATH`; dependency existence is left to the invoked programs so a missing
startup dependency retains the original nonblocking behavior. Configuration and
report files may contain private information; keep them outside the public tree.

From the repository root, after replacing the example layout filename:

```sh
python3 scripts/toolchain_launch.py --layout /example/private/launch.json --help
python3 scripts/toolchain_launch.py --layout /example/private/launch.json --doctor-only
```

Only the leading `--layout FILE` belongs to the launcher. Everything after it is
the original client argument list, including empty strings, spaces and a literal
`--`. Do not insert a separator unless the client should receive it. There is no
shell evaluation, model/profile/session default, directory change or environment
marker assignment. Use the launcher directly for an interactive CLI; a wrapper
that captures stdout may remove the required TTY.

## Retained order and effects

1. If the first original argument is `--doctor-only`, the launcher immediately
   replaces itself with the configured Python running the doctor with `-BE` and
   the explicit layout/report arguments, without `--startup`. Trailing original
   arguments are ignored, as in the original wrapper. The doctor's PID and exit
   status replace the launcher's; terminal recovery and the CLI are skipped.
2. Otherwise, the terminal helper receives `--before-launch` only when **both**
   stdin and stdout are TTYs. The included helper writes terminal control bytes
   on that path; it does not run `stty sane` for `--before-launch`. A helper error
   or nonzero status does not prevent the following steps.
3. The doctor runs with `-BE`, `--startup` and the selected report path. Both its
   stdout and stderr go to the launcher's stderr. A nonzero status or an inability
   to start the doctor does not prevent the final CLI exec. There is no added
   timeout: a doctor that remains running still delays the CLI, as before.
4. The launcher replaces itself with the configured CLI and every original
   argument. PID, working directory, environment and standard descriptors carry
   through the exec; Python's ignored pipe/file-size signals are reset to their
   defaults before replacement. A missing executable returns 127; another exec
   failure returns 126. A successful exec leaves the CLI's own status in control.

The launcher never creates a report or synthesizes a successful check. The
configured doctor owns report writes (including its selected parent directory)
and optional cache writes. If it cannot run, an earlier report may remain stale.
The included doctor's startup exit zero may still contain issues or a pending
full signature check. Reaching the CLI establishes neither repair success nor
client loading, application access, authenticated session identity or task
completion. Preserve the original task and session arguments; this wrapper does
not select or resume a session for you.

## Synthetic verification

Run only this increment with:

```sh
python3 -B -m unittest discover -s tests -p test_toolchain_launch.py -v
```

The cases use temporary fake doctor, helper and CLI files, pipe all descriptors,
and mock only the TTY predicate for branch coverage. They check argument and PID
preservation, environment/cwd/stdin inheritance, doctor-only report/status,
startup/helper failures, stderr routing and invalid layouts. No live CLI, model,
session, terminal reset, signing tool, report location or application is used.
The tests require `/bin/sh` only to exec the temporary fake programs safely.

## 繁體中文

這個可選啟動器把原 14 行 wrapper 的 Python、doctor、報告、終端 helper 和
CLI 五個固定入口改為明確私有設定，另補已公開 doctor 必需的設定檔、套件與
應用候選路徑。它會啟動指定 CLI、讓 doctor 寫報告，符合雙 TTY 條件時也會
呼叫終端 helper；它不是唯讀命令、安裝器或自動會話恢復工具。

依賴 POSIX Python 3.11 以上、呼叫者提供的 CLI，以及本套件的 doctor 與 Bash
終端命令。doctor 的簽名檢查另依賴 macOS 工具；其他 POSIX 平台能執行 wrapper
不代表已具備 macOS 簽名能力。原生 Windows 不在範圍內。doctor 應與
`package_layout.py` 同目錄，終端命令應與 `terminal_modes.sh` 同目錄。

上方 JSON 八欄均必填，路徑必須為絕對路徑；`app_candidates` 可明確設為空
陣列。只有加入可選 `cache` 路徑才會把快取位置交给 doctor。範例只是占位符，
沒有內建機器、模型、profile 或會話選擇。重複／未知欄位、相對路徑及錯誤 JSON
會在啟動依賴前以 exit 2 拒絕。設定與報告應保留在私有位置。

只有最前面的 `--layout FILE` 屬於 wrapper，其後所有參數逐字交給 CLI，包含
空字串和 `--`；只有其後第一個參數為 `--doctor-only` 才走 doctor 分支。此分支
以 `exec` 讓 doctor 接管原 PID、寫指定報告並決定退出碼，忽略其他參數，完全
略過終端 helper 和 CLI。一般分支只在 stdin、stdout **同時為 TTY** 時先呼叫
helper，再執行 doctor 的 `--startup`，兩種 doctor 輸出均導向 stderr，最後
`exec` 原 CLI 參數。沒有 shell eval，也不改 cwd、環境標記或會話參數。

helper 非零或缺失、doctor 非零或無法啟動，都保留原來繼續到 CLI 的行為；
沒有新增逾時，因此 doctor 若持續運行仍會延後 CLI。缺少最終執行檔為 127，
其他 exec 錯誤為 126。成功 exec 保留 PID、cwd、環境及標準描述符；替換前撤銷
Python 預設忽略的 pipe／file-size 信號。互動使用請直接執行，避免捕獲 stdout
的外層工具破壞 TTY 條件。

報告與可選快取由 doctor 寫入，wrapper 不造成功報告；doctor 未能執行時，舊
報告可能仍留在原處。`--startup` 的零退出碼可能仍有問題或待完整驗簽，繼續
啟動不等於恢復成功、工具載入、應用授權、會話身份或業務驗收。

上述測試只執行暫存假 doctor／helper／CLI，所有描述符均為管道，TTY 判斷以
mock 覆蓋分支。沒有操作真實終端、CLI、模型、會話、簽名工具或應用；也沒有
使用真實設定或報告位置。這次只提供原 launcher 的布局版本，不代替完整
client／updater、DSH 協議或其餘尚未整理的工具。
