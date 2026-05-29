import json
from pathlib import Path

MUNICIPALITIES_FILE = Path("municipalities.json")


def load_municipalities(active_only: bool = True) -> list[dict]:
    with open(MUNICIPALITIES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [m for m in data if m["active"]] if active_only else data
