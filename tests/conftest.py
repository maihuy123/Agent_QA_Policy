"""Fixture dùng chung: knowledge base tạm và embedding giả để test không cần gọi OpenAI."""

import hashlib
import math

import pytest

from src.config import get_settings
from src.ingestion import pipeline
from src.knowledge_base.store import KnowledgeBase
from src.tools import search_documents

DIM = 64


def fake_embed(texts, model=None):
    """Embedding giả: túi từ băm vào 64 chiều, đủ để các câu cùng từ khóa nằm gần nhau."""
    vectors = []
    for text in texts:
        vec = [0.0] * DIM
        for word in text.lower().split():
            vec[int(hashlib.md5(word.encode()).hexdigest(), 16) % DIM] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        vectors.append([v / norm for v in vec])
    return vectors


@pytest.fixture
def settings(tmp_path):
    return get_settings().with_overrides(
        chroma_path=tmp_path / "chroma",
        collection_name="test_docs",
        max_distance=0.9,
    )


@pytest.fixture
def kb(settings, monkeypatch):
    monkeypatch.setattr(pipeline, "embed_texts", fake_embed)
    monkeypatch.setattr(search_documents, "embed_texts", fake_embed)
    return KnowledgeBase(settings)
