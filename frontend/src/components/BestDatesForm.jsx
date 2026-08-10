import { useState } from 'react'

const MAX_SCAN_DAYS = 14

function addDays(dateStr, days) {
  const d = new Date(dateStr)
  d.setDate(d.getDate() + days)
  return d.toISOString().split('T')[0]
}

const HORIZONS = [
  { id: 30, label: '한 달 안에' },
  { id: 60, label: '두 달 안에' },
  { id: 90, label: '세 달 안에' },
  { id: 150, label: '다섯 달 안에' },
]

function BestDatesForm({ airports, onSearch, loading }) {
  const [mode, setMode] = useState('anytime') // 'anytime' | 'range'
  const [origin, setOrigin] = useState('ICN')
  const [destination, setDestination] = useState('KIX')
  const [horizon, setHorizon] = useState(60)
  const [earliest, setEarliest] = useState('')
  const [latest, setLatest] = useState('')
  const [minNights, setMinNights] = useState(2)
  const [maxNights, setMaxNights] = useState(4)
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

  const handleMinNights = (v) => {
    setMinNights(v)
    if (maxNights < v) setMaxNights(v)
    else if (maxNights - v > 3) setMaxNights(v + 3)
  }

  const handleMaxNights = (v) => {
    setMaxNights(v)
    if (minNights > v) setMinNights(v)
    else if (v - minNights > 3) setMinNights(v - 3)
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    const params = {
      origin,
      destination,
      min_nights: minNights,
      max_nights: maxNights,
      adults,
    }
    if (mode === 'anytime') {
      params.earliest_departure = addDays(today, 3)
      params.latest_departure = addDays(today, horizon)
    } else {
      params.earliest_departure = earliest
      params.latest_departure = latest
    }
    onSearch(params)
  }

  const canSubmit = mode === 'anytime' || (earliest && latest)

  return (
    <form className="search-form" onSubmit={handleSubmit}>
      <p className="form-hint">
        여행지만 정하면 됩니다. 시기가 미정이면 전체 기간에서 날짜를 골고루 뽑아 왕복 최저가를 비교하고,
        가장 싼 날짜부터 순서대로 보여드립니다.
      </p>

      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
        {[
          { id: 'anytime', label: '시기 미정 (전체 스캔)' },
          { id: 'range',   label: '날짜 범위 지정' },
        ].map(m => (
          <button
            key={m.id}
            type="button"
            onClick={() => setMode(m.id)}
            style={{
              padding: '6px 18px',
              borderRadius: '20px',
              border: '1.5px solid',
              borderColor: mode === m.id ? '#3182ce' : '#cbd5e0',
              background: mode === m.id ? '#3182ce' : 'white',
              color: mode === m.id ? 'white' : '#4a5568',
              fontWeight: 600,
              fontSize: '0.88rem',
              cursor: 'pointer',
            }}
          >
            {m.label}
          </button>
        ))}
      </div>

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
          <label>여행 기간 (최소)</label>
          <select value={minNights} onChange={e => handleMinNights(Number(e.target.value))}>
            {[1,2,3,4,5,6,7,8,9,10,12,14].map(n => (
              <option key={n} value={n}>{n}박부터</option>
            ))}
          </select>
        </div>
        <div className="form-group">
          <label>여행 기간 (최대)</label>
          <select value={maxNights} onChange={e => handleMaxNights(Number(e.target.value))}>
            {[1,2,3,4,5,6,7,8,9,10,12,14].map(n => (
              <option key={n} value={n}>{n}박까지</option>
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

      {mode === 'anytime' ? (
        <div className="form-row">
          <div className="form-group">
            <label>언제까지의 출발일을 볼까요?</label>
            <select value={horizon} onChange={e => setHorizon(Number(e.target.value))}>
              {HORIZONS.map(h => (
                <option key={h.id} value={h.id}>{h.label}</option>
              ))}
            </select>
          </div>
        </div>
      ) : (
        <div className="form-row">
          <div className="form-group">
            <label>가장 빠른 출발일</label>
            <input
              type="date"
              value={earliest}
              onChange={e => handleEarliest(e.target.value)}
              min={today}
              required={mode === 'range'}
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
              required={mode === 'range'}
            />
          </div>
        </div>
      )}

      <button type="submit" className="search-btn" disabled={loading || !canSubmit}>
        {loading
          ? '날짜·기간 조합별 최저가 비교 중...'
          : '가장 싼 시기 찾기'}
      </button>
    </form>
  )
}

export default BestDatesForm
