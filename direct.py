import sqlite3

# 1. 데이터베이스 파일 연결
db_path = "data/db/sogang_university.db"
conn = sqlite3.connect(db_path)

# 2. 커서(Cursor) 생성
cursor = conn.cursor()

# 3. SQL 쿼리 실행
query = "SELECT DISTINCT grade FROM takes ORDER BY grade;"
cursor.execute(query)

# 4. 결과 가져오기 (전체 데이터)
rows = cursor.fetchall()

# 5. 결과 출력
for row in rows:
    # row는 튜플 형태이므로 (dept_name,)에서 첫 번째 값을 가져옴
    print(row[0])

# 6. 연결 종료
conn.close()