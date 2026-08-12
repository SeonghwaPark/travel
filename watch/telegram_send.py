"""텔레그램 알림 발송 및 메시지 포맷 (night-brief과 동일한 패턴)."""

import requests

API = "https://api.telegram.org/bot{token}/sendMessage"

KO_WD = {"Mon": "월", "Tue": "화", "Wed": "수", "Thu": "목",
         "Fri": "금", "Sat": "토", "Sun": "일"}


def format_alert(watch, best, reasons, booking_url):
    """특가 감지 알림."""
    wd = KO_WD.get(best.get("weekday", ""), best.get("weekday", ""))
    lines = [
        f"✈️ 항공권 특가 — {watch['label']}",
        "",
        f"{watch['origin']} → {watch['dest']}  {best['nights']}박",
        f"{best['dep_date']}({wd}) 출발 · {best['ret_date']} 귀국",
        f"💰 {best['price']:,}원  ({best.get('airline') or '항공사 미상'}"
        + (", 직항" if best.get("stops") == 0 else "")
        + ")",
        "",
    ]
    for r in reasons:
        lines.append(r["text"])
    lines += [
        "",
        f"🔗 예약: {booking_url}",
        "",
        "※ Google Flights 표시가 기준이며 실제 결제가는 예약처에서 확인하세요.",
    ]
    return "\n".join(lines)


def format_deals(new_deals):
    """항공사 프로모션 신규 감지 알림."""
    lines = ["🏷 항공사 특가 페이지에 새 소식", ""]
    for d in new_deals:
        lines.append(f"• [{d['airline']}] {d['title']}")
        lines.append(f"  {d['url']}")
    lines.append("")
    lines.append("※ 페이지 문구 변화 감지 기반이라 실제 특가가 아닐 수 있습니다.")
    return "\n".join(lines)


def send(text: str, token: str, chat_id: str, post=requests.post) -> None:
    resp = post(
        API.format(token=token),
        json={"chat_id": chat_id, "text": text, "disable_web_page_preview": True},
        timeout=20,
    )
    resp.raise_for_status()
