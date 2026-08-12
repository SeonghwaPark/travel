"""Google Flights 스크래핑 코어.

FastAPI 웹앱(main.py)과 감시 봇(watch/) 양쪽이 쓰는 공통 모듈.
웹 프레임워크에 의존하지 않으므로 CI에서 fastapi 없이도 임포트된다.
"""

import re
import threading
import time
import time as _time

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

    # 지정 횟수만큼 시도, 매번 새 클라이언트로 요청
    for attempt in range(attempts):
        try:
            # Rate limiting: 요청 간 최소 간격 유지
            global _last_fetch_time
            with _fetch_lock:
                now = _time.time()
                wait = _FETCH_INTERVAL - (now - _last_fetch_time)
                if wait > 0:
                    _time.sleep(wait)
                _last_fetch_time = _time.time()

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
