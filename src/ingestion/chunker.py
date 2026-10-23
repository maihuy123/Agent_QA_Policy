"""Cắt tài liệu thành chunk, ưu tiên ngắt ở ranh giới đoạn văn và câu."""

import re
from dataclasses import dataclass

from src.ingestion.loaders import LoadedDocument

_SENTENCE_END = re.compile(r"(?<=[.!?;:])\s+")


@dataclass
class Chunk:
    """Một chunk sẵn sàng để embedding và lưu vào ChromaDB."""

    id: str
    text: str
    metadata: dict

    @property
    def embedding_text(self) -> str:
        """Văn bản đem đi embedding: thêm tên tài liệu và tên mục để tăng ngữ cảnh."""
        header = f"Tài liệu: {self.metadata['title']}"
        if self.metadata.get("section"):
            header += f"\nMục: {self.metadata['section']}"
        return f"{header}\n{self.text}"


def _hard_split(text: str, size: int) -> list[str]:
    # Cắt theo từ khi một câu vẫn dài hơn chunk_size
    pieces, current = [], ""
    for word in text.split():
        while len(word) > size:
            if current:
                pieces.append(current)
                current = ""
            pieces.append(word[:size])
            word = word[size:]
        candidate = f"{current} {word}" if current else word
        if len(candidate) <= size:
            current = candidate
        else:
            pieces.append(current)
            current = word
    if current:
        pieces.append(current)
    return pieces


def _units(text: str, size: int) -> list[str]:
    """Chia văn bản thành các đơn vị không dài hơn size: đoạn văn → câu → từ."""
    units = []
    for para in re.split(r"\n\s*\n", text):
        para = para.strip()
        if not para:
            continue
        if len(para) <= size:
            units.append(para)
            continue
        for sentence in _SENTENCE_END.split(para):
            sentence = sentence.strip()
            if not sentence:
                continue
            units.extend([sentence] if len(sentence) <= size else _hard_split(sentence, size))
    return units


def _tail(text: str, overlap: int) -> str:
    # Lấy phần cuối dài khoảng overlap ký tự, cắt ở đầu một từ để không bị nửa chữ
    if overlap <= 0 or not text:
        return ""
    tail = text[-overlap:]
    if len(text) > overlap and not text[-overlap - 1].isspace():
        space = re.search(r"\s", tail)
        tail = tail[space.end() :] if space else ""
    return tail.strip()


def split_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    """Cắt văn bản thành các chunk dài tối đa chunk_size ký tự, chồng lấp chunk_overlap ký tự."""
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap phải nhỏ hơn chunk_size")
    chunks: list[str] = []
    current = ""
    for unit in _units(text, chunk_size):
        candidate = f"{current}\n{unit}" if current else unit
        if len(candidate) <= chunk_size:
            current = candidate
            continue
        chunks.append(current)
        tail = _tail(current, chunk_overlap)
        current = f"{tail}\n{unit}" if tail and len(tail) + 1 + len(unit) <= chunk_size else unit
    if current:
        chunks.append(current)
    return chunks


def chunk_document(doc: LoadedDocument, chunk_size: int, chunk_overlap: int) -> list[Chunk]:
    """Cắt toàn bộ tài liệu, mỗi chunk mang đủ metadata để agent trích dẫn nguồn."""
    chunks: list[Chunk] = []
    for section in doc.sections:
        for text in split_text(section.text, chunk_size, chunk_overlap):
            index = len(chunks)
            chunks.append(
                Chunk(
                    id=f"{doc.source}::{index}",
                    text=text,
                    metadata={
                        "source": doc.source,
                        "title": doc.title,
                        "author": doc.author,
                        "updated_at": doc.updated_at,
                        "file_type": doc.file_type,
                        "page": section.page,
                        "section": section.heading,
                        "chunk_index": index,
                    },
                )
            )
    return chunks
