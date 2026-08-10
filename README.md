<!-- Banner -->
<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=waving&color=0:0a0e27,50:4fd1ff,100:ffe81f&height=200&section=header&text=Travel&fontSize=58&fontColor=ffffff&fontAlignY=38&desc=국내선%20항공편%20통합%20검색%20%C3%97%20실시간%20비교&descSize=16&descAlignY=60&animation=fadeIn" />
</p>

<p align="center">
  <img src="https://img.shields.io/badge/React-61DAFB?style=for-the-badge&logo=react&logoColor=black" />
  <img src="https://img.shields.io/badge/Vite-646CFF?style=for-the-badge&logo=vite&logoColor=white" />
  <img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/Status-Active-4fd1ff?style=for-the-badge" />
</p>

<p align="center">
  <i>여러 항공사 일정을 한 화면에서, 한눈에.</i>
</p>

---

## ✨ 주요 기능

- 🛫 **통합 검색** — 출발지·도착지·날짜로 국내선 한번에 조회
- 💰 **운임 비교** — 항공사별 가격·시간 동시 노출
- 📅 **최저가 날짜 찾기** — 여행지·기간을 정하면 출발일별 왕복 최저가를 스캔해 가장 싼 날짜 추천
- ⏱️ **실시간 갱신** — 백엔드에서 멀티 소스 동시 폴링
- 🪟 **데스크톱 단축키** — `start.bat` 한 번으로 백+프 동시 실행

---

## 🧬 아키텍처

```mermaid
flowchart LR
    User([🧑‍💻 User])
    UI[React + Vite<br/>:5173]
    API[FastAPI<br/>:8000]
    Sources[Multi-source<br/>flight providers]

    User --> UI
    UI -->|REST| API
    API -->|fetch + normalize| Sources
    Sources --> API
    API --> UI
```

---

## 🛠️ Tech Stack

| 영역 | 기술 |
|------|------|
| **Frontend** | React (Vite) |
| **Backend** | Python · FastAPI |
| **DevX** | Windows `.bat` 통합 실행, 데스크톱 바로가기 자동 생성 |

---

## 🚀 실행

```bash
# 한번에 실행 (백엔드 + 프론트엔드)
start.bat

# 또는 따로 실행
start-backend.bat       # FastAPI :8000
start-frontend.bat      # Vite :5173
```

> 데스크톱 단축키를 만들려면: `create_shortcut.ps1` 실행

### 최신 브랜치 받아서 실행하기

```bash
git fetch origin claude/travel-flight-price-search-xdkpdi
git checkout claude/travel-flight-price-search-xdkpdi
cd backend && pip install -r requirements.txt && cd ..
start.bat
```

### "최저가 날짜" 기능 확인

1. 브라우저에서 `http://localhost:5173` → **최저가 날짜** 탭
2. 상단의 **가격 그래프 연결 테스트** 버튼 클릭
   - ✓ 정상: 그대로 검색하면 됩니다 (여행지·기간만 고르고 "가장 싼 시기 찾기")
   - ✗ 실패: 화면에 표시되는 로그를 복사해서 알려주세요. 실패해도 검색은 날짜별 스캔 방식으로 자동 전환되어 동작합니다.
3. 직접 확인하려면 `http://localhost:8000/api/flights/price-graph/health` 를 열어도 됩니다.

### 테스트

```bash
cd backend
python test_price_graph.py   # 가격 그래프 요청·응답 처리 (네트워크 불필요)
```

가격 그래프는 Google의 비공식 내부 API라 요청 구조가 조금만 어긋나도 빈 응답이 옵니다.
이 테스트는 요청 페이로드를 Go 참조 구현과 대조해서 그런 어긋남을 미리 잡습니다.

### 문제 해결

**백엔드가 아예 실행되지 않고 `ImportError: cannot import name 'FlightData'` 가 뜬다면**

`fast-flights` 3.x가 설치된 경우입니다. 3.x는 이 프로젝트가 쓰는 2.x API(`FlightData`,
`TFSData`)를 제거해서 import 단계에서 실패합니다. `requirements.txt`에 `fast-flights<3`으로
고정해두었으니 아래를 실행하세요.

```bash
cd backend
pip install -r requirements.txt   # fast-flights 2.x로 다시 설치됨
```

**`[PriceGraph FAIL] ... tunnel error` 또는 연결 실패가 계속된다면**

방화벽·프록시가 `www.google.com` 접속을 막고 있는 경우입니다. 회사망이나 VPN을 쓰고 있다면
해제 후 다시 시도하세요. 연결이 안 되어도 검색 결과 화면에서 Google Flights로 바로 가는
링크는 제공됩니다.

---

## 📁 구조

```
travel/
├── frontend/                  # React (Vite)
├── backend/                   # FastAPI
├── start.bat                  # 통합 실행
├── start-backend.bat
├── start-frontend.bat
└── create_shortcut.ps1        # 바탕화면 바로가기 생성
```

---

<p align="center">
  <sub>⚡ Compare. Choose. Fly. ⚡</sub>
</p>
