# robot-agent2 架構參考

## 數據流

```
用戶自然語言
    ↓
Kimi CLI 讀取本 skill，生成 cmd_*.py
    ↓
寫入 incoming/
    ↓
robot_agent2.py 掃描並執行
    ↓
NexArmInterface → Board → ESP32 → 機械臂
    ↓
logs/ 記錄結果
```

## 核心模組

| 檔案 | 職責 |
|------|------|
| `robot_agent2.py` | 啟動器、命令列參數 |
| `src/nexarm_interface.py` | 高層運動 API、安全限位、狀態快取 |
| `src/process_incoming.py` | 文件隊列掃描、執行、歸檔、日誌 |
| `config/config.yaml` | 串口、限位、速度 |

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
