# Trợ lý hỏi đáp tài liệu nội bộ dựa trên AI

Nhân viên đặt câu hỏi bằng ngôn ngữ tự nhiên về quy trình, chính sách nội bộ và nhận câu trả lời kèm nguồn trích dẫn. Khi tài liệu không có thông tin, hệ thống nói rõ là không tìm thấy thay vì đoán.

Stack: FastAPI (agent) · Streamlit (chat) · ChromaDB (vector store) · OpenAI API qua OpenAI SDK.

## Cài đặt

Yêu cầu Python 3.11 trở lên (đã thử trên 3.14).

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env      # rồi điền OPENAI_API_KEY
```

ChromaDB chạy cục bộ, không cần tài khoản hay key. Dữ liệu nằm trong thư mục `chroma_db/`.

## Chạy

```powershell
# 1. Nạp tài liệu trong data/raw vào ChromaDB
python -m src.ingestion.pipeline --reset

# 2. Backend (terminal 1)
uvicorn src.api.main:app --reload

# 3. Giao diện chat (terminal 2)
streamlit run frontend/app.py
```

Mở http://localhost:8501 để chat, hoặc xem tài liệu API ở http://127.0.0.1:8000/docs.

Thêm tài liệu mới: chép file PDF, DOCX hoặc Markdown vào `data/raw/`, rồi chạy lại bước 1 hoặc bấm "Nạp lại tài liệu" trên giao diện. File Markdown có thể khai báo `title`, `author`, `updated` ở front matter.

## Cấu trúc

```
config.yaml               chunk size, overlap, top-k, ngưỡng liên quan, số bước agent
src/
  config.py               đọc .env và config.yaml
  clients.py              client OpenAI và hàm embedding dùng chung
  ingestion/              loaders (PDF/DOCX/MD) → chunker → pipeline
  knowledge_base/store.py lớp bọc ChromaDB
  tools/                  base.py (khung Tool), từng tool một file, registry.py
  agent/                  vòng lặp function calling, system prompt
  api/main.py             FastAPI: /chat, /sources, /ingest, /health
frontend/app.py           Streamlit
evaluation/               questions.jsonl, run_eval.py, results/
data/raw/                 tài liệu mẫu (công ty giả lập)
scripts/                  tiện ích, ví dụ tạo file DOCX mẫu
tests/                    pytest, không gọi OpenAI
```

## Thêm một tool mới

1. Tạo `src/tools/ten_tool.py`, viết hàm `def ten_tool(ctx: ToolContext, ...) -> dict` và khai báo `TOOL = Tool(name=..., description=..., parameters=<JSON schema>, handler=ten_tool)`.
2. Thêm module vào tuple trong `src/tools/registry.py`.

Agent sẽ tự thấy tool mới ở lần chạy sau.

## Đánh giá

```powershell
python -m evaluation.run_eval --limit 5                              # chạy thử nhanh
python -m evaluation.run_eval --retrieval-only --chunk-sizes 400 800 1200 --top-ks 3 5   # chỉ embedding, gần như miễn phí
python -m evaluation.run_eval                                        # đầy đủ, cấu hình trong config.yaml
```

Mỗi lần chạy tạo thư mục `evaluation/results/<thời gian>/`, gồm chi tiết từng câu (JSON) và bảng tổng hợp `summary.md` với ba chỉ số: tìm đúng tài liệu, trả lời đúng (LLM chấm), trích dẫn đúng nguồn.

Chế độ đầy đủ gọi model chat 3–4 lần mỗi câu, mỗi cấu hình chạy riêng. Nên dò chunk size và top-k bằng `--retrieval-only` trước, rồi mới chạy đầy đủ cho cấu hình tốt nhất.

## Test

```powershell
python -m pytest
```
