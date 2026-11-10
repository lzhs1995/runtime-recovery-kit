# Explicit adapter dispatcher / 明確指定的適配器派發

`scripts/agent_dispatch.py` replaces its own process with an adapter selected from a caller-supplied private JSON file. It provides the selection and `exec` behavior of the original small `herdr-agent` wrapper. It does not include any agent CLI, model provider, profile, session target or DSH protocol implementation.

The configuration has an `adapters` object mapping each allowed key directly to a nonempty argv array. An optional `herdr_agent` object maps selected keys to exact environment labels. Keep real executable paths and profile arguments in your own private file. The following names and paths are placeholders, not installed defaults:

```json
{
  "adapters": {
    "example": ["/path/to/adapter", "fixed-argument"],
    "example-alias": ["/path/to/adapter", "fixed-argument"],
    "inherit-marker": ["/path/to/another-adapter"]
  },
  "herdr_agent": {
    "example": "exact-label",
    "example-alias": "exact-label"
  }
}
```

Invoke it from the repository root using your private configuration:

```sh
python3 -B scripts/agent_dispatch.py --config /path/to/private-config.json example --argument "two words"
```

Everything after the adapter key is forwarded as separate, unchanged arguments after the configured argv prefix. There is no shell expansion or evaluation. An executable name can use the inherited `PATH`; an explicit path selects that path. The working directory, remaining environment and terminal descriptors are inherited. A successful `exec` replaces the dispatcher, so the adapter owns the same process ID and determines its exit status. Configuration or unknown/missing-key errors exit 2; missing or nonexecutable targets retain the shell-style 127 or 126 result.

Each configured label replaces `HERDR_AGENT` exactly. With no label for a key, the existing value remains inherited, including absence. This preserves the original distinction: most branches set an adapter-specific label, while the original `dsh` branch does not set one. Aliases are expressed explicitly with the same argv and label; no provider aliases or profile numbers are built in. `HERDR_AGENT` is a marker, not authenticated identity or permission to resume a session.

This is a launcher, not a read-only diagnostic. Running it can start the configured program and its model or session activity. The caller retains responsibility for the program, configuration, dependencies and existing task authorization. No configuration is discovered from home directories or environment variables, and no user profile or installed launcher is edited.

Use Python 3.11 or newer on POSIX for the tested process-replacement behavior. Seven synthetic tests execute only a temporary fake Python program and verify arguments, aliases, inherited labels, process ID, exit codes and rejected inputs. They do not establish that any real agent, provider, Herdr endpoint or DSH service is available. The DSH protocol adapter remains outside this increment.

## 繁體中文

此派發器只把原小型 `herdr-agent` wrapper 的選擇與 `exec` 行為改成明確私有設定。`adapters` 的每個鍵直接對應 argv 陣列；可選的 `herdr_agent` 另列精確標記。真實程式路徑、profile 參數和別名由自己的設定提供，不內建任何模型服務、profile 編號、機器路徑或會話目標。

adapter 鍵之後的參數逐項原樣接到設定的 argv 後面，不做 shell 展開或 `eval`。成功時以 `exec` 取代派發器，保留 PID、工作目錄、其他環境與終端描述符，並由被執行程式決定退出碼。設定錯誤、缺少或未知鍵回傳 2；找不到程式或無法執行分別回傳 127、126。

有標記時只將 `HERDR_AGENT` 設為指定字串；未設定時完整繼承原值，原本不存在就保持不存在。這也保留原 `dsh` 分支不主動設定標記的語義。別名需明確設定相同 argv 與標記；環境標記不代表身份認證或會話恢復授權。

這是會執行指定程式的啟動器，不是只讀 doctor。呼叫端需沿用實際任務授權並自行提供依賴與私有設定；工具不自動讀 home 設定、不修改已安裝入口、不包含 289 行 DSH 協議。七項測試僅執行暫存的假 Python 程式，不啟動真實模型或會話，也不宣稱所有平台或 CLI 已驗證。
