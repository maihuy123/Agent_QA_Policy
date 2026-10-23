from src.ingestion.pipeline import ingest_directory
from src.tools.base import ToolContext
from src.tools.registry import TOOLS, execute_tool, tool_schemas


def _write_docs(folder):
    folder.mkdir()
    (folder / "nghi_phep.md").write_text(
        "---\ntitle: Nghỉ phép\nauthor: HR\nupdated: 2026-03-01\n---\n"
        "## Số ngày phép\nNhân viên có 12 ngày phép năm.\n\n## Thủ tục\nTạo đơn trên hệ thống HRM.",
        encoding="utf-8",
    )
    (folder / "bao_mat.md").write_text(
        "---\ntitle: Bảo mật\nauthor: IT\n---\n## Mật khẩu\nMật khẩu dài ít nhất 12 ký tự.",
        encoding="utf-8",
    )


def test_registry_has_three_tools_with_valid_schema():
    assert set(TOOLS) == {"search_documents", "get_document_info", "list_sources"}
    for schema in tool_schemas():
        assert schema["type"] == "function"
        assert schema["function"]["parameters"]["type"] == "object"


def test_ingest_and_tools_end_to_end(tmp_path, kb, settings):
    _write_docs(tmp_path / "raw")
    summary = ingest_directory(tmp_path / "raw", settings=settings, kb=kb)
    assert summary["errors"] == {}
    assert summary["files"] == {"bao_mat.md": 1, "nghi_phep.md": 2}

    ctx = ToolContext(kb=kb, settings=settings)

    listing = execute_tool("list_sources", "{}", ctx)
    assert listing["count"] == 2

    info = execute_tool("get_document_info", '{"source": "nghi_phep.md"}', ctx)
    assert info["author"] == "HR" and info["updated_at"] == "2026-03-01"
    assert info["sections"] == ["Số ngày phép", "Thủ tục"]

    missing = execute_tool("get_document_info", '{"source": "nghi_phep"}', ctx)
    assert "error" in missing and "nghi_phep.md" in missing["suggestions"]

    found = execute_tool("search_documents", '{"query": "mật khẩu dài bao nhiêu ký tự"}', ctx)
    assert found["results"][0]["source"] == "bao_mat.md"

    only = execute_tool("search_documents", '{"query": "phép", "source": "nghi_phep.md"}', ctx)
    assert {r["source"] for r in only["results"]} == {"nghi_phep.md"}


def test_reingest_replaces_old_chunks(tmp_path, kb, settings):
    _write_docs(tmp_path / "raw")
    ingest_directory(tmp_path / "raw", settings=settings, kb=kb)
    ingest_directory(tmp_path / "raw", settings=settings, kb=kb)
    assert kb.count() == 3


def test_search_below_threshold_returns_no_result(tmp_path, kb, settings):
    _write_docs(tmp_path / "raw")
    ingest_directory(tmp_path / "raw", settings=settings, kb=kb)
    strict = ToolContext(kb=kb, settings=settings.with_overrides(max_distance=0.0))
    result = execute_tool("search_documents", '{"query": "thời tiết hôm nay"}', strict)
    assert result["results"] == [] and "message" in result


def test_execute_tool_errors_are_returned_not_raised(kb, settings):
    ctx = ToolContext(kb=kb, settings=settings)
    assert "error" in execute_tool("khong_ton_tai", "{}", ctx)
    assert "error" in execute_tool("list_sources", "not json", ctx)
    assert "error" in execute_tool("get_document_info", '{"wrong": 1}', ctx)
