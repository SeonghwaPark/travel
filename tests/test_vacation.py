"""휴가·방학·안전 축 테스트.

가장 중요한 건 '공휴일을 빼고 세는가'다. 설 연휴처럼 평일에 공휴일이 걸리면
휴가가 확 주는데, 그걸 반영 안 하면 날짜 비교가 통째로 어긋난다.
"""

import json
import os
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from explore import main as explore_main  # noqa: E402
from explore import vacation  # noqa: E402

CAL = {
    "holidays": {"2027": [
        {"date": "2027-02-08", "name": "설날 연휴"},
        {"date": "2027-02-09", "name": "설날 대체공휴일"},
    ]},
    "schools": {"테스트초": {
        "breaks": [{"from": "2026-12-31", "to": "2027-03-01",
                    "label": "겨울+봄방학", "estimated": True}],
    }},
    "vacation": {"value_krw": 415000, "paid_out": True, "basis": "테스트"},
}


# ── 휴가 일수 ──

def test_weekends_are_not_vacation():
    """1/16(토)~1/23(토): 평일은 18~22 다섯 개뿐."""
    assert vacation.workdays("2027-01-16", "2027-01-23", CAL) == 5


def test_public_holidays_are_not_vacation():
    """2/6(토)~2/14(일): 2/8·2/9가 공휴일이라 휴가는 3일뿐이다.

    이걸 빼먹으면 5일로 세어 설 연휴 안의 강점이 통째로 사라진다.
    """
    assert vacation.workdays("2027-02-06", "2027-02-14", CAL) == 3


def test_same_span_without_holidays_costs_more():
    """같은 8박이라도 공휴일이 없으면 휴가가 더 든다."""
    assert vacation.workdays("2027-02-20", "2027-02-28", CAL) == 5


def test_single_day_trip():
    assert vacation.workdays("2027-01-18", "2027-01-18", CAL) == 1
    assert vacation.workdays("2027-01-16", "2027-01-16", CAL) == 0


def test_reversed_dates_raise():
    with pytest.raises(ValueError):
        vacation.workdays("2027-01-23", "2027-01-16", CAL)


# ── 휴가 비용 ──

def test_cost_multiplies_days_by_value():
    c = vacation.cost("2027-01-16", "2027-01-23", CAL)
    assert c["days"] == 5 and c["total"] == 5 * 415000
    assert c["paid_out"] is True


def test_unpaid_leave_can_be_valued_at_zero():
    """소멸되는 연차라면 0으로 두면 계산에서 저절로 빠진다."""
    c = vacation.cost("2027-01-16", "2027-01-23", CAL, value=0)
    assert c["days"] == 5 and c["total"] == 0


# ── 방학 ──

def test_trip_inside_break():
    b = vacation.in_break("2027-01-16", "2027-01-23", data=CAL)
    assert b["ok"] is True and b["estimated"] is True


def test_trip_crossing_the_end_of_break_is_rejected():
    """하루라도 학기 중이면 못 가는 일정이다 — 걸치기만 해도 안 된다."""
    b = vacation.in_break("2027-02-25", "2027-03-05", data=CAL)
    assert b["ok"] is False


def test_no_school_registered():
    assert vacation.in_break("2027-01-16", "2027-01-23", data={})["ok"] is None


# ── 여행경보 ──

DESTS = {
    "DXB": {"name": "두바이", "travel_advisory": {"level": 3, "label": "출국권고"}},
    "CTS": {"name": "삿포로", "travel_advisory": {"level": 0, "label": "경보 없음"}},
    "NRT": {"name": "도쿄", "travel_advisory": {"level": None}},
    "XXX": {"name": "미상"},
}


def test_no_filter_passes_everything():
    kept, dropped, unchecked = explore_main.filter_by_advisory(DESTS)
    assert kept == DESTS and dropped == [] and unchecked == []


def test_advisory_above_limit_is_dropped():
    """두바이는 총예산까지 계산하고 나서야 3단계인 걸 알았다. 먼저 걸러야 한다."""
    kept, dropped, _ = explore_main.filter_by_advisory(DESTS, max_level=1)
    assert "DXB" not in kept
    assert dropped[0][0] == "DXB" and "3단계" in dropped[0][1]


def test_unchecked_passes_but_is_reported():
    """확인 안 한 것을 안전으로 단정하지 않는다 — 빼지 않되 따로 센다."""
    kept, _, unchecked = explore_main.filter_by_advisory(DESTS, max_level=1)
    assert "NRT" in kept and "XXX" in kept
    assert sorted(unchecked) == ["NRT", "XXX"]


def test_checked_zero_is_not_unchecked():
    """level 0(확인했고 경보 없음)과 null(확인 안 함)은 다른 상태다."""
    _, _, unchecked = explore_main.filter_by_advisory(DESTS, max_level=1)
    assert "CTS" not in unchecked


def test_real_calendar_file_loads():
    data = vacation.load()
    assert data.get("vacation", {}).get("value_krw")
    assert vacation.workdays("2027-02-06", "2027-02-14", data) == 3


def test_real_destinations_carry_advisory():
    with open(os.path.join(_ROOT, "destinations.json"), encoding="utf-8") as f:
        intl = json.load(f)["international"]
    assert all("travel_advisory" in v for v in intl.values())
    assert intl["DXB"]["travel_advisory"]["level"] == 3
