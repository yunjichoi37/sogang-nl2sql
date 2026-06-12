# pages/data_query.py — 데이터 조회 탭
import io
from datetime import datetime

import pandas as pd
import streamlit as st

from core.sql_agent import run_query_stream


def render():
    st.markdown("## 데이터 조회")
    st.caption("자연어로 학사 DB를 조회하세요.")
    st.divider()

    if "query_messages" not in st.session_state:
        st.session_state.query_messages = [
            {"role": "assistant", "content": "안녕하세요! 학사 데이터베이스에 대해 무엇이든 질문해 주세요.\n\n예시: '컴퓨터공학과 학생이 몇 명이야?', '학과별 평균 학점을 보여줘'"}
        ]

    for msg in st.session_state.query_messages:
        _render_message(msg)

    if user_input := st.chat_input("질문을 입력하세요..."):
        st.session_state.query_messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.write(user_input)

        with st.chat_message("assistant"):
            result = {}
            answer = st.write_stream(run_query_stream(user_input, result))

            if "error" in result:
                st.error(f"오류 발생: {result['error']}")
                st.session_state.query_messages.append({
                    "role": "assistant",
                    "content": f"오류: {result['error']}",
                })
                return

            if result.get("relevant_tables"):
                with st.expander(f"📌 참조 테이블: {', '.join(result['relevant_tables'])}", expanded=False):
                    if result.get("table_meta"):
                        st.code(result["table_meta"])
                    if result.get("rel_meta"):
                        st.markdown(result["rel_meta"])

            if result.get("intermediate_steps"):
                with st.expander("🔍 Agent 사고 흐름", expanded=False):
                    for step in result["intermediate_steps"]:
                        st.markdown(f"**SQL:** `{step.get('input', {}).get('sql_query', step.get('input', ''))}`")
                        st.markdown(f"**결과:** {step.get('output', '')}")
                        st.divider()

            csv_str = None
            csv_filename = None
            if result.get("df") is not None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                csv_str = result["df"].to_csv(index=False, encoding="utf-8-sig")
                csv_filename = f"result_{timestamp}.csv"
                st.dataframe(result["df"], use_container_width=True)
                st.download_button(
                    label="CSV 다운로드",
                    data=csv_str,
                    file_name=csv_filename,
                    mime="text/csv",
                )

            _render_chart(result)

            st.session_state.query_messages.append({
                "role": "assistant",
                "content": answer,
                "csv_str": csv_str,
                "csv_filename": csv_filename,
                "relevant_tables": result.get("relevant_tables", []),
                "table_meta": result.get("table_meta", ""),
                "rel_meta": result.get("rel_meta", ""),
                "intermediate_steps": result.get("intermediate_steps", []),
                "chart_config": result.get("chart_config", {"possible": False}),
            })


def _render_message(msg: dict):
    with st.chat_message(msg["role"]):
        if msg.get("relevant_tables"):
            with st.expander(f"📌 참조 테이블: {', '.join(msg['relevant_tables'])}", expanded=False):
                if msg.get("table_meta"):
                    st.code(msg["table_meta"])
                if msg.get("rel_meta"):
                    st.markdown(msg["rel_meta"])

        if msg.get("intermediate_steps"):
            with st.expander("🔍 Agent 사고 흐름", expanded=False):
                for step in msg["intermediate_steps"]:
                    st.markdown(f"**SQL:** `{step.get('input', {}).get('sql_query', step.get('input', ''))}`")
                    st.markdown(f"**결과:** {step.get('output', '')}")
                    st.divider()

        st.write(msg["content"])

        if msg.get("csv_str"):
            try:
                df = pd.read_csv(io.StringIO(msg["csv_str"]))
                st.dataframe(df, use_container_width=True)
                st.download_button(
                    label="CSV 다운로드",
                    data=msg["csv_str"],
                    file_name=msg.get("csv_filename", "result.csv"),
                    mime="text/csv",
                    key=f"dl_{msg.get('csv_filename', 'result')}",
                )
            except Exception:
                pass

        _render_chart(msg)


def _render_chart(data: dict):
    chart_config = data.get("chart_config", {})
    if not chart_config.get("possible"):
        return

    df = data.get("df")
    if df is None and data.get("csv_str"):
        try:
            df = pd.read_csv(io.StringIO(data["csv_str"]))
        except Exception:
            return
    if df is None:
        return

    x, y = chart_config["x"], chart_config["y"]
    chart_type = chart_config["type"]

    if x not in df.columns or y not in df.columns:
        return

    st.markdown("**📊 차트**")
    if chart_type == "bar":
        st.bar_chart(df.set_index(x)[y])
    elif chart_type == "line":
        st.line_chart(df.set_index(x)[y])
    elif chart_type == "pie":
        import plotly.express as px
        fig = px.pie(df, names=x, values=y)
        st.plotly_chart(fig, use_container_width=True)