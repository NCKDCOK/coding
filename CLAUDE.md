# coding

## Agent skills

### Issue tracker

GitHub Issues. See `docs/agents/issue-tracker.md`.

### Triage labels

Five standard labels: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context repo. See `docs/agents/domain.md`.

## 项目规范

### 技术栈

- Python 3.10+
- Anthropic SDK（同步，非异步）
- Pydantic（工具输入模型 + schema 自动生成）
- mimo-v2.5-pro 模型（Claude 兼容 API）

### 代码风格

- 标识符（变量名、函数名、类名）用英文
- 注释、docstring、系统提示词、错误消息用中文
- 所有公开接口必须有完整类型注解
- 内部实现可以省略类型注解

### 架构原则

- loop.py 是极薄的编排层，只负责"调人"，不负责"干活"
- 所有模块通过接口（契约）通信，不直接耦合
- Memory 只存 Message 类型，API 格式转换收口在 `as_messages()` 一处
- 工具执行失败返回 ToolResult（is_error=True），不抛异常——错误信息喂回 LLM 让它自救
- 工具使用显式列表注册，不搞自动发现
- SDK 调用封装在 llm.py，类型转换 + 日志都在这层完成

### 工具定义规范

每个工具是一个类，实现 Tool 协议：
- `name`: 工具名
- `description`: 描述
- `Input`: Pydantic 模型（自动生成 JSON Schema）
- `execute(args) -> ToolResult`: 同步执行，返回 ToolResult

#### 内置工具规格

**shell（ShellTool）**
- Input: `command: str`, `timeout: int = 30`
- 超时返回错误，非零退出码返回错误

**read_file（ReadFileTool）**
- Input: `path: str`, `start_line: int | None = None`, `end_line: int | None = None`
- 文件不存在：报错
- 不传行范围：读全文
- 传 start_line/end_line：读指定行范围

**write_file（WriteFileTool）**
- Input: `path: str`, `content: str`, `mode: Literal["overwrite", "append"] = "overwrite"`
- 文件不存在：创建
- 父目录不存在：报错

**edit_file（EditFileTool）**
- Input: `path: str`, `old_str: str`, `new_str: str`, `replace_all: bool = False`
- 文件不存在：报错
- old_str 为空：报错
- 找不到 old_str：报错，不修改
- 匹配多次且 replace_all=False：报错，不修改
- 匹配多次且 replace_all=True：全部替换
- 匹配一次：替换

### v1 范围

只做：Agent Loop + LLM 封装 + Context 组装 + Memory 短期记忆 + Tool Registry + 内置工具（shell/file_ops/todo）
暂不做：长期记忆、后台任务、定时调度、DAG 依赖、权限系统、Hook 机制、Sub-agent、上下文压缩
