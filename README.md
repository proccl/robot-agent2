# robot-agent2

基於 **Python + NexArm SDK** 的機械臂文件隊列代理，對照 MATLAB 項目 `robot-agent` 的架構遷移而來。

## 項目結構

```
robot-agent2/
├── robot_agent2.py               # 一鍵啟動腳本
├── sdk/                          # NexArm Python SDK
│   ├── __init__.py
│   └── ros_robot_controller_sdk.py
├── src/
│   ├── nexarm_interface.py       # 對照 Arm7R.m，封裝 NexArm SDK
│   ├── process_incoming.py       # 對照 processIncomingCommands.m，文件隊列執行器
│   ├── llm_client.py             # OpenAI-compatible LLM 客戶端
│   ├── skill_context.py          # 項目 Skill / 參考資料檢索
│   └── natural_language.py       # 自然語言指令轉 Python 腳本
├── config/config.yaml            # 串口、速度、安全限位、warmup、LLM 配置
├── docs/                         # 詳細文檔
├── tests/                        # pytest 測試
├── skills/robotagent2-ops/       # Kimi CLI 項目 skill
├── incoming/                     # 運行時指令隊列
├── incoming_history/             # 執行過的腳本備份
└── logs/                         # 日誌
```

## Quick Start

> 請先將下方的 `<project-path>` 替換為你本機的實際專案路徑。

### Windows (PowerShell)

```powershell
cd "<project-path>"
. .venv\Scripts\Activate.ps1

# 啟動 agent（乾跑模式測試）
python robot_agent2.py --dry-run --once --poll-interval 0.5

# 真機模式（持續後台值守）
python robot_agent2.py --port COM5 --poll-interval 0.5

# 真機模式 + 同時啟動 chat 線程
python robot_agent2.py --port COM5 --poll-interval 0.5 --with-chat

# 投放一條指令
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
@"
interface.home(duration=2)
print("[Done] home")
"@ | Set-Content -Encoding UTF8 "incoming/cmd_${timestamp}_001_home.py"
```

### Linux / macOS (Bash)

```bash
cd "<project-path>"
. .venv/bin/activate

# 啟動 agent（乾跑模式測試）
python robot_agent2.py --dry-run --once --poll-interval 0.5

# 真機模式（持續後台值守）
python robot_agent2.py --port COM5 --poll-interval 0.5

# 真機模式 + 同時啟動 chat 線程
python robot_agent2.py --port COM5 --poll-interval 0.5 --with-chat

# 投放一條指令
cat > incoming/cmd_$(date +%Y%m%d_%H%M%S)_001_home.py << 'PYEOF'
interface.home(duration=2)
print("[Done] home")
PYEOF
```

## 自然語言指令

除了直接編寫 `incoming/cmd_*.py`，你也可以用自然語言投放指令：

### 方式一：投放 `.txt` 文件

agent 會自動調用 LLM 將 `.txt` 轉為 `.py` 並執行。

```powershell
# Windows (PowerShell)
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
"請將機械臂回到零位" | Set-Content -Encoding UTF8 "incoming/cmd_${timestamp}_001_home.txt"
```

```bash
# Linux / macOS (Bash)
cat > incoming/cmd_$(date +%Y%m%d_%H%M%S)_001_home.txt << 'EOF'
請將機械臂回到零位
EOF
```

### 方式二：啟動 `--chat` 純對話模式

```bash
python robot_agent2.py --chat
```

這是純 LLM 對話模式，不連接機械臂，適合調試上下文與腳本生成。

### 方式三：與機械臂值守同時運行 chat

```bash
python robot_agent2.py --port COM5 --poll-interval 0.5 --with-chat
```

這會在後台啟動一個 chat 線程。你輸入自然語言後，LLM 會生成腳本並自動放入 `incoming/`，由 executor 依序執行。

### 方式四：通過 Kimi CLI 直接控制

如果你正在使用 Kimi CLI，也可以直接告訴我動作，例如「前向 100，然後回零位」。我會生成腳本並投放至 `incoming/`，由正在運行的 agent 自動執行。

### 方式五：Python API `ask_llm()`

```python
script = interface.ask_llm("向前移動 50 mm", execute=False, save=True)
interface.ask_llm("向前移動 50 mm", execute=True, save=True)
```

### LLM 配置

在 `config/config.yaml` 中配置 provider、model、API key 環境變量：

```yaml
llm:
  provider: sjtu
  base_url: https://models.sjtu.edu.cn/api/v1
  model: qwen3.6-27b
  api_key_env: SJTU_API_KEY
  default_temperature: 0.3
  default_max_tokens: 2048
  skill_context:
    - skills/robotagent2-ops/SKILL.md
    - skills/robotagent2-ops/references/script-templates-reference.md
    - skills/robotagent2-ops/references/hardware-reference.md
    - docs/robot_agent2_cmds.json
```

運行前設置環境變量：

```powershell
$env:SJTU_API_KEY="your-api-key"
```

## PyCharm 運行配置

項目已包含三個運行配置：

- `robot-agent2 dry-run`：`--dry-run --once --poll-interval 0.5`
- `robot-agent2 hardware`：`--port COM5 --poll-interval 0.5`（持續值守，無 `--once`）
- `robot-agent2 hardware + chat`：`--port COM5 --poll-interval 0.5 --with-chat`（值守並啟動 LLM chat）

三個配置均固定使用 Anaconda Python 3.12 解釋器。

## 與 MATLAB robot-agent 對照

| MATLAB 項目 | robot-agent2 |
|------------|--------------|
| `robotagent.m` | `robot_agent2.py` |
| `src/Arm7R.m` | `src/nexarm_interface.py` |
| `src/processIncomingCommands.m` | `src/process_incoming.py` |
| `incoming/cmd_*.m` | `incoming/cmd_*.py` / `incoming/cmd_*.txt` |
| `incoming_history/` | `incoming_history/` |
| `logs/log_*.txt` | `logs/robot_agent2_*.log` |
| - | `src/llm_client.py` |
| - | `src/skill_context.py` |
| - | `src/natural_language.py` |

## 核心指令

| 指令 | 生成腳本中的調用 |
|------|-----------------|
| home | `interface.home(duration=2)` |
| move_to | `interface.move_to(x, y, z, duration=3)` |
| relative_move | `interface.relative_move(dx, dy, dz, duration=2)` |
| joint_move | `interface.joint_move(servo_id, pos, duration=1)` |
| circle | `interface.circle(center=(x,y,z), radius=r, duration=5)` |
| line | `interface.line(target=(x,y,z), duration=4)` |
| get_status | `interface.get_status()` |

## 指令約定

- 指令文件命名：`incoming/cmd_YYYYMMDD_HHMMSS_XXX_<desc>.py`
- 腳本中可直接使用 `interface`（`NexArmInterface` 實例）與 `state`（當前狀態字典）
- 指令成功結尾建議輸出 `print("[Done] ...")`
- `dx` 為前方，`dy` 為左側，`dz` 為上方
- 連續指令會按文件隊列順序執行

## 硬件初始化與反饋

- 啟動時會自動執行 `warmup()`：蜂鳴 + 多次讀取狀態，確認固件就緒
- 每條指令開始時蜂鳴 1 聲，成功結束時蜂鳴 2 聲
- `get_status()` 採用 fallback 鏈：`get_full_state()` → `get_arm_coords()` → 緩存狀態

## 安全

- 所有運動指令有軟限位檢查
- `is_busy` 鎖防止並發執行
- `safety_timeout: 0` 表示 `--once` 模式無限等待，不會因超時退出
- 執行硬件測試前請清空機械臂活動範圍

## 版本

- 當前版本：**v0.0.6**
- 發布頁面：https://github.com/proccl/robot-agent2/releases

### v0.0.6 更新內容

- **SJTU LLM 集成**
  - 新增 `src/llm_client.py`：OpenAI-compatible 標準庫客戶端，支持流式與非流式
  - 新增 `src/skill_context.py`：按 Markdown 標題切分 chunk，基於關鍵詞重疊度檢索相關 Skill
  - 新增 `src/natural_language.py`：自然語言 → Python 腳本生成與保存
  - `process_incoming.py` 支持 `incoming/cmd_*.txt`，自動轉為 `.py` 並執行
  - `robot_agent2.py` 新增 `--chat` 與 `--with-chat` 終端交互模式
  - `--with-chat` 可在機械臂值守時並行運行 chat 線程，輸入自然語言後自動生成並執行腳本
  - `NexArmInterface` 新增 `ask_llm()` 方法
  - `config/config.yaml` 新增 `llm` 節點與 `SJTU_API_KEY` 環境變量配置
  - 新增對應 pytest 測試：`test_llm_client.py`、`test_skill_context.py`、`test_natural_language.py`、`test_launcher.py` 擴展

### v0.0.5 更新內容

- **Issue #2 修復：Quick Start Windows 兼容性**
  - 將 Quick Start 拆分為 **Windows (PowerShell)** 和 **Linux / macOS (Bash)** 兩個區塊
  - 把絕對路徑改為通用佔位符 `<project-path>`
  - 新增 `tests/test_docs.py` 回歸測試，確保 PowerShell 區塊不含 Bash-only 語法
- **文檔與測試**
  - 新增 `docs/plan.md` 計劃備份
  - `test_skill_files_exist` 加入 `hardware-reference.md` 存在性檢查

### v0.0.4 更新內容

- **硬件標定**
  - 確認腕部 roll（θ5）舵機型號為 **HX-12H**（非 HX-10HM）
  - 確認下位機將各舵機脈衝統一映射到內部 0–4095 坐標
  - 更新下位機最新代碼後，`roll` 指令值與實際角度達到 **1:1**
  - 測量底座 θ1 轉動區間：**-158.3° ~ +160.1°**
  - 驗證 roll 可達 **±90°**
  - 測量夾爪開合範圍：**-90.0° ~ +67.4°**，`claw > 70` 後進入機械限位
- **文檔與 Skill**
  - 更新 `skills/robotagent2-ops/references/hardware-reference.md`
  - 更新 `skills/robotagent2-ops/SKILL.md` 實戰經驗

### v0.0.3 更新內容

- 初始項目結構與基本運動指令
- 文件隊列執行器 `process_incoming.py`
- `nexarm_interface.py` 高層運動 API
- pytest 測試與 PyCharm 運行配置
