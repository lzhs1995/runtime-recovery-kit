# DSH adapter with explicit layout / 明確布局 DSH 適配器

`scripts/herdr-dsh.mjs` derives the original 289-line terminal adapter through a
required private JSON layout. It starts one caller-selected external DSH process,
speaks the original newline JSON-RPC protocol and optionally reports state to
Herdr. It does not install an SDK, configure providers, authenticate a session or
choose a previous task. Use it only for an authorized launch with the original
task's intended session and working directory.

## External dependency and compatibility evidence

Use Node 24 on POSIX and an independently installed DSH executable with a profile
that exposes the SDK JSON-RPC protocol on stdout. The adapter has only Node
standard-library imports; no DSH/Herdr SDK, model, provider, credential, profile or
binary is included. A profile is the external CLI's **selector**, not a claim that
arbitrary absolute profile filenames are supported. Native Windows and other
Node majors are outside this edition's executed fixture scope.

The source survey recorded installed npm metadata for `@deepseek-ai/dsh`,
`dsh-sdk-app`, `dsh-sdk-protocol` and `dsh-sdk-jsonrpc-server` at **0.2.1-rc.2**.
The installed JSON-RPC server source declared `serverInfo.name` as
`deepseek-harness-sdk-runtime` and its **wire version as 0.0.1**. These are separate
package and wire values seen in files, not a real `initialize` response, a latest
version claim, signature verification or proof that any private profile loads
that runtime. The adapter preserves the original **name-only** check; it does not
check the returned version or add a version gate. A matching name alone does not
authenticate the child, its package or its session.

## Explicit inputs

Create a private JSON layout. Every path and name below is a placeholder that the
caller must replace with their intended installation; no default provider or
model is selected:

```json
{
  "dsh_bin": "/example/bin/dsh",
  "profile": "chosen-sdk-profile",
  "provider": "chosen-provider",
  "model": "chosen-model",
  "reporter": { "mode": "disabled" },
  "resume_argv": [
    "/example/bin/node",
    "/example/runtime-recovery-kit/scripts/herdr-dsh.mjs",
    "--layout",
    "/example/private/dsh-layout.json"
  ]
}
```

All six fields are required. `dsh_bin` must be an absolute executable path and is
passed directly to `spawn` with `['--profile', profile]`; the adapter neither
searches `PATH` for another DSH installation nor uses a shell. The external binary
must be executable when invoked; validation of layout shape does not establish
its existence, signature or protocol compatibility. `profile`, `provider` and
`model` must be nonempty single-line strings without apostrophes, retaining the
original command-value restriction. Unknown fields and malformed values reject
before launch. JSON uses Node's ordinary `JSON.parse` semantics; keep keys unique.

Optional `dsh_home` selects an absolute path by overriding **only the child's
`DSH_HOME`**. The imported installed home resolver statically uses that variable;
this was not tested with a live DSH home. With no override, the original
environment is inherited, including any existing DSH home selection. The adapter
does not inspect, create or migrate a profile/home itself. The external DSH
program may read or write its own configuration, session and logs when launched;
caller-managed model credentials and other environment values still pass to it.

`resume_argv` is a nonempty literal argument array whose first entry is an
absolute executable path. Provide the real Node/launcher/module arguments and
**the same layout path** needed to reach this installation again. The adapter
does not prove the prefix is executable or validate that it selects the same
configuration. It appends `--session`, the actual session value, `--provider` and
`--model` with their effective values to state reports. No shell string is built,
and the adapter does not execute the resume array itself. This is a resume recipe
for the receiving integration, not authenticated identity or recovery authority.

For optional Herdr reporting, replace only the `reporter` object with an explicit
environment view:

```json
{
  "mode": "herdr",
  "env": {
    "HERDR_ENV": "1",
    "HERDR_SOCKET_PATH": "/example/private/herdr.sock",
    "HERDR_PANE_ID": "caller-selected-pane"
  }
}
```

The enabled marker must be exactly `"1"`, the socket path absolute and the pane ID
an explicit nonempty single-line string. This view is used only by the reporter;
it does not change the parent or child environment. `{"mode":"disabled"}` makes
the reporter skip connection attempts, even if the parent has Herdr variables.
There is no implicit environment discovery for the reporter and no pane identity
validation. Keep real layouts, output, socket/pane values and resume recipes
private.

## Launch and retained lifecycle

From the repository root, with a prepared private layout:

```sh
node scripts/herdr-dsh.mjs --layout /example/private/dsh-layout.json
node scripts/herdr-dsh.mjs --layout /example/private/dsh-layout.json --session original-session-value
```

`--provider` and `--model` explicitly override the corresponding layout fields,
regardless of argument order; repeated options retain the original last-value
behavior. No legacy provider/model environment value acts as an adapter default.
`--help`/`-h` prints usage without loading a layout or launching a child. Unknown
or incomplete arguments fail. The original session restriction is retained:
nonempty single-line values without apostrophes; UUID syntax is not newly enforced.

Without `--session`, the adapter generates a new UUID and requests
`session/working-directory/get`; with it, the adapter requests `session/resume`
for that exact supplied value. It does not read history or select a recent
session. The original current working directory is sent to `initialize` and
inherited by the child. Initialization order remains `initialize` → name check →
resume or working-directory/get → ready.

The input commands remain `/status`, `/quit` and `/exit`; Ctrl+C starts shutdown.
A prompt request is followed by `session/wait`. Prompt admission does not mean
idle or finished. Only same-session notifications update the state bridge:
running → working, idle → idle unless a failed turn is retained, and error/blocked
turn completion → blocked. Before ready, states are only observed. Another
session's events are ignored. Assistant text, tool names and turn errors retain
their original output behavior, including raw startup diagnostics; output may
contain private runtime information.

Stop calls share one promise. Shutdown is requested with the original 5-second
timeout, then the original bounded exit wait applies. Failure or a child still
running after the wait triggers `SIGTERM` on **only the child created here**.
There is no new process search, history cleanup, session deletion, `SIGKILL` or
guarantee that a child honoring neither shutdown nor SIGTERM has exited. State
release is idempotent and published only after ready; reporter queue completion
is awaited. The original signal handlers are removed when the adapter finishes.

## Protocol and reporter limits retained

`RpcPeer` retains incremental newline parsing, increasing request IDs, a pending
map, request timers and write/child failures. Its buffer guard is
`buffer.length > 8 * 1024 * 1024` on a **JavaScript string**, measured in UTF-16
code units after decoding. It is not a strict UTF-8 8 MiB byte limit, nor a new
per-frame security parser. The guard applies to the accumulated data before
splitting complete lines, as in the original source.

The reporter serializes requests. Any socket **data, end, error or timeout** ends
its wait; it does not parse an affirmative reply. A malformed reply, a refusal,
a closed connection or a timeout can therefore let `flush()` complete. Queue
completion proves neither Herdr receipt, authenticated pane/session identity,
business acceptance nor actual agent/resource release. This adapter preserves
that weak completion behavior and does not introduce a delivery system.

## New synthetic tests

```sh
node --test tests/test_herdr_dsh.mjs
```

The twelve cases are **new tests**, not reused original DSH tests. They use Node
memory streams, synthetic child objects, mocked sockets, and one temporary fake
SDK script behind a fake executable. They cover split/multiple/malformed frames,
JS-length overflow, timeout/write/exit failures, session filtering, ready/blocked
states, reporter ordering and weak completion, explicit arguments/home/cwd,
name-only handshake, prompt/wait and single-child stop. The direct-entry fixture
keeps its input pipe open until quit is processed; it does not represent a real
TTY. No real DSH, SDK profile, Herdr socket, model, credentials or session is used.

During preparation, eleven cases passed in the first run. The direct-entry case
needed two fixture-only corrections: avoid premature input EOF, then compare the
canonical temporary cwd on macOS. Both failures and original fixtures were
retained privately; the corrected case passed separately. The adapter itself did
not change for those corrections. A later combined CI run should execute this
suite together with the existing Python fixtures; preparation does not claim
that CI or real-runtime validation has already occurred.

## 繁體中文

此適配器將原 289 行 terminal client 的必要入口改為明確私有布局，保留原
`RpcPeer`、狀態橋、只核名稱的握手、同 session 事件及收尾行為。它會啟動
呼叫者指定的 DSH，Herdr reporter 可明確停用或指定 env 視圖；它不是安裝器、
新模型框架或自動會話恢复工具。需要 Node 24／POSIX、外部 DSH 及能在 stdout
提供 SDK JSON-RPC 的 profile。套件不附 SDK、CLI 二進位、profile、憑據或模型。

靜態來源所見 npm 套件為 **0.2.1-rc.2**，server 原碼的 wire 版本為 **0.0.1**，
两者分開記錄；沒有真實 initialize 回執。原程式只檢查
`deepseek-harness-sdk-runtime` 名稱，未新增版本門禁。名稱吻合不代表身份、
套件簽名、私有 profile 已載入或現役相容性。

六個必填欄位及可選 `dsh_home` 如上方範例；所有範例均為占位符。`dsh_bin`
為絕對路徑，profile 是外部 CLI 的 selector；不把它宣稱為任意設定檔路徑。
provider／model 必須提供，CLI 覆蓋布局，同名參數最後值生效。指定 `dsh_home`
只改本次 child 的 `DSH_HOME`，其餘環境保留；未指定則繼承原環境。適配器不讀
私有 profile，但真正啟動的外部程式仍可能讀寫它自己的設定、會話及日誌。

`resume_argv` 必須為 literal argv 陣列，以絕對執行檔開頭，並由呼叫者填入
能回到同一程式與同一 layout 的前綴。適配器不驗證前綴確實可恢復，只追加
原 session、有效 provider/model 後放入回報，自己不執行這個陣列。沒有指定
session 才產生新 UUID；指定時只 resume 該值，不掃 history、不挑最近會話。

Herdr 停用模式不連線；啟用需明確的 `HERDR_ENV="1"`、socket 絕對路徑及
pane ID，沒有從父環境猜身份。回報串行，但任意 data／end／error／timeout
都能結束等待；`flush()` 完成不是接收、身份認證、業務接受或資源釋放證據。
RPC 上限是 JavaScript string `length` 的 UTF-16 code units，不能称為严格
UTF-8 8 MiB 位元組限制。

只接受同 session 的狀態與事件；ready 前只記觀測，prompt 被接受不等於完成，
blocked 不被隨後 idle 蓋掉，新的 running 才解除 failed 狀態。stop 共用一次
Promise，保原 shutdown 及 5 秒有界等待，只對自己建立的 child 發 SIGTERM；
不刪會話／歷史、不關其他程序，也不宣稱一定殺死拒絕退出的 child。release
只在 ready 後一次性發出，其實際受理仍未證明。原 stdout／診斷可能含私有資訊。

十二項是這次**新增**的合成測試。只用內存流、假 child、mock socket 和暫存
假 SDK；沒有真 DSH、Herdr、模型、profile 或現役會話。首輪 11 項通過，直連
假 SDK 案例修正過早 EOF 及 macOS canonical cwd 預期後定向通過；兩次失敗
原件保留，產品原碼不因它們修改。後續組合 CI 與真實 runtime 驗收另行記錄。

## Preserved EOF limitation / 保留的 EOF 限制

The original lifecycle can still report `readline was closed` if the input pipe
closes before prompt/wait handling has finished. This candidate neither repairs
that behavior nor establishes graceful EOF handling. The passing fake-SDK case
covers only input held open until `/quit` is processed.

若輸入管道在 prompt／wait 處理完成前關閉，原生命週期仍可能回報
`readline was closed`。本候選沒有修復這個行為，也未驗證 graceful EOF；
通過的假 SDK 案例只涵蓋輸入保持開啟至 `/quit` 處理完成的情形。
