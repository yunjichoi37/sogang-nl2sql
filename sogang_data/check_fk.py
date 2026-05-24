import re

time_slots = set()
missing = []

with open("sogang_data/sogang_insert.sql", encoding="utf-8") as f:
    lines = f.readlines()

for line in lines:
    m = re.match(r"insert into time_slot values\('([^']+)'", line)
    if m:
        time_slots.add(m.group(1))

for line in lines:
    m = re.match(r"insert into section values\('[^']+', '[^']+', '[^']+', \d+, (?:'[^']*'|null), (?:'[^']*'|null), '([^']+)'", line)
    if m and m.group(1) not in time_slots:
        missing.append(line.strip()[:80])

print(f"time_slot에 없는 section: {len(missing)}개")
for x in missing[:10]:
    print(f"  {x}")