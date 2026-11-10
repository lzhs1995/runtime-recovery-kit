# 只在交互 shell 重新取得终端、即将显示提示符时复位。
# 不设后台定时器，不在正在运行的 TUI 内持续改写模式。
source "${${(%):-%x}:A:h}/terminal_modes.sh"

_codex_toolchain_prompt_recovery() {
    local codex_prompt_status=$?
    if [[ -n "${CMUX_SURFACE_ID:-}" && -o interactive && -t 0 && -t 1 ]]; then
        codex_toolchain_reset_terminal_modes
    fi
    return "$codex_prompt_status"
}

autoload -Uz add-zsh-hook
add-zsh-hook -d precmd _codex_toolchain_prompt_recovery
add-zsh-hook precmd _codex_toolchain_prompt_recovery
