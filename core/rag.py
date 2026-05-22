"""
rag.py
ChromaDB에서 관련 청크를 검색하고 LLM 답변을 생성
"""

import os

import chromadb
from chromadb.utils import embedding_functions
from groq import Groq


DB_PATH = "data/chroma_db"
TOP_K = 5  # 검색 결과 상위 몇 개


# ── ChromaDB 연결 ────────────────────────────────────────
def get_collections():
    client = chromadb.PersistentClient(path=DB_PATH)
    ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="paraphrase-multilingual-MiniLM-L12-v2"
    )
    yoram_col = client.get_or_create_collection(
        name="yoram", embedding_function=ef,
        metadata={"hnsw:space": "cosine"},
    )
    scholarship_col = client.get_or_create_collection(
        name="scholarship", embedding_function=ef,
        metadata={"hnsw:space": "cosine"},
    )
    return yoram_col, scholarship_col


# ── 검색 ─────────────────────────────────────────────────
def retrieve_yoram(col, query: str, year_hint: str = None, top_k: int = TOP_K) -> list[dict]:
    """요람 컬렉션에서 검색. year_hint가 있으면 해당 학번 필터링"""
    where = {"year": year_hint} if year_hint else None
    results = col.query(
        query_texts=[query],
        n_results=top_k,
        where=where,
    )
    return _parse_results(results)


def retrieve_scholarship(col, query: str, top_k: int = TOP_K) -> list[dict]:
    """장학금 컬렉션에서 검색"""
    results = col.query(
        query_texts=[query],
        n_results=top_k,
    )
    return _parse_results(results)


def _parse_results(results: dict) -> list[dict]:
    chunks = []
    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]
    for doc, meta, dist in zip(docs, metas, distances):
        chunks.append({"text": doc, "meta": meta, "score": 1 - dist})
    return chunks


# ── RAG 답변 생성 ────────────────────────────────────────
_RAG_SYSTEM = """당신은 서강대학교 AI 도우미입니다.
아래 참고 자료를 바탕으로 학생의 질문에 친절하고 정확하게 답변하세요.

참고 자료:
{context}

답변 규칙:
1. 참고 자료에 있는 내용만 사용하세요.
2. 참고 자료에 없는 내용은 "정확한 정보는 담당 부서에 문의해 주세요." 라고 안내하세요.
3. 출처(요람 페이지, 장학금 공고 제목 등)를 간단히 언급하세요.
4. 학번/학과 조건이 있는 경우 해당 조건을 명확히 안내하세요.
5. 한국어, 존댓말로 답변하세요.
"""

def rag_answer(
    query: str,
    chunks: list[dict],
    groq_client: Groq,
    context_info: dict = None,
) -> str:
    if not chunks:
        return "죄송합니다, 관련 정보를 찾지 못했어요. 담당 부서에 직접 문의해 주세요."

    # 컨텍스트 구성
    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        meta = chunk["meta"]
        source_label = _get_source_label(meta)
        context_parts.append(f"[{i}] {source_label}\n{chunk['text']}")
    context = "\n\n".join(context_parts)

    # 사용자 컨텍스트 (학번/학과 등) 붙이기
    user_context = ""
    if context_info:
        user_context = " / ".join(f"{k}: {v}" for k, v in context_info.items() if v)
        user_context = f"\n\n학생 정보: {user_context}"

    system = _RAG_SYSTEM.format(context=context)
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": f"{query}{user_context}"},
        ],
        temperature=0.3,
        max_tokens=1024,
    )
    return response.choices[0].message.content


def _get_source_label(meta: dict) -> str:
    if meta.get("source") == "yoram":
        return f"요람 {meta.get('year', '')}학번 기준 (p.{meta.get('page', '')})"
    elif meta.get("source") == "scholarship":
        return f"장학금 공고: {meta.get('title', '')} ({meta.get('date', '')})"
    return "참고 자료"


# ── 카테고리 보고 컬렉션 선택 ────────────────────────────
def retrieve_by_category(
    query: str,
    category: str,
    yoram_col,
    scholarship_col,
    year_hint: str = None,
) -> list[dict]:
    """분류 카테고리에 따라 적절한 컬렉션에서 검색"""
    if category == "장학":
        return retrieve_scholarship(scholarship_col, query)
    elif category in ("학사", "교무"):
        return retrieve_yoram(yoram_col, query, year_hint=year_hint)
    else:
        # 둘 다 검색해서 합치기
        yoram_chunks = retrieve_yoram(yoram_col, query, year_hint=year_hint, top_k=3)
        sch_chunks = retrieve_scholarship(scholarship_col, query, top_k=3)
        combined = yoram_chunks + sch_chunks
        # 스코어 기준 정렬
        return sorted(combined, key=lambda x: x["score"], reverse=True)[:TOP_K]
