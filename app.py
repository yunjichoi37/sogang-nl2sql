# app.py — 사이드바 + 페이지 라우팅
import streamlit as st

st.set_page_config(
    page_title="서강대학교 교직원 AI 에이전트",
    layout="wide",
)

st.markdown("""
    <style>
    [data-testid="stSidebarNav"] { display: none; }

    /* 사이드바 버튼 스타일 — 라디오처럼 보이게 */
    div[data-testid="stSidebar"] .stButton button {
        background: none;
        border: none;
        color: inherit;
        text-align: left;
        padding: 0.3rem 0.5rem;
        width: 100%;
        font-size: 0.95rem;
        cursor: pointer;
    }
    div[data-testid="stSidebar"] .stButton button:hover {
        background-color: rgba(151, 166, 195, 0.15);
        border-radius: 4px;
    }
    div[data-testid="stSidebar"] .stButton button:focus {
        box-shadow: none;
    }
    </style>
""", unsafe_allow_html=True)

# ── 현재 페이지 세션 초기화 ────────────────────────────────
if "current_page" not in st.session_state:
    st.session_state.current_page = "데이터 조회"

# ── 사이드바 ───────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 서강대학교\n교직원용 AI 에이전트")
    st.divider()

    st.caption("👨‍💼 교직원")
    for label in ["데이터 조회", "빠른 조회", "문의·건의 현황"]:
        if st.button(label, key=f"btn_{label}", use_container_width=True):
            st.session_state.current_page = label

    st.divider()

    st.caption("🎓 학생")
    if st.button("문의·건의 접수", key="btn_student", use_container_width=True):
        st.session_state.current_page = "문의·건의 접수"

    st.divider()
    st.caption("Powered by Groq · LLaMA 3.3")
    st.caption("서강대학교 생성형 AI 공모전")

# ── 페이지 라우팅 ──────────────────────────────────────────
page = st.session_state.current_page

if page == "데이터 조회":
    from pages.data_query import render
    render()

elif page == "빠른 조회":
    from pages.quick_query import render
    render()

elif page == "문의·건의 현황":
    from pages.inquiry_dashboard import render
    render()

elif page == "문의·건의 접수":
    from pages.student_inquiry import render
    render()