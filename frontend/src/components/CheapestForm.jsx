import { useState } from 'react'

function CheapestForm({ airports, onSearch, loading }) {
  const [origin, setOrigin] = useState('ICN')
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
      origin,
      departure_date: departureDate,
      return_date: returnDate || null,
      adults,
      children,
      infants_in_seat: infantsSeat,
      infants_on_lap: infantsLap,
    })
  }

  return (
    <form className="search-form" onSubmit={handleSubmit}>
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
        {loading ? '검색 중... (25개 도시 조회)' : '최저가 목적지 찾기'}
      </button>
    </form>
  )
}

export default CheapestForm
