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

## 注意事項

- 腳本內直接使用 `interface` 和 `state`，無需 import
- 輸出 `[Done]` / `[ERR]` / `[PAUSE]` 以便日誌解析
- 不要寫死會超出 `config/config.yaml` 限位的座標
- 實機測試新方向時，先用 10mm 小步距確認方向再加大
