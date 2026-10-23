import json

from evaluation import run_eval
from evaluation.run_eval import EVAL_DIR, load_questions


def test_question_set_is_well_formed():
    questions = load_questions(EVAL_DIR / "questions.jsonl")
    assert 30 <= len(questions) <= 50
    assert len({q["id"] for q in questions}) == len(questions)
    sources = {p.name for p in (EVAL_DIR.parent / "data" / "raw").iterdir()}
    for q in questions:
        assert q["type"] in {"factual", "metadata", "out_of_scope"}
        assert q["question"] and q["expected_answer"]
        if q["type"] == "out_of_scope":
            assert q["expected_source"] is None
        else:
            assert q["expected_source"] in sources


def test_retrieval_only_skips_chat_model(tmp_path, kb, settings, monkeypatch):
    from src.ingestion.pipeline import ingest_directory
    from tests.conftest import fake_embed
    from tests.test_tools import _write_docs

    _write_docs(tmp_path / "raw")
    ingest_directory(tmp_path / "raw", settings=settings, kb=kb)
    monkeypatch.setattr(run_eval, "embed_texts", fake_embed)
    monkeypatch.setattr(run_eval, "get_openai_client", lambda: (_ for _ in ()).throw(AssertionError("không được gọi")))
    questions = [
        {"id": "a", "type": "factual", "question": "mật khẩu dài bao nhiêu ký tự", "expected_answer": "", "expected_source": "bao_mat.md"},
        {"id": "b", "type": "out_of_scope", "question": "lương", "expected_answer": "", "expected_source": None},
    ]
    rows = run_eval.evaluate_retrieval(kb, questions, top_k=3, max_distance=0.9)
    assert [r["id"] for r in rows] == ["a"]
    assert rows[0]["retrieval_ok"] and rows[0]["rank"] == 1


def test_evaluate_question_scores(monkeypatch):
    class FakeAgent:
        def ask(self, question):
            from src.agent.agent import AgentResponse

            return AgentResponse(
                answer="12 ngày [Nguồn: a.md, mục X]",
                retrieved=[{"source": "a.md"}, {"source": "b.md"}],
                tool_calls=[{"tool": "search_documents"}],
            )

    monkeypatch.setattr(run_eval, "judge", lambda *a: {"correct": True, "reason": ""})
    q = {"id": "x", "type": "factual", "question": "?", "expected_answer": "12", "expected_source": "a.md"}
    row = run_eval.evaluate_question(FakeAgent(), q, ["a.md", "b.md"], "m")
    assert row["retrieval_ok"] and row["answer_ok"] and row["citation_ok"]
    assert row["cited_sources"] == ["a.md"]

    out = {**q, "type": "out_of_scope", "expected_source": None}
    assert run_eval.evaluate_question(FakeAgent(), out, ["a.md"], "m")["citation_ok"] is False
    json.dumps(row, ensure_ascii=False)  # kết quả phải ghi được ra JSON
