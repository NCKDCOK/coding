import subprocess
import json


def run_bash(command: str) -> str:
    """执行 shell 命令并返回结果。"""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        output = result.stdout
        if result.stderr:
            output += f"\n[stderr]\n{result.stderr}"
        if result.returncode != 0:
            output += f"\n[exit code: {result.returncode}]"
        return output.strip() or "(无输出)"
    except subprocess.TimeoutExpired:
        return "[错误] 命令执行超时（30秒）"
    except Exception as e:
        return f"[错误] {e}"


# 工具定义（传给 Claude API 的 tools 参数）
TOOLS = [
    {
        "name": "bash",
        "description": "执行 shell 命令。用于文件操作、运行脚本、查看系统信息等。命令超时时间为 30 秒。",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "要执行的 shell 命令",
                }
            },
            "required": ["command"],
        },
    }
]

# 路由表（工具名 → 执行函数）
HANDLERS = {
    "bash": lambda input: run_bash(input["command"]),
}
