"""AI 여행 플래너의 접지(RAG) 모듈 — 네트워크·LLM SDK 불필요.

일정 생성을 모델의 일반 지식에만 맡기면 숙소 구역·교통 요금·시즌 특성을
그럴듯하게 지어낸다. 이 리포에는 이미 사람이 정제한 값(lodging_areas.json,
trip_profiles.json, transport.json, calendar.json)이 있으므로, 요청된
목적지·날짜에 맞는 부분만 골라 프롬프트에 끼워 넣는다.

날짜 계산(요일·연휴 겹침)은 모델에 맡기지 않고 여기서 한다 — 모델이 가장
자주 틀리는 부분이 날짜 산수다.

원칙은 브리프와 같다: 없는 정밀도를 지어내지 않는다. 달력에 없는 연도의
공휴일은 "없다"가 아니라 "확인 불가"로 말한다.
"""

import json
import os
import re
from datetime import date, timedelta

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_WEEKDAYS = "월화수목금토일"


def _load(name):
    try:
        with open(os.path.join(_ROOT, name), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


_LODGING = _load("lodging_areas.json").get("destinations", {})
_PROFILES = _load("trip_profiles.json").get("destinations", {})
_TRANSPORT = _load("transport.json").get("regions", {})
_CALENDAR = _load("calendar.json")
_DESTINATIONS = _load("destinations.json")


# ── 목적지 매칭 ──

def _name_tokens(name):
    """이름을 대조용 토큰으로 쪼갠다. '고마쓰 (가나자와)' → {고마쓰, 가나자와}."""
    tokens = set()
    inner = re.findall(r"\(([^)]*)\)", name)
    base = re.sub(r"\([^)]*\)", "", name)
    for part in [base] + inner:
        part = part.replace(" ", "").strip()
        if part:
            tokens.add(part)
    return tokens


def _candidates():
    """코드→이름 후보를 모든 데이터 파일에서 모은다. 프로필이 있는 쪽을 우선한다."""
    cands = {}
    for section in ("international", "domestic"):
        for code, info in _DESTINATIONS.get(section, {}).items():
            cands[code] = info.get("name", "")
    for code, info in _LODGING.items():
        cands[code] = info.get("name", cands.get(code, ""))
    for code, info in _PROFILES.items():
        cands[code] = info.get("name", cands.get(code, ""))
    return cands


def match_destination(text):
    """여행지 문자열을 데이터의 목적지 코드로 잇는다. 못 이으면 None.

    '제주 전체'→CJU, '부산'→'부산 (김해)'처럼 부분 일치를 허용하되,
    긴 토큰부터 대조해 짧은 이름이 엉뚱하게 걸리지 않게 한다.
    """
    query = (text or "").replace(" ", "").strip()
    if not query:
        return None
    if re.fullmatch(r"[A-Za-z]{3}", query):
        code = query.upper()
        return code if code in _candidates() else None

    best_code, best_len = None, 0
    for code, name in _candidates().items():
        for token in _name_tokens(name):
            if token in query or query in token:
                score = min(len(token), len(query))
                if score >= 2 and score > best_len:
                    best_code, best_len = code, score
    return best_code


# ── 날짜 사실 ──

def date_facts(start_date, end_date):
    """기간의 요일·박수·공휴일 겹침을 계산한다. 날짜가 이상하면 None.

    달력에 등록 안 된 연도는 holidays_known=False로 구분한다 —
    '공휴일 없음'과 '확인 불가'는 다른 말이다.
    """
    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
    except (TypeError, ValueError):
        return None
    if end < start or (end - start).days > 30:
        return None

    holidays_by_date = {}
    known_years = set(_CALENDAR.get("holidays", {}).keys())
    for year in range(start.year, end.year + 1):
        for h in _CALENDAR.get("holidays", {}).get(str(year), []):
            holidays_by_date[h["date"]] = h["name"]

    days = []
    holidays = []
    for i in range((end - start).days + 1):
        d = start + timedelta(days=i)
        iso = d.isoformat()
        entry = {"date": iso, "weekday": _WEEKDAYS[d.weekday()]}
        if iso in holidays_by_date:
            entry["holiday"] = holidays_by_date[iso]
            holidays.append({"date": iso, "name": holidays_by_date[iso]})
        days.append(entry)

    return {
        "days": days,
        "nights": (end - start).days,
        "holidays": holidays,
        "holidays_known": all(str(y) in known_years
                              for y in range(start.year, end.year + 1)),
        "weekend_days": sum(1 for d in days if d["weekday"] in "토일"),
    }


# ── 시즌 배수 ──

def _season_warnings(profile, facts):
    """여행 기간이 시즌 배수 구간(눈축제 등)과 겹치면 경고 문장을 만든다."""
    if not profile or not facts:
        return []
    warnings = []
    trip_dates = {d["date"][5:] for d in facts["days"]}  # MM-DD
    for m in profile.get("season_multipliers", []):
        if m.get("lunar"):
            continue  # 음력 구간은 연도별 환산이 없으면 못 겹쳐본다
        start, end = m.get("from"), m.get("to")
        if not start or not end:
            continue
        if start <= end:
            hit = any(start <= md <= end for md in trip_dates)
        else:  # 연말연시처럼 해를 넘는 구간
            hit = any(md >= start or md <= end for md in trip_dates)
        if hit:
            warnings.append(
                f"{m.get('reason', '성수기')} 기간({start}~{end})과 겹친다 — "
                f"숙박비가 평소의 약 {m.get('factor')}배까지 오른다.")
    return warnings


# ── 컨텍스트 조립 ──

def build_context(destination_text, start_date, end_date):
    """프롬프트에 넣을 접지 텍스트를 만든다.

    반환: (context_text, grounding, n_days)
    - context_text: 프롬프트에 그대로 끼울 한국어 블록. 쓸 데이터가 없으면 "".
    - grounding: {"destination_code", "sources"} — 응답에 실어 무엇을 근거로
      썼는지 사용자에게 보여준다.
    - n_days: 여행 일수 (날짜가 이상하면 None).
    """
    code = match_destination(destination_text)
    facts = date_facts(start_date, end_date)
    profile = _PROFILES.get(code) if code else None
    lodging = _LODGING.get(code) if code else None
    transport = None
    if profile and profile.get("transport_region"):
        transport = _TRANSPORT.get(profile["transport_region"])

    sections = []
    sources = []

    if facts:
        lines = [f"- 일정: {facts['nights']}박 {facts['nights'] + 1}일, "
                 f"주말 {facts['weekend_days']}일 포함"]
        lines.append("- 날짜와 요일: " + ", ".join(
            f"{d['date']}({d['weekday']})" for d in facts["days"]))
        if facts["holidays_known"]:
            if facts["holidays"]:
                lines.append("- 기간 중 한국 공휴일: " + ", ".join(
                    f"{h['date']} {h['name']}" for h in facts["holidays"]) +
                    " — 출발·귀국 혼잡과 가격 상승에 주의")
            else:
                lines.append("- 기간 중 한국 공휴일 없음")
        else:
            lines.append("- 공휴일: 달력에 등록되지 않은 연도라 확인 불가 "
                         "(없다고 단정하지 말 것)")
        sections.append("[날짜 정보 — 아래 요일·공휴일을 그대로 사용할 것]\n"
                        + "\n".join(lines))
        sources.append("달력")

    if profile:
        lines = []
        if profile.get("season_note"):
            lines.append(f"- 시즌 특성: {profile['season_note']}")
        months = profile.get("best_months")
        if months and facts:
            trip_months = {int(d["date"][5:7]) for d in facts["days"]}
            tag = "제철이다" if trip_months & set(months) else "제철이 아니다"
            lines.append(f"- 제철: {', '.join(str(m) for m in months)}월 — "
                         f"이번 여행 시기는 {tag}")
        fam = profile.get("family")
        if fam:
            lines.append(f"- 가족 적합도 {fam.get('score')}/5: {fam.get('why')}")
        if profile.get("daily_cost"):
            lines.append(f"- 1인 1일 현지비 어림 {profile['daily_cost']:,}원 "
                         "(식비+시내교통+입장료, 숙박·항공 제외, 아동은 0.6배)")
        if profile.get("lodging_per_night"):
            lines.append(f"- 1박 숙박비 어림 {profile['lodging_per_night']:,}원")
        for w in _season_warnings(profile, facts):
            lines.append(f"- 주의: {w}")
        highlights = profile.get("highlights", [])[:6]
        if highlights:
            lines.append("- 대표 스팟: " + "; ".join(
                f"{h['name']} ({h['for']})" for h in highlights))
        if lines:
            sections.append(f"[{profile['name']} 목적지 프로필]\n" + "\n".join(lines))
            sources.append("목적지 프로필")

    if lodging:
        lines = []
        for tip in lodging.get("tips", []):
            lines.append(f"- 팁: {tip}")
        for area in lodging.get("areas", [])[:5]:
            line = f"- 구역 '{area['name']}': {area.get('good_for', '')}. {area.get('why', '')}"
            if area.get("caution"):
                line += f" (주의: {area['caution']})"
            lines.append(line)
        if lines:
            sections.append(f"[{lodging['name']} 숙박 구역 가이드 — "
                            "숙소 추천은 반드시 이 구역들 중에서 고를 것]\n"
                            + "\n".join(lines))
            sources.append("숙박 구역 가이드")

    if transport:
        lines = []
        for leg in transport.get("legs", {}).values():
            lines.append(f"- {leg['from']}→{leg['to']}: {leg['minutes']}분, "
                         f"{leg['fare']:,} {transport.get('currency', '')} ({leg['service']})")
        for p in transport.get("passes", []):
            lines.append(f"- 패스: {p['name']} {p['price']:,} "
                         f"{transport.get('currency', '')} ({p.get('note', '')})")
        if lines:
            note = ("" if transport.get("fares_verified")
                    else " — 어림값이므로 '약'을 붙여 쓸 것")
            sections.append(f"[{transport['name']} 교통 요금표{note}]\n"
                            + "\n".join(lines))
            sources.append("교통 요금표")

    context = "\n\n".join(sections)
    grounding = {"destination_code": code, "sources": sources}
    n_days = facts["nights"] + 1 if facts else None
    return context, grounding, n_days


# ── LLM 응답 처리 ──

def salvage_json(text):
    """모델 응답에서 JSON 오브젝트를 건져낸다. 실패하면 None.

    JSON 모드를 켜도 fallback 모델이 코드펜스나 앞뒤 설명을 붙이는 일이
    있어서, 파싱 전에 걷어내고 가장 바깥 {...}만 남긴다.
    """
    if not text:
        return None
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        parsed = json.loads(text[start:end + 1])
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return None


def plan_max_tokens(n_days):
    """일수에 비례해 응답 토큰 상한을 잡는다.

    6000 고정이면 5일 이상 일정에서 JSON이 중간에 잘려 파싱이 깨진다.
    상한 16000은 gpt-4o-mini의 출력 한도(16384) 안쪽이다.
    """
    if not n_days:
        n_days = 4
    return min(16000, 2500 + 1300 * max(1, n_days))
