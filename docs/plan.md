# 計劃：將 SJTU LLM API 集成到 robot-agent2，並支持調用項目 Skill

## 背景

用戶希望 robot-agent2 能直接調用 SJTU LLM，而且 **LLM 必須能讀取並使用項目 skill**（`robotagent2-ops`）的知識，從而生成正確的機械臂控制腳本，不再依賴外部 coding agent。

SJTU provider 已配置在：

```toml
[providers.sjtu]
type = "openai_legacy"
base_url = "https://models.sjtu.edu.cn/api/v1"
api_key = "..."
```

可用模型（已通過 API `/v1/models` 實時查詢）：`minimax`、`qwen`、`claw`、`deepseek-chat`、`deepseek-reasoner`、`minimax-m2.7`、`qwen3.6-27b`。用戶指定預設使用 `qwen3.6-27b`。

項目 skill 包含：

- `skills/robotagent2-ops/SKILL.md`：生成腳本的約定與常見指令
- `skills/robotagent2-ops/references/script-templates-reference.md`：腳本模板
- `docs/robot_agent2_cmds.json`：指令集規範
- `skills/robotagent2-ops/references/hardware-reference.md`：硬件參數與標定數據

## 目標

1. robot-agent2 能直接調用 SJTU LLM。
2. 調用 LLM 時自動注入項目 skill 內容作為上下文。
3. 支持自然語言指令：用戶說「向前移動 100mm」，agent 自動生成並執行正確的 `incoming/cmd_*.py`。

## 方案

新增三個解耦模組，並集成到文件隊列執行流程：

- `src/llm_client.py`：封裝 OpenAI 兼容 API（SJTU provider）。
- `src/skill_context.py`：讀取 project skill 文件，按章節切分，根據 query 檢索最相關 chunk。
- `src/natural_language.py`：接收自然語言，調用 LLM（帶 skill 上下文）生成 Python 腳本。
- 修改 `src/process_incoming.py`：當掃描到 `cmd_*.txt` 自然語言指令文件時，自動轉換為 Python 腳本並執行。
- 在 `src/nexarm_interface.py` 暴露 `ask_llm()` 方法，供普通腳本直接調用 LLM。

## 實作步驟

**原則：每一步開發後都必須先通過對應測試，才能進入下一步。**

### 步驟 0：備份計劃到 docs

- 將本 plan 文件複製到 `docs/plan.md`，方便團隊成員查看本次改動規劃。
- **對應測試**：`tests/test_config.py::test_plan_backup_exists` 應通過。

### 步驟 1：配置

在 `config/config.yaml` 新增：

```yaml
llm:
  provider: sjtu
  base_url: https://models.sjtu.edu.cn/api/v1
  model: qwen3.6-27b
  api_key_env: SJTU_API_KEY
  default_temperature: 0.3
  default_max_tokens: 2048
  skill_context:
    - skills/robotagent2-ops/SKILL.md
    - skills/robotagent2-ops/references/script-templates-reference.md
    - skills/robotagent2-ops/references/hardware-reference.md
    - docs/robot_agent2_cmds.json
```

API key 通過環境變量 `SJTU_API_KEY` 傳入，不寫入代碼倉庫。

**對應測試**：
- `tests/test_config.py` 新增 `test_llm_config_loads()`：驗證 `llm` 節點被正確解析，包含 `base_url`、`model`、`api_key_env`、`skill_context`。
- 運行 `pytest tests/test_config.py -v` 通過後再進下一步。

### 步驟 2：LLM 客戶端

創建 `src/llm_client.py`：

- `LLMClient` 類
- `chat(messages: list[dict]) -> str`：非流式調用
- `chat_stream(messages: list[dict]) -> Iterator[str]`：流式調用，逐字返回 assistant 內容
- 使用標準庫 `urllib` 或 `requests` 發送 POST 到 `/chat/completions`
- 處理網路錯誤與 API 錯誤

**對應測試**：
- 創建 `tests/test_llm_client.py`：
  - `test_chat_sends_correct_payload`：mock HTTP，驗證請求體包含 model、messages、temperature。
  - `test_chat_returns_assistant_content`：驗證正常響應被正確解析。
  - `test_chat_raises_on_api_error`：驗證 API 錯誤時拋出異常。
  - `test_chat_stream_yields_tokens`：mock SSE 流，驗證 `chat_stream` 正確逐字產出。
- 運行 `pytest tests/test_llm_client.py -v` 通過後再進下一步。

### 步驟 3：Skill 上下文檢索

創建 `src/skill_context.py`：

#### 切分策略

- 按 Markdown 標題層級切分，優先以二級標題 `##` 為單位，若某章節過長再細分為三級標題 `###`。
- 每個 chunk 包含：標題、內文、所屬文件路徑。
- 例如 `SKILL.md` 中「常見指令」表格會被切為一個 chunk，`hardware-reference.md` 中「夾爪開合範圍」會被切為另一個 chunk。

#### 檢索策略（第一版）

- 對每個 chunk 提取關鍵字：標題詞、內容中的技術詞彙（如 `move_to`、`relative_move`、`claw`、`roll`、`workspace_limits`）。
- 根據用戶 query 中的關鍵字，計算與各 chunk 的詞彙重疊度，返回 `top_k` 個最相關 chunk。
- 提供 `retrieve(query: str, top_k: int = 3) -> list[str]`。

#### 為什麼要檢索而不是全量注入

Skill 的設計理念就是「按需讀取」。項目 skill 包含 `SKILL.md` 和多個 reference，一次性全讀會佔用大量上下文窗口，而且會混入無關資訊。通過檢索，我們可以：
- 只把與用戶指令相關的 chunk 送給 LLM
- 保留更多上下文給對話歷史和執行反饋
- 未來更容易擴展到更強的語義檢索

#### 主流實現與未來擴展

主流 RAG/Agent 實現通常會：
- 用 **LangChain / LlamaIndex** 做文檔載入、切分、向量化和檢索；
- 用 **LangGraph / AutoGen / CrewAI** 做多步 agent loop、工具調用、記憶管理；
- 用 **向量資料庫**（Chroma、FAISS、Pinecone）做語義相似度檢索。

對於 robot-agent2 第一版，我們**不引入重型框架**，原因：
- skill 文件數量少、體量小，關鍵字檢索已足夠；
- 減少依賴，降低部署複雜度；
- 未來若任務變複雜，可平滑遷移到 LlamaIndex + LangGraph。

具體遷移路徑：
1. 第一版：簡單 Markdown 切分 + 關鍵字檢索 + 自定義重試 loop。
2. 未來：改用 `sentence-transformers` 生成 chunk embedding，存入 `FAISS` 或 `Chroma`，實現語義檢索；再用 `LangGraph` 實現 ReAct / Plan-and-Solve 循環。

**對應測試**：
- 創建 `tests/test_skill_context.py`：
  - `test_chunks_are_created_from_headings`：驗證 Markdown 文件被正確切分為多個 chunk。
  - `test_retrieve_returns_relevant_chunks`：驗證「夾爪打開」能檢索到 claw 相關 chunk。
  - `test_retrieve_limits_top_k`：驗證 `top_k=3` 只返回 3 個 chunk。
- 運行 `pytest tests/test_skill_context.py -v` 通過後再進下一步。

### 步驟 4：自然語言處理

創建 `src/natural_language.py`：

- `NaturalLanguageAgent` 類
- `generate_script(user_input: str) -> str`：
  - 先調用 `SkillContext.retrieve(user_input)` 獲取相關 skill chunk
  - 構建 system prompt（檢索到的 skill chunk + 「你是一個 robot-agent2 指令生成器...」）
  - 調用 LLMClient
  - 從響應中提取 Python 代碼塊或直接返回文本
- 提供 `write_incoming_script(content: str, description: str) -> str` 工具函數：將生成的 Python 腳本寫入 `incoming/cmd_<timestamp>_<desc>.py`。
  - 第一版可由 `NaturalLanguageAgent` 直接調用，無需 LLM 輸出 tool call。
  - 未來可升級為 OpenAI 兼容的 function calling：讓 LLM 主動輸出 `write_incoming_script` tool call，agent 再執行該工具。主流框架（LangChain、AutoGen、CrewAI、OpenAI Assistants API）都支持這種自定義工具。
- 簡單重試 loop：如果生成的腳本執行失敗，把錯誤日誌和相關 skill 片段再次送給 LLM，要求修正後重新生成（最多重試 2 次）。

**對應測試**：
- 創建 `tests/test_natural_language.py`：
  - `test_generate_script_calls_skill_retrieve`：mock SkillContext 和 LLMClient，驗證 `generate_script` 會先檢索 skill。
  - `test_generate_script_extracts_code_block`：驗證從 LLM 響應中提取 Python 代碼。
  - `test_write_incoming_script_creates_file`：驗證 `write_incoming_script` 正確創建 incoming 文件。
- 運行 `pytest tests/test_natural_language.py -v` 通過後再進下一步。

### 步驟 5：集成到指令執行流程

修改 `src/process_incoming.py`：

- 當掃描到 `cmd_*.txt` 文件時，讀取內容。
- 調用 `NaturalLanguageAgent.generate_script()` 生成 Python 代碼。
- 將生成的代碼寫入 `incoming/cmd_*_generated.py`。
- 執行生成的腳本。
- 成功後歸檔原始 `.txt` 和生成的 `.py`。

**對應測試**：
- 在 `tests/test_executor.py` 新增：
  - `test_txt_command_is_converted_and_executed`：mock NaturalLanguageAgent，驗證 `.txt` 文件被轉換為 `.py` 並執行。
  - `test_txt_command_failure_is_archived`：驗證轉換失敗時正確歸檔到 failed。
- 運行 `pytest tests/test_executor.py -v` 通過後再進下一步。

### 步驟 6：在 NexArmInterface 暴露 ask_llm

修改 `src/nexarm_interface.py`：

- 初始化時根據 config 創建 `LLMClient` 和 `SkillContext`（可選，未配置則為 None）。
- 新增 `ask_llm(prompt: str) -> str`：直接調用 LLM 並返回回答。

**對應測試**：
- 在 `tests/test_interface.py` 新增：
  - `test_ask_llm_returns_llm_response`：mock LLMClient，驗證 `interface.ask_llm()` 返回 LLM 回答。
  - `test_ask_llm_disabled_when_no_config`：驗證未配置 llm 時調用會拋出或返回友好提示。
- 運行 `pytest tests/test_interface.py -v` 通過後再進下一步。

### 步驟 7：文檔

- `README.md` 新增「LLM 與自然語言指令」小節。
- `skills/robotagent2-ops/SKILL.md` 更新常見指令表，加入 `ask_llm`。

**對應測試**：
- 在 `tests/test_docs.py` 新增：
  - `test_readme_has_llm_section`：驗證 README 包含 LLM/自然語言相關內容。
- 運行 `pytest tests/test_docs.py -v` 通過後再進下一步。

### 步驟 8：全量回歸測試

- 運行 `pytest tests/ -v`，確認 34+ 個測試全部通過。

### 步驟 9：流式交互界面（終端 CLI）

新增終端交互界面，讓用戶能直接與 LLM 對話並實時看到輸出：

- 在 `robot_agent2.py` 新增 `--interactive` 或 `--chat` 參數。
- 啟動後進入終端交互循環：
  1. 提示用戶輸入自然語言指令。
  2. 調用 `LLMClient.chat_stream()` 實時打印 LLM 回覆到終端。
  3. 如果回覆包含 Python 代碼塊，詢問用戶是否執行；若確認則寫入 incoming 並執行。
  4. 輸入 `exit` 或 `quit` 退出。
- 在 `src/chat_ui.py`（新增）中封裝交互邏輯，方便獨立測試。

**優點**：無額外依賴、跨平台、啟動快、適合開發調試。

**對應測試**：
- 創建 `tests/test_chat_ui.py`：
  - `test_chat_ui_exits_on_quit`：驗證輸入 `quit` 後循環結束。
  - `test_chat_ui_writes_script_when_confirmed`：mock 用戶輸入和 LLM 輸出，驗證確認後腳本被寫入 incoming。
- 運行 `pytest tests/test_chat_ui.py -v` 通過後，再進行全量回歸測試。

## 預計修改文件

- `config/config.yaml`
- `src/llm_client.py`（新增）
- `src/skill_context.py`（新增）
- `src/natural_language.py`（新增）
- `src/nexarm_interface.py`
- `src/process_incoming.py`
- `tests/test_config.py`
- `tests/test_llm_client.py`（新增）
- `tests/test_skill_context.py`（新增）
- `tests/test_natural_language.py`（新增）
- `tests/test_executor.py`
- `tests/test_interface.py`
- `tests/test_docs.py`
- `tests/test_chat_ui.py`（新增）
- `README.md`
- `skills/robotagent2-ops/SKILL.md`
- `src/chat_ui.py`（新增）

## 安全注意事項

- API key 通過環境變量 `SJTU_API_KEY` 傳入，不寫入 config.yaml 或代碼。
- 生成腳本後先保存到 incoming，由現有 executor 執行，保留限位檢查和日誌歸檔。
- 對 LLM 生成內容進行基本過濾，避免執行危險代碼（可選第一版暫不實現，依賴用戶審查）。


## 執行狀態

- [x] 步驟 0：計劃備份到 `docs/plan.md`
- [x] 步驟 1：`config/config.yaml` 新增 `llm` 節點，`tests/test_config.py` 新增 `test_llm_config_loads`
- [x] 步驟 2：創建 `src/llm_client.py`，新增 `tests/test_llm_client.py`
- [x] 步驟 3：創建 `src/skill_context.py`，新增 `tests/test_skill_context.py`
- [x] 步驟 4：創建 `src/natural_language.py`（類名為 `NaturalLanguagePlanner`），新增 `tests/test_natural_language.py`
- [x] 步驟 5：`src/process_incoming.py` 支持 `cmd_*.txt`，`tests/test_executor.py` 新增對應測試
- [x] 步驟 6：`src/nexarm_interface.py` 新增 `ask_llm()`，`tests/test_interface.py` 新增對應測試
- [x] 步驟 7：更新 `README.md` 與 `skills/robotagent2-ops/SKILL.md`
- [x] 步驟 8：全量回歸測試 `pytest tests/ -v` 全部通過
- [x] 步驟 9：`robot_agent2.py` 新增 `--interactive`/`--chat` 參數與 `chat_loop()`，`tests/test_launcher.py` 新增對應測試

## 備註

- 自然語言模塊類名採用 `NaturalLanguagePlanner` 而非原計劃的 `NaturalLanguageAgent`，更貼近「規劃生成腳本」的語義。
- 第一版未實現自動重試 loop 與代碼危險性過濾，後續可根據實際需求擴展。
- 未新增獨立 `src/chat_ui.py`，聊天邏輯直接內聯在 `robot_agent2.py` 中。
- 後續根據使用反饋新增 `--with-chat`：在機械臂值守模式下以 daemon 線程並行運行 chat，生成的腳本直接寫入 `incoming/` 由 executor 執行。
