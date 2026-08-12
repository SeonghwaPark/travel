"""항공사 특가 페이지 감시.

각 페이지의 프로모션 제목 후보를 뽑아 이전 스냅샷과 비교하고, 새로 등장한
항목만 돌려준다.

한계: 항공사 페이지 상당수가 JS로 목록을 그리는 SPA라 정적 HTML만으로는
제목이 안 잡히는 곳이 있다. 잡히는 곳만 best-effort로 감시하고, 실패한
사이트는 조용히 건너뛴다(링크 자체는 알림에 계속 실려 사람이 직접 볼 수 있다).
"""

import json
import os
import re

import primp
from selectolax.lexbor import LexborHTMLParser

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AIRLINES_PATH = os.path.join(REPO_ROOT, "airlines.json")
SNAPSHOT_PATH = os.path.join(REPO_ROOT, "history", "deals_snapshot.json")

IMPERSONATE = "chrome_146"

# 프로모션성 문구로 볼 키워드
KEYWORDS = ("특가", "프로모션", "할인", "이벤트", "세일", "얼리버드", "땡처리", "최대")

# 상시 노출되는 메뉴/버튼 문구는 프로모션이 아니므로 제외
NOISE = ("이벤트 안내", "이벤트 목록", "프로모션 안내", "전체보기", "더보기",
         "이벤트/프로모션", "진행중인 이벤트", "종료된 이벤트")


def load_airlines():
    with open(AIRLINES_PATH, encoding="utf-8") as f:
        return json.load(f)


def _titles(html):
    """페이지에서 프로모션 제목 후보를 추출."""
    parser = LexborHTMLParser(html)
    found = set()
    for sel in ("h1", "h2", "h3", "h4", "a", "li", "strong", "p"):
        for el in parser.css(sel):
            t = (el.text() or "").strip()
            t = re.sub(r"\s+", " ", t)
            if not (6 <= len(t) <= 80):
                continue
            if t in NOISE:
                continue
            if any(k in t for k in KEYWORDS):
                found.add(t)
    return found


def fetch_one(airline):
    try:
        client = primp.Client(impersonate=IMPERSONATE, verify=False, timeout=20)
        res = client.get(airline["url"])
        if res.status_code != 200:
            return None
        return _titles(res.text)
    except Exception:
        return None


def check(verbose=True):
    """새로 등장한 프로모션 항목 목록을 돌려준다."""
    airlines = load_airlines()

    snapshot = {}
    if os.path.exists(SNAPSHOT_PATH):
        try:
            with open(SNAPSHOT_PATH, encoding="utf-8") as f:
                snapshot = json.load(f)
        except json.JSONDecodeError:
            snapshot = {}

    new_deals = []
    updated = dict(snapshot)

    for a in airlines:
        titles = fetch_one(a)
        if titles is None:
            if verbose:
                print(f"  [skip] {a['airline']} — 가져오기 실패/차단")
            continue

        prev = set(snapshot.get(a["airline"], []))
        fresh = titles - prev
        updated[a["airline"]] = sorted(titles)

        if verbose:
            print(f"  [ok]   {a['airline']} — 후보 {len(titles)}건, 신규 {len(fresh)}건")

        # 첫 수집 때는 전부 '신규'라 알림이 폭주하므로 기준선만 만들고 넘어간다
        if not prev:
            continue
        for t in sorted(fresh):
            new_deals.append({"airline": a["airline"], "title": t, "url": a["url"]})

    os.makedirs(os.path.dirname(SNAPSHOT_PATH), exist_ok=True)
    with open(SNAPSHOT_PATH, "w", encoding="utf-8") as f:
        json.dump(updated, f, ensure_ascii=False, indent=2, sort_keys=True)

    return new_deals
