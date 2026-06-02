import sys
import os
import json
import uuid
import anthropic
import config
from tools import TOOLS, HANDLERS
from todo import TodoList, Status, TODO_TOOL, make_todo_handler
from compression import compress_messages
from sub_agent import DELEGATE_TOOL, DELEGATE_HANDLER


SYSTEM_PROMPT = "你是一个 mini coding agent。你可以通过 bash 工具执行 shell 命令来完成用户的任务。对于复杂的多步任务，先使用 manage_todo 工具创建任务计划，然后逐步执行并更新状态。"

LOGS_DIR = os.path.join(os.path.dirname(__file__), "logs")


class SessionLogger:
    def __init__(self, silent=False):
        self.silent = silent
        if not silent:
            os.makedirs(LOGS_DIR, exist_ok=True)
            self.session_id = str(uuid.uuid4())[:8]
            self.log_path = os.path.join(LOGS_DIR, f"{self.session_id}.jsonl")
            self._file = open(self.log_path, "a", encoding="utf-8")
            print(f"📝 日志文件: {self.log_path}")
        else:
            self.session_id = "sub"
            self.log_path = None
            self._file = None

    def _write(self, entry: dict):
        if self._file:
            self._file.write(json.dumps(entry, ensure_ascii=False) + "\n")
            self._file.flush()

    def _serialize(self, obj):
        if hasattr(obj, "__dict__"):
            return {k: v for k, v in obj.__dict__.items() if not k.startswith("_")}
        return str(obj)

    def log_request(self, round_num: int, messages: list, system: str, tools: list):
        payload = {
            "model": config.MODEL,
            "max_tokens": 4096,
            "system": system,
            "tools": tools,
            "messages": messages,
        }
        if not self.silent:
            print(f"\n{'='*60}")
            print(f"📤 [Round {round_num}] REQUEST")
            print(f"{'='*60}")
            print(json.dumps(payload, ensure_ascii=False, indent=2, default=self._serialize))
            print(f"{'='*60}")
        self._write({
            "type": "request",
            "round": round_num,
            "payload": json.loads(json.dumps(payload, default=self._serialize)),
        })

    def log_response(self, round_num: int, response):
        resp_dict = {
            "id": response.id,
            "model": response.model,
            "stop_reason": response.stop_reason,
            "usage": {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
            "content": [],
        }
        for block in response.content:
            if block.type == "text":
                resp_dict["content"].append({"type": "text", "text": block.text})
            elif block.type == "tool_use":
                resp_dict["content"].append({
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                })
        if not self.silent:
            print(f"\n{'='*60}")
            print(f"📥 [Round {round_num}] RESPONSE")
            print(f"{'='*60}")
            print(json.dumps(resp_dict, ensure_ascii=False, indent=2))
            print(f"{'='*60}")
        self._write({"type": "response", "round": round_num, **resp_dict})

    def log_tool_call(self, round_num: int, name: str, input_data: dict, result: str):
        if not self.silent:
            print(f"\n  🔧 调用工具: {name}({json.dumps(input_data, ensure_ascii=False)})")
            print(f"  ✅ 结果: {result[:200]}{'...' if len(result) > 200 else ''}")
        self._write({
            "type": "tool_call",
            "round": round_num,
            "tool": name,
            "input": input_data,
            "result": result,
        })

    def close(self):
        if self._file:
            self._file.close()


logger: SessionLogger | None = None


def build_tools_and_handlers(todo: TodoList):
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
    global logger
    if logger is None:
        logger = SessionLogger()
    if todo is None:
        todo = TodoList()
    if tools is None or handlers is None:
        tools, handlers = build_tools_and_handlers(todo)

    round_count = 0

    while round_count < max_rounds:
        round_count += 1

        full_system = system
        if todo.items:
            full_system += f"\n\n{todo.render()}"

        if len(messages) > 10:
            messages[:] = compress_messages(messages, client, logger)

        logger.log_request(round_count, messages, full_system, tools)
        response = client.messages.create(
            model=config.MODEL,
            max_tokens=4096,
            system=full_system,
            tools=tools,
            messages=messages,
        )
        logger.log_response(round_count, response)

        text_parts = []
        tool_uses = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_uses.append(block)

        if response.stop_reason != "tool_use":
            return "\n".join(text_parts)

        messages.append({"role": "assistant", "content": response.content})

        tool_results = []
        for tool_use in tool_uses:
            tool_name = tool_use.name
            tool_input = tool_use.input

            if tool_name in handlers:
                result = handlers[tool_name](tool_input)
            else:
                result = f"[错误] 未知工具: {tool_name}"

            if len(result) > 5000:
                result = result[:5000] + "\n... (输出过长，已截断)"

            logger.log_tool_call(round_count, tool_name, tool_input, result)

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_use.id,
                "content": result,
            })

        messages.append({"role": "user", "content": tool_results})

    return "[达到最大循环次数]"


def interactive_mode():
    global logger
    logger = SessionLogger()
    client = anthropic.Anthropic(api_key=config.API_KEY, base_url=config.BASE_URL)
    messages = []
    todo = TodoList()
    tools, handlers = build_tools_and_handlers(todo)

    print(f"🤖 Mini Coding Agent | 模型: {config.MODEL} | 输入 quit 退出")
    print("-" * 40)

    while True:
        try:
            user_input = input("\n🧑 ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            logger.close()
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            print("再见！")
            logger.close()
            break

        messages.append({"role": "user", "content": user_input})
        reply = agent_loop(messages, client, tools=tools, handlers=handlers, todo=todo)
        print(f"\n🤖 {reply}")
        messages.append({"role": "assistant", "content": reply})


def single_shot_mode(task: str):
    global logger
    logger = SessionLogger()
    client = anthropic.Anthropic(api_key=config.API_KEY, base_url=config.BASE_URL)
    messages = [{"role": "user", "content": task}]
    todo = TodoList()
    tools, handlers = build_tools_and_handlers(todo)

    reply = agent_loop(messages, client, tools=tools, handlers=handlers, todo=todo)
    print(reply)
    logger.close()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        single_shot_mode(" ".join(sys.argv[1:]))
    else:
        interactive_mode()
