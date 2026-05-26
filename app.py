# app.py — 사이드바 + 페이지 라우팅
import streamlit as st

st.set_page_config(
    page_title="서강대 교직원 AI 플랫폼",
    page_icon="🏫",
    layout="wide",
)

# ── 사이드바 ───────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🏫 서강대\n### 교직원 AI 플랫폼")
    st.divider()

    menu = st.radio(
        "메뉴",
        options=["📊 데이터 조회", "💬 메시지 발송", "📋 건의·문의 현황"],
        label_visibility="collapsed",
    )

    st.divider()
    st.caption("Powered by Groq · LLaMA 3.3")
    st.caption("서강대학교 생성형 AI 공모전")

# ── 페이지 라우팅 ──────────────────────────────────────────
if menu == "📊 데이터 조회":
    from pages.data_query import render
    render()

elif menu == "💬 메시지 발송":
    from pages.message_send import render
    render()

elif menu == "📋 건의·문의 현황":
    from pages.inquiry_dashboard import render
    render()