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
