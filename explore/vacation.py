"""휴가·방학·공휴일 축 — 날짜를 고를 때 가격만큼 무거운 조건.

2027년 1~2월 검토에서 결론을 가른 가장 큰 변수가 "휴가 며칠 쓰나"였는데
코드에 하나도 없어서 매번 손으로 셌다. 공휴일 목록도 그때그때 손으로 넣었다.
그 계산이 어디에도 안 쌓여서, 다음 여행에 또 처음부터 해야 했다.

세 가지를 답한다.
  - 이 일정에 휴가가 며칠 드나 (주말·공휴일은 빼고)
  - 그 휴가가 돈으로 얼마인가
  - 이 일정이 아이 방학 안에 들어가나

휴가 가치는 미사용 연차를 수당으로 받을 때만 실제 현금이다. 소멸되는
연차라면 value_krw를 0으로 두면 계산에서 저절로 빠진다.

    python -m explore.vacation --start 2027-01-16 --end 2027-01-23
"""

import argparse
import json
import os
from datetime import date, timedelta

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CALENDAR_JSON = os.path.join(_ROOT, "calendar.json")


def load(path=None):
    try:
        with open(path or CALENDAR_JSON, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def holidays(data=None, year=None):
    """공휴일 날짜 집합. year를 주면 그 해만."""
    data = load() if data is None else data
    out = set()
    for y, items in (data.get("holidays") or {}).items():
        if year is not None and str(year) != str(y):
            continue
        for h in items:
            if h.get("date"):
                out.add(h["date"])
    return out


def _days(start, end):
    d0, d1 = date.fromisoformat(start), date.fromisoformat(end)
    if d1 < d0:
        raise ValueError("귀국일이 출발일보다 빠릅니다")
    return [d0 + timedelta(i) for i in range((d1 - d0).days + 1)]


def workdays(start, end, data=None):
    """출발~귀국 사이 실제로 휴가를 써야 하는 날 수.

    주말과 공휴일은 빼고 센다. 설 연휴처럼 공휴일이 평일에 걸리면 휴가가
    확 줄어드는데, 그걸 반영하지 않으면 날짜 비교가 통째로 어긋난다.
    """
    hol = holidays(data)
    return sum(1 for d in _days(start, end)
               if d.weekday() < 5 and d.isoformat() not in hol)


def cost(start, end, data=None, value=None):
    """휴가 소요 비용. {days, value, total, paid_out}"""
    data = load() if data is None else data
    v = data.get("vacation") or {}
    per = v.get("value_krw", 0) if value is None else value
    n = workdays(start, end, data)
    return {"days": n, "value": per, "total": n * per,
            "paid_out": v.get("paid_out"), "basis": v.get("basis")}


def in_break(start, end, school=None, data=None):
    """일정이 아이 방학 안에 온전히 들어가는가. {ok, label, estimated, breaks}

    걸치기만 해도 안 된다 — 하루라도 학기 중이면 못 가는 일정이다.
    """
    data = load() if data is None else data
    schools = data.get("schools") or {}
    if not schools:
        return {"ok": None, "reason": "등록된 학교가 없습니다"}
    key = school or next(iter(schools))
    s = schools.get(key)
    if s is None:
        return {"ok": None, "reason": f"학교를 찾지 못함: {key}"}
    for b in s.get("breaks", []):
        if b["from"] <= start and end <= b["to"]:
            return {"ok": True, "school": key, "label": b.get("label"),
                    "estimated": b.get("estimated", False), "note": b.get("note")}
    return {"ok": False, "school": key,
            "reason": "방학 기간을 벗어납니다",
            "breaks": [(b["from"], b["to"], b.get("label")) for b in s.get("breaks", [])]}


def describe(start, end, data=None):
    """한 일정에 대한 요약 한 덩어리."""
    data = load() if data is None else data
    c = cost(start, end, data)
    b = in_break(start, end, data=data)
    nights = (date.fromisoformat(end) - date.fromisoformat(start)).days
    return {"start": start, "end": end, "nights": nights, **c, "break": b}


def run(argv=None):
    ap = argparse.ArgumentParser(description="휴가·방학 계산")
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--school", default=None)
    a = ap.parse_args(argv)

    data = load()
    r = describe(a.start, a.end, data)
    print(f"{r['start']} ~ {r['end']}  ({r['nights']}박)")
    print(f"  휴가 {r['days']}일 x {r['value']:,}원 = {r['total']:,}원"
          + ("" if r["paid_out"] else "  (연차 수당 미지급 — 실제 현금은 아님)"))
    if r["basis"]:
        print(f"    근거: {r['basis']}")
    b = r["break"]
    if b.get("ok") is True:
        tail = " (확정 아님 — 학교 미공개)" if b.get("estimated") else ""
        print(f"  방학 {b['school']} · {b['label']} 안에 들어감{tail}")
    elif b.get("ok") is False:
        print(f"  방학 {b['school']} — {b['reason']}")
        for f, t, lab in b.get("breaks", []):
            print(f"    {f} ~ {t}  {lab}")
    else:
        print(f"  방학 확인 불가 — {b.get('reason')}")
    return r


if __name__ == "__main__":
    run()
