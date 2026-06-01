from dataclasses import dataclass, field
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

    def get_current(self) -> TodoItem | None:
        for item in self.items:
            if item.status == Status.IN_PROGRESS:
                return item
        # 返回第一个 pending 的
        for item in self.items:
            if item.status == Status.PENDING:
                return item
        return None

    def is_complete(self) -> bool:
        return all(item.status == Status.COMPLETED for item in self.items)

    def render(self) -> str:
        """渲染为文本，用于注入 system prompt。"""
        if not self.items:
            return ""
        lines = ["## 当前任务计划"]
        for item in self.items:
            icon = {"pending": "[ ]", "in_progress": "[>]", "completed": "[x]"}
            lines.append(f"{icon[item.status.value]} {item.id}. {item.task}")
        return "\n".join(lines)
