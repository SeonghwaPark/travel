import sys, io
if sys.stdout and hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr and hasattr(sys.stderr, 'buffer'):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fast_flights import FlightData, Passengers, TFSData
from selectolax.lexbor import LexborHTMLParser
import primp
import asyncio
import re
import threading
import time as _time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote

# Google 요청 간 최소 간격 (rate limiting 방지)
_fetch_lock = threading.Lock()
_last_fetch_time = 0.0
_FETCH_INTERVAL = 1.5  # 최소 1.5초 간격

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


class HotelSearchRequest(BaseModel):
    destination: str
    check_in: str
    check_out: str
    adults: int = 1


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

AIRLINE_DEALS = [
    {
        "airline": "대한항공",
        "logo": "KE",
        "description": "대한항공 공식 특가 이벤트 및 프로모션",
        "url": "https://www.koreanair.com/content/koreanair/kr/ko/offers/promotions.html",
    },
    {
        "airline": "아시아나항공",
        "logo": "OZ",
        "description": "아시아나항공 특가 이벤트 및 얼리버드",
        "url": "https://flyasiana.com/C/KR/KO/event/eventList",
    },
    {
        "airline": "진에어",
        "logo": "LJ",
        "description": "진에어 특가 & 프로모션 이벤트",
        "url": "https://www.jinair.com/promotion/list",
    },
    {
        "airline": "제주항공",
        "logo": "7C",
        "description": "제주항공 땡처리 특가 이벤트",
        "url": "https://www.jejuair.net/ko/promotion",
    },
    {
        "airline": "티웨이항공",
        "logo": "TW",
        "description": "티웨이항공 특가 & 이벤트",
        "url": "https://www.twayair.com/app/promotionEvents/promotionEventsList",
    },
    {
        "airline": "에어부산",
        "logo": "BX",
        "description": "에어부산 특가 프로모션",
        "url": "https://www.airbusan.com/promotion/list",
    },
    {
        "airline": "에어서울",
        "logo": "RS",
        "description": "에어서울 특가 이벤트",
        "url": "https://www.airseoul.com/promotion",
    },
    {
        "airline": "에어프레미아",
        "logo": "YP",
        "description": "에어프레미아 특가 & 프로모션",
        "url": "https://www.airpremia.com/promotion",
    },
    {
        "airline": "땡처리닷컴",
        "logo": "땡",
        "description": "항공권·여행 땡처리 특가 모음",
        "url": "https://www.ttour.com/flight",
    },
    {
        "airline": "스카이스캐너",
        "logo": "SK",
        "description": "전 세계 항공사 최저가 비교",
        "url": "https://www.skyscanner.co.kr/flights",
    },
    {
        "airline": "클룩",
        "logo": "KL",
        "description": "항공권·패스·체험 특가 이벤트",
        "url": "https://www.klook.com/ko/flights/",
    },
]

KOREAN_AIRPORTS = {
    "ICN": "인천국제공항",
    "GMP": "김포국제공항",
    "PUS": "김해국제공항",
    "CJU": "제주국제공항",
    "TAE": "대구국제공항",
}

DOMESTIC_DESTINATIONS = {
    "CJU": {"name": "제주",       "country": "국내"},
    "PUS": {"name": "부산 (김해)", "country": "국내"},
    "TAE": {"name": "대구",       "country": "국내"},
    "RSU": {"name": "여수",       "country": "국내"},
    "KWJ": {"name": "광주",       "country": "국내"},
    "CJJ": {"name": "청주",       "country": "국내"},
    "YNY": {"name": "양양",       "country": "국내"},
    "KPO": {"name": "포항 (경주)", "country": "국내"},
    "USN": {"name": "울산",       "country": "국내"},
    "MWX": {"name": "무안",       "country": "국내"},
    "HIN": {"name": "진주 (사천)", "country": "국내"},
    "WJU": {"name": "원주",       "country": "국내"},
}

POPULAR_DESTINATIONS = {
    "NRT": {"name": "도쿄 나리타", "country": "일본"},
    "KIX": {"name": "오사카 간사이", "country": "일본"},
    "FUK": {"name": "후쿠오카", "country": "일본"},
    "BKK": {"name": "방콕", "country": "태국"},
    "SIN": {"name": "싱가포르", "country": "싱가포르"},
    "HKG": {"name": "홍콩", "country": "홍콩"},
    "TPE": {"name": "타이베이", "country": "대만"},
    "DAD": {"name": "다낭", "country": "베트남"},
    "SGN": {"name": "호치민", "country": "베트남"},
    "HAN": {"name": "하노이", "country": "베트남"},
    "MNL": {"name": "마닐라", "country": "필리핀"},
    "CEB": {"name": "세부", "country": "필리핀"},
    "DPS": {"name": "발리", "country": "인도네시아"},
    "KUL": {"name": "쿠알라룸푸르", "country": "말레이시아"},
    "PNH": {"name": "프놈펜", "country": "캄보디아"},
    "REP": {"name": "시엠립", "country": "캄보디아"},
    "LAX": {"name": "로스앤젤레스", "country": "미국"},
    "JFK": {"name": "뉴욕", "country": "미국"},
    "SFO": {"name": "샌프란시스코", "country": "미국"},
    "CDG": {"name": "파리", "country": "프랑스"},
    "LHR": {"name": "런던", "country": "영국"},
    "FCO": {"name": "로마", "country": "이탈리아"},
    "BCN": {"name": "바르셀로나", "country": "스페인"},
    "SYD": {"name": "시드니", "country": "호주"},
    "GUM": {"name": "괌", "country": "미국"},
}


# ── Helpers ──

def parse_price(price_str):
    """'₩129,100' -> 129100"""
    if price_str is None:
        return None
    if isinstance(price_str, (int, float)):
        return int(price_str)
    price_str = str(price_str)
    nums = re.sub(r"[^\d]", "", price_str)
    return int(nums) if nums else None



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


def _parse_aria_label(label):
    """aria-label에서 항공편 정보 추출"""
    info = {"name": "", "price": "", "departure": "", "arrival": "",
            "duration": "", "stops": 0}

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


def _search_flights(origin, destination, departure_date, return_date, adults,
                     children=0, infants_in_seat=0, infants_on_lap=0):
    """Google Flights에서 항공편 검색 (aria-label 파싱, 최대 3회 재시도)"""
    from datetime import datetime, timedelta
    import time

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

    # 최대 5회 시도, 매번 새 클라이언트로 요청
    for attempt in range(5):
        try:
            # Rate limiting: 요청 간 최소 간격 유지
            global _last_fetch_time
            with _fetch_lock:
                now = _time.time()
                wait = _FETCH_INTERVAL - (now - _last_fetch_time)
                if wait > 0:
                    _time.sleep(wait)
                _last_fetch_time = _time.time()

            client = primp.Client(impersonate="chrome_131", verify=False)
            res = client.get("https://www.google.com/travel/flights", params=params)
            if res.status_code != 200:
                print(f"[HTTP {res.status_code}] {origin}->{destination} 시도 {attempt+1}/5")
                time.sleep(2)
                continue

            parser = LexborHTMLParser(res.text)

            flights = []
            for el in parser.css("div.JMc5Xc"):
                label = el.attributes.get("aria-label", "")
                if not label or "Select flight" not in label:
                    continue
                info = _parse_aria_label(label)
                if info["price"]:
                    flights.append(info)

            if flights:
                try:
                    print(f"[OK] {origin}->{destination} | {len(flights)} flights | "
                          f"top: {flights[0]['name'] or 'N/A'} {flights[0]['price']}won")
                except Exception:
                    pass
                return flights
            else:
                try:
                    print(f"[EMPTY] {origin}->{destination} attempt {attempt+1}/5 (Loading)")
                except Exception:
                    pass
        except Exception as e:
            try:
                print(f"[FAIL] {origin}->{destination} attempt {attempt+1}/5: {e}")
            except Exception:
                pass
        time.sleep(2)

    return []


# ── Airports ──

@app.get("/api/airports")
def get_airports_endpoint():
    return {
        "origins": KOREAN_AIRPORTS,
        "destinations": POPULAR_DESTINATIONS,
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


# ── Hotels (외부 링크) ──

@app.post("/api/hotels/search")
def search_hotels(req: HotelSearchRequest):
    dest_info = POPULAR_DESTINATIONS.get(req.destination)
    if not dest_info:
        raise HTTPException(status_code=400, detail="지원하지 않는 목적지입니다")

    dest_name = dest_info["name"].split()[0]
    hotels = [
        {
            "name": f"{dest_name} 호텔 검색 (네이버 호텔)",
            "hotel_id": "naver",
            "rating": None,
            "price": {"total": "0", "currency": ""},
            "room_type": "",
            "bed_type": "",
            "description": f"{dest_info['country']} {dest_name} 지역 호텔 가격 비교",
            "check_in": req.check_in,
            "check_out": req.check_out,
            "booking_link": f"https://hotel.naver.com/hotels/search?destination={quote(dest_name)}&checkin={req.check_in}&checkout={req.check_out}",
        },
        {
            "name": f"{dest_name} 호텔 검색 (Booking.com)",
            "hotel_id": "booking",
            "rating": None,
            "price": {"total": "0", "currency": ""},
            "room_type": "",
            "bed_type": "",
            "description": f"전 세계 최대 호텔 예약 사이트에서 {dest_name} 숙소 검색",
            "check_in": req.check_in,
            "check_out": req.check_out,
            "booking_link": f"https://www.booking.com/searchresults.ko.html?ss={quote(dest_name)}&checkin={req.check_in}&checkout={req.check_out}",
        },
        {
            "name": f"{dest_name} 호텔 검색 (Agoda)",
            "hotel_id": "agoda",
            "rating": None,
            "price": {"total": "0", "currency": ""},
            "room_type": "",
            "bed_type": "",
            "description": f"아시아 특화 호텔 예약, {dest_name} 최저가 검색",
            "check_in": req.check_in,
            "check_out": req.check_out,
            "booking_link": f"https://www.agoda.com/ko-kr/search?city={quote(dest_name)}&checkIn={req.check_in}&checkOut={req.check_out}",
        },
    ]

    return {"count": len(hotels), "hotels": hotels}


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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
