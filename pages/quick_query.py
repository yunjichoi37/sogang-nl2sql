# pages/quick_query.py — 빠른 조회 탭
import sqlite3
import pandas as pd
import streamlit as st

DB_PATH = "data/db/sogang_university.db"

DEPT_LIST = [
    "AI기반자유전공학부", "SCIENCE기반자유전공학부", "경영학부(경영학전공)",
    "경제학과", "국어국문학과", "글로벌한국학부", "기계공학과", "물리학과",
    "미디어&엔터테인먼트학과", "사학과", "사회학과", "생명과학과", "수학과",
    "시스템반도체공학과", "신문방송학과", "심리학과", "아트&테크놀로지학과",
    "인공지능학과", "인문학기반자유전공학부", "전자공학과", "정치외교학과",
    "종교학과", "중국문화학과", "철학과", "컴퓨터공학과", "화공생명공학과",
    "화학과", "유럽문화학과",
]

SEMESTER_LIST = ["1학기", "2학기"]

GPA_CASE = """CASE t.grade
    WHEN 'A+' THEN 4.3 WHEN 'A0' THEN 4.0 WHEN 'A-' THEN 3.7
    WHEN 'B+' THEN 3.3 WHEN 'B0' THEN 3.0 WHEN 'B-' THEN 2.7
    WHEN 'C+' THEN 2.3 WHEN 'C0' THEN 2.0 WHEN 'C-' THEN 1.7
    WHEN 'D+' THEN 1.3 WHEN 'D0' THEN 1.0 WHEN 'F'  THEN 0.0
    ELSE NULL END"""

TEMPLATES = [
    {
        "label": "학과 평균 GPA",
        "emoji": "🎓",
        "params": [
            {"key": "dept", "label": "학과", "type": "select", "options": DEPT_LIST},
        ],
        "sql_fn": lambda p: f"""
SELECT ROUND(AVG({GPA_CASE}), 2) AS 평균_GPA,
       COUNT(DISTINCT s.ID) AS 학생수
FROM student s
JOIN takes t ON s.ID = t.ID
WHERE s.dept_name = '{p["dept"]}'
  AND t.grade IS NOT NULL
""",
        "caption_fn": lambda p: f"{p['dept']} 학생들의 평균 GPA",
    },
    {
        "label": "학과 인원수",
        "emoji": "👥",
        "params": [
            {"key": "dept", "label": "학과", "type": "select", "options": DEPT_LIST},
        ],
        "sql_fn": lambda p: f"""
SELECT COUNT(*) AS 학생수
FROM student
WHERE dept_name = '{p["dept"]}'
""",
        "caption_fn": lambda p: f"{p['dept']} 재학생 수",
    },
    {
        "label": "GPA 이상 학생",
        "emoji": "⭐",
        "params": [
            {"key": "dept", "label": "학과", "type": "select", "options": DEPT_LIST},
            {"key": "gpa", "label": "최소 GPA", "type": "float", "min": 0.0, "max": 4.3, "default": 3.5, "step": 0.1},
        ],
        "sql_fn": lambda p: f"""
SELECT s.ID AS 학번, s.name AS 이름,
       ROUND(AVG({GPA_CASE}), 2) AS 평균_GPA
FROM student s
JOIN takes t ON s.ID = t.ID
WHERE s.dept_name = '{p["dept"]}'
  AND t.grade IS NOT NULL
GROUP BY s.ID, s.name
HAVING 평균_GPA >= {p["gpa"]}
ORDER BY 평균_GPA DESC
""",
        "caption_fn": lambda p: f"{p['dept']} 학생 중 GPA {p['gpa']} 이상",
    },
    {
        "label": "수강 현황",
        "emoji": "📚",
        "params": [
            {"key": "dept", "label": "학과", "type": "select", "options": DEPT_LIST},
            {"key": "semester", "label": "학기", "type": "select", "options": SEMESTER_LIST},
        ],
        "sql_fn": lambda p: f"""
SELECT s.ID AS 학번, s.name AS 이름,
       c.title AS 과목명, c.credits AS 학점수
FROM student s
JOIN takes t ON s.ID = t.ID
JOIN course c ON t.course_id = c.course_id
WHERE s.dept_name = '{p["dept"]}'
  AND t.year = 2025
  AND t.semester = '{p["semester"]}'
  AND t.grade IS NULL
ORDER BY s.name
""",
        "caption_fn": lambda p: f"{p['dept']} · 2025년 {p['semester']} 수강 중인 학생",
    },
    {
        "label": "교수 목록",
        "emoji": "👨‍🏫",
        "params": [
            {"key": "dept", "label": "학과", "type": "select", "options": DEPT_LIST},
        ],
        "sql_fn": lambda p: f"""
SELECT ID AS 교수번호, name AS 이름, salary AS 급여
FROM instructor
WHERE dept_name = '{p["dept"]}'
ORDER BY name
""",
        "caption_fn": lambda p: f"{p['dept']} 소속 교수 목록",
    },
    {
        "label": "개설 과목",
        "emoji": "📋",
        "params": [
            {"key": "dept", "label": "학과", "type": "select", "options": DEPT_LIST},
        ],
        "sql_fn": lambda p: f"""
SELECT course_id AS 과목코드, title AS 과목명, credits AS 학점수
FROM course
WHERE dept_name = '{p["dept"]}'
ORDER BY course_id
""",
        "caption_fn": lambda p: f"{p['dept']} 개설 과목 목록",
    },
]


def _run_direct_sql(sql: str) -> pd.DataFrame | None:
    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query(sql, conn)
        conn.close()
        return df
    except Exception as e:
        st.error(f"쿼리 실행 오류: {e}")
        return None


def render():
    st.markdown("## 빠른 조회")
    st.caption("자주 쓰는 조회를 빠르게 실행하세요.")
    st.divider()

    if "active_template" not in st.session_state:
        st.session_state.active_template = None
    if "quick_result" not in st.session_state:
        st.session_state.quick_result = None

    # ── 버튼 나열 ──────────────────────────────────────────
    cols = st.columns(len(TEMPLATES))
    for i, tpl in enumerate(TEMPLATES):
        with cols[i]:
            is_active = st.session_state.active_template == i
            if st.button(
                f"{tpl['emoji']} {tpl['label']}",
                key=f"tpl_btn_{i}",
                type="primary" if is_active else "secondary",
                use_container_width=True,
            ):
                st.session_state.active_template = None if is_active else i
                st.session_state.quick_result = None
                st.rerun()

    # ── 파라미터 폼 ────────────────────────────────────────
    active = st.session_state.active_template
    if active is not None:
        tpl = TEMPLATES[active]
        st.markdown("")

        with st.container(border=True):
            param_values = {}
            cols_param = st.columns(len(tpl["params"]) + 1)

            for j, param in enumerate(tpl["params"]):
                with cols_param[j]:
                    if param["type"] == "select":
                        param_values[param["key"]] = st.selectbox(
                            param["label"],
                            options=param["options"],
                            key=f"tpl_param_{active}_{param['key']}",
                        )
                    elif param["type"] == "float":
                        param_values[param["key"]] = st.number_input(
                            param["label"],
                            min_value=param["min"],
                            max_value=param["max"],
                            value=param["default"],
                            step=param["step"],
                            key=f"tpl_param_{active}_{param['key']}",
                        )

            with cols_param[-1]:
                st.markdown("<div style='margin-top:28px'/>", unsafe_allow_html=True)
                if st.button("🔍 조회", key=f"tpl_run_{active}", type="primary", use_container_width=True):
                    sql = tpl["sql_fn"](param_values)
                    caption = tpl["caption_fn"](param_values)
                    df = _run_direct_sql(sql)
                    if df is not None:
                        st.session_state.quick_result = {
                            "df": df,
                            "caption": caption,
                            "emoji": tpl["emoji"],
                        }
                    st.rerun()

    # ── 결과 표시 ──────────────────────────────────────────
    result = st.session_state.get("quick_result")
    if result:
        st.divider()
        st.markdown(f"##### {result['emoji']} {result['caption']}")
        df: pd.DataFrame = result["df"]
        if df.empty:
            st.info("조회된 데이터가 없어요.")
        else:
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.caption(f"총 {len(df)}건")