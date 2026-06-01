import sys
import json
import anthropic
import config
from tools import TOOLS, HANDLERS
from todo import TodoList, Status
from compression import compress_messages
from sub_agent import DELEGATE_TOOL, DELEGATE_HANDLER
from todo_tool import TODO_TOOL, make_todo_handler


SYSTEM_PROMPT = "你是一个 mini coding agent。你可以通过 bash 工具执行 shell 命令来完成用户的任务。对于复杂的多步任务，先使用 manage_todo 工具创建任务计划，然后逐步执行并更新状态。"


def build_tools_and_handlers(todo: TodoList):
    """构建完整的工具列表和路由表。"""
    tools = TOOLS + [DELEGATE_TOOL, TODO_TOOL]
    handlers = {
        **HANDLERS,
        "delegate": DELEGATE_HANDLER,
        "manage_todo": make_todo_handler(todo),
    }
    return tools, handlers


def agent_loop(
    messages: list[dict],
    client: anthropic.Anthropic,
    system: str = SYSTEM_PROMPT,
    tools: list | None = None,
    handlers: dict | None = None,
    todo: TodoList | None = None,
    max_rounds: int = 20,
) -> str:
    """核心 agent loop。循环调用模型直到模型不再调用工具。

    Args:
        messages: 对话历史
        client: Anthropic 客户端
        system: system prompt
        tools: 工具定义列表（为 None 时自动构建）
        handlers: 工具路由字典（为 None 时自动构建）
        todo: 可选的 todo list
        max_rounds: 最大循环次数，防止死循环

    Returns:
        模型的最终文本回复
    """
    if todo is None:
        todo = TodoList()
    if tools is None or handlers is None:
        tools, handlers = build_tools_and_handlers(todo)

    round_count = 0

    while round_count < max_rounds:
        round_count += 1

        # 构建 system prompt（注入 todo list）
        full_system = system
        if todo.items:
            full_system += f"\n\n{todo.render()}"

        # 压缩检查：消息太多时压缩历史
        if len(messages) > 10:
            messages[:] = compress_messages(messages, client)

        # 调用模型
        response = client.messages.create(
            model=config.MODEL,
            max_tokens=4096,
            system=full_system,
            tools=tools,
            messages=messages,
        )

        # 提取文本和工具调用
        text_parts = []
        tool_uses = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_uses.append(block)

        # 如果没有工具调用，返回结果
        if response.stop_reason != "tool_use":
            return "\n".join(text_parts)

        # 有工具调用：执行每个工具
        # 先把 assistant 的回复加入历史
        messages.append({"role": "assistant", "content": response.content})

        # 执行工具并收集结果
        tool_results = []
        for tool_use in tool_uses:
            tool_name = tool_use.name
            tool_input = tool_use.input

            print(f"\n  🔧 调用工具: {tool_name}({json.dumps(tool_input, ensure_ascii=False)})")

            if tool_name in handlers:
                result = handlers[tool_name](tool_input)
            else:
                result = f"[错误] 未知工具: {tool_name}"

            # 截断过长的结果
            if len(result) > 5000:
                result = result[:5000] + "\n... (输出过长，已截断)"

            print(f"  ✅ 结果: {result[:200]}{'...' if len(result) > 200 else ''}")

            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": result,
                }
            )

        # 把工具结果加入消息
        messages.append({"role": "user", "content": tool_results})

    return "[达到最大循环次数]"


def interactive_mode():
    """交互式多轮对话模式。"""
    client = anthropic.Anthropic(
        api_key=config.API_KEY,
        base_url=config.BASE_URL,
    )
    messages = []
    todo = TodoList()
    tools, handlers = build_tools_and_handlers(todo)

    print("🤖 Mini Coding Agent (输入 'quit' 退出)")
    print(f"   模型: {config.MODEL}")
    print("-" * 40)

    while True:
        try:
            user_input = input("\n🧑 ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            print("再见！")
            break

        messages.append({"role": "user", "content": user_input})

        reply = agent_loop(messages, client, tools=tools, handlers=handlers, todo=todo)
        print(f"\n🤖 {reply}")
        messages.append({"role": "assistant", "content": reply})


def single_shot_mode(task: str):
    """单次任务模式。给定任务，执行到完成。"""
    client = anthropic.Anthropic(
        api_key=config.API_KEY,
        base_url=config.BASE_URL,
    )
    messages = [{"role": "user", "content": task}]
    todo = TodoList()
    tools, handlers = build_tools_and_handlers(todo)

    reply = agent_loop(messages, client, tools=tools, handlers=handlers, todo=todo)
    print(reply)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # 单次模式：python agent.py "任务描述"
        task = " ".join(sys.argv[1:])
        single_shot_mode(task)
    else:
        # 交互模式
        interactive_mode()
