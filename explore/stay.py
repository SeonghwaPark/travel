"""숙박 구역별 가격 + 구역 가이드를 함께 내는 스캐너.

숙박은 항공권과 문제가 다르다. 항공권은 "언제"가 값을 좌우해서 날짜 스캔이
답이었지만, 숙박은 "어느 동네"가 더 크게 좌우한다. 그래서 가격만 뽑지 않고
lodging_areas.json의 구역 가이드·팁을 같이 실어 판단할 수 있게 한다.

가격 조회는 브라우저가 필요해 GitHub Actions에서 돌리는 걸 전제로 한다.
조회가 실패해도 가이드는 그대로 나온다 — 스크래핑이 깨져도 쓸모가 남게.

    python -m explore.stay --dest CTS --check-in 2027-02-17 --check-out 2027-02-23 \
        --adults 2 --children 1
"""

import argparse
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AREAS_JSON = os.path.join(_ROOT, "lodging_areas.json")
RESULTS_DIR = os.path.join(_ROOT, "explore", "results")


def load_areas(path=None):
    with open(path or AREAS_JSON, encoding="utf-8") as f:
        return json.load(f)


def destination(data, code):
    dest = data["destinations"].get(code.upper())
    if dest is None:
        known = ", ".join(sorted(data["destinations"]))
        raise SystemExit(f"구역 가이드가 없는 목적지: {code} (있는 것: {known})")
    return dest


def _won(n):
    return f"{n:,}원"


def to_markdown(result):
    """가격과 가이드를 한 문서로. 가격이 없어도 가이드는 남는다."""
    m = result["meta"]
    pax = f"성인 {m['adults']}"
    if m["children"]:
        pax += f" · 아동 {m['children']}"

    lines = [
        f"# {m['destination_name']} 숙박 — {m['check_in']} ~ {m['check_out']} ({m['nights']}박)",
        "",
        f"- **인원**: {pax}",
        f"- **조회 시각**: {m['scanned_at']}",
        "",
    ]

    priced = [a for a in result["areas"] if a.get("prices")]
    if priced:
        lines += [
            "## 구역별 1박 가격",
            "",
            "| 구역 | 최저 | 중앙값 | 표본 | 이런 경우에 |",
            "|------|------|--------|------|-------------|",
        ]
        for a in sorted(priced, key=lambda x: x["prices"]["min_per_night"]):
            p = a["prices"]
            lines.append(
                f"| {a['name']} | {_won(p['min_per_night'])} | {_won(p['median_per_night'])} "
                f"| {p['count']}곳 | {a['good_for']} |"
            )
        lines += ["", "> 1박 기준이며 방 1개 가격이다. 실제 결제가는 예약처에서 확인해야 한다.", ""]
    else:
        lines += [
            "## 구역별 1박 가격",
            "",
            "> 가격을 가져오지 못했다. 아래 구역 가이드와 예약처 링크로 직접 확인하면 된다.",
            "",
        ]

    lines += ["## 구역 가이드", ""]
    for a in result["areas"]:
        lines.append(f"### {a['name']}")
        if a.get("prices"):
            p = a["prices"]
            lines.append(f"*1박 {_won(p['min_per_night'])}부터 (중앙값 {_won(p['median_per_night'])})*")
        lines += [
            "",
            f"- **이런 경우에**: {a['good_for']}",
            f"- **왜**: {a['why']}",
            f"- **주의**: {a['caution']}",
        ]
        for s in (a.get("prices") or {}).get("samples", [])[:3]:
            rating = f" ★{s['rating']}" if s.get("rating") else ""
            lines.append(f"  - {s['name']}{rating} — {_won(s['price_per_night'])}")
        lines.append("")

    if result.get("tips"):
        lines += ["## 이 지역 숙박 팁", ""]
        lines += [f"- {t}" for t in result["tips"]]
        lines.append("")

    if result.get("failed"):
        lines += [f"> 가격 조회 실패: {', '.join(result['failed'])}", ""]

    return "\n".join(lines)


def build(dest_code, dest, check_in, check_out, adults, children, fetcher=None):
    """구역마다 가격을 붙인 결과를 만든다. fetcher가 없으면 가이드만."""
    nights = (datetime.strptime(check_out, "%Y-%m-%d")
              - datetime.strptime(check_in, "%Y-%m-%d")).days
    if nights < 1:
        raise SystemExit("체크아웃이 체크인보다 빠르거나 같습니다")

    areas, failed = [], []
    for area in dest["areas"]:
        entry = dict(area)
        if fetcher is not None:
            try:
                hotels = fetcher(area["query"], check_in, check_out, adults, children)
            except Exception as e:
                print(f"  {area['name']} 조회 실패: {e}")
                hotels = []
            import ghotels
            summary = ghotels.summarize(hotels)
            if summary:
                entry["prices"] = summary
                print(f"  {area['name']}: {summary['count']}곳, "
                      f"최저 {summary['min_per_night']:,}원")
            else:
                failed.append(area["name"])
                print(f"  {area['name']}: 가격 없음")
        areas.append(entry)

    return {
        "meta": {
            "destination": dest_code.upper(),
            "destination_name": dest["name"],
            "check_in": check_in,
            "check_out": check_out,
            "nights": nights,
            "adults": adults,
            "children": children,
            "scanned_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        },
        "areas": areas,
        "tips": dest.get("tips", []),
        "failed": failed,
    }


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="숙박 구역별 가격·가이드")
    p.add_argument("--dest", required=True, help="목적지 코드 (예: CTS)")
    p.add_argument("--check-in", required=True)
    p.add_argument("--check-out", required=True)
    p.add_argument("--adults", type=int, default=2)
    p.add_argument("--children", type=int, default=0)
    p.add_argument("--no-prices", action="store_true",
                   help="가격 조회 없이 가이드만 (브라우저 불필요)")
    p.add_argument("--tag", default="")
    return p.parse_args(argv)


def run(argv=None):
    a = parse_args(argv)
    data = load_areas()
    dest = destination(data, a.dest)

    fetcher = None
    if not a.no_prices:
        import ghotels
        fetcher = ghotels.fetch

    print(f"▶ {dest['name']} {a.check_in}~{a.check_out} | 구역 {len(dest['areas'])}곳")
    result = build(a.dest, dest, a.check_in, a.check_out,
                   a.adults, a.children, fetcher)

    tag = a.tag or f"stay-{a.dest.upper()}-{a.check_in}-{a.check_out}-{a.adults}a{a.children}c"
    os.makedirs(RESULTS_DIR, exist_ok=True)
    jpath = os.path.join(RESULTS_DIR, f"{tag}.json")
    mpath = os.path.join(RESULTS_DIR, f"{tag}.md")
    with open(jpath, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
        f.write("\n")
    with open(mpath, "w", encoding="utf-8") as f:
        f.write(to_markdown(result) + "\n")

    print(f"\n저장: {jpath}\n      {mpath}")
    return result


if __name__ == "__main__":
    run()
