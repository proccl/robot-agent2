# 重構：將 Python SDK 從 Nex_Arm 移到 sdk/

## 背景與目標

用戶希望：
1. 新建 `sdk/` 文件夾作為機械臂 Python SDK 的專屬位置。
2. 將實際使用的 `ros_robot_controller_sdk.py` 移到 `sdk/`。
3. 刪除整個 `Nex_Arm/` 目錄（包含 C++ 固件、頭文件、文檔等）。
4. 更新所有引用與文檔，並通過測試。

## 當前狀態

- `Nex_Arm/` 目錄包含 61 個文件，其中只有 `ros_robot_controller_sdk.py` 被 `robot_agent2.py` 使用。
- `robot_agent2.py` 使用 `from Nex_Arm.ros_robot_controller_sdk import Board`。
- `config/config.yaml` 中有 `nexarm_sdk_path: "./Nex_Arm"`（已棄用）。
- `AGENTS.md`、`docs/plan.md`、skill 文件中多處提到 `Nex_Arm/`。
- 現有測試不檢查 `Nex_Arm/` 目錄存在性，只檢查 `nexarm_sdk_path` 鍵存在。

## 修改方案

### 1. 備份本計畫到 `docs/`

將本 plan 文件複製到 `docs/plan_sdk_refactor.md`，作為重構前的備份與決策記錄。

### 2. 創建 `sdk/` 並移入 SDK

```bash
mkdir sdk
mv Nex_Arm/ros_robot_controller_sdk.py sdk/ros_robot_controller_sdk.py
```

並新增 `sdk/__init__.py`，使 `sdk` 成為標準 Python package。

### 3. 刪除 `Nex_Arm/`

```bash
rm -rf Nex_Arm
```

此操作會永久刪除 C++ 固件源碼。用戶已確認直接刪除，無需備份。

### 4. 更新 `robot_agent2.py`

將 import 改為：

```python
from sdk.ros_robot_controller_sdk import Board
```

`DryRunBoard` 保持不變，因其模擬 `Board` 行為而非依賴 import 路徑。

### 5. 更新 `config/config.yaml`

保留 `nexarm_sdk_path` 鍵以通過 `test_config.py`，但更新其值與註釋：

```yaml
nexarm_sdk_path: "./sdk"  # 已棄用，現在使用標準 package import（保留向後兼容）
```

### 6. 更新文檔與 skill

- `AGENTS.md`：
  - 更新技術棧中 SDK 路徑描述
  - 更新項目結構樹（移除 `Nex_Arm/`，新增 `sdk/`）
  - 更新配置文件範例與註釋
  - 更新開發注意事項中的文件路徑
- `docs/plan.md`：更新 NexArm SDK 路徑引用
- `skills/robotagent2-ops/SKILL.md` 與 references：將 `Nex_Arm` 改為 `sdk`

### 7. 測試

用戶已連接真機，測試順序如下：

1. **單元測試**：`pytest tests/ -v`，預期 30 個測試全部通過。
2. **乾跑驗證**：
   ```bash
   python robot_agent2.py --dry-run --once --poll-interval 0.5
   ```
   投放一條指令確認流程正常。
3. **真機驗證**：
   - 啟動 `robot_agent2.py --port COM5 --once --poll-interval 0.5`
   - 先投放 `interface.relative_move(dx=100, dy=0, dz=0, duration=2)`，確認前向運動正常
   - 再投放 `interface.home(duration=2)`，確認能回零位
   - 若真機驗證失敗，立即回滾到上一個 git commit（`v0.0.1`）

## 測試失敗處理原則

- 單元測試或乾跑失敗時，先自行調試修復。
- 若遇到會影響設計方向、數據刪除範圍、或真機安全的決策，暫停並詢問用戶。
- 真機驗證失敗且無法快速定位時，可回滾到 `v0.0.1` tag 並詢問用戶是否繼續。

## 風險與注意事項

- **數據丟失**：`Nex_Arm/` 下的 C++ 固件將被永久刪除。用戶已確認無需備份。
- **Import 錯誤**：若漏改任何 `Nex_Arm` 引用，運行時會報 `ModuleNotFoundError`。Grep 全項目檢查後再測試。
- **Git 追蹤**：`Nex_Arm/` 之前已被 git 追蹤，刪除後會在下次提交中體現為文件刪除。

## 預期結果

- 項目結構更清晰：`sdk/` 只包含實際使用的 Python SDK。
- `robot_agent2.py` 從 `sdk.ros_robot_controller_sdk` 導入 `Board`。
- 所有測試通過，乾跑與真機模式正常運作。
