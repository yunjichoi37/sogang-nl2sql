# sql_agent.py
"""
Text-to-SQL 에이전트 핵심 로직
- SQLite 연결 및 SQL 실행
- CSV 저장
- LLM / Agent 생성 및 실행 (LangGraph create_react_agent 사용)
- 메타데이터 로딩 (metadata_loader)
"""

import os
import csv
import glob
import sqlite3
import warnings
import json
import re
from datetime import datetime
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage, AIMessageChunk, ToolMessage
from langchain_google_vertexai import ChatVertexAI
from langgraph.prebuilt import create_react_agent

from core.metadata_loader import get_relevant_tables, load_table_metadata, load_relationships

warnings.filterwarnings("ignore")
load_dotenv()

GCP_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT")
DB_PATH = "data/db/sogang_university.db"
OUTPUT_DIR = "data/query_outputs"
MAX_ROWS_IN_CONTEXT = 10

last_query_results = {"data": None}


# 테이블 목록 수집
def get_all_tables() -> list[str]:
    table_files = glob.glob("data/metadata/tables/*.json")
    return [Path(f).stem for f in table_files]

ALL_TABLES: list[str] = get_all_tables()


# 프롬프트
AGENT_PREFIX = """당신은 서강대학교 교직원을 위한 학사 데이터베이스 SQL 전문가입니다.

==================================================
## 기본 규칙
==================================================
1. 반드시 SQLite 문법을 사용하세요. (T-SQL, PL/SQL 사용 금지)
2. 'execute_sql_query' 툴로 데이터를 조회하세요.
3. 아래 메타데이터에 있는 테이블과 컬럼만 사용하세요. 존재하지 않는 컬럼은 절대 사용하지 마세요.
4. 툴 입력에 마크다운 코드블록(```)을 사용하지 마세요. SQL 문자열만 전달하세요.
5. 쿼리 결과를 사실 그대로 보고하세요.
6. 집계 함수에는 항상 별칭을 사용하세요. (예: COUNT(*) AS count)
7. 결과가 많아 미리보기만 표시된 경우, 전체 데이터는 CSV로 저장된다고 안내하세요.
8. 한국어로 답변하세요.

==================================================
## SQLite 문법 주의사항
==================================================
- 문자열 연결: || 사용 (+ 사용 금지)
- TOP 대신 LIMIT 사용
- semester 값: '1학기' 또는 '2학기' (Fall/Spring 등 영문 절대 사용 금지)
- 수록 데이터 범위: 2025년도만 존재
- "이번 학기", "최근 학기" → year = 2025 조건 사용
- grade는 문자열이며, grade IS NULL이면 현재 수강 중 (미완료), grade IS NOT NULL이면 이수 완료

==================================================
## "학점" 해석 규칙 (반드시 준수)
==================================================
"학점"은 문맥에 따라 의미가 완전히 다릅니다.

[성적 학점 → GPA 계산]
- 해당 표현: "평균 학점", "학점이 몇이야", "GPA", "성적이 어때"
- 방법: takes.grade 컬럼으로 아래 GPA CASE WHEN 식 사용

[이수 학점 수 → credits 합산]
- 해당 표현: "몇 학점 들어야", "이수 학점", "취득 학점 수", "졸업 학점"
- 방법: takes JOIN course ON ... WHERE grade IS NOT NULL → SUM(course.credits)
- 주의: student.tot_cred는 더미 데이터이므로 절대 사용하지 마세요.

==================================================
## GPA 계산식 (4.3 스케일, 서강대학교 기준)
==================================================
GPA를 계산할 때는 반드시 아래 CASE WHEN 식을 그대로 사용하세요.
F는 0.0으로 GPA에 포함됩니다. ROUND(..., 2)로 소수점 둘째 자리까지 표시하세요.

ROUND(AVG(
    CASE takes.grade
        WHEN 'A+' THEN 4.3
        WHEN 'A0' THEN 4.0
        WHEN 'A-' THEN 3.7
        WHEN 'B+' THEN 3.3
        WHEN 'B0' THEN 3.0
        WHEN 'B-' THEN 2.7
        WHEN 'C+' THEN 2.3
        WHEN 'C0' THEN 2.0
        WHEN 'C-' THEN 1.7
        WHEN 'D+' THEN 1.3
        WHEN 'D0' THEN 1.0
        WHEN 'F'  THEN 0.0
        ELSE NULL
    END
), 2) AS avg_gpa

- ELSE NULL: 수강 중인 과목(grade IS NULL)은 AVG 계산에서 자동 제외됩니다.

==================================================
## 학과명 줄임말 매핑
==================================================
사용자가 줄임말을 쓰면 아래 정확한 dept_name을 WHERE 조건에 사용하세요.

컴공/컴퓨터공학 → '컴퓨터공학과'
경영/경영학 → '경영학부(경영학전공)'
경제/경제학 → '경제학과'
국문/국어국문 → '국어국문학과'
기계/기계공학 → '기계공학과'
물리/물리학 → '물리학과'
미디어/미엔 → '미디어&엔터테인먼트학과'
사학 → '사학과'
사회/사회학 → '사회학과'
생명/생명과학 → '생명과학과'
수학 → '수학과'
시반공 → '시스템반도체공학과'
신방/신문방송 → '신문방송학과'
심리/심리학 → '심리학과'
아텍 → '아트&테크놀로지학과'
철학 → '철학과'
화학 → '화학과'
화공/화공생명 → '화공생명공학과'
전자/전자공학 → '전자공학과'
인공지능/AI → '인공지능학과'
중문 → '중국문화학과'
종교/종교학 → '종교학과'
정외/정치외교 → '정치외교학과'
유럽/유문 → '유럽문화학과'
글한 → '글로벌한국학부'
AI자전 → 'AI기반자유전공학부'
사이언스자전 → 'SCIENCE기반자유전공학부'
인자전 → '인문학기반자유전공학부'

==================================================
## Few-shot SQL 예시
==================================================

[예시 1] 학과별 평균 GPA 조회
질문: "학과별 평균 학점을 알려줘"
SQL:
SELECT s.dept_name,
       ROUND(AVG(
         CASE t.grade
           WHEN 'A+' THEN 4.3 WHEN 'A0' THEN 4.0 WHEN 'A-' THEN 3.7
           WHEN 'B+' THEN 3.3 WHEN 'B0' THEN 3.0 WHEN 'B-' THEN 2.7
           WHEN 'C+' THEN 2.3 WHEN 'C0' THEN 2.0 WHEN 'C-' THEN 1.7
           WHEN 'D+' THEN 1.3 WHEN 'D0' THEN 1.0 WHEN 'F'  THEN 0.0
           ELSE NULL
         END
       ), 2) AS avg_gpa,
       COUNT(DISTINCT s.ID) AS student_count
FROM student s
JOIN takes t ON s.ID = t.ID
WHERE t.grade IS NOT NULL
GROUP BY s.dept_name
ORDER BY avg_gpa DESC;

[예시 2] 특정 학과 학생의 이수 학점 합산
질문: "컴퓨터공학과 학생들이 이수한 학점 수를 보여줘"
SQL:
SELECT s.ID, s.name, SUM(c.credits) AS total_credits
FROM student s
JOIN takes t ON s.ID = t.ID
JOIN course c ON t.course_id = c.course_id
WHERE s.dept_name = '컴퓨터공학과'
    AND t.grade IS NOT NULL
GROUP BY s.ID, s.name
ORDER BY total_credits DESC;

[예시 3] 현재 수강 중인 학생 목록
질문: "2025년 1학기에 수강 중인 컴공과 학생 목록 보여줘"
SQL:
SELECT DISTINCT s.ID, s.name, c.title AS course_title
FROM student s
JOIN takes t ON s.ID = t.ID
JOIN course c ON t.course_id = c.course_id
WHERE s.dept_name = '컴퓨터공학과'
    AND t.year = 2025
    AND t.semester = '1학기'
    AND t.grade IS NULL
ORDER BY s.name;
"""


# LLM 싱글톤
_llm: ChatVertexAI | None = None

def get_llm() -> ChatVertexAI:
    global _llm
    if _llm is None:
        _llm = ChatVertexAI(
            model_name="gemini-2.5-flash",
            temperature=0,
            project=GCP_PROJECT,
        )
    return _llm


# SQL 실행 툴
@tool
def execute_sql_query(sql_query: str) -> str:
    """
    SQLite DB에 쿼리를 실행하고 결과를 반환한다.
    10행 이하: 전체 결과 텍스트 반환
    10행 초과: 상위 5행 미리보기 + CSV 저장 안내
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(sql_query)

        if cursor.description is None:
            conn.close()
            return "실행 완료 (반환된 데이터 없음)"

        columns = [col[0] for col in cursor.description]
        rows = cursor.fetchall()
        results = [dict(zip(columns, row)) for row in rows]
        conn.close()

        last_query_results["data"] = results

        if len(results) <= MAX_ROWS_IN_CONTEXT:
            return str(results)

        preview = results[:5]
        return (
            f"쿼리 결과: 총 {len(results)}행 (데이터가 많아 상위 5행만 표시)\n"
            f"{preview}"
        )

    except Exception as e:
        last_query_results["data"] = None
        return f"SQL 실행 에러: {e}\n이 에러를 바탕으로 쿼리를 수정해서 다시 시도하세요."


# CSV 저장
def save_csv_if_needed() -> tuple[str | None, pd.DataFrame | None]:
    data = last_query_results.get("data")
    if not data:
        return None, None

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = os.path.join(OUTPUT_DIR, f"result_{timestamp}.csv")

    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)

    df = pd.DataFrame(data)
    last_query_results["data"] = None
    return csv_path, df


# Agent 생성
def build_agent(dynamic_prefix: str):
    llm = get_llm()
    tools = [execute_sql_query]

    agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt=dynamic_prefix,
    )
    return agent


def _extract_intermediate_steps(messages: list) -> list:
    steps = []
    for msg in messages:
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tc in msg.tool_calls:
                steps.append({"tool": tc["name"], "input": tc["args"]})
        elif isinstance(msg, ToolMessage):
            if steps:
                steps[-1]["output"] = msg.content
    return steps


# 차트 판단
def decide_chart(df: pd.DataFrame, user_question: str) -> dict:
    if df is None or len(df) <= 1:
        return {"possible": False}

    llm = get_llm()
    schema_info = {
        "columns": list(df.columns),
        "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
        "sample": df.head(2).to_dict(orient="records"),
    }

    prompt = f"""아래는 SQL 쿼리 결과 데이터의 스키마입니다.
{json.dumps(schema_info, ensure_ascii=False)}

사용자 질문: {user_question}

이 데이터를 차트로 표현할 수 있나요?
가능하면 아래 JSON 형식으로만 답하세요. 다른 말은 하지 마세요.
{{"possible": true, "type": "bar", "x": "컬럼명", "y": "컬럼명"}}

type은 bar, line, pie 중 하나입니다.
불가능하면: {{"possible": false}}"""

    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        match = re.search(r'\{.*\}', response.content, re.DOTALL)
        if not match:
            return {"possible": False}

        config = json.loads(match.group())
        if config.get("possible"):
            if not config.get("x") or not config.get("y"):
                return {"possible": False}
            if config.get("x") not in df.columns or config.get("y") not in df.columns:
                return {"possible": False}
            if not pd.api.types.is_numeric_dtype(df[config["y"]]):
                return {"possible": False}

        return config

    except Exception:
        return {"possible": False}


# 메인 실행 함수
def run_query(user_input: str, callbacks: list | None = None) -> dict:
    llm = get_llm()
    relevant_tables = get_relevant_tables(user_input, llm, ALL_TABLES)
    table_meta = load_table_metadata(relevant_tables)
    rel_meta = load_relationships(relevant_tables)

    print(f"[테이블] {relevant_tables}")

    dynamic_prefix = AGENT_PREFIX
    if table_meta:
        dynamic_prefix += f"\n\n=== 테이블 메타데이터 ===\n{table_meta}"
    if rel_meta:
        dynamic_prefix += f"\n\n{rel_meta}"

    agent = build_agent(dynamic_prefix)

    invoke_input = {"messages": [HumanMessage(content=user_input)]}
    invoke_config = {}
    if callbacks:
        invoke_config["callbacks"] = callbacks

    try:
        result = agent.invoke(invoke_input, {**invoke_config, "recursion_limit": 10})

        messages = result.get("messages", [])
        answer = ""
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and not msg.tool_calls:
                answer = msg.content
                break

        intermediate_steps = _extract_intermediate_steps(messages)
        csv_path, df = save_csv_if_needed()
        chart_config = decide_chart(df, user_input) if df is not None else {"possible": False}

        return {
            "answer": answer,
            "csv_path": csv_path,
            "df": df,
            "chart_config": chart_config,
            "relevant_tables": relevant_tables,
            "table_meta": table_meta,
            "rel_meta": rel_meta,
            "intermediate_steps": intermediate_steps,
        }

    except Exception as e:
        last_query_results["data"] = None
        return {
            "answer": "",
            "csv_path": None,
            "df": None,
            "chart_config": {"possible": False},
            "relevant_tables": relevant_tables,
            "table_meta": table_meta,
            "rel_meta": rel_meta,
            "intermediate_steps": [],
            "error": str(e),
        }


def run_query_stream(user_input: str, result_container: dict, callbacks: list | None = None):
    """텍스트 청크를 yield하며 스트리밍. 완료 후 result_container에 메타데이터를 채운다."""
    llm = get_llm()
    relevant_tables = get_relevant_tables(user_input, llm, ALL_TABLES)
    table_meta = load_table_metadata(relevant_tables)
    rel_meta = load_relationships(relevant_tables)

    print(f"[테이블] {relevant_tables}")

    dynamic_prefix = AGENT_PREFIX
    if table_meta:
        dynamic_prefix += f"\n\n=== 테이블 메타데이터 ===\n{table_meta}"
    if rel_meta:
        dynamic_prefix += f"\n\n{rel_meta}"

    agent = build_agent(dynamic_prefix)
    invoke_input = {"messages": [HumanMessage(content=user_input)]}
    invoke_config: dict = {"recursion_limit": 10}
    if callbacks:
        invoke_config["callbacks"] = callbacks

    intermediate_steps = []
    current_tool: dict | None = None
    current_tool_args = ""

    try:
        for chunk, _ in agent.stream(invoke_input, invoke_config, stream_mode="messages"):
            if isinstance(chunk, AIMessageChunk):
                if chunk.tool_call_chunks:
                    for tc in chunk.tool_call_chunks:
                        if tc.get("name"):
                            current_tool = {"tool": tc["name"], "input": {}}
                            current_tool_args = ""
                        if tc.get("args"):
                            current_tool_args += tc["args"]
                elif chunk.content:
                    yield chunk.content

            elif isinstance(chunk, ToolMessage) and current_tool is not None:
                try:
                    current_tool["input"] = json.loads(current_tool_args)
                except Exception:
                    current_tool["input"] = {"sql_query": current_tool_args}
                current_tool["output"] = chunk.content
                intermediate_steps.append(current_tool)
                current_tool = None
                current_tool_args = ""

        csv_path, df = save_csv_if_needed()
        chart_config = decide_chart(df, user_input) if df is not None else {"possible": False}

        result_container.update({
            "csv_path": csv_path,
            "df": df,
            "chart_config": chart_config,
            "relevant_tables": relevant_tables,
            "table_meta": table_meta,
            "rel_meta": rel_meta,
            "intermediate_steps": intermediate_steps,
        })

    except Exception as e:
        last_query_results["data"] = None
        result_container.update({
            "error": str(e),
            "csv_path": None,
            "df": None,
            "chart_config": {"possible": False},
            "relevant_tables": relevant_tables,
            "table_meta": table_meta,
            "rel_meta": rel_meta,
            "intermediate_steps": intermediate_steps,
        })