# sql_agent.py
"""
Text-to-SQL 에이전트 핵심 로직
- SQLite 연결 및 SQL 실행
- CSV 저장
- LLM / Agent 생성 및 실행
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
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage

from metadata_loader import get_relevant_tables, load_table_metadata, load_relationships

warnings.filterwarnings("ignore")
load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
DB_PATH = "data/university.db"
OUTPUT_DIR = "data/query_outputs"
MAX_ROWS_IN_CONTEXT = 10

last_query_results = {"data": None}


# ── 테이블 목록 ────────────────────────────────────────────
def get_all_tables() -> list[str]:
    table_files = glob.glob("data/metadata/tables/*.json")
    return [Path(f).stem for f in table_files]

ALL_TABLES: list[str] = get_all_tables()


# ── 프롬프트 ───────────────────────────────────────────────
AGENT_PREFIX = """당신은 서강대학교 교직원을 위한 학사 데이터베이스 SQL 전문가입니다.

규칙:
1. 반드시 SQLite 문법을 사용하세요. (T-SQL, PL/SQL 사용 금지)
2. 'execute_sql_query' 툴로 데이터를 조회하세요.
3. 아래 메타데이터에 있는 테이블과 컬럼만 사용하세요. 존재하지 않는 컬럼은 절대 사용하지 마세요.
4. 툴 입력에 마크다운 코드블록(```)을 사용하지 마세요. SQL 문자열만 전달하세요.
5. 쿼리 결과를 사실 그대로 보고하세요. 불필요한 단서나 면책 조항을 추가하지 마세요.
6. 집계 함수에는 항상 별칭을 사용하세요. (예: COUNT(*) AS count)
7. 결과가 많아 미리보기만 표시된 경우, 전체 데이터는 CSV로 저장된다고 안내하세요.
8. 한국어로 답변하세요.

SQLite 주의사항:
- 문자열 연결: || 사용 (+ 사용 금지)
- TOP 대신 LIMIT 사용
- grade는 문자열 ('A+', 'A', 'B+' 등), grade IS NULL이면 수강 중
- semester 값: 'Fall', 'Spring', 'Winter', 'Summer'
"""


# ── LLM 싱글톤 ─────────────────────────────────────────────
_llm: ChatGroq | None = None

def get_llm() -> ChatGroq:
    global _llm
    if _llm is None:
        _llm = ChatGroq(
            api_key=GROQ_API_KEY,
            model_name="llama-3.3-70b-versatile",
            temperature=0,
        )
    return _llm


# ── SQL 실행 툴 ────────────────────────────────────────────
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


# ── CSV 저장 ───────────────────────────────────────────────
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


# ── Agent 생성 ─────────────────────────────────────────────
def build_agent_executor(dynamic_prefix: str) -> AgentExecutor:
    llm = get_llm()
    tools = [execute_sql_query]

    prompt = ChatPromptTemplate.from_messages([
        ("system", dynamic_prefix),
        ("human", "{input}"),
        MessagesPlaceholder("agent_scratchpad"),
    ])

    agent = create_tool_calling_agent(llm, tools, prompt)
    return AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        handle_parsing_errors=True,
        return_intermediate_steps=True,
    )


# ── 차트 판단 ──────────────────────────────────────────────
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


# ── 메인 실행 함수 ─────────────────────────────────────────
def run_query(user_input: str, callbacks: list | None = None) -> dict:
    """사용자 질문 처리 → 결과 dict 반환"""
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

    agent_executor = build_agent_executor(dynamic_prefix)

    invoke_config = {}
    if callbacks:
        invoke_config["callbacks"] = callbacks

    try:
        response = agent_executor.invoke({"input": user_input}, invoke_config)
        answer = response["output"]
        intermediate_steps = response.get("intermediate_steps", [])

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