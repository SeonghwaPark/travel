"""Google 호텔 가격을 긁을 수 있는지 판별하는 탐침 (일회성 진단용).

항공권은 가격 그래프라는 내부 API가 있어서 풀렸다. 호텔도 같은 수법이 통하는지
확인해야 하는데, 파서를 먼저 쓰고 실패하면 원인을 알 수 없다. 그래서 파싱을
확정하지 않고 **응답에 뭐가 들어있는지만** 보고한다.

_probe_impersonate.py와 같은 성격의 진단 스크립트다. 판별이 끝나면 지워도 된다.

    python backend/_probe_hotels.py "삿포로" 2027-02-17 2027-02-23
"""

import json
import re
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])

import gflights  # noqa: E402
import primp  # noqa: E402


def probe(place, check_in, check_out, adults=2, children=1):
    url = "https://www.google.com/travel/search"
    params = {
        "q": f"{place} 호텔",
        "hl": "ko",
        "gl": "kr",
        "curr": "KRW",
        "ved": "0",
    }

    print(f"▶ 요청: {url}  q={params['q']}  {check_in}~{check_out}")
    try:
        client = primp.Client(impersonate=gflights._IMPERSONATE, verify=False,
                              cookie_store=True)
        res = client.get(url, params=params)
    except Exception as e:
        print(f"✗ 요청 실패: {e}")
        return 1

    text = res.text or ""
    print(f"  HTTP {res.status_code} | 본문 {len(text):,}자")
    if res.status_code != 200:
        print("✗ 200이 아니라 여기서 중단")
        return 1

    findings = {}

    # 1) 구글이 초기 데이터를 심는 대표적인 두 가지 형태
    findings["AF_initDataCallback"] = text.count("AF_initDataCallback")
    findings["ds:_ 블록"] = len(re.findall(r"key:\s*'ds:\d+'", text))

    # 2) 가격처럼 보이는 문자열
    won = re.findall(r"₩\s?[\d,]{4,}", text)
    krw = re.findall(r"\bKRW\s?[\d,]{4,}", text)
    findings["₩ 패턴"] = len(won)
    findings["KRW 패턴"] = len(krw)

    # 3) 호텔명이 실릴 만한 힌트
    findings["'박' 언급"] = text.count("박")
    findings["'1박' 언급"] = text.count("1박")

    print("\n  발견:")
    for k, v in findings.items():
        print(f"    {k:<22} {v}")

    if won or krw:
        print("\n  가격 샘플 (최대 8개):")
        for s in (won + krw)[:8]:
            print(f"    {s}")

    # 4) 초기 데이터 블록의 앞부분만 살짝 — 구조 판단용
    m = re.search(r"AF_initDataCallback\((\{.{0,400})", text, re.S)
    if m:
        print("\n  초기 데이터 블록 시작부:")
        print("   ", m.group(1)[:300].replace("\n", " "))

    verdict = "가능성 있음" if (won or krw) else "가격 문자열이 안 보임"
    print(f"\n판정: {verdict}")
    print(json.dumps(findings, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    a = sys.argv[1:]
    sys.exit(probe(a[0] if a else "삿포로",
                   a[1] if len(a) > 1 else "2027-02-17",
                   a[2] if len(a) > 2 else "2027-02-23"))
