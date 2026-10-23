"""Lớp bọc ChromaDB: phần còn lại của dự án không gọi ChromaDB trực tiếp."""

from dataclasses import dataclass
from functools import lru_cache

import chromadb

from src.config import Settings, get_settings
from src.ingestion.chunker import Chunk

# Các trường metadata cấp file, giống nhau ở mọi chunk của cùng một tài liệu
DOCUMENT_FIELDS = ("source", "title", "author", "updated_at", "file_type")


@dataclass
class SearchHit:
    """Một chunk tìm được cùng khoảng cách cosine tới câu hỏi (càng nhỏ càng gần)."""

    id: str
    text: str
    metadata: dict
    distance: float


@lru_cache
def _client(path: str) -> chromadb.ClientAPI:
    return chromadb.PersistentClient(path=path)


class KnowledgeBase:
    """Lưu và truy vấn chunk trong một collection ChromaDB."""

    def __init__(self, settings: Settings | None = None, collection_name: str | None = None):
        self.settings = settings or get_settings()
        self.name = collection_name or self.settings.collection_name
        self._db = _client(str(self.settings.chroma_path))
        self.collection = self._open()

    def _open(self):
        # embedding_function=None: ta tự tạo embedding bằng OpenAI, ChromaDB chỉ lưu và tìm
        return self._db.get_or_create_collection(
            name=self.name,
            embedding_function=None,
            metadata={"hnsw:space": "cosine"},
        )

    def reset(self) -> None:
        """Xóa toàn bộ dữ liệu của collection."""
        try:
            self._db.delete_collection(self.name)
        except Exception:
            pass  # collection chưa tồn tại
        self.collection = self._open()

    def count(self) -> int:
        """Số chunk đang lưu."""
        return self.collection.count()

    def delete_source(self, source: str) -> None:
        """Xóa mọi chunk của một file, dùng trước khi nạp lại file đó."""
        self.collection.delete(where={"source": source})

    def add_chunks(self, chunks: list[Chunk], embeddings: list[list[float]]) -> None:
        """Lưu chunk cùng embedding và metadata."""
        if not chunks:
            return
        if len(chunks) != len(embeddings):
            raise ValueError("Số chunk và số embedding không khớp")
        self.collection.upsert(
            ids=[c.id for c in chunks],
            documents=[c.text for c in chunks],
            metadatas=[c.metadata for c in chunks],
            embeddings=embeddings,
        )

    def query(self, embedding: list[float], top_k: int, source: str | None = None) -> list[SearchHit]:
        """Trả về top_k chunk gần nhất, có thể giới hạn trong một file."""
        if self.count() == 0:
            return []
        result = self.collection.query(
            query_embeddings=[embedding],
            n_results=top_k,
            where={"source": source} if source else None,
            include=["documents", "metadatas", "distances"],
        )
        return [
            SearchHit(id=i, text=d, metadata=m, distance=float(dist))
            for i, d, m, dist in zip(
                result["ids"][0], result["documents"][0], result["metadatas"][0], result["distances"][0]
            )
        ]

    def list_sources(self) -> list[dict]:
        """Liệt kê các tài liệu đang có, kèm số chunk của mỗi tài liệu."""
        data = self.collection.get(include=["metadatas"])
        docs: dict[str, dict] = {}
        for meta in data["metadatas"]:
            entry = docs.get(meta["source"])
            if entry is None:
                entry = {k: meta.get(k, "") for k in DOCUMENT_FIELDS}
                entry["num_chunks"] = 0
                docs[meta["source"]] = entry
            entry["num_chunks"] += 1
        return sorted(docs.values(), key=lambda d: d["source"])

    def get_document(self, source: str) -> dict | None:
        """Thông tin cấp file của một tài liệu, hoặc None nếu không có."""
        data = self.collection.get(where={"source": source}, include=["metadatas"])
        metas = data["metadatas"]
        if not metas:
            return None
        info = {k: metas[0].get(k, "") for k in DOCUMENT_FIELDS}
        info["num_chunks"] = len(metas)
        pages = sorted({m["page"] for m in metas if m.get("page")})
        sections = list(dict.fromkeys(m["section"] for m in metas if m.get("section")))
        if pages:
            info["num_pages"] = pages[-1]
        if sections:
            info["sections"] = sections
        return info
