"""Google Flights 스크래핑 코어.

FastAPI 웹앱(main.py)과 감시 봇(watch/) 양쪽이 쓰는 공통 모듈.
웹 프레임워크에 의존하지 않으므로 CI에서 fastapi 없이도 임포트된다.
"""

import json
import re
import threading
import time
import time as _time
from collections import deque
from urllib.parse import quote

import primp
from fast_flights import FlightData, Passengers, TFSData
from selectolax.lexbor import LexborHTMLParser

# Google 요청 간 최소 간격 (rate limiting 방지)
_fetch_lock = threading.Lock()
_last_fetch_time = 0.0
_FETCH_INTERVAL = 1.5  # 최소 1.5초 간격

# primp가 지원하는 브라우저 지문. primp 버전이 오르면 옛 값은 삭제되고
# "Impersonate 'x' does not exist, using 'random'" 경고 후 무작위로 떨어진다.
# 유효값 확인: python _probe_impersonate.py
_IMPERSONATE = "chrome_146"

# Google 연결 자체가 막힌 상태(방화벽·프록시)에서 재시도는 시간만 버린다.
# 한 번 막히면 잠깐 쉬었다가 다시 시도한다 — 40건씩 훑는 스캐너/감시봇에서 특히 크다.
_NETWORK_DOWN_COOLDOWN = 30
_network_down_until = 0.0


def mark_network_down():
    global _network_down_until
    _network_down_until = _time.time() + _NETWORK_DOWN_COOLDOWN


def network_is_down():
    return _time.time() < _network_down_until


def _is_connection_error(exc):
    return "tunnel" in str(exc).lower() or "connect" in str(exc).lower()


def _throttle():
    """Google 요청 간 최소 간격 유지. 스크래핑과 가격 그래프가 같은 간격을 공유한다."""
    global _last_fetch_time
    with _fetch_lock:
        wait = _FETCH_INTERVAL - (_time.time() - _last_fetch_time)
        if wait > 0:
            _time.sleep(wait)
        _last_fetch_time = _time.time()


def parse_price(price_str):
    """'₩129,100' -> 129100"""
    if price_str is None:
        return None
    if isinstance(price_str, (int, float)):
        return int(price_str)
    price_str = str(price_str)
    nums = re.sub(r"[^\d]", "", price_str)
    return int(nums) if nums else None


def parse_aria_label(label):
    """aria-label에서 항공편 정보 추출"""
    info = {"name": "", "price": "", "departure": "", "arrival": "",
            "duration": "", "stops": 0}

    # narrow no-break space(U+202F) / no-break space(U+00A0)를 일반 공백으로
    label = re.sub(r"[\u202f\u00a0]", " ", label)

    m = re.search(r"From ([\d,]+)", label)
    if m:
        info["price"] = m.group(1).replace(",", "")

    m = re.search(r"(Nonstop|(\d+) stops?) flight with (.+?)\.", label)
    if m:
        if m.group(1) == "Nonstop":
            info["stops"] = 0
            info["name"] = m.group(3)
        else:
            info["stops"] = int(m.group(2))
            info["name"] = m.group(3)

    m = re.search(r"at (\d+:\d+ [AP]M) on", label)
    if m:
        info["departure"] = m.group(1)

    m = re.search(r"arrives at .+? at (\d+:\d+ [AP]M)", label)
    if m:
        info["arrival"] = m.group(1)

    m = re.search(r"Total duration (.+?)\.", label)
    if m:
        info["duration"] = m.group(1)

    return info


def search_flights(origin, destination, departure_date, return_date, adults,
                   children=0, infants_in_seat=0, infants_on_lap=0,
                   attempts=5, retry_sleep=2.0, quiet=False):
    """Google Flights에서 항공편 검색 (aria-label 파싱)

    반환: [{name, price, departure, arrival, duration, stops}, ...] (가격은 문자열)
    가격은 전체 승객 합계 기준으로 표시된다.

    attempts/retry_sleep: 날짜 범위를 대량 스캔할 때 재시도를 줄여 총 소요시간을 통제.
    """
    from datetime import datetime, timedelta

    effective_return = return_date
    if not effective_return:
        dep = datetime.strptime(departure_date, "%Y-%m-%d")
        effective_return = (dep + timedelta(days=3)).strftime("%Y-%m-%d")

    tfs = TFSData.from_interface(
        flight_data=[
            FlightData(date=departure_date, from_airport=origin, to_airport=destination),
            FlightData(date=effective_return, from_airport=destination, to_airport=origin),
        ],
        trip="round-trip",
        passengers=Passengers(
            adults=adults, children=children,
            infants_in_seat=infants_in_seat, infants_on_lap=infants_on_lap,
        ),
        seat="economy",
    )
    b64 = tfs.as_b64()
    if isinstance(b64, bytes):
        b64 = b64.decode("utf-8")
    params = {"tfs": b64, "hl": "en", "tfu": "EgQIABABIgA", "curr": "KRW"}

    if network_is_down():
        if not quiet:
            print(f"[SKIP] {origin}->{destination} — Google 연결 차단 상태, 재시도 생략")
        return []

    # 지정 횟수만큼 시도, 매번 새 클라이언트로 요청
    for attempt in range(attempts):
        try:
            _throttle()

            client = primp.Client(impersonate=_IMPERSONATE, verify=False)
            res = client.get("https://www.google.com/travel/flights", params=params)
            if res.status_code != 200:
                if not quiet:
                    print(f"[HTTP {res.status_code}] {origin}->{destination} 시도 {attempt+1}/{attempts}")
                time.sleep(retry_sleep)
                continue

            parser = LexborHTMLParser(res.text)

            flights = []
            for el in parser.css("div.JMc5Xc"):
                label = el.attributes.get("aria-label", "")
                if not label or "Select flight" not in label:
                    continue
                info = parse_aria_label(label)
                if info["price"]:
                    flights.append(info)

            if flights:
                if not quiet:
                    try:
                        print(f"[OK] {origin}->{destination} | {len(flights)} flights | "
                              f"top: {flights[0]['name'] or 'N/A'} {flights[0]['price']}won")
                    except Exception:
                        pass
                return flights
            else:
                if not quiet:
                    try:
                        print(f"[EMPTY] {origin}->{destination} attempt {attempt+1}/{attempts} (Loading)")
                    except Exception:
                        pass
        except Exception as e:
            if not quiet:
                try:
                    print(f"[FAIL] {origin}->{destination} attempt {attempt+1}/{attempts}: {e}")
                except Exception:
                    pass
            # 네트워크 자체가 막힌 경우 재시도해도 소용없으므로 빠르게 포기
            if _is_connection_error(e):
                mark_network_down()
                return []
        time.sleep(retry_sleep)

    return []


def cheapest(origin, destination, departure_date, return_date, adults,
             children=0, infants_in_seat=0, infants_on_lap=0, **kw):
    """해당 일정의 최저가 1건. 결과 없으면 None."""
    raw = search_flights(origin, destination, departure_date, return_date, adults,
                         children, infants_in_seat, infants_on_lap, **kw)
    best = None
    for f in raw:
        p = parse_price(f.get("price"))
        if p is None:
            continue
        if best is None or p < best["price"]:
            best = {
                "price": p,
                "airline": f.get("name") or "",
                "duration": f.get("duration") or "",
                "departure": f.get("departure") or "",
                "arrival": f.get("arrival") or "",
                "stops": f.get("stops", 0),
            }
    return best


# ── 가격 그래프 ──
#
# Google Flights가 달력 화면에 쓰는 내부 API. 요청 한 번으로 날짜 범위 전체의
# 왕복 최저가를 받아온다 — 날짜마다 검색 페이지를 긁는 search_flights보다 수십 배 빠르다.
# 비공식 API라 구조가 조금만 어긋나도 빈 응답이 오므로, 호출부는 실패 시
# search_flights 스캔으로 되돌아갈 수 있어야 한다.

MAX_RANGE_DAYS = 161  # 한 번에 조회 가능한 최대 기간

_pg_log = deque(maxlen=50)  # 최근 호출 기록 (진단용)


def pg_log():
    """가격 그래프 최근 로그 사본."""
    return list(_pg_log)


def _pg_print(msg):
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    _pg_log.append(line)
    try:
        print(line)
    except Exception:
        pass


def price_graph_leg(src, dst, date):
    """내부 API가 기대하는 구간(leg) 배열. 마지막 3은 좌석 등급(economy)."""
    return [[[[src, 0]]], [[[dst, 0]]], None, 0, [], [], date, None, [], [], [], None, None, [], 3]


def parse_price_graph(text):
    """batchexecute 응답에서 (출발일, 귀국일, 가격) 목록 추출.

    응답은 줄 단위로 길이 헤더와 JSON이 섞여 오고, 실제 데이터는 JSON 문자열
    안에 다시 JSON으로 들어있다. 어느 단계가 깨져도 빈 결과를 돌려준다.
    """
    offers = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("[["):
            continue
        try:
            chunk = json.loads(line)
        except json.JSONDecodeError:
            continue
        for part in chunk:
            if not (isinstance(part, list) and len(part) >= 3 and isinstance(part[2], str)):
                continue
            try:
                inner = json.loads(part[2])
            except json.JSONDecodeError:
                continue
            if not (isinstance(inner, list) and len(inner) >= 2 and isinstance(inner[1], list)):
                continue
            for o in inner[1]:
                try:
                    dep_date, ret_date = o[0], o[1]
                    price = o[2][0][1]
                    if dep_date and ret_date and price:
                        offers.append({
                            "departure_date": dep_date,
                            "return_date": ret_date,
                            "price": int(price),
                        })
                except (TypeError, IndexError, ValueError):
                    continue
    return offers


def fetch_price_graph(origin, destination, range_start, range_end, nights,
                      adults=1, children=0, infants_in_seat=0, infants_on_lap=0,
                      attempts=3, retry_sleep=2.0):
    """range_start~range_end 사이 모든 출발일의 왕복 최저가를 한 번에 조회.

    반환: [{departure_date, return_date, price}, ...] (실패 시 빈 리스트)
    """
    from datetime import datetime, timedelta

    if network_is_down():
        _pg_print(f"[PriceGraph SKIP] {origin}->{destination} — Google 연결 차단 상태")
        return []

    dep = datetime.strptime(range_start, "%Y-%m-%d")
    ret = dep + timedelta(days=nights)

    # 내부 요청 구조: [null, 검색조건, [기간 시작, 기간 끝], null, [여행일수, 여행일수]]
    # 승객 순서는 성인, 소아, 무릎유아, 좌석유아 — 순서가 바뀌면 조용히 다른 가격이 온다.
    inner = [
        None,
        [None, None, 1, None, [], 1,
         [adults, children, infants_on_lap, infants_in_seat],
         None, None, None, None, None, None,
         [
             price_graph_leg(origin, destination, dep.strftime("%Y-%m-%d")),
             price_graph_leg(destination, origin, ret.strftime("%Y-%m-%d")),
         ],
         None, None, None, 1, None, None, None, None, None, []],
        [range_start, range_end],
        None,
        [nights, nights],
    ]
    freq = json.dumps([None, json.dumps(inner, separators=(",", ":"))],
                      separators=(",", ":"))
    body = ("f.req=" + quote(freq, safe="")
            + "&at=AAuQa1oq5qIkgkQ2nG9vQZFTgSME%3A" + str(int(_time.time())) + "&")

    url = ("https://www.google.com/_/FlightsFrontendUi/data/"
           "travel.frontend.flights.FlightsFrontendService/GetCalendarGraph"
           "?f.sid=-8920707734915550076&bl=boq_travel-frontend-ui_20230627.07_p1"
           "&hl=en&soc-app=162&soc-platform=1&soc-device=1&_reqid=261464&rt=c")

    headers = {
        "accept": "*/*",
        "accept-language": "en-US,en;q=0.9",
        "content-type": "application/x-www-form-urlencoded;charset=UTF-8",
        "x-goog-ext-259736195-jspb":
            '["en-US","US","KRW",1,null,[-120],null,[[48764689,47907128,48676280,'
            '48710756,48627726,48480739,48593234,48707380]],1,[]]',
    }

    for attempt in range(attempts):
        try:
            _throttle()

            client = primp.Client(impersonate=_IMPERSONATE, verify=False, cookie_store=True)
            client.get("https://www.google.com/")  # 쿠키 확보
            res = client.post(url, content=body.encode(), headers=headers)
            if res.status_code != 200:
                _pg_print(f"[PriceGraph HTTP {res.status_code}] {origin}->{destination} "
                          f"{nights}박 시도 {attempt+1}/{attempts}")
                time.sleep(retry_sleep)
                continue

            offers = parse_price_graph(res.text)
            if offers:
                _pg_print(f"[PriceGraph OK] {origin}->{destination} {nights}박 | {len(offers)}개 날짜")
                return offers
            _pg_print(f"[PriceGraph EMPTY] {origin}->{destination} {nights}박 "
                      f"시도 {attempt+1}/{attempts}")
        except Exception as e:
            _pg_print(f"[PriceGraph FAIL] {origin}->{destination} {nights}박 "
                      f"시도 {attempt+1}/{attempts}: {e}")
            if _is_connection_error(e):
                mark_network_down()
                return []
        time.sleep(retry_sleep)

    return []
