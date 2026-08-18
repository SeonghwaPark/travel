"""탐색 결과 집계·순위 로직.

순수 함수만 둔다 — 네트워크 없이 테스트할 수 있어야 하고, 조회(main.py)와
판단(여기)을 섞지 않는다.
"""

import statistics

TOP_DATES = 10           # 목적지별로 마크다운에 싣는 싼 출발일 수
DETAIL_DESTINATIONS = 8  # 날짜 표를 실을 상위 목적지 수 (JSON에는 전부 들어간다)


def summarize(dest_code, info, offers_by_nights, pax):
    """한 목적지의 조회 결과를 요약한다.

    offers_by_nights: {박수: [{departure_date, return_date, price}, ...]}
    pax: 가격을 나눌 인원 수 (성인+소아. 무릎유아는 좌석이 없어 제외)

    반환 None이면 가격을 하나도 못 받은 것.
    """
    flat = []
    for nights, offers in offers_by_nights.items():
        for o in offers:
            if o.get("price"):
                flat.append({**o, "nights": nights})
    if not flat:
        return None

    prices = [o["price"] for o in flat]
    best = min(flat, key=lambda o: o["price"])
    median = int(statistics.median(prices))

    # 출발일별 최저가 곡선. 가격 그래프는 날짜별 가격을 전부 받아오는데 최저가
    # 한 건만 남기면 "그럼 3일 출발은 얼마인데?"에 답하려고 스캔을 또 돌려야 한다.
    # 같은 출발일에 박수가 여럿이면 싼 쪽만 남긴다.
    by_date = {}
    for o in flat:
        cur = by_date.get(o["departure_date"])
        if cur is None or o["price"] < cur["price"]:
            by_date[o["departure_date"]] = {
                "departure_date": o["departure_date"],
                "return_date": o["return_date"],
                "nights": o["nights"],
                "price": o["price"],
                "per_person": round(o["price"] / pax) if pax else o["price"],
            }

    return {
        "code": dest_code,
        "name": info.get("name", dest_code),
        "country": info.get("country", ""),
        "best_price": best["price"],
        "per_person": round(best["price"] / pax) if pax else best["price"],
        "departure_date": best["departure_date"],
        "return_date": best["return_date"],
        "nights": best["nights"],
        "median_price": median,
        # 그 목적지 안에서 이 날짜가 얼마나 좋은 타이밍인가 (기간 중앙값 대비)
        "dip_pct": round((median - best["price"]) / median * 100, 1) if median else 0.0,
        "winter_snow": info.get("winter_snow"),
        "observed": len(prices),
        "date_curve": [by_date[d] for d in sorted(by_date)],
    }


def cheapest_dates(summary, n=10):
    """한 목적지의 싼 출발일 상위 n개."""
    return sorted(summary.get("date_curve", []), key=lambda d: d["price"])[:n]


def rank(summaries):
    """최저가 오름차순. 같은 값이면 기간 중앙값 대비 하락폭이 큰 쪽을 앞에 둔다."""
    return sorted((s for s in summaries if s),
                  key=lambda s: (s["best_price"], -s["dip_pct"]))


def snow_label(ws):
    """설경 축을 한 칸에 담는다. 값이 없으면 '—'.

    세 축을 한 숫자로 뭉개지 않는다 — 발밑에 눈이 있는 것(city), 눈을 밟으러
    나가는 것(daytrip_min), 설산을 바라보는 것(view_min)은 서로 다른 여행이다.
    나고야(시내 0·밟기 140분)와 고마쓰(시내 2)를 같은 점수로 묶으면 안 된다.

    표 한 칸이라 시내 적설에 더해 '가까운 쪽 하나'만 붙인다. 나머지는 JSON에 있다.
    """
    if not ws:
        return "—"
    city = ws.get("city")
    if city is None:
        return "—"
    if city >= 2:
        return f"시내 {city}"
    day, view = ws.get("daytrip_min"), ws.get("view_min")
    near = None
    if day is not None and view is not None:
        near = (f"밟기 {day}분" if day <= view else f"조망 {view}분")
    elif day is not None:
        near = f"밟기 {day}분"
    elif view is not None:
        near = f"조망 {view}분"
    if city == 1:
        return "시내 1" + (f" · {near}" if near else "")
    return near or "없음"


def _won(n):
    return f"{n:,}원"


def to_markdown(result, contexts=None):
    """커밋해두고 사람이 읽을 결과 표.

    contexts: {목적지코드: trend.context()} — 과거 스캔 대비 위치. 있으면 열이 하나 는다.
    """
    contexts = contexts or {}
    m = result["meta"]
    pax_desc = f"성인 {m['adults']}"
    if m["children"]:
        pax_desc += f" · 소아 {m['children']}"
    if m["infants"]:
        pax_desc += f" · 유아 {m['infants']}"

    lines = [
        f"# {m['origin']} 출발 · {m['start']} ~ {m['end']} 최저가 탐색",
        "",
        f"- **인원**: {pax_desc} (가격은 **전체 승객 합계**)",
        f"- **여행 기간**: {', '.join(str(n) + '박' for n in m['nights'])}",
        f"- **조회 목적지**: {m['scanned']}곳 중 {len(result['ranking'])}곳 응답",
        f"- **조회 시각**: {m['scanned_at']}",
        "",
    ]

    if not result["ranking"]:
        lines += ["> 가격을 받아오지 못했습니다. 로그를 확인하세요.", ""]
        return "\n".join(lines)

    has_ctx = any(contexts.get(r["code"]) for r in result["ranking"])
    if has_ctx:
        lines += [
            "| # | 목적지 | 총액 | 1인당 | 출발 | 귀국 | 박 | 설경 | 기간 중앙값 대비 | 과거 스캔 대비 |",
            "|---|--------|------|-------|------|------|----|------|------------------|----------------|",
        ]
    else:
        lines += [
            "| # | 목적지 | 총액 | 1인당 | 출발 | 귀국 | 박 | 설경 | 기간 중앙값 대비 |",
            "|---|--------|------|-------|------|------|----|------|------------------|",
        ]
    for i, r in enumerate(result["ranking"], 1):
        dip = f"−{r['dip_pct']}%" if r["dip_pct"] > 0 else "—"
        row = (f"| {i} | {r['name']} ({r['code']}) | {_won(r['best_price'])} | "
               f"{_won(r['per_person'])} | {r['departure_date']} | {r['return_date']} | "
               f"{r['nights']} | {snow_label(r.get('winter_snow'))} | {dip} |")
        if has_ctx:
            from . import trend as trend_mod
            row += f" {trend_mod.describe(contexts.get(r['code'])) or '—'} |"
        lines.append(row)

    lines += [
        "",
        "> **기간 중앙값 대비**는 그 목적지의 조회 기간 안에서 이 날짜가 얼마나 싼지를 뜻한다.",
        "> 목적지끼리 비교하는 값이 아니라, 같은 목적지 안에서 타이밍이 좋은지를 본다.",
    ]
    if has_ctx:
        lines += [
            "",
            "> **과거 스캔 대비**는 같은 조건(기간·박수·인원)으로 돌린 이전 스캔들과 비교한 값이다.",
            "> 이게 있어야 '지금 사도 되는 가격인가'에 답할 수 있다. 관측 2회부터 나온다.",
        ]
    lines += [
        "",
        "> 가격은 Google Flights 표시가(왕복, 전체 승객 합계)다. 실제 결제가는 예약처에서 확인해야 한다.",
    ]

    # 날짜별 곡선 — 상위 목적지만. 전부 실으면 25곳 × 날짜라 표가 읽기 어려워진다.
    detailed = result["ranking"][:DETAIL_DESTINATIONS]
    if any(r.get("date_curve") for r in detailed):
        lines += ["", "---", "", f"## 목적지별 싼 출발일 (상위 {TOP_DATES}개)", ""]
        if len(result["ranking"]) > DETAIL_DESTINATIONS:
            lines += [f"> 순위 상위 {DETAIL_DESTINATIONS}곳만 싣는다. "
                      f"나머지 {len(result['ranking']) - DETAIL_DESTINATIONS}곳의 "
                      f"날짜별 가격은 같은 이름의 JSON 파일에 전부 들어 있다.", ""]
        for r in detailed:
            top = cheapest_dates(r, TOP_DATES)
            if not top:
                continue
            lines += [
                f"### {r['name']} ({r['code']})",
                "",
                "| 출발 | 귀국 | 박 | 총액 | 1인당 |",
                "|------|------|----|------|-------|",
            ]
            for d in top:
                lines.append(f"| {d['departure_date']} | {d['return_date']} | {d['nights']} | "
                             f"{_won(d['price'])} | {_won(d['per_person'])} |")
            lines.append("")

    if result.get("failed"):
        lines += ["", f"조회 실패: {', '.join(result['failed'])}"]

    return "\n".join(lines)
