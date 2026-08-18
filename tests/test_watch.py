import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from watch import config, rules, telegram_send  # noqa: E402
from watch.main import _combos, booking_url  # noqa: E402


# ── rules ──

def _hist(*prices):
    return [{"best_price": p} for p in prices]


def test_no_alert_without_history_or_target():
    assert rules.evaluate(1_000_000, [], {"drop_pct": 10, "all_time_low": True}) == []


def test_target_price_hit():
    r = rules.evaluate(1_500_000, [], {"target_price": 1_600_000})
    assert [x["type"] for x in r] == ["target"]


def test_target_price_not_hit():
    assert rules.evaluate(1_700_000, [], {"target_price": 1_600_000}) == []


def test_drop_pct_triggers_on_decline():
    r = rules.evaluate(900_000, _hist(1_000_000), {"drop_pct": 8})
    assert [x["type"] for x in r] == ["drop"]


def test_drop_pct_ignores_small_decline():
    assert rules.evaluate(980_000, _hist(1_000_000), {"drop_pct": 8}) == []


def test_drop_pct_ignores_price_increase():
    assert rules.evaluate(1_200_000, _hist(1_000_000), {"drop_pct": 8}) == []


def test_all_time_low_needs_three_observations():
    cfg = {"all_time_low": True}
    assert rules.evaluate(500_000, _hist(900_000, 800_000), cfg) == []
    r = rules.evaluate(500_000, _hist(900_000, 800_000, 850_000), cfg)
    assert "atl" in [x["type"] for x in r]


def test_all_time_low_not_triggered_when_higher():
    r = rules.evaluate(900_000, _hist(800_000, 850_000, 820_000), {"all_time_low": True})
    assert "atl" not in [x["type"] for x in r]


def test_discount_vs_median():
    # 중앙값 1,000,000 대비 20% 저렴
    r = rules.evaluate(800_000, _hist(1_000_000, 1_000_000, 1_000_000),
                       {"discount_pct": 15})
    assert "discount" in [x["type"] for x in r]


def test_discount_needs_enough_observations():
    r = rules.evaluate(800_000, _hist(1_000_000, 1_000_000), {"discount_pct": 15})
    assert "discount" not in [x["type"] for x in r]


def test_zero_price_never_alerts():
    assert rules.evaluate(None, _hist(1_000_000), {"target_price": 9_000_000}) == []


def test_multiple_reasons_stack():
    r = rules.evaluate(700_000, _hist(1_000_000, 1_000_000, 1_000_000),
                       {"target_price": 800_000, "drop_pct": 10,
                        "all_time_low": True, "discount_pct": 15})
    assert {x["type"] for x in r} == {"target", "drop", "atl", "discount"}


# ── config ──

def test_defaults_merge_into_watch(tmp_path):
    p = tmp_path / "w.json"
    p.write_text(json.dumps({
        "defaults": {"origin": "ICN", "adults": 1, "children": 0, "infants": 0,
                     "alert": {"drop_pct": 8, "all_time_low": True}},
        "watches": [{"id": "a", "dest": "CTS", "date_from": "2027-02-01",
                     "date_to": "2027-02-05", "nights": [3],
                     "adults": 2, "alert": {"target_price": 100}}],
    }, ensure_ascii=False), encoding="utf-8")

    w = config.load(str(p))[0]
    assert w["adults"] == 2            # watch가 defaults를 덮어씀
    assert w["origin"] == "ICN"        # defaults 상속
    assert w["alert"]["target_price"] == 100
    assert w["alert"]["drop_pct"] == 8  # alert도 병합됨
    assert w["label"] == "a"            # label 없으면 id


def test_missing_required_field_raises(tmp_path):
    p = tmp_path / "w.json"
    p.write_text(json.dumps({"watches": [{"id": "a", "dest": "CTS"}]}), encoding="utf-8")
    with pytest.raises(ValueError, match="필수 항목 누락"):
        config.load(str(p))


def test_duplicate_id_raises(tmp_path):
    p = tmp_path / "w.json"
    base = {"dest": "CTS", "date_from": "2027-02-01", "date_to": "2027-02-05",
            "nights": [3]}
    p.write_text(json.dumps({"watches": [{"id": "a", **base}, {"id": "a", **base}]}),
                 encoding="utf-8")
    with pytest.raises(ValueError, match="중복"):
        config.load(str(p))


def test_real_watchlist_loads():
    ws = config.load()
    assert ws and all(w["origin"] and w["dest"] for w in ws)


# ── combos ──

def test_combos_respects_max_queries():
    w = {"date_from": "2027-02-01", "date_to": "2027-02-28", "nights": [2, 3, 4, 5],
         "step": 1, "max_queries": 10}
    c = _combos(w)
    assert len(c) == 10
    assert len(set(c)) == 10  # 중복 없이 균등하게 솎였는지


def test_combos_under_cap_returns_all():
    w = {"date_from": "2027-02-01", "date_to": "2027-02-03", "nights": [3],
         "step": 1, "max_queries": 40}
    assert len(_combos(w)) == 3


def test_combos_step_skips_dates():
    w = {"date_from": "2027-02-01", "date_to": "2027-02-11", "nights": [3],
         "step": 5, "max_queries": 40}
    assert [d for d, _ in _combos(w)] == ["2027-02-01", "2027-02-06", "2027-02-11"]


# ── 메시지 ──

def test_alert_message_contains_key_facts():
    watch = {"label": "삿포로", "origin": "ICN", "dest": "CTS"}
    best = {"dep_date": "2027-02-21", "ret_date": "2027-02-26", "nights": 5,
            "price": 1_741_200, "airline": "Jeju Air", "stops": 0, "weekday": "Sun"}
    msg = telegram_send.format_alert(watch, best, [{"type": "target", "text": "🎯 목표가"}],
                                     "https://example.com")
    assert "1,741,200원" in msg
    assert "2027-02-21(일)" in msg
    assert "직항" in msg
    assert "https://example.com" in msg


def test_booking_url_encodes_passengers():
    url = booking_url("ICN", "CTS", "2027-02-21", "2027-02-26", 2, 1, 0)
    assert "curr=KRW" in url
    assert "2%20adults" in url and "1%20children" in url


# ── 확정안 대비 하락 ──
#
# 일정을 정한 뒤에는 "역대 최저인가"보다 "내가 사려던 값보다 싼가"가 실질적인
# 질문이다. 목표가를 그래프값으로 잡았다가 실측이 9.8% 비싸서, 웬만한 하락은
# 조용히 지나가는 상태였다.

BASE = {"price": 2130600, "measured_at": "2026-08-18"}


def test_baseline_drop_fires():
    r = rules.evaluate(2020000, [], {"baseline_pct": 2}, baseline=BASE)
    assert [x["type"] for x in r] == ["baseline"]
    assert "5.2% 저렴" in r[0]["text"] and "110,600원 절약" in r[0]["text"]


def test_small_drop_below_threshold_is_quiet():
    """1% 빠진 걸로 알리면 알림이 노이즈가 된다."""
    assert rules.evaluate(2110000, [], {"baseline_pct": 2}, baseline=BASE) == []


def test_price_above_baseline_is_quiet():
    assert rules.evaluate(2200000, [], {"baseline_pct": 2}, baseline=BASE) == []


def test_no_baseline_skips_the_rule():
    """baseline이 없는 감시는 종전대로 동작한다."""
    assert rules.evaluate(100, [], {}) == []


def test_baseline_stacks_with_other_reasons():
    """확정안보다 싸면서 목표가도 달성하면 둘 다 알린다."""
    r = rules.evaluate(2000000, [], {"target_price": 2020000, "baseline_pct": 2},
                       baseline=BASE)
    assert sorted(x["type"] for x in r) == ["baseline", "target"]
