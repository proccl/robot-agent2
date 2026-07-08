# 計劃：新增 Quick Start 兼容性測試

## 背景

Issue #2 反饋 `README.md` 的 Quick Start 命令在 Windows PowerShell 中會失敗，特別是 Bash 專屬語法 `cat > incoming/cmd_... << 'PYEOF'`。PR #3 已將 Quick Start 拆分為 Windows (PowerShell) 和 Linux/macOS (Bash) 兩個區塊。

另外，README 中目前使用了絕對路徑 `D:\software package\NexArm模仿学习机械臂\robot-agent2`，這會讓其他開發者複製命令時需要手動修改，不夠通用。

## 目標

1. 修改 `README.md` Quick Start，將顯式絕對路徑改為通用佔位符（如 `<project-path>` 或 `./robot-agent2`），讓文檔對任何安裝位置都適用。
2. 在 `tests/test_docs.py` 中新增測試，驗證 `README.md` 的 Quick Start 區塊同時提供適用於 Windows PowerShell 和 Linux/macOS Bash 的正確命令。

## 推薦方案

採用靜態分析測試（無需調用外部 shell）：

1. 解析 `README.md`，定位 `## Quick Start` 區塊。
2. 提取該區塊下的程式碼塊。
3. 驗證存在兩個子區塊：
   - `### Windows (PowerShell)`
   - `### Linux / macOS (Bash)`
4. 對 PowerShell 區塊：
   - 斷言不應包含 Bash 專屬語法，例如 `<<`（here-document）或 `$(date +...)`。
   - 斷言使用 PowerShell 慣用寫法，例如 `Set-Content`、`Get-Date`、`.venv\Scripts\Activate.ps1`。
5. 對 Bash 區塊：
   - 斷言包含預期的 Bash here-document 模式 `<< 'PYEOF'` 或等效寫法。
6. 順便更新 `test_skill_files_exist`，加入 `skills/robotagent2-ops/references/hardware-reference.md` 的文件存在性檢查（該文件在 v0.0.4 新增，但目前未被測試覆蓋）。

## 選擇此方案的原因

- **針對性強**：直接抓住 Issue #2 的根因（Windows 區塊出現 Bash 語法）。
- **快速可靠**：不依賴 PowerShell 是否安裝，也不受命令行轉義問題影響。
- **易於維護**：僅做簡單的字串/區塊解析；未來若新增更多 shell 區塊也容易擴展。

## 實作步驟

1. 將本計劃備份到 `docs/plan.md`，方便團隊成員查看本次改動的規劃。
2. 修改 `README.md` Quick Start：
   - 將 `cd "D:/software package/NexArm模仿学习机械臂/robot-agent2"` 與 `cd "D:\software package\NexArm模仿学习机械臂\robot-agent2"` 改為 `cd <project-path>` 或 `./robot-agent2` 等佔位符。
   - 在 Quick Start 上方加一句說明：「請先將 `<project-path>` 替換為你的實際專案路徑」。
2. 在 `tests/test_docs.py` 中讀取 `README.md`。
3. 新增輔助函式 `_extract_quick_start_blocks(readme_text)`，返回 PowerShell 與 Bash 程式碼塊。
4. 新增 `test_quick_start_has_windows_and_bash_sections()`。
5. 新增 `test_quick_start_powershell_no_bash_syntax()`。
6. 新增 `test_quick_start_bash_has_heredoc()`。
7. 新增 `test_readme_quick_start_no_absolute_project_path()`，斷言 Quick Start 程式碼塊中不出現 `D:\software package\NexArm模仿学习机械臂\robot-agent2` 這類絕對路徑。
8. 更新 `test_skill_files_exist()`，加入 `hardware-reference.md` 的存在性斷言。
9. 執行 `pytest tests/test_docs.py -v` 驗證。

## 預計修改文件

- `README.md`
- `tests/test_docs.py`

## 驗證方式

- `pytest tests/test_docs.py -v` 全部通過。
- 若用此測試去檢查 PR #3 之前的 `README.md`（僅有 Bash 區塊），新測試應該會失敗；檢查當前已修復版本則應該通過。
