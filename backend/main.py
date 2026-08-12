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
import re  # AI 플래너 응답의 코드펜스 제거에 사용
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote
from dotenv import load_dotenv
from openai import OpenAI
from groq import Groq

load_dotenv()
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY")) if os.getenv("OPENAI_API_KEY") else None
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY")) if os.getenv("GROQ_API_KEY") else None

# 스크래핑 코어는 gflights로 분리 — 감시 봇(watch/)도 같은 코드를 쓴다
from gflights import parse_price, search_flights as _search_flights

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

# 감시 봇(watch/deals.py)과 같은 목록을 써야 하므로 리포 루트 airlines.json에서 읽는다
_AIRLINES_JSON = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "airlines.json")
try:
    with open(_AIRLINES_JSON, encoding="utf-8") as _f:
        AIRLINE_DEALS = json.load(_f)
except (OSError, json.JSONDecodeError):
    AIRLINE_DEALS = []

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


# ── Trip Planner (AI) ──

class TripPlanRequest(BaseModel):
    destination: str
    start_date: str
    end_date: str
    travelers: str = "성인 2명"
    preferences: str = ""


@app.post("/api/trip/generate")
async def generate_trip_plan(req: TripPlanRequest):
    prompt = f"""당신은 한국 여행 전문가입니다. 다음 조건에 맞는 상세한 여행 일정을 만들어주세요.

여행지: {req.destination}
기간: {req.start_date} ~ {req.end_date}
인원: {req.travelers}
{f'선호사항: {req.preferences}' if req.preferences else ''}

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

    # OpenAI 우선 시도, 실패 시 Groq fallback
    providers = []
    if openai_client:
        providers.append(("openai", openai_client, "gpt-4o-mini", 6000))
    if groq_client:
        providers.append(("groq", groq_client, "llama-3.3-70b-versatile", 6000))

    if not providers:
        raise HTTPException(status_code=500, detail="AI API 키가 설정되지 않았습니다. .env 파일을 확인하세요.")

    loop = asyncio.get_event_loop()
    last_error = None

    for provider_name, client, model, max_tokens in providers:
        try:
            for attempt in range(2):
                response = await loop.run_in_executor(
                    None,
                    lambda c=client, m=model, mt=max_tokens: c.chat.completions.create(
                        model=m,
                        messages=messages,
                        temperature=0.5,
                        max_tokens=mt,
                    ),
                )
                content = response.choices[0].message.content.strip()

                if content.startswith("```"):
                    content = re.sub(r"^```(?:json)?\s*", "", content)
                    content = re.sub(r"\s*```$", "", content)

                try:
                    plan = json.loads(content)
                    plan["_provider"] = provider_name
                    return plan
                except json.JSONDecodeError:
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
