"""가격 이력 저장소.

watch별로 JSONL 한 줄 = 한 번의 관측(run). 리포지토리에 커밋되어
GitHub Actions 실행 간에 이력이 이어진다.
"""

import json
import os

HISTORY_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "history"
)


def _path(watch_id):
    return os.path.join(HISTORY_DIR, f"{watch_id}.jsonl")


def load(watch_id):
    """과거 관측 목록 (오래된 순)."""
    p = _path(watch_id)
    if not os.path.exists(p):
        return []
    out = []
    with open(p, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def append(watch_id, record):
    os.makedirs(HISTORY_DIR, exist_ok=True)
    with open(_path(watch_id), "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def previous_best(history):
    """직전 관측의 최저가. 없으면 None."""
    for rec in reversed(history):
        if rec.get("best_price"):
            return rec["best_price"]
    return None


def all_time_low(history):
    """과거 전체 최저가. 없으면 None."""
    prices = [r["best_price"] for r in history if r.get("best_price")]
    return min(prices) if prices else None
