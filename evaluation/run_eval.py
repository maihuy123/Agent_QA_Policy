"""Đánh giá agent trên bộ câu hỏi mẫu với nhiều cấu hình chunk size và top-k.

Chạy từ thư mục gốc dự án:
    python -m evaluation.run_eval                                  # cấu hình trong config.yaml
    python -m evaluation.run_eval --chunk-sizes 400 800 1200 --top-ks 3 5
    python -m evaluation.run_eval --limit 5                        # chạy thử 5 câu đầu
    python -m evaluation.run_eval --retrieval-only --chunk-sizes 400 800 1200 --top-ks 3 5

Chi phí: chế độ đầy đủ gọi model chat 3-4 lần mỗi câu (agent + chấm điểm), khoảng 0,2 USD
cho 35 câu với gpt-4.1-mini. --retrieval-only chỉ gọi embedding, gần như miễn phí; dùng nó để dò
chunk size/top-k rồi mới chạy đầy đủ cho cấu hình tốt nhất.

Mỗi chunk size được nạp vào một collection riêng (eval_cs<size>) để không đụng dữ liệu chính.
Kết quả chi tiết lưu ở evaluation/results/<thời gian>/, bảng tổng hợp ở summary.md cùng thư mục.

Chỉ số:
- retrieval: câu hỏi nội dung (factual) có tìm ra đúng file nguồn trong các chunk agent lấy được.
- answer: câu trả lời đúng so với đáp án chuẩn (LLM chấm); câu ngoài phạm vi đúng khi agent từ chối.
- citation: câu trả lời trích dẫn đúng file nguồn; câu ngoài phạm vi đúng khi không trích dẫn file nào.
"""

import argparse
import json
import logging
from datetime import datetime
from pathlib import Path

from src.agent.agent import Agent
from src.clients import embed_texts, get_openai_client
from src.config import get_settings
from src.ingestion.pipeline import ingest_directory
from src.knowledge_base.store import KnowledgeBase

EVAL_DIR = Path(__file__).resolve().parent
OVERLAP_RATIO = 0.2  # overlap tính theo tỷ lệ để so sánh công bằng giữa các chunk size

JUDGE_PROMPT = """Bạn là giám khảo chấm câu trả lời của một trợ lý hỏi đáp tài liệu nội bộ.
Câu hỏi: {question}
Đáp án chuẩn: {expected}
Câu trả lời của trợ lý: {answer}

Quy tắc chấm:
- Nếu đáp án chuẩn là "Không có thông tin trong tài liệu", câu trả lời ĐÚNG khi trợ lý nói rõ không tìm thấy \
thông tin và không bịa nội dung; SAI nếu trợ lý đưa ra câu trả lời cụ thể.
- Ngược lại, câu trả lời ĐÚNG khi chứa đủ các ý chính và số liệu của đáp án chuẩn, không mâu thuẫn với đáp án. \
Thông tin thêm không sai thì không bị trừ. Bỏ qua phần trích dẫn nguồn khi chấm.
Trả về JSON: {{"correct": true hoặc false, "reason": "<giải thích ngắn>"}}"""


def load_questions(path: Path, limit: int | None = None) -> list[dict]:
    """Đọc bộ câu hỏi dạng JSONL."""
    with open(path, encoding="utf-8") as f:
        questions = [json.loads(line) for line in f if line.strip()]
    return questions[:limit] if limit else questions


def judge(question: str, expected: str, answer: str, model: str) -> dict:
    """Dùng LLM chấm đúng/sai câu trả lời so với đáp án chuẩn."""
    response = get_openai_client().chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": JUDGE_PROMPT.format(question=question, expected=expected, answer=answer)}],
        response_format={"type": "json_object"},
        temperature=0,
    )
    try:
        verdict = json.loads(response.choices[0].message.content)
        return {"correct": bool(verdict.get("correct")), "reason": str(verdict.get("reason", ""))}
    except (json.JSONDecodeError, TypeError):
        return {"correct": False, "reason": "Giám khảo trả về JSON không hợp lệ"}


def evaluate_question(agent: Agent, q: dict, known_sources: list[str], judge_model: str) -> dict:
    """Hỏi agent một câu và tính ba chỉ số cho câu đó."""
    response = agent.ask(q["question"])
    expected = q["expected_source"]
    retrieved = sorted({r["source"] for r in response.retrieved})
    cited = sorted(s for s in known_sources if s in response.answer)

    if expected is None:
        citation_ok = not cited
    else:
        citation_ok = expected in cited
    retrieval_ok = (expected in retrieved) if q["type"] == "factual" else None
    verdict = judge(q["question"], q["expected_answer"], response.answer, judge_model)

    return {
        **q,
        "answer": response.answer,
        "retrieved_sources": retrieved,
        "cited_sources": cited,
        "tools_used": [c["tool"] for c in response.tool_calls],
        "retrieval_ok": retrieval_ok,
        "answer_ok": verdict["correct"],
        "judge_reason": verdict["reason"],
        "citation_ok": citation_ok,
    }


def evaluate_retrieval(kb: KnowledgeBase, questions: list[dict], top_k: int, max_distance: float) -> list[dict]:
    """Chỉ đo tìm đúng tài liệu: embedding câu hỏi rồi tra ChromaDB, không gọi model chat."""
    rows = []
    in_scope = [q for q in questions if q["expected_source"] is not None]
    vectors = embed_texts([q["question"] for q in in_scope])
    for q, vector in zip(in_scope, vectors):
        hits = [h for h in kb.query(vector, top_k) if h.distance <= max_distance]
        sources = [h.metadata["source"] for h in hits]
        rows.append({
            **q,
            "retrieved_sources": sources,
            "rank": sources.index(q["expected_source"]) + 1 if q["expected_source"] in sources else None,
            "retrieval_ok": q["expected_source"] in sources,
            "answer_ok": None,
            "citation_ok": None,
        })
    return rows


def _evaluate_agent(kb, settings, questions: list[dict], known_sources: list[str], judge_model: str) -> list[dict]:
    """Chạy agent đầy đủ trên từng câu hỏi (tốn phí gọi model chat)."""
    agent = Agent(settings=settings, kb=kb)
    mark = lambda v: "-" if v is None else ("✓" if v else "✗")
    rows = []
    for i, q in enumerate(questions, start=1):
        row = evaluate_question(agent, q, known_sources, judge_model)
        rows.append(row)
        print(
            f"[cs={settings.chunk_size} k={settings.top_k}] {i}/{len(questions)} {q['id']}: "
            f"retrieval {mark(row['retrieval_ok'])} answer {mark(row['answer_ok'])} citation {mark(row['citation_ok'])}",
            flush=True,
        )
    return rows


def _rate(rows: list[dict], key: str) -> float | None:
    values = [r[key] for r in rows if r[key] is not None]
    return round(sum(values) / len(values), 3) if values else None


def run(
    chunk_sizes: list[int],
    top_ks: list[int],
    limit: int | None,
    judge_model: str | None,
    retrieval_only: bool = False,
) -> Path:
    """Chạy toàn bộ lưới cấu hình, trả về thư mục chứa kết quả."""
    base = get_settings()
    judge_model = judge_model or base.chat_model
    questions = load_questions(EVAL_DIR / "questions.jsonl", limit)
    out_dir = EVAL_DIR / "results" / datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)
    summary_rows = []

    for chunk_size in chunk_sizes:
        settings = base.with_overrides(
            chunk_size=chunk_size,
            chunk_overlap=int(chunk_size * OVERLAP_RATIO),
            collection_name=f"eval_cs{chunk_size}",
        )
        kb = KnowledgeBase(settings)
        ingest = ingest_directory(settings=settings, kb=kb, reset=True)
        if ingest["errors"]:
            raise RuntimeError(f"Nạp tài liệu lỗi: {ingest['errors']}")
        known_sources = [d["source"] for d in kb.list_sources()]

        for top_k in top_ks:
            if retrieval_only:
                rows = evaluate_retrieval(kb, questions, top_k, settings.max_distance)
                print(f"[cs={chunk_size} k={top_k}] tìm đúng {sum(r['retrieval_ok'] for r in rows)}/{len(rows)}")
            else:
                rows = _evaluate_agent(kb, settings.with_overrides(top_k=top_k), questions, known_sources, judge_model)
            metrics = {
                "chunk_size": chunk_size,
                "chunk_overlap": settings.chunk_overlap,
                "top_k": top_k,
                "num_chunks": ingest["total_chunks"],
                "retrieval": _rate(rows, "retrieval_ok"),
                "answer": _rate(rows, "answer_ok"),
                "citation": _rate(rows, "citation_ok"),
            }
            summary_rows.append(metrics)
            with open(out_dir / f"cs{chunk_size}_k{top_k}.json", "w", encoding="utf-8") as f:
                json.dump({"metrics": metrics, "model": settings.chat_model, "results": rows}, f, ensure_ascii=False, indent=2)

    _write_summary(out_dir, summary_rows, base.chat_model, base.embedding_model, len(questions))
    return out_dir


def _write_summary(out_dir: Path, rows: list[dict], chat_model: str, embedding_model: str, n: int) -> None:
    pct = lambda v: "-" if v is None else f"{v * 100:.1f}%"
    lines = [
        f"# Kết quả đánh giá {out_dir.name}",
        "",
        f"- Model chat: `{chat_model}`, embedding: `{embedding_model}`",
        f"- Số câu hỏi: {n}",
        "",
        "| chunk_size | overlap | top_k | số chunk | tìm đúng tài liệu | trả lời đúng | trích dẫn đúng |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['chunk_size']} | {r['chunk_overlap']} | {r['top_k']} | {r['num_chunks']} | "
            f"{pct(r['retrieval'])} | {pct(r['answer'])} | {pct(r['citation'])} |"
        )
    (out_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


def main() -> None:
    base = get_settings()
    parser = argparse.ArgumentParser(description="Đánh giá agent hỏi đáp tài liệu")
    parser.add_argument("--chunk-sizes", type=int, nargs="+", default=[base.chunk_size])
    parser.add_argument("--top-ks", type=int, nargs="+", default=[base.top_k])
    parser.add_argument("--limit", type=int, help="chỉ chạy N câu đầu để thử nhanh")
    parser.add_argument("--judge-model", help="model chấm điểm (mặc định: OPENAI_CHAT_MODEL)")
    parser.add_argument("--retrieval-only", action="store_true", help="chỉ đo tìm đúng tài liệu, không gọi model chat")
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING)
    out_dir = run(args.chunk_sizes, args.top_ks, args.limit, args.judge_model, args.retrieval_only)
    print(f"\nĐã lưu kết quả vào {out_dir}")


if __name__ == "__main__":
    main()
