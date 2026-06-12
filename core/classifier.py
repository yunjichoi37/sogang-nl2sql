# core/classifier.py
import json
import os
import re
from langchain_google_vertexai import ChatVertexAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

GCP_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT")

# 싱글톤
_llm_classify: ChatVertexAI | None = None
_llm_chat: ChatVertexAI | None = None

def _get_classify_llm() -> ChatVertexAI:
    global _llm_classify
    if _llm_classify is None:
        _llm_classify = ChatVertexAI(
            model_name="gemini-2.5-flash",
            temperature=0,
            max_output_tokens=256,
            project=GCP_PROJECT,
        )
    return _llm_classify

def _get_chat_llm() -> ChatVertexAI:
    global _llm_chat
    if _llm_chat is None:
        _llm_chat = ChatVertexAI(
            model_name="gemini-2.5-flash",
            temperature=0.7,
            max_output_tokens=1024,
            project=GCP_PROJECT,
        )
    return _llm_chat


# LLM 분류
_CLASSIFY_SYSTEM = """당신은 서강대학교 AI 도우미의 분류기입니다.
사용자 입력을 분석해서 아래 JSON 형식으로만 답하세요. 다른 말은 절대 하지 마세요.

{
  "type": "건의" 또는 "문의",
  "category": "시설" | "학사" | "장학" | "시스템" | "학생생활" | "교무" | "기타",
  "is_complete": true 또는 false,
  "missing_fields": ["빠진 정보1", "빠진 정보2"]
}

분류 기준:
- 건의: 불편함, 개선 요청, 고장 신고 등 학교에 변화를 요청하는 내용
- 문의: 정보, 규정, 절차를 묻는 내용

is_complete 기준 (건의):
- 시설: 건물명 + 위치(층/호실) + 증상이 모두 있으면 true
- 시스템: 시스템명 + 오류 내용이 있으면 true
- 기타 건의: 무엇이 불편한지 명확하면 true

is_complete 기준 (문의):
- 무엇을 묻는지 명확하면 true
"""

def classify(user_input: str) -> dict:
    """사용자 입력을 건의/문의로 분류"""
    llm = _get_classify_llm()
    response = llm.invoke([
        SystemMessage(content=_CLASSIFY_SYSTEM),
        HumanMessage(content=f"사용자 입력: {user_input}"),
    ])
    raw = response.content.strip()
    raw = re.sub(r"```json|```", "", raw).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {
            "type": "문의",
            "category": "기타",
            "is_complete": True,
            "missing_fields": [],
        }


# 대화 응답 생성
_CHAT_SYSTEM = """당신은 서강대학교 AI 도우미입니다.
학생의 문의·건의를 친절하게 도와주세요.

현재 분류 결과:
- 유형: {inquiry_type}
- 분류: {category}
- 구체화 완료: {is_complete}
- 부족한 정보: {missing_fields}

응답 규칙:
1. 구체화 완료(is_complete=true)이고 유형이 건의인 경우:
   - 내용을 정리해서 "아래 내용으로 접수할게요!" 라고 안내하세요
   - 마지막에 "접수하시겠어요?" 라고 물어보세요
2. 구체화 미완료(is_complete=false)인 경우:
   - 부족한 정보만 간단히 질문하세요 (한 번에 1~2개만)
3. 문의인 경우:
   - 알고 있는 정보를 친절하게 안내하세요
   - 정확하지 않은 정보는 담당 부서 문의를 권유하세요
4. 항상 한국어로, 존댓말로 답하세요.
"""

def get_ai_response(messages: list[dict], classify_result: dict) -> str:
    """분류 결과를 바탕으로 대화 응답 생성"""
    llm = _get_chat_llm()
    system = _CHAT_SYSTEM.format(
        inquiry_type=classify_result.get("type", "미분류"),
        category=classify_result.get("category", "기타"),
        is_complete=classify_result.get("is_complete", False),
        missing_fields=", ".join(classify_result.get("missing_fields", [])) or "없음",
    )
    lc_messages = [SystemMessage(content=system)]
    for m in messages:
        if m["role"] == "user":
            lc_messages.append(HumanMessage(content=m["content"]))
        else:
            lc_messages.append(AIMessage(content=m["content"]))

    response = llm.invoke(lc_messages)
    return response.content
