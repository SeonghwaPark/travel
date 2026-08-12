"""watchlist.json 로딩 — defaults를 각 watch에 병합해 완전한 설정으로 만든다."""

import json
import os

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_PATH = os.path.join(REPO_ROOT, "watchlist.json")

REQUIRED = ("id", "dest", "date_from", "date_to", "nights")


def load(path=None):
    path = path or DEFAULT_PATH
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)

    defaults = raw.get("defaults", {})
    default_alert = defaults.get("alert", {})

    watches = []
    seen = set()
    for w in raw.get("watches", []):
        missing = [k for k in REQUIRED if not w.get(k)]
        if missing:
            raise ValueError(f"watch {w.get('id', '?')}: 필수 항목 누락 {missing}")
        if w["id"] in seen:
            raise ValueError(f"watch id 중복: {w['id']}")
        seen.add(w["id"])

        merged = {**defaults, **w}
        merged["alert"] = {**default_alert, **w.get("alert", {})}
        merged.setdefault("label", merged["id"])
        merged["nights"] = list(merged["nights"])
        watches.append(merged)

    if not watches:
        raise ValueError("watchlist.json에 감시 대상이 없음")
    return watches
