"""가격 그래프 요청/응답 처리 테스트 (네트워크 불필요).

요청 페이로드는 Go 구현(krisukox/google-flights-api)의 포맷 문자열을 그대로 재현해
우리 파이썬 구조와 대조한다. Google 내부 API는 비공식이라 구조가 조금만 어긋나도
빈 응답이 오는데, 그 경우 원인 파악이 어려우므로 여기서 미리 잡는다.

실행: python test_price_graph.py
"""
import json
import sys

import main

AIRPORT_CONST = "0"  # Go: flightAirportConst
TRIP_TYPE = 1        # Go: RoundTrip = iota + 1
CLASS = 1            # Go: Economy = iota + 1
STOPS = "0"          # Go: serializeFlightStop(AnyStops)


def build_go_payload(origin, dest, dep, ret, range_start, range_end, nights,
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


def build_our_payload(origin, dest, dep, ret, range_start, range_end, nights,
                      adults, children, inf_lap, inf_seat):
    inner = [
        None,
        [None, None, 1, None, [], 1,
         [adults, children, inf_lap, inf_seat],
         None, None, None, None, None, None,
         [main._price_graph_leg(origin, dest, dep),
          main._price_graph_leg(dest, origin, ret)],
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
    go = json.loads(json.loads(build_go_payload(*args))[1])
    ours = json.loads(json.loads(build_our_payload(*args))[1])
    assert go == ours, (
        "가격 그래프 요청 구조가 Go 원본과 다릅니다.\n"
        f"Go  : {json.dumps(go, separators=(',', ':'))}\n"
        f"Ours: {json.dumps(ours, separators=(',', ':'))}"
    )
    # 여행자 순서는 성인, 소아, 무릎유아, 좌석유아 (Go serializeFlightTravelers와 동일)
    assert ours[1][6] == [2, 1, 0, 1]
    print("✓ 요청 페이로드가 Go 원본과 동일")


def test_leg_structure():
    leg = main._price_graph_leg("ICN", "KIX", "2026-09-01")
    assert leg[0] == [[["ICN", 0]]] and leg[1] == [[["KIX", 0]]]
    assert leg[6] == "2026-09-01"
    assert leg[14] == 3 and len(leg) == 15
    print("✓ 구간(leg) 구조 정상")


def test_parse_response():
    """batchexecute 응답에서 (출발일, 귀국일, 가격)을 뽑아내는지 확인."""
    inner = [None, [
        ["2026-09-01", "2026-09-04", [[None, 210000.0]], 1],
        ["2026-09-02", "2026-09-05", [[None, 180000.0]], 1],
        ["2026-09-03", "2026-09-06", [[None, None]], 1],   # 가격 없음 → 제외
    ]]
    body = json.dumps([["wrb.fr", None, json.dumps(inner)]])
    text = ")]}'\n\n123\n" + body + "\n25\n[[\"di\",59]]\n"

    offers = main._parse_price_graph(text)
    assert len(offers) == 2, offers
    assert offers[0] == {"departure_date": "2026-09-01",
                         "return_date": "2026-09-04", "price": 210000}
    assert offers[1]["price"] == 180000
    print("✓ 응답 파싱 정상 (가격 없는 항목 제외)")


def test_parse_garbage_is_safe():
    """깨진 응답이 와도 예외 없이 빈 결과를 돌려준다."""
    for text in ("", ")]}'\n\n", "[[not json", '[["wrb.fr",null,"{bad}"]]',
                 json.dumps([["wrb.fr", None, json.dumps([None, "not-a-list"])]])):
        assert main._parse_price_graph(text) == []
    print("✓ 잘못된 응답에도 안전")


def test_impersonate_is_supported():
    """primp가 실제 지원하는 지문을 골랐는지 (무작위 대체는 차단 위험)."""
    assert main._IMPERSONATE in main._IMPERSONATE_CANDIDATES
    print(f"✓ 브라우저 지문 = {main._IMPERSONATE}")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
    print(f"\n{len(tests)}개 테스트 통과")
