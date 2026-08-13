"""Google 호텔 가격 조회 (헤드리스 브라우저).

가격이 최초 HTML에 안 실린다 — 화면 골격만 오고 요금은 렌더링 후 채워진다.
(backend/_probe_hotels.py로 확인: HTTP 200, 본문 2.8MB, '1박' 80회, 가격 0개)
그래서 항공권처럼 HTTP 한 방으로는 안 되고 브라우저로 렌더링해야 한다.

숙박은 항공권과 달리 161일치를 훑을 필요가 없다. "이 동네 이 날짜 3인 얼마"만
알면 되므로 느려도 된다 — 구역 하나당 수 초면 충분하다.

파싱은 parse_cards()로 분리해 뒀다. 브라우저 없이 테스트할 수 있어야 하고,
구글이 화면 구조를 바꾸면 여기만 고치면 된다.
"""

import re

# 페이지에서 긁어온 텍스트 덩어리에서 가격을 찾는다.
# 한국어 로케일 기준: "₩123,456" 또는 "123,456원"
_PRICE = re.compile(r"₩\s?([\d,]{4,})|([\d,]{4,})\s?원")
_RATING = re.compile(r"\b([1-5]\.\d)\b")


def parse_price(text):
    """텍스트에서 첫 번째 가격을 원 단위 정수로. 없으면 None."""
    m = _PRICE.search(text or "")
    if not m:
        return None
    raw = m.group(1) or m.group(2)
    digits = raw.replace(",", "")
    return int(digits) if digits.isdigit() else None


def parse_cards(cards):
    """카드 텍스트 목록 -> 숙소 정보 목록.

    cards: 화면에서 긁은 카드별 텍스트. 첫 줄을 이름으로 본다.
    가격이 없는 카드(광고·안내문 등)는 버린다.
    """
    out = []
    for text in cards:
        if not text:
            continue
        price = parse_price(text)
        if price is None:
            continue
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        if not lines:
            continue
        rating = None
        m = _RATING.search(text)
        if m:
            rating = float(m.group(1))
        out.append({"name": lines[0][:80], "price_per_night": price, "rating": rating})
    return out


def summarize(hotels, top=5):
    """구역 하나의 가격 요약. 결과가 없으면 None."""
    prices = sorted(h["price_per_night"] for h in hotels)
    if not prices:
        return None
    mid = len(prices) // 2
    median = prices[mid] if len(prices) % 2 else (prices[mid - 1] + prices[mid]) // 2
    return {
        "count": len(prices),
        "min_per_night": prices[0],
        "median_per_night": median,
        "samples": sorted(hotels, key=lambda h: h["price_per_night"])[:top],
    }


# ── 브라우저 조회 (네트워크 필요) ──

SEARCH_URL = "https://www.google.com/travel/search"


def _query(place, check_in, check_out, adults, children):
    """자연어 질의. Google 여행 검색이 날짜·인원을 문장에서 읽어낸다."""
    q = f"{place} 호텔 {check_in} ~ {check_out}"
    who = f" 성인 {adults}명"
    if children:
        who += f" 어린이 {children}명"
    return q + who


def fetch(place, check_in, check_out, adults=2, children=0,
          timeout_ms=45000, max_cards=40, headless=True, debug=False):
    """구역 하나의 숙소 가격을 긁는다. 실패하면 빈 리스트.

    Playwright가 없거나 브라우저를 못 띄우면 ImportError/RuntimeError가 아니라
    빈 결과를 돌려준다 — 호출부(스캐너)가 한 구역 실패로 통째로 죽지 않게.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[ghotels] playwright가 설치되지 않았습니다")
        return []

    q = _query(place, check_in, check_out, adults, children)
    params = f"?q={q}&hl=ko&gl=kr&curr=KRW"

    cards, page_dates = [], None
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=headless)
            ctx = browser.new_context(
                locale="ko-KR",
                viewport={"width": 1400, "height": 1000},
            )
            page = ctx.new_page()
            page.goto(SEARCH_URL + params, timeout=timeout_ms,
                      wait_until="domcontentloaded")

            # 가격이 렌더링될 때까지 기다린다. 안 나오면 그대로 진행해
            # 무엇이 보였는지라도 남긴다.
            try:
                page.wait_for_selector("text=/₩\\s?[\\d,]{4,}/", timeout=timeout_ms)
            except Exception:
                print("[ghotels] 가격 요소를 기다리다 시간 초과")

            body = page.inner_text("body")
            m = re.search(r"\d{1,2}월\s?\d{1,2}일\s?[–~-]\s?\d{1,2}월\s?\d{1,2}일", body)
            if m:
                page_dates = m.group(0)

            # 숙소 카드는 링크 단위로 묶여 있다. 구조가 바뀔 수 있어
            # 선택자를 여러 개 시도한다.
            for sel in ("div[jsname] a[href*='/travel/'] >> xpath=ancestor::div[1]",
                        "c-wiz div[role='link']",
                        "div[role='link']",
                        "a[href*='/travel/search'] >> xpath=ancestor::div[2]"):
                try:
                    els = page.query_selector_all(sel)
                except Exception:
                    continue
                if len(els) >= 3:
                    cards = [e.inner_text() for e in els[:max_cards]]
                    if debug:
                        print(f"[ghotels] 선택자 적중: {sel} ({len(els)}개)")
                    break

            if not cards:
                # 최후 수단: 본문을 줄 단위로 잘라 가격이 있는 덩어리만 본다
                chunks = re.split(r"\n{2,}", body)
                cards = [c for c in chunks if _PRICE.search(c)][:max_cards]
                if debug:
                    print(f"[ghotels] 폴백 분할 사용 ({len(cards)}개)")

            browser.close()
    except Exception as e:
        print(f"[ghotels] 조회 실패 ({place}): {e}")
        return []

    hotels = parse_cards(cards)
    print(f"[ghotels] {place}: 카드 {len(cards)}개 → 가격 {len(hotels)}건"
          + (f" | 페이지 날짜: {page_dates}" if page_dates else ""))
    return hotels
