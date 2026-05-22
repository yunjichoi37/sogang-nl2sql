from core.sql_agent import run_query
result = run_query("A학점 받은 학생이 몇 명이야?")
print(result["answer"])