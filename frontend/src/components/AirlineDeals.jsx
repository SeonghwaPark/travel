const AIRLINES = [
  { airline: '대한항공', logo: 'KE', description: '대한항공 공식 특가 이벤트 및 프로모션', url: 'https://www.koreanair.com/kr/ko/offers' },
  { airline: '아시아나항공', logo: 'OZ', description: '아시아나항공 특가 이벤트 및 얼리버드', url: 'https://flyasiana.com/', hint: '홈 → 이벤트/프로모션 탭으로 이동' },
  { airline: '진에어', logo: 'LJ', description: '진에어 특가 & 프로모션 이벤트', url: 'https://www.jinair.com/promotion/list' },
  { airline: '제주항공', logo: '7C', description: '제주항공 땡처리 특가 이벤트', url: 'https://www.jejuair.net/', hint: '홈 → 특가/이벤트 탭으로 이동' },
  { airline: '티웨이항공', logo: 'TW', description: '티웨이항공 특가 & 이벤트', url: 'https://www.twayair.com/promotions' },
  { airline: '에어부산', logo: 'BX', description: '에어부산 특가 프로모션', url: 'https://www.airbusan.com/promotion/list' },
  { airline: '에어프레미아', logo: 'YP', description: '에어프레미아 특가 & 프로모션', url: 'https://www.airpremia.com/ko' },
  { airline: '땡처리닷컴', logo: '땡', description: '항공권·여행 땡처리 특가 모음', url: 'https://www.ttour.com/flight' },
  { airline: '스카이스캐너', logo: 'SS', description: '전 세계 항공사 최저가 비교', url: 'https://www.skyscanner.co.kr/flights' },
  { airline: '클룩', logo: 'KL', description: '항공권·패스·체험 특가 이벤트', url: 'https://www.klook.com/ko/flights/' },
]

function AirlineDeals() {
  return (
    <div className="results">
      <h2>항공사 특가 이벤트</h2>
      <p style={{ color: '#718096', marginBottom: '1.5rem', fontSize: '0.9rem' }}>
        각 항공사 공식 특가·프로모션 페이지로 바로 이동합니다
      </p>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: '0.75rem' }}>
        {AIRLINES.map(item => (
          <a key={item.airline} href={item.url} target="_blank" rel="noopener noreferrer" style={{ textDecoration: 'none' }}>
            <div
              style={{
                background: 'white',
                borderRadius: '10px',
                padding: '16px',
                boxShadow: '0 1px 4px rgba(0,0,0,0.07)',
                border: '1px solid #e2e8f0',
                cursor: 'pointer',
                transition: 'transform 0.12s, box-shadow 0.12s',
              }}
              onMouseEnter={e => {
                e.currentTarget.style.transform = 'translateY(-2px)'
                e.currentTarget.style.boxShadow = '0 5px 16px rgba(0,0,0,0.12)'
                e.currentTarget.style.borderColor = '#90cdf4'
              }}
              onMouseLeave={e => {
                e.currentTarget.style.transform = 'none'
                e.currentTarget.style.boxShadow = '0 1px 4px rgba(0,0,0,0.07)'
                e.currentTarget.style.borderColor = '#e2e8f0'
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <span style={{ background: '#3182ce', color: '#fff', borderRadius: '6px', padding: '2px 7px', fontSize: '0.75rem', fontWeight: 700 }}>
                    {item.logo}
                  </span>
                  <span style={{ fontWeight: 700, fontSize: '1rem', color: '#2d3748' }}>{item.airline}</span>
                </div>
                <span style={{ fontSize: '0.72rem', color: '#3182ce', border: '1px solid #bee3f8', background: '#ebf8ff', borderRadius: '10px', padding: '2px 7px' }}>
                  특가 →
                </span>
              </div>
              <p style={{ margin: '0.5rem 0 0', color: '#718096', fontSize: '0.83rem' }}>
                {item.description}
              </p>
              {item.hint && (
                <p style={{ margin: '0.4rem 0 0', fontSize: '0.73rem', color: '#e67e22', fontWeight: 600 }}>
                  ⚠ {item.hint}
                </p>
              )}
            </div>
          </a>
        ))}
      </div>
    </div>
  )
}

export default AirlineDeals
