"""Khung chung cho mọi tool: thêm tool mới chỉ cần tạo một file định nghĩa `TOOL = Tool(...)`."""

from dataclasses import dataclass
from typing import Callable

from src.config import Settings
from src.knowledge_base.store import KnowledgeBase


@dataclass
class ToolContext:
    """Tài nguyên dùng chung mà tool cần, truyền vào lúc thực thi thay vì tạo lại mỗi lần."""

    kb: KnowledgeBase
    settings: Settings


@dataclass
class Tool:
    """Một tool agent có thể gọi: tên, mô tả, JSON schema tham số và hàm xử lý."""

    name: str
    description: str
    parameters: dict
    handler: Callable[..., dict]

    def schema(self) -> dict:
        """Định dạng tool theo chuẩn function calling của OpenAI."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def run(self, ctx: ToolContext, **kwargs) -> dict:
        """Thực thi tool với tham số model đã sinh."""
        return self.handler(ctx, **kwargs)
