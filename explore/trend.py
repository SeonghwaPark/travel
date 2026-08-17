"""탐색 결과를 시계열로 쌓고, "이 가격이 싼가"에 답한다.

explore/results/<tag>.json은 매 실행마다 덮어써서 마지막 결과만 남는다. 그래서
같은 조건을 한 달 뒤 다시 돌려도 "지난번보다 싼가"를 알 수 없었다. 여기서는
실행마다 한 줄씩 explore/history/<tag>.jsonl에 append해 그 질문에 답한다.

비교 가능성은 tag가 보장한다 — tag에 출발지·기간·박수·인원이 전부 들어 있으므로
같은 파일에 쌓인 기록끼리는 조건이 같다. 조건이 다르면 파일이 갈린다.
(인원이 다른 스캔을 섞으면 소아 요금 때문에 비교가 거짓이 된다.)

순수 함수 + 파일 IO만 둔다. 네트워크 없이 테스트할 수 있어야 한다.
"""

import json
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HISTORY_DIR = os.path.join(_ROOT, "explore", "history")

# 관측이 이만큼은 쌓여야 '추세'나 '역대'라는 말이 의미가 있다.
MIN_FOR_RANGE = 2
MIN_FOR_TREND = 3
# 추세 판정 문턱 — 관측 1회당 평균 변화율(%)이 이보다 작으면 횡보로 본다.
TREND_EPS = 1.0
# 추세를 볼 때 참고할 최근 관측 수. 오래된 값까지 넣으면 기울기가 둔해진다.
TREND_WINDOW = 5


def history_path(tag):
    return os.path.join(HISTORY_DIR, f"{tag}.jsonl")


def snapshot(result):
    """스캔 결과 하나를 기록용 한 줄로 압축한다.

    목적지별로 최저가와 그 날짜만 남긴다. 날짜 곡선 전체는 results JSON에 있고
    여기까지 넣으면 파일이 급격히 커진다.
    """
    return {
        "at": result["meta"]["scanned_at"],
        "dests": {
            r["code"]: {
                "best_price": r["best_price"],
                "per_person": r["per_person"],
                "median_price": r["median_price"],
                "departure_date": r["departure_date"],
                "return_date": r["return_date"],
                "nights": r["nights"],
            }
            for r in result.get("ranking", [])
        },
    }


def append(tag, result):
    """이번 스캔을 이력에 덧붙인다. 기록할 게 없으면 아무것도 안 한다."""
    snap = snapshot(result)
    if not snap["dests"]:
        return None
    os.makedirs(HISTORY_DIR, exist_ok=True)
    path = history_path(tag)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(snap, ensure_ascii=False) + "\n")
    return path


def load(tag):
    """이력을 오래된 순으로 읽는다. 없으면 빈 리스트."""
    path = history_path(tag)
    if not os.path.exists(path):
        return []
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                # 실행이 중간에 끊겨 줄이 깨졌을 수 있다. 한 줄 버리고 계속한다.
                continue
    return records


def series(records, dest_code):
    """한 목적지의 최저가 시계열. [(관측시각, 가격), ...] 오래된 순."""
    out = []
    for rec in records:
        d = rec.get("dests", {}).get(dest_code)
        if d and d.get("best_price"):
            out.append((rec.get("at", ""), d["best_price"]))
    return out


def _slope_pct(prices):
    """관측 1회당 평균 변화율(%). 최소제곱 기울기를 평균가로 정규화한다."""
    n = len(prices)
    mean_price = sum(prices) / n
    if not mean_price:
        return 0.0
    mean_x = (n - 1) / 2
    num = sum((i - mean_x) * (p - mean_price) for i, p in enumerate(prices))
    den = sum((i - mean_x) ** 2 for i in range(n))
    if not den:
        return 0.0
    return (num / den) / mean_price * 100


def context(records, dest_code, current_price):
    """지금 가격이 과거 관측 대비 어디쯤인지.

    이번 스캔 결과는 아직 이력에 넣기 전 상태로 넘겨야 한다 — 자기 자신과
    비교하면 항상 '역대 최저 대비 0%'가 나온다.

    관측이 모자라면 None을 돌려준다. 없는 정밀도를 지어내지 않는다.
    """
    if not current_price:
        return None
    past = [p for _, p in series(records, dest_code)]
    if len(past) < MIN_FOR_RANGE:
        return None

    low, high = min(past), max(past)
    prev = past[-1]

    ctx = {
        "observations": len(past),
        "past_low": low,
        "past_high": high,
        "vs_low_pct": round((current_price - low) / low * 100, 1) if low else 0.0,
        "vs_prev_pct": round((current_price - prev) / prev * 100, 1) if prev else 0.0,
        "is_record_low": current_price < low,
        "trend": None,
        "trend_pct": None,
    }

    if len(past) >= MIN_FOR_TREND:
        window = (past + [current_price])[-TREND_WINDOW:]
        slope = _slope_pct(window)
        ctx["trend_pct"] = round(slope, 1)
        if slope <= -TREND_EPS:
            ctx["trend"] = "하락"
        elif slope >= TREND_EPS:
            ctx["trend"] = "상승"
        else:
            ctx["trend"] = "횡보"

    return ctx


def describe(ctx):
    """사람이 읽을 한 줄. context()가 None이면 빈 문자열."""
    if not ctx:
        return ""
    if ctx["is_record_low"]:
        parts = [f"🏆 역대 최저", f"이전 {ctx['past_low']:,}원"]
    elif ctx["vs_low_pct"] <= 0:
        parts = [f"역대 최저 타이 {ctx['past_low']:,}원"]
    else:
        parts = [f"역대 최저 대비 +{ctx['vs_low_pct']}%"]

    if ctx["trend"]:
        parts.append(f"{ctx['trend']}세")
    parts.append(f"관측 {ctx['observations']}회")
    return " · ".join(parts)


def contexts_for(tag, result):
    """스캔 결과의 목적지 전부에 대해 context를 구한다. {코드: ctx}."""
    records = load(tag)
    if not records:
        return {}
    out = {}
    for r in result.get("ranking", []):
        ctx = context(records, r["code"], r["best_price"])
        if ctx:
            out[r["code"]] = ctx
    return out
