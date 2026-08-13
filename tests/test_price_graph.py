"""가격 그래프 요청/응답 처리 테스트 (네트워크 불필요).

요청 페이로드는 Go 구현(krisukox/google-flights-api)의 포맷 문자열을 그대로 재현해
우리 파이썬 구조와 대조한다. Google 내부 API는 비공식이라 구조가 조금만 어긋나도
빈 응답이 오는데, 그 경우 원인 파악이 어려우므로 여기서 미리 잡는다.
"""

import json
import os
import subprocess
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "backend"))

import gflights  # noqa: E402

AIRPORT_CONST = "0"  # Go: flightAirportConst
TRIP_TYPE = 1        # Go: RoundTrip = iota + 1
CLASS = 1            # Go: Economy = iota + 1
STOPS = "0"          # Go: serializeFlightStop(AnyStops)


# ── 요청 페이로드 ──

def _build_go_payload(origin, dest, dep, ret, range_start, range_end, nights,
                      adults, children, inf_lap, inf_seat):
    """Go의 getPriceGraphReqData가 만드는 문자열을 그대로 재현한다."""
    ser_src = f'[\\"{origin}\\",{AIRPORT_CONST}]'
    ser_dst = f'[\\"{dest}\\",{AIRPORT_CONST}]'
    ser_travelers = f"[{adults},{children},{inf_lap},{inf_seat}]"

    raw = (f"[null,null,{TRIP_TYPE},null,[],{CLASS},{ser_travelers},"
           f"null,null,null,null,null,null,[")
    raw += (f'[[[{ser_src}]],[[{ser_dst}]],null,{STOPS},[],[],'
            f'\\"{dep}\\",null,[],[],[],null,null,[],3]')
    raw += (f',[[[{ser_dst}]],[[{ser_src}]],null,{STOPS},[],[],'
            f'\\"{ret}\\",null,[],[],[],null,null,[],3]')

    prefix = '[null,"[null,'
    suffix = (f'],null,null,null,1,null,null,null,null,null,[]],'
              f'[\\"{range_start}\\",\\"{range_end}\\"],null,[{nights},{nights}]]"]')
    return prefix + raw + suffix


def _build_our_payload(origin, dest, dep, ret, range_start, range_end, nights,
                       adults, children, inf_lap, inf_seat):
    inner = [
        None,
        [None, None, 1, None, [], 1,
         [adults, children, inf_lap, inf_seat],
         None, None, None, None, None, None,
         [gflights.price_graph_leg(origin, dest, dep),
          gflights.price_graph_leg(dest, origin, ret)],
         None, None, None, 1, None, None, None, None, None, []],
        [range_start, range_end],
        None,
        [nights, nights],
    ]
    return json.dumps([None, json.dumps(inner, separators=(",", ":"))],
                      separators=(",", ":"))


def test_payload_matches_go():
    args = ("ICN", "KIX", "2026-09-01", "2026-09-04",
            "2026-09-01", "2026-10-30", 3, 2, 1, 0, 1)
    go = json.loads(json.loads(_build_go_payload(*args))[1])
    ours = json.loads(json.loads(_build_our_payload(*args))[1])
    assert go == ours, (
        "가격 그래프 요청 구조가 Go 원본과 다릅니다.\n"
        f"Go  : {json.dumps(go, separators=(',', ':'))}\n"
        f"Ours: {json.dumps(ours, separators=(',', ':'))}"
    )
    # 여행자 순서는 성인, 소아, 무릎유아, 좌석유아 (Go serializeFlightTravelers와 동일)
    assert ours[1][6] == [2, 1, 0, 1]


def test_leg_structure():
    leg = gflights.price_graph_leg("ICN", "KIX", "2026-09-01")
    assert leg[0] == [[["ICN", 0]]] and leg[1] == [[["KIX", 0]]]
    assert leg[6] == "2026-09-01"
    assert leg[14] == 3 and len(leg) == 15


# ── 응답 파싱 ──

def test_parse_response():
    """batchexecute 응답에서 (출발일, 귀국일, 가격)을 뽑아내는지 확인."""
    inner = [None, [
        ["2026-09-01", "2026-09-04", [[None, 210000.0]], 1],
        ["2026-09-02", "2026-09-05", [[None, 180000.0]], 1],
        ["2026-09-03", "2026-09-06", [[None, None]], 1],   # 가격 없음 → 제외
    ]]
    body = json.dumps([["wrb.fr", None, json.dumps(inner)]])
    text = ")]}'\n\n123\n" + body + "\n25\n[[\"di\",59]]\n"

    offers = gflights.parse_price_graph(text)
    assert len(offers) == 2, offers
    assert offers[0] == {"departure_date": "2026-09-01",
                         "return_date": "2026-09-04", "price": 210000}
    assert offers[1]["price"] == 180000


def test_parse_garbage_is_safe():
    """깨진 응답이 와도 예외 없이 빈 결과를 돌려준다."""
    for text in ("", ")]}'\n\n", "[[not json", '[["wrb.fr",null,"{bad}"]]',
                 json.dumps([["wrb.fr", None, json.dumps([None, "not-a-list"])]])):
        assert gflights.parse_price_graph(text) == []


# ── 네트워크 차단 감지 ──

def test_network_down_skips_requests(monkeypatch):
    """차단 상태로 표시되면 요청을 만들지 않고 즉시 빈 결과를 돌려준다."""
    monkeypatch.setattr(gflights, "_network_down_until", gflights._time.time() + 60)
    assert gflights.network_is_down() is True
    assert gflights.fetch_price_graph("ICN", "KIX", "2026-09-01", "2026-10-01", 3) == []
    assert gflights.search_flights("ICN", "KIX", "2026-09-01", "2026-09-04", 1, quiet=True) == []


def test_network_down_expires(monkeypatch):
    """쿨다운이 지나면 다시 시도할 수 있어야 한다."""
    monkeypatch.setattr(gflights, "_network_down_until", gflights._time.time() - 1)
    assert gflights.network_is_down() is False


def test_mark_network_down_sets_cooldown(monkeypatch):
    monkeypatch.setattr(gflights, "_network_down_until", 0.0)
    gflights.mark_network_down()
    remaining = gflights._network_down_until - gflights._time.time()
    assert 0 < remaining <= gflights._NETWORK_DOWN_COOLDOWN


def test_connection_error_detection():
    assert gflights._is_connection_error(Exception("tunnel connection failed"))
    assert gflights._is_connection_error(Exception("Failed to connect to host"))
    assert not gflights._is_connection_error(Exception("timed out parsing"))


# ── 브라우저 지문 ──

def test_impersonate_is_supported():
    """primp가 실제 지원하는 지문인지 확인 — 무작위로 대체되면 차단 위험이 커진다.

    경고를 Rust가 fd2로 직접 찍으므로 자식 프로세스로 돌려 stderr를 잡는다
    (backend/_probe_impersonate.py와 같은 방식).
    """
    child = f"import primp; primp.Client(impersonate={gflights._IMPERSONATE!r}, verify=False)"
    p = subprocess.run([sys.executable, "-c", child], capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    assert "does not exist" not in (p.stderr or ""), (
        f"primp가 {gflights._IMPERSONATE}를 모릅니다. "
        f"python backend/_probe_impersonate.py 로 유효값을 확인하세요.\n{p.stderr}"
    )
