# robotagent2-ops

Kimi CLI 操作 `robot-agent2` 的項目 skill。

## 用途

協助 Kimi CLI 根據用戶自然語言生成正確的 `incoming/cmd_*.py` 腳本。

## 快速參考

- 項目根目錄：`D:/software package/NexArm模仿学习机械臂/NexArm模仿学习机械臂/robot-agent2`
- 啟動 agent：`python robot_agent2.py --port COM5`
- 指令隊列：`incoming/`
- 指令模板：見 `references/script-templates-reference.md`
- 指令規範：見 `docs/robot_agent2_cmds.json`

## 生成腳本約定

1. 檔名格式：`cmd_YYYYMMDD_HHMMSS_XXX_<description>.py`
2. 腳本內可直接使用 `interface` 與 `state`
3. 成功結尾輸出 `print("[Done] ...")`
4. 失敗時輸出 `print("[ERR] ...")` 並拋出異常
5. 不要硬編碼超出 `config/config.yaml` 安全限位的座標

## 常見指令

| 用戶意圖 | 生成腳本 |
|---------|---------|
| 回零位 | `interface.home(duration=2)` |
| 移動到某點 | `interface.move_to(x=..., y=..., z=..., duration=...)` |
| 相對移動 | `interface.relative_move(dx=..., dy=..., dz=..., duration=...)` |
| 單關節 | `interface.joint_move(servo_id=..., pos=..., duration=...)` |
| 畫圓 | `interface.circle(center=(...), radius=..., duration=...)` |
| 直線 | `interface.line(target=(...), duration=...)` |
| 查狀態 | `interface.get_status()` |

## 單次執行模式（推薦測試用）

測試單條指令時，使用 `--once` 讓 agent 執行一條指令後自動退出：

```bash
python robot_agent2.py --port COM5 --once --poll-interval 0.5
```

## 實戰經驗

- **已驗證環境**：Windows + COM5 + NexArm SDK，`home`、`relative_move(dx=100)`、三步連續動作（forward → down → home）均成功依序執行。
- **座標方向**：目前 `relative_move` 的 `dx` 對應機械臂基座前方（X 軸正方向），`dz` 為垂直方向。
- **執行流程**：投放腳本 → agent 掃描 → 執行 → 備份到 `incoming_history/` → 日誌寫入 `logs/`。
- **多步指令會依序執行**：`nexarm_interface.py` 的運動方法預設 `wait=True`，會根據 `duration` 自動等待，所以腳本內連續指令不會重疊。
- **安全提醒**：每次實機運動前必須確認周圍無障礙物；先執行 `home` 確認狀態再進行其他運動。
- **虛擬環境**：若移動了專案目錄，`.venv` 內的激活路徑會失效，建議刪除後重建。
- **SDK 路徑**：`config/config.yaml` 中的 `nexarm_sdk_path` 使用相對路徑 `./Nex_Arm`，專案隨倉庫一起移動時不會失效。

## 疑難排解

| 現象 | 可能原因 | 解決 |
|------|---------|------|
| 無法開啟 COM5 | 埠號錯誤或被佔用 | 檢查裝置管理員，改用 `--port COM3/COM4` |
| 腳本未被執行 | 檔名不符合 `cmd_*.py` 或時間戳順序不對 | 確認檔名以 `cmd_` 開頭且為 `.py` |
| 移動方向與預期相反 | 座標軸定義與直覺不同 | 先用小距離（如 `dx=10`）測試方向 |
| `relative_move` 沒反應 | 上一条指令仍在執行，`is_busy` 鎖住 | 等待完成或檢查 `logs/` 中的 `[ERR]` |

詳見 `references/troubleshooting-reference.md`。
