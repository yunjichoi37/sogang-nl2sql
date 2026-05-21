import json
from collections import deque
from pathlib import Path
from langchain_core.messages import HumanMessage

METADATA_DIR = Path("data/metadata/tables")
RELATIONSHIPS_PATH = Path("data/metadata/relationships.json")
DOMAIN_GUIDE_PATH = Path("data/metadata/domain_guide.txt")


def get_relevant_tables(user_question: str, llm, all_tables: list) -> list:
    """사용자 질문에서 관련 테이블을 LLM으로 선택"""

    domain_guide = ""
    if DOMAIN_GUIDE_PATH.exists():
        domain_guide = DOMAIN_GUIDE_PATH.read_text(encoding="utf-8")

    table_summaries = []
    for table in all_tables:
        json_path = METADATA_DIR / f"{table}.json"
        if json_path.exists():
            with open(json_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            summary = meta.get("summary", "설명 없음")
            description = meta.get("description", "")
        else:
            summary = "(메타데이터 없음)"
            description = ""
        table_summaries.append(f"- {table}: {summary} ({description})")

    prompt = f"""{domain_guide}

아래는 데이터베이스 테이블 목록과 각 테이블의 간단한 설명입니다.

{chr(10).join(table_summaries)}

사용자 질문: {user_question}

이 질문에 답하려면 어떤 테이블이 필요한가요?
테이블 이름만 쉼표로 구분해서 답하세요. 다른 말은 하지 마세요.
예시: student, takes, course"""

    response = llm.invoke([HumanMessage(content=prompt)])
    selected = [t.strip() for t in response.content.split(",")]
    return [t for t in selected if t in all_tables]


def _parse_column_line(col: str, meta_str: str) -> str:
    """
    JSON 컬럼 메타 문자열을 파싱해서
    col_name(Type) | Label | Desc 형식으로 변환

    저장 형식:
      "Label: 학번 | Type: TEXT | Desc: 학생 고유 식별자 (PK)"
      "Label: 누적취득학점 | Type: INTEGER"
    """
    label = ""
    col_type = ""
    description = ""

    for part in meta_str.split(" | "):
        part = part.strip()
        if part.startswith("Label:"):
            label = part[len("Label:"):].strip()
        elif part.startswith("Type:"):
            col_type = part[len("Type:"):].strip()
        elif part.startswith("Desc:"):
            description = part[len("Desc:"):].strip()

    # col_name(Type) | Label | Desc
    parts = [f"{col}({col_type})", label]
    if description:
        parts.append(description)

    return " | ".join(parts)


def load_table_metadata(relevant_tables: list) -> str:
    """선택된 테이블의 컬럼 메타데이터 로드"""
    if not relevant_tables:
        return ""

    lines = []
    for table in relevant_tables:
        json_path = METADATA_DIR / f"{table}.json"
        if not json_path.exists():
            lines.append(f"[Table: {table}]")
            lines.append("  (메타데이터 파일 없음)")
            lines.append("")
            continue

        with open(json_path, "r", encoding="utf-8") as f:
            meta = json.load(f)

        summary = meta.get("summary", "") or meta.get("description", "")
        header = f"[Table: {summary} ({table})]" if summary else f"[Table: {table}]"
        lines.append(header)

        for col, meta_str in meta.get("columns", {}).items():
            lines.append("  " + _parse_column_line(col, meta_str))

        if meta.get("common_filters"):
            lines.append(f"  Filter: {meta['common_filters']}")
        if meta.get("notes"):
            lines.append(f"  Notes: {meta['notes']}")

        lines.append("")

    return "\n".join(lines).rstrip()


def _build_graph(all_rels: list) -> dict:
    """관계 리스트로 양방향 인접 그래프 구성"""
    graph = {}
    for r in all_rels:
        frm, to = r["from_table"], r["to_table"]
        graph.setdefault(frm, []).append((to, r))
        graph.setdefault(to, []).append((frm, r))
    return graph


def _find_join_path_bfs(start_tables: list, all_rels: list, max_hops: int = 2) -> list:
    """
    선택된 테이블들 사이의 연결 경로를 BFS로 탐색
    직접 연결이 없을 때 보완용
    """
    graph = _build_graph(all_rels)
    target_set = set(start_tables)
    visited_rel_keys = set()
    result_rels = []

    for start in start_tables:
        queue = deque([(start, 0)])
        visited_nodes = {start}

        while queue:
            node, hops = queue.popleft()
            if hops >= max_hops:
                continue

            for neighbor, rel in graph.get(node, []):
                rel_key = (
                    rel["from_table"],
                    rel["from_col"],
                    rel["to_table"],
                    rel["to_col"],
                )
                if neighbor in target_set and rel_key not in visited_rel_keys:
                    visited_rel_keys.add(rel_key)
                    result_rels.append(rel)

                if neighbor not in visited_nodes:
                    visited_nodes.add(neighbor)
                    queue.append((neighbor, hops + 1))

    return result_rels


def load_relationships(relevant_tables: list) -> str:
    """선택된 테이블 간 JOIN 관계 로드"""
    if not RELATIONSHIPS_PATH.exists() or not relevant_tables:
        return ""

    with open(RELATIONSHIPS_PATH, "r", encoding="utf-8") as f:
        all_rels = json.load(f)

    relevant_set = set(relevant_tables)

    # 1순위: 직접 연결
    filtered = [
        r for r in all_rels
        if r.get("from_table") in relevant_set
        and r.get("to_table") in relevant_set
        and r.get("from_table") != r.get("to_table")
    ]

    # 직접 연결 없으면 BFS
    if not filtered:
        print("[관계 탐색] 직접 연결 없음 → BFS 보완 (max_hops=2)")
        filtered = _find_join_path_bfs(relevant_tables, all_rels, max_hops=2)

    if not filtered:
        return ""

    lines = ["[Joins]"]
    for r in filtered:
        note = f"  -- {r['note']}" if r.get("note") else ""
        lines.append(
            f"  {r['from_table']} LEFT JOIN {r['to_table']} "
            f"ON {r['from_table']}.{r['from_col']} = {r['to_table']}.{r['to_col']}"
            f"{note}"
        )

    return "\n".join(lines)