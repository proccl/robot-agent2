# robot-agent2 腳本模板

## 檔名規範

```
cmd_YYYYMMDD_HHMMSS_XXX_description.py
```

- `XXX`：三位序號
- `description`：簡短英文描述

## 模板

### home

```python
# cmd_YYYYMMDD_HHMMSS_XXX_home.py
interface.home(duration=2)
print("[Done] home")
```

### move_to

```python
# cmd_YYYYMMDD_HHMMSS_XXX_move_to.py
interface.move_to(x=250, y=0, z=300, duration=3)
print("[Done] move_to")
```

### relative_move

```python
# cmd_YYYYMMDD_HHMMSS_XXX_relative.py
interface.relative_move(dx=0, dy=0, dz=-50, duration=1)
print("[Done] relative_move")
```

**座標方向**：`dx` 為機械臂前方（X 軸正方向），`dy` 為左側，`dz` 為上方。

### joint_move

```python
# cmd_YYYYMMDD_HHMMSS_XXX_joint.py
interface.joint_move(servo_id=1, pos=1500, duration=1)
print("[Done] joint_move")
```

### 多段指令

```python
# cmd_YYYYMMDD_HHMMSS_XXX_sequence.py
interface.home(duration=2)
interface.move_to(x=250, y=0, z=300, duration=3)
interface.relative_move(dx=0, dy=0, dz=-50, duration=1)
print("[Done] sequence")
```

由於運動方法預設 `wait=True`，以上三步會依序完成，不會重疊。

## Chat 模式生成腳本約定

當用戶使用 `--with-chat` 或投放 `.txt` 自然語言指令時，LLM 應遵循以下格式：

1. 只返回 Python 腳本本體，不要過多解釋。
2. 使用 markdown 圍欄包裹腳本：

```python
interface.relative_move(dx=100, dy=0, dz=0, duration=2)
interface.home(duration=2)
print("[Done] forward 100mm then home")
```

3. 腳本開頭不需要 `import`，直接使用 `interface` 與 `state`。
4. 每條運動指令後無需手動 `time.sleep()`，因為 `interface` 方法預設 `wait=True`。
5. 結尾必須輸出 `print("[Done] ...")`。

## 注意事項

- 腳本內直接使用 `interface` 和 `state`，無需 import
- 輸出 `[Done]` / `[ERR]` / `[PAUSE]` 以便日誌解析
- 不要寫死會超出 `config/config.yaml` 限位的座標
- 實機測試新方向時，先用 10mm 小步距確認方向再加大
- **無需手動添加蜂鳴器**：真機模式下，`robot_agent2.py` 啟動時、每條指令開始時、每條指令成功結束時會自動發送蜂鳴提示
- **無需手動等待初始化**：`robot_agent2.py` 啟動後會自動執行 `warmup()`，聽到啟動蜂鳴後即可投放指令
