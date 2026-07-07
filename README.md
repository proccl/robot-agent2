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
│   └── process_incoming.py       # 對照 processIncomingCommands.m，文件隊列執行器
├── config/config.yaml            # 串口、速度、安全限位、warmup
├── docs/                         # 詳細文檔
├── tests/                        # pytest 測試
├── skills/robotagent2-ops/       # Kimi CLI 項目 skill
├── incoming/                     # 運行時指令隊列
├── incoming_history/             # 執行過的腳本備份
└── logs/                         # 日誌
```

## Quick Start

```bash
cd "D:/software package/NexArm模仿学习机械臂/robot-agent2"
. .venv/Scripts/activate

# 啟動 agent（乾跑模式測試）
python robot_agent2.py --dry-run --once --poll-interval 0.5

# 真機模式（持續後台值守）
python robot_agent2.py --port COM5 --poll-interval 0.5

# 投放一條指令
cat > incoming/cmd_$(date +%Y%m%d_%H%M%S)_001_home.py << 'PYEOF'
interface.home(duration=2)
print("[Done] home")
PYEOF
```

## PyCharm 運行配置

項目已包含兩個運行配置：

- `robot-agent2 dry-run`：`--dry-run --once --poll-interval 0.5`
- `robot-agent2 hardware`：`--port COM5 --poll-interval 0.5`（持續值守，無 `--once`）

兩個配置均固定使用 Anaconda Python 3.12 解釋器。

## 與 MATLAB robot-agent 對照

| MATLAB 項目 | robot-agent2 |
|------------|--------------|
| `robotagent.m` | `robot_agent2.py` |
| `src/Arm7R.m` | `src/nexarm_interface.py` |
| `src/processIncomingCommands.m` | `src/process_incoming.py` |
| `incoming/cmd_*.m` | `incoming/cmd_*.py` |
| `incoming_history/` | `incoming_history/` |
| `logs/log_*.txt` | `logs/robot_agent2_*.log` |

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

- 當前版本：**v0.0.4**
- 發布頁面：https://github.com/proccl/robot-agent2/releases

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
