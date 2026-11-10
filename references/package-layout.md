# Package helper layout / 套件輔助程式位置

`runtime_helper_path(package, entry)` in `scripts/package_layout.py` is a small library extracted unchanged from the local client-management tool. Both paths must be supplied by the caller. From the repository root:

```python
from scripts.package_layout import runtime_helper_path

# verified_package and verified_entry come from the caller's package checks.
helper = runtime_helper_path(verified_package, verified_entry)
```

It resolves the supplied paths and follows the original helper-selection rule: recognized `bin`, `codex-resources` and `CodexCLI.app/Contents/MacOS` entry directories use the package layout, including a preferred existing `codex-resources/codex-code-mode-host`. An entry in another directory uses its adjacent helper. The resolved helper must be a regular file inside the supplied package and the same file as `bin/codex-code-mode-host`. Missing paths raise the original filesystem exception; a mismatched helper raises `ValueError`.

The check does not verify package provenance, signatures, executable bytes, release versions or the entry's ownership by the package. It does not establish that the client actually loaded this helper. The caller must perform the relevant package and executable verification separately. The function reads path metadata only; it does not create files, launch processes, read private configuration or update an installation. Other processes can change paths after the observation.

The implementation uses Python's standard library and has no machine-specific path. These tests use POSIX filesystem fixtures for the existing Codex package layouts; they do not establish support for every native Codex release or platform. This extraction does not include the full client updater, doctor, launcher or their remaining tests.

`runtime_helper_path(package, entry)` 是從本機客戶端管理工具逐字抽取的檔案布局檢查函式；兩個路徑均由呼叫端明確提供。它沿原規則選取 helper，要求解析後位於指定套件內、為一般檔案，且與 `bin/codex-code-mode-host` 是同一檔案。缺檔保留原檔案系統例外；helper 不符時回報 `ValueError`。

此檢查不驗證來源、簽名、程式位元組、版本或 entry 是否隸屬套件，也不證明客戶端已載入 helper。它只讀路徑中繼資料，不寫檔、不啟動程式、不讀私人設定或更新安裝；觀測後仍可能發生路徑變更。完整 client／doctor／launcher 與其餘測試仍待後續處理。

Run only the three extracted fixture cases / 僅執行三項抽取案例：

```sh
python3 -B -m unittest discover -s tests -p test_package_layout.py -v
```

The cases retain their original assertions: reject an adjacent helper with different file identity; accept standard and app layouts; reject a preferred resource helper with different identity, then accept its symlink to the package helper. They create only temporary synthetic files and do not execute a real client.
