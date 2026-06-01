# S01 — Mini Coding Agent

学习目标：将 Learn Claude Code s01-s06 的核心概念落地为可运行的 Python agent。

## 架构概览

```
s01/
├── agent.py           # 主 loop（交互式 + 单次模式）
├── tools.py           # 工具定义 + handlers
├── todo.py            # 结构化 todo list 管理
├── sub_agent.py       # 子 agent 机制
├── compression.py     # 上下文压缩
├── config.py          # API 配置
└── requirements.txt
```

## 核心模块

### 1. Agent Loop（s01）

核心闭环：`while stop_reason == "tool_use"` 循环。

```
用户输入 → Claude API → tool_use? → 执行工具 → tool_result → 再次调用 → ...
                                          ↓ 不是
                                       输出结果，等待下一轮输入
```

两种模式：
- **会话模式**：多轮交互，持续对话
- **单次模式**：给定任务，agent 自动执行到完成

### 2. Tool Usage（s02）

路由层设计，loop 和工具完全解耦：

```python
# 工具定义（传给 API）
tools = [{"name": "bash", "description": "...", "input_schema": {...}}]

# 路由表（本地执行）
handlers = {"bash": run_bash}
```

新增工具只需往两个结构各加一行，loop 代码不变。

### 3. Todo Writing（s03）

结构化 todo list，防止多步任务偏离目标。

- agent 在复杂任务开始时生成 todo list
- 每完成一步更新状态（pending → in_progress → completed）
- todo list 作为 system prompt 的一部分注入，保持 agent 聚焦

### 4. Sub-agents（s04）

将探索性工作委派给子 agent，保持主 agent 上下文干净。

- 子 agent 有独立的上下文窗口
- 执行结果返回主 agent
- 适合：代码探索、信息收集、独立子任务

### 5. Context Compression（s06）

对话过长时压缩历史，保留关键信息而非简单截断。

触发条件：token 数接近模型上限时自动压缩。

## 技术决策

| 决策 | 选择 | 原因 |
|------|------|------|
| 语言 | Python | 学习生态最成熟 |
| SDK | anthropic Python SDK | 直接管理 messages list，理解底层机制 |
| 工具执行 | subprocess.run 同步 | 简单直接，先跑通 loop |
| 权限确认 | v1 不做 | 后续通过 hook 机制实现 |
| Skill System | v1 不做 | 等核心跑通再加 |

## API 配置

- Base URL: `https://api.xiaomimimo.com/anthropic`
- 模型: `mimo-v2.5-pro`（小米自研，支持 tool use）
- API Key: 在 config.py 中配置

## 运行方式

```bash
# 安装依赖
pip install -r requirements.txt

# 会话模式
python agent.py

# 单次模式
python agent.py "帮我列出当前目录的文件"
```
