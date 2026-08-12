"""항공권 특가 감시 봇 엔트리포인트.

watchlist.json의 감시 대상을 훑어 최저가를 구하고, 이전 관측과 비교해
특가로 판단되면 텔레그램으로 알린다. 항공사 프로모션 페이지도 함께 확인한다.

    python -m watch.main            # 정상 실행 (알림 발송)
    python -m watch.main --dry-run  # 조회/판정만, 발송·저장 안 함
    python -m watch.main --only sapporo-feb2027
    python -m watch.main --skip-deals
"""

import argparse
import os
import sys
from datetime import datetime, timedelta
from urllib.parse import quote

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))

import gflights  # noqa: E402

from . import config, deals, rules, store, telegram_send  # noqa: E402


def booking_url(origin, dest, dep_date, ret_date, adults, children, infants):
    """Google Flights 자연어 쿼리 URL (예약처로 바로 연결)."""
    q = f"Flights to {dest} from {origin} on {dep_date} through {ret_date}"
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


def _combos(watch):
    """조회할 (출발일, 박수) 목록. max_queries를 넘으면 균등 간격으로 솎는다."""
    start = datetime.strptime(watch["date_from"], "%Y-%m-%d")
    end = datetime.strptime(watch["date_to"], "%Y-%m-%d")
    step = max(1, int(watch.get("step", 1)))

    dates, d = [], start
    while d <= end:
        dates.append(d.strftime("%Y-%m-%d"))
        d += timedelta(days=step)

    combos = [(dt, n) for dt in dates for n in watch["nights"]]

    cap = int(watch.get("max_queries", 40))
    if len(combos) > cap:
        stride = len(combos) / cap
        combos = [combos[int(i * stride)] for i in range(cap)]
    return combos


def scan_watch(watch, verbose=True):
    """감시 대상 하나를 훑어 최저가 1건을 돌려준다."""
    combos = _combos(watch)
    if verbose:
        print(f"\n▶ {watch['label']} ({watch['origin']}→{watch['dest']}) — {len(combos)}건 조회")

    best = None
    for dep_date, nights in combos:
        ret_date = (datetime.strptime(dep_date, "%Y-%m-%d")
                    + timedelta(days=nights)).strftime("%Y-%m-%d")
        found = gflights.cheapest(
            watch["origin"], watch["dest"], dep_date, ret_date,
            adults=watch["adults"], children=watch["children"],
            infants_in_seat=0, infants_on_lap=watch["infants"],
            attempts=2, retry_sleep=1.5, quiet=True,
        )
        if not found:
            continue
        if best is None or found["price"] < best["price"]:
            best = {
                **found,
                "dep_date": dep_date,
                "ret_date": ret_date,
                "nights": nights,
                "weekday": datetime.strptime(dep_date, "%Y-%m-%d").strftime("%a"),
            }
            if verbose:
                print(f"  최저 갱신: {dep_date} {nights}박 {found['price']:,}원 {found['airline']}")

    return best


def run():
    ap = argparse.ArgumentParser(description="항공권 특가 감시 봇")
    ap.add_argument("--dry-run", action="store_true", help="발송·저장 없이 판정만")
    ap.add_argument("--only", default="", help="특정 watch id만 실행")
    # 기본 꺼짐: 항공사 프로모션 페이지 대부분이 SPA/차단이라 신호가 거의 없다.
    # 실제 특가는 가격 자체가 떨어져 drop/discount 규칙에 잡히는 쪽이 확실하다.
    ap.add_argument("--with-deals", action="store_true",
                    help="항공사 프로모션 페이지도 확인 (best-effort, 대부분 미탐지)")
    ap.add_argument("--skip-deals", action="store_true",
                    help=argparse.SUPPRESS)  # 하위 호환
    ap.add_argument("--watchlist", default=None)
    args = ap.parse_args()

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    can_send = bool(token and chat_id) and not args.dry_run
    if not can_send:
        why = "--dry-run" if args.dry_run else "TELEGRAM_BOT_TOKEN/CHAT_ID 없음"
        print(f"[알림 발송 안 함: {why}]")

    watches = config.load(args.watchlist)
    if args.only:
        watches = [w for w in watches if w["id"] == args.only]
        if not watches:
            raise SystemExit(f"watch id를 찾지 못함: {args.only}")

    alerted = 0
    for w in watches:
        best = scan_watch(w)
        history = store.load(w["id"])

        if not best:
            print(f"  결과 없음 — 건너뜀 ({w['id']})")
            continue

        reasons = rules.evaluate(best["price"], history, w["alert"])
        med_note = f" (관측 {len(history)}회 누적)" if history else " (첫 관측 — 기준선 생성)"
        print(f"  최저가 {best['price']:,}원{med_note}, 알림사유 {len(reasons)}건")

        record = {
            "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "best_price": best["price"],
            "dep_date": best["dep_date"],
            "ret_date": best["ret_date"],
            "nights": best["nights"],
            "airline": best["airline"],
            "reasons": [r["type"] for r in reasons],
        }
        if not args.dry_run:
            store.append(w["id"], record)

        if reasons:
            url = booking_url(w["origin"], w["dest"], best["dep_date"], best["ret_date"],
                              w["adults"], w["children"], w["infants"])
            msg = telegram_send.format_alert(w, best, reasons, url)
            print("---- 알림 ----")
            print(msg)
            print("--------------")
            if can_send:
                telegram_send.send(msg, token, chat_id)
                alerted += 1

    if args.with_deals and not args.skip_deals:
        print("\n▶ 항공사 특가 페이지 확인")
        new_deals = deals.check()
        if new_deals:
            msg = telegram_send.format_deals(new_deals)
            print("---- 알림 ----")
            print(msg)
            print("--------------")
            if can_send:
                telegram_send.send(msg, token, chat_id)
                alerted += 1
        else:
            print("  신규 프로모션 없음")

    print(f"\n완료 — 발송 {alerted}건")


if __name__ == "__main__":
    run()
