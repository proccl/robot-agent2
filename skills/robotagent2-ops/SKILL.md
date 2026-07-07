# robotagent2-ops

Kimi CLI 操作 `robot-agent2` 的項目 skill。

## 用途

協助 Kimi CLI 根據用戶自然語言生成正確的 `incoming/cmd_*.py` 腳本。

## 快速參考

- 項目根目錄：`D:/software package/NexArm模仿学习机械臂/robot-agent2`
- 啟動 agent（Anaconda）：`D:/Users/HW/anaconda3/python.exe robot_agent2.py --port COM5`
- 單次測試模式：`D:/Users/HW/anaconda3/python.exe robot_agent2.py --port COM5 --once --poll-interval 0.5`
- 指令隊列：`incoming/`
- 指令模板：見 `references/script-templates-reference.md`
- 指令規範：見 `docs/robot_agent2_cmds.json`
- 硬件結構與運動學：見 `references/hardware-reference.md`
- 疑難排解：見 `references/troubleshooting-reference.md`

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

## 啟動流程與提示音

真機模式下，`robot_agent2.py` 啟動後會自動執行以下流程：

1. 連接串口 `COM5`
2. 發送蜂鳴器 → **嘀**（warmup 初始化開始）
3. 嘗試讀取機械臂狀態，最多重試 5 次
4. 日誌出現 `Warmup OK: x=..., y=..., z=...` 後進入主循環
5. 投放指令後：
   - 指令開始 → **嘀**
   - 指令成功結束 → **嘀-嘀**

聽到啟動蜂鳴後，即可投放指令，無需額外等待或手動蜂鳴。

## 單次執行模式（推薦測試用）

測試單條指令時，使用 `--once` 讓 agent 執行一條指令後自動退出：

```bash
D:/Users/HW/anaconda3/python.exe robot_agent2.py --port COM5 --once --poll-interval 0.5
```

## 實戰經驗

- **已驗證環境**：Windows + COM5 + NexArm SDK，`home`、`relative_move(dx=100)`、三步連續動作（forward → down → home）均成功依序執行。
- **真機啟動需要 warmup**：機械臂控制板上電後，ESP32 固件需要數秒初始化。`robot_agent2.py` 啟動時會自動發送蜂鳴器並嘗試讀取狀態，完成後才進入主循環。若跳過此步驟直接發送運動指令，機械臂可能不響應。
- **蜂鳴器提示音**：真機模式下聲音順序為——啟動時 **嘀**（warmup 初始化）、每條指令開始時 **嘀**、每條指令成功結束時 **嘀-嘀**。這些由系統自動處理，無需在腳本中手動添加蜂鳴器。
- **座標方向**：目前 `relative_move` 的 `dx` 對應機械臂基座前方（X 軸正方向），`dz` 為垂直方向。
- **執行流程**：投放腳本 → agent 掃描 → 執行 → 備份到 `incoming_history/` → 日誌寫入 `logs/`。
- **多步指令會依序執行**：`nexarm_interface.py` 的運動方法預設 `wait=True`，會根據 `duration` 自動等待，所以腳本內連續指令不會重疊。
- **安全提醒**：每次實機運動前必須確認周圍無障礙物；先執行 `home` 確認狀態再進行其他運動。
- **狀態讀取**：`interface.get_status()` 內部優先使用 `get_full_state()`，失敗時會自動後備到 `get_arm_coords()`。真機上若看到 `z=0` 導致限位錯誤，通常是啟動時未完成 warmup。
- **關節型號與縮放**：經實機確認，底座 θ1 為 HX-65HM，大臂 θ2 為 HX-30HM，小臂 θ3 為 HX-12H，腕部 pitch θ4 為 HX-10HM，腕部 roll θ5 為 **HX-12H**，夾爪為 HX-10HM。下位機會將各舵機脈衝統一映射到內部 0–4095 坐標，詳見 `references/hardware-reference.md`。
- **roll 縮放**：更新下位機最新代碼後，`roll` 指令值與實際角度為 **1:1**，可達 ±90°。
- **夾爪範圍**：夾爪實際機械範圍約 **-90° ~ +67.4°**；`claw` 在 -90 ~ 70 範圍內線性可控，超過 +70 後進入機械限位。
- **單關節脈衝控制**：可用 `interface.board.arm_move_servo_single(servo_id, pos, time_ms)` 直接控制，其中 `pos` 為下位機內部 0–4095 坐標。

## 疑難排解

| 現象 | 可能原因 | 解決 |
|------|---------|------|
| 無法開啟 COM5 | 埠號錯誤或被佔用 | 檢查裝置管理員，改用 `--port COM3/COM4` |
| 腳本未被執行 | 檔名不符合 `cmd_*.py` 或時間戳順序不對 | 確認檔名以 `cmd_` 開頭且為 `.py` |
| 移動方向與預期相反 | 座標軸定義與直覺不同 | 先用小距離（如 `dx=10`）測試方向 |
| `relative_move` 沒反應 | 上一条指令仍在執行，`is_busy` 鎖住 | 等待完成或檢查 `logs/` 中的 `[ERR]` |
| 啟動後機械臂不動 | 缺少 warmup 初始化；固件尚未準備好接收運動指令 | 確認 `config.yaml` 中 `warmup.enabled: true`，重啟 `robot_agent2.py` 等待蜂鳴器響後再投放指令 |
| `get_status()` 返回 `z=0` | `get_full_state()` 在真機上超時 | 系統會自動後備到 `get_arm_coords()`；若仍為 0，檢查機械臂電源與串口連接 |

詳見 `references/troubleshooting-reference.md`。
