"""Danh sách tool của agent và hàm điều phối lệnh gọi tool."""

import json

from src.tools import get_document_info, list_sources, search_documents
from src.tools.base import Tool, ToolContext

# Thêm tool mới: tạo module định nghĩa TOOL rồi thêm vào tuple này
TOOLS: dict[str, Tool] = {
    m.TOOL.name: m.TOOL for m in (search_documents, get_document_info, list_sources)
}


def tool_schemas() -> list[dict]:
    """Schema của mọi tool, truyền vào tham số `tools` khi gọi model."""
    return [tool.schema() for tool in TOOLS.values()]


def execute_tool(name: str, arguments: str | dict, ctx: ToolContext) -> dict:
    """Chạy tool theo tên với tham số JSON từ model; lỗi được trả về dạng dict để model tự xử lý."""
    tool = TOOLS.get(name)
    if tool is None:
        return {"error": f"Tool không tồn tại: {name}"}
    try:
        kwargs = json.loads(arguments) if isinstance(arguments, str) else dict(arguments)
        kwargs = kwargs or {}
    except json.JSONDecodeError:
        return {"error": "Tham số không phải JSON hợp lệ"}
    try:
        return tool.run(ctx, **kwargs)
    except TypeError as exc:
        return {"error": f"Tham số không hợp lệ cho {name}: {exc}"}
    except Exception as exc:
        return {"error": f"Lỗi khi chạy {name}: {exc}"}
