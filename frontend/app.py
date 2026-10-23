"""Giao diện chat Streamlit. Chạy: streamlit run frontend/app.py (backend phải đang chạy)."""

import os

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()
API_URL = os.getenv("API_URL", "http://127.0.0.1:8000").rstrip("/")

st.set_page_config(page_title="Trợ lý tài liệu nội bộ", page_icon="📚")
st.title("📚 Trợ lý hỏi đáp tài liệu nội bộ")
st.caption("Đặt câu hỏi về quy trình, chính sách. Câu trả lời luôn kèm nguồn trích dẫn.")


def call_api(method: str, path: str, **kwargs):
    """Gọi backend, trả về JSON hoặc None nếu lỗi (lỗi được hiển thị trên giao diện)."""
    try:
        resp = requests.request(method, f"{API_URL}{path}", timeout=120, **kwargs)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        st.error(f"Không gọi được backend tại {API_URL}: {exc}")
        return None


def render_details(data: dict) -> None:
    """Hiển thị nguồn trích dẫn và các tool agent đã gọi."""
    if data.get("sources"):
        with st.expander("Nguồn trích dẫn"):
            for s in data["sources"]:
                where = ", ".join(s["locations"])
                st.markdown(f"- **{s['title']}** (`{s['source']}`){' — ' + where if where else ''}, cập nhật {s['updated_at']}")
    if data.get("tool_calls"):
        with st.expander(f"Agent đã gọi {len(data['tool_calls'])} tool"):
            for call in data["tool_calls"]:
                st.markdown(f"**{call['tool']}** `{call['arguments']}`")
                st.json(call["result"], expanded=False)


with st.sidebar:
    st.header("Tài liệu")
    if st.button("Nạp lại tài liệu"):
        with st.spinner("Đang nạp..."):
            result = call_api("POST", "/ingest", json={"reset": True})
        if result:
            st.success(f"Đã nạp {len(result['files'])} file, {result['total_chunks']} chunk.")
            for name, err in result["errors"].items():
                st.warning(f"{name}: {err}")
    listing = call_api("GET", "/sources")
    if listing:
        if not listing["count"]:
            st.info("Chưa có tài liệu. Bấm 'Nạp lại tài liệu'.")
        for doc in listing["sources"]:
            st.markdown(f"- {doc['title']}  \n  `{doc['source']}` · {doc['updated_at']}")
    if st.button("Xóa hội thoại"):
        st.session_state.messages = []

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("details"):
            render_details(msg["details"])

if question := st.chat_input("Ví dụ: Thủ tục xin nghỉ phép năm như thế nào?"):
    history = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages]
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"):
        with st.spinner("Đang tìm trong tài liệu..."):
            data = call_api("POST", "/chat", json={"question": question, "history": history})
        if data:
            st.markdown(data["answer"])
            render_details(data)
            st.session_state.messages.append({"role": "assistant", "content": data["answer"], "details": data})
