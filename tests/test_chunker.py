import pytest

from src.ingestion.chunker import chunk_document, split_text
from src.ingestion.loaders import LoadedDocument, Section


def test_short_text_is_single_chunk():
    assert split_text("Một đoạn ngắn.", 100, 10) == ["Một đoạn ngắn."]


def test_chunks_respect_size_limit():
    text = "\n\n".join(f"Đoạn số {i}. " + "nội dung " * 30 for i in range(10))
    chunks = split_text(text, 200, 40)
    assert len(chunks) > 1
    assert all(len(c) <= 200 for c in chunks)


def test_overlap_repeats_tail_of_previous_chunk():
    text = " ".join(f"câu{i}." for i in range(200))
    chunks = split_text(text, 120, 30)
    for prev, cur in zip(chunks, chunks[1:]):
        first_word = cur.split()[0]
        assert first_word in prev


def test_very_long_word_is_hard_split():
    chunks = split_text("x" * 250, 100, 10)
    assert all(len(c) <= 100 for c in chunks)
    assert "".join(c.replace("\n", "") for c in chunks).count("x") >= 250


def test_overlap_must_be_smaller_than_size():
    with pytest.raises(ValueError):
        split_text("abc", 50, 50)


def test_chunk_metadata_has_source_info():
    doc = LoadedDocument(
        source="a.md", title="Tài liệu A", author="HR", updated_at="2026-01-01", file_type="markdown",
        sections=[Section(text="Nội dung mục một.", heading="Mục 1"), Section(text="Trang hai.", page=2)],
    )
    chunks = chunk_document(doc, 100, 10)
    assert [c.id for c in chunks] == ["a.md::0", "a.md::1"]
    assert chunks[0].metadata["section"] == "Mục 1"
    assert chunks[1].metadata["page"] == 2
    assert all(c.metadata["source"] == "a.md" and c.metadata["updated_at"] for c in chunks)
    assert chunks[0].embedding_text.startswith("Tài liệu: Tài liệu A\nMục: Mục 1")
