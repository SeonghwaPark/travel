import { useState } from 'react'

const DOMESTIC_ORIGINS = {
  GMP: '김포국제공항',
  ICN: '인천국제공항',
  PUS: '김해국제공항',
  TAE: '대구국제공항',
  CJU: '제주국제공항',
}

function CheapestForm({ airports, onSearch, loading }) {
  const [mode, setMode] = useState('international')
  const [origin, setOrigin] = useState('ICN')
  const [domesticOrigin, setDomesticOrigin] = useState('GMP')
  const [departureDate, setDepartureDate] = useState('')
  const [returnDate, setReturnDate] = useState('')
  const [adults, setAdults] = useState(1)
  const [children, setChildren] = useState(0)
  const [infantsSeat, setInfantsSeat] = useState(0)
  const [infantsLap, setInfantsLap] = useState(0)

  const today = new Date().toISOString().split('T')[0]

  const handleSubmit = (e) => {
    e.preventDefault()
    onSearch({
      origin: mode === 'domestic' ? domesticOrigin : origin,
      departure_date: departureDate,
      return_date: returnDate || null,
      adults,
      children,
      infants_in_seat: infantsSeat,
      infants_on_lap: infantsLap,
      mode,
    })
  }

  const destCount = mode === 'domestic' ? 12 : 25

  return (
    <form className="search-form" onSubmit={handleSubmit}>
      {/* 국내/해외 토글 */}
      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
        {[
          { id: 'international', label: '해외 최저가' },
          { id: 'domestic',      label: '국내 최저가' },
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
          {mode === 'domestic' ? (
            <select value={domesticOrigin} onChange={e => setDomesticOrigin(e.target.value)}>
              {Object.entries(DOMESTIC_ORIGINS).map(([code, name]) => (
                <option key={code} value={code}>{name} ({code})</option>
              ))}
            </select>
          ) : (
            <select value={origin} onChange={e => setOrigin(e.target.value)}>
              {Object.entries(airports.origins).map(([code, name]) => (
                <option key={code} value={code}>{name} ({code})</option>
              ))}
            </select>
          )}
        </div>
        <div className="form-group">
          <label>출발일</label>
          <input
            type="date"
            value={departureDate}
            onChange={e => setDepartureDate(e.target.value)}
            min={today}
            required
          />
        </div>
        <div className="form-group">
          <label>귀국일 (선택)</label>
          <input
            type="date"
            value={returnDate}
            onChange={e => setReturnDate(e.target.value)}
            min={departureDate || today}
          />
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
          <label>소아 (2~11세)</label>
          <select value={children} onChange={e => setChildren(Number(e.target.value))}>
            {[0,1,2,3,4].map(n => (
              <option key={n} value={n}>{n}명</option>
            ))}
          </select>
        </div>
        <div className="form-group">
          <label>좌석 유아 (2세 미만)</label>
          <select value={infantsSeat} onChange={e => setInfantsSeat(Number(e.target.value))}>
            {[0,1,2].map(n => (
              <option key={n} value={n}>{n}명</option>
            ))}
          </select>
        </div>
        <div className="form-group">
          <label>무릎 유아 (2세 미만)</label>
          <select value={infantsLap} onChange={e => setInfantsLap(Number(e.target.value))}>
            {[0,1,2].map(n => (
              <option key={n} value={n}>{n}명</option>
            ))}
          </select>
        </div>
      </div>

      <button type="submit" className="search-btn" disabled={loading || !departureDate}>
        {loading
          ? `검색 중... (${destCount}개 도시 조회)`
          : `${mode === 'domestic' ? '국내' : '해외'} 최저가 목적지 찾기`}
      </button>
    </form>
  )
}

export default CheapestForm
