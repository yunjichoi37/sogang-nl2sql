"""
create_db.py
ddl_sogang.sql + sogang_insert.sql → university DB 생성

수정 이력:
- split_statements: 주석 라인 선처리 추가 (주석 뒤 첫 INSERT 스킵 버그 수정)
- clean_sql_for_sqlite: numeric(p,0) → INTEGER, numeric(p,d) → REAL 분리
- credits check: >= 0 (0학점 과목 허용)
- PRAGMA foreign_keys = ON 유지 (무결성 검증)
"""
import sqlite3
import re
import os

DDL_PATH    = "sogang_data/ddl_sogang.sql"
INSERT_PATH = "sogang_data/sogang_insert.sql"
DB_PATH     = "sogang_data/sogang_university.db"

def clean_sql_for_sqlite(sql: str) -> str:
    """표준 SQL → SQLite 호환 타입으로 변환"""
    # numeric(p,0) → INTEGER (year, credits 등 정수)
    sql = re.sub(r'\bnumeric\s*\(\s*\d+\s*,\s*0\s*\)', 'INTEGER', sql, flags=re.IGNORECASE)
    # numeric(p,d) → REAL (budget, salary 등 실수)
    sql = re.sub(r'\bnumeric\s*\(\s*\d+\s*,\s*\d+\s*\)', 'REAL',    sql, flags=re.IGNORECASE)
    # numeric(p) → INTEGER
    sql = re.sub(r'\bnumeric\s*\(\s*\d+\s*\)',           'INTEGER', sql, flags=re.IGNORECASE)
    sql = re.sub(r'\bvarchar\s*\(\d+\)', 'TEXT', sql, flags=re.IGNORECASE)
    sql = re.sub(r'\bchar\s*\(\d+\)',    'TEXT', sql, flags=re.IGNORECASE)
    sql = re.sub(r'\bfloat\b',           'REAL', sql, flags=re.IGNORECASE)
    return sql

def split_statements(sql: str) -> list:
    """
    SQL 문장 분리
    - 주석 라인(--)을 먼저 제거해서 '주석+다음INSERT' 합쳐지는 버그 방지
    - 따옴표 안 세미콜론 무시
    """
    # 1단계: 주석 라인 선처리
    clean_lines = []
    for line in sql.splitlines():
        clean_lines.append('' if line.strip().startswith('--') else line)
    sql = '\n'.join(clean_lines)

    # 2단계: 따옴표 인식하며 세미콜론으로 분리
    statements = []
    current = []
    in_quote = False
    quote_char = None
    for ch in sql:
        if in_quote:
            current.append(ch)
            if ch == quote_char:
                in_quote = False
        else:
            if ch in ("'", '"'):
                in_quote = True
                quote_char = ch
                current.append(ch)
            elif ch == ';':
                stmt = ''.join(current).strip()
                if stmt:
                    statements.append(stmt)
                current = []
            else:
                current.append(ch)
    stmt = ''.join(current).strip()
    if stmt:
        statements.append(stmt)
    return statements

def run_sql_file(cursor, filepath: str, label: str):
    print(f"\n{label} 실행 중: {filepath}")
    with open(filepath, "r", encoding="utf-8") as f:
        raw = f.read()
    cleaned = clean_sql_for_sqlite(raw)
    statements = split_statements(cleaned)

    success, fail = 0, 0
    errors = []
    for stmt in statements:
        try:
            cursor.execute(stmt)
            success += 1
        except Exception as e:
            fail += 1
            if len(errors) < 5:
                errors.append((str(e), stmt[:100]))

    print(f"     성공: {success}개 / 실패(스킵): {fail}개")
    for err, sql in errors:
        print(f"      스킵: {err}")
        print(f"      SQL : {sql}...")

def verify_db(cursor):
    print("\nDB 검증")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall()]
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"  {table:25s}: {count:>7,}행")

def main():
    for path in [DDL_PATH, INSERT_PATH]:
        if not os.path.exists(path):
            print(f"파일 없음: {path}")
            return

    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"기존 {DB_PATH} 삭제")

    # isolation_level=None: 수동 트랜잭션 관리
    conn = sqlite3.connect(DB_PATH, isolation_level=None)
    cursor = conn.cursor()

    try:
        # 1. DDL: FK OFF로 테이블 생성
        cursor.execute("PRAGMA foreign_keys = OFF")
        run_sql_file(cursor, DDL_PATH, "DDL (테이블 생성)")

        # 2. INSERT: FK ON으로 무결성 검증
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute("BEGIN")
        run_sql_file(cursor, INSERT_PATH, "INSERT (데이터 삽입)")
        cursor.execute("COMMIT")

        verify_db(cursor)
        print(f"\nDB 생성 완료: {DB_PATH}")

    except Exception as e:
        print(f"\n오류 발생: {e}")
        cursor.execute("ROLLBACK")
    finally:
        conn.close()

if __name__ == "__main__":
    main()