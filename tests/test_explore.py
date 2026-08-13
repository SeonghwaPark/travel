"""탐색 스캐너 집계·순위·CLI 배선 테스트 (네트워크 불필요)."""

import json
import os
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from explore import rank as rank_mod  # noqa: E402
from explore import main as explore_main  # noqa: E402


def _offers(*triples):
    return [{"departure_date": d, "return_date": r, "price": p} for d, r, p in triples]


# ── summarize ──

def test_summarize_picks_cheapest_across_nights():
    s = rank_mod.summarize(
        "FUK", {"name": "후쿠오카", "country": "일본"},
        {2: _offers(("2027-02-05", "2027-02-07", 500000),
                    ("2027-02-12", "2027-02-14", 460000)),
         3: _offers(("2027-02-05", "2027-02-08", 420000))},
        pax=2)
    assert s["best_price"] == 420000
    assert s["nights"] == 3 and s["departure_date"] == "2027-02-05"
    assert s["per_person"] == 210000
    assert s["observed"] == 3
    assert s["name"] == "후쿠오카" and s["country"] == "일본"


def test_summarize_dip_against_median():
    """기간 중앙값 대비 얼마나 싼 날짜인지."""
    s = rank_mod.summarize(
        "KIX", {"name": "오사카"},
        {3: _offers(("2027-02-01", "2027-02-04", 300000),
                    ("2027-02-02", "2027-02-05", 200000),
                    ("2027-02-03", "2027-02-06", 100000))},
        pax=1)
    assert s["median_price"] == 200000
    assert s["dip_pct"] == 50.0   # 200000 -> 100000


def test_summarize_returns_none_without_prices():
    assert rank_mod.summarize("XXX", {}, {}, pax=1) is None
    assert rank_mod.summarize("XXX", {}, {3: []}, pax=1) is None
    # 가격이 0/None인 항목만 있으면 결과 없음으로 본다
    assert rank_mod.summarize(
        "XXX", {}, {3: [{"departure_date": "2027-02-01",
                         "return_date": "2027-02-04", "price": None}]}, pax=1) is None


def test_summarize_per_person_excludes_lap_infant():
    """무릎유아는 좌석이 없으니 1인당 계산에서 빠진다 (호출부가 pax로 넘긴다)."""
    s = rank_mod.summarize("FUK", {}, {2: _offers(("2027-02-05", "2027-02-07", 900000))},
                           pax=3)
    assert s["per_person"] == 300000


# ── rank ──

def test_rank_orders_by_price_then_dip():
    a = {"code": "A", "best_price": 500000, "dip_pct": 5.0}
    b = {"code": "B", "best_price": 300000, "dip_pct": 1.0}
    c = {"code": "C", "best_price": 300000, "dip_pct": 9.0}
    out = rank_mod.rank([a, b, c, None])
    assert [r["code"] for r in out] == ["C", "B", "A"]


def test_rank_drops_none():
    assert rank_mod.rank([None, None]) == []


# ── markdown ──

def test_markdown_renders_table():
    result = {
        "meta": {"origin": "ICN", "start": "2027-02-01", "end": "2027-02-28",
                 "nights": [4, 5], "adults": 2, "children": 1, "infants": 0,
                 "scanned": 25, "scanned_at": "2026-08-13 06:00:00"},
        "ranking": [{"code": "FUK", "name": "후쿠오카", "country": "일본",
                     "best_price": 460200, "per_person": 153400,
                     "departure_date": "2027-02-12", "return_date": "2027-02-16",
                     "nights": 4, "median_price": 520000, "dip_pct": 11.5,
                     "observed": 40}],
        "failed": ["SYD"],
    }
    md = rank_mod.to_markdown(result)
    assert "후쿠오카 (FUK)" in md
    assert "460,200원" in md
    assert "−11.5%" in md
    assert "성인 2 · 소아 1" in md
    assert "조회 실패: SYD" in md


def test_markdown_handles_empty_ranking():
    md = rank_mod.to_markdown({
        "meta": {"origin": "ICN", "start": "2027-02-01", "end": "2027-02-28",
                 "nights": [4], "adults": 1, "children": 0, "infants": 0,
                 "scanned": 25, "scanned_at": "2026-08-13 06:00:00"},
        "ranking": [], "failed": []})
    assert "받아오지 못했습니다" in md


# ── CLI 배선 (조회는 스텁) ──

@pytest.fixture
def stub_graph(monkeypatch, tmp_path):
    """가격 그래프를 목적지별 고정 가격으로 대체하고 결과를 tmp에 쓰게 한다."""
    prices = {"NRT": 700000, "KIX": 500000, "FUK": 300000}
    calls = []

    def fake(origin, dest, start, end, nights, **kw):
        calls.append((dest, nights))
        if dest not in prices:
            return []
        return [{"departure_date": start, "return_date": end,
                 "price": prices[dest] + nights * 10000}]

    monkeypatch.setattr(explore_main.gflights, "fetch_price_graph", fake)
    monkeypatch.setattr(explore_main, "RESULTS_DIR", str(tmp_path))
    return calls, tmp_path


def test_run_ranks_and_writes_files(stub_graph):
    calls, tmp_path = stub_graph
    result = explore_main.run([
        "--start", "2027-02-01", "--end", "2027-02-28",
        "--nights", "4,5", "--adults", "2",
        "--only", "NRT,KIX,FUK", "--tag", "test",
    ])

    assert [r["code"] for r in result["ranking"]] == ["FUK", "KIX", "NRT"]
    assert result["ranking"][0]["best_price"] == 340000   # 300000 + 4*10000
    assert result["ranking"][0]["per_person"] == 170000   # 성인 2명
    assert len(calls) == 6                                # 목적지 3 × 박수 2

    assert (tmp_path / "test.json").exists()
    written = json.loads((tmp_path / "test.json").read_text(encoding="utf-8"))
    assert written["meta"]["origin"] == "ICN"
    assert written["meta"]["nights"] == [4, 5]
    md = (tmp_path / "test.md").read_text(encoding="utf-8")
    assert "후쿠오카" in md


def test_run_records_destinations_without_prices(stub_graph):
    _calls, _tmp = stub_graph
    result = explore_main.run([
        "--start", "2027-02-01", "--end", "2027-02-28",
        "--only", "FUK,BKK", "--tag", "t2",
    ])
    assert [r["code"] for r in result["ranking"]] == ["FUK"]
    assert result["failed"] == ["BKK"]      # 조용히 사라지지 않고 기록된다


def test_run_excludes_origin_from_destinations(stub_graph):
    calls, _tmp = stub_graph
    explore_main.run([
        "--origin", "CJU", "--scope", "domestic",
        "--start", "2027-02-01", "--end", "2027-02-10", "--tag", "t3",
    ])
    assert "CJU" not in {dest for dest, _n in calls}


def test_run_clamps_range_to_price_graph_limit(stub_graph):
    calls, _tmp = stub_graph
    explore_main.run([
        "--start", "2027-02-01", "--end", "2028-02-01",
        "--only", "FUK", "--tag", "t4",
    ])
    _dest, _n = calls[0]
    result = json.loads((_tmp / "t4.json").read_text(encoding="utf-8"))
    span = (
        __import__("datetime").datetime.strptime(result["meta"]["end"], "%Y-%m-%d")
        - __import__("datetime").datetime.strptime(result["meta"]["start"], "%Y-%m-%d")
    ).days + 1
    assert span == explore_main.gflights.MAX_RANGE_DAYS


def test_run_rejects_reversed_range(stub_graph):
    with pytest.raises(SystemExit):
        explore_main.run(["--start", "2027-02-28", "--end", "2027-02-01", "--only", "FUK"])


def test_run_rejects_empty_destination_set(stub_graph):
    with pytest.raises(SystemExit):
        explore_main.run(["--start", "2027-02-01", "--end", "2027-02-10",
                          "--only", "NOPE"])
