"""날짜 범위 전체를 훑어 '언제 가장 싼가'를 찾는 항공권 스캐너.

기존 /api/flights/search 는 날짜를 지정해야만 조회된다. 이 스크립트는 그 위에
2단계 스캔을 얹어 "지금부터 내년 3월 사이 최저가 시기"처럼 기간 자체를 찾는다.

  coarse  — step일 간격으로 성기게 훑어 저렴한 구간을 찾는다
  refine  — 저렴한 상위 구간 주변만 하루 단위로 다시 훑는다

결과는 out/ 아래 JSON + CSV로 저장하고, 같은 조건의 조회 결과는 캐시에 남겨
중간에 끊기거나 다시 돌려도 이미 조회한 날짜는 건너뛴다.

사용 예:
    python scan_cheapest.py --dest CTS --start 2026-08-13 --end 2027-03-31 \
        --nights 2,3,4,5 --adults 2 --children 1
"""

import argparse
import csv
import json
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

import gflights

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")


# ── 캐시 ──

class Cache:
    """(출발일, 박수) -> 조회결과. 파일에 append 하며 진행상황을 보존한다."""

    def __init__(self, path):
        self.path = path
        self.lock = threading.Lock()
        self.data = {}
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    self.data[rec["key"]] = rec["value"]

    def get(self, key):
        return self.data.get(key)

    def put(self, key, value):
        with self.lock:
            self.data[key] = value
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps({"key": key, "value": value}, ensure_ascii=False) + "\n")


# ── 조회 ──

def search_one(cache, origin, dest, dep_date, nights, pax, attempts, quiet=True):
    """출발일+박수 한 조합의 최저가. 결과 없으면 None."""
    key = f"{origin}-{dest}|{dep_date}|{nights}n|{pax['adults']}a{pax['children']}c{pax['infants']}i"
    cached = cache.get(key)
    if cached is not None:
        return cached or None  # 캐시에 저장된 빈 결과({})는 None으로

    ret_date = (datetime.strptime(dep_date, "%Y-%m-%d") + timedelta(days=nights)).strftime("%Y-%m-%d")

    best = gflights.cheapest(
        origin, dest, dep_date, ret_date,
        adults=pax["adults"], children=pax["children"],
        infants_in_seat=0, infants_on_lap=pax["infants"],
        attempts=attempts, retry_sleep=1.5, quiet=quiet,
    )

    result = None
    if best:
        result = {
            "dep_date": dep_date,
            "ret_date": ret_date,
            "nights": nights,
            "weekday": datetime.strptime(dep_date, "%Y-%m-%d").strftime("%a"),
            **best,
        }

    cache.put(key, result or {})
    return result


def scan(cache, origin, dest, dates, nights_list, pax, workers, attempts, label):
    """(날짜 × 박수) 조합을 병렬 조회. Google 요청 간격은 main 쪽 락이 통제한다."""
    combos = [(d, n) for d in dates for n in nights_list]
    total = len(combos)
    results, done = [], 0

    print(f"\n=== {label}: {total}건 조회 시작 ===", flush=True)
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {
            ex.submit(search_one, cache, origin, dest, d, n, pax, attempts): (d, n)
            for d, n in combos
        }
        for fut in as_completed(futures):
            d, n = futures[fut]
            done += 1
            try:
                r = fut.result()
            except Exception as e:
                print(f"  [{done}/{total}] {d} {n}박 실패: {e}", flush=True)
                continue
            if r:
                results.append(r)
                print(f"  [{done}/{total}] {r['dep_date']}({r['weekday']}) {n}박 "
                      f"{r['price']:>9,}원 {r['airline']}", flush=True)
            else:
                print(f"  [{done}/{total}] {d} {n}박 - 결과없음", flush=True)

    results.sort(key=lambda r: r["price"])
    return results


# ── 저장 ──

def save(results, basename, meta):
    os.makedirs(OUT_DIR, exist_ok=True)
    jpath = os.path.join(OUT_DIR, basename + ".json")
    cpath = os.path.join(OUT_DIR, basename + ".csv")

    with open(jpath, "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "results": results}, f, ensure_ascii=False, indent=2)

    if results:
        cols = ["dep_date", "weekday", "ret_date", "nights", "price",
                "airline", "duration", "departure", "arrival", "stops"]
        with open(cpath, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            for r in results:
                w.writerow({c: r.get(c, "") for c in cols})

    print(f"\n저장: {jpath}\n      {cpath}", flush=True)


def print_top(results, n, title):
    print(f"\n===== {title} TOP {n} =====", flush=True)
    print(f"{'출발일':<12} {'요일':<4} {'박':<3} {'가격':>11}  {'항공사':<18} {'경유':<5} 소요", flush=True)
    for r in results[:n]:
        stops = "직항" if r["stops"] == 0 else f"{r['stops']}회"
        print(f"{r['dep_date']:<12} {r['weekday']:<4} {r['nights']:<3} "
              f"{r['price']:>10,}원  {r['airline']:<18} {stops:<5} {r['duration']}", flush=True)


# ── main ──

def daterange(start, end, step):
    d, out = start, []
    while d <= end:
        out.append(d.strftime("%Y-%m-%d"))
        d += timedelta(days=step)
    return out


def parse_args():
    p = argparse.ArgumentParser(description="날짜 범위 항공권 최저가 스캐너")
    p.add_argument("--origin", default="ICN")
    p.add_argument("--dest", default="CTS")
    p.add_argument("--start", required=True, help="스캔 시작 출발일 YYYY-MM-DD")
    p.add_argument("--end", required=True, help="스캔 종료 출발일 YYYY-MM-DD")
    p.add_argument("--nights", default="3,4", help="박수 목록, 예: 2,3,4,5")
    p.add_argument("--coarse-nights", default="", help="coarse 단계에서만 쓸 박수(기본: nights 전체)")
    p.add_argument("--step", type=int, default=4, help="coarse 단계 날짜 간격(일)")
    p.add_argument("--refine-top", type=int, default=6, help="정밀 재탐색할 상위 구간 수")
    p.add_argument("--refine-window", type=int, default=4, help="상위 구간 앞뒤 ±일")
    p.add_argument("--adults", type=int, default=1)
    p.add_argument("--children", type=int, default=0)
    p.add_argument("--infants", type=int, default=0)
    p.add_argument("--workers", type=int, default=3)
    p.add_argument("--attempts", type=int, default=2)
    p.add_argument("--tag", default="", help="출력 파일명 접미사")
    p.add_argument("--no-refine", action="store_true")
    return p.parse_args()


def run():
    a = parse_args()
    start = datetime.strptime(a.start, "%Y-%m-%d")
    end = datetime.strptime(a.end, "%Y-%m-%d")
    nights_list = [int(x) for x in a.nights.split(",") if x.strip()]
    coarse_nights = ([int(x) for x in a.coarse_nights.split(",") if x.strip()]
                     or nights_list)
    pax = {"adults": a.adults, "children": a.children, "infants": a.infants}

    tag = a.tag or f"{a.origin}-{a.dest}"
    os.makedirs(OUT_DIR, exist_ok=True)
    cache = Cache(os.path.join(OUT_DIR, f"cache_{tag}.jsonl"))

    meta = {
        "origin": a.origin, "dest": a.dest,
        "range": [a.start, a.end], "nights": nights_list,
        "pax": pax, "step": a.step,
        "scanned_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "price_note": "Google Flights 표시가(왕복, 전체 승객 합계 추정). 실제 결제가는 예약처에서 확인 필요.",
    }

    # 1) coarse
    coarse_dates = daterange(start, end, a.step)
    coarse = scan(cache, a.origin, a.dest, coarse_dates, coarse_nights, pax,
                  a.workers, a.attempts, f"coarse ({a.step}일 간격)")
    print_top(coarse, 15, "coarse 최저가")
    # 박수를 파일명에 넣어야 같은 태그로 박수만 바꿔 돌릴 때 이전 결과를 덮어쓰지 않는다
    nsig = "-".join(str(n) for n in coarse_nights) + "n"
    save(coarse, f"coarse_{tag}_{nsig}", meta)

    if a.no_refine or not coarse:
        return

    # 2) refine — 저렴한 상위 구간 주변만 하루 단위로
    anchors, seen = [], set()
    for r in coarse:
        wk = r["dep_date"][:7]  # 같은 달에 앵커가 몰리지 않게 분산
        if wk in seen and len(anchors) >= 2:
            continue
        seen.add(wk)
        anchors.append(r["dep_date"])
        if len(anchors) >= a.refine_top:
            break

    refine_dates = set()
    for anc in anchors:
        base = datetime.strptime(anc, "%Y-%m-%d")
        for off in range(-a.refine_window, a.refine_window + 1):
            d = base + timedelta(days=off)
            if start <= d <= end:
                refine_dates.add(d.strftime("%Y-%m-%d"))

    print(f"\n정밀 재탐색 앵커: {', '.join(anchors)}", flush=True)
    fine = scan(cache, a.origin, a.dest, sorted(refine_dates), nights_list, pax,
                a.workers, a.attempts, "refine (1일 간격)")

    # coarse + refine 합치고 (출발일,박수) 중복 제거
    merged = {}
    for r in coarse + fine:
        merged[(r["dep_date"], r["nights"])] = r
    allr = sorted(merged.values(), key=lambda r: r["price"])

    print_top(allr, 20, "최종 최저가")
    save(allr, f"final_{tag}", meta)


if __name__ == "__main__":
    run()
