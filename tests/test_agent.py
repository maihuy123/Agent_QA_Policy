"""Kiểm tra vòng lặp agent bằng client OpenAI giả (không gọi mạng)."""

import json
from types import SimpleNamespace as NS

from src.agent.agent import Agent
from src.ingestion.pipeline import ingest_directory
from tests.test_tools import _write_docs


class FakeClient:
    """Trả lần lượt các message đã định sẵn và ghi lại request để kiểm tra."""

    def __init__(self, messages):
        self._messages = list(messages)
        self.requests = []
        self.chat = NS(completions=NS(create=self._create))

    def _create(self, **kwargs):
        self.requests.append(kwargs)
        return NS(choices=[NS(message=self._messages.pop(0))])


def _tool_call(call_id, name, args):
    return NS(id=call_id, function=NS(name=name, arguments=json.dumps(args)))


def test_agent_calls_tool_then_answers_with_citation(tmp_path, kb, settings):
    _write_docs(tmp_path / "raw")
    ingest_directory(tmp_path / "raw", settings=settings, kb=kb)
    client = FakeClient([
        NS(content=None, tool_calls=[_tool_call("c1", "search_documents", {"query": "số ngày phép năm"})]),
        NS(content="Nhân viên có 12 ngày phép năm [Nguồn: nghi_phep.md, mục Số ngày phép].", tool_calls=None),
    ])
    agent = Agent(settings=settings, kb=kb, client=client)

    response = agent.ask("Tôi có bao nhiêu ngày phép?")

    assert "12 ngày" in response.answer
    assert [c["tool"] for c in response.tool_calls] == ["search_documents"]
    assert [s["source"] for s in response.sources] == ["nghi_phep.md"]
    assert client.requests[0]["tool_choice"] == "required"
    assert client.requests[1]["tool_choice"] == "auto"
    # Kết quả tool được gửi lại cho model ở lượt thứ hai
    tool_msgs = [m for m in client.requests[1]["messages"] if m["role"] == "tool"]
    assert tool_msgs and tool_msgs[0]["tool_call_id"] == "c1"


def test_agent_cites_document_from_get_document_info(tmp_path, kb, settings):
    _write_docs(tmp_path / "raw")
    ingest_directory(tmp_path / "raw", settings=settings, kb=kb)
    client = FakeClient([
        NS(content=None, tool_calls=[_tool_call("c1", "get_document_info", {"source": "nghi_phep.md"})]),
        NS(content="Do HR soạn, cập nhật 2026-03-01 [Nguồn: nghi_phep.md].", tool_calls=None),
    ])
    response = Agent(settings=settings, kb=kb, client=client).ask("Ai soạn chính sách nghỉ phép?")
    assert [s["source"] for s in response.sources] == ["nghi_phep.md"]


def test_agent_stops_after_max_steps(kb, settings):
    looping = [NS(content=None, tool_calls=[_tool_call(f"c{i}", "list_sources", {})]) for i in range(10)]
    agent = Agent(settings=settings.with_overrides(max_agent_steps=3), kb=kb, client=FakeClient(looping))
    response = agent.ask("abc")
    assert len(response.tool_calls) == 3
    assert response.sources == []
