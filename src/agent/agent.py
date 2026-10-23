"""Agent hỏi đáp: vòng lặp gọi model → thực thi tool → gọi lại model cho tới khi có câu trả lời."""

import json
from dataclasses import dataclass, field

from openai import OpenAI

from src.agent.prompts import MAX_STEPS_ANSWER, SYSTEM_PROMPT
from src.clients import get_openai_client
from src.config import Settings, get_settings
from src.knowledge_base.store import KnowledgeBase
from src.tools.base import ToolContext
from src.tools.registry import execute_tool, tool_schemas


@dataclass
class AgentResponse:
    """Kết quả một lượt hỏi: câu trả lời, các nguồn được trích dẫn và vết gọi tool."""

    answer: str
    sources: list[dict] = field(default_factory=list)
    retrieved: list[dict] = field(default_factory=list)
    tool_calls: list[dict] = field(default_factory=list)


class Agent:
    """Agent dùng function calling của OpenAI để chọn và gọi tool."""

    def __init__(
        self,
        settings: Settings | None = None,
        kb: KnowledgeBase | None = None,
        client: OpenAI | None = None,
    ):
        self.settings = settings or get_settings()
        self.ctx = ToolContext(kb=kb or KnowledgeBase(self.settings), settings=self.settings)
        self.client = client or get_openai_client()
        self.tools = tool_schemas()

    def ask(self, question: str, history: list[dict] | None = None) -> AgentResponse:
        """Trả lời một câu hỏi; history là các lượt trước dạng {"role", "content"}."""
        messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
        for turn in history or []:
            if turn.get("role") in ("user", "assistant") and turn.get("content"):
                messages.append({"role": turn["role"], "content": turn["content"]})
        messages.append({"role": "user", "content": question})

        tool_log: list[dict] = []
        retrieved: dict[str, dict] = {}  # chunk lấy từ search_documents, theo chunk_id
        documents: dict[str, dict] = {}  # thông tin file lấy từ get_document_info, theo tên file

        for step in range(self.settings.max_agent_steps):
            response = self.client.chat.completions.create(
                model=self.settings.chat_model,
                messages=messages,
                tools=self.tools,
                # Bước đầu bắt buộc gọi tool để câu trả lời luôn dựa trên tài liệu
                tool_choice="required" if step == 0 else "auto",
                temperature=0,
            )
            message = response.choices[0].message

            if not message.tool_calls:
                answer = (message.content or "").strip()
                return AgentResponse(
                    answer=answer,
                    sources=_cited_sources(answer, retrieved, documents),
                    retrieved=list(retrieved.values()),
                    tool_calls=tool_log,
                )

            messages.append(
                {
                    "role": "assistant",
                    "content": message.content,
                    "tool_calls": [
                        {
                            "id": call.id,
                            "type": "function",
                            "function": {"name": call.function.name, "arguments": call.function.arguments},
                        }
                        for call in message.tool_calls
                    ],
                }
            )
            for call in message.tool_calls:
                result = execute_tool(call.function.name, call.function.arguments, self.ctx)
                tool_log.append(
                    {"tool": call.function.name, "arguments": call.function.arguments, "result": _summarize(result)}
                )
                for hit in result.get("results", []):
                    retrieved.setdefault(hit["chunk_id"], hit)
                if call.function.name == "get_document_info" and "source" in result:
                    documents[result["source"]] = result
                messages.append(
                    {"role": "tool", "tool_call_id": call.id, "content": json.dumps(result, ensure_ascii=False)}
                )

        return AgentResponse(
            answer=MAX_STEPS_ANSWER, retrieved=list(retrieved.values()), tool_calls=tool_log
        )


def _cited_sources(answer: str, retrieved: dict[str, dict], documents: dict[str, dict]) -> list[dict]:
    """Các tài liệu agent đã lấy qua tool mà tên file thực sự xuất hiện trong câu trả lời."""
    cited: dict[str, dict] = {}

    def entry_for(item: dict) -> dict:
        return cited.setdefault(
            item["source"],
            {"source": item["source"], "title": item["title"], "updated_at": item["updated_at"], "locations": []},
        )

    for hit in retrieved.values():
        if hit["source"] in answer:
            entry = entry_for(hit)
            location = f"trang {hit['page']}" if hit["page"] else hit["section"]
            if location and location not in entry["locations"]:
                entry["locations"].append(location)
    for source, info in documents.items():
        if source in answer:
            entry_for(info)
    return list(cited.values())


def _summarize(result: dict) -> dict:
    # Rút gọn kết quả tool để hiển thị vết gọi trên giao diện, không lặp lại toàn bộ nội dung chunk
    if "results" in result:
        return {
            "num_results": len(result["results"]),
            "hits": [
                {"source": r["source"], "section": r["section"], "page": r["page"], "score": r["score"]}
                for r in result["results"]
            ],
            **({"message": result["message"]} if "message" in result else {}),
        }
    return result
