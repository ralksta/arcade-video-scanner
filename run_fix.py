import sqlite3
import subprocess

db_path = "arcade_data/media_library.db"
conn = sqlite3.connect(db_path)
cur = conn.cursor()
cur.execute("SELECT file_path FROM media WHERE file_path LIKE '%_opt.mp4' AND codec='hevc'")
rows = cur.fetchall()

for row in rows:
    file = row[0]
    subprocess.run(["python3", "scripts/fix_av1_tags.py", file])
