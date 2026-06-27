# robot-agent2 架構參考

## 數據流

```
用戶自然語言
    ↓
Kimi CLI 讀取本 skill，生成 cmd_*.py
    ↓
寫入 incoming/
    ↓
robot_agent2.py 啟動
    ↓
NexArmInterface.warmup()：蜂鳴器喚醒 + 讀取狀態
    ↓
掃描並執行 incoming/ 指令
    ↓
NexArmInterface → Board → ESP32 → 機械臂
    ↓
每條指令開始/結束時自動蜂鳴提示
    ↓
logs/ 記錄結果
```

## 核心模組

| 檔案 | 職責 |
|------|------|
| `robot_agent2.py` | 啟動器、命令列參數、真機啟動時調用 warmup |
| `src/nexarm_interface.py` | 高層運動 API、安全限位、狀態快取、warmup |
| `src/process_incoming.py` | 文件隊列掃描、執行、歸檔、日誌、指令蜂鳴提示 |
| `config/config.yaml` | 串口、限位、速度、warmup 配置 |

## 狀態

`interface.get_status()` 返回：

```python
{
    "x": 200,
    "y": 0,
    "z": 200,
    "pitch": 0.0,
    "roll": 0,
    "claw": 0,
    "servos": [2048, 2048, 2048, 2048, 2048, 2048]
}
```

實現細節：
- 優先調用 `board.get_full_state()`。
- 若失敗，嘗試 `board.get_arm_coords()` 並用座標構造狀態。
- 若都失敗，返回上一次成功快取的狀態 `_last_status`。
- 這保證了真機上即使 `get_full_state()` 偶爾超時，也能獲得有效座標。
