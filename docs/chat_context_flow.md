# `--with-chat` 上下文組裝流程

本文檔描述 `robot_agent2.py --with-chat` 模式下，用戶自然語言指令如何與項目 Skill 結合，最終組裝成發送給 LLM 的 `messages` 列表。

## 入口函數

主要入口為 `robot_agent2.py` 中的 `chat_loop_for_arm(planner: NaturalLanguagePlanner)`。

該函數在後台 daemon 線程中運行，與主線程的 `CommandExecutor` 並行工作。

```
用戶輸入（自然語言）
    │
    ▼
chat_loop_for_arm()
    │
    ├── 載入 SkillContext
    ├── 檢索通用上下文（system prompt）
    ├── 檢索與用戶輸入相關的 Skill chunk
    ├── 組裝 messages
    ├── 調用 LLMClient.chat_stream(messages)
    ├── 接收 LLM 回覆
    ├── 提取 Python 腳本
    └── 保存到 incoming/，等待 executor 執行
```

## 上下文組裝步驟

### 1. System Prompt 初始化

啟動 `chat_loop_for_arm()` 時，首先從 `SkillContext` 檢索與機械臂通用操作相關的內容：

```python
base_chunks = skill_context.retrieve(
    "NexArm robot arm general operation",
    top_k=3
)
```

`SkillContext` 會：
1. 將 `SKILL.md`、`script-templates-reference.md`、`hardware-reference.md`、`robot_agent2_cmds.json` 等文件按 Markdown 標題切分為 chunk。
2. 對每個 chunk 提取中英文關鍵詞。
3. 對查詢語句「NexArm robot arm general operation」也提取關鍵詞。
4. 計算關鍵詞重疊數量，返回最相關的 3 個 chunk。

然後構建 system message：

```text
You are an assistant for the NexArm 6-DOF robot arm.
Convert the user's request into a Python script using the `interface` object.
Return only the Python script in a markdown fence.
Keep explanations minimal.

Project context:
# SKILL
Source: skills/robotagent2-ops/SKILL.md
...

# 常見指令
Source: skills/robotagent2-ops/SKILL.md
...
```

該 system message 會作為 `messages[0]` 一直保留。

### 2. 用戶輸入與動態檢索

每當用戶輸入一句話，例如「向前 100mm 然後回家」，系統會再次檢索：

```python
chunks = skill_context.retrieve(user_input, top_k=2)
```

這次檢索會根據具體指令返回最相關的 chunk，例如「relative_move」、「home」等相關段落。

### 3. User Message 組裝

如果檢索到相關 chunk，會把它們附加到用戶輸入之前：

```text
Relevant project context:
# 常見指令
Source: skills/robotagent2-ops/SKILL.md
...

User request: 向前 100mm 然後回家
```

如果沒有命中相關 chunk，則直接使用用戶輸入作為 user message。

### 4. 發送給 LLM 的 messages 結構

第一次對話時：

```json
[
  {
    "role": "system",
    "content": "You are an assistant for the NexArm 6-DOF robot arm. ..."
  },
  {
    "role": "user",
    "content": "Relevant project context: ...\n\nUser request: 向前 100mm 然後回家"
  }
]
```

多輪對話後：

```json
[
  {
    "role": "system",
    "content": "You are an assistant for the NexArm 6-DOF robot arm. ..."
  },
  {
    "role": "user",
    "content": "Relevant project context: ...\n\nUser request: 向前 100mm 然後回家"
  },
  {
    "role": "assistant",
    "content": "```python\ninterface.relative_move(dx=100, dy=0, dz=0, duration=2)\ninterface.home(duration=2)\nprint('[Done] forward 100mm then home')\n```"
  },
  {
    "role": "user",
    "content": "User request: 再向上 50mm"
  }
]
```

### 5. 上下文長度控制

為避免對話過長導致 token 超限，當 `messages` 總數超過 12 條時：

```python
if len(messages) > 12:
    messages = [messages[0]] + messages[-10:]
```

即：
- 始終保留 `messages[0]`（system prompt）。
- 只保留最近 10 條對話歷史。
- 丟棄更早的對話。

## 從 LLM 回覆到機械臂執行

`chat_loop_for_arm()` 收到 LLM 回覆後：

1. 將回覆內容追加到 `messages` 中（作為 assistant message）。
2. 調用 `NaturalLanguagePlanner._clean_script(response)` 提取 markdown 圍欄內的 Python 代碼。
3. 如果提取到腳本，調用 `planner.save_script(user_input, script)` 保存到 `incoming/`。
4. `CommandExecutor` 主線程掃描到該腳本後執行。

## 涉及的關鍵類與文件

| 組件 | 文件 | 職責 |
|-----|------|------|
| `chat_loop_for_arm()` | `robot_agent2.py` | chat 線程主循環，組裝上下文並調用 LLM |
| `SkillContext` | `src/skill_context.py` | 載入 skill 文件、切分 chunk、關鍵詞檢索 |
| `NaturalLanguagePlanner` | `src/natural_language.py` | 調用 LLM、清理腳本、保存到 incoming |
| `LLMClient` | `src/llm_client.py` | 發送 HTTP 請求到 SJTU LLM API |
| `CommandExecutor` | `src/process_incoming.py` | 掃描並執行 incoming/ 中的腳本 |

## 注意事項

- System prompt 中的 project context 是啟動時固定檢索的，不會隨每輪對話改變。
- 每輪用戶輸入會動態檢索相關 chunk，確保 LLM 獲得與當前指令最相關的參考資料。
- 檢索策略是關鍵詞重疊，不是語義向量檢索，因此對於同義詞可能不夠魯棒。
- 由於 `chat_loop_for_arm()` 運行在 daemon 線程中，當主程序退出時，chat 線程也會被終止。
