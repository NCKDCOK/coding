import anthropic
import config


def compress_messages(messages: list[dict], client: anthropic.Anthropic, logger=None) -> list[dict]:
    if len(messages) <= 4:
        return messages

    recent = messages[-4:]
    to_compress = messages[:-4]

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

    if logger:
        logger.log_request(0, [{"role": "user", "content": "[压缩] 请总结以下对话"}], "压缩模式", [])

    response = client.messages.create(
        model=config.MODEL,
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": f"请用中文总结以下对话的关键信息，保留决策、文件路径、代码修改和任务进度。用简洁要点输出。\n\n{conversation_text}",
        }],
    )

    if logger:
        logger.log_response(0, response)

    summary = response.content[0].text

    return [
        {"role": "user", "content": f"[以下是之前对话的总结]\n{summary}"},
        {"role": "assistant", "content": "好的，我已了解之前的对话内容。请继续。"},
    ] + recent
