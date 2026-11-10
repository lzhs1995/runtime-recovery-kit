# Codex writer observation / Codex 寫入鎖觀測

`scripts/resume_check.py` is an optional library for a specifically requested inspection. Running the file by itself does not perform a check. Importing it defines functions without reading a target or starting a client. It requires POSIX `fcntl`, `os.pread`, non-following file opens and the matching Codex `thread-writer-locks` layout. Synthetic API fixtures passed locally on Python 3.14. This is not native Codex release or multi-version Python compatibility evidence.

此檔是可選函式庫，直接執行不會啟動檢查；匯入也不讀取目標或啟動客戶端。需要 POSIX 檔案鎖、對應檔案 API，以及與當前 Codex 相符的 `thread-writer-locks` 格式。本機 Python 3.14 的合成 API fixtures 已通過；這不代表多版本 Python 或原生 Codex 相容性已驗證。

## API

Call `inspect_writer(target, codex_home=absolute_private_home)` through your own private integration. Keep the target outside the public checkout. Pass the home explicitly rather than relying on an inherited environment value.

| Target key | Required value |
|---|---|
| `agent` | The literal `codex` |
| `sid` | The original session's canonical UUID, privately supplied |
| `history` | Its existing canonical absolute history path under that home's `sessions` directory |

`codex_home` is the existing canonical absolute Codex home. The function checks file ownership, modes, path identity and the original history header. It reads at most the first 256 KiB, attempts nonblocking shared locks on existing native files and closes them on return. It creates or removes no files and starts no agent. The shared-lock attempts are transient synchronization, not a zero-interaction probe.

請透過自己的私人整合呼叫上述 API，明確傳入原目標與 home。不要把真實目標清單、history 或回傳報告提交至公開倉庫。函式核對擁有者、模式、路徑身分與原始 history 標頭，最多讀取開頭 256 KiB，僅短暫嘗試既有檔案的非阻塞共享鎖。它不建立／刪除檔案，也不啟動 agent；鎖定嘗試仍是一種暫時同步操作。

## Interpret the result

- `IN_USE`: the original native writer lock was held at the check.
- `IDLE_AT_CHECK`: no held original writer lock was observed within the checked namespace at that instant.
- `UNKNOWN`: the required files, contract or identities could not be confirmed. Preserve the original session and inspect the stated reason.

All results retain `recovery_authorized: false`. The function does not reserve a pane, authenticate the calling agent or authorize a new launch. The native client must obtain its own lock when an independently authorized resume actually occurs. Returned session IDs, paths and errors are private task evidence.

三種結果分別表示「檢查時仍被占用」、「該當刻未觀察到占用」及「無法確認」。所有結果均保留 `recovery_authorized: false`；它不保留面板、不認證呼叫者，也不授權啟動。實際恢復時仍須由原生客戶端取得自己的鎖，回傳識別碼、路徑與錯誤僅作私人任務證據。

See [synthetic verification](validation.md) for reproducible fixture checks that do not use a live home, history or native lock.
