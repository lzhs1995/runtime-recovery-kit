# Terminal integration / 終端接線

These are opt-in adapters around the unchanged `terminal_modes.sh` function. Keep the complete `scripts/` directory together. Source paths are resolved relative to the adapter itself, including when the checkout path contains spaces. No profile or installed command is changed automatically.

## Manual Bash command

At your own interactive shell prompt, after the affected application has returned terminal control:

```sh
bash ./scripts/codex-terminal-recover --check
bash ./scripts/codex-terminal-recover --before-launch
```

`--check` prints the scope without touching terminal modes. The default and `--before-launch` return silently unless both stdin and stdout are TTYs; otherwise they call the included protocol-reset function. The historical flag name does not start an application. Only an explicit `--shell` additionally runs `/bin/stty sane` before the reset, changing terminal attributes as well as protocol modes. Do not invoke these actions inside a running TUI or another agent's input.

## Optional Zsh prompt hook

From an interactive Zsh prompt, opt in for the current shell:

```zsh
source ./scripts/terminal_prompt_recovery.zsh
```

The hook resets modes only before a prompt and only when Zsh is interactive, stdin/stdout are TTYs and `CMUX_SURFACE_ID` is present. That marker is a scope condition inherited from the original integration, not an authenticated identity. Sourcing twice keeps one hook. The preceding command's exit status is preserved. There is no background timer or live-TUI reset loop.

Remove this hook from the current shell with:

```zsh
add-zsh-hook -d precmd _codex_toolchain_prompt_recovery
```

The package does not edit `.zshrc`, discover another shell, resume a session, or start Codex/cmux/Herdr. A user may choose a persistent shell integration separately after checking the local environment. Native Windows is outside these shell adapters' scope. Real terminal behavior depends on the emulator; the repository's tests only use pipes and temporary files.

## 繁體中文

兩個適配器只把原本固定的函式來源改成套件相對路徑；需保留完整 `scripts/` 目錄，不會自動安裝或修改 shell 設定。

手動命令的 `--check` 只印說明；預設及 `--before-launch` 僅在輸入、輸出均為 TTY 時重設原輸入協議，旗標名稱不代表會啟動程式。明確指定 `--shell` 才會額外執行 `/bin/stty sane`，因此它也改動終端屬性。只在程式已交回控制權後，於自己的 shell 提示符使用。

可選 Zsh hook 保留互動 shell、TTY、cmux 標記及提示符邊界；重複載入不重複登記，並保留前一命令退出碼。cmux 標記不是身份認證，hook 沒有背景循環，不操作其他 agent。上面的移除命令只移除目前 shell 的這一個 hook。真實終端效果尚需使用者的具體環境核驗，合成測試不代表所有客戶端或模擬器都已實測。
