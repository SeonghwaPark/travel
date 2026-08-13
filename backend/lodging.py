"""숙박 예약처 딥링크 생성.

가격을 직접 긁지 않는다 — 아고다·부킹닷컴 등은 상용 봇 차단을 쓰고 약관상
스크래핑을 금지한다. 대신 **조건이 정확히 채워진 검색 링크**를 만들어 준다.

기존 구현은 도시명과 날짜만 넘겨서, 3인 가족이 열어도 2인 기준 결과가 떴다.
인원·객실·아동 나이가 빠지면 검색 결과가 통째로 달라지므로 여기서 전부 채운다.

※ 각 사이트의 쿼리 파라미터는 예고 없이 바뀐다. 링크가 조건을 못 물고 오면
   해당 빌더만 고치면 된다 — 호출부는 그대로 둘 수 있게 분리해 놓았다.
"""

from urllib.parse import quote, urlencode

DEFAULT_CHILD_AGE = 8


def _rooms_for(adults, children):
    """인원에 맞는 최소 객실 수. 대부분의 호텔이 1실 최대 3~4인이다."""
    heads = adults + children
    if heads <= 3:
        return 1
    return (heads + 2) // 3


def _child_ages(children, child_ages):
    if child_ages:
        return list(child_ages)[:children]
    return [DEFAULT_CHILD_AGE] * children


def booking_com(place, check_in, check_out, adults, children, child_ages, rooms):
    q = [
        ("ss", place),
        ("checkin", check_in),
        ("checkout", check_out),
        ("group_adults", adults),
        ("group_children", children),
        ("no_rooms", rooms),
        ("selected_currency", "KRW"),
    ]
    # 아동은 나이마다 age 파라미터가 하나씩 붙는다
    q += [("age", a) for a in child_ages]
    return "https://www.booking.com/searchresults.ko.html?" + urlencode(q)


def agoda(place, check_in, check_out, adults, children, child_ages, rooms):
    q = {
        "textToSearch": place,
        "checkIn": check_in,
        "checkOut": check_out,
        "adults": adults,
        "children": children,
        "rooms": rooms,
        "currency": "KRW",
    }
    if children:
        q["childAges"] = ",".join(str(a) for a in child_ages)
    return "https://www.agoda.com/ko-kr/search?" + urlencode(q)


def hotels_com(place, check_in, check_out, adults, children, child_ages, rooms):
    # Expedia 계열은 아동을 "나이" 목록으로 받는다
    q = {
        "destination": place,
        "startDate": check_in,
        "endDate": check_out,
        "adults": adults,
        "rooms": rooms,
    }
    if children:
        q["children"] = ",".join(str(a) for a in child_ages)
    return "https://kr.hotels.com/Hotel-Search?" + urlencode(q)


def trip_com(place, check_in, check_out, adults, children, child_ages, rooms):
    q = {
        "city": place,
        "checkin": check_in.replace("-", ""),
        "checkout": check_out.replace("-", ""),
        "adult": adults,
        "children": children,
        "crn": rooms,
        "curr": "KRW",
    }
    if children:
        q["childrenAges"] = ",".join(str(a) for a in child_ages)
    return "https://kr.trip.com/hotels/list?" + urlencode(q)


def airbnb(place, check_in, check_out, adults, children, child_ages, rooms):
    q = {
        "checkin": check_in,
        "checkout": check_out,
        "adults": adults,
        "children": children,
    }
    return f"https://www.airbnb.co.kr/s/{quote(place)}/homes?" + urlencode(q)


def naver_hotel(place, check_in, check_out, adults, children, child_ages, rooms):
    q = {
        "destination": place,
        "checkIn": check_in,
        "checkOut": check_out,
        "adultCnt": adults,
    }
    return "https://hotel.naver.com/hotels/search?" + urlencode(q)


def google_hotels(place, check_in, check_out, adults, children, child_ages, rooms):
    """여러 예약처 가격을 한 화면에 모아 보여준다 — 비교 시작점으로 좋다."""
    q = {"q": f"{place} 호텔", "hl": "ko", "gl": "kr", "curr": "KRW"}
    return "https://www.google.com/travel/search?" + urlencode(q)


# 표시 순서 = 이 목록 순서. 구글은 비교용이라 맨 앞에 둔다.
PROVIDERS = [
    ("google_hotels", "Google 호텔 (가격 비교)", google_hotels,
     "여러 예약처 가격을 한 화면에서 비교"),
    ("booking", "Booking.com", booking_com, "전 세계 최대 규모, 무료 취소 옵션 많음"),
    ("agoda", "Agoda", agoda, "아시아 지역에 강함"),
    ("hotels", "Hotels.com", hotels_com, "10박 적립 리워드"),
    ("trip", "Trip.com", trip_com, "아시아 노선·호텔 프로모션 잦음"),
    ("airbnb", "Airbnb", airbnb, "가족 단위 아파트·주택. 주방 필요하면 유리"),
    ("naver", "네이버 호텔", naver_hotel, "국내 결제·리뷰 확인 편함"),
]


def search_links(place, check_in, check_out, adults=2, children=0,
                 child_ages=None, rooms=None):
    """예약처별 검색 링크. place는 도시명 등 자유 문자열."""
    children = max(0, int(children))
    adults = max(1, int(adults))
    ages = _child_ages(children, child_ages)
    rooms = int(rooms) if rooms else _rooms_for(adults, children)

    out = []
    for key, name, builder, note in PROVIDERS:
        out.append({
            "provider": key,
            "name": name,
            "note": note,
            "url": builder(place, check_in, check_out, adults, children, ages, rooms),
        })
    return {
        "place": place,
        "check_in": check_in,
        "check_out": check_out,
        "adults": adults,
        "children": children,
        "child_ages": ages,
        "rooms": rooms,
        "links": out,
    }
