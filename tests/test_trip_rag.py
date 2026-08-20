"""AI 플래너 접지(RAG) 테스트 (네트워크·LLM SDK 불필요).

접지의 가치는 '모델이 지어내지 않게 하는 것'이므로, 여기서 지키는 건 두 가지다.
하나, 있는 데이터는 반드시 컨텍스트에 실린다 (숙박 구역·시즌 배수·공휴일).
둘, 없는 데이터는 없다고 말하지 않는다 — 달력에 없는 연도의 공휴일은
'없음'이 아니라 '확인 불가'여야 한다. 없는 정밀도를 지어내지 않는 원칙은
프롬프트에도 적용된다.
"""

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "backend"))

import trip_rag  # noqa: E402


# ── 목적지 매칭 ──

def test_matches_international_by_name():
    assert trip_rag.match_destination("삿포로") == "CTS"
    assert trip_rag.match_destination("도쿄") == "NRT"


def test_matches_paren_alias():
    """'고마쓰 (가나자와)'처럼 괄호 안 이름으로도 찾아진다."""
    assert trip_rag.match_destination("가나자와") == "KMQ"


def test_matches_domestic_partial():
    assert trip_rag.match_destination("제주 전체") == "CJU"
    assert trip_rag.match_destination("부산") == "PUS"  # 데이터명은 '부산 (김해)'


def test_matches_iata_code_directly():
    assert trip_rag.match_destination("CTS") == "CTS"


def test_unknown_destination_returns_none():
    assert trip_rag.match_destination("평창") is None
    assert trip_rag.match_destination("") is None


# ── 날짜 사실 ──

def test_date_facts_weekday_and_holidays():
    """요일·연휴 계산은 코드 몫이다 — 모델이 가장 자주 틀리는 부분이라서."""
    facts = trip_rag.date_facts("2027-02-05", "2027-02-10")
    assert facts["nights"] == 5
    assert facts["days"][0] == {"date": "2027-02-05", "weekday": "금"}
    assert facts["holidays_known"] is True
    names = [h["name"] for h in facts["holidays"]]
    assert "설날" in names and len(names) == 4  # 연휴 3일 + 대체공휴일


def test_date_facts_unregistered_year_is_unknown_not_empty():
    """달력에 없는 연도는 '공휴일 없음'이 아니라 '모름'이다."""
    facts = trip_rag.date_facts("2026-05-01", "2026-05-03")
    assert facts["holidays"] == []
    assert facts["holidays_known"] is False


def test_date_facts_rejects_garbage():
    assert trip_rag.date_facts("없는날짜", "2027-02-10") is None
    assert trip_rag.date_facts("2027-02-10", "2027-02-05") is None  # 역순
    assert trip_rag.date_facts("2027-01-01", "2027-03-01") is None  # 30일 초과


# ── 컨텍스트 조립 ──

def test_context_grounds_cts_with_all_sources():
    ctx, grounding, n_days = trip_rag.build_context(
        "삿포로", "2027-02-05", "2027-02-10")
    assert n_days == 6
    assert grounding["destination_code"] == "CTS"
    assert grounding["sources"] == ["달력", "목적지 프로필",
                                    "숙박 구역 가이드", "교통 요금표"]
    # 숙박 구역·교통 요금이 실제로 실렸는지
    assert "삿포로역 주변" in ctx
    assert "신치토세공항" in ctx
    # 눈축제 시즌 배수(02-04~02-12)와 겹치면 경고가 붙는다
    assert "눈축제" in ctx and "1.9배" in ctx


def test_context_off_season_is_labeled():
    ctx, _, _ = trip_rag.build_context("삿포로", "2027-06-01", "2027-06-04")
    assert "제철이 아니다" in ctx
    assert "1.9배" not in ctx  # 시즌 밖에서는 배수 경고가 없다


def test_context_domestic_without_profile_still_has_calendar():
    """정제 데이터가 없는 국내 목적지도 날짜·공휴일 접지는 받는다."""
    ctx, grounding, _ = trip_rag.build_context("속초", "2027-02-27", "2027-03-02")
    assert grounding["sources"] == ["달력"]
    assert "삼일절" in ctx
    assert "숙박 구역" not in ctx  # 없는 데이터 섹션을 지어내지 않는다


def test_context_bad_dates_degrade_gracefully():
    ctx, grounding, n_days = trip_rag.build_context("삿포로", "언젠가", "곧")
    assert n_days is None
    assert "달력" not in grounding["sources"]
    assert "숙박 구역 가이드" in grounding["sources"]  # 날짜와 무관한 접지는 산다


# ── LLM 응답 처리 ──

def test_salvage_json_plain():
    assert trip_rag.salvage_json('{"title": "ok"}') == {"title": "ok"}


def test_salvage_json_strips_code_fence():
    assert trip_rag.salvage_json('```json\n{"title": "ok"}\n```') == {"title": "ok"}


def test_salvage_json_extracts_from_chatter():
    """fallback 모델이 앞뒤에 설명을 붙여도 바깥 {...}만 건진다."""
    text = '알겠습니다! 일정입니다:\n{"title": "ok", "days": []}\n도움이 되길!'
    assert trip_rag.salvage_json(text) == {"title": "ok", "days": []}


def test_salvage_json_rejects_hopeless():
    assert trip_rag.salvage_json("JSON이 아님") is None
    assert trip_rag.salvage_json("") is None
    assert trip_rag.salvage_json('[1, 2]') is None  # 오브젝트만 받는다


def test_plan_max_tokens_scales_with_days():
    """고정 6000이면 긴 일정에서 JSON이 잘리던 문제의 회귀 방지."""
    assert trip_rag.plan_max_tokens(2) < trip_rag.plan_max_tokens(7)
    assert trip_rag.plan_max_tokens(7) > 6000
    assert trip_rag.plan_max_tokens(30) <= 16000  # gpt-4o-mini 출력 한도 안쪽
    assert trip_rag.plan_max_tokens(None) == trip_rag.plan_max_tokens(4)
