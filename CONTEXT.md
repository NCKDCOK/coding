# coding-cli

一个工程化的 coding agent，从 s01 演进而来。核心目标是学会模块串联，将独立的能力（LLM 调用、工具执行、记忆管理、上下文组装）通过接口契约组合成完整的 agent 系统。

## Language

**Harness**:
所有模块的宿主，不是某个模块，而是所有模块的编排层。通过接口（契约）和各模块通信，不关心具体实现。
_Avoid_: orchestrator, coordinator, main loop

**Agent Loop**:
Harness 的核心——think → act → observe 循环。接收用户输入，组装上下文，调用 LLM，分发工具调用，把结果喂回 LLM，直到 LLM 给出最终回答。
_Avoid_: main loop, execution loop

**Tool Registry**:
工具注册表。维护 name → handler 的映射，负责按名称查找工具并执行。使用显式列表注册，不搞自动发现。
_Avoid_: tool manager, tool dispatcher

**Message**:
对话历史的统一数据格式。Memory 只存 Message，不存裸 dict。API 格式的转换在 `as_messages()` 一处完成。
_Avoid_: chat entry, conversation item

**ToolResult**:
工具执行的返回值。包含输出内容和是否失败。错误信息作为 ToolResult 回传给 LLM，不抛异常。
_Avoid_: tool output, tool response

**LLMResponse**:
LLM 调用的返回值。包含内容块（文本 + 工具调用）、停止原因、token 用量。
_Avoid_: api response, model output

**Context Builder**:
上下文组装器。负责拼接系统提示词、注入任务计划、渲染 todo 状态。
_Avoid_: prompt builder, message assembler
