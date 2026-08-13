"""교통 구간 요금 합산 및 패스 손익 계산.

실시간 조회가 아니다. 열차 요금·소요시간은 잘 안 변하므로 transport.json에
표로 들고 있고, 여기서는 "이 일정이면 패스가 이득인가"만 계산한다.

순수 함수라 네트워크가 필요 없고, 요금이 바뀌면 JSON만 고치면 된다.
"""

import json
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRANSPORT_JSON = os.path.join(_ROOT, "transport.json")


def load(path=None):
    with open(path or TRANSPORT_JSON, encoding="utf-8") as f:
        return json.load(f)


def _region(data, region_id):
    region = data["regions"].get(region_id)
    if region is None:
        raise KeyError(f"모르는 지역: {region_id}")
    return region


def leg_total(region, leg_ids):
    """구간 목록의 개별권 합계.

    반환: (합계, 구간 상세, 표에 없는 구간 목록)
    표에 없는 구간은 조용히 빼지 않고 따로 돌려준다 — 0원으로 치면
    패스가 손해인데도 이득으로 보인다.
    """
    legs = region["legs"]
    total, detail, unknown = 0, [], []
    for lid in leg_ids:
        leg = legs.get(lid)
        if leg is None:
            unknown.append(lid)
            continue
        total += leg["fare"]
        detail.append({"id": lid, **leg})
    return total, detail, unknown


def compare_passes(region, leg_ids, trip_days=None):
    """구간 합계와 각 패스를 비교한다.

    trip_days를 주면 패스 유효일수 안에 일정이 들어가는지도 함께 본다.
    """
    total, detail, unknown = leg_total(region, leg_ids)

    options = []
    for p in region.get("passes", []):
        fits = None if trip_days is None else p["days"] >= trip_days
        options.append({
            "id": p["id"],
            "name": p["name"],
            "days": p["days"],
            "price": p["price"],
            "note": p.get("note", ""),
            "savings": total - p["price"],       # 양수면 패스가 이득
            "worth_it": total > p["price"],
            "covers_trip_length": fits,
        })

    # 이득이 큰 순. 같으면 싼 패스 먼저.
    options.sort(key=lambda o: (-o["savings"], o["price"]))
    return {
        "currency": region.get("currency", "JPY"),
        "individual_total": total,
        "legs": detail,
        "unknown_legs": unknown,
        "passes": options,
        "fares_verified": region.get("fares_verified", False),
        "fares_noted_at": region.get("fares_noted_at"),
        "source": region.get("source"),
    }


def plan(region_id, leg_ids, trip_days=None, data=None):
    """지역 + 구간 목록으로 손익 계산 결과를 만든다."""
    data = data or load()
    region = _region(data, region_id)
    result = compare_passes(region, leg_ids, trip_days)
    result["region"] = region_id
    result["region_name"] = region["name"]

    best = result["passes"][0] if result["passes"] else None
    if best and best["worth_it"]:
        cur = result["currency"]
        result["verdict"] = (
            f"{best['name']}가 {best['savings']:,}{cur} 이득입니다 "
            f"(개별권 {result['individual_total']:,} vs 패스 {best['price']:,})."
        )
        # 유효일수가 일정보다 짧으면 이득이 그대로 실현되지 않는다. 별도 필드로만
        # 두면 놓치기 쉬우므로 판정문에 붙인다.
        if best["covers_trip_length"] is False:
            covering = next((p for p in result["passes"]
                             if p["covers_trip_length"] and p["worth_it"]), None)
            result["verdict"] += (
                f" 다만 유효 {best['days']}일이 일정 {trip_days}일보다 짧아, "
                f"기간 밖 구간은 따로 사야 하므로 실제 이득은 줄어듭니다."
            )
            result["verdict"] += (
                f" 일정 전체를 덮으면서 이득인 건 {covering['name']}입니다."
                if covering else
                " 일정 전체를 덮는 패스 중에는 이득인 것이 없습니다."
            )
    else:
        cheapest = min(region.get("passes", []), key=lambda p: p["price"], default=None)
        if cheapest:
            result["verdict"] = (
                f"개별권이 낫습니다 (합계 {result['individual_total']:,}{result['currency']}, "
                f"가장 싼 패스가 {cheapest['price']:,})."
            )
        else:
            result["verdict"] = f"개별권 합계 {result['individual_total']:,}{result['currency']}."

    if result["unknown_legs"]:
        result["verdict"] += (
            f" ※ 요금표에 없는 구간이 있어 합계가 실제보다 적습니다: "
            f"{', '.join(result['unknown_legs'])}"
        )
    if not result["fares_verified"]:
        result["verdict"] += " ※ 요금은 어림값이니 예약 전 확인하세요."

    total_minutes = sum(l["minutes"] for l in result["legs"])
    result["total_minutes"] = total_minutes
    result["total_hours"] = round(total_minutes / 60, 1)
    return result
