"""브리프 합산·비교·추천 테스트 (네트워크 불필요).

가장 중요한 건 '인원이 다른 스캔이 섞이지 않는가'다. 소아 요금은 성인과 다르게
붙어서, 섞이면 표는 멀쩡해 보이는데 비교가 통째로 거짓이 된다.
"""

import json
import os
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from brief import compose  # noqa: E402

PROFILES = {
    "child_cost_ratio": 0.6,
    "destinations": {
        "AAA": {"name": "에이", "daily_cost": 50000, "flight_hours": 2.0,
                "lodging_per_night": 100000, "best_months": [2],
                "family": {"score": 5, "why": "아이 천국"},
                "season_note": "2월이 좋다",
                "highlights": [{"name": "놀이공원", "for": "종일", "kid": True},
                               {"name": "미술관", "for": "반나절", "kid": False}]},
        "BBB": {"name": "비", "daily_cost": 100000, "flight_hours": 4.0,
                "lodging_per_night": 200000, "best_months": [7],
                "family": {"score": 2, "why": "어른 취향"},
                "season_note": "여름이 좋다", "highlights": []},
    },
}


def _flight(code, price, party=(2, 1), dep="2027-02-17"):
    return {"code": code, "best_price": price, "departure_date": dep,
            "return_date": "2027-02-23", "nights": 6, "party": party,
            "scanned_at": "2026-08-13 08:00:00"}


# ── 예산 합산 ──

def test_budget_sums_flight_lodging_and_daily():
    b = compose.estimate_budget(PROFILES["destinations"]["AAA"], nights=6,
                                adults=2, children=1, flight_total=1000000)
    amounts = {i["label"]: i["amount"] for i in b["items"]}
    assert amounts["항공권"] == 1000000
    assert amounts["숙박"] == 600000                 # 100,000 × 6박
    assert amounts["현지비"] == 910000               # 50,000 × 2.6명 × 7일
    assert b["total"] == 2510000
    assert b["per_person"] == round(2510000 / 3)


def test_budget_marks_estimated_lodging():
    b = compose.estimate_budget(PROFILES["destinations"]["AAA"], 6, 2, 1, 1000000)
    lodging = [i for i in b["items"] if i["label"] == "숙박"][0]
    assert lodging["source"] == compose.ESTIMATED


def test_budget_prefers_measured_lodging():
    b = compose.estimate_budget(PROFILES["destinations"]["AAA"], 6, 2, 1, 1000000,
                                stay={"per_night": 150000, "area": "역앞"})
    lodging = [i for i in b["items"] if i["label"] == "숙박"][0]
    assert lodging["source"] == compose.MEASURED
    assert lodging["amount"] == 900000
    assert "역앞" in lodging["note"]


def test_budget_reports_measured_ratio():
    """어림값이 얼마나 섞였는지 알 수 있어야 한다."""
    b = compose.estimate_budget(PROFILES["destinations"]["AAA"], 6, 2, 1, 1000000)
    assert 0 < b["measured_ratio"] < 1        # 항공권만 실측


def test_child_counted_at_reduced_rate():
    solo = compose.estimate_budget(PROFILES["destinations"]["AAA"], 6, 2, 0, 0)
    with_kid = compose.estimate_budget(PROFILES["destinations"]["AAA"], 6, 2, 1, 0)
    daily_solo = [i for i in solo["items"] if i["label"] == "현지비"][0]["amount"]
    daily_kid = [i for i in with_kid["items"] if i["label"] == "현지비"][0]["amount"]
    assert daily_kid > daily_solo
    assert daily_kid < daily_solo * 1.5       # 아동은 0.6배지 1배가 아니다


# ── 인원 불일치 차단 ──

def test_build_skips_mismatched_party():
    """다른 인원으로 조회한 결과를 쓰면 비교가 거짓이 된다."""
    flights = {"AAA": _flight("AAA", 1000000, party=(2, 1)),
               "BBB": _flight("BBB", 500000, party=(2, 0))}
    r = compose.build(["AAA", "BBB"], PROFILES, flights, {}, 2, 1, 6)
    assert [row["code"] for row in r["rows"]] == ["AAA"]
    assert r["skipped"] == [("BBB", "인원 불일치 (스캔 2성인0소아)")]


def test_read_flight_scans_filters_by_party(tmp_path):
    def write(name, adults, children, code, price):
        (tmp_path / name).write_text(json.dumps({
            "meta": {"adults": adults, "children": children,
                     "scanned_at": "2026-08-13 08:00:00"},
            "ranking": [{"code": code, "best_price": price}],
        }, ensure_ascii=False), encoding="utf-8")

    write("a.json", 2, 1, "AAA", 1000000)
    write("b.json", 2, 0, "BBB", 500000)

    matched = compose.read_flight_scans(str(tmp_path), adults=2, children=1)
    assert set(matched) == {"AAA"}
    assert set(compose.read_flight_scans(str(tmp_path))) == {"AAA", "BBB"}


def test_read_flight_scans_takes_latest_per_destination(tmp_path):
    for name, when, price in (("old.json", "2026-08-01 00:00:00", 900000),
                              ("new.json", "2026-08-13 00:00:00", 800000)):
        (tmp_path / name).write_text(json.dumps({
            "meta": {"adults": 2, "children": 1, "scanned_at": when},
            "ranking": [{"code": "AAA", "best_price": price}],
        }), encoding="utf-8")
    got = compose.read_flight_scans(str(tmp_path), adults=2, children=1)
    assert got["AAA"]["best_price"] == 800000


def test_read_flight_scans_ignores_stay_and_brief_files(tmp_path):
    (tmp_path / "stay-X.json").write_text("{}", encoding="utf-8")
    (tmp_path / "brief-X.json").write_text("{}", encoding="utf-8")
    (tmp_path / "broken.json").write_text("not json", encoding="utf-8")
    assert compose.read_flight_scans(str(tmp_path)) == {}


def test_read_stay_scans_skips_results_without_prices(tmp_path):
    (tmp_path / "stay-a.json").write_text(json.dumps({
        "meta": {"destination": "AAA", "scanned_at": "2026-08-13 08:00:00"},
        "areas": [{"name": "구역", "prices": {"min_per_night": 90000,
                                              "median_per_night": 120000}}],
    }, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "stay-b.json").write_text(json.dumps({
        "meta": {"destination": "BBB", "scanned_at": "2026-08-13 08:00:00"},
        "areas": [{"name": "구역"}],
    }, ensure_ascii=False), encoding="utf-8")

    got = compose.read_stay_scans(str(tmp_path))
    assert set(got) == {"AAA"}
    assert got["AAA"]["per_night"] == 120000   # 중앙값을 쓴다


# ── 비교·추천 ──

def test_cheap_flight_can_lose_on_total():
    """이 도구의 존재 이유. BBB는 항공권이 150만원 싸지만 숙박·현지비가 비싸
    총액은 더 높다. 항공권만 보면 정반대 결론이 난다."""
    flights = {"AAA": _flight("AAA", 2000000), "BBB": _flight("BBB", 500000)}
    r = compose.build(["AAA", "BBB", "ZZZ"], PROFILES, flights, {}, 2, 1, 6)
    assert [row["code"] for row in r["rows"]] == ["AAA", "BBB"]
    totals = {row["code"]: row["budget"]["total"] for row in r["rows"]}
    assert totals["AAA"] < totals["BBB"]
    assert ("ZZZ", "프로필 없음") in r["skipped"]


def test_build_flags_out_of_season():
    flights = {"AAA": _flight("AAA", 1000000, dep="2027-02-17"),
               "BBB": _flight("BBB", 1000000, dep="2027-02-17")}
    r = compose.build(["AAA", "BBB"], PROFILES, flights, {}, 2, 1, 6)
    by = {row["code"]: row for row in r["rows"]}
    assert by["AAA"]["in_season"] is True       # 2월이 제철
    assert by["BBB"]["in_season"] is False      # 7월이 제철


def test_recommend_budget_picks_lowest_total():
    # BBB가 총액에서 이기려면 항공권이 숙박·현지비 차이(151만원)를 넘게 싸야 한다
    flights = {"AAA": _flight("AAA", 3000000), "BBB": _flight("BBB", 1000000)}
    rows = compose.build(["AAA", "BBB"], PROFILES, flights, {}, 2, 1, 6)["rows"]
    assert compose.recommend(rows, "budget")["code"] == "BBB"


def test_recommend_family_picks_highest_score_even_if_pricier():
    flights = {"AAA": _flight("AAA", 3000000), "BBB": _flight("BBB", 1000000)}
    rows = compose.build(["AAA", "BBB"], PROFILES, flights, {}, 2, 1, 6)["rows"]
    assert compose.recommend(rows, "family")["code"] == "AAA"


def test_recommend_balanced_trades_small_premium_for_fit():
    """조금 비싸도 적합도가 높으면 그쪽. 많이 비싸면 안 된다."""
    close = {"AAA": _flight("AAA", 1050000), "BBB": _flight("BBB", 1000000)}
    rows = compose.build(["AAA", "BBB"], PROFILES, close, {}, 2, 1, 6)["rows"]
    assert compose.recommend(rows, "balanced")["code"] == "AAA"

    far = {"AAA": _flight("AAA", 5000000), "BBB": _flight("BBB", 1000000)}
    rows = compose.build(["AAA", "BBB"], PROFILES, far, {}, 2, 1, 6)["rows"]
    assert compose.recommend(rows, "balanced")["code"] == "BBB"


def test_recommend_none_when_no_rows():
    assert compose.recommend([], "balanced") is None


# ── 배포 데이터 ──

def test_shipped_profiles_are_complete():
    data = compose.load_profiles()
    for code, d in data["destinations"].items():
        missing = ({"name", "daily_cost", "flight_hours", "lodging_per_night",
                    "family", "highlights"} - set(d))
        assert not missing, f"{code}에 없는 항목: {missing}"
        assert 1 <= d["family"]["score"] <= 5, code
        assert d["daily_cost"] > 0 and d["lodging_per_night"] > 0, code


# ── 계절·이벤트 배수 ──

PROFILE_M = {
    "name": "테스트", "daily_cost": 50000, "flight_hours": 2.0,
    "lodging_per_night": 100000, "lodging_confidence": "low",
    "family": {"score": 3, "why": ""}, "highlights": [],
    "season_multipliers": [
        {"from": "02-04", "to": "02-12", "factor": 1.9, "reason": "축제",
         "confidence": "medium", "lunar": False},
        {"from": "12-28", "to": "01-03", "factor": 1.5, "reason": "연말연시",
         "confidence": "medium", "lunar": False},
    ],
}


def test_season_multiplier_hits_event_window():
    assert compose.season_multiplier(PROFILE_M, "2027-02-10")["factor"] == 1.9
    assert compose.season_multiplier(PROFILE_M, "2027-02-10")["reason"] == "축제"


def test_season_multiplier_outside_window_is_one():
    assert compose.season_multiplier(PROFILE_M, "2027-02-17")["factor"] == 1.0


def test_season_multiplier_wraps_year_end():
    """연말연시처럼 해를 넘기는 구간도 잡아야 한다."""
    assert compose.season_multiplier(PROFILE_M, "2026-12-30")["factor"] == 1.5
    assert compose.season_multiplier(PROFILE_M, "2027-01-02")["factor"] == 1.5
    assert compose.season_multiplier(PROFILE_M, "2027-01-10")["factor"] == 1.0


def test_season_multiplier_handles_bad_date():
    for bad in (None, "", "2027", 20270210):
        assert compose.season_multiplier(PROFILE_M, bad)["factor"] == 1.0


def test_budget_applies_event_multiplier():
    plain = compose.estimate_budget(PROFILE_M, 6, 2, 1, 0, check_in="2027-02-17")
    peak = compose.estimate_budget(PROFILE_M, 6, 2, 1, 0, check_in="2027-02-10")
    lodging = lambda b: [i for i in b["items"] if i["label"] == "숙박"][0]
    assert lodging(plain)["amount"] == 600000
    assert lodging(peak)["amount"] == 1140000        # 100,000 × 1.9 × 6박
    assert "축제" in lodging(peak)["note"]


def test_measured_lodging_ignores_multiplier():
    """실측이 있으면 배수를 또 곱하면 안 된다 — 실측에 이미 반영돼 있다."""
    b = compose.estimate_budget(PROFILE_M, 6, 2, 1, 0, check_in="2027-02-10",
                                stay={"per_night": 150000, "area": "역앞"})
    lodging = [i for i in b["items"] if i["label"] == "숙박"][0]
    assert lodging["amount"] == 900000
    assert lodging["confidence"] == "high"


def test_measured_items_have_no_error_band():
    b = compose.estimate_budget(PROFILE_M, 6, 2, 1, 1000000)
    flight = [i for i in b["items"] if i["label"] == "항공권"][0]
    assert flight["low"] == flight["high"] == flight["amount"]


def test_estimated_items_carry_band():
    b = compose.estimate_budget(PROFILE_M, 6, 2, 1, 1000000)
    lodging = [i for i in b["items"] if i["label"] == "숙박"][0]
    assert lodging["low"] < lodging["amount"] < lodging["high"]
    assert b["total_low"] < b["total"] < b["total_high"]


# ── 구분 가능성 ──

def _row(name, total, low, high):
    return {"name": name, "budget": {"total": total, "total_low": low,
                                     "total_high": high}}


def test_overlapping_candidates_share_a_tier():
    """범위가 겹치면 순위를 말할 수 없다."""
    rows = [_row("A", 100, 80, 130), _row("B", 120, 95, 150)]
    compose.mark_separability(rows)
    assert rows[0]["tier"] == rows[1]["tier"] == 0
    assert rows[0]["tier_peers"] == 1


def test_separated_candidates_get_different_tiers():
    rows = [_row("A", 100, 90, 110), _row("B", 500, 450, 550)]
    compose.mark_separability(rows)
    assert rows[0]["tier"] != rows[1]["tier"]
    assert rows[0]["tier_peers"] == 0


def test_tiers_chain_transitively():
    """A~B가 겹치고 B~C가 겹치면 셋 다 한 그룹이다."""
    rows = [_row("A", 100, 80, 130), _row("B", 140, 120, 170),
            _row("C", 180, 160, 210), _row("D", 900, 880, 920)]
    compose.mark_separability(rows)
    assert [r["tier"] for r in rows] == [0, 0, 0, 1]


# ── 직접 확인 견적 ──

QUOTE = {"dest": "AAA", "check_in": "2027-02-17", "check_out": "2027-02-23",
         "adults": 2, "children": 1, "per_night": 150000, "currency": "KRW",
         "area": "역앞", "source": "booking.com", "quoted_at": "2026-08-10"}
TODAY = "2026-08-20"


def test_quote_matches_overlapping_window():
    q = compose.match_quote([QUOTE], "AAA", "2027-02-19", "2027-02-25", today=TODAY)
    assert q and q["per_night"] == 150000 and q["stale"] is False


def test_quote_matches_nearby_window():
    """창이 안 겹쳐도 체크인이 ±14일 안이면 같은 시즌으로 본다."""
    q = compose.match_quote([QUOTE], "AAA", "2027-02-25", "2027-03-03", today=TODAY)
    assert q is not None


def test_quote_rejects_far_window():
    """2월 견적을 7월 여행에 쓰면 안 된다 — 숙박비는 시기 따라 다르다."""
    assert compose.match_quote([QUOTE], "AAA", "2027-07-01", "2027-07-07",
                               today=TODAY) is None


def test_quote_rejects_other_destination():
    assert compose.match_quote([QUOTE], "BBB", "2027-02-17", "2027-02-23",
                               today=TODAY) is None


def test_quote_ages_out():
    """45일 지나면 낡음 표시, 180일 지나면 버린다."""
    q = compose.match_quote([QUOTE], "AAA", "2027-02-17", "2027-02-23",
                            today="2026-10-15")
    assert q["stale"] is True
    assert compose.match_quote([QUOTE], "AAA", "2027-02-17", "2027-02-23",
                               today="2027-04-01") is None


def test_quote_prefers_freshest():
    older = {**QUOTE, "per_night": 999999, "quoted_at": "2026-07-01"}
    q = compose.match_quote([older, QUOTE], "AAA", "2027-02-17", "2027-02-23",
                            today=TODAY)
    assert q["per_night"] == 150000


def test_quote_requires_quoted_at_and_krw():
    """나이를 모르는 값과 통화가 섞인 값은 실측이라 부를 수 없다."""
    no_date = {k: v for k, v in QUOTE.items() if k != "quoted_at"}
    usd = {**QUOTE, "currency": "USD"}
    for bad in (no_date, usd):
        assert compose.match_quote([bad], "AAA", "2027-02-17", "2027-02-23",
                                   today=TODAY) is None


def test_build_uses_quote_as_measured_with_narrow_band():
    flights = {"AAA": _flight("AAA", 1000000)}
    r = compose.build(["AAA"], PROFILES, flights, {}, 2, 1, 6,
                      quotes=[QUOTE], today=TODAY)
    lodging = [i for i in r["rows"][0]["budget"]["items"] if i["label"] == "숙박"][0]
    assert lodging["source"] == compose.MEASURED
    assert lodging["amount"] == 900000                    # 150,000 × 6박
    assert lodging["high"] - lodging["low"] == 180000     # ±10% — 어림값(±40%)보다 좁다
    assert "2026-08-10 확인" in lodging["note"]


def test_read_lodging_quotes_filters_party(tmp_path):
    p = tmp_path / "q.json"
    p.write_text(json.dumps({"quotes": [QUOTE, {**QUOTE, "children": 0}]},
                            ensure_ascii=False), encoding="utf-8")
    assert len(compose.read_lodging_quotes(str(p), adults=2, children=1)) == 1
    assert compose.read_lodging_quotes(str(tmp_path / "없음.json")) == []


def test_markdown_warns_when_tiers_overlap():
    from brief import main as bmain
    flights = {"AAA": _flight("AAA", 1000000), "BBB": _flight("BBB", 900000)}
    result = compose.build(["AAA", "BBB"], PROFILES, flights, {}, 2, 1, 6)
    md = bmain.to_markdown(result,
                           {"nights": 6, "adults": 2, "children": 1, "built_at": "t"},
                           compose.recommend(result["rows"], "balanced"))
    assert "순위를 확정할 수 없다" in md
    assert "~" in md   # 범위 열


# ── 박수 정합 ──
#
# 스캔의 대표값(best_price)은 5·6·7박을 통틀어 가장 싼 값이라 요청 박수와 다를 수
# 있다. 그대로 쓰면 7박 항공권에 6박 숙박을 더한 '실재하지 않는 여행'의 총예산이
# 나온다. 표는 멀쩡해 보이는데 합계가 조용히 틀린다.

def _flight_multi(code, party=(2, 1)):
    """5·6·7박이 모두 있는 스캔 결과. 대표값은 가장 싼 7박."""
    curve = [
        {"departure_date": "2027-01-05", "return_date": "2027-01-10",
         "nights": 5, "price": 1500000},
        {"departure_date": "2027-01-06", "return_date": "2027-01-12",
         "nights": 6, "price": 1400000},
        {"departure_date": "2027-01-07", "return_date": "2027-01-14",
         "nights": 7, "price": 1000000},
    ]
    return {"code": code, "best_price": 1000000, "departure_date": "2027-01-07",
            "return_date": "2027-01-14", "nights": 7, "party": party,
            "scanned_at": "2026-08-18 11:00:00", "date_curve": curve}


def test_flight_uses_requested_nights_not_overall_best():
    res = compose.build(["AAA"], PROFILES, {"AAA": _flight_multi("AAA")}, {},
                        2, 1, 6)
    row = res["rows"][0]
    fare = next(i for i in row["budget"]["items"] if i["label"] == "항공권")
    assert fare["amount"] == 1400000          # 7박의 1,000,000원이 아니다
    assert row["flight"]["nights"] == 6
    assert row["flight"]["departure_date"] == "2027-01-06"
    assert row["flight"]["return_date"] == "2027-01-12"


def test_missing_requested_nights_skips_candidate():
    """요청 박수 결과가 없으면 다른 박수로 때우지 않고 후보에서 뺀다."""
    f = _flight_multi("AAA")
    f["date_curve"] = [p for p in f["date_curve"] if p["nights"] == 5]
    f.update(best_price=1500000, departure_date="2027-01-05",
             return_date="2027-01-10", nights=5)
    res = compose.build(["AAA"], PROFILES, {"AAA": f}, {}, 2, 1, 6)
    assert res["rows"] == []
    assert res["skipped"] == [("AAA", "6박 항공권 결과 없음")]


def test_representative_already_matches_requested_nights():
    """대표값이 이미 요청 박수면 date_curve 없이도 그대로 쓴다."""
    f = _flight_multi("AAA")
    del f["date_curve"]
    f.update(best_price=1400000, departure_date="2027-01-06",
             return_date="2027-01-12", nights=6)
    res = compose.build(["AAA"], PROFILES, {"AAA": f}, {}, 2, 1, 6)
    fare = next(i for i in res["rows"][0]["budget"]["items"]
                if i["label"] == "항공권")
    assert fare["amount"] == 1400000
