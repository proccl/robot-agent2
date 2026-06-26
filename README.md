# robot-agent2

基於 **Python + NexArm SDK** 的機械臂文件隊列代理，對照 MATLAB 項目 `robot-agent` 的架構遷移而來。

## 項目結構

```
robot-agent2/
├── robot_agent2.py               # 一鍵啟動腳本
├── src/
│   ├── nexarm_interface.py       # 對照 Arm7R.m，封裝 NexArm SDK
│   └── process_incoming.py       # 對照 processIncomingCommands.m，文件隊列執行器
├── config/config.yaml            # 串口、速度、安全限位
├── docs/                         # 詳細文檔
├── tests/                        # pytest 測試
├── skills/robotagent2-ops/       # Kimi CLI 項目 skill
├── incoming/                     # 運行時指令隊列
├── incoming_history/             # 執行過的腳本備份
└── logs/                         # 日誌
```

## Quick Start

```bash
cd "D:/software package/NexArm模仿学习机械臂/NexArm模仿学习机械臂/robot-agent2"
. .venv/Scripts/activate

# 啟動 agent（乾跑模式測試）
python robot_agent2.py --dry-run --once --poll-interval 0.5

# 投放一條指令
cat > incoming/cmd_$(date +%Y%m%d_%H%M%S)_001_home.py << 'PYEOF'
interface.home(duration=2)
print("[Done] home")
PYEOF
```

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

## 安全

- 所有運動指令有軟限位檢查
- `is_busy` 鎖防止並發執行
- 執行硬體測試前請清空機械臂活動範圍
