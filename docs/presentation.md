# Trợ lý hỏi đáp tài liệu nội bộ dựa trên AI

Dàn ý thuyết trình 12 slide, khoảng 10–15 phút. Phần "Ghi chú" là lời nói của người thuyết trình, không đưa lên slide.

---

## Slide 1: Trang tiêu đề

- Tên đề tài: *Trợ lý hỏi đáp tài liệu nội bộ dựa trên AI*
- Tên nhóm, thành viên, khóa học AI Application Engineer

---

## Slide 2: Vấn đề

- Tài liệu nội bộ nằm rải rác: Confluence, Drive, email, file PDF/Word
- Nhân viên mới mất nhiều giờ để tìm một quy trình hoặc chính sách
- Câu hỏi giống nhau được hỏi lặp đi lặp lại với đồng nghiệp cũ

*Ghi chú: Mở đầu bằng một tình huống cụ thể, ví dụ "Nhân viên mới hỏi: làm sao xin nghỉ phép?", để khán giả dễ liên hệ.*

---

## Slide 3: Mục tiêu

- Người dùng đặt câu hỏi bằng ngôn ngữ tự nhiên
- Hệ thống trả lời ngay, kèm nguồn trích dẫn để kiểm chứng
- Khi không tìm thấy thông tin, hệ thống nói rõ thay vì bịa câu trả lời

---

## Slide 4: Kiến trúc tổng quan

- Frontend: giao diện chat Streamlit
- Backend: API agent (FastAPI) điều phối luồng xử lý
- Knowledge base: ChromaDB lưu các đoạn tài liệu đã được chuyển thành vector
- LLM: OpenAI API (`gpt-4.1-mini` cho chat, `text-embedding-3-small` cho embedding), gọi qua OpenAI SDK

*Ghi chú: Vẽ sơ đồ luồng: Người dùng → Frontend → Agent → ChromaDB → LLM → Câu trả lời kèm nguồn.*

---

## Slide 5: Các khái niệm cốt lõi

- **Chunk**: cắt tài liệu dài thành các đoạn nhỏ, ví dụ 800 ký tự mỗi đoạn, hai đoạn liền nhau lặp lại một phần để không mất ý ở chỗ cắt
- **Embedding**: chuyển một đoạn văn thành dãy số, sao cho các đoạn có ý nghĩa gần nhau thì dãy số cũng gần nhau
- **Vector**: chính là dãy số đó; ChromaDB dùng để tìm các đoạn gần nghĩa nhất với câu hỏi
- **RAG**: tìm đoạn liên quan trước, rồi đưa cho LLM đọc và trả lời dựa trên đoạn đó

*Ghi chú: Dùng ví dụ đời thường: "Tìm sách trong thư viện theo chủ đề, không theo tên sách chính xác." Đây là slide quan trọng nhất để khán giả hiểu phần sau.*

---

## Slide 6: Luồng nạp tài liệu (Ingestion)

- Bước 1: Đọc file (PDF, DOCX, Markdown)
- Bước 2: Chunk, giữ metadata (tên file, trang, ngày cập nhật)
- Bước 3: Tạo embedding cho từng chunk bằng model embedding của OpenAI (kèm tên tài liệu và tên mục để tăng ngữ cảnh)
- Bước 4: Lưu vector và metadata vào ChromaDB

---

## Slide 7: Luồng hỏi đáp (Query)

- Bước 1: Người dùng đặt câu hỏi
- Bước 2: Tạo embedding cho câu hỏi
- Bước 3: ChromaDB trả về top-k chunk liên quan nhất; chunk có khoảng cách vượt ngưỡng bị loại
- Bước 4: LLM nhận câu hỏi và các chunk, sinh câu trả lời kèm nguồn; không còn chunk nào thì trả lời "không tìm thấy thông tin"

---

## Slide 8: Agent và Tools

- Agent không chỉ tìm kiếm mà còn chọn công cụ phù hợp:
  - `search_documents`: tìm trong knowledge base
  - `get_document_info`: lấy thông tin file gốc (tác giả, ngày cập nhật)
  - `list_sources`: liệt kê tài liệu đang có
- Agent quyết định khi nào cần gọi tool, và có thể gọi nhiều tool trong một lượt hỏi
- Tool được thiết kế để tái sử dụng: mỗi tool là một file riêng, thêm tool mới chỉ cần khai báo và đăng ký

*Ghi chú: Đây là phần thể hiện tính "agent". Có thể cho ví dụ một câu hỏi cần gọi hai tool liên tiếp.*

---

## Slide 9: Demo

- Câu hỏi có đáp án rõ ràng, có trích dẫn
- Câu hỏi không có trong tài liệu, hệ thống từ chối trả lời
- Câu hỏi mơ hồ, hệ thống hỏi lại

---

## Slide 10: Đánh giá chất lượng

- Bộ câu hỏi mẫu 35 câu với đáp án chuẩn: 29 câu nội dung, 2 câu về thông tin tài liệu, 4 câu ngoài phạm vi
- Trả lời đúng hay sai do một LLM chấm, so với đáp án chuẩn
- Chỉ số: tỷ lệ tìm đúng tài liệu, tỷ lệ trả lời đúng, tỷ lệ trích dẫn đúng nguồn
- Thử nghiệm các cấu hình khác nhau: kích thước chunk, số lượng top-k
- Kết quả tìm đúng tài liệu (31 câu có nguồn): top-k=3 đạt 93,5%, top-k=5 đạt 96,8%; chunk size 400/800/1200 cho kết quả như nhau vì tài liệu mẫu chia mục ngắn

- Đánh giá đầy đủ qua agent (chunk 800, top-k 5, 35 câu): tìm đúng tài liệu 100%, trả lời đúng 97,1% (34/35), trích dẫn đúng 100%; cả 4 câu ngoài phạm vi đều được từ chối đúng
- Qua agent, tỷ lệ tìm đúng cao hơn tra cứu trực tiếp (100% so với 96,8%) vì agent tự viết lại câu truy vấn

*Ghi chú: Câu duy nhất bị chấm sai (q19) thực ra trả lời đúng ý chính "phản hồi trong 30 phút", nhưng thiếu chi tiết khung giờ 9h–17h có trong đáp án chuẩn. Đây là ví dụ để nói về độ khắt khe của LLM khi chấm. Bảng chi tiết trong `evaluation/results/`.*

---

## Slide 11: Hạn chế và hướng phát triển

- Hạn chế: tài liệu scan chất lượng thấp, bảng biểu phức tạp khó chunk đúng (ví dụ thực tế: câu hỏi số máy lẻ IT nằm trong bảng bị xếp hạng 7, ngoài top-5)
- Hạn chế: chỉ dùng ngưỡng khoảng cách thì không tách được câu ngoài phạm vi, vì khoảng cách của chúng chồng lấn với câu hợp lệ; việc từ chối trả lời phải dựa thêm vào LLM
- Hạn chế: chi phí API tăng theo số lượt hỏi
- Hướng phát triển: phân quyền theo phòng ban, cập nhật tài liệu tự động, thêm bước reranking

---

## Slide 12: Tổng kết và Q&A

- Đã làm được: nạp tài liệu, hỏi đáp có trích dẫn, agent gọi tool
- Bài học chính nhóm rút ra
- Cảm ơn và nhận câu hỏi
