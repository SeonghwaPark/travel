"""숙박 구역 스캐너 테스트 (네트워크·브라우저 불필요).

가격 조회는 언제든 깨질 수 있다. 깨져도 구역 가이드는 그대로 나와야 한다는 게
이 모듈의 설계 전제라, 그 점을 특히 확인한다.
"""

import json
import os
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "backend"))

import ghotels  # noqa: E402
from explore import stay  # noqa: E402


DEST = {
    "name": "테스트시",
    "tips": ["팁 하나", "팁 둘"],
    "areas": [
        {"id": "a", "name": "A구역", "query": "A 호텔", "good_for": "교통",
         "why": "역이 가깝다", "caution": "비싸다"},
        {"id": "b", "name": "B구역", "query": "B 호텔", "good_for": "가성비",
         "why": "값이 싸다", "caution": "식당이 적다"},
    ],
}


def _fetcher(prices_by_query):
    def fetch(query, check_in, check_out, adults, children):
        return [{"name": f"{query} 호텔{i}", "price_per_night": p, "rating": 4.0}
                for i, p in enumerate(prices_by_query.get(query, []))]
    return fetch


# ── 가격 파싱 ──

def test_parse_price_handles_both_notations():
    assert ghotels.parse_price("₩123,456") == 123456
    assert ghotels.parse_price("₩ 98,000") == 98000
    assert ghotels.parse_price("1박 87,500원") == 87500
    assert ghotels.parse_price("가격 정보 없음") is None
    assert ghotels.parse_price("") is None
    assert ghotels.parse_price(None) is None


def test_parse_price_ignores_short_numbers():
    """평점 4.5나 '3인' 같은 숫자를 가격으로 오인하면 안 된다."""
    assert ghotels.parse_price("평점 4.5 · 3인") is None


def test_parse_cards_drops_cards_without_price():
    cards = ["호텔 A\n★4.5\n₩120,000", "광고 배너\n자세히 보기", "호텔 B\n89,000원"]
    out = ghotels.parse_cards(cards)
    assert [h["name"] for h in out] == ["호텔 A", "호텔 B"]
    assert [h["price_per_night"] for h in out] == [120000, 89000]
    assert out[0]["rating"] == 4.5


def test_parse_cards_survives_empty_input():
    assert ghotels.parse_cards([]) == []
    assert ghotels.parse_cards(["", None]) == []


# ── 요약 ──

def test_summarize_median_and_min():
    hotels = [{"name": f"h{i}", "price_per_night": p, "rating": None}
              for i, p in enumerate([150000, 90000, 120000])]
    s = ghotels.summarize(hotels)
    assert s["min_per_night"] == 90000
    assert s["median_per_night"] == 120000
    assert s["count"] == 3
    assert [x["price_per_night"] for x in s["samples"]] == [90000, 120000, 150000]


def test_summarize_even_count_averages_middle():
    hotels = [{"name": "x", "price_per_night": p, "rating": None}
              for p in (100000, 200000)]
    assert ghotels.summarize(hotels)["median_per_night"] == 150000


def test_summarize_none_when_empty():
    assert ghotels.summarize([]) is None


# ── 조합 ──

def test_build_attaches_prices_per_area():
    r = stay.build("TST", DEST, "2027-02-17", "2027-02-23", 2, 1,
                   fetcher=_fetcher({"A 호텔": [200000, 180000],
                                     "B 호텔": [90000, 110000]}))
    assert r["meta"]["nights"] == 6
    by_name = {a["name"]: a for a in r["areas"]}
    assert by_name["A구역"]["prices"]["min_per_night"] == 180000
    assert by_name["B구역"]["prices"]["min_per_night"] == 90000
    assert r["failed"] == []


def test_build_records_areas_without_prices():
    r = stay.build("TST", DEST, "2027-02-17", "2027-02-23", 2, 1,
                   fetcher=_fetcher({"A 호텔": [200000]}))
    assert "prices" not in [a for a in r["areas"] if a["name"] == "B구역"][0]
    assert r["failed"] == ["B구역"]


def test_build_survives_fetcher_raising():
    """한 구역 조회가 터져도 나머지는 계속돼야 한다."""
    def boom(query, *a):
        if query == "A 호텔":
            raise RuntimeError("브라우저 죽음")
        return [{"name": "ok", "price_per_night": 90000, "rating": None}]

    r = stay.build("TST", DEST, "2027-02-17", "2027-02-23", 2, 1, fetcher=boom)
    assert r["failed"] == ["A구역"]
    assert [a for a in r["areas"] if a["name"] == "B구역"][0]["prices"]


def test_build_without_fetcher_still_returns_guide():
    """가격 조회를 아예 안 해도 가이드는 나온다 — 스크래핑이 깨져도 쓸모가 남게."""
    r = stay.build("TST", DEST, "2027-02-17", "2027-02-23", 2, 1, fetcher=None)
    assert len(r["areas"]) == 2
    assert all("prices" not in a for a in r["areas"])
    assert r["tips"] == ["팁 하나", "팁 둘"]


def test_build_rejects_bad_date_range():
    with pytest.raises(SystemExit):
        stay.build("TST", DEST, "2027-02-23", "2027-02-17", 2, 1)


# ── 마크다운 ──

def test_markdown_includes_prices_guide_and_tips():
    r = stay.build("TST", DEST, "2027-02-17", "2027-02-23", 2, 1,
                   fetcher=_fetcher({"A 호텔": [200000], "B 호텔": [90000]}))
    md = stay.to_markdown(r)
    assert "구역별 1박 가격" in md
    assert "90,000원" in md and "200,000원" in md
    assert "역이 가깝다" in md and "식당이 적다" in md   # why / caution
    assert "팁 하나" in md
    assert "6박" in md


def test_markdown_without_prices_still_useful():
    md = stay.to_markdown(stay.build("TST", DEST, "2027-02-17", "2027-02-23", 2, 1))
    assert "가격을 가져오지 못했다" in md
    assert "A구역" in md and "B구역" in md
    assert "팁 하나" in md


def test_markdown_sorts_areas_by_price():
    r = stay.build("TST", DEST, "2027-02-17", "2027-02-23", 2, 1,
                   fetcher=_fetcher({"A 호텔": [200000], "B 호텔": [90000]}))
    md = stay.to_markdown(r)
    table = md[md.index("| 구역"):md.index("## 구역 가이드")]
    assert table.index("B구역") < table.index("A구역")


# ── 배포 데이터 ──

def test_shipped_areas_json_is_well_formed():
    data = stay.load_areas()
    assert data["destinations"]
    for code, dest in data["destinations"].items():
        assert dest["name"] and dest["areas"], code
        for area in dest["areas"]:
            missing = {"id", "name", "query", "good_for", "why", "caution"} - set(area)
            assert not missing, f"{code}/{area.get('id')}에 없는 항목: {missing}"


def test_unknown_destination_exits_with_known_list():
    with pytest.raises(SystemExit) as e:
        stay.destination(stay.load_areas(), "ZZZ")
    assert "CTS" in str(e.value)


def test_live_destinations_present():
    """이번에 검토한 후보들은 가이드가 있어야 한다."""
    data = stay.load_areas()["destinations"]
    for code in ("CTS", "HKD", "NBR", "NRT", "HKG", "TPE", "FUK", "KIX"):
        assert code in data, code
