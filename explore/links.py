"""탐색 결과에서 다음 행동으로 바로 넘어가는 바로가기.

탐색 결과표는 "어디가 싸다"까지만 답한다. 거기서 실제로 예약하거나 더 파고들려면
예약처마다 조건을 손으로 다시 넣어야 했다. 두세 번 하면 지쳐서 탐색이 멈춘다.

그래서 항공권을 요소(노선·날짜·인원)로 분해해 각 요소에 맞는 링크와 명령어를
미리 만들어 붙인다. 마찰이 사라지면 탐색을 열 단계 스무 단계 이어가도 지치지 않는다.

세 가지를 붙인다.
  1. 예약처 3사 — 같은 조건이라도 표시가가 다르다. 한 곳만 보면 손해다.
  2. 인원 분할 — 2명 검색가 ≠ 1명 검색가 × 2. 좌석 재고 버킷이 인원마다 달라
     쪼개 예약하는 쪽이 쌀 때가 있다.
  3. 다음 탐색 명령 — 이 목적지만 정밀 스캔하거나 감시에 등록하는 명령어.

URL 형식은 예약처가 바꿀 수 있는 best-effort다. 깨지면 링크만 못 쓰고
결과표 자체는 멀쩡하다.
"""

from urllib.parse import quote

# 바로가기를 붙일 상위 목적지 수. 전부 붙이면 표보다 링크가 길어진다.
TOP_DESTINATIONS = 5


def _yymmdd(date_str):
    """2027-02-17 → 270217 (스카이스캐너 형식)."""
    y, m, d = date_str.split("-")
    return f"{y[2:]}{m}{d}"


def _compact(date_str):
    """2027-02-17 → 20270217 (네이버 형식)."""
    return date_str.replace("-", "")


def google_flights(origin, dest, dep, ret, adults, children, infants):
    """자연어 쿼리 방식. 구글이 UI를 바꿔도 이 형식은 오래 버텼다."""
    q = f"Flights to {dest} from {origin} on {dep} through {ret}"
    pax = []
    if adults > 1:
        pax.append(f"{adults} adults")
    if children > 0:
        pax.append(f"{children} children")
    if infants > 0:
        pax.append(f"{infants} infants")
    if pax:
        q += " " + " ".join(pax)
    return f"https://www.google.com/travel/flights?q={quote(q)}&curr=KRW&hl=ko"


def skyscanner(origin, dest, dep, ret, adults, children, infants):
    url = (f"https://www.skyscanner.co.kr/transport/flights/"
           f"{origin.lower()}/{dest.lower()}/{_yymmdd(dep)}/{_yymmdd(ret)}/"
           f"?adults={adults}&cabinclass=economy")
    if children:
        url += f"&children={children}"
    if infants:
        url += f"&infants={infants}"
    return url


def naver(origin, dest, dep, ret, adults, children, infants):
    return (f"https://flight.naver.com/flights/international/"
            f"{origin}-{dest}-{_compact(dep)}/{dest}-{origin}-{_compact(ret)}"
            f"?adult={adults}&child={children}&infant={infants}")


def vendor_links(origin, dest, dep, ret, adults, children, infants):
    """예약처 3사 링크. 같은 조건이라도 표시가가 다르다."""
    args = (origin, dest, dep, ret, adults, children, infants)
    return [
        ("구글 플라이트", google_flights(*args)),
        ("스카이스캐너", skyscanner(*args)),
        ("네이버 항공권", naver(*args)),
    ]


def split_links(origin, dest, dep, ret, adults, children, infants):
    """인원을 쪼개 조회하는 링크.

    합계 인원으로 검색하면 그 인원을 한 번에 태울 수 있는 운임 버킷만 잡혀
    비싸질 수 있다. 1인 검색가 × 인원수가 더 싸면 따로 예약하는 게 맞다.
    승객이 1명뿐이면 쪼갤 게 없으므로 빈 리스트.
    """
    if adults + children + infants <= 1:
        return []
    out = [("성인 1명만", google_flights(origin, dest, dep, ret, 1, 0, 0))]
    if children:
        out.append(("성인 1 + 소아 1",
                    google_flights(origin, dest, dep, ret, 1, 1, 0)))
    return out


def next_commands(meta, dest_code, dep, ret, nights):
    """이 목적지를 더 파고드는 명령어."""
    pax = (f"--adults {meta['adults']} --children {meta['children']} "
           f"--infants {meta['infants']}")
    return [
        ("항공사·시간까지 정밀 스캔",
         f"cd backend && python scan_cheapest.py --dest {dest_code} "
         f"--start {meta['start']} --end {meta['end']} "
         f"--nights {nights} --step 1 {pax} --tag {dest_code.lower()}"),
        ("이 목적지만 다시 탐색 (날짜 곡선 갱신)",
         f"python -m explore.main --start {meta['start']} --end {meta['end']} "
         f"--nights {','.join(str(n) for n in meta['nights'])} "
         f"{pax} --only {dest_code}"),
        ("숙박 견적 링크 받기",
         f"python -m brief.quote links --dest {dest_code} "
         f"--check-in {dep} --check-out {ret} "
         f"--adults {meta['adults']} --children {meta['children']}"),
    ]


def to_markdown(result, top=TOP_DESTINATIONS):
    """결과 마크다운 뒤에 붙일 바로가기 섹션."""
    ranking = result.get("ranking", [])
    if not ranking:
        return ""

    m = result["meta"]
    origin = m["origin"]
    adults, children, infants = m["adults"], m["children"], m["infants"]

    lines = ["---", "", f"## 🔗 탐색 바로가기 (상위 {min(top, len(ranking))}곳)", "",
             "> 조건이 채워진 링크다. 예약처마다 표시가가 다르니 최소 두 곳은 비교한다.", ""]

    for r in ranking[:top]:
        dep, ret = r["departure_date"], r["return_date"]
        lines += [
            f"### {r['name']} ({r['code']}) — {r['best_price']:,}원 · {dep} ~ {ret} · {r['nights']}박",
            "",
        ]

        vendors = vendor_links(origin, r["code"], dep, ret, adults, children, infants)
        lines.append("**예약처 비교** — " + " · ".join(f"[{n}]({u})" for n, u in vendors))
        lines.append("")

        splits = split_links(origin, r["code"], dep, ret, adults, children, infants)
        if splits:
            lines.append("**인원 쪼개 보기** — " + " · ".join(f"[{n}]({u})" for n, u in splits))
            lines.append(
                f"> 합계 {adults + children}명 검색가와 1인 검색가 × {adults + children}을 비교한다. "
                "1인 쪽이 싸면 따로 예약하는 게 맞다.")
            lines.append("")

        lines.append("**다음 탐색**")
        lines.append("")
        lines.append("```bash")
        for label, cmd in next_commands(m, r["code"], dep, ret, r["nights"]):
            lines.append(f"# {label}")
            lines.append(cmd)
        lines.append("```")
        lines.append("")

    return "\n".join(lines)
