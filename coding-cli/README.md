# coding-cli

一个工程化的 coding agent，从 s01 演进而来。

## 设计理念

**harness 架构**：loop.py 是极薄的编排层，只负责"调人"，不负责"干活"。所有能力通过接口（契约）接入，模块之间不直接耦合。

核心循环：`think → act → observe`

```
用户输入
   ↓
loop.py（编排层）
   ├── context.py    组装上下文（系统提示词 + 记忆 + 历史）
   ├── llm.py        调用 LLM（SDK 封装 + 类型转换 + 日志）
   ├── registry.py   分发工具调用（按名查找 + 执行）
   └── memory.py     管理对话历史（存取 + 序列化）
```

## 目录结构

```
coding-cli/
├── main.py                      ← 入口：读配置、创建 Agent、启动交互循环
├── pyproject.toml               ← 项目元数据 + 依赖
├── config.toml                  ← 配置（gitignore）
├── config.example.toml          ← 配置模板
│
├── agent/                       ← 纯代码
│   ├── config.py                ← 配置加载
│   ├── types.py                 ← 数据结构（Message, ToolCall, ToolResult, LLMResponse）
│   ├── loop.py                  ← 核心编排：think → act → observe 主循环
│   ├── llm.py                   ← LLM 封装：SDK 调用 + 类型转换 + 日志
│   ├── context.py               ← prompt 组装：系统提示词 + 任务计划
│   ├── memory.py                ← 短期记忆：对话历史管理
│   └── tools/
│       ├── base.py              ← Tool 协议（接口定义）
│       ├── registry.py          ← 注册表：name → handler 映射 + 执行分发
│       └── builtin/
│           ├── shell.py         ← 执行 shell 命令
│           ├── file_ops.py      ← read_file / write_file / edit_file
│           └── todo.py          ← 任务管理
│
└── sessions/                    ← 运行时会话日志（gitignore）
```

## 模块职责边界

| 模块 | 只管什么 | 不管什么 |
|---|---|---|
| loop.py | 编排顺序、循环控制、终止条件 | 不管 prompt 怎么拼、工具怎么跑 |
| llm.py | SDK 调用、类型转换、日志 | 不管消息从哪来、结果往哪送 |
| context.py | 拼系统提示词、注入任务计划、压缩历史 | 不管 LLM 怎么调 |
| memory.py | 存取对话历史、序列化成 messages | 不管 prompt 模板 |
| tools/base.py | 定义 Tool 长什么样（接口） | 不管具体实现 |
| tools/registry.py | 注册工具、按名查找、执行分发 | 不管工具内部逻辑 |
| types.py | 纯数据结构，零逻辑 | 不依赖任何其他模块 |

## 技术选型

- Python 3.10+
- Anthropic SDK（同步，非异步）
- Pydantic（工具输入模型 + schema 自动生成）
- mimo-v2.5-pro 模型（Claude 兼容 API）
- JSONL 会话日志

## 当前版本范围

**v1 — 跑通主循环 + 学会模块串联：**
- [ ] Agent Loop（think → act → observe）
- [ ] LLM 封装（SDK + 类型转换 + 日志）
- [ ] Context 组装（系统提示词 + 任务计划注入）
- [ ] Memory 短期记忆（对话历史管理，只存 Message 类型）
- [ ] Tool Registry（显式注册 + Pydantic schema + 执行分发）
- [ ] 内置工具：shell / read_file / write_file / edit_file / todo

**暂不做：**
- 长期记忆 / 向量存储
- 上下文压缩
- 后台任务
- 定时调度
- DAG 依赖
- 权限系统
- Hook 机制
- Sub-agent
