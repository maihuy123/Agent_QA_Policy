# Trợ lý hỏi đáp tài liệu nội bộ dựa trên AI

Đồ án nhóm trong khóa AI Application Engineer. Hệ thống cho phép nhân viên đặt câu hỏi bằng ngôn ngữ tự nhiên về tài liệu nội bộ (quy trình, chính sách), nhận câu trả lời kèm nguồn trích dẫn. Khi không có thông tin trong tài liệu, hệ thống phải nói rõ thay vì bịa.

## Stack

- **Backend agent:** FastAPI, điều phối luồng xử lý và gọi tool
- **Frontend:** Streamlit (giao diện chat)
- **Knowledge base:** ChromaDB, lưu vector và metadata của các chunk
- **LLM và Embedding:** OpenAI API (platform.openai.com), gọi qua OpenAI SDK. Mặc định `gpt-4.1-mini` và `text-embedding-3-small`, đổi qua biến môi trường
- **Ngôn ngữ:** Python

## Luồng chính

1. **Ingestion (nạp tài liệu):** đọc file (PDF, DOCX, Markdown) → chunk, giữ metadata (tên file, trang, ngày cập nhật) → tạo embedding → lưu vào ChromaDB
2. **Query (hỏi đáp):** embedding câu hỏi bằng cùng model đã dùng khi nạp → ChromaDB trả về top-k chunk → LLM trả lời dựa trên chunk, kèm nguồn

## Tools của agent

- `search_documents`: tìm chunk liên quan trong ChromaDB
- `get_document_info`: lấy thông tin file gốc (tác giả, ngày cập nhật)
- `list_sources`: liệt kê tài liệu đang có trong knowledge base

## Quy ước khi viết code

- Mọi lệnh gọi model đi qua OpenAI SDK, không gọi HTTP trực tiếp
- Đọc cấu hình (API key, tên model, đường dẫn ChromaDB) từ biến môi trường (`.env`, mẫu ở `.env.example`), không hard-code
- Client OpenAI chỉ được tạo trong `src/clients.py`; ChromaDB chỉ được gọi qua `src/knowledge_base/store.py`
- Thêm tool mới: tạo file trong `src/tools/` định nghĩa `TOOL = Tool(...)` rồi đăng ký trong `src/tools/registry.py`
- Không commit API key. File `.env` phải nằm trong `.gitignore`
- Mỗi chunk phải có metadata nguồn để agent trích dẫn được
- Khi không tìm thấy chunk đủ liên quan, agent trả lời rằng không có thông tin, không tự suy đoán
- Viết docstring ngắn cho hàm công khai; comment bằng tiếng Việt hoặc tiếng Anh đều được, nhưng giữ nhất quán trong một file
- Giữ chunk size và top-k trong file cấu hình (`config.yaml`) để dễ thử nghiệm khi đánh giá
- Chạy test: `.venv\Scripts\python.exe -m pytest` (test không gọi OpenAI, dùng embedding giả)

## Đánh giá

- Bộ câu hỏi mẫu: khoảng 30–50 câu, mỗi câu có đáp án chuẩn và file nguồn đúng
- Chỉ số: tỷ lệ tìm đúng tài liệu, tỷ lệ trả lời đúng, tỷ lệ trích dẫn đúng nguồn
- Thử nhiều cấu hình chunk size và top-k, ghi kết quả vào file riêng
- Bộ câu hỏi: `evaluation/questions.jsonl`; chạy `python -m evaluation.run_eval`; kết quả ở `evaluation/results/<thời gian>/`

## Tài liệu tham chiếu

- Nội dung thuyết trình: `docs/presentation.md` (dàn ý 12 slide). Khi đổi chức năng, cập nhật phần liên quan trong file này.

## Khi làm việc với Claude

- Trước khi sửa code lớn, hãy đề xuất cách làm và chờ xác nhận
- Ưu tiên thay đổi nhỏ, dễ kiểm tra; chạy test hoặc thử câu hỏi mẫu sau mỗi thay đổi
- Nếu một yêu cầu mâu thuẫn với quy ước trong file này, hỏi lại trước khi làm