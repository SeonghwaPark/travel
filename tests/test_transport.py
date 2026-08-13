"""교통 구간 합산·패스 손익 계산 테스트 (네트워크 불필요)."""

import os
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "backend"))

import transport  # noqa: E402

# 계산 로직 자체를 검증하려면 요금이 고정돼야 한다. 실제 JSON 값이 개정돼도
# 이 테스트는 깨지지 않아야 하므로 고정 데이터를 쓴다.
FIXTURE = {
    "regions": {
        "test": {
            "name": "테스트지역",
            "currency": "JPY",
            "fares_verified": True,
            "legs": {
                "A-B": {"from": "A", "to": "B", "minutes": 60, "fare": 5000, "service": "특급"},
                "B-C": {"from": "B", "to": "C", "minutes": 120, "fare": 8000, "service": "특급"},
                "C-A": {"from": "C", "to": "A", "minutes": 200, "fare": 9000, "service": "특급"},
            },
            "passes": [
                {"id": "p5", "name": "5일권", "days": 5, "price": 21000},
                {"id": "p7", "name": "7일권", "days": 7, "price": 27000},
            ],
        }
    }
}


def _plan(legs, trip_days=None):
    return transport.plan("test", legs, trip_days, data=FIXTURE)


# ── 합산 ──

def test_leg_total_sums_fares_and_minutes():
    r = _plan(["A-B", "B-C"])
    assert r["individual_total"] == 13000
    assert r["total_minutes"] == 180 and r["total_hours"] == 3.0
    assert [l["id"] for l in r["legs"]] == ["A-B", "B-C"]


def test_repeated_leg_counted_twice():
    """왕복이면 같은 구간을 두 번 탄다."""
    assert _plan(["A-B", "A-B"])["individual_total"] == 10000


def test_unknown_leg_is_reported_not_ignored():
    """표에 없는 구간을 0원으로 치면 패스가 손해인데 이득으로 보인다."""
    r = _plan(["A-B", "NOPE"])
    assert r["unknown_legs"] == ["NOPE"]
    assert r["individual_total"] == 5000
    assert "요금표에 없는 구간" in r["verdict"]


# ── 패스 손익 ──

def test_pass_worth_it_when_fares_exceed_price():
    r = _plan(["A-B", "B-C", "C-A"])       # 22,000 > 21,000
    best = r["passes"][0]
    assert best["id"] == "p5"
    assert best["worth_it"] is True
    assert best["savings"] == 1000
    assert "5일권" in r["verdict"] and "이득" in r["verdict"]


def test_individual_wins_when_fares_are_low():
    r = _plan(["A-B"])                      # 5,000 < 21,000
    assert all(not p["worth_it"] for p in r["passes"])
    assert "개별권이 낫습니다" in r["verdict"]


def test_passes_sorted_by_savings():
    r = _plan(["A-B", "B-C", "C-A"])
    savings = [p["savings"] for p in r["passes"]]
    assert savings == sorted(savings, reverse=True)


def test_trip_length_flag():
    """일정이 패스 유효일수를 넘으면 알려줘야 한다."""
    r = _plan(["A-B", "B-C", "C-A"], trip_days=6)
    by_id = {p["id"]: p for p in r["passes"]}
    assert by_id["p5"]["covers_trip_length"] is False
    assert by_id["p7"]["covers_trip_length"] is True


def test_trip_length_unknown_when_not_given():
    r = _plan(["A-B"])
    assert all(p["covers_trip_length"] is None for p in r["passes"])


# ── 신뢰도 표시 ──

def test_unverified_fares_are_flagged():
    data = {"regions": {"test": {**FIXTURE["regions"]["test"], "fares_verified": False}}}
    r = transport.plan("test", ["A-B"], data=data)
    assert "어림값" in r["verdict"]


def test_verified_fares_not_flagged():
    assert "어림값" not in _plan(["A-B"])["verdict"]


def test_unknown_region_raises():
    with pytest.raises(KeyError):
        transport.plan("nowhere", ["A-B"], data=FIXTURE)


# ── 실제 데이터 정합성 ──

def test_shipped_json_is_well_formed():
    """배포되는 transport.json이 계산기가 기대하는 모양인지."""
    data = transport.load()
    assert data["regions"], "지역이 하나도 없다"
    for rid, region in data["regions"].items():
        assert region["name"] and region.get("currency")
        assert region["legs"], f"{rid}에 구간이 없다"
        for lid, leg in region["legs"].items():
            assert {"from", "to", "minutes", "fare"} <= set(leg), f"{rid}/{lid}"
            assert leg["fare"] > 0 and leg["minutes"] > 0
        for p in region.get("passes", []):
            assert {"id", "name", "days", "price"} <= set(p)


def test_hokkaido_itinerary_runs():
    """이번 여행 일정(삿포로→하코다테→노보리베츠→삿포로)이 계산되는지."""
    r = transport.plan("hokkaido", ["CTS-SPK", "SPK-HKD", "NBR-HKD", "SPK-NBR", "CTS-SPK"],
                       trip_days=7)
    assert r["unknown_legs"] == []
    assert r["individual_total"] > 0
    assert r["passes"]


def test_short_pass_warning_is_in_verdict_not_only_a_field():
    """유효일수 부족을 별도 필드로만 두면 놓친다 — 판정문에 나와야 한다."""
    r = _plan(["A-B", "B-C", "C-A"], trip_days=6)   # 22,000 vs 5일권 21,000
    assert r["passes"][0]["id"] == "p5"
    assert "짧아" in r["verdict"] and "6일" in r["verdict"]
    # 일정을 덮는 7일권은 27,000이라 손해 → 대안이 없다고 알려야 한다
    assert "이득인 것이 없습니다" in r["verdict"]


def test_short_pass_suggests_covering_alternative_when_one_exists():
    data = {"regions": {"test": {**FIXTURE["regions"]["test"],
                                 "passes": [{"id": "p5", "name": "5일권", "days": 5, "price": 10000},
                                            {"id": "p7", "name": "7일권", "days": 7, "price": 15000}]}}}
    r = transport.plan("test", ["A-B", "B-C", "C-A"], trip_days=6, data=data)  # 22,000
    assert r["passes"][0]["id"] == "p5"          # 절약액은 5일권이 크지만
    assert "7일권입니다" in r["verdict"]          # 일정을 덮는 대안을 제시


def test_no_length_warning_when_pass_covers_trip():
    r = _plan(["A-B", "B-C", "C-A"], trip_days=4)
    assert "짧아" not in r["verdict"]
