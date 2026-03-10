const SITES = [
  {
    site: '야놀자',
    category: '숙소',
    tags: ['호텔', '펜션', '모텔', '리조트'],
    buildUrl: (kw, ci, co, adults) =>
      `https://www.yanolja.com/leisure/list?keyword=${kw}&checkIn=${ci}&checkOut=${co}&adultCount=${adults}`,
  },
  {
    site: '여기어때',
    category: '숙소',
    tags: ['호텔', '모텔', '펜션', '풀빌라'],
    buildUrl: (kw, ci, co, adults) =>
      `https://www.yeogi.com/domestic-accommodations?searchType=KEYWORD&keyword=${kw}&checkIn=${ci}&checkOut=${co}&numberOfRoom=1&numberOfAdult=${adults}`,
  },
  {
    site: '네이버 호텔',
    category: '숙소',
    tags: ['호텔', '리조트', '가격비교'],
    buildUrl: (kw, ci, co, adults) =>
      `https://hotels.naver.com/accommodation?keyword=${kw}&checkIn=${ci}&checkOut=${co}&adults=${adults}`,
  },
  {
    site: '트립닷컴',
    category: '숙소',
    tags: ['호텔', '리조트', 'Trip.com'],
    buildUrl: (kw, ci, co, adults) =>
      `https://kr.trip.com/hotels/?q=${kw}&checkIn=${ci}&checkOut=${co}&adult=${adults}`,
  },
  {
    site: '마이리얼트립',
    category: '액티비티·체험',
    tags: ['투어', '체험', '티켓', '데이트코스'],
    buildUrl: (kw) =>
      `https://www.myrealtrip.com/offers?q=${kw}`,
  },
  {
    site: '클룩',
    category: '액티비티·체험',
    tags: ['투어', '액티비티', '입장권'],
    buildUrl: (kw) =>
      `https://www.klook.com/ko/search/?query=${kw}`,
  },
  {
    site: '인터파크 투어',
    category: '패키지',
    tags: ['여행패키지', '기차여행', '버스투어'],
    hint: '국내 투어 메인 → 직접 검색',
    buildUrl: () =>
      `https://travel.interpark.com/tour/main/domestic`,
  },
  {
    site: '땡처리닷컴',
    category: '패키지·특가',
    tags: ['땡처리', '마감특가', '초특가'],
    buildUrl: (kw) =>
      `https://www.ttour.com/search?keyword=${kw}`,
  },
]

const CATEGORY_ORDER = ['숙소', '액티비티·체험', '패키지·특가', '패키지']

function DomesticResults({ regionName, keyword, checkIn, checkOut, adults }) {
  if (!keyword) return null

  const kw = encodeURIComponent(keyword)
  const nights = Math.round((new Date(checkOut) - new Date(checkIn)) / 86400000)
  const [, ciM, ciD] = checkIn.split('-')
  const [, coM, coD] = checkOut.split('-')

  const grouped = {}
  for (const s of SITES) {
    if (!grouped[s.category]) grouped[s.category] = []
    grouped[s.category].push({ ...s, url: s.buildUrl(kw, checkIn, checkOut, adults) })
  }

  const categories = Object.keys(grouped).sort(
    (a, b) => CATEGORY_ORDER.indexOf(a) - CATEGORY_ORDER.indexOf(b)
  )

  return (
    <div className="results">
      {/* 검색 조건 요약 */}
      <div style={{
        background: '#ebf8ff',
        border: '1.5px solid #bee3f8',
        borderRadius: '12px',
        padding: '1.1rem 1.4rem',
        marginBottom: '1.5rem',
      }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', alignItems: 'center', marginBottom: '0.6rem' }}>
          <span style={{ fontWeight: 700, fontSize: '1.05rem', color: '#2b6cb0' }}>{regionName}</span>
          <span style={{ background: '#3182ce', color: '#fff', borderRadius: '8px', padding: '3px 10px', fontSize: '0.82rem', fontWeight: 600 }}>
            {ciM}월 {ciD}일 → {coM}월 {coD}일
          </span>
          <span style={{ background: '#3182ce', color: '#fff', borderRadius: '8px', padding: '3px 10px', fontSize: '0.82rem', fontWeight: 600 }}>
            {nights}박 {nights + 1}일
          </span>
          <span style={{ background: '#3182ce', color: '#fff', borderRadius: '8px', padding: '3px 10px', fontSize: '0.82rem', fontWeight: 600 }}>
            성인 {adults}명
          </span>
        </div>
        <p style={{ margin: 0, color: '#2c5282', fontSize: '0.8rem' }}>
          클릭하면 해당 사이트로 이동합니다. <strong>야놀자</strong>는 키워드 자동입력 후 <strong>Enter</strong>로 검색, 나머지는 날짜·인원 포함 자동 적용됩니다.
        </p>
      </div>

      {categories.map(cat => (
        <div key={cat} style={{ marginBottom: '1.5rem' }}>
          <h3 style={{
            color: '#718096',
            fontSize: '0.78rem',
            fontWeight: 700,
            marginBottom: '0.7rem',
            textTransform: 'uppercase',
            letterSpacing: '0.07em',
            borderBottom: '1px solid #e2e8f0',
            paddingBottom: '0.35rem',
          }}>
            {cat}
          </h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: '0.7rem' }}>
            {grouped[cat].map(item => (
              <a
                key={item.site}
                href={item.url}
                target="_blank"
                rel="noopener noreferrer"
                style={{ textDecoration: 'none' }}
              >
                <div
                  style={{
                    background: 'white',
                    borderRadius: '10px',
                    padding: '14px 16px',
                    boxShadow: '0 1px 4px rgba(0,0,0,0.07)',
                    cursor: 'pointer',
                    transition: 'transform 0.12s, box-shadow 0.12s',
                    border: '1px solid #e2e8f0',
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
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                    <span style={{ fontWeight: 700, fontSize: '0.97rem', color: '#2d3748' }}>{item.site}</span>
                    <span style={{ fontSize: '0.7rem', color: '#3182ce', border: '1px solid #bee3f8', background: '#ebf8ff', borderRadius: '10px', padding: '2px 7px' }}>
                      바로가기 →
                    </span>
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                    {item.tags.map(tag => (
                      <span key={tag} style={{
                        fontSize: '0.7rem',
                        background: '#f7fafc',
                        border: '1px solid #e2e8f0',
                        borderRadius: '5px',
                        padding: '1px 6px',
                        color: '#718096',
                      }}>
                        {tag}
                      </span>
                    ))}
                  </div>
                  {item.hint && (
                    <p style={{ margin: '6px 0 0', fontSize: '0.7rem', color: '#e67e22', fontWeight: 600 }}>
                      ⚠ {item.hint}
                    </p>
                  )}
                </div>
              </a>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

export default DomesticResults
