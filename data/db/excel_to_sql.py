"""
서강대 개설교과목 엑셀 → university DB INSERT SQL 생성기

사용법:
    1. XLS_FILES 리스트에 엑셀 파일 경로들 추가
    2. python3 excel_to_sql.py
    3. sogang_insert.sql 파일 생성됨
"""

import pandas as pd
import re
import random
import string
from collections import defaultdict

random.seed(42)  # 재현 가능하도록 고정

# ================================================================
# 설정: 엑셀 파일 경로 목록 (파일 추가할 때 여기에만 넣으면 됨)
# ================================================================
XLS_FILES = [
    "sogang_data/excel/개설교과목정보(1).xls",
    "sogang_data/excel/개설교과목정보(2).xls",
    "sogang_data/excel/개설교과목정보(3).xls",
    "sogang_data/excel/개설교과목정보(4).xls",
    "sogang_data/excel/개설교과목정보(5).xls",
    "sogang_data/excel/개설교과목정보(6).xls",
    "sogang_data/excel/개설교과목정보(7).xls",
    "sogang_data/excel/개설교과목정보(8).xls",
    "sogang_data/excel/개설교과목정보(9).xls",
    "sogang_data/excel/개설교과목정보(10).xls",
    "sogang_data/excel/개설교과목정보(11).xls",
    "sogang_data/excel/개설교과목정보(12).xls",
    "sogang_data/excel/개설교과목정보(13).xls",
    "sogang_data/excel/개설교과목정보(14).xls",
    "sogang_data/excel/개설교과목정보(15).xls",
    "sogang_data/excel/개설교과목정보(16).xls"
]

OUTPUT_FILE = "sogang_data/sogang_insert.sql"

# 생성할 더미 데이터 수량
NUM_STUDENTS   = 6000
NUM_TAKES      = 60000
NUM_PREREQ     = 400

# ================================================================
# 건물 코드 → 건물명 매핑
# ================================================================
BUILDING_MAP = {
    'A':  '본관(A)',
    'GN': '게페르트 남덕우 경제관(GN)',
    'GA': '삼성 가브리엘관(GA)',
    'PA': '금호아시아나 바오로 경영관(PA)',
    'T':  '토마스 모어관(T)',
    'MA': '마태오관(MA)',
    'M':  '메리홀(M)',
    'I':  '성이냐시오관(I)',
    'E':  '엠마오관(E)',
    'X':  '하비에르관(X)',
    'D':  '다산관(D)',
    'TE': '떼이야르관(TE)',
    'J':  '정하상관(J)',
    'RA': '리치별관(RA)',
    'AS': '아담 샬관(AS)',
    'R':  '리치 과학관(R)',
    'K':  '김대건관(K)',
    'AR': '아루페관(AR)',
    'G':  '체육관(G)',
}

# 성씨 + 이름 음절 풀 (더미 학생 이름용)
LAST_NAMES  = ['김','이','박','최','정','강','조','윤','장','임','한','오','서','신','권','황','안','송','류','전']
FIRST_SYLS  = ['민','지','서','예','수','현','재','윤','도','하','승','준','진','연','태','혜','유','은','성','나']
SECOND_SYLS = ['준','아','원','호','린','우','율','빈','찬','영','진','혁','훈','경','현','희','연','정','민','선']

GRADES = ['A+', 'A0', 'A-', 'B+', 'B0', 'B-', 'C+', 'C0', 'C-', 'D+', 'D0', 'F']
GRADE_WEIGHTS = [8, 15, 12, 15, 12, 8, 9, 6, 5, 4, 3, 3]  # A=35%, B=35%, 나머지=30%
STUDENT_YEARS = [2022, 2023, 2024, 2025]

# ================================================================
# 유틸 함수
# ================================================================

def get_building_code(room_code):
    if not room_code:
        return None
    alpha = re.match(r'^([A-Z]+)', room_code)
    if not alpha:
        return None
    alpha = alpha.group(1)
    if 'B' in alpha and len(alpha) > 1:
        alpha = alpha[:alpha.index('B')]
    if alpha[:2] in BUILDING_MAP:
        return alpha[:2]
    if alpha[:1] in BUILDING_MAP:
        return alpha[:1]
    return alpha

def get_building_name(room_code):
    code = get_building_code(room_code)
    return BUILDING_MAP.get(code, f'알수없음({room_code})') if code else None

def parse_schedule(val):
    if pd.isna(val):
        return []
    val = str(val).strip()
    room_match = re.search(r'\[([^\]]+)\]', val)
    room_code = room_match.group(1) if room_match else None
    time_match = re.search(r'(\d{2}):(\d{2})~(\d{2}):(\d{2})', val)
    if not time_match:
        return []
    s_hr, s_min, e_hr, e_min = [int(x) for x in time_match.groups()]
    day_part = val.split()[0]
    days = [d.strip() for d in day_part.split(',')]
    return [(d, s_hr, s_min, e_hr, e_min, room_code) for d in days]

def make_time_slot_id(days, s_hr, s_min, e_hr, e_min):
    day_str = ''.join(days)
    return f"{day_str}_{s_hr:02d}{s_min:02d}_{e_hr:02d}{e_min:02d}"

def sq(val):
    return str(val).replace("'", "''")

def make_instructor_id(name, existing_ids):
    base = abs(hash(name)) % 90000 + 10000
    uid = str(base)
    while uid in existing_ids:
        base = (base + 1) % 90000 + 10000
        uid = str(base)
    existing_ids.add(uid)
    return uid

def make_student_name():
    last = random.choice(LAST_NAMES)
    first = random.choice(FIRST_SYLS) + random.choice(SECOND_SYLS)
    return last + first

def make_student_id(existing_ids):
    """2022~2025 + 4자리 형태 학번 생성 (예: 20221234)"""
    while True:
        year = random.choice(STUDENT_YEARS)
        seq  = random.randint(1000, 9999)
        uid  = f"{year}{seq}"
        if uid not in existing_ids:
            existing_ids.add(uid)
            return uid

# ================================================================
# 데이터 수집
# ================================================================

def load_xls(path):
    tables = pd.read_html(path, encoding="utf-8")
    df = tables[0]
    df.columns = df.iloc[0]
    df = df.iloc[1:].reset_index(drop=True)
    return df

def collect_all_data(files):
    frames = []
    for f in files:
        try:
            df = load_xls(f)
            frames.append(df)
            print(f"  ✓ {f} ({len(df)}행)")
        except Exception as e:
            print(f"  ✗ {f} 읽기 실패: {e}")
    if not frames:
        raise RuntimeError("읽을 수 있는 파일이 없습니다.")
    return pd.concat(frames, ignore_index=True)

# ================================================================
# INSERT 생성
# ================================================================

def generate_sql(df):
    lines = []
    lines.append("-- ================================================")
    lines.append("-- 서강대학교 university DB INSERT 파일")
    lines.append("-- 자동 생성: excel_to_sql.py")
    lines.append("-- ================================================\n")

    # ── 수집용 컨테이너 ──────────────────────────────
    classrooms   = {}
    departments  = {}
    courses      = {}
    instructors  = {}
    time_slots   = {}
    sections     = {}
    teaches_rows = []

    inst_ids = set()
    semester_map = {'1학기': '1학기', '2학기': '2학기'}
    year = 2025

    # 학과별 course_id 목록 (prereq 생성용)
    dept_courses = defaultdict(list)

    def safe_str(val, default=''):
        try:
            if pd.isna(val):
                return default
        except Exception:
            pass
        s = str(val).strip()
        return default if s == 'nan' else s

    def safe_int(val, default=3):
        try:
            f = float(val)
            if pd.isna(f):
                return default
            return int(f)
        except (TypeError, ValueError):
            return default

    for _, row in df.iterrows():
        dept      = safe_str(row.get('학과', ''))
        course_id = safe_str(row.get('과목번호', ''))
        sec_id    = safe_str(row.get('분반', '01'), '01')
        title     = safe_str(row.get('과목명', ''))
        credits   = safe_int(row.get('학점', 3))
        professor = safe_str(row.get('교수진', ''))
        semester  = semester_map.get(safe_str(row.get('학기', '1학기'), '1학기'), '1학기')
        schedule  = row.get('수업시간/강의실', '')

        if not dept or not course_id:
            continue

        departments[dept] = dept
        courses[course_id] = (course_id, title, dept, credits)
        dept_courses[dept].append(course_id)

        if professor:
            if professor not in instructors:
                inst_id = make_instructor_id(professor, inst_ids)
                instructors[professor] = (inst_id, professor, dept)

        parsed = parse_schedule(schedule)
        if not parsed:
            continue

        days_in_class = []
        s_hr = s_min = e_hr = e_min = 0
        room_code = None

        for day, sh, sm, eh, em, rc in parsed:
            days_in_class.append(day)
            s_hr, s_min, e_hr, e_min = sh, sm, eh, em
            if rc:
                room_code = rc

        ts_id = make_time_slot_id(days_in_class, s_hr, s_min, e_hr, e_min)

        if ts_id not in time_slots:
            time_slots[ts_id] = parsed

        if room_code:
            building_name = get_building_name(room_code)
            classrooms[room_code] = (building_name, room_code)

        original_sec_id = sec_id
        sec_key = (course_id, sec_id, semester, year)
        counter = 1
        
        while sec_key in sections:
            counter += 1
            sec_id = f"{original_sec_id}-{counter}"
            sec_key = (course_id, sec_id, semester, year)
            
        building_name = get_building_name(room_code) if room_code else None
        sections[sec_key] = (building_name, room_code, ts_id)

        if professor and professor in instructors:
            inst_id = instructors[professor][0]
            teaches_rows.append((inst_id, course_id, sec_id, semester, year))

    # ================================================================
    # 더미 데이터 생성
    # ================================================================

    dept_list    = list(departments.keys())
    section_keys = list(sections.keys())   # (course_id, sec_id, semester, year)
    inst_id_list = [v[0] for v in instructors.values()]

    # 학과별 instructor ID 목록 (advisor 동일 학과 배정용)
    dept_inst_map = defaultdict(list)   # dept_name → [inst_id, ...]
    for name, (inst_id, nm, dept) in instructors.items():
        dept_inst_map[dept].append(inst_id)

    # ── student 생성 ─────────────────────────────────
    student_ids  = set()   # 학번은 8자리(20221234), instructor ID(5자리)와 겹칠 일 없음
    students     = []      # (id, name, dept, tot_cred)
    for _ in range(NUM_STUDENTS):
        sid   = make_student_id(student_ids)
        name  = make_student_name()
        dept  = random.choice(dept_list)
        cred  = random.randint(0, 140)
        students.append((sid, name, dept, cred))

    print(f"  student {len(students)}명 생성")

    # ── advisor 생성 ─────────────────────────────────
    # student 1명당 같은 학과 instructor 1명 (PK: s_ID)
    advisors = []
    for (sid, _, dept, _) in students:
        # 같은 학과 교수가 있으면 그 중에서, 없으면 전체에서 랜덤
        pool = dept_inst_map.get(dept) or inst_id_list
        i_id = random.choice(pool)
        advisors.append((sid, i_id))

    print(f"  advisor {len(advisors)}개 생성")

    # ── takes 생성 ───────────────────────────────────
    # (ID, course_id, sec_id, semester, year) PK 중복 방지
    takes_set  = set()
    takes_rows = []
    attempts   = 0
    max_attempts = NUM_TAKES * 5

    while len(takes_rows) < NUM_TAKES and attempts < max_attempts:
        attempts += 1
        sid = random.choice(students)[0]
        sec = random.choice(section_keys)   # (course_id, sec_id, semester, year)
        cid, sec_id, sem, yr = sec
        key = (sid, cid, sec_id, sem, yr)
        if key in takes_set:
            continue
        takes_set.add(key)
        grade = random.choices(GRADES, weights=GRADE_WEIGHTS, k=1)[0].strip()
        takes_rows.append((sid, cid, sec_id, sem, yr, grade))

    print(f"  takes {len(takes_rows)}개 생성 (시도 {attempts}회)")

    # ── prereq 생성 ──────────────────────────────────
    # 같은 학과 내 과목끼리, 순환 참조 방지
    prereq_rows = []
    prereq_set  = set()   # (course_id, prereq_id)
    # 역방향도 저장해서 순환 방지
    reverse_set = set()

    course_list = list(courses.keys())
    attempts = 0
    max_attempts = NUM_PREREQ * 10

    while len(prereq_rows) < NUM_PREREQ and attempts < max_attempts:
        attempts += 1
        # 같은 학과 내에서 뽑기
        dept = random.choice([d for d, cids in dept_courses.items() if len(cids) >= 2])
        cids = dept_courses[dept]
        cid, prereq_id = random.sample(cids, 2)

        # 중복, 자기 자신, 순환 참조 방지
        if cid == prereq_id:
            continue
        if (cid, prereq_id) in prereq_set:
            continue
        if (prereq_id, cid) in prereq_set:   # 역방향 → 순환
            continue

        prereq_set.add((cid, prereq_id))
        prereq_rows.append((cid, prereq_id))

    print(f"  prereq {len(prereq_rows)}개 생성")

    # ================================================================
    # INSERT 출력
    # ================================================================

    # 1. classroom
    lines.append("-- ── classroom ─────────────────────────────────")
    for room_code, (building, _) in sorted(classrooms.items()):
        lines.append(f"insert into classroom values('{sq(building)}', '{sq(room_code)}', 50);")
    lines.append("")

    # 2. department
    lines.append("-- ── department ────────────────────────────────")
    for dept in sorted(departments):
        lines.append(f"insert into department values('{sq(dept)}', '본관(A)', 100000000.00);")
    lines.append("")

    # 3. course
    lines.append("-- ── course ────────────────────────────────────")
    for course_id, (cid, title, dept, credits) in sorted(courses.items()):
        lines.append(f"insert into course values('{sq(cid)}', '{sq(title)}', '{sq(dept)}', {credits});")
    lines.append("")

    # 4. instructor
    lines.append("-- ── instructor ────────────────────────────────")
    for name, (inst_id, nm, dept) in sorted(instructors.items(), key=lambda x: x[1][0]):
        lines.append(f"insert into instructor values('{inst_id}', '{sq(nm)}', '{sq(dept)}', 60000000.00);")
    lines.append("")

    # 5. time_slot
    lines.append("-- ── time_slot ─────────────────────────────────")
    for ts_id, slots in sorted(time_slots.items()):
        for (day, sh, sm, eh, em, _) in slots:
            lines.append(f"insert into time_slot values('{sq(ts_id)}', '{day}', {sh}, {sm}, {eh}, {em});")
    lines.append("")

    # 6. section
    lines.append("-- ── section ───────────────────────────────────")
    for (cid, sec_id, sem, yr), (building, room, ts_id) in sorted(sections.items()):
        if building and room:
            lines.append(
                f"insert into section values('{sq(cid)}', '{sq(sec_id)}', '{sem}', {yr}, "
                f"'{sq(building)}', '{sq(room)}', '{sq(ts_id)}');"
            )
        else:
            lines.append(
                f"insert into section values('{sq(cid)}', '{sq(sec_id)}', '{sem}', {yr}, "
                f"null, null, '{sq(ts_id)}');"
            )
    lines.append("")

    # 7. teaches
    lines.append("-- ── teaches ───────────────────────────────────")
    seen_teaches = set()
    for (inst_id, cid, sec_id, sem, yr) in teaches_rows:
        key = (inst_id, cid, sec_id, sem, yr)
        if key not in seen_teaches:
            seen_teaches.add(key)
            lines.append(
                f"insert into teaches values('{inst_id}', '{sq(cid)}', '{sq(sec_id)}', '{sem}', {yr});"
            )
    lines.append("")

    # 8. student
    lines.append("-- ── student ───────────────────────────────────")
    for (sid, name, dept, cred) in students:
        lines.append(f"insert into student values('{sid}', '{sq(name)}', '{sq(dept)}', {cred});")
    lines.append("")

    # 9. takes
    lines.append("-- ── takes ─────────────────────────────────────")
    for (sid, cid, sec_id, sem, yr, grade) in takes_rows:
        lines.append(
            f"insert into takes values('{sid}', '{sq(cid)}', '{sq(sec_id)}', '{sem}', {yr}, '{grade}');"
        )
    lines.append("")

    # 10. advisor
    lines.append("-- ── advisor ───────────────────────────────────")
    for (sid, iid) in advisors:
        lines.append(f"insert into advisor values('{sid}', '{iid}');")
    lines.append("")

    # 11. prereq
    lines.append("-- ── prereq ────────────────────────────────────")
    for (cid, prereq_id) in prereq_rows:
        lines.append(f"insert into prereq values('{sq(cid)}', '{sq(prereq_id)}');")
    lines.append("")

    return '\n'.join(lines)

# ================================================================
# 메인
# ================================================================

if __name__ == "__main__":
    print("=== 서강대 university DB INSERT 생성기 ===\n")
    print("파일 로딩 중...")
    df = collect_all_data(XLS_FILES)
    print(f"총 {len(df)}개 강의 로드 완료\n")

    print("INSERT 생성 중...")
    sql = generate_sql(df)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(sql)

    print(f"\n✓ '{OUTPUT_FILE}' 생성 완료!")
    print("나중에 파일 추가할 때는 XLS_FILES 리스트에 경로만 추가하세요.")