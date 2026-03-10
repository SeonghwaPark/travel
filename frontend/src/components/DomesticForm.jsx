import { useState } from 'react'

const today = new Date().toISOString().slice(0, 10)
const tomorrow = new Date(Date.now() + 86400000).toISOString().slice(0, 10)

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
      { id: 'geoje', name: '거제' },
      { id: 'namhae', name: '남해' },
      { id: 'sacheon', name: '사천' },
      { id: 'hadong', name: '하동' },
    ],
  },
  {
    group: '강원',
    regions: [
      { id: 'sokcho', name: '속초·고성' },
      { id: 'gangneung', name: '강릉' },
      { id: 'yangyang', name: '양양' },
      { id: 'pyeongchang', name: '평창·정선' },
      { id: 'chuncheon', name: '춘천' },
      { id: 'hongcheon', name: '홍천' },
      { id: 'wonju', name: '원주' },
      { id: 'jeongseon', name: '영월·태백' },
    ],
  },
  {
    group: '경기/인천',
    regions: [
      { id: 'gapyeong', name: '가평·양평' },
      { id: 'pocheon', name: '포천·연천' },
      { id: 'yongin', name: '용인·수원' },
      { id: 'incheon', name: '인천' },
      { id: 'ansan', name: '안산·시흥' },
    ],
  },
  {
    group: '전남/광주',
    regions: [
      { id: 'yeosu', name: '여수' },
      { id: 'suncheon', name: '순천·담양' },
      { id: 'mokpo', name: '목포·해남' },
      { id: 'wando', name: '완도·진도' },
      { id: 'gwangju', name: '광주' },
    ],
  },
  {
    group: '전북',
    regions: [
      { id: 'jeonju', name: '전주' },
      { id: 'gunsan', name: '군산' },
      { id: 'buan', name: '부안·고창' },
    ],
  },
  {
    group: '충청',
    regions: [
      { id: 'boryeong', name: '보령·태안' },
      { id: 'danyang', name: '단양·충주' },
      { id: 'chungju', name: '청주' },
      { id: 'daejeon', name: '대전' },
    ],
  },
  {
    group: '경북/대구',
    regions: [
      { id: 'gyeongju', name: '경주' },
      { id: 'pohang', name: '포항' },
      { id: 'andong', name: '안동' },
      { id: 'daegu', name: '대구' },
      { id: 'mun경north', name: '문경·영주' },
    ],
  },
  {
    group: '서울',
    regions: [
      { id: 'seoul', name: '서울 (호캉스)' },
    ],
  },
]

// DomesticForm에서 쓰는 keyword 매핑 (백엔드로 전달)
const REGION_KEYWORDS = {
  jeju: '제주', 'jeju-city': '제주시', seogwipo: '서귀포',
  busan: '부산', tongyeong: '통영', geoje: '거제', namhae: '남해', sacheon: '사천', hadong: '하동',
  sokcho: '속초', gangneung: '강릉', yangyang: '양양', pyeongchang: '평창', chuncheon: '춘천',
  hongcheon: '홍천', wonju: '원주', jeongseon: '영월',
  gapyeong: '가평', pocheon: '포천', yongin: '용인', incheon: '인천', ansan: '안산',
  yeosu: '여수', suncheon: '순천', mokpo: '목포', wando: '완도', gwangju: '광주',
  jeonju: '전주', gunsan: '군산', buan: '부안',
  boryeong: '보령', danyang: '단양', chungju: '청주', daejeon: '대전',
  gyeongju: '경주', pohang: '포항', andong: '안동', daegu: '대구', mun경north: '문경',
  seoul: '서울',
}

function DomesticForm({ onSearch, loading }) {
  const [regionId, setRegionId] = useState('jeju')
  const [checkIn, setCheckIn] = useState(today)
  const [checkOut, setCheckOut] = useState(tomorrow)
  const [adults, setAdults] = useState(2)

  const selectedName = REGION_GROUPS.flatMap(g => g.regions).find(r => r.id === regionId)?.name || regionId

  const handleSubmit = (e) => {
    e.preventDefault()
    onSearch({
      region: regionId,
      regionName: selectedName,
      keyword: REGION_KEYWORDS[regionId] || regionId,
      check_in: checkIn,
      check_out: checkOut,
      adults,
    })
  }

  return (
    <form className="search-form" onSubmit={handleSubmit}>
      <div className="form-row">
        <div className="form-group">
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
        <div className="form-group">
          <label>체크인</label>
          <input type="date" value={checkIn} min={today} onChange={e => setCheckIn(e.target.value)} />
        </div>
        <div className="form-group">
          <label>체크아웃</label>
          <input type="date" value={checkOut} min={checkIn} onChange={e => setCheckOut(e.target.value)} />
        </div>
        <div className="form-group">
          <label>인원</label>
          <select value={adults} onChange={e => setAdults(Number(e.target.value))}>
            {[1,2,3,4,5,6].map(n => (
              <option key={n} value={n}>{n}명</option>
            ))}
          </select>
        </div>
      </div>
      <button type="submit" className="search-btn" disabled={loading}>
        {loading ? '검색 중...' : '국내여행 검색'}
      </button>
    </form>
  )
}

export default DomesticForm
export { REGION_KEYWORDS }
