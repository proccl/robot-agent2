# AGENTS.md

> 本文件面向 AI 編碼代理。若你此前不了解 `robot-agent2` 項目，請先閱讀本文件再修改代碼。

## 項目概述

`robot-agent2` 是一個基於 **Python + NexArm SDK** 的機械臂文件隊列代理，對照 MATLAB 項目 `robot-agent` 的架構遷移而來。

核心運作方式：任何程式或 Kimi CLI 將 Python 腳本寫入 `incoming/cmd_*.py`，`robot_agent2.py` 會按檔名時間排序掃描、執行、記錄日誌並歸檔。

數據流：

```
用戶自然語言 / 外部程式
    ↓
生成 incoming/cmd_YYYYMMDD_HHMMSS_XXX_<description>.py
    ↓
robot_agent2.py（CommandExecutor 掃描隊列）
    ↓
NexArmInterface（高層運動 API + 安全限位）
    ↓
NexArm SDK Board 類 → ESP32 → 機械臂
    ↓
logs/ 記錄 [Done] / [ERR]
```

## 技術棧與運行環境

- **語言**：Python 3.12.3
- **Python 環境**：可直接使用 Anaconda 基礎解釋器，或項目自帶的 `.venv/`（使用 Anaconda 建立，`include-system-site-packages = false`）
- **核心依賴**：
  - `pyserial`：串口通訊
  - `pyyaml`：載入 `config/config.yaml`
  - `pytest`：單元測試與整合測試
- **SDK**：`Nex_Arm/ros_robot_controller_sdk.py`（作為標準 Python package `Nex_Arm` 導入）
- **硬體**：NexArm 機械臂，通過 USB 串口（預設 `COM5`，波特率 `1000000`）連接 ESP32 控制板

## 項目結構

```
robot-agent2/
├── robot_agent2.py               # 一鍵啟動腳本，處理命令列參數與主循環
├── src/
│   ├── __init__.py
│   ├── nexarm_interface.py       # 對照 MATLAB Arm7R.m，封裝 NexArm SDK 高層 API
│   └── process_incoming.py       # 對照 MATLAB processIncomingCommands.m，文件隊列執行器
├── config/
│   └── config.yaml               # 串口、速度、安全限位配置
├── tests/
│   ├── conftest.py               # MockBoard 與通用 fixture
│   ├── test_config.py            # 配置與目錄結構測試
│   ├── test_docs.py              # 文檔與 skill 文件存在性測試
│   ├── test_executor.py          # CommandExecutor 測試
│   ├── test_interface.py         # NexArmInterface 測試
│   └── test_launcher.py          # robot_agent2.py 啟動測試
├── docs/
│   ├── README.md                 # 指令協議詳細說明
│   ├── plan.md                   # 開發計畫基線
│   └── robot_agent2_cmds.json    # 指令協議規範（JSON）
├── skills/robotagent2-ops/       # Kimi CLI 項目 skill
│   ├── SKILL.md
│   └── references/
│       ├── architecture-reference.md
│       ├── script-templates-reference.md
│       └── troubleshooting-reference.md
├── Nex_Arm/                      # NexArm SDK（C++ / Python）
│   ├── __init__.py
│   └── ros_robot_controller_sdk.py
├── incoming/                     # 運行時指令隊列（.gitignore）
│   └── failed/                   # 執行失敗腳本歸檔
├── incoming_history/             # 執行過的腳本備份（.gitignore）
└── logs/                         # 日誌輸出（.gitignore）
```

## 核心模組說明

### `robot_agent2.py`

啟動器，負責：

- 解析命令列參數（`--config`、`--port`、`--dry-run`、`--once`、`--poll-interval` 等）
- 載入 `config/config.yaml`
- 初始化 `NexArmInterface`（真實硬體或乾跑模式）
- 建立 `CommandExecutor` 並進入主循環
- 處理 `Ctrl+C` 優雅退出

常用命令：

```bash
# 真實硬體模式（需確認 COM 埠正確）
python robot_agent2.py --port COM5

# 乾跑模式：不連接串口，使用 DryRunBoard 模擬
python robot_agent2.py --dry-run --once --poll-interval 0.5
```

### `src/nexarm_interface.py`

`NexArmInterface` 將底層 `Board` 協議映射為 robot-agent 風格的高層運動 API，並提供安全限位。

主要方法：

| 方法 | 對應 SDK 調用 | 說明 |
|------|--------------|------|
| `home(duration)` | `arm_all_reset(time_ms)` | 回零位 |
| `move_to(x, y, z, ...)` | `set_arm_coords(...)` | 絕對座標移動 |
| `relative_move(dx, dy, dz, ...)` | `arm_move_inc(...)` | 相對座標移動 |
| `joint_move(servo_id, pos, ...)` | `arm_move_servo_single(...)` | 單關節移動 |
| `circle(center, radius, ...)` | 多點 `set_arm_coords` 序列 | XY 平面畫圓 |
| `line(target, ...)` | 插值後多點 `set_arm_coords` | 直線插值移動 |
| `get_status()` | `get_full_state()` | 取得當前位姿與舵機脈衝 |

安全機制：

- `SafetyError`（繼承 `ValueError`）：目標超出範圍時拋出
- 工作空間軟限位：`workspace_limits`（`x`/`y`/`z`/`pitch`/`roll`/`claw`）
- 舵機脈衝限位：`servo_limits.pulse_min` / `pulse_max`（預設 0~4095）
- 所有運動方法預設 `wait=True`，會根據 `duration` 阻塞等待，避免連續指令堆疊

### `src/process_incoming.py`

`CommandExecutor` 文件隊列執行器：

- `scan()`：掃描 `incoming/cmd_*.py` 並按檔名升冪排序
- `execute_script(path)`：用 `exec()` 執行腳本，globals 注入 `interface` 與 `state`
- 成功：原檔刪除，備份到 `incoming_history/`，日誌記錄 `[Done]`
- 失敗：原檔移至 `incoming/failed/`，備份到 `incoming_history/`，日誌記錄 `[ERR]` 與 traceback
- `is_busy` 鎖：執行期間為 `True`，防止並發執行新指令
- 日誌：`logs/robot_agent2_YYYYMMDD_HHMMSS.log`，每天運行時建立新檔案

## 配置文件

`config/config.yaml`：

```yaml
port: COM5
baudrate: 1000000
timeout: 0.1
nexarm_sdk_path: "./Nex_Arm"       # 已棄用，現在使用標準 package import（保留向後兼容）
default_speed: 1.5                 # 預設運動時間（秒）
workspace_limits:                  # 工作空間軟限位
  x: { min: 0, max: 350 }
  y: { min: -250, max: 250 }
  z: { min: 50, max: 450 }
  pitch: { min: -90, max: 90 }
  roll: { min: -90, max: 90 }
  claw: { min: -90, max: 90 }
servo_limits:
  pulse_min: 0
  pulse_max: 4095
safety_timeout: 10                 # --once 等待超時（秒）
log_level: INFO
```

**注意**：`nexarm_sdk_path` 已棄用。`robot_agent2.py` 現直接使用 `from Nex_Arm.ros_robot_controller_sdk import Board` 導入，無需動態修改 `sys.path`。

## 構建與測試命令

### 使用 Anaconda 直接運行（推薦）

項目已配置使用 Anaconda 基礎解釋器：

```bash
cd "D:/software package/NexArm模仿学习机械臂/robot-agent2"
D:/Users/HW/anaconda3/python.exe -m pytest tests/ -v
D:/Users/HW/anaconda3/python.exe robot_agent2.py --dry-run --once --poll-interval 0.5
```

### 使用項目虛擬環境

```bash
cd "D:/software package/NexArm模仿学习机械臂/NexArm模仿学习机械臂/robot-agent2"
. .venv/Scripts/activate
```

### 運行全部測試

```bash
pytest tests/ -v
```

### 啟動 agent（乾跑測試）

```bash
python robot_agent2.py --dry-run --once --poll-interval 0.5
```

### 投放一條測試指令

```bash
cat > incoming/cmd_$(date +%Y%m%d_%H%M%S)_001_home.py << 'PYEOF'
interface.home(duration=2)
print("[Done] home")
PYEOF
```

## 指令腳本約定

投放至 `incoming/` 的腳本需遵循以下約定：

1. **檔名格式**：`cmd_YYYYMMDD_HHMMSS_XXX_<description>.py`
2. **執行環境**：無需 import，`globals` 已注入 `interface`（`NexArmInterface` 實例）與 `state`（當前狀態字典）
3. **成功標記**：腳本結尾輸出 `print("[Done] ...")`
4. **失敗處理**：拋出異常會被 `CommandExecutor` 捕獲，原檔移至 `incoming/failed/`
5. **座標方向**：
   - `dx`：X 軸正方向（機械臂前方）
   - `dy`：Y 軸正方向（左側）
   - `dz`：Z 軸正方向（上方）

常用指令範例：

```python
interface.home(duration=2)
interface.move_to(x=250, y=0, z=300, duration=3)
interface.relative_move(dx=0, dy=0, dz=-50, duration=1)
interface.joint_move(servo_id=1, pos=1500, duration=1)
interface.circle(center=(200, 0, 200), radius=50, duration=5)
interface.line(target=(300, 0, 300), duration=4)
status = interface.get_status()
```

## 代碼風格指南

- **語言**：源代碼注釋與文檔使用繁體中文；變數名、函數名使用英文小寫 + 下劃線（snake_case）
- **導入順序**：標準庫 → 第三方庫 → 本項目模組，每組之間空一行
- **縮排**：4 個空格
- **字符串**：優先使用雙引號，但保持一致即可
- **路徑**：跨平台使用 `pathlib.Path`；配置中的路徑使用正斜槓
- **時間單位**：
  - 配置與高層 API 使用**秒**（`duration`）
  - 底層 SDK 使用**毫秒**（`time_ms`）
  - `NexArmInterface._duration()` 負責秒轉毫秒
- **異常**：安全限位使用自訂的 `SafetyError`（繼承 `ValueError`），測試中可直接 assert `SafetyError`

## 測試策略

項目使用 `pytest`，配置在 `pytest.ini`：

```ini
[pytest]
pythonpath = .
testpaths = tests
```

測試分類：

| 測試文件 | 測試範圍 |
|---------|---------|
| `test_config.py` | 配置可載入、目錄結構完整、plan 備份存在 |
| `test_docs.py` | JSON 協議有效、README 與 skill 文件存在 |
| `test_interface.py` | `home`、`move_to`、`relative_move`、`joint_move`、軌跡、限位、等待邏輯 |
| `test_executor.py` | 隊列排序、成功歸檔、失敗歸檔、`is_busy` 鎖 |
| `test_launcher.py` | `--help`、乾跑 `--once` 模式整體流程 |

測試使用 `tests/conftest.py` 中的 `MockBoard` 模擬 SDK，無需真實硬體即可運行。

運行全部測試通過是提交前的基本要求。

## 安全注意事項

- **硬體測試前**：必須清空機械臂活動範圍，確認周圍無障礙物
- **並發控制**：`CommandExecutor` 使用 `is_busy` 鎖，移動期間不會執行新指令
- **軟限位**：所有絕對運動與軌跡點都會檢查 `workspace_limits`，超出範圍拋 `SafetyError`
- **相對運動**：`relative_move` 目前僅由 SDK 處理邊界，未在 interface 層預先計算目標限位
- **日誌審查**：實機運動後檢查 `logs/robot_agent2_*.log` 中的 `[Done]` / `[ERR]` 標記
- **Python 環境**：PyCharm Run Configuration 已固定使用 `D:\Users\HW\anaconda3\python.exe`；若改用 `.venv`，請相應調整運行配置中的解釋器路徑

## 開發注意事項

- 修改 `Nex_Arm/ros_robot_controller_sdk.py` 時需極度謹慎，該文件直接控制硬體通訊協議
- 新增高層 API 時，應同步更新 `docs/robot_agent2_cmds.json`、`docs/README.md`、`skills/robotagent2-ops/` 與對應測試
- 新增測試時優先使用 `MockBoard`，避免在無硬體環境下引入失敗
- 文件隊列腳本使用 `exec()` 執行，切勿將不受信任的內容寫入 `incoming/`

## 與 MATLAB 項目對照

| MATLAB 項目 | robot-agent2 |
|------------|--------------|
| `robotagent.m` | `robot_agent2.py` |
| `src/Arm7R.m` | `src/nexarm_interface.py` |
| `src/processIncomingCommands.m` | `src/process_incoming.py` |
| `incoming/cmd_*.m` | `incoming/cmd_*.py` |
| `incoming_history/` | `incoming_history/` |
| `logs/log_*.txt` | `logs/robot_agent2_*.log` |
