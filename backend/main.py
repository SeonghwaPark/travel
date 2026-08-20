import sys, io
# 원본 스트림 참조를 유지해야 함 — 안 그러면 GC가 원본 TextIOWrapper를 수거하면서
# 밑에 깔린 buffer까지 닫아버려 이후 print가 "I/O operation on closed file"로 죽는다.
_ORIG_STDOUT, _ORIG_STDERR = sys.stdout, sys.stderr
if sys.stdout and hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
if sys.stderr and hasattr(sys.stderr, 'buffer'):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import asyncio
import json
import os
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote
from dotenv import load_dotenv
from openai import OpenAI
from groq import Groq

load_dotenv()
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY")) if os.getenv("OPENAI_API_KEY") else None
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY")) if os.getenv("GROQ_API_KEY") else None

# 스크래핑 코어는 gflights로 분리 — 감시 봇(watch/)도 같은 코드를 쓴다
import lodging
import transport
import trip_rag  # AI 플래너 접지 — 리포의 정제 데이터를 프롬프트에 끼운다

from gflights import (
    MAX_RANGE_DAYS,
    fetch_price_graph,
    network_is_down,
    parse_price,
    pg_log,
    search_flights as _search_flights,
)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request Models ──

class FlightSearchRequest(BaseModel):
    origin: str
    destination: str
    departure_date: str
    return_date: str | None = None
    adults: int = 1
    children: int = 0
    infants_in_seat: int = 0
    infants_on_lap: int = 0
    max_results: int = 10


class CheapestDestinationsRequest(BaseModel):
    origin: str = "ICN"
    departure_date: str
    return_date: str | None = None
    adults: int = 1
    children: int = 0
    infants_in_seat: int = 0
    infants_on_lap: int = 0
    mode: str = "international"  # "international" | "domestic" | "all"


class BestDatesRequest(BaseModel):
    origin: str = "ICN"
    destination: str
    earliest_departure: str
    latest_departure: str
    nights: int = 3
    min_nights: int | None = None  # 지정 시 nights 대신 min~max 조합 스캔
    max_nights: int | None = None
    adults: int = 1
    children: int = 0
    infants_in_seat: int = 0
    infants_on_lap: int = 0


class HotelSearchRequest(BaseModel):
    destination: str
    check_in: str
    check_out: str
    adults: int = 1
    children: int = 0
    child_ages: list[int] | None = None
    rooms: int | None = None


class TransportPlanRequest(BaseModel):
    region: str = "hokkaido"
    legs: list[str]
    trip_days: int | None = None


class ActivitySearchRequest(BaseModel):
    destination: str


class DomesticSearchRequest(BaseModel):
    region: str
    check_in: str
    check_out: str
    adults: int = 2


# ── Data ──

DOMESTIC_REGIONS = {
    "jeju":      {"name": "제주",    "keyword": "제주"},
    "busan":     {"name": "부산",    "keyword": "부산"},
    "sokcho":    {"name": "속초",    "keyword": "속초"},
    "gangneung": {"name": "강릉",    "keyword": "강릉"},
    "gyeongju":  {"name": "경주",    "keyword": "경주"},
    "yeosu":     {"name": "여수",    "keyword": "여수"},
    "jeonju":    {"name": "전주",    "keyword": "전주"},
    "tongyeong": {"name": "통영",    "keyword": "통영"},
    "gapyeong":  {"name": "가평",    "keyword": "가평"},
    "seoul":     {"name": "서울",    "keyword": "서울"},
    "incheon":   {"name": "인천",    "keyword": "인천"},
    "daegu":     {"name": "대구",    "keyword": "대구"},
    "gwangju":   {"name": "광주",    "keyword": "광주"},
    "daejeon":   {"name": "대전",    "keyword": "대전"},
    "chuncheon": {"name": "춘천",    "keyword": "춘천"},
    "namhae":    {"name": "남해",    "keyword": "남해"},
    "boryeong":  {"name": "보령",    "keyword": "보령"},
    "yangyang":  {"name": "양양",    "keyword": "양양"},
}

# 감시 봇(watch/deals.py)과 같은 목록을 써야 하므로 리포 루트 airlines.json에서 읽는다
_AIRLINES_JSON = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "airlines.json")
try:
    with open(_AIRLINES_JSON, encoding="utf-8") as _f:
        AIRLINE_DEALS = json.load(_f)
except (OSError, json.JSONDecodeError):
    AIRLINE_DEALS = []

# 목적지 목록은 리포 루트 destinations.json에서 읽는다 — 탐색 스캐너(explore/)가
# FastAPI 없이 같은 목록을 써야 하므로. airlines.json과 같은 방식.
_DESTINATIONS_JSON = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "destinations.json")
with open(_DESTINATIONS_JSON, encoding="utf-8") as _f:
    _DESTINATIONS = json.load(_f)

KOREAN_AIRPORTS = _DESTINATIONS["origins"]
DOMESTIC_DESTINATIONS = _DESTINATIONS["domestic"]
POPULAR_DESTINATIONS = _DESTINATIONS["international"]


# ── Helpers ──
# parse_price / 항공편 검색은 gflights 모듈로 이동함 (상단 import 참고)

def google_flights_url(origin, destination, departure_date, return_date=None,
                       adults=1, children=0, infants_in_seat=0, infants_on_lap=0):
    """Google Flights URL - 자연어 쿼리 방식 (자동입력 확실히 됨)"""
    q = f"Flights to {destination} from {origin} on {departure_date}"
    if return_date:
        q += f" through {return_date}"
    pax = []
    if adults > 1:
        pax.append(f"{adults} adults")
    if children > 0:
        pax.append(f"{children} children")
    if infants_in_seat + infants_on_lap > 0:
        pax.append(f"{infants_in_seat + infants_on_lap} infants")
    if pax:
        q += " " + " ".join(pax)
    return f"https://www.google.com/travel/flights?q={quote(q)}&curr=KRW&hl=ko"


def kayak_url(origin, destination, departure_date, return_date=None,
              adults=1, children=0, infants=0):
    """Kayak 항공권 검색 URL"""
    dep = departure_date
    path = f"/flights/{origin}-{destination}/{dep}"
    if return_date:
        path += f"/{return_date}"
    params = f"?sort=bestflight_a&fs=cabin=e"
    if adults > 1:
        params += f"&adults={adults}"
    if children > 0:
        params += f"&children={children}"
    return f"https://www.kayak.co.kr{path}{params}"


_AIRPORT_TO_CITY = {
    "ICN": "SEL", "GMP": "SEL",
    "NRT": "TYO", "HND": "TYO",
    "KIX": "OSA", "ITM": "OSA",
    "FUK": "FUK",
    "BKK": "BKK", "DMK": "BKK",
    "SIN": "SIN",
    "HKG": "HKG",
    "TPE": "TPE", "TSA": "TPE",
    "HAN": "HAN", "SGN": "SGN", "DAD": "DAD",
    "MNL": "MNL", "CEB": "CEB",
    "KUL": "KUL",
    "DPS": "DPS",
    "GUM": "GUM",
    "LAX": "LAX", "SFO": "SFO", "JFK": "NYC", "EWR": "NYC",
    "LHR": "LON", "LGW": "LON", "STN": "LON",
    "CDG": "PAR", "ORY": "PAR",
    "FCO": "ROM", "BCN": "BCN",
    "SYD": "SYD", "PEK": "BJS", "PKX": "BJS",
    "PVG": "SHA", "SHA": "SHA",
    "CNX": "CNX", "PNH": "PNH", "REP": "REP",
}

def trip_com_url(origin, destination, departure_date, return_date=None,
                 adults=1, children=0, infants=0):
    """Trip.com 항공권 검색 URL"""
    cabin = "Y"  # economy
    o_city = _AIRPORT_TO_CITY.get(origin.upper(), origin)
    d_city = _AIRPORT_TO_CITY.get(destination.upper(), destination)
    base = f"https://kr.trip.com/flights/{o_city.lower()}-to-{d_city.lower()}/tickets-{o_city}-{d_city}?dcity={o_city}&acity={d_city}&ddate={departure_date}&flighttype="
    if return_date:
        base += f"RT&rdate={return_date}"
    else:
        base += "OW"
    base += f"&adult={adults}&child={children}&infant={infants}&class={cabin}&lowpricesource=searchform&curr=KRW"
    return base


def naver_flights_domestic_url(origin, destination, departure_date, return_date=None,
                               adults=1, children=0, infants=0):
    """네이버 항공 국내선 URL"""
    dep = departure_date.replace("-", "")
    base = f"https://flight.naver.com/flights/domestic/{origin}-{destination}/{dep}?adult={adults}"
    if children > 0:
        base += f"&child={children}"
    if infants > 0:
        base += f"&infant={infants}"
    if return_date:
        ret = return_date.replace("-", "")
        base = f"https://flight.naver.com/flights/domestic/{origin}-{destination}/{dep}/{destination}-{origin}/{ret}?adult={adults}"
        if children > 0:
            base += f"&child={children}"
        if infants > 0:
            base += f"&infant={infants}"
    return base


def _booking_links(origin, destination, departure_date, return_date=None,
                   adults=1, children=0, infants_in_seat=0, infants_on_lap=0,
                   domestic=False):
    """예약 링크 생성 (국내/해외 구분)"""
    infants = infants_in_seat + infants_on_lap
    links = {
        "google_flights": google_flights_url(origin, destination, departure_date, return_date,
                                             adults, children, infants_in_seat, infants_on_lap),
    }
    if domestic:
        links["naver_flights"] = naver_flights_domestic_url(
            origin, destination, departure_date, return_date, adults, children, infants)
    else:
        links["kayak"] = kayak_url(origin, destination, departure_date, return_date,
                                   adults, children, infants)
        links["trip_com"] = trip_com_url(origin, destination, departure_date, return_date,
                                         adults, children, infants)
    return links


# ── Airports ──

@app.get("/api/airports")
def get_airports_endpoint():
    return {
        "origins": KOREAN_AIRPORTS,
        "destinations": POPULAR_DESTINATIONS,
        # 최저가 날짜 탭에서 국내 목적지도 고를 수 있어야 한다
        "domestic_destinations": DOMESTIC_DESTINATIONS,
    }


# ── Flights ──

@app.post("/api/flights/search")
def search_flights(req: FlightSearchRequest):
    links = _booking_links(req.origin, req.destination, req.departure_date, req.return_date,
                           req.adults, req.children, req.infants_in_seat, req.infants_on_lap)
    try:
        raw_flights = _search_flights(
            req.origin, req.destination,
            req.departure_date, req.return_date, req.adults,
            req.children, req.infants_in_seat, req.infants_on_lap,
        )

        if not raw_flights:
            return {"count": 0, "flights": [], "booking_links": links}

        flights = []
        for i, f in enumerate(raw_flights[:req.max_results]):
            price = int(f["price"]) if f["price"] else None
            if price is None:
                continue

            flights.append({
                "id": str(i),
                "itineraries": [{
                    "duration": f["duration"],
                    "segments": [{
                        "departure_airport": req.origin,
                        "departure_time": f["departure"],
                        "arrival_airport": req.destination,
                        "arrival_time": f["arrival"],
                        "carrier": f["name"],
                        "flight_number": f["name"],
                        "duration": f["duration"],
                        "aircraft": "",
                    }],
                    "stops": f["stops"],
                }],
                "price": {
                    "total": str(price),
                    "currency": "KRW",
                },
                "booking_class": "economy",
                "seats_remaining": None,
                "airline": f["name"],
                "booking_links": links,
            })

        flights.sort(key=lambda fl: int(fl["price"]["total"]))

        return {"count": len(flights), "flights": flights}
    except Exception:
        return {"count": 0, "flights": [], "message": "검색 결과를 가져오지 못했습니다. 외부 사이트에서 직접 검색해보세요.", "booking_links": links}


# ── Cheapest Destinations ──

executor = ThreadPoolExecutor(max_workers=3)


def _search_one_destination(origin, dest_code, departure_date, return_date, adults,
                             children=0, infants_in_seat=0, infants_on_lap=0,
                             destinations_db=None, domestic=False):
    if destinations_db is None:
        destinations_db = POPULAR_DESTINATIONS
    try:
        raw_flights = _search_flights(origin, dest_code, departure_date, return_date, adults,
                                      children, infants_in_seat, infants_on_lap)
        prices = []
        for f in raw_flights:
            p = int(f["price"]) if f["price"] else None
            if p is not None:
                prices.append((p, f))

        if prices:
            prices.sort(key=lambda x: x[0])
            dest_info = destinations_db.get(dest_code, {})
            booking_links = _booking_links(origin, dest_code, departure_date, return_date,
                                           adults, children, infants_in_seat, infants_on_lap,
                                           domestic=domestic)

            cheapest_price, cheapest = prices[0]

            seen = set()
            alternatives = []
            for p, f in prices:
                key = (f["name"], f["departure"])
                if key in seen:
                    continue
                seen.add(key)
                alternatives.append({
                    "price": str(p),
                    "airline": f["name"],
                    "duration": f["duration"],
                    "departure": f["departure"],
                    "arrival": f["arrival"],
                    "stops": f["stops"],
                })
                if len(alternatives) >= 5:
                    break

            return {
                "destination_code": dest_code,
                "destination_name": dest_info.get("name", dest_code),
                "country": dest_info.get("country", ""),
                "price": {"total": str(cheapest_price), "currency": "KRW"},
                "airline": cheapest["name"],
                "duration": cheapest["duration"],
                "departure": cheapest["departure"],
                "arrival": cheapest["arrival"],
                "stops": cheapest["stops"],
                "alternatives": alternatives,
                "booking_links": booking_links,
            }
    except Exception:
        pass
    return None


@app.post("/api/flights/cheapest-destinations")
async def cheapest_destinations(req: CheapestDestinationsRequest):
    if req.mode == "domestic":
        destinations_db = DOMESTIC_DESTINATIONS
        domestic = True
    elif req.mode == "all":
        destinations_db = {**POPULAR_DESTINATIONS, **DOMESTIC_DESTINATIONS}
        domestic = False
    else:
        destinations_db = POPULAR_DESTINATIONS
        domestic = False

    # 국내선은 출발지에서 자기 자신 제외
    dest_codes = [c for c in destinations_db if c != req.origin]

    loop = asyncio.get_event_loop()
    tasks = [
        loop.run_in_executor(
            executor,
            _search_one_destination,
            req.origin, dest_code, req.departure_date, req.return_date, req.adults,
            req.children, req.infants_in_seat, req.infants_on_lap,
            destinations_db, domestic,
        )
        for dest_code in dest_codes
    ]
    results = await asyncio.gather(*tasks)
    destinations = [r for r in results if r is not None]
    destinations.sort(key=lambda d: int(d["price"]["total"]))

    return {"count": len(destinations), "destinations": destinations, "mode": req.mode}


# ── Best Dates (목적지 고정, 최저가 날짜 찾기) ──
#
# 가격 그래프로 기간 전체를 한 번에 받고, 실패하면 날짜별 스캔으로 되돌아간다.
# 스캔은 요청당 수십 건을 긁게 되므로 조합 수에 상한을 둔다.

_MAX_DATE_SCAN = 14   # 폴백 스캔 시 최대 출발일 수
_MAX_COMBOS = 28      # 폴백 스캔 시 출발일 × 여행기간 조합 상한
_MAX_NIGHTS_SPAN = 4  # 한 번에 비교할 수 있는 박수 종류 (예: 2~5박)
_TOP_DETAIL = 5       # 상세 항공편(항공사·시간)을 조회할 상위 조합 수


def _search_one_date(origin, destination, departure_date, return_date, adults,
                     children=0, infants_in_seat=0, infants_on_lap=0, domestic=False):
    """한 날짜 조합의 최저가 + 항공사·시간까지. 결과 없으면 None."""
    try:
        raw_flights = _search_flights(origin, destination, departure_date, return_date,
                                      adults, children, infants_in_seat, infants_on_lap)
        prices = []
        for f in raw_flights:
            p = parse_price(f["price"])
            if p is not None:
                prices.append((p, f))
        if not prices:
            return None

        prices.sort(key=lambda x: x[0])
        cheapest_price, cheapest = prices[0]
        booking_links = _booking_links(origin, destination, departure_date, return_date,
                                       adults, children, infants_in_seat, infants_on_lap,
                                       domestic=domestic)
        return {
            "departure_date": departure_date,
            "return_date": return_date,
            "price": {"total": str(cheapest_price), "currency": "KRW"},
            "airline": cheapest["name"],
            "duration": cheapest["duration"],
            "departure": cheapest["departure"],
            "arrival": cheapest["arrival"],
            "stops": cheapest["stops"],
            "booking_links": booking_links,
        }
    except Exception:
        return None


@app.post("/api/flights/best-dates")
async def best_dates(req: BestDatesRequest):
    from datetime import datetime, timedelta

    try:
        earliest = datetime.strptime(req.earliest_departure, "%Y-%m-%d")
        latest = datetime.strptime(req.latest_departure, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="날짜 형식이 잘못되었습니다 (YYYY-MM-DD)")
    if latest < earliest:
        raise HTTPException(status_code=400, detail="마지막 출발일이 첫 출발일보다 빠릅니다")

    min_n = req.min_nights if req.min_nights is not None else req.nights
    max_n = req.max_nights if req.max_nights is not None else req.nights
    if min_n < 1 or max_n > 30 or min_n > max_n:
        raise HTTPException(status_code=400, detail="여행 기간은 1~30박, 최소가 최대보다 클 수 없습니다")
    if max_n - min_n + 1 > _MAX_NIGHTS_SPAN:
        raise HTTPException(
            status_code=400,
            detail=f"여행 기간 범위는 최대 {_MAX_NIGHTS_SPAN}개(예: 2~5박)까지 가능합니다")
    nights_options = list(range(min_n, max_n + 1))

    window_days = (latest - earliest).days + 1
    if window_days > MAX_RANGE_DAYS:
        latest = earliest + timedelta(days=MAX_RANGE_DAYS - 1)
        window_days = MAX_RANGE_DAYS

    dest_code = req.destination.upper()
    origin_code = req.origin.upper()
    domestic = dest_code in DOMESTIC_DESTINATIONS and origin_code in KOREAN_AIRPORTS
    dest_info = {**POPULAR_DESTINATIONS, **DOMESTIC_DESTINATIONS}.get(dest_code, {})
    earliest_s = earliest.strftime("%Y-%m-%d")
    latest_s = latest.strftime("%Y-%m-%d")

    loop = asyncio.get_event_loop()

    # 1) 가격 그래프: 여행기간(박수)당 요청 1번으로 전체 날짜의 최저가 확보
    pg_results = await asyncio.gather(*[
        loop.run_in_executor(
            executor,
            fetch_price_graph,
            origin_code, dest_code, earliest_s, latest_s, n,
            req.adults, req.children, req.infants_in_seat, req.infants_on_lap,
        )
        for n in nights_options
    ])

    found = []
    for n, offers in zip(nights_options, pg_results):
        for o in offers:
            found.append({
                "departure_date": o["departure_date"],
                "return_date": o["return_date"],
                "nights": n,
                "price": {"total": str(o["price"]), "currency": "KRW"},
                # 가격 그래프는 가격만 준다 — 상위 조합만 아래에서 상세 보강한다
                "airline": "",
                "duration": "",
                "departure": "",
                "arrival": "",
                "stops": None,
                "booking_links": _booking_links(
                    origin_code, dest_code, o["departure_date"], o["return_date"],
                    req.adults, req.children, req.infants_in_seat, req.infants_on_lap,
                    domestic=domestic),
            })
    method = "price_graph"
    sampled = False
    scanned_dates = window_days

    # 2) 폴백: 가격 그래프 실패 시 날짜별 스캔 (범위 넓으면 균등 샘플링)
    if not found:
        method = "scan"
        max_dates = max(1, min(_MAX_DATE_SCAN, _MAX_COMBOS // len(nights_options)))
        if window_days <= max_dates:
            day_offsets = list(range(window_days))
        else:
            step = (window_days - 1) / (max_dates - 1) if max_dates > 1 else 0
            day_offsets = sorted({round(i * step) for i in range(max_dates)})
            sampled = True
        scanned_dates = len(day_offsets)

        date_pairs = []
        for off in day_offsets:
            dep = earliest + timedelta(days=off)
            for n in nights_options:
                ret = dep + timedelta(days=n)
                date_pairs.append((dep.strftime("%Y-%m-%d"), ret.strftime("%Y-%m-%d"), n))

        results = await asyncio.gather(*[
            loop.run_in_executor(
                executor,
                _search_one_date,
                origin_code, dest_code, dep, ret, req.adults,
                req.children, req.infants_in_seat, req.infants_on_lap, domestic,
            )
            for dep, ret, _n in date_pairs
        ])
        for r, (_dep, _ret, n) in zip(results, date_pairs):
            if r is not None:
                r["nights"] = n
                found.append(r)

    by_price = sorted(found, key=lambda r: int(r["price"]["total"]))
    prices = [int(r["price"]["total"]) for r in found]

    # 3) 상위 조합만 상세 항공편(항공사·시간) 보강
    if method == "price_graph" and by_price:
        top = by_price[:_TOP_DETAIL]
        details = await asyncio.gather(*[
            loop.run_in_executor(
                executor,
                _search_one_date,
                origin_code, dest_code, r["departure_date"], r["return_date"], req.adults,
                req.children, req.infants_in_seat, req.infants_on_lap, domestic,
            )
            for r in top
        ])
        for r, d in zip(top, details):
            if d is not None:
                r.update({k: d[k] for k in ("airline", "duration", "departure", "arrival", "stops")})

    message = None
    if not by_price:
        message = (
            "Google 항공편 서버에 연결하지 못했습니다. 네트워크나 방화벽 설정을 확인해주세요."
            if network_is_down() else
            "해당 조건의 항공편 가격을 가져오지 못했습니다. 여행 기간이나 날짜 범위를 바꿔 다시 시도해보세요."
        )

    fallback_link = google_flights_url(
        origin_code, dest_code, earliest_s, None, req.adults,
        req.children, req.infants_in_seat, req.infants_on_lap)

    return {
        "origin": origin_code,
        "destination_code": dest_code,
        "destination_name": dest_info.get("name", dest_code),
        "country": dest_info.get("country", ""),
        "min_nights": min_n,
        "max_nights": max_n,
        "method": method,
        "scanned_dates": scanned_dates,
        "sampled": sampled,
        "count": len(by_price),
        "cheapest": by_price[0] if by_price else None,
        "average_price": int(sum(prices) / len(prices)) if prices else None,
        "results": by_price[:40],
        "message": message,
        "fallback_link": fallback_link if message else None,
    }


@app.get("/api/flights/price-graph/health")
async def price_graph_health():
    """가격 그래프 연결 자가 진단: ICN→KIX 30일 범위를 한 번 조회해본다."""
    from datetime import datetime, timedelta

    start = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    end = (datetime.now() + timedelta(days=37)).strftime("%Y-%m-%d")

    loop = asyncio.get_event_loop()
    offers = await loop.run_in_executor(
        executor, fetch_price_graph, "ICN", "KIX", start, end, 3)

    return {
        "ok": len(offers) > 0,
        "tested_route": "ICN → KIX",
        "tested_range": f"{start} ~ {end} (3박)",
        "offers_found": len(offers),
        "sample": offers[:3],
        "logs": pg_log(),
        "hint": ("정상 동작 중입니다." if offers else
                 "가격 그래프 조회에 실패했습니다. logs 내용을 복사해서 알려주시면 원인을 잡을 수 있습니다. "
                 "실패해도 '최저가 날짜' 검색은 날짜별 스캔 방식으로 자동 전환되어 동작합니다."),
    }


# ── Hotels (외부 링크) ──

@app.post("/api/hotels/search")
def search_hotels(req: HotelSearchRequest):
    """예약처별 검색 링크. 가격은 긁지 않는다 (약관·봇차단 문제).

    인원·객실·아동 나이까지 채워서 보낸다 — 이게 빠지면 3인 가족이 열어도
    2인 기준 결과가 떠서 링크가 사실상 쓸모없어진다.
    """
    dest_info = {**POPULAR_DESTINATIONS, **DOMESTIC_DESTINATIONS}.get(req.destination)
    if not dest_info:
        raise HTTPException(status_code=400, detail="지원하지 않는 목적지입니다")

    place = dest_info["name"].split()[0]
    result = lodging.search_links(
        place, req.check_in, req.check_out,
        adults=req.adults, children=req.children,
        child_ages=req.child_ages, rooms=req.rooms,
    )
    result["destination_code"] = req.destination
    result["destination_name"] = dest_info["name"]
    result["country"] = dest_info.get("country", "")
    result["count"] = len(result["links"])
    result["note"] = (
        "가격은 각 사이트에서 확인하세요. 인원·객실 조건은 링크에 이미 반영돼 있습니다."
    )
    return result


# ── Transport (구간 요금·패스 손익) ──

@app.get("/api/transport/regions")
def get_transport_regions():
    data = transport.load()
    return {
        "regions": [
            {
                "id": rid,
                "name": r["name"],
                "currency": r.get("currency"),
                "legs": [{"id": lid, **leg} for lid, leg in r["legs"].items()],
                "passes": r.get("passes", []),
                "fares_verified": r.get("fares_verified", False),
            }
            for rid, r in data["regions"].items()
        ]
    }


@app.post("/api/transport/plan")
def plan_transport(req: TransportPlanRequest):
    """구간 목록으로 개별권 합계와 패스 손익을 계산한다."""
    try:
        return transport.plan(req.region, req.legs, req.trip_days)
    except KeyError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Activities (외부 링크) ──

@app.post("/api/activities/search")
def search_activities(req: ActivitySearchRequest):
    dest_info = POPULAR_DESTINATIONS.get(req.destination)
    if not dest_info:
        raise HTTPException(status_code=400, detail="지원하지 않는 목적지입니다")

    dest_name = dest_info["name"].split()[0]
    activities = [
        {
            "name": f"{dest_name} 투어 & 액티비티 (Klook)",
            "description": f"{dest_info['country']} {dest_name}의 투어, 체험, 입장권을 검색하세요",
            "rating": None,
            "review_count": 0,
            "price": {"amount": "0", "currency": ""},
            "picture": None,
            "booking_link": f"https://www.klook.com/ko/search/?query={quote(dest_name)}",
            "duration": "",
        },
        {
            "name": f"{dest_name} 현지 체험 (GetYourGuide)",
            "description": f"{dest_name}의 가이드 투어, 박물관 입장권, 현지 체험",
            "rating": None,
            "review_count": 0,
            "price": {"amount": "0", "currency": ""},
            "picture": None,
            "booking_link": f"https://www.getyourguide.com/s/?q={quote(dest_name)}",
            "duration": "",
        },
        {
            "name": f"{dest_name} 여행 액티비티 (Viator)",
            "description": f"{dest_name} 관광, 데이투어, 크루즈 등",
            "rating": None,
            "review_count": 0,
            "price": {"amount": "0", "currency": ""},
            "picture": None,
            "booking_link": f"https://www.viator.com/searchResults/all?text={quote(dest_name)}",
            "duration": "",
        },
    ]

    return {"count": len(activities), "activities": activities}


# ── Domestic Regions ──

@app.get("/api/domestic/regions")
def get_domestic_regions():
    return DOMESTIC_REGIONS


@app.post("/api/domestic/search")
def search_domestic(req: DomesticSearchRequest):
    region = DOMESTIC_REGIONS.get(req.region)
    if not region:
        raise HTTPException(status_code=400, detail="지원하지 않는 지역입니다")

    kw = quote(region["keyword"])
    ci, co, adults = req.check_in, req.check_out, req.adults

    links = [
        {
            "site": "야놀자",
            "category": "숙소",
            "description": f"{region['name']} 숙소 최저가 비교",
            "url": f"https://www.yanolja.com/search?keyword={kw}&checkIn={ci}&checkOut={co}&adultCount={adults}",
        },
        {
            "site": "여기어때",
            "category": "숙소",
            "description": f"{region['name']} 호텔·펜션·모텔 특가",
            "url": f"https://www.goodchoice.kr/product/search?keyword={kw}&startdate={ci}&enddate={co}",
        },
        {
            "site": "네이버 호텔",
            "category": "숙소",
            "description": f"{region['name']} 호텔 가격 비교",
            "url": f"https://hotel.naver.com/hotels/search?destination={kw}&checkin={ci}&checkout={co}&adult={adults}",
        },
        {
            "site": "마이리얼트립",
            "category": "액티비티·체험",
            "description": f"{region['name']} 현지 체험, 투어, 티켓",
            "url": f"https://www.myrealtrip.com/offers?q={kw}",
        },
        {
            "site": "클룩",
            "category": "액티비티·체험",
            "description": f"{region['name']} 투어·액티비티 예약",
            "url": f"https://www.klook.com/ko/search/?query={kw}",
        },
        {
            "site": "아고다",
            "category": "숙소",
            "description": f"{region['name']} 호텔·리조트 특가 (아고다)",
            "url": f"https://www.agoda.com/ko-kr/search?city={kw}&checkIn={ci}&checkOut={co}&adults={adults}",
        },
        {
            "site": "인터파크 투어",
            "category": "패키지",
            "description": f"{region['name']} 국내 여행 패키지",
            "url": f"https://tour.interpark.com/search?keyword={kw}",
        },
        {
            "site": "땡처리닷컴",
            "category": "패키지·특가",
            "description": f"{region['name']} 땡처리 여행 상품 특가",
            "url": f"https://www.ttour.com/search?keyword={kw}",
        },
        {
            "site": "트립닷컴",
            "category": "숙소·패키지",
            "description": f"{region['name']} 호텔·리조트 (Trip.com)",
            "url": f"https://kr.trip.com/hotels/list?city={kw}&checkIn={ci}&checkOut={co}&adult={adults}",
        },
    ]

    return {"region": region["name"], "links": links}


# ── Airline Deals ──

@app.get("/api/airline-deals")
def get_airline_deals():
    return {"airlines": AIRLINE_DEALS}


# ── Trip Planner (AI) ──

class TripPlanRequest(BaseModel):
    destination: str
    start_date: str
    end_date: str
    travelers: str = "성인 2명"
    preferences: str = ""


@app.post("/api/trip/generate")
async def generate_trip_plan(req: TripPlanRequest):
    # 접지: 리포의 정제 데이터(숙박 구역·프로필·교통·달력)에서 이 여행에
    # 해당하는 부분만 골라 프롬프트에 넣는다. 없으면 빈 문자열이라 무해하다.
    context, grounding, n_days = trip_rag.build_context(
        req.destination, req.start_date, req.end_date)
    context_block = ""
    if context:
        context_block = f"""
--- 참고 데이터 (이 서비스가 관리하는 실측·정제 값) ---
{context}
--- 참고 데이터 끝 ---

참고 데이터가 있는 항목(숙소 구역, 교통 요금, 시즌 특성, 요일·공휴일)은 반드시
그 값을 따르세요. 참고 데이터에 없는 가격은 지어내지 말고 "약 15,000원"처럼
어림값임이 드러나게 쓰세요.
"""

    prompt = f"""당신은 한국 여행 전문가입니다. 다음 조건에 맞는 상세한 여행 일정을 만들어주세요.

여행지: {req.destination}
기간: {req.start_date} ~ {req.end_date}
인원: {req.travelers}
{f'선호사항: {req.preferences}' if req.preferences else ''}
{context_block}
반드시 아래 JSON 형식으로만 응답하세요. 다른 텍스트 없이 JSON만 출력하세요:
{{
  "title": "여행 제목",
  "summary": "여행 한줄 요약",
  "days": [
    {{
      "date": "YYYY-MM-DD",
      "label": "DAY 1",
      "theme": "이 날의 테마 (예: 도착 & 해안 드라이브)",
      "items": [
        {{
          "time": "09:00",
          "title": "장소/활동명",
          "category": "관광지|맛집|카페|숙소|이동|체험",
          "description": "상세 설명 (왜 추천하는지, 팁 등)",
          "duration": "약 1시간",
          "cost": "입장료 무료" 또는 "1인 15,000원" 등,
          "address": "대략적 주소나 위치"
        }}
      ],
      "accommodation": {{
        "name": "추천 숙소명",
        "type": "호텔|펜션|리조트|게스트하우스",
        "reason": "추천 이유",
        "price_range": "1박 10~15만원"
      }},
      "tip": "이 날의 여행 팁"
    }}
  ],
  "budget_summary": {{
    "accommodation": "총 숙박비 예상",
    "food": "총 식비 예상",
    "activities": "총 관광/체험비 예상",
    "transport": "총 교통비 예상",
    "total": "총 예상 비용"
  }},
  "packing_tips": ["준비물1", "준비물2"],
  "warnings": ["주의사항1"]
}}

각 날짜별로 아침~저녁까지 시간대별로 빈틈없이 일정을 짜주세요.
동선을 고려해서 효율적으로 배치하고, 맛집은 구체적인 메뉴 추천도 포함하세요.
숙소는 매일 추천해주되, 같은 숙소에 연박하는 것도 괜찮습니다."""

    system_msg = "You are a Korean travel expert. Always respond with valid JSON only. No markdown, no extra text. Use only Korean characters (한글), never use Chinese characters (한자). All text must be in pure Korean."
    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": prompt},
    ]

    # OpenAI 우선 시도, 실패 시 Groq fallback.
    # max_tokens는 일수에 비례 — 고정 6000이면 긴 일정에서 JSON이 잘린다.
    max_tokens = trip_rag.plan_max_tokens(n_days)
    providers = []
    if openai_client:
        providers.append(("openai", openai_client, "gpt-4o-mini"))
    if groq_client:
        providers.append(("groq", groq_client, "llama-3.3-70b-versatile"))

    if not providers:
        raise HTTPException(status_code=500, detail="AI API 키가 설정되지 않았습니다. .env 파일을 확인하세요.")

    loop = asyncio.get_event_loop()
    last_error = None

    for provider_name, client, model in providers:
        try:
            for attempt in range(2):
                # JSON 모드: 두 제공자 모두 지원한다. 코드펜스·잡담이 줄어
                # 파싱 실패로 인한 재시도(비용·지연)가 크게 준다.
                response = await loop.run_in_executor(
                    None,
                    lambda c=client, m=model: c.chat.completions.create(
                        model=m,
                        messages=messages,
                        temperature=0.5,
                        max_tokens=max_tokens,
                        response_format={"type": "json_object"},
                        timeout=90,
                    ),
                )
                plan = trip_rag.salvage_json(response.choices[0].message.content)
                if plan is not None:
                    plan["_provider"] = provider_name
                    plan["_grounding"] = grounding
                    return plan
                if attempt == 0:
                    continue
                last_error = f"{provider_name}: JSON 파싱 실패"
                break
        except Exception as e:
            last_error = f"{provider_name}: {str(e)}"
            print(f"[Trip AI] {provider_name} 실패: {e}")
            continue

    raise HTTPException(status_code=500, detail=f"AI 일정 생성 실패: {last_error}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
