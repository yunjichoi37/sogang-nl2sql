# app.py — 사이드바 + 페이지 라우팅
import streamlit as st

st.set_page_config(
    page_title="서강대학교 교직원 AI 에이전트",
    page_icon="🏫",
    layout="wide",
)

st.markdown("""
    <style>
    [data-testid="stSidebarNav"] { display: none; }
    </style>
""", unsafe_allow_html=True)

# ── 사이드바 ───────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 서강대학교\n교직원용 AI 에이전트")
    st.divider()

    menu = st.radio(
        "메뉴",
        options=["데이터 조회", "빠른 조회", "문의·건의 현황"],
        label_visibility="collapsed",
    )

    st.divider()
    st.caption("Powered by Groq · LLaMA 3.3")
    st.caption("서강대학교 생성형 AI 공모전")

# ── 페이지 라우팅 ──────────────────────────────────────────
if menu == "빠른 조회":
    from pages.quick_query import render
    render()

elif menu == "데이터 조회":
    from pages.data_query import render
    render()
    
elif menu == "문의·건의 현황":
    from pages.inquiry_dashboard import render
    render()