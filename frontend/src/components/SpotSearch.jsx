import { useState } from 'react'
import { REGION_KEYWORDS } from './DomesticForm'

const REGION_GROUPS = [
  {
    group: '제주',
    regions: [
      { id: 'jeju', name: '제주 전체' },
      { id: 'jeju-city', name: '제주시' },
      { id: 'seogwipo', name: '서귀포' },
    ],
  },
  {
    group: '부산/경남',
    regions: [
      { id: 'busan', name: '부산' },
      { id: 'tongyeong', name: '통영' },
      { id: 'namhae', name: '남해' },
      { id: 'gyeongju', name: '경주' },
    ],
  },
  {
    group: '강원',
    regions: [
      { id: 'sokcho', name: '속초·고성' },
      { id: 'gangneung', name: '강릉' },
      { id: 'yangyang', name: '양양' },
      { id: 'chuncheon', name: '춘천' },
    ],
  },
  {
    group: '전남/전북',
    regions: [
      { id: 'yeosu', name: '여수' },
      { id: 'jeonju', name: '전주' },
      { id: 'mokpo', name: '목포' },
    ],
  },
  {
    group: '기타',
    regions: [
      { id: 'seoul', name: '서울' },
      { id: 'incheon', name: '인천' },
      { id: 'daegu', name: '대구' },
      { id: 'gwangju', name: '광주' },
      { id: 'daejeon', name: '대전' },
    ],
  },
]

const SPOT_SITES = [
  {
    site: '네이버 지도',
    category: '맛집',
    tags: ['맛집', '블로그리뷰', '별점'],
    buildUrl: (kw) => `https://map.naver.com/p/search/${kw} 맛집`,
  },
  {
    site: '카카오맵',
    category: '맛집',
    tags: ['맛집', '카페', '평점순'],
    buildUrl: (kw) => `https://map.kakao.com/?q=${kw} 맛집`,
  },
  {
    site: '망고플레이트',
    category: '맛집',
    tags: ['맛집랭킹', '리뷰', '평점'],
    buildUrl: (kw) => `https://www.mangoplate.com/search/${kw}`,
  },
  {
    site: '다이닝코드',
    category: '맛집',
    tags: ['빅데이터', '맛집분석', 'TV맛집'],
    buildUrl: (kw) => `https://www.diningcode.com/list.dc?query=${kw} 맛집`,
  },
  {
    site: '네이버 지도',
    category: '관광지',
    tags: ['관광명소', '체험', '포토스팟'],
    buildUrl: (kw) => `https://map.naver.com/p/search/${kw} 관광지`,
  },
  {
    site: '한국관광공사',
    category: '관광지',
    tags: ['공식관광정보', '축제', '여행코스'],
    buildUrl: (kw) => `https://korean.visitkorea.or.kr/search/search.do?searchTerm=${kw}`,
  },
  {
    site: '트립어드바이저',
    category: '관광지',
    tags: ['관광지순위', '리뷰', '글로벌'],
    buildUrl: (kw) => `https://www.tripadvisor.co.kr/Search?q=${kw}`,
  },
  {
    site: '구글 지도',
    category: '관광지',
    tags: ['관광명소', '리뷰', '사진'],
    buildUrl: (kw) => `https://www.google.com/maps/search/${kw}+관광지`,
  },
  {
    site: '네이버 카페 검색',
    category: '카페',
    tags: ['카페', '디저트', '뷰맛집'],
    buildUrl: (kw) => `https://map.naver.com/p/search/${kw} 카페`,
  },
  {
    site: '카카오맵',
    category: '카페',
    tags: ['카페', '브런치', '베이커리'],
    buildUrl: (kw) => `https://map.kakao.com/?q=${kw} 카페`,
  },
]

const CATEGORY_ORDER = ['맛집', '관광지', '카페']

function SpotSearch() {
  const [regionId, setRegionId] = useState('jeju')
  const [searched, setSearched] = useState(false)
  const [searchRegion, setSearchRegion] = useState(null)

  const selectedName = REGION_GROUPS.flatMap(g => g.regions).find(r => r.id === regionId)?.name || regionId

  const handleSearch = (e) => {
    e.preventDefault()
    setSearchRegion({
      id: regionId,
      name: selectedName,
      keyword: REGION_KEYWORDS[regionId] || regionId,
    })
    setSearched(true)
  }

  const kw = searchRegion ? encodeURIComponent(searchRegion.keyword) : ''

  const grouped = {}
  for (const s of SPOT_SITES) {
    if (!grouped[s.category]) grouped[s.category] = []
    grouped[s.category].push({ ...s, url: s.buildUrl(kw) })
  }

  const categories = Object.keys(grouped).sort(
    (a, b) => CATEGORY_ORDER.indexOf(a) - CATEGORY_ORDER.indexOf(b)
  )

  return (
    <>
      <form className="search-form" onSubmit={handleSearch}>
        <div className="form-row">
          <div className="form-group" style={{ flex: 2 }}>
            <label>여행지</label>
            <select value={regionId} onChange={e => setRegionId(e.target.value)}>
              {REGION_GROUPS.map(g => (
                <optgroup key={g.group} label={g.group}>
                  {g.regions.map(r => (
                    <option key={r.id} value={r.id}>{r.name}</option>
                  ))}
                </optgroup>
              ))}
            </select>
          </div>
        </div>
        <button type="submit" className="search-btn">
          맛집·관광지 검색
        </button>
      </form>

      {searched && searchRegion && (
        <div className="results">
          <div style={{
            background: '#ebf8ff',
            border: '1.5px solid #bee3f8',
            borderRadius: '12px',
            padding: '1.1rem 1.4rem',
            marginBottom: '1.5rem',
          }}>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', alignItems: 'center', marginBottom: '0.6rem' }}>
              <span style={{ fontWeight: 700, fontSize: '1.05rem', color: '#2b6cb0' }}>{searchRegion.name}</span>
              <span style={{ background: '#3182ce', color: '#fff', borderRadius: '8px', padding: '3px 10px', fontSize: '0.82rem', fontWeight: 600 }}>
                맛집·관광지·카페
              </span>
            </div>
            <p style={{ margin: 0, color: '#2c5282', fontSize: '0.8rem' }}>
              클릭하면 해당 사이트에서 <strong>{searchRegion.keyword}</strong> 지역을 검색합니다.
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
                {grouped[cat].map((item, idx) => (
                  <a
                    key={`${item.site}-${item.category}-${idx}`}
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
                          바로가기
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
                    </div>
                  </a>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  )
}

export default SpotSearch
