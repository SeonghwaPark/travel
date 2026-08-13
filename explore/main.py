"""여러 목적지 × 기간 전체를 훑어 '언제 어디가 제일 싼가'를 찾는 탐색 스캐너.

backend/scan_cheapest.py는 목적지 하나를 날짜별로 훑고, 웹앱의 최저가 목적지 탭은
날짜 하나에 목적지 여럿을 본다. 이 스크립트는 그 사이의 빈칸 — 목적지 여럿을
기간 전체에 걸쳐 — 을 채운다. 가격 그래프를 쓰므로 목적지·박수당 요청 1번이면 된다.

GitHub Actions에서 도는 걸 전제로 한다 (로컬 네트워크가 Google을 막아도 무관).
결과는 explore/results/ 아래 JSON + Markdown으로 남겨 커밋한다.

    python -m explore.main --start 2027-02-01 --end 2027-02-28 --nights 4,5 --adults 2
    python -m explore.main --start 2027-02-01 --end 2027-02-28 --only NRT,KIX,FUK,TPE
"""

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))

import gflights  # noqa: E402

from . import rank as rank_mod  # noqa: E402

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DESTINATIONS_JSON = os.path.join(_ROOT, "destinations.json")
RESULTS_DIR = os.path.join(_ROOT, "explore", "results")


def load_destinations(scope):
    with open(DESTINATIONS_JSON, encoding="utf-8") as f:
        data = json.load(f)
    if scope == "domestic":
        return dict(data["domestic"])
    if scope == "all":
        return {**data["international"], **data["domestic"]}
    return dict(data["international"])


def scan_destination(dest_code, origin, start, end, nights_list, pax):
    """한 목적지를 박수별로 조회. {박수: offers} 반환."""
    out = {}
    for n in nights_list:
        out[n] = gflights.fetch_price_graph(
            origin, dest_code, start, end, n,
            adults=pax["adults"], children=pax["children"],
            infants_in_seat=0, infants_on_lap=pax["infants"],
        )
    return out


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="여러 목적지 × 기간 최저가 탐색")
    p.add_argument("--origin", default="ICN")
    p.add_argument("--start", required=True, help="가장 빠른 출발일 YYYY-MM-DD")
    p.add_argument("--end", required=True, help="가장 늦은 출발일 YYYY-MM-DD")
    p.add_argument("--nights", default="4,5", help="비교할 박수 목록, 예: 3,4,5")
    p.add_argument("--adults", type=int, default=1)
    p.add_argument("--children", type=int, default=0)
    p.add_argument("--infants", type=int, default=0)
    p.add_argument("--scope", default="international",
                   choices=["international", "domestic", "all"])
    p.add_argument("--only", default="", help="특정 목적지 코드만, 예: NRT,KIX,FUK")
    p.add_argument("--limit", type=int, default=0, help="목적지 수 상한 (0=전체)")
    p.add_argument("--workers", type=int, default=3)
    p.add_argument("--tag", default="", help="결과 파일명 (기본: origin-start-end)")
    return p.parse_args(argv)


def run(argv=None):
    a = parse_args(argv)

    start = datetime.strptime(a.start, "%Y-%m-%d")
    end = datetime.strptime(a.end, "%Y-%m-%d")
    if end < start:
        raise SystemExit("--end가 --start보다 빠릅니다")

    span = (end - start).days + 1
    if span > gflights.MAX_RANGE_DAYS:
        end = start.fromordinal(start.toordinal() + gflights.MAX_RANGE_DAYS - 1)
        print(f"[알림] 기간이 {span}일이라 가격 그래프 상한인 "
              f"{gflights.MAX_RANGE_DAYS}일로 줄입니다 → {end:%Y-%m-%d}")
    start_s, end_s = start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")

    nights_list = [int(x) for x in a.nights.split(",") if x.strip()]
    if not nights_list:
        raise SystemExit("--nights가 비었습니다")

    destinations = load_destinations(a.scope)
    if a.only:
        wanted = [c.strip().upper() for c in a.only.split(",") if c.strip()]
        missing = [c for c in wanted if c not in destinations]
        if missing:
            print(f"[알림] destinations.json에 없는 코드는 건너뜁니다: {', '.join(missing)}")
        destinations = {c: destinations[c] for c in wanted if c in destinations}
    destinations.pop(a.origin.upper(), None)  # 출발지 자기 자신 제외
    if a.limit:
        destinations = dict(list(destinations.items())[:a.limit])
    if not destinations:
        raise SystemExit("조회할 목적지가 없습니다")

    pax = {"adults": a.adults, "children": a.children, "infants": a.infants}
    head_count = max(1, a.adults + a.children)  # 무릎유아는 좌석이 없어 제외

    total_reqs = len(destinations) * len(nights_list)
    print(f"▶ {a.origin} 출발 | {start_s} ~ {end_s} | "
          f"{', '.join(str(n) + '박' for n in nights_list)} | "
          f"목적지 {len(destinations)}곳 → 요청 {total_reqs}건")

    summaries, failed = [], []
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futures = {
            ex.submit(scan_destination, code, a.origin, start_s, end_s, nights_list, pax): code
            for code in destinations
        }
        done = 0
        for fut in as_completed(futures):
            code = futures[fut]
            done += 1
            try:
                offers_by_nights = fut.result()
            except Exception as e:
                print(f"  [{done}/{len(futures)}] {code} 실패: {e}", flush=True)
                failed.append(code)
                continue

            s = rank_mod.summarize(code, destinations[code], offers_by_nights, head_count)
            if s is None:
                print(f"  [{done}/{len(futures)}] {code} 결과 없음", flush=True)
                failed.append(code)
                continue
            summaries.append(s)
            print(f"  [{done}/{len(futures)}] {s['name']:<12} {s['best_price']:>10,}원 "
                  f"{s['departure_date']} {s['nights']}박 (관측 {s['observed']})", flush=True)

    result = {
        "meta": {
            "origin": a.origin.upper(),
            "start": start_s,
            "end": end_s,
            "nights": nights_list,
            "adults": a.adults,
            "children": a.children,
            "infants": a.infants,
            "scope": a.scope,
            "scanned": len(destinations),
            "scanned_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "price_note": "Google Flights 표시가(왕복, 전체 승객 합계). 실제 결제가는 예약처에서 확인 필요.",
        },
        "ranking": rank_mod.rank(summaries),
        "failed": sorted(failed),
    }

    tag = a.tag or f"{a.origin.upper()}-{start_s}-{end_s}"
    os.makedirs(RESULTS_DIR, exist_ok=True)
    jpath = os.path.join(RESULTS_DIR, f"{tag}.json")
    mpath = os.path.join(RESULTS_DIR, f"{tag}.md")
    with open(jpath, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
        f.write("\n")
    with open(mpath, "w", encoding="utf-8") as f:
        f.write(rank_mod.to_markdown(result) + "\n")

    print(f"\n저장: {jpath}\n      {mpath}")
    if result["ranking"]:
        top = result["ranking"][0]
        print(f"\n최저가: {top['name']} {top['best_price']:,}원 "
              f"({top['departure_date']} ~ {top['return_date']}, {top['nights']}박)")
    else:
        print("\n가격을 하나도 받지 못했습니다 — 네트워크나 가격 그래프 응답을 확인하세요.")
    return result


if __name__ == "__main__":
    run()
