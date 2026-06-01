"""Todo 管理工具，让 agent 能创建和更新任务计划。"""

from todo import TodoList, Status


def make_todo_handler(todo: TodoList):
    """创建绑定到特定 todo list 的 handler。"""

    def manage_todo(input: dict) -> str:
        action = input.get("action", "")
        if action == "add":
            task = input.get("task", "")
            item = todo.add(task)
            return f"已添加任务 #{item.id}: {task}"
        elif action == "update":
            item_id = input.get("item_id", 0)
            status = input.get("status", "")
            try:
                s = Status(status)
            except ValueError:
                return f"[错误] 无效状态: {status}，可选: pending, in_progress, completed"
            if todo.update_status(item_id, s):
                return f"已更新任务 #{item_id} 状态为 {status}"
            return f"[错误] 任务 #{item_id} 不存在"
        elif action == "list":
            return todo.render() or "暂无任务"
        elif action == "clear":
            todo.items.clear()
            return "已清空任务列表"
        else:
            return f"[错误] 未知操作: {action}"

    return manage_todo


# 工具定义
TODO_TOOL = {
    "name": "manage_todo",
    "description": (
        "管理任务计划。用于多步任务的规划和跟踪。"
        "操作: add（添加任务）, update（更新状态）, list（查看列表）, clear（清空）"
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["add", "update", "list", "clear"],
                "description": "操作类型",
            },
            "task": {
                "type": "string",
                "description": "任务描述（add 时必填）",
            },
            "item_id": {
                "type": "integer",
                "description": "任务 ID（update 时必填）",
            },
            "status": {
                "type": "string",
                "enum": ["pending", "in_progress", "completed"],
                "description": "新状态（update 时必填）",
            },
        },
        "required": ["action"],
    },
}
