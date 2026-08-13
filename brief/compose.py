"""여행 브리프 — 항공권·숙박·교통·현지비를 합쳐 후보를 비교한다.

수집(네트워크)과 종합(계산)을 분리하는 게 이 모듈의 존재 이유다.
스캔은 느리고 깨지기 쉽고 Actions에서만 되지만, 종합은 쌓인 결과 파일만 읽으면
되므로 어디서나 즉시 돈다. 수집기가 깨져도 판단은 계속할 수 있다.

가격 출처를 항상 표시한다. 실측과 어림값을 섞어 놓고 출처를 안 밝히면
합계가 실제보다 정확해 보인다.
"""

import json
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROFILES_JSON = os.path.join(_ROOT, "trip_profiles.json")
RESULTS_DIR = os.path.join(_ROOT, "explore", "results")

MEASURED = "실측"
ESTIMATED = "추정"


def load_profiles(path=None):
    with open(path or PROFILES_JSON, encoding="utf-8") as f:
        return json.load(f)


# ── 스캔 결과 읽기 ──

def read_flight_scans(results_dir=None, adults=None, children=None):
    """항공권 스캔 결과를 목적지별로 모은다. 같은 목적지가 여러 번이면 최신.

    adults/children을 주면 그 인원으로 조회한 스캔만 쓴다. 소아 요금은 성인과
    다르게 붙어서, 인원이 다른 스캔을 섞으면 후보 비교가 통째로 거짓이 된다.
    """
    results_dir = results_dir or RESULTS_DIR
    if not os.path.isdir(results_dir):
        return {}

    best = {}
    for fname in sorted(os.listdir(results_dir)):
        if not fname.endswith(".json") or fname.startswith(("stay-", "brief-")):
            continue
        try:
            with open(os.path.join(results_dir, fname), encoding="utf-8") as f:
                data = json.load(f)
            meta, ranking = data["meta"], data["ranking"]
        except (OSError, json.JSONDecodeError, KeyError):
            continue
        if adults is not None and meta.get("adults") != adults:
            continue
        if children is not None and meta.get("children") != children:
            continue
        for row in ranking:
            code = row.get("code")
            if not code:
                continue
            prev = best.get(code)
            if prev is None or meta["scanned_at"] > prev["scanned_at"]:
                best[code] = {**row, "scanned_at": meta["scanned_at"],
                              "party": (meta["adults"], meta["children"]),
                              "source_file": fname}
    return best


def read_stay_scans(results_dir=None):
    """숙박 스캔 결과를 목적지별로. 가격이 실제로 있는 것만."""
    results_dir = results_dir or RESULTS_DIR
    if not os.path.isdir(results_dir):
        return {}

    out = {}
    for fname in sorted(os.listdir(results_dir)):
        if not (fname.startswith("stay-") and fname.endswith(".json")):
            continue
        try:
            with open(os.path.join(results_dir, fname), encoding="utf-8") as f:
                data = json.load(f)
            code = data["meta"]["destination"]
            priced = [a for a in data["areas"] if a.get("prices")]
        except (OSError, json.JSONDecodeError, KeyError):
            continue
        if not priced:
            continue
        cheapest = min(priced, key=lambda a: a["prices"]["min_per_night"])
        out[code] = {
            "per_night": cheapest["prices"]["median_per_night"],
            "area": cheapest["name"],
            "scanned_at": data["meta"]["scanned_at"],
            "source_file": fname,
        }
    return out


# ── 합산 ──

def estimate_budget(profile, nights, adults, children, flight_total,
                    stay=None, transport_total=0, child_ratio=0.6):
    """한 목적지의 총예산. 각 항목에 출처(실측/추정)를 붙인다."""
    days = nights + 1
    heads = adults + children * child_ratio

    if stay:
        per_night, stay_src = stay["per_night"], MEASURED
    else:
        per_night, stay_src = profile["lodging_per_night"], ESTIMATED
    lodging = per_night * nights

    daily = round(profile["daily_cost"] * heads) * days

    items = [
        {"label": "항공권", "amount": flight_total, "source": MEASURED,
         "note": f"{adults}성인+{children}소아 왕복 합계"},
        {"label": "숙박", "amount": lodging, "source": stay_src,
         "note": f"1박 {per_night:,}원 × {nights}박"
                 + (f" ({stay['area']})" if stay else " (3인 1실 중급 어림)")},
        {"label": "현지비", "amount": daily, "source": ESTIMATED,
         "note": f"1인 1일 {profile['daily_cost']:,}원 × {days}일 (아동 {child_ratio}배)"},
    ]
    if transport_total:
        items.append({"label": "교통(구간·패스)", "amount": transport_total,
                      "source": ESTIMATED, "note": "지역 내 이동"})

    total = sum(i["amount"] for i in items)
    return {
        "total": total,
        "per_person": round(total / max(1, adults + children)),
        "items": items,
        "measured_ratio": round(
            sum(i["amount"] for i in items if i["source"] == MEASURED) / total, 2)
        if total else 0.0,
    }


def _month_of(date_str):
    try:
        return int(date_str.split("-")[1])
    except (AttributeError, IndexError, ValueError):
        return None


def build(candidates, profiles, flights, stays, adults, children,
          nights, transport_costs=None):
    """후보별 예산·적합도를 계산해 총액 오름차순으로 돌려준다."""
    transport_costs = transport_costs or {}
    child_ratio = profiles.get("child_cost_ratio", 0.6)
    rows, skipped = [], []

    for code in candidates:
        profile = profiles["destinations"].get(code)
        flight = flights.get(code)
        if profile is None:
            skipped.append((code, "프로필 없음"))
            continue
        if flight is None:
            skipped.append((code, "항공권 스캔 결과 없음"))
            continue
        # 인원이 다른 스캔이 섞이면 비교가 거짓이 된다 — 여기서 한 번 더 막는다
        if flight.get("party") not in (None, (adults, children)):
            skipped.append((code,
                            f"인원 불일치 (스캔 {flight['party'][0]}성인"
                            f"{flight['party'][1]}소아)"))
            continue

        budget = estimate_budget(
            profile, nights, adults, children, flight["best_price"],
            stay=stays.get(code), transport_total=transport_costs.get(code, 0),
            child_ratio=child_ratio)

        month = _month_of(flight.get("departure_date"))
        in_season = month in profile.get("best_months", []) if month else None

        rows.append({
            "code": code,
            "name": profile["name"],
            "budget": budget,
            "flight": flight,
            "stay": stays.get(code),
            "flight_hours": profile["flight_hours"],
            "family_score": profile["family"]["score"],
            "family_why": profile["family"]["why"],
            "season_note": profile.get("season_note", ""),
            "in_season": in_season,
            "highlights": profile.get("highlights", []),
        })

    rows.sort(key=lambda r: r["budget"]["total"])
    return {"rows": rows, "skipped": skipped}


def recommend(rows, prefer="balanced"):
    """추천 하나와 이유. prefer: budget | family | balanced"""
    if not rows:
        return None
    if prefer == "budget":
        pick = rows[0]
        why = "총예산이 가장 낮습니다."
    elif prefer == "family":
        pick = max(rows, key=lambda r: (r["family_score"], -r["budget"]["total"]))
        why = f"아이 동반 적합도가 가장 높습니다 ({pick['family_score']}/5). {pick['family_why']}"
    else:
        # 총예산이 최저 대비 25% 이내인 후보 중 적합도가 가장 높은 곳
        floor = rows[0]["budget"]["total"]
        near = [r for r in rows if r["budget"]["total"] <= floor * 1.25] or rows[:1]
        pick = max(near, key=lambda r: (r["family_score"], -r["budget"]["total"]))
        why = (f"최저가({rows[0]['name']}) 대비 "
               f"{pick['budget']['total'] - floor:+,}원 안에서 적합도가 가장 높습니다 "
               f"({pick['family_score']}/5).")
    return {"code": pick["code"], "name": pick["name"], "why": why, "row": pick}
