"""Tool liệt kê các tài liệu đang có trong knowledge base."""

from src.tools.base import Tool, ToolContext


def list_sources(ctx: ToolContext) -> dict:
    """Danh sách tài liệu kèm tiêu đề, ngày cập nhật và số chunk."""
    sources = ctx.kb.list_sources()
    return {"count": len(sources), "sources": sources}


TOOL = Tool(
    name="list_sources",
    description=(
        "Liệt kê tất cả tài liệu đang có trong knowledge base (tên file, tiêu đề, ngày cập nhật). "
        "Dùng khi người dùng hỏi có những tài liệu nào, hoặc cần biết tên file chính xác."
    ),
    parameters={"type": "object", "properties": {}},
    handler=list_sources,
)
