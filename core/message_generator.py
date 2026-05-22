# core/message_generator.py
"""
조회 결과 또는 교직원 지시 → 카카오워크 메시지 초안 생성
"""

import os
import pandas as pd
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

_client = None

def get_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    return _client


_MESSAGE_SYSTEM = """당신은 서강대학교 교직원을 도와 카카오워크 메시지 초안을 작성하는 AI입니다.

작성 규칙:
1. 공식적이지만 친근한 말투를 사용하세요.
2. 핵심 내용을 간결하게 전달하세요.
3. 수신자(학생)가 취해야 할 행동이 있다면 명확히 안내하세요.
4. 마감일/기한이 있다면 강조하세요.
5. 문의처(부서명, 연락처)를 안내하세요.
6. 이모지를 적절히 활용해 가독성을 높이세요.
7. 메시지 길이는 모바일에서 읽기 적합하게 300자 내외로 작성하세요.

메시지 형식:
[제목/이모지]

안녕하세요, 서강대학교 [부서명]입니다.

[본문]

[행동 요청 사항]

문의: [부서명] ([연락처/이메일])
"""

def generate_message(
    instruction: str,
    df: pd.DataFrame | None = None,
    department: str = "학생처",
) -> str:
    """
    instruction: 교직원의 메시지 작성 지시
    df: 조회된 학생 데이터 (선택)
    department: 발송 부서명
    """
    client = get_client()

    # 데이터 요약 (있을 경우)
    data_context = ""
    if df is not None and len(df) > 0:
        row_count = len(df)
        columns = list(df.columns)
        sample = df.head(3).to_dict(orient="records")
        data_context = f"""
조회된 대상 데이터:
- 총 {row_count}명
- 컬럼: {columns}
- 샘플: {sample}
"""

    user_prompt = f"""발송 부서: {department}
{data_context}
교직원 지시: {instruction}

위 내용을 바탕으로 카카오워크 메시지 초안을 작성해주세요."""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": _MESSAGE_SYSTEM},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
        max_tokens=1024,
    )
    return response.choices[0].message.content