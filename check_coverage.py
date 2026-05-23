import json
from configs.db import get_connection

conn = get_connection()

# Which municipalities have pages in DB
rows = conn.execute(
    "SELECT municipality_id, COUNT(*) as pages FROM pages GROUP BY municipality_id"
).fetchall()
conn.close()

crawled = {r["municipality_id"]: r["pages"] for r in rows}

with open("municipalities.json", encoding="utf-8") as f:
    all_munis = json.load(f)

active = [m for m in all_munis if m["active"]]

print(f"\nTotal active: {len(active)}")
print(f"With data:    {len(crawled)}  ({len(crawled)/len(active)*100:.0f}%)")
print(f"Missing:      {len(active) - len(crawled)}")

print("\n--- MISSING (never crawled) ---")
for m in active:
    if m["id"] not in crawled:
        print(f"  {m['id']:8s}  {m['name']:<40s}  {m['root_url']}")

print("\n--- CRAWLED ---")
for m in active:
    if m["id"] in crawled:
        print(f"  {m['id']:8s}  {crawled[m['id']]:4d} pages  {m['name']}")
