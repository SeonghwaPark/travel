"""탐색 이력·가격 맥락 테스트. 네트워크 없이 돈다."""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from explore import trend  # noqa: E402


def _result(scanned_at, prices):
    """{코드: 가격} → 스캔 결과 모양."""
    return {
        "meta": {"scanned_at": scanned_at},
        "ranking": [
            {
                "code": code,
                "best_price": price,
                "per_person": price // 3,
                "median_price": price + 50_000,
                "departure_date": "2027-02-17",
                "return_date": "2027-02-23",
                "nights": 6,
            }
            for code, price in prices.items()
        ],
    }


@pytest.fixture
def tmp_history(tmp_path, monkeypatch):
    monkeypatch.setattr(trend, "HISTORY_DIR", str(tmp_path))
    return tmp_path


# --- 저장·적재 ---------------------------------------------------------------

def test_append_then_load_roundtrip(tmp_history):
    trend.append("t", _result("2026-08-17 09:00:00", {"CTS": 1_566_600}))
    trend.append("t", _result("2026-08-18 09:00:00", {"CTS": 1_500_000}))

    records = trend.load("t")
    assert len(records) == 2
    assert records[0]["at"] == "2026-08-17 09:00:00"
    assert records[1]["dests"]["CTS"]["best_price"] == 1_500_000


def test_load_missing_file_is_empty(tmp_history):
    assert trend.load("없는태그") == []


def test_append_skips_empty_ranking(tmp_history):
    assert trend.append("t", {"meta": {"scanned_at": "x"}, "ranking": []}) is None
    assert trend.load("t") == []


def test_load_tolerates_broken_line(tmp_history):
    """실행이 끊겨 줄이 깨져도 나머지는 읽혀야 한다."""
    path = os.path.join(str(tmp_history), "t.jsonl")
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps({"at": "1", "dests": {"CTS": {"best_price": 100}}}) + "\n")
        f.write('{"at": "2", "dests": {"CTS"\n')  # 중간에 끊긴 줄
        f.write(json.dumps({"at": "3", "dests": {"CTS": {"best_price": 200}}}) + "\n")

    assert [r["at"] for r in trend.load("t")] == ["1", "3"]


def test_series_skips_destinations_not_in_that_scan(tmp_history):
    """목적지 목록이 스캔마다 다를 수 있다. 없는 회차는 건너뛴다."""
    trend.append("t", _result("1", {"CTS": 100, "FUK": 50}))
    trend.append("t", _result("2", {"FUK": 60}))
    trend.append("t", _result("3", {"CTS": 120, "FUK": 55}))

    assert [p for _, p in trend.series(trend.load("t"), "CTS")] == [100, 120]
    assert [p for _, p in trend.series(trend.load("t"), "FUK")] == [50, 60, 55]


# --- 가격 맥락 ---------------------------------------------------------------

def test_context_none_until_enough_observations(tmp_history):
    """관측 1회로는 '과거 대비'를 말할 수 없다."""
    trend.append("t", _result("1", {"CTS": 1_000_000}))
    assert trend.context(trend.load("t"), "CTS", 900_000) is None


def test_context_record_low(tmp_history):
    trend.append("t", _result("1", {"CTS": 1_000_000}))
    trend.append("t", _result("2", {"CTS": 950_000}))

    ctx = trend.context(trend.load("t"), "CTS", 900_000)
    assert ctx["is_record_low"] is True
    assert ctx["past_low"] == 950_000
    assert ctx["observations"] == 2
    assert "역대 최저" in trend.describe(ctx)


def test_context_above_past_low(tmp_history):
    trend.append("t", _result("1", {"CTS": 1_000_000}))
    trend.append("t", _result("2", {"CTS": 900_000}))

    ctx = trend.context(trend.load("t"), "CTS", 990_000)
    assert ctx["is_record_low"] is False
    assert ctx["vs_low_pct"] == 10.0        # 900,000 → 990,000
    assert ctx["vs_prev_pct"] == 10.0       # 직전도 900,000
    assert "+10.0%" in trend.describe(ctx)


def test_context_excludes_current_scan(tmp_history):
    """이번 값을 이력에 넣기 전에 물어야 자기 자신과 비교하지 않는다."""
    trend.append("t", _result("1", {"CTS": 1_000_000}))
    trend.append("t", _result("2", {"CTS": 1_000_000}))

    ctx = trend.context(trend.load("t"), "CTS", 800_000)
    assert ctx["past_low"] == 1_000_000
    assert ctx["is_record_low"] is True


def test_trend_needs_three_observations(tmp_history):
    trend.append("t", _result("1", {"CTS": 1_000_000}))
    trend.append("t", _result("2", {"CTS": 990_000}))

    ctx = trend.context(trend.load("t"), "CTS", 980_000)
    assert ctx["trend"] is None


@pytest.mark.parametrize("past, current, expected", [
    ([1_000_000, 950_000, 900_000], 850_000, "하락"),
    ([850_000, 900_000, 950_000], 1_000_000, "상승"),
    ([1_000_000, 1_001_000, 999_000], 1_000_500, "횡보"),
])
def test_trend_direction(tmp_history, past, current, expected):
    for i, p in enumerate(past):
        trend.append("t", _result(str(i), {"CTS": p}))

    ctx = trend.context(trend.load("t"), "CTS", current)
    assert ctx["trend"] == expected
    assert expected in trend.describe(ctx)


def test_trend_uses_only_recent_window(tmp_history):
    """오래전 폭등은 최근 하락 추세를 가리지 않아야 한다."""
    for p in [5_000_000, 4_000_000, 1_000_000, 990_000, 980_000, 970_000]:
        trend.append("t", _result("x", {"CTS": p}))

    ctx = trend.context(trend.load("t"), "CTS", 960_000)
    assert ctx["trend"] == "하락"
    # 최근 5개(1_000_000~960_000)만 봤다면 기울기가 완만하다.
    # 옛날 500만원까지 섞였다면 훨씬 가팔라진다.
    assert abs(ctx["trend_pct"]) < 5


def test_context_none_without_price(tmp_history):
    trend.append("t", _result("1", {"CTS": 1_000_000}))
    trend.append("t", _result("2", {"CTS": 900_000}))
    assert trend.context(trend.load("t"), "CTS", None) is None


def test_describe_empty_for_none():
    assert trend.describe(None) == ""


def test_contexts_for_covers_all_destinations(tmp_history):
    trend.append("t", _result("1", {"CTS": 1_000_000, "FUK": 500_000}))
    trend.append("t", _result("2", {"CTS": 900_000, "FUK": 480_000}))

    result = _result("3", {"CTS": 850_000, "FUK": 470_000})
    ctxs = trend.contexts_for("t", result)

    assert set(ctxs) == {"CTS", "FUK"}
    assert ctxs["CTS"]["is_record_low"] is True
    assert ctxs["FUK"]["is_record_low"] is True


def test_contexts_for_empty_on_first_scan(tmp_history):
    assert trend.contexts_for("t", _result("1", {"CTS": 100})) == {}
