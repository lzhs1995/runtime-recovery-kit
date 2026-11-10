# Recovery layers / 故障層次

| Observed failure / 現象 | Smallest useful check / 最小檢查 | What it does not prove / 尚未證明 |
|---|---|---|
| Executable missing / 找不到程式 | Resolve the configured executable and inspect its existence and executable permission. / 核設定的入口與執行權限。 | Active process version, signature, client loading. / 現役版本、簽名及載入。 |
| Configuration rejected / 設定被拒 | Parse with the actual configuration format; check required transport fields and paths without executing configured commands. / 依實際格式解析，檢查傳輸欄位與路徑，不執行設定中的命令。 | Transport initialization or tool availability. / 傳輸初始化與工具可用性。 |
| Tool missing from one list / 單一清單缺工具 | Inspect both native and deferred interfaces, then perform an authorized minimal call. / 核原生與延遲入口，再做獲授權的最小呼叫。 | Application access or business success. / 應用存取與業務成功。 |
| CLI works but a tool fails / CLI 可用但工具失敗 | Check the helper actually resolved by that same package and entry path. / 核同一套件及入口實際解析到的輔助程式。 | Another helper somewhere on disk is not proof. / 磁碟其他位置有檔不代表接線有效。 |
| Terminal prints control codes / 終端顯示控制碼 | Once back at the interactive shell, use the included terminal mode function once. / 回到互動 shell 後呼叫所附函式一次。 | All terminal attributes, application health or draft delivery. / 全部終端屬性、應用健康或草稿送達。 |
| Application list works but a window fails / 應用清單可用但視窗失敗 | Refresh the window binding and distinguish a dialog, stale handle and process replacement. / 更新視窗綁定，區分對話框、舊物件與程式更換。 | Saving, rendering or content correctness. / 儲存、渲染與內容正確。 |
| An operation timed out / 原操作逾時 | Preserve its original receipt and use its supported status/readback endpoint. / 保留原回執，沿支援的狀態入口讀回。 | Timeout is not proof that nothing was sent or changed. / 逾時不代表未送出或未改動。 |
| Session may still have a writer / 會話可能仍有寫入者 | Use the original client's version-specific check with a privately supplied exact target. / 用原客戶端版本對應檢查，私下提供精確目標。 | An idle snapshot is not resume authorization or an atomic reservation. / 空閒快照不等於恢復授權或原子保留。 |

## Minimal evidence / 最小證據

Record the time, tool/source version, original operation, actual result and remaining unknowns in the private task log. Public summaries should contain issue codes and validation scope, not raw configuration, command arguments, session IDs or manuscript paths.

於私人任務日誌保留時間、工具／來源版本、原操作、實際結果與未知項。公開摘要只保留問題代碼及驗證範圍，不直接貼設定、參數、會話 ID 或稿件路徑。

A repair can be accepted at one layer while downstream work remains incomplete. Resume from the original checkpoint and avoid repeating already accepted research or replaying completed operations.

修復可只在某一層通過，下游工作仍可能未完。沿原斷點繼續，不重做已驗收研究，也不重放已完成操作。
