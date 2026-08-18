"""소스축 테스트 — 가격 그래프와 실제 조회가 갈리는지 짝지어 세는 부분.

가장 중요한 건 '시점이 벌어진 짝을 세지 않는가'다. 한 달 전 그래프와 오늘 실측의
차이는 소스가 갈린 게 아니라 그냥 가격이 움직인 것인데, 그걸 불일치로 세면
"그래프를 믿어도 되나"의 답이 통째로 거짓이 된다.
"""

import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from explore import agree  # noqa: E402


def _obs(price, at, dep="2027-02-17", ret="2027-02-23", dest="CTS"):
    return {"watch_id": "w", "dest": dest, "adults": 2, "children": 1,
            "departure_date": dep, "return_date": ret, "nights": 6,
            "price": price, "at": at}


def _graph(price, at, dep="2027-02-17", ret="2027-02-23", dest="CTS"):
    return {(dest, 2, 1, dep, ret, 6): {"price": price, "at": at,
                                        "source_file": "s.json"}}


def test_pairs_same_itinerary_and_measures_difference():
    pairs, skipped = agree.compare([_obs(1566600, "2026-08-18 00:54:20")],
                                   _graph(1457500, "2026-08-18 11:05:05"))
    assert skipped == []
    p = pairs[0]
    assert p["graph_price"] == 1457500 and p["real_price"] == 1566600
    assert p["diff"] == 109100
    assert p["diff_pct"] == 7.49


def test_skips_pairs_measured_too_far_apart():
    """시점이 벌어지면 소스 차이가 아니라 가격 변동이다."""
    pairs, skipped = agree.compare([_obs(1566600, "2026-09-30 00:00:00")],
                                   _graph(1457500, "2026-08-18 11:05:05"))
    assert pairs == []
    assert skipped[0]["reason"] == "관측 시점 차이"
    assert skipped[0]["gap_days"] == 42   # 08-18 11:05 → 09-30 00:00, 하루가 덜 찬다


def test_max_gap_is_adjustable():
    obs, g = [_obs(1500000, "2026-08-25 00:00:00")], _graph(1450000, "2026-08-18 00:00:00")
    assert agree.compare(obs, g, max_gap_days=3)[0] == []
    assert len(agree.compare(obs, g, max_gap_days=10)[0]) == 1


def test_unmatched_itineraries_are_ignored_not_guessed():
    """일정이 다르면 짝짓지 않는다 — 가까운 날짜로 대신하면 없는 비교를 지어낸다."""
    pairs, skipped = agree.compare([_obs(1566600, "2026-08-18 00:00:00", dep="2027-02-18")],
                                   _graph(1457500, "2026-08-18 00:00:00"))
    assert pairs == [] and skipped == []


def test_summary_counts_itineraries_separately_from_pairs():
    """같은 일정을 네 번 관측해도 일정은 하나다. 그걸 안 나누면 통계가 기운다."""
    obs = [_obs(1566600, f"2026-08-1{d} 00:00:00") for d in (5, 6, 7, 8)]
    g = _graph(1457500, "2026-08-17 00:00:00")
    pairs, _ = agree.compare(obs, g, max_gap_days=3)
    s = agree.summarize(pairs)
    assert s["pairs"] == 4 and s["itineraries"] == 1
    assert s["graph_cheaper"] == 4


def test_summary_withholds_mean_when_too_few_pairs():
    """짝이 3건 미만이면 평균을 내지 않는다 — 없는 정밀도를 지어내지 않는다."""
    pairs, _ = agree.compare([_obs(1566600, "2026-08-18 00:00:00")],
                             _graph(1457500, "2026-08-18 00:00:00"))
    s = agree.summarize(pairs)
    assert "mean_abs_pct" not in s
    assert s["max_abs_pct"] == 7.49


def test_append_history_does_not_duplicate(tmp_path):
    pairs, _ = agree.compare([_obs(1566600, "2026-08-18 00:00:00")],
                             _graph(1457500, "2026-08-18 00:00:00"))
    path = str(tmp_path / "agreement.jsonl")
    assert len(agree.append_history(pairs, path)) == 1
    assert agree.append_history(pairs, path) == []
    assert len(open(path, encoding="utf-8").read().strip().splitlines()) == 1


def test_watch_history_without_a_watch_entry_is_skipped(tmp_path):
    """감시 목록에서 지워진 이력은 조건을 알 수 없어 비교에 못 쓴다."""
    wl = tmp_path / "watchlist.json"
    wl.write_text(json.dumps({"defaults": {"adults": 1},
                              "watches": [{"id": "keep", "dest": "CTS", "adults": 2,
                                           "children": 1}]}),
                  encoding="utf-8")
    hist = tmp_path / "history"
    hist.mkdir()
    rec = {"at": "2026-08-18 00:00:00", "best_price": 100, "dep_date": "2027-02-17",
           "ret_date": "2027-02-23", "nights": 6}
    (hist / "keep.jsonl").write_text(json.dumps(rec) + "\n", encoding="utf-8")
    (hist / "gone.jsonl").write_text(json.dumps(rec) + "\n", encoding="utf-8")
    obs = agree.load_watch_observations(str(wl), str(hist))
    assert [o["watch_id"] for o in obs] == ["keep"]
    assert obs[0]["dest"] == "CTS" and obs[0]["adults"] == 2
