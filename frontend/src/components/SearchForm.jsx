import { useState } from 'react'

function SearchForm({ airports, onSearch, loading }) {
  const [origin, setOrigin] = useState('ICN')
  const [destination, setDestination] = useState('NRT')
  const [departureDate, setDepartureDate] = useState('')
  const [returnDate, setReturnDate] = useState('')
  const [adults, setAdults] = useState(1)
  const [children, setChildren] = useState(0)
  const [infantsSeat, setInfantsSeat] = useState(0)
  const [infantsLap, setInfantsLap] = useState(0)
  const [nonstop, setNonstop] = useState(false)

  const today = new Date().toISOString().split('T')[0]

  const handleSubmit = (e) => {
    e.preventDefault()
    onSearch({
      origin,
      destination,
      departure_date: departureDate,
      return_date: returnDate || null,
      adults,
      children,
      infants_in_seat: infantsSeat,
      infants_on_lap: infantsLap,
      nonstop,
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
          <label>도착지</label>
          <select value={destination} onChange={e => setDestination(e.target.value)}>
            {Object.entries(airports.destinations).map(([code, info]) => (
              <option key={code} value={code}>
                {info.name} ({code}) - {info.country}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="form-row">
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

      <div className="form-options">
        <label>
          <input
            type="checkbox"
            checked={nonstop}
            onChange={e => setNonstop(e.target.checked)}
          />
          직항만 검색
        </label>
      </div>

      <button type="submit" className="search-btn" disabled={loading || !departureDate}>
        {loading ? '검색 중...' : '항공편 검색'}
      </button>
    </form>
  )
}

export default SearchForm
