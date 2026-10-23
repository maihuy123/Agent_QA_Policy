"""Điểm duy nhất tạo client OpenAI và gọi model embedding."""

from functools import lru_cache

from openai import OpenAI

from src.config import get_settings

EMBEDDING_BATCH_SIZE = 100


@lru_cache
def get_openai_client() -> OpenAI:
    """Client OpenAI dùng chung cho cả tiến trình."""
    api_key = get_settings().openai_api_key
    if not api_key:
        raise RuntimeError("Thiếu OPENAI_API_KEY. Hãy tạo file .env từ .env.example.")
    return OpenAI(api_key=api_key)


def embed_texts(texts: list[str], model: str | None = None) -> list[list[float]]:
    """Tạo embedding cho danh sách văn bản, gửi theo từng lô để tránh giới hạn request."""
    model = model or get_settings().embedding_model
    client = get_openai_client()
    vectors: list[list[float]] = []
    for start in range(0, len(texts), EMBEDDING_BATCH_SIZE):
        batch = texts[start : start + EMBEDDING_BATCH_SIZE]
        response = client.embeddings.create(model=model, input=batch)
        # API trả về theo đúng thứ tự input, sắp xếp lại theo index cho chắc chắn
        vectors.extend(item.embedding for item in sorted(response.data, key=lambda d: d.index))
    return vectors
