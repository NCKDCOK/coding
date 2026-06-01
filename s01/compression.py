import anthropic
import config


def compress_messages(messages: list[dict], client: anthropic.Anthropic) -> list[dict]:
    """压缩对话历史，保留关键信息。

    策略：让模型总结之前的对话，用总结替代完整历史。
    """
    if len(messages) <= 4:
        return messages

    # 提取要压缩的消息（保留最近 2 轮）
    recent = messages[-4:]
    to_compress = messages[:-4]

    # 构建总结请求
    conversation_text = ""
    for msg in to_compress:
        role = msg["role"]
        content = msg["content"]
        if isinstance(content, str):
            conversation_text += f"[{role}]: {content}\n"
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        conversation_text += f"[{role}]: {block['text']}\n"
                    elif block.get("type") == "tool_use":
                        conversation_text += f"[{role} 调用工具]: {block['name']}({block['input']})\n"
                    elif block.get("type") == "tool_result":
                        result_text = block.get("content", "")
                        if isinstance(result_text, list):
                            result_text = str(result_text)
                        conversation_text += f"[工具结果]: {result_text}\n"

    response = client.messages.create(
        model=config.MODEL,
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": f"请用中文总结以下对话的关键信息，保留所有重要的决策、文件路径、代码修改和任务进度。用简洁的要点格式输出。\n\n{conversation_text}",
            }
        ],
    )

    summary = response.content[0].text

    # 用总结替换历史
    compressed = [
        {
            "role": "user",
            "content": f"[以下是之前对话的总结]\n{summary}",
        },
        {
            "role": "assistant",
            "content": "好的，我已了解之前的对话内容。请继续。",
        },
    ]

    return compressed + recent
