from dataclasses import dataclass
from enum import Enum


class Status(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


@dataclass
class TodoItem:
    id: int
    task: str
    status: Status = Status.PENDING


class TodoList:
    def __init__(self):
        self.items: list[TodoItem] = []
        self._next_id = 1

    def add(self, task: str) -> TodoItem:
        item = TodoItem(id=self._next_id, task=task)
        self.items.append(item)
        self._next_id += 1
        return item

    def update_status(self, item_id: int, status: Status) -> bool:
        for item in self.items:
            if item.id == item_id:
                item.status = status
                return True
        return False

    def clear(self):
        self.items.clear()

    def render(self) -> str:
        if not self.items:
            return ""
        lines = ["## 当前任务计划"]
        for item in self.items:
            icon = {"pending": "[ ]", "in_progress": "[>]", "completed": "[x]"}
            lines.append(f"{icon[item.status.value]} {item.id}. {item.task}")
        return "\n".join(lines)


def make_todo_handler(todo: TodoList):
    def manage_todo(inp: dict) -> str:
        action = inp.get("action", "")
        if action == "add":
            task = inp.get("task", "")
            item = todo.add(task)
            return f"已添加任务 #{item.id}: {task}"
        elif action == "update":
            item_id = inp.get("item_id", 0)
            status = inp.get("status", "")
            try:
                s = Status(status)
            except ValueError:
                return f"[错误] 无效状态: {status}"
            if todo.update_status(item_id, s):
                return f"已更新任务 #{item_id} 状态为 {status}"
            return f"[错误] 任务 #{item_id} 不存在"
        elif action == "list":
            return todo.render() or "暂无任务"
        elif action == "clear":
            todo.clear()
            return "已清空任务列表"
        else:
            return f"[错误] 未知操作: {action}"
    return manage_todo


TODO_TOOL = {
    "name": "manage_todo",
    "description": "管理任务计划。操作: add, update, list, clear",
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["add", "update", "list", "clear"]},
            "task": {"type": "string", "description": "任务描述（add 时必填）"},
            "item_id": {"type": "integer", "description": "任务 ID（update 时必填）"},
            "status": {"type": "string", "enum": ["pending", "in_progress", "completed"]},
        },
        "required": ["action"],
    },
}
