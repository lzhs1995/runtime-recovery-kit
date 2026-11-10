# Synthetic verification / 合成驗證

Run from the repository root with POSIX Python:

```sh
python3 -B -m unittest discover -s tests -v
```

The fixtures create a temporary, canonical home with synthetic session IDs and history headers. Every observer call passes that temporary home explicitly. Two short-lived fixture children hold exclusive locks on those temporary files to verify the `IN_USE` and coordination-busy results. Each observation checks `recovery_authorized=false`, zero reported writes/launches, and unchanged fixture paths/content. The children terminate when the fixture closes its input; they are not agents or clients.

The cases also cover absent/unheld writers, wrong and incomplete headers, symlink history/locks, unsafe lock permissions, a history outside the supplied home, and a valid historical hardlink. These are API contract tests, not observations of a real Codex session or a native-release compatibility claim.

The Bash and Zsh fixtures use piped stdout and nonterminal stdin. Sourcing must emit nothing; invoking the function must emit exactly the documented reset sequences into the pipe. Captured control bytes never go to a real TTY. The suite uses whichever of `/bin/bash` and `/bin/zsh` exists; the local candidate review records which shells were available.

測試只建立暫存的 canonical home、合成 SID 與 history 標頭；每次觀測都明確傳入該暫存 home。兩個短命測試子程序只鎖定其中的合成檔案，以核驗寫入占用及協調鎖忙碌分支。所有結果均檢查 `recovery_authorized=false`、回報寫入/啟動為零，且測試檔案路徑與內容不變。

其餘案例涵蓋無寫入鎖、未持有的既有鎖、錯誤/不完整標頭、symlink、不安全權限、home 外 history 及合法歷史 hardlink。這是 API 合成測試，沒有讀真實 `CODEX_HOME`、history、鎖或應用狀態。

終端測試只將輸出導入管道：載入函式不應輸出；呼叫後核對完整控制碼。沒有重設真實終端、啟動會話、請求模型或安裝客戶端。CI 定義涵蓋 Linux/macOS 的 Python 3.11/3.14；此本機候選尚未在 GitHub 執行 CI，不預先聲稱矩陣通過。
