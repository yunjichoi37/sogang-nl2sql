# pages/inquiry_dashboard.py — 건의·문의 현황 탭
import os
import json
from datetime import datetime

import numpy as np
import pandas as pd
import streamlit as st

SUBMISSIONS_PATH = "data/submissions.csv"
SEED_DATA_PATH = "data/seed_submissions.json"


# ── 시드 데이터 생성 ───────────────────────────────────────
def _create_seed_data():
    """시드 데이터가 없으면 자동 생성"""
    seed = [
        {"type": "건의", "category": "시설", "content": "도서관 4층 에어컨이 작동하지 않습니다.", "date": "2025-05-01"},
        {"type": "건의", "category": "시설", "content": "도서관 냉방이 너무 약해요.", "date": "2025-05-02"},
        {"type": "건의", "category": "시설", "content": "도서관 에어컨 고장으로 공부하기 힘듭니다.", "date": "2025-05-03"},
        {"type": "건의", "category": "시설", "content": "R관 엘리베이터가 자주 고장납니다.", "date": "2025-05-04"},
        {"type": "건의", "category": "시설", "content": "화장실 세면대 수도꼭지가 고장났어요.", "date": "2025-05-05"},
        {"type": "건의", "category": "시설", "content": "강의실 조명이 너무 어둡습니다.", "date": "2025-05-06"},
        {"type": "건의", "category": "시스템", "content": "수강신청 페이지가 느립니다.", "date": "2025-05-01"},
        {"type": "건의", "category": "시스템", "content": "포털 로그인이 자꾸 튕겨요.", "date": "2025-05-02"},
        {"type": "건의", "category": "시스템", "content": "수강신청 시 오류가 발생합니다.", "date": "2025-05-03"},
        {"type": "건의", "category": "학생생활", "content": "기숙사 식단이 다양하지 않아요.", "date": "2025-05-01"},
        {"type": "건의", "category": "학생생활", "content": "동아리방 공간이 부족합니다.", "date": "2025-05-04"},
        {"type": "건의", "category": "학사", "content": "수강정정 기간을 늘려주세요.", "date": "2025-05-05"},
        {"type": "문의", "category": "장학", "content": "국가장학금 신청 기간이 언제인가요?", "date": "2025-05-01"},
        {"type": "문의", "category": "장학", "content": "성적 장학금 기준이 어떻게 되나요?", "date": "2025-05-02"},
        {"type": "문의", "category": "학사", "content": "졸업 학점이 몇 점인가요?", "date": "2025-05-03"},
        {"type": "문의", "category": "학사", "content": "휴학 신청 방법을 알려주세요.", "date": "2025-05-04"},
        {"type": "문의", "category": "시설", "content": "도서관 이용 시간이 어떻게 되나요?", "date": "2025-05-05"},
    ]
    os.makedirs("data", exist_ok=True)
    with open(SEED_DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(seed, f, ensure_ascii=False, indent=2)
    return seed


def load_submissions() -> pd.DataFrame:
    """CSV + 시드 데이터 합쳐서 로드"""
    records = []

    # 시드 데이터
    if not os.path.exists(SEED_DATA_PATH):
        _create_seed_data()
    with open(SEED_DATA_PATH, encoding="utf-8") as f:
        seeds = json.load(f)
    for s in seeds:
        records.append({
            "접수번호": f"SEED-{len(records)+1:04d}",
            "유형": s["type"],
            "카테고리": s["category"],
            "내용": s["content"],
            "접수일": s["date"],
            "상태": "처리완료",
        })

    # 실제 접수 데이터
    if os.path.exists(SUBMISSIONS_PATH):
        df_real = pd.read_csv(SUBMISSIONS_PATH, encoding="utf-8-sig")
        for _, row in df_real.iterrows():
            records.append({
                "접수번호": row.get("접수번호", "-"),
                "유형": row.get("유형", "-"),
                "카테고리": row.get("카테고리", "기타"),
                "내용": row.get("내용", ""),
                "접수일": row.get("접수일", ""),
                "상태": row.get("상태", "접수완료"),
            })

    return pd.DataFrame(records)


def cluster_submissions(df: pd.DataFrame) -> pd.DataFrame:
    """sentence-transformers로 유사 건의 클러스터링"""
    try:
        from sentence_transformers import SentenceTransformer
        from sklearn.cluster import KMeans
        from sklearn.preprocessing import normalize

        contents = df["내용"].tolist()
        if len(contents) < 3:
            df["클러스터"] = range(len(df))
            return df

        model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
        embeddings = model.encode(contents)
        embeddings = normalize(embeddings)

        n_clusters = min(6, len(contents) // 2)
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        df = df.copy()
        df["클러스터"] = kmeans.fit_predict(embeddings)
        return df

    except ImportError:
        df = df.copy()
        df["클러스터"] = 0
        return df


def render():
    st.markdown("## 📋 건의·문의 현황")
    st.caption("접수된 건의·문의를 분석하고 부서별로 현황을 확인하세요.")
    st.divider()

    df = load_submissions()

    if df.empty:
        st.info("아직 접수된 건의·문의가 없어요.")
        return

    # ── 요약 지표 ────────────────────────────────────────────
    total = len(df)
    suggestions = len(df[df["유형"] == "건의"])
    inquiries = len(df[df["유형"] == "문의"])
    pending = len(df[df["상태"] == "접수완료"])

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("전체 접수", f"{total}건")
    c2.metric("건의", f"{suggestions}건")
    c3.metric("문의", f"{inquiries}건")
    c4.metric("처리 대기", f"{pending}건")

    st.divider()

    # ── 차트 ─────────────────────────────────────────────────
    col_left, col_right = st.columns([1, 1], gap="large")

    with col_left:
        st.markdown("#### 카테고리별 건의·문의 건수")
        cat_counts = df.groupby(["카테고리", "유형"]).size().reset_index(name="건수")
        if not cat_counts.empty:
            pivot = cat_counts.pivot(index="카테고리", columns="유형", values="건수").fillna(0)
            st.bar_chart(pivot)

    with col_right:
        st.markdown("#### 유형별 비율")
        type_counts = df["유형"].value_counts().reset_index()
        type_counts.columns = ["유형", "건수"]
        try:
            import plotly.express as px
            fig = px.pie(type_counts, names="유형", values="건수",
                        color_discrete_sequence=["#AA1D31", "#4A90D9"])
            st.plotly_chart(fig, use_container_width=True)
        except ImportError:
            st.bar_chart(type_counts.set_index("유형"))

    st.divider()

    # ── 클러스터링 ───────────────────────────────────────────
    st.markdown("#### 🔗 유사 건의 클러스터링")

    suggestions_df = df[df["유형"] == "건의"].copy()
    if len(suggestions_df) >= 3:
        with st.spinner("유사 건의 분석 중..."):
            clustered = cluster_submissions(suggestions_df)

        for cluster_id in sorted(clustered["클러스터"].unique()):
            cluster_rows = clustered[clustered["클러스터"] == cluster_id]
            count = len(cluster_rows)
            representative = cluster_rows.iloc[0]["내용"]
            category = cluster_rows.iloc[0]["카테고리"]

            with st.expander(f"📌 [{category}] {representative[:40]}... ({count}건)", expanded=False):
                for _, row in cluster_rows.iterrows():
                    st.markdown(f"- {row['내용']} `{row['접수일']}`")
    else:
        st.info("클러스터링을 위해 건의가 3건 이상 필요해요.")

    st.divider()

    # ── 전체 목록 ────────────────────────────────────────────
    st.markdown("#### 📄 전체 접수 목록")
    filter_type = st.multiselect(
        "유형 필터",
        options=["건의", "문의"],
        default=["건의", "문의"],
    )
    filtered = df[df["유형"].isin(filter_type)]
    st.dataframe(
        filtered[["접수번호", "유형", "카테고리", "내용", "접수일", "상태"]],
        use_container_width=True,
        hide_index=True,
    )