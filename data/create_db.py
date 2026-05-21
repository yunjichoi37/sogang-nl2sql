"""
create_db.py
DDL.sql + largeRelationsInsertFile.sql로 university DB 생성
"""

import sqlite3
import re
import os

DDL_PATH = "data/DDL.sql"
INSERT_PATH = "data/largeRelationsInsertFile.sql"
DB_PATH = "data/university.db"


def clean_sql_for_sqlite(sql: str) -> str:
    """
    표준 SQL → SQLite 호환으로 변환
    - varchar(n) → TEXT
    - numeric(p,d) → REAL
    - float → REAL
    - char(n) → TEXT
    - 불필요한 세미콜론 이후 공백 처리
    """
    sql = re.sub(r'\bvarchar\s*\(\d+\)', 'TEXT', sql, flags=re.IGNORECASE)
    sql = re.sub(r'\bchar\s*\(\d+\)', 'TEXT', sql, flags=re.IGNORECASE)
    sql = re.sub(r'\bnumeric\s*\(\d+,\s*\d+\)', 'REAL', sql, flags=re.IGNORECASE)
    sql = re.sub(r'\bfloat\b', 'REAL', sql, flags=re.IGNORECASE)
    return sql


def split_statements(sql: str) -> list[str]:
    """세미콜론 기준으로 SQL 문 분리 (빈 문장 제거)"""
    statements = []
    for stmt in sql.split(";"):
        stmt = stmt.strip()
        if stmt and not stmt.startswith("--"):
            statements.append(stmt)
    return statements


def run_sql_file(cursor, filepath: str, label: str):
    print(f"\n{label} 실행 중: {filepath}")
    with open(filepath, "r", encoding="utf-8") as f:
        raw = f.read()

    cleaned = clean_sql_for_sqlite(raw)
    statements = split_statements(cleaned)

    success, fail = 0, 0
    for stmt in statements:
        try:
            cursor.execute(stmt)
            success += 1
        except Exception as e:
            fail += 1
            if fail <= 5:  # 에러는 처음 5개만 출력
                print(f"      스킵: {e}")
                print(f"      SQL: {stmt[:80]}...")

    print(f"     성공: {success}개 / 실패(스킵): {fail}개")


def verify_db(cursor):
    """테이블별 행 수 확인"""
    print("\nDB 검증")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall()]
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"  {table:20s}: {count:>6,}행")


def main():
    # 파일 존재 확인
    for path in [DDL_PATH, INSERT_PATH]:
        if not os.path.exists(path):
            print(f"파일 없음: {path}")
            print("   data/ 폴더에 DDL.sql과 largeRelationsInsertFile.sql을 넣어주세요.")
            return

    # 기존 DB 삭제
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"기존 {DB_PATH} 삭제")

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()

    try:
        # 1. 테이블 생성
        run_sql_file(cursor, DDL_PATH, "DDL (테이블 생성)")
        conn.commit()

        # 2. 데이터 삽입
        run_sql_file(cursor, INSERT_PATH, "largeRelations (데이터 삽입)")
        conn.commit()

        # 3. 검증
        verify_db(cursor)
        print(f"\nDB 생성 완료: {DB_PATH}")

    except Exception as e:
        print(f"\n오류 발생: {e}")
        conn.rollback()
    finally:
        conn.close()


if __name__ == "__main__":
    main()