"""가격 그래프와 실제 항공편 조회가 서로 맞는지 기록한다 — 소스축의 0번째 버전.

지금 이 도구의 가격은 전부 구글 한 곳에서 온다. 그래서 "이 값이 싼가"(시간축)와
"총예산으로 싼가"(항목축)에는 답하지만, "이 표시가가 맞나"에는 답하지 못한다.
검증할 다른 소스가 없기 때문이다.

그런데 이미 경로는 둘이다. explore는 가격 그래프(달력 API)를 쓰고 watch는 실제
항공편 검색 페이지를 훑는다. 같은 구글이지만 다른 응답이고, 실제로 갈릴 수 있다.
그래프는 빠른 대신 대표값이고 검색은 느린 대신 실제 편이다.

둘이 같은 일정을 두고 무슨 값을 냈는지 짝지어 쌓는다. 새 API 없이, 이미 있는
두 경로만으로 소스축을 연다. 쌓이면 "그래프를 얼마나 믿어도 되는가"에 숫자로
답할 수 있다 — 지금은 사례 하나를 손으로 적어 두었을 뿐이다.

관측 시점이 벌어진 짝은 버린다. 한 달 전 그래프와 오늘 실측의 차이는 소스가
갈린 게 아니라 그냥 가격이 움직인 것이다. 그걸 불일치로 세면 거짓이 쌓인다.

    python -m explore.agree
    python -m explore.agree --max-gap 7 --dry-run
"""

import argparse
import glob
import json
import os
from datetime import datetime

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WATCHLIST_JSON = os.path.join(_ROOT, "watchlist.json")
WATCH_HISTORY_DIR = os.path.join(_ROOT, "history")
RESULTS_DIR = os.path.join(_ROOT, "explore", "results")
AGREEMENT_JSONL = os.path.join(_ROOT, "explore", "agreement.jsonl")

MAX_GAP_DAYS = 3


def _parse_at(s):
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except (ValueError, TypeError):
            continue
    return None


def load_watch_observations(watchlist_path=None, history_dir=None):
    """watch 이력을 일정 단위로 편다.

    이력 파일에는 목적지도 인원도 없다 — 파일명이 watch id이고 조건은 watchlist에
    있다. 둘을 붙여야 explore 결과와 같은 열쇠로 맞출 수 있다.
    """
    watchlist_path = watchlist_path or WATCHLIST_JSON
    history_dir = history_dir or WATCH_HISTORY_DIR
    try:
        with open(watchlist_path, encoding="utf-8") as f:
            wl = json.load(f)
    except (OSError, json.JSONDecodeError):
        return []
    defaults = wl.get("defaults") or {}
    by_id = {w["id"]: {**defaults, **w} for w in (wl.get("watches") or [])}

    out = []
    for path in sorted(glob.glob(os.path.join(history_dir, "*.jsonl"))):
        wid = os.path.splitext(os.path.basename(path))[0]
        cfg = by_id.get(wid)
        if cfg is None:      # 감시 목록에서 지워진 이력 — 조건을 알 수 없다
            continue
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    rec = json.loads(line)
                    if not rec.get("best_price"):
                        continue
                    out.append({
                        "watch_id": wid,
                        "dest": cfg.get("dest"),
                        "adults": cfg.get("adults", 1),
                        "children": cfg.get("children", 0),
                        "departure_date": rec.get("dep_date"),
                        "return_date": rec.get("ret_date"),
                        "nights": rec.get("nights"),
                        "price": rec["best_price"],
                        "at": rec.get("at"),
                    })
        except (OSError, json.JSONDecodeError):
            continue
    return out


def load_graph_prices(results_dir=None):
    """explore 스캔의 날짜 곡선을 일정 단위로 편다. 같은 일정이 여럿이면 최신 스캔."""
    results_dir = results_dir or RESULTS_DIR
    if not os.path.isdir(results_dir):
        return {}
    best = {}
    for path in sorted(glob.glob(os.path.join(results_dir, "*.json"))):
        name = os.path.basename(path)
        if name.startswith(("stay-", "brief-")):
            continue
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            meta, ranking = data["meta"], data["ranking"]
        except (OSError, json.JSONDecodeError, KeyError):
            continue
        for row in ranking:
            for p in row.get("date_curve") or []:
                if not p.get("price"):
                    continue
                key = (row.get("code"), meta.get("adults"), meta.get("children"),
                       p.get("departure_date"), p.get("return_date"), p.get("nights"))
                prev = best.get(key)
                if prev is None or meta["scanned_at"] > prev["at"]:
                    best[key] = {"price": p["price"], "at": meta["scanned_at"],
                                 "source_file": name}
    return best


def compare(observations, graph, max_gap_days=MAX_GAP_DAYS):
    """같은 일정·같은 인원끼리 짝지어 차이를 낸다.

    diff는 실측 − 그래프다. 양수면 그래프가 실제보다 싸게 보였다는 뜻이고,
    그쪽이 위험하다 — 싸 보여서 갔는데 결제창에서 더 비싼 경우다.
    """
    pairs, skipped = [], []
    for o in observations:
        key = (o["dest"], o["adults"], o["children"],
               o["departure_date"], o["return_date"], o["nights"])
        g = graph.get(key)
        if g is None:
            continue
        t_real, t_graph = _parse_at(o.get("at")), _parse_at(g.get("at"))
        gap = abs((t_real - t_graph).days) if (t_real and t_graph) else None
        if gap is not None and gap > max_gap_days:
            # 시점이 벌어지면 소스 차이가 아니라 가격 변동이다
            skipped.append({**o, "gap_days": gap, "reason": "관측 시점 차이"})
            continue
        diff = o["price"] - g["price"]
        pairs.append({
            "dest": o["dest"], "watch_id": o["watch_id"],
            "departure_date": o["departure_date"],
            "return_date": o["return_date"], "nights": o["nights"],
            "adults": o["adults"], "children": o["children"],
            "graph_price": g["price"], "real_price": o["price"],
            "diff": diff,
            "diff_pct": round(diff / g["price"] * 100, 2) if g["price"] else None,
            "graph_at": g["at"], "real_at": o.get("at"), "gap_days": gap,
            "graph_source": g.get("source_file"),
        })
    pairs.sort(key=lambda p: (p["real_at"] or "", p["dest"] or ""))
    return pairs, skipped


def summarize(pairs):
    """일치도 요약. 짝이 적으면 평균을 내지 않는다."""
    if not pairs:
        return {"pairs": 0}
    diffs = [abs(p["diff_pct"]) for p in pairs if p["diff_pct"] is not None]
    # 같은 일정을 여러 날 관측하면 짝도 여러 개 생긴다. 그걸 그대로 세면
    # 자주 본 일정 하나가 통계를 끌고 간다. 일정 수를 따로 센다.
    itineraries = {(p["dest"], p["departure_date"], p["return_date"], p["nights"])
                   for p in pairs}
    out = {
        "pairs": len(pairs),
        "itineraries": len(itineraries),
        "exact": sum(1 for p in pairs if p["diff"] == 0),
        "max_abs_pct": max(diffs) if diffs else None,
        "graph_cheaper": sum(1 for p in pairs if p["diff"] > 0),
        "graph_pricier": sum(1 for p in pairs if p["diff"] < 0),
    }
    if len(pairs) >= 3:
        out["mean_abs_pct"] = round(sum(diffs) / len(diffs), 2)
    return out


def load_history(path=None):
    """쌓인 짝 기록을 읽는다."""
    path = path or AGREEMENT_JSONL
    out = []
    if not os.path.exists(path):
        return out
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
    except (OSError, json.JSONDecodeError):
        pass
    return out


def flight_band(dest=None, path=None, min_pairs=3, records=None):
    """가격 그래프 값에 씌울 오차 폭. 근거가 얇으면 얇다고 말한다.

    브리프는 항공권을 '실측'으로 보고 오차 0으로 다뤘다. 실제 항공편 조회라면
    맞지만, 탐색이 넘기는 값은 가격 그래프다. 그래프는 달력에 띄우려고 미리
    계산해 둔 대표값이라 실제 검색과 어긋난다 — 삿포로에서 최대 7.5% 어긋났고
    다섯 번 다 그래프가 싼 쪽이었다. 오차 0으로 두면 그 위험이 표에서 사라진다.

    폭은 관측된 '최대' 어긋남을 쓴다. 평균을 쓰면 최악을 감춘다.
    노선 관측이 충분하면 그 노선 것을, 없으면 다른 노선 것을 빌려 쓰되
    빌렸다고 basis에 적는다. 관측이 아예 없으면 0을 주고 없다고 말한다.
    """
    rows = load_history(path) if records is None else records
    mine = [r for r in rows if dest and r.get("dest") == dest]
    pool, basis = None, None
    if len(mine) >= min_pairs:
        pool, basis = mine, "이 노선 관측 {}건".format(len(mine))
    elif len(rows) >= min_pairs:
        pool, basis = rows, "다른 노선 관측 {}건을 빌려 씀".format(len(rows))
    elif rows:
        pool, basis = rows, "관측 {}건뿐 — 근거가 얇다".format(len(rows))
    if not pool:
        return {"band": 0.0, "basis": "관측 없음", "pairs": 0, "dest_pairs": len(mine)}
    worst = max((abs(r.get("diff_pct") or 0) for r in pool), default=0.0)
    return {"band": round(worst / 100, 4), "basis": basis,
            "pairs": len(pool), "dest_pairs": len(mine)}


def append_history(pairs, path=None):
    """짝을 기록에 쌓는다. 같은 짝을 두 번 쌓지 않는다."""
    path = path or AGREEMENT_JSONL
    seen = set()
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        r = json.loads(line)
                        seen.add((r.get("dest"), r.get("departure_date"),
                                  r.get("return_date"), r.get("nights"),
                                  r.get("real_at")))
        except (OSError, json.JSONDecodeError):
            pass
    fresh = [p for p in pairs
             if (p["dest"], p["departure_date"], p["return_date"],
                 p["nights"], p["real_at"]) not in seen]
    if fresh:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            for p in fresh:
                f.write(json.dumps(p, ensure_ascii=False) + "\n")
    return fresh


def run(argv=None):
    ap = argparse.ArgumentParser(description="가격 그래프 ↔ 실제 조회 일치도")
    ap.add_argument("--max-gap", type=int, default=MAX_GAP_DAYS,
                    help="짝지을 관측 시점 차이 상한(일)")
    ap.add_argument("--dry-run", action="store_true", help="기록하지 않고 출력만")
    a = ap.parse_args(argv)

    obs = load_watch_observations()
    graph = load_graph_prices()
    pairs, skipped = compare(obs, graph, a.max_gap)

    print("실측 관측 {}건 | 그래프 일정 {}건 -> 짝지어진 것 {}건".format(
        len(obs), len(graph), len(pairs)), flush=True)
    if skipped:
        print("  (시점 차이 {}일 초과로 제외 {}건)".format(a.max_gap, len(skipped)),
              flush=True)

    if not pairs:
        print("\n짝지을 일정이 없습니다. 감시와 탐색이 같은 일정을 훑어야 비교됩니다.")
        return []

    print()
    for p in pairs:
        d = "일치" if not p["diff"] else "{:+,}원 ({:+.1f}%)".format(
            p["diff"], p["diff_pct"])
        gap = "{}일".format(p["gap_days"]) if p["gap_days"] is not None else "-"
        print("  {:<5} {}~{} {}박   그래프 {:>10,}  실제 {:>10,}   {:<20} 시점차 {}".format(
            p["dest"] or "?", p["departure_date"], p["return_date"], p["nights"],
            p["graph_price"], p["real_price"], d, gap))

    s = summarize(pairs)
    line = "\n짝 {}건(서로 다른 일정 {}개) 중 정확히 일치 {}건".format(
        s["pairs"], s["itineraries"], s["exact"])
    if s.get("mean_abs_pct") is not None:
        line += " · 평균 오차 {}% · 최대 {}%".format(s["mean_abs_pct"], s["max_abs_pct"])
    else:
        line += " · 최대 오차 {}%".format(s["max_abs_pct"])
    print(line)
    if s.get("mean_abs_pct") is None:
        print("  (짝이 3건 미만이라 평균은 내지 않는다 — 없는 정밀도를 지어내지 않는다)")
    if s.get("graph_cheaper"):
        print("  [주의] 그래프가 실제보다 싸게 보인 경우 {}건 — 싸 보여서 갔다가 "
              "결제창에서 더 비싼 쪽이라 이쪽이 위험하다".format(s["graph_cheaper"]))

    if not a.dry_run:
        fresh = append_history(pairs)
        print("\n기록: {} (새로 {}건)".format(AGREEMENT_JSONL, len(fresh)))
    return pairs


if __name__ == "__main__":
    run()
