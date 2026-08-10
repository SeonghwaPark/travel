import { useState } from 'react'

const MAX_SCAN_DAYS = 14

function addDays(dateStr, days) {
  const d = new Date(dateStr)
  d.setDate(d.getDate() + days)
  return d.toISOString().split('T')[0]
}

function BestDatesForm({ airports, onSearch, loading }) {
  const [origin, setOrigin] = useState('ICN')
  const [destination, setDestination] = useState('NRT')
  const [earliest, setEarliest] = useState('')
  const [latest, setLatest] = useState('')
  const [nights, setNights] = useState(3)
  const [adults, setAdults] = useState(1)

  const today = new Date().toISOString().split('T')[0]

  const handleEarliest = (v) => {
    setEarliest(v)
    if (!latest || latest < v) {
      setLatest(addDays(v, 6))
    } else if (v && latest > addDays(v, MAX_SCAN_DAYS - 1)) {
      setLatest(addDays(v, MAX_SCAN_DAYS - 1))
    }
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    onSearch({
      origin,
      destination,
      earliest_departure: earliest,
      latest_departure: latest,
      nights,
      adults,
    })
  }

  const scanCount = earliest && latest
    ? Math.min(Math.floor((new Date(latest) - new Date(earliest)) / 86400000) + 1, MAX_SCAN_DAYS)
    : 0

  return (
    <form className="search-form" onSubmit={handleSubmit}>
      <p className="form-hint">
        출발 가능한 날짜 범위를 정하면, 날짜별 왕복 최저가를 비교해서 가장 싼 출발일을 찾아드립니다.
      </p>
      <div className="form-row">
        <div className="form-group">
          <label>출발지</label>
          <select value={origin} onChange={e => setOrigin(e.target.value)}>
            {Object.entries(airports.origins).map(([code, name]) => (
              <option key={code} value={code}>{name} ({code})</option>
            ))}
          </select>
        </div>
        <div className="form-group">
          <label>여행지</label>
          <select value={destination} onChange={e => setDestination(e.target.value)}>
            <optgroup label="해외">
              {Object.entries(airports.destinations).map(([code, info]) => (
                <option key={code} value={code}>{info.name} ({code})</option>
              ))}
            </optgroup>
            <optgroup label="국내">
              {Object.entries(airports.domestic_destinations || {}).map(([code, info]) => (
                <option key={code} value={code}>{info.name} ({code})</option>
              ))}
            </optgroup>
          </select>
        </div>
        <div className="form-group">
          <label>여행 기간</label>
          <select value={nights} onChange={e => setNights(Number(e.target.value))}>
            {[1,2,3,4,5,6,7,8,9,10,12,14].map(n => (
              <option key={n} value={n}>{n}박 {n + 1}일</option>
            ))}
          </select>
        </div>
        <div className="form-group">
          <label>성인</label>
          <select value={adults} onChange={e => setAdults(Number(e.target.value))}>
            {[1,2,3,4,5].map(n => (
              <option key={n} value={n}>{n}명</option>
            ))}
          </select>
        </div>
      </div>

      <div className="form-row">
        <div className="form-group">
          <label>가장 빠른 출발일</label>
          <input
            type="date"
            value={earliest}
            onChange={e => handleEarliest(e.target.value)}
            min={today}
            required
          />
        </div>
        <div className="form-group">
          <label>가장 늦은 출발일 (최대 {MAX_SCAN_DAYS}일 범위)</label>
          <input
            type="date"
            value={latest}
            onChange={e => setLatest(e.target.value)}
            min={earliest || today}
            max={earliest ? addDays(earliest, MAX_SCAN_DAYS - 1) : undefined}
            required
          />
        </div>
      </div>

      <button type="submit" className="search-btn" disabled={loading || !earliest || !latest}>
        {loading
          ? `날짜별 최저가 비교 중... (${scanCount}개 출발일 조회)`
          : '최저가 날짜 찾기'}
      </button>
    </form>
  )
}

export default BestDatesForm
