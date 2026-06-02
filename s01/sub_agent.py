import anthropic
import config
from tools import TOOLS, HANDLERS


def run_sub_agent(task: str) -> str:
    from agent import agent_loop, logger

    client = anthropic.Anthropic(api_key=config.API_KEY, base_url=config.BASE_URL)
    messages = [{"role": "user", "content": task}]
    system = "你是子任务执行器。专注完成任务，返回简洁结果。不要询问额外信息。"

    result = agent_loop(
        messages=messages,
        client=client,
        system=system,
        tools=TOOLS,
        handlers=HANDLERS,
        max_rounds=10,
    )
    if len(result) > 5000:
        result = result[:5000] + "\n... (输出过长，已截断)"
    return result


DELEGATE_TOOL = {
    "name": "delegate",
    "description": "将子任务委派给子 agent 执行。子 agent 有独立上下文，适合探索性任务。",
    "input_schema": {
        "type": "object",
        "properties": {
            "task": {"type": "string", "description": "要委派的任务描述"},
        },
        "required": ["task"],
    },
}

DELEGATE_HANDLER = lambda inp: run_sub_agent(inp["task"])
