# pages/student_inquiry.py — 학생용 문의·건의 접수 페이지
import os
import csv
import uuid
from datetime import date

import streamlit as st

from core.classifier import classify, get_ai_response

SUBMISSIONS_PATH = "data/submissions/submissions.csv"
SUBMISSIONS_DIR = "data/submissions"

CATEGORY_DEPT = {
    "시설":    "시설팀",
    "학사":    "학사팀",
    "장학":    "장학팀",
    "시스템":  "IT지원팀",
    "학생생활": "학생처",
    "교무":    "교무처",
    "기타":    "학생처",
}


# ── CSV 저장 ────────────────────────────────────────────────
def _save_submission(inquiry_type: str, category: str, content: str) -> str:
    os.makedirs(SUBMISSIONS_DIR, exist_ok=True)
    receipt_no = f"REQ-{uuid.uuid4().hex[:6].upper()}"
    today = date.today().isoformat()
    file_exists = os.path.exists(SUBMISSIONS_PATH)

    with open(SUBMISSIONS_PATH, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["접수번호", "유형", "카테고리", "내용", "접수일", "상태"])
        if not file_exists:
            writer.writeheader()
        writer.writerow({
            "접수번호": receipt_no,
            "유형": inquiry_type,
            "카테고리": category,
            "내용": content,
            "접수일": today,
            "상태": "접수완료",
        })
    return receipt_no


# ── 배지 ────────────────────────────────────────────────────
def _badge(inquiry_type: str | None, category: str | None) -> str | None:
    if not inquiry_type:
        return None
    emoji = "🟠" if inquiry_type == "건의" else "🔵"
    cat = f" · {category}" if category else ""
    return f"{emoji} {inquiry_type}{cat}"


# ── 세션 초기화 ─────────────────────────────────────────────
def _init_state():
    if "inq_messages" not in st.session_state:
        st.session_state.inq_messages = []
    if "inq_classify" not in st.session_state:
        st.session_state.inq_classify = {
            "type": None, "category": None,
            "is_complete": False, "missing_fields": [],
        }
    if "inq_submitted" not in st.session_state:
        st.session_state.inq_submitted = False
    if "inq_receipt_no" not in st.session_state:
        st.session_state.inq_receipt_no = None


def _reset_state():
    st.session_state.inq_messages = []
    st.session_state.inq_classify = {
        "type": None, "category": None,
        "is_complete": False, "missing_fields": [],
    }
    st.session_state.inq_submitted = False
    st.session_state.inq_receipt_no = None


# ── 메인 렌더 ───────────────────────────────────────────────
def render():
    st.markdown("## 문의·건의 접수")
    st.caption("궁금한 점이나 불편한 점을 자유롭게 말씀해 주세요. AI가 도와드릴게요.")
    st.divider()

    _init_state()

    # ── 접수 완료 화면 ──────────────────────────────────────
    if st.session_state.inq_submitted:
        receipt_no = st.session_state.inq_receipt_no
        classify_result = st.session_state.inq_classify
        dept = CATEGORY_DEPT.get(classify_result.get("category", "기타"), "학생처")

        st.success(f"✅ 접수가 완료되었어요!")
        with st.container(border=True):
            col1, col2, col3 = st.columns(3)
            col1.metric("접수번호", receipt_no)
            col2.metric("담당 부서", dept)
            col3.metric("처리 예정", "3~5 영업일")

        st.info(f"📬 **{dept}**에서 검토 후 처리해 드릴게요. 접수번호를 기억해 두세요!")

        if st.button("새 문의·건의 작성", type="primary"):
            _reset_state()
            st.rerun()
        return

    # ── 분류 배지 ───────────────────────────────────────────
    classify_result = st.session_state.inq_classify
    badge = _badge(classify_result.get("type"), classify_result.get("category"))
    if badge:
        st.markdown(f"**현재 분류:** {badge}")

    # ── 대화 기록 렌더링 ────────────────────────────────────
    if not st.session_state.inq_messages:
        with st.chat_message("assistant"):
            st.write("안녕하세요! 학교 생활 중 불편한 점이나 궁금한 점을 말씀해 주세요. 문의·건의 접수를 도와드릴게요. 😊")

    for msg in st.session_state.inq_messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    # ── 접수 확인 버튼 (구체화 완료된 건의일 때) ────────────
    cr = st.session_state.inq_classify
    show_confirm = (
        cr.get("type") == "건의"
        and cr.get("is_complete")
        and not st.session_state.inq_submitted
        and len(st.session_state.inq_messages) > 0
    )
    if show_confirm:
        st.markdown("")
        col_yes, col_no = st.columns([1, 4])
        with col_yes:
            if st.button("✅ 네, 접수할게요", type="primary", use_container_width=True):
                # 마지막 사용자 메시지를 내용으로 저장
                content = next(
                    (m["content"] for m in reversed(st.session_state.inq_messages) if m["role"] == "user"),
                    ""
                )
                receipt_no = _save_submission(cr["type"], cr["category"], content)
                st.session_state.inq_receipt_no = receipt_no
                st.session_state.inq_submitted = True
                st.rerun()
        with col_no:
            if st.button("✏️ 내용 수정할게요", use_container_width=True):
                # 마지막 AI 메시지만 제거하고 다시 입력 유도
                st.session_state.inq_messages = [
                    m for m in st.session_state.inq_messages if not (
                        m["role"] == "assistant" and "접수하시겠어요" in m["content"]
                    )
                ]
                st.rerun()

    # ── 채팅 입력 ───────────────────────────────────────────
    if user_input := st.chat_input("내용을 입력하세요..."):
        st.session_state.inq_messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.write(user_input)

        with st.chat_message("assistant"):
            with st.spinner("분석 중..."):
                # 분류
                new_classify = classify(user_input)
                st.session_state.inq_classify.update(new_classify)

                # 배지 업데이트
                updated_badge = _badge(new_classify.get("type"), new_classify.get("category"))
                if updated_badge:
                    st.markdown(f"**분류:** {updated_badge}")

                # 응답 생성
                response = get_ai_response(st.session_state.inq_messages, new_classify)

            st.write(response)
            st.session_state.inq_messages.append({"role": "assistant", "content": response})

        st.rerun()