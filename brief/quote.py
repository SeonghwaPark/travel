"""숙박 견적 — 최종 후보만 사람이 확인해 실측으로 저장한다.

전 세계 숙박비 자동 수집은 구조적으로 막혀 있다. 부킹닷컴·익스피디아는 API를
제휴사에만 열고, Google 호텔 스크래핑은 두 번 다 막혔다(HTML에 가격 없음,
헤드리스 브라우저에도 미제공). 그래서 넓은 탐색은 항공권 스캔(자동)이 맡아
후보를 3~4곳으로 좁히고, 숙박은 그 후보만 확인한다 — 조건이 채워진 링크를
열어 값을 읽고 저장하면 브리프가 그때부터 실측으로 쓴다. 여행 한 번에 5분이다.

    python -m brief.quote links --dest CTS --check-in 2027-02-17 --check-out 2027-02-23 \
        --adults 2 --children 1
    python -m brief.quote add --dest CTS --check-in 2027-02-17 --check-out 2027-02-23 \
        --adults 2 --children 1 --per-night 145000 --area 삿포로역 --source booking.com
"""

import argparse
import json
import os
import sys
from datetime import date, datetime

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "backend"))

QUOTES_JSON = os.path.join(_ROOT, "lodging_quotes.json")
DESTINATIONS_JSON = os.path.join(_ROOT, "destinations.json")


def _dest_name(code):
    with open(DESTINATIONS_JSON, encoding="utf-8") as f:
        d = json.load(f)
    info = {**d["international"], **d["domestic"]}.get(code.upper())
    if info is None:
        known = ", ".join(sorted({**d["international"], **d["domestic"]}))
        raise SystemExit(f"destinations.json에 없는 목적지: {code} (있는 것: {known})")
    return info["name"].split()[0]


def cmd_links(a):
    import lodging
    place = _dest_name(a.dest)
    result = lodging.search_links(place, a.check_in, a.check_out,
                                  adults=a.adults, children=a.children)
    print(f"▶ {place} {a.check_in}~{a.check_out} · 성인 {a.adults}"
          + (f"+아동 {a.children}" if a.children else "")
          + f" · {result['rooms']}실 조건이 채워진 링크\n")
    for link in result["links"]:
        print(f"  [{link['name']}] {link['note']}")
        print(f"  {link['url']}\n")
    print("확인한 1박 값 저장:")
    print(f"  python -m brief.quote add --dest {a.dest.upper()}"
          f" --check-in {a.check_in} --check-out {a.check_out}"
          f" --adults {a.adults} --children {a.children}"
          f" --per-night <원> --area <구역> --source <사이트>")


def cmd_add(a):
    if a.per_night <= 0:
        raise SystemExit("--per-night는 0보다 커야 합니다")
    for d in (a.check_in, a.check_out):
        datetime.strptime(d, "%Y-%m-%d")
    if a.check_out <= a.check_in:
        raise SystemExit("체크아웃이 체크인보다 늦어야 합니다")
    _dest_name(a.dest)  # 코드 검증

    try:
        with open(QUOTES_JSON, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        data = {"quotes": []}

    data.setdefault("quotes", []).append({
        "dest": a.dest.upper(),
        "check_in": a.check_in,
        "check_out": a.check_out,
        "adults": a.adults,
        "children": a.children,
        "per_night": a.per_night,
        "currency": "KRW",
        "area": a.area,
        "hotel": a.hotel,
        "source": a.source,
        "quoted_at": date.today().isoformat(),
    })
    with open(QUOTES_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"저장: {a.dest.upper()} {a.check_in}~{a.check_out} "
          f"1박 {a.per_night:,}원 ({a.source or '출처 미기재'})")
    print("커밋해야 다음 브리프가 이 값을 실측으로 쓴다.")


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="숙박 견적 링크·저장")
    sub = p.add_subparsers(dest="cmd", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--dest", required=True, help="목적지 코드 (예: CTS)")
    common.add_argument("--check-in", required=True)
    common.add_argument("--check-out", required=True)
    common.add_argument("--adults", type=int, default=2)
    common.add_argument("--children", type=int, default=0)

    sub.add_parser("links", parents=[common],
                   help="조건이 채워진 예약처 링크 출력")

    add = sub.add_parser("add", parents=[common], help="확인한 1박 값 저장")
    add.add_argument("--per-night", type=int, required=True, help="1박 가격(원)")
    add.add_argument("--area", default="", help="구역 (예: 삿포로역)")
    add.add_argument("--hotel", default="", help="숙소 이름 (선택)")
    add.add_argument("--source", default="", help="확인한 사이트 (예: booking.com)")
    return p.parse_args(argv)


def run(argv=None):
    a = parse_args(argv)
    if a.cmd == "links":
        cmd_links(a)
    else:
        cmd_add(a)


if __name__ == "__main__":
    run()
