"""알림 판정 규칙.

특가로 볼 조건 5가지 — 하나라도 걸리면 알린다.
  target   : 목표가 이하로 떨어짐
  drop     : 직전 관측 대비 N% 이상 하락
  atl      : 역대 최저가 경신
  discount : 평소 시세(과거 중앙값) 대비 N% 이상 저렴
  baseline : 확정안 실측가보다 싸짐

baseline이 나머지와 다른 점은 기준이 '과거 관측'이 아니라 '내가 사려던 값'이라는
것이다. 이미 일정을 정한 뒤에는 "역대 최저인가"보다 "내가 본 값보다 싼가"가
실질적인 질문이다. 예약 전까지 그 질문에 답하라고 둔다.
"""

import statistics


def _median_price(history):
    prices = [r["best_price"] for r in history if r.get("best_price")]
    return statistics.median(prices) if len(prices) >= 3 else None


def evaluate(best_price, history, alert_cfg, baseline=None):
    """알림 사유 목록을 돌려준다. 빈 리스트면 알리지 않는다.

    baseline: 확정안의 실측가. {"price": N, ...} 형태이며 없으면 이 규칙은 건너뛴다.
    """
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

    base = (baseline or {}).get("price")
    base_pct = alert_cfg.get("baseline_pct", 2)
    if base and best_price < base:
        off = (base - best_price) / base * 100
        if off >= base_pct:
            reasons.append({
                "type": "baseline",
                "text": (f"✅ 확정안({base:,}원)보다 {off:.1f}% 저렴 — "
                         f"{best_price:,}원 · {base - best_price:,}원 절약"),
            })

    return reasons
