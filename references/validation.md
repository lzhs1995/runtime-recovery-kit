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
