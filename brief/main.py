"""브리프 CLI — 목적지·시기만 던지면 종합 판단이 나온다.

    python -m brief.main --nights 6 --adults 2 --children 1
    python -m brief.main --candidates CTS,TPE,HKG,NRT --nights 6 --prefer family

스캔 결과(explore/results/)를 읽어 계산만 하므로 네트워크가 필요 없다.
후보를 안 주면 스캔 결과가 있는 목적지를 전부 비교한다.
"""

import argparse
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))

from brief import compose  # noqa: E402

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "explore", "results")


def _won(n):
    return f"{n:,}원"


def transport_costs(candidates, profiles, adults, children, legs_by_region=None):
    """지역 교통 데이터가 있는 목적지만 개별권 합계를 계산한다."""
    try:
        import transport as tmod
    except ImportError:
        return {}
    legs_by_region = legs_by_region or {}
    heads = adults + children
    out = {}
    for code in candidates:
        profile = profiles["destinations"].get(code, {})
        region = profile.get("transport_region")
        legs = legs_by_region.get(region)
        if not (region and legs):
            continue
        try:
            plan = tmod.plan(region, legs, data=tmod.load())
        except KeyError:
            continue
        # 엔 -> 원 환산은 하지 않는다. 통화가 섞이면 합계가 거짓이 된다.
        out[code] = 0
        out[f"{code}__detail"] = plan
    return out


def to_markdown(result, meta, recommendation):
    lines = [
        f"# 여행 브리프 — {meta['nights']}박, 성인 {meta['adults']}"
        + (f" · 아동 {meta['children']}" if meta["children"] else ""),
        "",
        f"- **생성**: {meta['built_at']}",
        f"- **비교 후보**: {len(result['rows'])}곳",
        "",
    ]

    if recommendation:
        r = recommendation["row"]
        lines += [
            f"## 추천 — {recommendation['name']}",
            "",
            f"**총예산 {_won(r['budget']['total'])}** "
            f"(1인 {_won(r['budget']['per_person'])})",
            "",
            f"{recommendation['why']}",
            "",
        ]
        if r["flight"].get("departure_date"):
            lines.append(f"- **항공권 최적 일정**: {r['flight']['departure_date']} ~ "
                         f"{r['flight']['return_date']} ({r['flight']['nights']}박)")
        if r["season_note"]:
            lines.append(f"- **시기**: {r['season_note']}")
        lines.append("")

    lines += [
        "## 후보 비교",
        "",
        "| 목적지 | 총예산 | 범위 | 1인 | 항공권 | 숙박 | 현지비 | 비행 | 아이 |",
        "|--------|--------|------|-----|--------|------|--------|------|------|",
    ]
    for r in result["rows"]:
        b = {i["label"]: i for i in r["budget"]["items"]}
        stay_mark = "" if r["stay"] else "*"
        lines.append(
            f"| {r['name']} | **{_won(r['budget']['total'])}** "
            f"| {_won(r['budget']['total_low'])}~{_won(r['budget']['total_high'])} "
            f"| {_won(r['budget']['per_person'])} "
            f"| {_won(b['항공권']['amount'])} "
            f"| {_won(b['숙박']['amount'])}{stay_mark} "
            f"| {_won(b['현지비']['amount'])} "
            f"| {r['flight_hours']}h "
            f"| {'★' * r['family_score']} |"
        )
    lines += [
        "",
        "> `*` 표시는 숙박 실측이 없어 어림값을 쓴 경우다. 현지비는 항상 추정치다.",
        "",
    ]
    if result["rows"] and result["rows"][0].get("tier_peers"):
        n = result["rows"][0]["tier_peers"] + 1
        lines += [f"> ⚠️ 상위 {n}곳은 추정 오차 범위가 겹쳐 **총액 순위를 확정할 수 없다**. "
                  "숙박 견적(`python -m brief.quote`)을 넣으면 범위가 좁혀진다.", ""]

    lines += ["## 목적지별 상세", ""]
    for r in result["rows"]:
        lines += [f"### {r['name']} — {_won(r['budget']['total'])}", ""]
        lines += ["| 항목 | 금액 | 출처 | 근거 |", "|------|------|------|------|"]
        for i in r["budget"]["items"]:
            lines.append(f"| {i['label']} | {_won(i['amount'])} | {i['source']} | {i['note']} |")
        lines += ["", f"- **아이 적합도** {r['family_score']}/5 — {r['family_why']}"]
        if r["season_note"]:
            lines.append(f"- **시기** — {r['season_note']}")
        kid = [h for h in r["highlights"] if h.get("kid")]
        if kid:
            lines.append("- **아이와 갈 만한 곳**")
            for h in kid[:5]:
                lines.append(f"  - {h['name']} — {h['for']}")
        lines.append("")

    if result["skipped"]:
        lines += ["## 비교에서 빠진 곳", ""]
        for code, why in result["skipped"]:
            lines.append(f"- {code}: {why}")
        lines.append("")

    return "\n".join(lines)


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="여행 브리프 — 총예산 합산·비교·추천")
    p.add_argument("--candidates", default="",
                   help="비교할 목적지 코드 (비우면 스캔 결과가 있는 전부)")
    p.add_argument("--nights", type=int, required=True)
    p.add_argument("--adults", type=int, default=2)
    p.add_argument("--children", type=int, default=0)
    p.add_argument("--prefer", default="balanced",
                   choices=["budget", "family", "balanced"])
    p.add_argument("--tag", default="")
    return p.parse_args(argv)


def run(argv=None):
    a = parse_args(argv)
    profiles = compose.load_profiles()
    flights = compose.read_flight_scans(adults=a.adults, children=a.children)
    stays = compose.read_stay_scans()
    quotes = compose.read_lodging_quotes(adults=a.adults, children=a.children)

    if a.candidates:
        candidates = [c.strip().upper() for c in a.candidates.split(",") if c.strip()]
    else:
        candidates = sorted(set(flights) & set(profiles["destinations"]))
    if not candidates:
        raise SystemExit("비교할 후보가 없습니다. 먼저 항공권 스캔을 돌리세요.")

    print(f"▶ 후보 {len(candidates)}곳 | 항공권 실측 {len(flights)}곳 "
          f"| 숙박 스캔 {len(stays)}곳 | 직접 견적 {len(quotes)}건")

    result = compose.build(candidates, profiles, flights, stays,
                           a.adults, a.children, a.nights, quotes=quotes)
    rec = compose.recommend(result["rows"], a.prefer)

    meta = {
        "nights": a.nights, "adults": a.adults, "children": a.children,
        "prefer": a.prefer,
        "built_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    md = to_markdown(result, meta, rec)

    tag = a.tag or f"brief-{a.nights}n-{a.adults}a{a.children}c-{a.prefer}"
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, f"{tag}.md"), "w", encoding="utf-8") as f:
        f.write(md + "\n")
    with open(os.path.join(OUT_DIR, f"{tag}.json"), "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "recommendation":
                   {k: v for k, v in (rec or {}).items() if k != "row"},
                   "rows": result["rows"], "skipped": result["skipped"]},
                  f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(md)
    return result


if __name__ == "__main__":
    run()
