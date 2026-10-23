"""Tool tìm chunk liên quan tới câu hỏi trong knowledge base."""

from src.clients import embed_texts
from src.tools.base import Tool, ToolContext

NO_RESULT_MESSAGE = "Không tìm thấy đoạn tài liệu nào đủ liên quan."


def search_documents(ctx: ToolContext, query: str, source: str | None = None, top_k: int | None = None) -> dict:
    """Embedding câu truy vấn, lấy top-k chunk và bỏ những chunk vượt ngưỡng khoảng cách."""
    top_k = top_k or ctx.settings.top_k
    embedding = embed_texts([query], ctx.settings.embedding_model)[0]
    hits = ctx.kb.query(embedding, top_k=top_k, source=source or None)
    results = [
        {
            "chunk_id": h.id,
            "source": h.metadata["source"],
            "title": h.metadata.get("title", ""),
            "page": h.metadata.get("page", 0),
            "section": h.metadata.get("section", ""),
            "updated_at": h.metadata.get("updated_at", ""),
            "score": round(1 - h.distance, 3),
            "text": h.text,
        }
        for h in hits
        if h.distance <= ctx.settings.max_distance
    ]
    if not results:
        return {"results": [], "message": NO_RESULT_MESSAGE}
    return {"results": results}


TOOL = Tool(
    name="search_documents",
    description=(
        "Tìm các đoạn trong tài liệu nội bộ (quy trình, chính sách) liên quan tới câu hỏi. "
        "Luôn gọi tool này trước khi trả lời câu hỏi về nội dung tài liệu. "
        "Có thể gọi nhiều lần với cách diễn đạt khác nếu lần đầu không có kết quả."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Câu truy vấn tìm kiếm, nên viết đầy đủ ý bằng tiếng Việt.",
            },
            "source": {
                "type": "string",
                "description": "Tên file để chỉ tìm trong một tài liệu (lấy từ list_sources). Bỏ trống để tìm tất cả.",
            },
            "top_k": {
                "type": "integer",
                "description": "Số đoạn muốn lấy. Bỏ trống để dùng giá trị mặc định.",
                "minimum": 1,
                "maximum": 20,
            },
        },
        "required": ["query"],
    },
    handler=search_documents,
)
