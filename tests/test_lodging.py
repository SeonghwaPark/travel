"""숙박 딥링크 생성 테스트 (네트워크 불필요).

링크가 조건을 못 물고 가면 사용자가 사이트에서 다시 입력해야 한다 —
그러면 링크를 만드는 의미가 없다. 그래서 인원·객실·아동 나이가 실제로
쿼리에 붙는지를 확인한다.
"""

import os
import sys
from urllib.parse import parse_qs, urlparse

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "backend"))

import lodging  # noqa: E402


def _qs(url):
    return parse_qs(urlparse(url).query)


def _links(**kw):
    base = dict(place="삿포로", check_in="2027-02-17", check_out="2027-02-23",
                adults=2, children=1, child_ages=[8])
    base.update(kw)
    return {l["provider"]: l["url"] for l in lodging.search_links(**base)["links"]}


# ── 인원이 실제로 붙는가 ──

def test_booking_carries_pax_and_child_age():
    q = _qs(_links()["booking"])
    assert q["group_adults"] == ["2"]
    assert q["group_children"] == ["1"]
    assert q["age"] == ["8"]          # 아동 나이는 age 파라미터로
    assert q["no_rooms"] == ["1"]
    assert q["checkin"] == ["2027-02-17"] and q["checkout"] == ["2027-02-23"]


def test_agoda_carries_pax_and_child_age():
    q = _qs(_links()["agoda"])
    assert q["adults"] == ["2"] and q["children"] == ["1"]
    assert q["childAges"] == ["8"]
    assert q["textToSearch"] == ["삿포로"]


def test_hotels_com_sends_children_as_ages():
    q = _qs(_links(children=2, child_ages=[8, 5])["hotels"])
    assert q["adults"] == ["2"]
    assert q["children"] == ["8,5"]   # Expedia 계열은 나이 목록


def test_trip_com_uses_compact_dates():
    q = _qs(_links()["trip"])
    assert q["checkin"] == ["20270217"] and q["checkout"] == ["20270223"]
    assert q["adult"] == ["2"] and q["childrenAges"] == ["8"]


def test_airbnb_puts_place_in_path():
    url = _links()["airbnb"]
    assert "/s/%EC%82%BF%ED%8F%AC%EB%A1%9C/homes" in url
    q = _qs(url)
    assert q["adults"] == ["2"] and q["children"] == ["1"]


def test_every_provider_carries_dates():
    """어느 사이트든 최소한 날짜는 들어가야 한다."""
    for provider, url in _links().items():
        if provider == "google_hotels":
            continue   # 구글 호텔은 검색어만 넘기고 날짜는 화면에서 고른다
        assert "2027" in url, provider


# ── 아동 처리 ──

def test_child_ages_default_when_omitted():
    q = _qs(_links(children=1, child_ages=None)["booking"])
    assert q["age"] == [str(lodging.DEFAULT_CHILD_AGE)]


def test_child_ages_truncated_to_children_count():
    result = lodging.search_links("삿포로", "2027-02-17", "2027-02-23",
                                  adults=2, children=1, child_ages=[8, 5, 3])
    assert result["child_ages"] == [8]


def test_no_children_means_no_age_params():
    q = _qs(_links(children=0, child_ages=None)["booking"])
    assert "age" not in q
    assert q["group_children"] == ["0"]


# ── 객실 수 ──

def test_rooms_default_one_for_family_of_three():
    assert lodging.search_links("삿포로", "2027-02-17", "2027-02-23",
                                adults=2, children=1)["rooms"] == 1


def test_rooms_split_for_large_group():
    """3인을 넘으면 한 방에 안 들어간다 — 객실 수를 올려야 결과가 맞다."""
    assert lodging._rooms_for(4, 0) == 2
    assert lodging._rooms_for(2, 2) == 2
    assert lodging._rooms_for(4, 3) == 3


def test_explicit_rooms_wins():
    assert lodging.search_links("삿포로", "2027-02-17", "2027-02-23",
                                adults=2, children=1, rooms=2)["rooms"] == 2


# ── 전체 ──

def test_all_providers_present_and_labelled():
    result = lodging.search_links("삿포로", "2027-02-17", "2027-02-23", adults=2)
    assert len(result["links"]) == len(lodging.PROVIDERS)
    for link in result["links"]:
        assert link["name"] and link["note"] and link["url"].startswith("https://")


def test_adults_never_below_one():
    assert lodging.search_links("삿포로", "2027-02-17", "2027-02-23",
                                adults=0)["adults"] == 1


def test_stay_city_overrides_airport_town():
    """'고마쓰 (가나자와)'는 공항(도시) 순서라 첫 토큰이 체류 도시가 아니다.

    그 도시로 숙박을 검색하면 엉뚱한 값이 실측으로 저장된다.
    """
    from brief import quote
    assert quote._dest_name("KMQ") == "가나자와"
    assert quote._dest_name("CTS") == "삿포로"    # 도시(공항) 순서는 그대로
    assert quote._dest_name("NGO") == "나고야"
