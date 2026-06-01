import anthropic
import config
from tools import TOOLS, HANDLERS


def run_sub_agent(task: str) -> str:
    """启动子 agent 执行独立任务。

    子 agent 有独立的上下文，执行完后返回结果。
    """
    # 避免循环导入
    from agent import agent_loop

    client = anthropic.Anthropic(
        api_key=config.API_KEY,
        base_url=config.BASE_URL,
    )

    messages = [{"role": "user", "content": task}]

    system = (
        "你是一个 mini coding agent 的子任务执行器。"
        "专注于完成给定的任务，完成后返回简洁的结果。"
        "不要询问额外信息，尽力完成任务。"
    )

    return agent_loop(
        messages=messages,
        client=client,
        system=system,
        tools=TOOLS,
        handlers=HANDLERS,
        max_rounds=10,
    )


# 子 agent 工具定义
DELEGATE_TOOL = {
    "name": "delegate",
    "description": (
        "将子任务委派给子 agent 执行。"
        "适用于：探索性任务、独立的信息收集、需要隔离上下文的工作。"
        "子 agent 有独立的上下文窗口，不会污染主对话。"
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "task": {
                "type": "string",
                "description": "要委派给子 agent 的任务描述",
            }
        },
        "required": ["task"],
    },
}

# 子 agent handler
DELEGATE_HANDLER = lambda input: run_sub_agent(input["task"])
