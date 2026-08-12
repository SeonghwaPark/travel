"""알림 판정 규칙.

특가로 볼 조건 4가지 — 하나라도 걸리면 알린다.
  target   : 목표가 이하로 떨어짐
  drop     : 직전 관측 대비 N% 이상 하락
  atl      : 역대 최저가 경신
  discount : 평소 시세(과거 중앙값) 대비 N% 이상 저렴
"""

import statistics


def _median_price(history):
    prices = [r["best_price"] for r in history if r.get("best_price")]
    return statistics.median(prices) if len(prices) >= 3 else None


def evaluate(best_price, history, alert_cfg):
    """알림 사유 목록을 돌려준다. 빈 리스트면 알리지 않는다."""
    if not best_price:
        return []

    reasons = []

    target = alert_cfg.get("target_price")
    if target and best_price <= target:
        reasons.append({
            "type": "target",
            "text": f"🎯 목표가 달성 — {best_price:,}원 (목표 {target:,}원 이하)",
        })

    prev = None
    for rec in reversed(history):
        if rec.get("best_price"):
            prev = rec["best_price"]
            break

    drop_pct = alert_cfg.get("drop_pct")
    if prev and drop_pct:
        change = (prev - best_price) / prev * 100
        if change >= drop_pct:
            reasons.append({
                "type": "drop",
                "text": f"📉 직전 대비 {change:.1f}% 하락 — {prev:,}원 → {best_price:,}원",
            })

    if alert_cfg.get("all_time_low"):
        prices = [r["best_price"] for r in history if r.get("best_price")]
        # 관측이 최소 3회는 쌓여야 '역대 최저'라는 말이 의미가 있다
        if len(prices) >= 3 and best_price < min(prices):
            reasons.append({
                "type": "atl",
                "text": f"🏆 역대 최저가 경신 — 이전 최저 {min(prices):,}원 → {best_price:,}원",
            })

    discount_pct = alert_cfg.get("discount_pct", 15)
    med = _median_price(history)
    if med and discount_pct:
        off = (med - best_price) / med * 100
        if off >= discount_pct:
            reasons.append({
                "type": "discount",
                "text": f"🔥 평소 시세 대비 {off:.0f}% 저렴 — 중앙값 {int(med):,}원 → {best_price:,}원",
            })

    return reasons
