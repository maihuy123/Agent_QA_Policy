"""Tool lấy thông tin file gốc: tác giả, ngày cập nhật, số trang, các mục."""

import difflib

from src.tools.base import Tool, ToolContext


def get_document_info(ctx: ToolContext, source: str) -> dict:
    """Trả về metadata của tài liệu; nếu sai tên file thì gợi ý tên gần đúng."""
    info = ctx.kb.get_document(source)
    if info is not None:
        return info
    names = [d["source"] for d in ctx.kb.list_sources()]
    suggestions = difflib.get_close_matches(source, names, n=3, cutoff=0.3)
    return {"error": f"Không có tài liệu tên '{source}'.", "suggestions": suggestions}


TOOL = Tool(
    name="get_document_info",
    description=(
        "Lấy thông tin về một file tài liệu gốc: tiêu đề, tác giả/đơn vị soạn, ngày cập nhật, "
        "số chunk, các mục. Dùng khi người dùng hỏi tài liệu do ai soạn, cập nhật khi nào."
    ),
    parameters={
        "type": "object",
        "properties": {
            "source": {
                "type": "string",
                "description": "Tên file chính xác, ví dụ 'chinh_sach_nghi_phep.md' (lấy từ list_sources hoặc kết quả search_documents).",
            }
        },
        "required": ["source"],
    },
    handler=get_document_info,
)
