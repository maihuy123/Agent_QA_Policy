"""Backend FastAPI. Chạy: uvicorn src.api.main:app --reload"""

from dataclasses import asdict
from functools import lru_cache
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.agent.agent import Agent
from src.ingestion.pipeline import ingest_directory

app = FastAPI(title="Trợ lý hỏi đáp tài liệu nội bộ")


class Turn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    question: str = Field(min_length=1)
    history: list[Turn] = []


class IngestRequest(BaseModel):
    reset: bool = False


@lru_cache
def get_agent() -> Agent:
    # Tạo agent một lần; client OpenAI và kết nối ChromaDB được dùng lại giữa các request
    return Agent()


@app.get("/health")
def health() -> dict:
    """Kiểm tra backend còn chạy và knowledge base có dữ liệu chưa."""
    return {"status": "ok", "chunks": get_agent().ctx.kb.count()}


@app.post("/chat")
def chat(req: ChatRequest) -> dict:
    """Trả lời câu hỏi kèm nguồn trích dẫn và vết gọi tool."""
    try:
        response = get_agent().ask(req.question, [t.model_dump() for t in req.history])
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Lỗi khi gọi model: {exc}") from exc
    return asdict(response)


@app.get("/sources")
def sources() -> dict:
    """Danh sách tài liệu trong knowledge base."""
    items = get_agent().ctx.kb.list_sources()
    return {"count": len(items), "sources": items}


@app.post("/ingest")
def ingest(req: IngestRequest) -> dict:
    """Nạp lại tài liệu từ DATA_DIR."""
    agent = get_agent()
    return ingest_directory(settings=agent.settings, kb=agent.ctx.kb, reset=req.reset)
