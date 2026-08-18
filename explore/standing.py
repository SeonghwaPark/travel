"""정기 탐색 — explore_watchlist.json의 질문들을 한 번에 돌린다.

explore.main은 질문 하나를 수동으로 던지는 도구다. 그것만으로는 매번 결과가
덮어써져 "지난달보다 싼가"를 알 수 없다. 여기서는 같은 질문을 같은 조건으로
주기적으로 반복해 explore/history/에 시계열을 쌓는다.

    python -m explore.standing              # 전체
    python -m explore.standing --only family-feb2027
    python -m explore.standing --list       # 질문 목록만 확인
"""

import argparse
import json
import os
import sys

from . import main as explore_main

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WATCHLIST_JSON = os.path.join(_ROOT, "explore_watchlist.json")


def load(path=None):
    with open(path or WATCHLIST_JSON, encoding="utf-8") as f:
        data = json.load(f)
    questions = data.get("questions", [])
    seen = set()
    for q in questions:
        if not q.get("id"):
            raise SystemExit("질문에 id가 없습니다")
        if q["id"] in seen:
            raise SystemExit(f"id가 중복입니다: {q['id']}")
        seen.add(q["id"])
    return questions


def to_argv(q):
    """질문 하나를 explore.main의 인자로 바꾼다.

    tag를 id로 고정하는 게 핵심이다. 기본 tag는 조건을 문자열로 이어붙여 만드는데,
    그러면 질문 문구를 조금만 손봐도 파일이 갈려 이력이 끊긴다.
    """
    argv = [
        "--start", q["start"],
        "--end", q["end"],
        "--nights", str(q.get("nights", "4,5")),
        "--adults", str(q.get("adults", 1)),
        "--children", str(q.get("children", 0)),
        "--infants", str(q.get("infants", 0)),
        "--scope", q.get("scope", "international"),
        "--tag", q["id"],
    ]
    if q.get("origin"):
        argv += ["--origin", q["origin"]]
    if q.get("only"):
        argv += ["--only", q["only"]]
    if q.get("limit"):
        argv += ["--limit", str(q["limit"])]
    if q.get("min_snow") is not None:
        argv += ["--min-snow", str(q["min_snow"])]
    if q.get("max_snow_daytrip") is not None:
        argv += ["--max-snow-daytrip", str(q["max_snow_daytrip"])]
    if q.get("max_snow_view") is not None:
        argv += ["--max-snow-view", str(q["max_snow_view"])]
    if q.get("max_advisory") is not None:
        argv += ["--max-advisory", str(q["max_advisory"])]
    return argv


def run(argv=None):
    p = argparse.ArgumentParser(description="정기 탐색 실행")
    p.add_argument("--only", default="", help="특정 질문 id만")
    p.add_argument("--list", action="store_true", help="질문 목록만 출력")
    p.add_argument("--watchlist", default=None)
    a = p.parse_args(argv)

    questions = load(a.watchlist)
    if a.only:
        questions = [q for q in questions if q["id"] == a.only]
        if not questions:
            raise SystemExit(f"질문 id를 찾지 못함: {a.only}")

    if a.list:
        for q in questions:
            print(f"{q['id']:<24} {q.get('label', '')}")
        return []

    results, failed = [], []
    for i, q in enumerate(questions, 1):
        print(f"\n{'=' * 70}")
        print(f"[{i}/{len(questions)}] {q['id']} — {q.get('label', '')}")
        print("=" * 70)
        try:
            results.append((q, explore_main.run(to_argv(q))))
        except SystemExit:
            raise
        except Exception as e:
            # 질문 하나가 실패해도 나머지는 돌아야 한다. 주 1회뿐이라
            # 여기서 멈추면 그 주 관측이 통째로 비어버린다.
            print(f"  [실패] {q['id']}: {e}", flush=True)
            failed.append(q["id"])

    print(f"\n{'=' * 70}")
    print(f"정기 탐색 완료 — 성공 {len(results)}건, 실패 {len(failed)}건")
    if failed:
        print(f"실패: {', '.join(failed)}")
    return results


if __name__ == "__main__":
    sys.exit(0 if run() is not None else 1)
