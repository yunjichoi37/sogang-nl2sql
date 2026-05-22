# pages/message_send.py — 메시지 발송 탭
import pandas as pd
import streamlit as st

from core.message_generator import generate_message

DEPARTMENTS = [
    "학생처", "장학팀", "학사팀", "교무처",
    "IT지원팀", "시설팀", "총무팀", "교직원 공통",
]


def render():
    st.markdown("## 💬 카카오워크 메시지 발송")
    st.caption("조회된 학생 데이터를 바탕으로 메시지 초안을 생성하고 발송하세요.")
    st.divider()

    col_left, col_right = st.columns([1, 1], gap="large")

    # ── 왼쪽: 입력 ──────────────────────────────────────────
    with col_left:
        st.markdown("### ✏️ 메시지 설정")

        # 데이터 조회 탭에서 넘어온 데이터 확인
        last_df = st.session_state.get("last_df")
        use_last = False

        if last_df is not None:
            st.success(f"📊 데이터 조회 탭에서 {len(last_df)}명의 데이터가 연결됐어요.")
            use_last = st.checkbox("조회된 학생 데이터를 수신자 기반으로 활용", value=True)
            if use_last:
                st.dataframe(last_df.head(5), use_container_width=True)
                if len(last_df) > 5:
                    st.caption(f"... 외 {len(last_df) - 5}명")
        else:
            st.info("💡 데이터 조회 탭에서 학생을 조회하면 자동으로 연결돼요.")

        st.markdown("")
        department = st.selectbox("발송 부서", DEPARTMENTS)

        instruction = st.text_area(
            "메시지 내용 지시",
            placeholder="예: 장학금 신청 기간 안내 메시지를 작성해줘. 신청 기간은 12월 1일~15일이고, 포털에서 신청 가능해.",
            height=120,
        )

        if st.button("🤖 메시지 초안 생성", type="primary", use_container_width=True):
            if not instruction:
                st.warning("메시지 내용 지시를 입력해주세요.")
            else:
                with st.spinner("메시지 초안 생성 중..."):
                    df_to_use = last_df if use_last and last_df is not None else None
                    draft = generate_message(
                        instruction=instruction,
                        df=df_to_use,
                        department=department,
                    )
                st.session_state.message_draft = draft

    # ── 오른쪽: 미리보기 + 발송 ────────────────────────────
    with col_right:
        st.markdown("### 📱 메시지 미리보기")

        draft = st.session_state.get("message_draft", "")

        if draft:
            edited = st.text_area(
                "초안을 자유롭게 수정하세요",
                value=draft,
                height=320,
                key="edited_draft",
            )

            st.markdown("")
            col_copy, col_send = st.columns([1, 1])

            with col_copy:
                if st.button("📋 복사", use_container_width=True):
                    st.code(edited)
                    st.caption("위 내용을 복사해서 카카오워크에 붙여넣으세요.")

            with col_send:
                if st.button("📨 발송 (Mock)", type="primary", use_container_width=True):
                    recipient_count = len(last_df) if use_last and last_df is not None else "전체"
                    st.success(f"✅ {recipient_count}명에게 발송 완료! (Mock)")
                    st.caption("실제 카카오워크 API 연동은 추후 예정입니다.")
                    st.balloons()

            # 발송 이력
            if "send_history" not in st.session_state:
                st.session_state.send_history = []

        else:
            st.markdown(
                """
                <div style='
                    border: 1.5px dashed #ccc;
                    border-radius: 12px;
                    padding: 60px 20px;
                    text-align: center;
                    color: #aaa;
                '>
                    ← 왼쪽에서 메시지 초안을 생성해주세요
                </div>
                """,
                unsafe_allow_html=True,
            )