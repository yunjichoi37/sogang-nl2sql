import streamlit as st


def init_inquiry_state():
    """건의/문의 상태 초기화"""
    if "inquiry_state" not in st.session_state:
        reset_inquiry_state()


def reset_inquiry_state():
    st.session_state.inquiry_state = {
        "type": None,           # "건의" / "문의"
        "category": None,       # "시설" / "학사" / "장학" / "시스템" / "학생생활" / "교무" / "기타"
        "is_complete": False,   # 구체화 완료 여부
        "summary": "",          # AI 요약본 (접수 시 사용)
        "missing_fields": [],   # 부족한 정보 필드
    }


def get_inquiry_state() -> dict:
    return st.session_state.get("inquiry_state", {})


def update_inquiry_state(**kwargs):
    for k, v in kwargs.items():
        st.session_state.inquiry_state[k] = v


def get_badge(inquiry_type: str | None, category: str | None) -> str | None:
    """분류 배지 텍스트 반환"""
    if not inquiry_type:
        return None
    type_emoji = "🟠" if inquiry_type == "건의" else "🔵"
    category_text = f" · {category}" if category else ""
    return f"{type_emoji} {inquiry_type}{category_text}"
