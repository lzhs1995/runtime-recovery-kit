# Synthetic verification / 合成驗證

Run from the repository root with POSIX Python:

```sh
python3 -B -m unittest discover -s tests -v
```

The original 11 cases remain unchanged. The terminal-adapter increment can be checked separately with `python3 -B -m unittest discover -s tests -p test_terminal_adapters.py -v`; its preparation does not rerun the unchanged observer suite or claim a new remote CI run.

The package-layout increment reuses three existing helper cases through `python3 -B -m unittest discover -s tests -p test_package_layout.py -v`. They check adjacent-helper identity, standard/app layouts and resource-helper precedence using temporary files only. This candidate preparation does not rerun the existing observer or terminal suites, and claims no new remote CI result.

The explicit-doctor delta is checked separately with `python3 -B -m unittest discover -s tests -p test_doctor_layout.py -v`. All configuration, package and app files are temporary fixtures. Every native subprocess is intercepted and every active-PID observation is forbidden in these fixtures. The checks cover explicit paths, optional cache/report writes, startup behavior, signature/team/file-identity failures and helper mismatch; they are not real codesign or active-client observations.

The fixtures create a temporary, canonical home with synthetic session IDs and history headers. Every observer call passes that temporary home explicitly. Two short-lived fixture children hold exclusive locks on those temporary files to verify the `IN_USE` and coordination-busy results. Each observation checks `recovery_authorized=false`, zero reported writes/launches, and unchanged fixture paths/content. The children terminate when the fixture closes its input; they are not agents or clients.

The cases also cover absent/unheld writers, wrong and incomplete headers, symlink history/locks, unsafe lock permissions, a history outside the supplied home, and a valid historical hardlink. These are API contract tests, not observations of a real Codex session or a native-release compatibility claim.

The Bash and Zsh fixtures use piped stdout and nonterminal stdin. Sourcing must emit nothing; invoking the function must emit exactly the documented reset sequences into the pipe. Captured control bytes never go to a real TTY. The suite uses whichever of `/bin/bash` and `/bin/zsh` exists; the local candidate review records which shells were available.

The adapter tests copy only the three terminal files to a temporary directory containing spaces. Bash tests cover the check/help and non-TTY branches; Zsh tests use a temporary `ZDOTDIR`, disable startup rc files, and verify relative loading, hook deduplication, the previous exit status and silence in an interactive shell whose descriptors are pipes. No fixture uses a real TTY or runs the `stty sane` branch. That branch is retained from the original command and is explicitly outside this fixture execution.

For commit [48770554](https://github.com/lzhs1995/runtime-recovery-kit/commit/4877055432138e0b38431545768c947a4e579afc), [GitHub Actions run 42813115561](https://github.com/lzhs1995/runtime-recovery-kit/actions/runs/42813115561) completed successfully in all four Linux/macOS × Python 3.11/3.14 jobs. These results cover the synthetic fixtures above; they do not establish live terminal recovery, client loading or native-release compatibility.

測試只建立暫存的 canonical home、合成 SID 與 history 標頭；每次觀測都明確傳入該暫存 home。兩個短命測試子程序只鎖定其中的合成檔案，以核驗寫入占用及協調鎖忙碌分支。所有結果均檢查 `recovery_authorized=false`、回報寫入/啟動為零，且測試檔案路徑與內容不變。

其餘案例涵蓋無寫入鎖、未持有的既有鎖、錯誤/不完整標頭、symlink、不安全權限、home 外 history 及合法歷史 hardlink。這是 API 合成測試，沒有讀真實 `CODEX_HOME`、history、鎖或應用狀態。

終端測試只將輸出導入管道：載入函式不應輸出；呼叫後核對完整控制碼。沒有重設真實終端、啟動會話、請求模型或安裝客戶端。固定提交 [48770554](https://github.com/lzhs1995/runtime-recovery-kit/commit/4877055432138e0b38431545768c947a4e579afc) 的 [GitHub Actions 執行 42813115561](https://github.com/lzhs1995/runtime-recovery-kit/actions/runs/42813115561) 已完成 Linux／macOS × Python 3.11／3.14 四組工作，全部成功。此結果僅涵蓋上述合成案例，不代表真實終端恢復、客戶端載入或原生版本相容性已驗收。

The configured dispatcher adds seven synthetic cases, runnable separately with `python3 -B -m unittest discover -s tests -p test_agent_dispatch.py -v`. They use only a temporary fake Python executable to check exact argv, unchanged PID after exec, exit statuses, explicit aliases, inherited or overridden markers, and rejected configuration/keys. No real model, agent CLI, session, TTY or endpoint is used. These cases do not establish external adapter availability.

The client-manager increment retains 22 original transaction/status cases in `test_codex_client.py`, `test_codex_client_status.py` and `test_codex_client_publication.py`, and adds seven explicit-layout/plan cases in `test_codex_client_layout.py`. The three original helper-only cases stay in `test_package_layout.py`; they are not copied into the client suite. Run the client increment with `python3 -B -m unittest discover -s tests -p 'test_codex_client*.py' -v`.

These fixtures use temporary layouts, synthetic package files and intercepted subprocess/process observations. They preserve archive traversal/link rejection, helper identity, active-client refusal, lock serialization, alias readback/rollback, exact old-package retirement and uncertain final-receipt behavior. Added cases distinguish configuration/planning from execution, bind the actual layout bytes, reject changed plans and compare the configured capacity threshold before download. None runs real status, codesign, package downloads, installed aliases, app access or a live update. The local first pass recorded 32 successes before removing three duplicate helper methods; retained test/setup ASTs are unchanged. A combined fixed-commit suite and any live maintenance results require their own evidence.

The explicit-layout launcher adds nine synthetic cases, runnable with `python3 -B -m unittest discover -s tests -p test_toolchain_launch.py -v`. Temporary fake doctor/helper/CLI programs verify full argv and PID replacement, inherited stdin/environment/cwd, doctor-only report/status, dual-TTY ordering, nonblocking failures and rejected layouts. Descriptors remain pipes even when the TTY predicate is mocked. No live CLI, model, session, terminal reset, signing tool or application is used; these results do not prove actual recovery.

明確布局啟動器的九項合成案例只執行暫存假 doctor／helper／CLI，核完整參數、PID、stdin／環境／cwd、doctor-only 報告與狀態、雙 TTY 順序及失敗後繼續。即使 mock TTY 判斷，所有描述符仍為管道；沒有真實 CLI、模型、會話、終端重設、簽名工具或應用操作。

The DSH adapter adds twelve **new** Node synthetic cases, run separately with `node --test tests/test_herdr_dsh.mjs` on Node 24. They use memory streams, fake child objects, mock sockets and one temporary fake SDK executable with piped input. They cover RPC parsing/limits/failures, same-session state, ready/blocked/release behavior, reporter serialization and weak completion, explicit layout/home/cwd, name-only initialize, prompt/wait and single-child shutdown. No original DSH test reuse, real SDK/profile/model or actual Herdr connection is claimed.

DSH 候選的十二項為本次新增測試，使用內存流、假 child、mock socket 與暫存假 SDK。首輪 11 項通過，最後一項先修測試的過早 EOF，再修 macOS canonical cwd 預期，定向通過；兩次失敗保留，產品原碼未因測試變更。後續組合 CI 應執行完整 Node 測試及原 Python 套件，不能把候選準備當成真實 runtime 或 CI 已通過。

## Combined suite

The combined source contains 75 Python cases and 12 Node cases. Run `python3 -B -m unittest discover -s tests -v` and `node --test tests/test_herdr_dsh.mjs`. CI keeps the four Linux/macOS × Python 3.11/3.14 jobs and adds two separate Linux/macOS Node 24 jobs. Consult the workflow result for the exact commit; fixture coverage does not establish native client, signing, provider or Herdr delivery success.

組合源碼共 75 項 Python 與 12 項 Node 案例。CI 保留 Linux／macOS × Python 3.11／3.14 四組，另設 Linux／macOS 的 Node 24 兩組。是否通過以對應提交的實際工作流程回執為準；合成案例不代表現役客戶端、簽名、模型服務或 Herdr 送達已驗收。
