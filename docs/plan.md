# Plan: 建立 robot-agent2（Python + NexArm SDK，文件隊列架構）

## 參考項目分析

`D:\Document\code\Matlab\robot-agent` 是一個 MATLAB 7R 機械臂代理系統，核心架構為：

- **文件隊列橋接**：Kimi CLI 生成 `cmd_*.m` 腳本 → 丟入 `incoming/` → MATLAB `timer` 掃描執行
- **核心類**：`Arm7R.m` 封裝 7R 運動學與高層運動 API（`home`、`move_to`、軌跡規劃等）
- **執行器**：`processIncomingCommands.m` 負責掃描 `incoming/`、排序、注入狀態、執行、日誌、錯誤歸檔
- **指令集**：`home`、`move_to`、`trajectory`（circle/line）、`joint_move`、`set_speed`、`get_status`、`plot`
- **可視化**：MATLAB Figure 動畫
- **日誌**：`diary` 輸出到 `logs/log_*.txt`

本計畫將其遷移為 **Python + NexArm 實機控制** 的版本，命名為 `robot-agent2`，並採用與原項目一致的文件隊列架構。

## 可復用的 NexArm SDK 能力

- `Board.arm_all_reset(time_ms)` — 回零位
- `Board.set_arm_coords(x, y, z, pitch, roll, claw, time_ms)` — 絕對座標移動
- `Board.arm_move_inc(dx, dy, dz, dpitch, droll, dclaw, time_ms)` — 相對座標移動
- `Board.arm_move_servo_single(servo_id, pos, time_ms)` — 單關節
- `Board.get_full_state()` — 取得當前座標與舵機脈衝
- `Board.set_buzzer(...)` / `set_oled_text(...)` — 狀態反饋

## 建議位置

`D:\software package\NexArm模仿学习机械臂\NexArm模仿学习机械臂\robot-agent2`（與 NexArm 專案放在同一倉庫內，方便引用 SDK）。

## 架構（對照原項目）

```
robot-agent2/
├── robot_agent2.py               # 一鍵啟動腳本（對照 robotagent.m），放在頂層方便執行
├── src/                          # 源代碼（對照 robot-agent/src/）
│   ├── __init__.py
│   ├── nexarm_interface.py       # 對照 Arm7R.m
│   └── process_incoming.py       # 對照 processIncomingCommands.m
├── config/                       # 配置檔案
│   └── config.yaml
├── docs/                         # 文檔（對照 robot-agent/docs/）
│   ├── README.md
│   └── robot_agent2_cmds.json    # 指令協議規範（對照 robot_agent_cmds.json）
├── tests/                        # 測試（對照 robot-agent/tests/）
│   ├── test_interface.py
│   ├── test_executor.py
│   ├── test_launcher.py
│   └── conftest.py               # mock Board fixture
├── skills/                       # Kimi CLI 項目 skill（對照 robot-agent/skills/）
│   └── robotagent2-ops/
│       ├── SKILL.md
│       └── references/
│           ├── architecture-reference.md
│           └── script-templates-reference.md
├── incoming/                     # 運行時指令隊列（.gitignore）
│   └── failed/                   # 執行失敗腳本歸檔
├── incoming_history/             # 執行過的腳本備份（.gitignore）
├── logs/                         # 日誌輸出（.gitignore）
├── README.md                     # 項目總覽
└── .gitignore
```

## 為什麼有 SDK 還要 nexarm_interface.py？

`ros_robot_controller_sdk.py` 的 `Board` 類是底層協議封裝（直接對應 ESP32 命令字節），而 `nexarm_interface.py` 對照的是 MATLAB 項目中的 `Arm7R.m`：

- **語義轉換**：把 SDK 的 `set_arm_coords`、`arm_move_inc` 等轉成 robot-agent 風格的 `move_to(x,y,z)`、`relative_move(dx,dy,dz)`。
- **安全限位**：統一工作空間、軟限位、最大速度檢查，避免每個生成腳本各自硬編碼。
- **狀態管理**：快取 `current_pose`、`current_servos`，減少反覆呼叫 `get_full_state()`。
- **可測試性**：單元測試可用 mock `NexArmInterface` 替換真實 `Board`。

這與 MATLAB 項目中「`Arm7R` 負責運動學，`processIncomingCommands` 負責執行隊列」的分層一致。

## 實施步驟（分階段，每階段結束必須通過測試）

> **調試原則**：每個 Phase 的測試若失敗，我會先自主排查並修正（檢查語法、路徑、mock 邏輯、配置載入等），直到該 Phase 的測試通過後才進入下一 Phase。若遇到需要你做決策的選項（例如座標系方向、安全限位範圍、是否跳過某項硬體測試），我會暫停並叫你。

### Phase 1：項目骨架與環境

**任務**：
1. 先把本 plan 檔案備份到 `docs/plan.md`，作為開發過程中的參考基線
2. 建立目錄結構：`src/`、`config/`、`docs/`、`tests/`、`skills/robotagent2-ops/references/`、`incoming/`、`incoming/failed/`、`incoming_history/`、`logs/`
3. 建立 `.gitignore`，排除 `incoming/`、`incoming_history/`、`logs/`、`.venv/`、`__pycache__`、`.pyc`
4. 建立虛擬環境 `.venv`，安裝 `pyserial`、`pyyaml`、`pytest`
5. 建立 `config/config.yaml`：預設 `port: COM5`、`baudrate: 1000000`、`workspace_limits`、`default_speed`、`safety_timeout`

**測試（通過後才能進 Phase 2）**：
```bash
cd "D:/software package/NexArm模仿学习机械臂/NexArm模仿学习机械臂/robot-agent2"
test -f docs/plan.md
. .venv/Scripts/activate
python -c "import yaml; cfg=yaml.safe_load(open('config/config.yaml')); print(cfg['port']); assert cfg['baudrate'] == 1000000"
pytest tests/ -k test_config --collect-only
ls src/ config/ docs/ tests/ incoming/ incoming_history/ logs/
```

### Phase 2：NexArmInterface 模組

**任務**：
1. 建立 `src/__init__.py`
2. 建立 `src/nexarm_interface.py`：
   - `class NexArmInterface` 封裝 `Board`
   - 方法：`home(duration)`、`move_to(x,y,z,duration)`、`relative_move(dx,dy,dz,duration)`、`joint_move(servo_id,pos,duration)`、`circle(center,radius,duration)`、`line(target,duration)`、`get_status()`
   - 每個方法內做安全限位檢查，超限拋 `ValueError`
   - 使用 `get_full_state()` 快取當前狀態
3. 建立 `tests/conftest.py` 提供 mock `Board` fixture
4. 建立 `tests/test_interface.py`：
   - 測試 `home()` 呼叫 `arm_all_reset`
   - 測試 `move_to()` 轉換成正確 `set_arm_coords` 參數
   - 測試 `relative_move()` 轉換成 `arm_move_inc`
   - 測試限位檢查：傳入非法座標應拋錯
   - 測試 `get_status()` 解析 `get_full_state` 回傳

**測試（通過後才能進 Phase 3）**：
```bash
cd "D:/software package/NexArm模仿学习机械臂/NexArm模仿学习机械臂/robot-agent2"
. .venv/Scripts/activate
pytest tests/test_interface.py -v
```

### Phase 3：指令執行器（文件隊列）

**任務**：
1. 建立 `src/process_incoming.py`：
   - `CommandExecutor` 類
   - `scan_incoming()` 掃描 `incoming/cmd_*.py`，按檔名時間戳排序
   - `execute_script(path)` 用 `runpy.run_path` 或 `exec` 執行腳本，globals 注入 `interface` 與 `state`
   - 成功：備份到 `incoming_history/`，刪除原檔
   - 失敗：備份到 `incoming_history/`，原檔移至 `incoming/failed/`，日誌記錄 `[ERR]` 與 traceback
   - `is_busy` 鎖：執行期間 `True`，結束後 `False`
   - 使用 Python `logging` 輸出到 `logs/robot_agent2_YYYYmmdd_HHMMSS.log`
2. 建立 `tests/test_executor.py`：
   - 測試排序邏輯
   - 測試成功執行後檔案歸檔
   - 測試失敗執行後移至 `failed/`
   - 測試 `is_busy` 鎖防止並發

**測試（通過後才能進 Phase 4）**：
```bash
cd "D:/software package/NexArm模仿学习机械臂/NexArm模仿学习机械臂/robot-agent2"
. .venv/Scripts/activate
pytest tests/test_executor.py -v
```

### Phase 4：頂層一鍵啟動器

**任務**：
1. 建立頂層 `robot_agent2.py`：
   - 解析命令列參數 `--port`、`--config`、`--dry-run`
   - 載入 `config/config.yaml`
   - 初始化 `NexArmInterface`
   - 啟動 `CommandExecutor` 主循環
   - 處理 `Ctrl+C` 優雅退出
2. 建立 `tests/test_launcher.py`：
   - 測試 `--help` 正常顯示
   - 測試 `--dry-run` 模式下不連接真實串口也能啟動循環並正確退出

**測試（通過後才能進 Phase 5）**：
```bash
cd "D:/software package/NexArm模仿学习机械臂/NexArm模仿学习机械臂/robot-agent2"
. .venv/Scripts/activate
python robot_agent2.py --help
pytest tests/test_launcher.py -v
```

### Phase 5：文檔與 Kimi CLI skill

**任務**：
1. 建立 `README.md`：Quick Start、項目結構、與 MATLAB 項目的對照表
2. 建立 `docs/README.md`：詳細指令說明
3. 建立 `docs/robot_agent2_cmds.json`：指令協議規範（JSON 格式）
4. 建立 `skills/robotagent2-ops/SKILL.md` 與 `references/`：提供 Kimi CLI 生成 `cmd_*.py` 的模板與約定

**測試（通過後才能進 Phase 6）**：
```bash
cd "D:/software package/NexArm模仿学习机械臂/NexArm模仿学习机械臂/robot-agent2"
. .venv/Scripts/activate
python -m json.tool docs/robot_agent2_cmds.json > /dev/null
python -c "import yaml; yaml.safe_load(open('README.md'))"  # 僅確認 README 存在
ls skills/robotagent2-ops/SKILL.md skills/robotagent2-ops/references/
```

### Phase 6：硬體在環測試

**任務**：
1. 確保 NexArm 已上電、周圍無障礙物
2. 啟動 agent：
   ```bash
   python robot_agent2.py --port COM5
   ```
3. 投放測試指令：
   ```bash
   cat > incoming/cmd_$(date +%Y%m%d_%H%M%S)_001_home.py << 'PYEOF'
   interface.home(duration=2)
   print("[Done] home")
   PYEOF
   ```
4. 觀察日誌，確認機械臂回零位
5. 依次測試 `move_to`、`relative_move`、`get_status`

**通過標準**：
- agent 啟動無錯誤
- `home` 指令讓機械臂回零位
- `move_to` 與 `relative_move` 移動到預期位置
- `logs/` 中正確記錄 `[Done]` / `[ERR]`

> **注意**：Phase 6 必須在前五個 Phase 全部通過後才執行，且執行前需用戶再次確認機械臂周圍安全。

## 核心指令對照

| MATLAB 項目指令 | robot-agent2 生成腳本中的調用 | NexArm SDK 對應 |
|----------------|------------------------------|-----------------|
| `home` | `interface.home(duration=2)` | `arm_all_reset(time_ms)` |
| `move_to` | `interface.move_to(x, y, z, duration=3)` | `set_arm_coords(...)` |
| `relative_move` | `interface.relative_move(dx, dy, dz, duration=2)` | `arm_move_inc(...)` |
| `joint_move` | `interface.joint_move(servo_id, pos, duration=1)` | `arm_move_servo_single(...)` |
| `trajectory/circle` | `interface.circle(center, radius, duration=5)` | 多點 `set_arm_coords` 序列 |
| `trajectory/line` | `interface.line(target, duration=4)` | 插值後多點 `set_arm_coords` |
| `set_speed` | 改變 `interface.default_speed` 或指令參數 | 改變 `time_ms` |
| `get_status` | `interface.get_status()` | `get_full_state()` |

## 依賴

- `pyserial`
- `pyyaml`
- `pytest`（開發依賴）
- NexArm SDK：`Nex_Arm/ros_robot_controller_sdk.py`（通過相對路徑或 `PYTHONPATH` 引用）

## 安全注意事項

- 所有運動指令預設加軟限位與速度上限，超出範圍回傳 `[ERR]`
- `move_to` 先讀 `get_full_state()` 確認當前姿態，再發送絕對座標
- `is_busy` 鎖防止移動期間並發執行新指令
- Phase 6 硬體測試前必須清空機械臂活動範圍，並確認已通過 Phase 1–5
