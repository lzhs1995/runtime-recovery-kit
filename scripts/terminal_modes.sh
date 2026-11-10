# bash / zsh 共用；只复位输入协议，不清除屏幕、历史或输入内容。
codex_toolchain_reset_terminal_modes() {
    printf '\033[?9l\033[?1000l\033[?1002l\033[?1003l\033[?1005l\033[?1006l\033[?1015l\033[?1016l\033[?1004l\033[?2004l\033[?25h'
    # 恢复 modifyOtherKeys 默认值，并退出残留的 Kitty 键盘协议栈。
    printf '\033[>m\033[<8u'
}
