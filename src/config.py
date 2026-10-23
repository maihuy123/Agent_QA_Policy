"""Cấu hình dự án: bí mật đọc từ biến môi trường (.env), tham số thử nghiệm đọc từ config.yaml."""

import os
from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    """Toàn bộ cấu hình cần cho ingestion, agent và đánh giá."""

    openai_api_key: str
    chat_model: str
    embedding_model: str
    chroma_path: Path
    collection_name: str
    data_dir: Path
    chunk_size: int
    chunk_overlap: int
    top_k: int
    max_distance: float
    max_agent_steps: int

    def with_overrides(self, **changes) -> "Settings":
        """Trả về bản sao với một số tham số thay đổi (dùng khi thử nhiều cấu hình)."""
        return replace(self, **changes)


def _resolve_path(value: str) -> Path:
    # Đường dẫn tương đối được tính từ thư mục gốc dự án, không phụ thuộc thư mục đang chạy
    path = Path(value)
    return path if path.is_absolute() else ROOT_DIR / path


def load_settings(config_path: str | None = None) -> Settings:
    """Đọc cấu hình từ biến môi trường và file YAML."""
    yaml_path = _resolve_path(config_path or os.getenv("CONFIG_PATH", "config.yaml"))
    with open(yaml_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    chunking = cfg.get("chunking", {})
    retrieval = cfg.get("retrieval", {})
    agent = cfg.get("agent", {})

    settings = Settings(
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        chat_model=os.getenv("OPENAI_CHAT_MODEL", "gpt-4.1-mini"),
        embedding_model=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
        chroma_path=_resolve_path(os.getenv("CHROMA_PATH", "chroma_db")),
        collection_name=os.getenv("CHROMA_COLLECTION", "internal_docs"),
        data_dir=_resolve_path(os.getenv("DATA_DIR", "data/raw")),
        chunk_size=int(chunking.get("chunk_size", 800)),
        chunk_overlap=int(chunking.get("chunk_overlap", 150)),
        top_k=int(retrieval.get("top_k", 5)),
        max_distance=float(retrieval.get("max_distance", 0.65)),
        max_agent_steps=int(agent.get("max_steps", 6)),
    )
    if settings.chunk_overlap >= settings.chunk_size:
        raise ValueError("chunk_overlap phải nhỏ hơn chunk_size")
    return settings


@lru_cache
def get_settings() -> Settings:
    """Cấu hình mặc định, chỉ đọc một lần cho mỗi tiến trình."""
    return load_settings()
