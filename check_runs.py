import psycopg2

conn = psycopg2.connect(
    host="127.0.0.1",
    port=15432,
    user="papermate",
    password="1a838d728b6a46cb5197918a0d0ca9a5e26d3a508b8d911873dd03d20ec623cd",
    dbname="papermate",
)
cur = conn.cursor()

print("=== 论文解析运行状态 ===\n")

# 活跃 run 详情
print("--- 活跃 run ---")
cur.execute("""
SELECT
    substring(r.id::text, 1, 8) AS run_id,
    r.status,
    substring(p.title, 1, 60) AS title,
    EXTRACT(EPOCH FROM (NOW() - r.started_at))::int AS elapsed_sec,
    r.error_message
FROM paper_analysis_runs r
JOIN papers p ON p.id = r.paper_id
WHERE r.status NOT IN ('completed', 'failed', 'cancelled')
ORDER BY r.created_at DESC
LIMIT 20;
""")
rows = cur.fetchall()
if rows:
    print(f"{'RUN_ID':<10} {'STATUS':<16} {'ELAPSED':>8}  TITLE")
    print("-" * 80)
    for row in rows:
        rid, status, title, elapsed, err = row
        print(f"{rid:<10} {status:<16} {str(elapsed)+'s':>8}  {title}")
else:
    print("(无活跃 run)")

print("")

# 各状态统计
print("--- 解析状态统计 ---")
cur.execute("""
SELECT status, COUNT(*) AS runs
FROM paper_analysis_runs
GROUP BY status
ORDER BY CASE status
    WHEN 'running' THEN 1 WHEN 'queued' THEN 2
    WHEN 'downloading' THEN 3 WHEN 'parsing' THEN 4
    WHEN 'chunking' THEN 5 WHEN 'extracting' THEN 6
    WHEN 'embedding' THEN 7 WHEN 'persisting' THEN 8
    WHEN 'retry_wait' THEN 9 WHEN 'completed' THEN 10
    WHEN 'failed' THEN 11 WHEN 'cancelled' THEN 12
    ELSE 13 END;
""")
for status, count in cur.fetchall():
    print(f"  {status:<20} {count}")

print("")

# 论文概览
print("--- 论文概览 ---")
cur.execute("""
SELECT parsed_status, COUNT(*) AS papers
FROM papers
GROUP BY parsed_status
ORDER BY parsed_status;
""")
for status, count in cur.fetchall():
    print(f"  {status:<20} {count}")

cur.close()
conn.close()
