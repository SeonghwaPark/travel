"""탐색 결과 집계·순위 로직.

순수 함수만 둔다 — 네트워크 없이 테스트할 수 있어야 하고, 조회(main.py)와
판단(여기)을 섞지 않는다.
"""

import statistics


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
        "observed": len(prices),
    }


def rank(summaries):
    """최저가 오름차순. 같은 값이면 기간 중앙값 대비 하락폭이 큰 쪽을 앞에 둔다."""
    return sorted((s for s in summaries if s),
                  key=lambda s: (s["best_price"], -s["dip_pct"]))


def _won(n):
    return f"{n:,}원"


def to_markdown(result):
    """커밋해두고 사람이 읽을 결과 표."""
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

    lines += [
        "| # | 목적지 | 총액 | 1인당 | 출발 | 귀국 | 박 | 기간 중앙값 대비 |",
        "|---|--------|------|-------|------|------|----|------------------|",
    ]
    for i, r in enumerate(result["ranking"], 1):
        dip = f"−{r['dip_pct']}%" if r["dip_pct"] > 0 else "—"
        lines.append(
            f"| {i} | {r['name']} ({r['code']}) | {_won(r['best_price'])} | "
            f"{_won(r['per_person'])} | {r['departure_date']} | {r['return_date']} | "
            f"{r['nights']} | {dip} |"
        )

    lines += [
        "",
        "> **기간 중앙값 대비**는 그 목적지의 조회 기간 안에서 이 날짜가 얼마나 싼지를 뜻한다.",
        "> 목적지끼리 비교하는 값이 아니라, 같은 목적지 안에서 타이밍이 좋은지를 본다.",
        "",
        "> 가격은 Google Flights 표시가(왕복, 전체 승객 합계)다. 실제 결제가는 예약처에서 확인해야 한다.",
    ]

    if result.get("failed"):
        lines += ["", f"조회 실패: {', '.join(result['failed'])}"]

    return "\n".join(lines)
