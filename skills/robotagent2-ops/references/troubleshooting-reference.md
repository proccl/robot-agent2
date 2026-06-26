# robot-agent2 疑難排解參考

## 連線問題

### 無法開啟串口

```
serial.serialutil.SerialException: could not open port 'COM5'
```

**排查**：
1. 確認 ESP32 已連接電腦
2. 在裝置管理員查看正確埠號
3. 嘗試 `--port COM3`、`--port COM4` 等
4. 確認沒有其他程式（如 Arduino IDE、串口助手）佔用該埠

## 指令未執行

### 腳本丟入 incoming/ 但沒反應

**可能原因**：
- 檔名不符合 `cmd_*.py`
- `is_busy` 為 True，上一條指令還在執行
- 腳本內語法錯誤，被歸檔到 `incoming/failed/`

**排查**：
```bash
ls incoming/
ls incoming/failed/
cat logs/robot_agent2_*.log
```

## 運動問題

### 腳本內多條指令同時動

**原因**：SDK 發送命令後立即返回，不會等機械臂走完。如果 interface 沒有等待，連續指令會快速堆疊。

**解決**：`nexarm_interface.py` 已預設 `wait=True`，會根據 `duration` 自動等待。若需要連續發送（例如自訂軌跡點），可傳 `wait=False`。

### 移動方向與預期不同

robot-agent2 目前使用世界座標系：

- `dx`：X 軸正方向（機械臂前方）
- `dy`：Y 軸正方向（左側）
- `dz`：Z 軸正方向（上方）

**建議**：先用小位移測試方向，例如 `relative_move(dx=10, dy=0, dz=0, duration=1)`。

### 指令被安全限位拒絕

如果看到 `[ERR]` 或 `SafetyError`，檢查 `config/config.yaml` 中的 `workspace_limits` 與 `servo_limits`。

## 測試問題

### pytest 找不到 `src` 模組

確保 `pytest.ini` 存在且包含：

```ini
[pytest]
pythonpath = .
```

## 日誌解讀

| 標記 | 含義 |
|------|------|
| `[Done]` | 腳本執行成功 |
| `[ERR]` | 腳本執行失敗，後面會附 traceback |
| `[PAUSE]` | 軌跡中斷，機械臂停在最後有效位置 |
