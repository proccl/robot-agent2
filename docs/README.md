# robot-agent2 詳細文檔

## 指令協議

robot-agent2 使用文件隊列協議：任何程式或 Kimi CLI 只需將 Python 腳本寫入 `incoming/cmd_*.py`，`robot_agent2.py` 會按檔名時間排序執行。

### 腳本執行環境

執行時，腳本的 globals 中會注入：

- `interface`：`NexArmInterface` 實例
- `state`：當前機械臂狀態字典（由 `interface.get_status()` 取得）

### 指令範例

#### home

```python
interface.home(duration=2)
print("[Done] home")
```

#### move_to

```python
interface.move_to(x=250, y=0, z=300, duration=3)
print("[Done] move_to")
```

#### relative_move

```python
interface.relative_move(dx=0, dy=0, dz=-50, duration=1)
print("[Done] relative_move")
```

#### joint_move

```python
interface.joint_move(servo_id=1, pos=1500, duration=1)
print("[Done] joint_move")
```

#### circle

```python
interface.circle(center=(200, 0, 200), radius=50, duration=5)
print("[Done] circle")
```

#### line

```python
interface.line(target=(300, 0, 300), duration=4)
print("[Done] line")
```

## 配置說明

`config/config.yaml`：

- `port`: 串口埠號，例如 `COM5`
- `baudrate`: 串口波特率，預設 `1000000`
- `nexarm_sdk_path`: NexArm SDK 路徑
- `default_speed`: 預設運動時間（秒）
- `workspace_limits`: 工作空間軟限位
- `servo_limits`: 舵機脈衝限位

## 錯誤處理

- 腳本執行成功：`logs/` 中記錄 `[Done] 腳本名`，原檔備份到 `incoming_history/`
- 腳本執行失敗：`logs/` 中記錄 `[ERR]` 與 traceback，原檔移至 `incoming/failed/`，同時備份到 `incoming_history/`
