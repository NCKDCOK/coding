## Problem Statement

s01 原型用 ~300 行跑通了核心 agent 循环，但架构不可扩展：裸 dict 工具、无类型注解、inline 定义、context 压缩和 sub-agent 混在主循环里。需要一个工程化的 harness 架构，将独立能力（LLM 调用、工具执行、记忆管理、上下文组装）通过接口契约组合成完整的 agent 系统，为后续扩展（后台任务、定时调度、权限等）打下基础。

## Solution

构建 coding-cli v1：一个同步的 harness 架构 coding agent。loop.py 是极薄编排层（只调人不干活），所有模块通过接口通信。核心循环 `think -> act -> observe`，支持 CLI 交互（一次性 / pipe / REPL 三种模式）。

## User Stories

1. As a developer, I want to run `python main.py "fix the bug in auth.py"` and get a one-shot agent response, so that I can use the agent in scripts and CI
2. As a developer, I want to pipe input via `echo "explain this code" | python main.py` and get output, so that I can compose the agent with other Unix tools
3. As a developer, I want an interactive REPL when I run `python main.py` with no arguments, so that I can have a multi-turn conversation with the agent
4. As a developer, I want the agent to execute shell commands on my behalf, so that it can run tests, install dependencies, and inspect system state
5. As a developer, I want the agent to read files with line numbers, so that it can understand and reference specific parts of my codebase
6. As a developer, I want the agent to write new files, so that it can create boilerplate, configs, and new modules
7. As a developer, I want the agent to edit existing files with surgical string replacement, so that it can make precise code changes without rewriting entire files
8. As a developer, I want the agent to manage a todo list, so that it can track multi-step tasks and show me progress
9. As a developer, I want tool failures to be fed back to the LLM as error messages (not exceptions), so that the agent can self-correct and retry
10. As a developer, I want the agent to handle multiple tool calls in a single assistant turn, so that the model can parallelize independent operations
11. As a developer, I want prompt caching to work (static system prompt with cache_control), so that API costs are reduced on repeated calls
12. As a developer, I want session logs in JSONL format, so that I can audit what happened in each session
13. As a developer, I want the agent to gracefully handle Ctrl+C, so that I can interrupt without corrupting state
14. As a developer, I want a configurable max iterations limit, so that the agent cannot run in an infinite loop
15. As a developer, I want todo state to persist across agent turns within a session, so that multi-step tasks survive tool execution cycles
16. As a developer, I want the todo list injected into context each round without polluting history, so that the model always sees current state without bloating the conversation
17. As a developer, I want the agent to detect and handle `max_tokens` truncation cleanly, so that partial output is surfaced rather than silently lost
18. As a developer, I want orphaned tool_use blocks (from interrupted turns) to be patched with error results, so that session history is always valid for replay
19. As a developer, I want LLM errors (auth, bad request, transient) to be handled with clear domain exceptions, so that the loop can make informed retry/terminate decisions
20. As a developer, I want tool schemas auto-generated from Pydantic models, so that I do not hand-write JSON Schema for each tool
21. As a developer, I want shell command output truncated with head+tail preservation (not naive chop), so that error messages at the end of output are not lost
22. As a developer, I want shell commands to run in isolated process groups, so that timeout kills all spawned subprocesses, not just the direct child
23. As a developer, I want file edits to use atomic writes (temp file + os.replace), so that a crash mid-write does not corrupt my source files
24. As a developer, I want edit_file to report match count and suggest whitespace issues on failure, so that the LLM can fix its own edit attempts
25. As a developer, I want the agent to warn me when max iterations are hit (not silently stop), so that I know the answer may be incomplete
26. As a developer, I want configuration in TOML with a separate example file, so that I can version-control my config without leaking secrets
27. As a developer, I want system prompt in a standalone markdown file, so that I can iterate on prompts without touching code

## Implementation Decisions

### 1. types.py — 核心数据结构

- ContentBlock 是唯一的内容原子，使用 Pydantic discriminated union（`type` 字段区分）：TextBlock / ToolUseBlock / ToolResultBlock
- Message.content 统一 `list[ContentBlock]`（不提供 str 快捷路径，避免下游序列化分支）
- ToolCall = ToolUseBlock，ToolResult = ToolResultBlock（领域别名，不写第二套定义）
- Message(role, content)：role="system" 仅作统一存储，序列化时由 llm.py 提取为顶层 system 参数；tool_result 走 role="user" 的 message
- LLMResponse(content, stop_reason, usage)：stop_reason 限 4 个值（end_turn / tool_use / max_tokens / stop_sequence）
- Usage 包含 cache_creation_input_tokens / cache_read_input_tokens（计费与统计独立记账）
- 不做业务校验、不做格式转换，结构对齐 Anthropic Messages API

### 2. memory.py — 短期记忆

- 纯内存 `list[Message]`，v1 不落盘
- `as_messages()` 返回 `list[Message]`，序列化到 API 格式收口在 llm.py
- 接口：`add(message)` / `clear()` / `all()` / `as_messages()`

### 3. context.py — Context Builder

- system prompt 存放在 `prompts/system.md`，config.toml 只存路径 + 旋钮（model / max_tokens / temperature）
- config.py 启动时读成 str 传入，ContextBuilder 零 I/O
- system 全程静态 — prompt cache 命中的前提
- `build(history, todos) -> BuiltContext(system, messages)`，具名结构不用裸 tuple
- tools 不在 context 层（归 tool 层，loop 装配）；messages 是域对象 `list[Message]`，序列化压到 llm client 边界
- todo 不进 system prompt（否则每轮打穿缓存），渲染成 `<todo_status>` 块临时追加到末条 user 消息，不回写历史
- TaskState：内存权威 + `.task` 文件写穿，原子写（临时文件 + fsync + os.replace），损坏退回空（history 才是真源，`.task` 只是续跑缓存）

### 4. llm.py — LLM 封装

- 序列化：`model_dump` 为主（types.py 字段对齐 Anthropic API 命名），私有装配方法只做三件事：提取 ctx.system 当顶层参数、dump messages、挂 tools
- 不跨消息重新路由 block（上游保证不变量），不提取 system（context.py 已分离）
- 入站方向用 `model_validate` 直接吃 SDK 响应
- `cache_control` 断点在 llm.py 加：静态 system 包成带 `cache_control: ephemeral` 的块 — 这是 prompt cache 命中的唯一落点
- 错误处理：API 失败走异常通道（不走 ToolResult 模式）
- `LLMError` 基类，下分 `Auth` / `BadRequest` / `Transient`
- 瞬时类（超时、429、5xx）靠 SDK 的 `max_retries` 内置退避；不可重试类（401/403、400）立即抛
- loop 只 catch `LLMError` 决定重试还是终止，vendor-neutral

### 5. SessionLog — 会话日志

- loop.py 是唯一写者（llm.py 看不到 tool_result，只能记一半）
- append-only JSONL，一条 entry 对一条 message 的忠实转录（不把 tool_use 拍扁成独立事件）
- `usage` 和 `stop_reason` 内联在 assistant entry 上（成本聚合直接读这条）
- 统一信封 `{timestamp, seq, type, ...}`，`seq` 用单调序号（毫秒时间戳会撞、时钟可能回拨）
- 补 `error` 和 `session_meta`（model、system 哈希、config）两类非消息 entry
- SessionLog 包含 history，续跑就是把消息类 entry 回放成 history

### 6. loop.py — Agent Loop

**循环顺序**：`build -> call -> 立刻落 assistant 轮（memory + log）-> 按 stop_reason 分支`

关键：assistant 轮在分支之前就落库，否则 end_turn 那轮永远没写进 memory。

**tool_use 分支**：遍历执行所有 tool_use 块，收集结果打包成**一条** user 消息（content 是 tool_result 块的列表），追加一次，再循环。

**孤儿不变量**：每次 llm.call 前，检查上一条 assistant 的 tool_use 块是否都有配对 tool_result，缺的补 `is_error=True, content="interrupted"` 的 ToolResult。保证历史永远合法、可回放。

**终止条件**：
- 终止类：end_turn / stop_sequence（输出文本结束）、refusal（输出拒答文本结束）
- 继续类：tool_use / pause_turn（兜底当继续）
- 护栏类：最大轮次（可配，截断时明确标注"被轮次上限截断"）、可选总 token 预算
- 异常类：LLMError（auth/bad-request 致命，transient 耗尽停止）
- 截断类：max_tokens 不续写，截断标注后结束；残破 tool_use 块丢弃

**Ctrl+C**：catch KeyboardInterrupt，优雅退出。日志 append-only + TaskState 原子写穿已耐崩。

**I/O 不可知**：loop 拿初始消息 + provider，不关心输入来源。CLI 薄壳按优先级选源：argv 参数 -> 一次性；stdin pipe -> 一次性；tty -> 交互式 REPL。

### 7. tools/base.py — Tool 协议

- `Tool[InputT]` 泛型化，`execute(self, args: InputT)` 类型自洽（方法参数逆变，泛型解决）
- execute 收 `ToolUseBlock`（不是 name + args），tool_use_id 自然流入 ToolResult
- Input 是 Pydantic 模型类，`Field(description=...)` 要写厚 — 模型读字段描述来填参，直接决定工具调用准确率

### 8. tools/registry.py — Tool Registry

- `register(tool)` 拒重名（两个同名工具模型没法区分），直接抛
- `execute(call: ToolUseBlock) -> ToolResult`：Pydantic 解析 + 分发
- **唯一错误围栏**：catch `Exception`（不包括 `BaseException`），ValidationError + 运行时异常统一转 `ToolResult(is_error=True)`。agent loop 绝不能被写挫的工具搞崩
- 未知工具名转 `ToolResult(is_error=True)`（模型幻觉出不存在的工具名很常见）
- `schemas()` 返回缓存好的 `{name, description, input_schema}` 信封列表（register 时生成一次）

### 9. 内置工具 — shell（ShellTool）

- Input：`command: str`, `timeout: int = 30`
- `shell=True`（模型要发 `ls | grep x && cat y`，没 shell 不叫 shell 工具）
- `start_new_session=True` 开新进程组，超时杀整个组（TimeoutExpired -> kill process group）
- `stderr=subprocess.STDOUT` 合并，保留时间顺序
- 永远带 exit code
- 非零退出 != is_error（`grep` 没匹配返回 1 是正常结果），is_error 只留给超时 / 无法 spawn
- 输出截断：留头 + 留尾，中间打 `[... 截断 N 字符 ...]` 标记，默认 8000 字符可配
- 工作目录固定 cwd，每次命令全新 shell、cd 不跨调用（无状态可预测）
- 安全围栏不在 subprocess 参数里，在 permissions/sandbox 层

### 10. 内置工具 — file_ops

**read_file（ReadFileTool）**
- Input：`path: str`, `start_line: int | None = None`, `end_line: int | None = None`
- 带行号（cat -n 风格），方便 LLM 引用
- 工具描述里写死：行号是展示用的，edit 的 old_str 必须匹配原始内容、不能带行号前缀
- offset/limit 读窗口防撑爆上下文；不传则读全文
- 文件不存在 / 二进制 / 解码失败 -> is_error

**write_file（WriteFileTool）**
- Input：`path: str`, `content: str`, `mode: Literal["overwrite", "append"] = "overwrite"`
- 文件不存在 -> 创建；父目录不存在 -> 报错（路径来自不可信模型，不能默默建目录树）
- 原子写（临时文件 + fsync + os.replace）

**edit_file（EditFileTool）**
- Input：`path: str`, `old_str: str`, `new_str: str`, `replace_all: bool = False`
- 校验在工具内部做（业务语义不是参数 schema）：空 old_str 报错、找不到报错、多匹配且 replace_all=False 报错
- 报错信息可执行：报出匹配次数、提示空白缩进问题
- 原子写（临时文件 + fsync + os.replace）
- 路径穿越防护归 permissions 层

### 11. 内置工具 — todo（TodoWriteTool）

- Input：`todos: list[TodoItem]`（全量替换，模型每次给完整当前列表）
- 只写不读 — 当前 todo 每轮由 ContextBuilder 渲染成 `<todo_status>` 注入上下文，模型看得到
- 不增量（避免 delta 跟踪让模型心智和实际状态漂移）
- TaskState 按引用共享：loop 创建唯一实例，注入给 todo 工具（写）和 context.build（读同一个对象）
- 工具返回简短确认，不重复输出全量列表（下一轮上下文里又会出现，避免双重注入）

### 12. config.py — 配置加载

- 读 `config.toml`，返回具名结构（model / max_tokens / temperature / system_prompt_path 等）
- system prompt 从 `prompts/system.md` 读成 str，随配置一起传入
- 提供 `config.example.toml` 模板

### 13. main.py — CLI 入口

- 解析 argv：有参数 -> 一次性模式；stdin 非 tty -> pipe 模式；tty 无参数 -> REPL 模式
- 装配所有模块（config -> memory -> context -> registry -> tools -> loop）
- REPL 模式支持退出命令（exit / quit / Ctrl+D）

## Testing Decisions

- 测试只覆盖外部可观测行为，不测内部实现细节
- types.py：序列化 / 反序列化往返（Message <-> API dict）、discriminated union 分发正确性
- memory.py：add / clear / as_messages 的基本行为
- context.py：build 输出结构、todo 注入不污染 history、system prompt 静态不变
- llm.py：API 请求组装正确性（system 提取、cache_control 加入）、LLMError 分类
- registry.py：schema 自动生成、重名拒绝、未知工具名转 is_error、异常围栏
- shell：超时杀进程组、非零退出 != is_error、输出截断保留头尾
- file_ops：行号显示、old_str 匹配逻辑、原子写、父目录不存在报错
- todo：全量替换语义、TaskState 共享实例
- loop：孤儿 tool_use 补丁、max_iterations 截断标注、Ctrl+C 优雅退出
- s01 原型可作为集成测试的参考（已跑通的核心循环行为）

## Out of Scope

- 长期记忆 / 向量存储
- 上下文压缩（Context Compaction）
- 后台任务（Background Tasks）
- 定时调度（Scheduling）
- DAG 依赖（Task Management 的依赖图部分）
- 权限系统 / 沙箱（Permissions & Guardrails）
- Hook 机制
- Sub-agent
- 多 Agent 协调
- 自动续写（max_tokens 截断后不续写，留给 v2 带护栏实现）

## Further Notes

- 所有模块同步架构（ADR-0001），future migration cost 低（仅 llm.call 和 shell.execute 两个 choke-point）
- SessionLog JSONL 即会话历史的持久化形态，v1 虽然 Memory 纯内存，但日志已为 v2 续跑打好基础
- TaskState 的 `.task` 文件是续跑缓存，history 才是真源 — 损坏可安全退回空
- 工具安全围栏（shell RCE、file_ops 路径穿越）统一收口到未来的 permissions 层，v1 不在工具内部做
