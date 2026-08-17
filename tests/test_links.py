"""탐색 바로가기 링크·명령어 테스트. 네트워크 없이 돈다."""

import os
import sys
from urllib.parse import parse_qs, unquote, urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from explore import links  # noqa: E402

PAX = dict(adults=2, children=1, infants=0)


def _result(**meta_over):
    meta = {
        "origin": "ICN", "start": "2027-02-01", "end": "2027-02-28",
        "nights": [5, 6], "adults": 2, "children": 1, "infants": 0,
    }
    meta.update(meta_over)
    return {
        "meta": meta,
        "ranking": [{
            "code": "CTS", "name": "삿포로", "best_price": 1_566_600,
            "per_person": 522_200, "departure_date": "2027-02-17",
            "return_date": "2027-02-23", "nights": 6, "dip_pct": 5.0,
        }],
    }


# --- 날짜 형식 ---------------------------------------------------------------

def test_date_formats():
    assert links._yymmdd("2027-02-17") == "270217"
    assert links._compact("2027-02-17") == "20270217"


# --- 예약처 링크 -------------------------------------------------------------

def test_google_flights_encodes_dates_and_pax():
    url = links.google_flights("ICN", "CTS", "2027-02-17", "2027-02-23", 2, 1, 0)
    q = unquote(parse_qs(urlparse(url).query)["q"][0])
    assert "from ICN" in q and "to CTS" in q
    assert "2027-02-17" in q and "2027-02-23" in q
    assert "2 adults" in q and "1 children" in q


def test_google_flights_omits_pax_when_single_adult():
    url = links.google_flights("ICN", "CTS", "2027-02-17", "2027-02-23", 1, 0, 0)
    q = unquote(parse_qs(urlparse(url).query)["q"][0])
    assert "adults" not in q and "children" not in q


def test_skyscanner_path_and_params():
    url = links.skyscanner("ICN", "CTS", "2027-02-17", "2027-02-23", 2, 1, 0)
    path = urlparse(url).path
    assert path.endswith("/icn/cts/270217/270223/")
    qs = parse_qs(urlparse(url).query)
    assert qs["adults"] == ["2"] and qs["children"] == ["1"]
    assert "infants" not in qs          # 0명은 붙이지 않는다


def test_naver_round_trip_legs():
    url = links.naver("ICN", "CTS", "2027-02-17", "2027-02-23", 2, 1, 0)
    assert "ICN-CTS-20270217/CTS-ICN-20270223" in url
    qs = parse_qs(urlparse(url).query)
    assert qs["adult"] == ["2"] and qs["child"] == ["1"] and qs["infant"] == ["0"]


def test_vendor_links_cover_three_platforms():
    names = [n for n, _ in links.vendor_links("ICN", "CTS", "2027-02-17",
                                              "2027-02-23", **PAX)]
    assert names == ["구글 플라이트", "스카이스캐너", "네이버 항공권"]


# --- 인원 분할 ---------------------------------------------------------------

def test_split_links_for_family():
    got = links.split_links("ICN", "CTS", "2027-02-17", "2027-02-23", 2, 1, 0)
    assert [n for n, _ in got] == ["성인 1명만", "성인 1 + 소아 1"]

    solo = dict(got)["성인 1명만"]
    q = unquote(parse_qs(urlparse(solo).query)["q"][0])
    assert "adults" not in q and "children" not in q


def test_split_links_skipped_for_solo_traveler():
    assert links.split_links("ICN", "CTS", "2027-02-17", "2027-02-23", 1, 0, 0) == []


def test_split_links_adults_only_has_no_child_variant():
    got = links.split_links("ICN", "CTS", "2027-02-17", "2027-02-23", 2, 0, 0)
    assert [n for n, _ in got] == ["성인 1명만"]


# --- 다음 탐색 명령 ----------------------------------------------------------

def test_next_commands_carry_scan_conditions():
    cmds = dict(links.next_commands(_result()["meta"], "CTS",
                                    "2027-02-17", "2027-02-23", 6))
    scan = cmds["항공사·시간까지 정밀 스캔"]
    assert "--dest CTS" in scan
    assert "--start 2027-02-01" in scan and "--end 2027-02-28" in scan
    assert "--adults 2 --children 1" in scan

    again = cmds["이 목적지만 다시 탐색 (날짜 곡선 갱신)"]
    assert "--only CTS" in again and "--nights 5,6" in again

    stay = cmds["숙박 견적 링크 받기"]
    assert "--check-in 2027-02-17" in stay and "--check-out 2027-02-23" in stay


# --- 마크다운 ----------------------------------------------------------------

def test_markdown_has_all_three_sections():
    md = links.to_markdown(_result())
    assert "탐색 바로가기" in md
    assert "예약처 비교" in md
    assert "인원 쪼개 보기" in md
    assert "다음 탐색" in md
    assert "삿포로 (CTS)" in md
    assert "1,566,600원" in md


def test_markdown_empty_when_no_ranking():
    assert links.to_markdown({"meta": {}, "ranking": []}) == ""


def test_markdown_limits_destinations():
    result = _result()
    result["ranking"] = [dict(result["ranking"][0], code=f"D{i}", name=f"도시{i}")
                         for i in range(10)]
    md = links.to_markdown(result, top=3)
    assert md.count("**예약처 비교**") == 3


def test_markdown_omits_split_for_solo():
    md = links.to_markdown(_result(adults=1, children=0))
    assert "인원 쪼개 보기" not in md
