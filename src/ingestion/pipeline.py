"""Luồng nạp tài liệu: đọc file → chunk → embedding → lưu ChromaDB.

Chạy từ thư mục gốc dự án:
    python -m src.ingestion.pipeline            # nạp (hoặc nạp lại) mọi file trong DATA_DIR
    python -m src.ingestion.pipeline --reset    # xóa sạch collection rồi nạp lại
"""

import argparse
import logging
from pathlib import Path

from src.clients import embed_texts
from src.config import Settings, get_settings
from src.ingestion.chunker import chunk_document
from src.ingestion.loaders import SUPPORTED_EXTENSIONS, load_document
from src.knowledge_base.store import KnowledgeBase

logger = logging.getLogger(__name__)


def ingest_file(path: Path, kb: KnowledgeBase, settings: Settings) -> int:
    """Nạp một file, thay thế phiên bản cũ nếu đã có. Trả về số chunk đã lưu."""
    doc = load_document(path)
    chunks = chunk_document(doc, settings.chunk_size, settings.chunk_overlap)
    kb.delete_source(doc.source)
    if not chunks:
        logger.warning("Không đọc được nội dung từ %s (có thể là file scan)", path.name)
        return 0
    embeddings = embed_texts([c.embedding_text for c in chunks], settings.embedding_model)
    kb.add_chunks(chunks, embeddings)
    return len(chunks)


def ingest_directory(
    data_dir: Path | None = None,
    settings: Settings | None = None,
    kb: KnowledgeBase | None = None,
    reset: bool = False,
) -> dict:
    """Nạp mọi file được hỗ trợ trong thư mục. Trả về số chunk theo từng file và danh sách lỗi."""
    settings = settings or get_settings()
    data_dir = Path(data_dir or settings.data_dir)
    kb = kb or KnowledgeBase(settings)
    if reset:
        kb.reset()

    files = sorted(p for p in data_dir.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS)
    summary = {"files": {}, "errors": {}}
    for path in files:
        try:
            summary["files"][path.name] = ingest_file(path, kb, settings)
            logger.info("Đã nạp %s: %d chunk", path.name, summary["files"][path.name])
        except Exception as exc:
            # Một file lỗi không làm dừng cả quá trình nạp
            summary["errors"][path.name] = str(exc)
            logger.error("Lỗi khi nạp %s: %s", path.name, exc)
    summary["total_chunks"] = kb.count()
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Nạp tài liệu vào ChromaDB")
    parser.add_argument("--reset", action="store_true", help="xóa collection trước khi nạp")
    parser.add_argument("--data-dir", help="thư mục chứa tài liệu (mặc định: DATA_DIR)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    for noisy in ("httpx", "openai"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    summary = ingest_directory(Path(args.data_dir) if args.data_dir else None, reset=args.reset)
    print(f"Hoàn tất: {len(summary['files'])} file, {summary['total_chunks']} chunk trong knowledge base.")
    if summary["errors"]:
        print(f"Có {len(summary['errors'])} file lỗi: {', '.join(summary['errors'])}")


if __name__ == "__main__":
    main()
