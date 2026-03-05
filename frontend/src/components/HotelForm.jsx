import { useState } from 'react'

function HotelForm({ airports, onSearch, loading }) {
  const [destination, setDestination] = useState('NRT')
  const [checkIn, setCheckIn] = useState('')
  const [checkOut, setCheckOut] = useState('')
  const [adults, setAdults] = useState(1)

  const today = new Date().toISOString().split('T')[0]

  const handleSubmit = (e) => {
    e.preventDefault()
    onSearch({
      destination,
      check_in: checkIn,
      check_out: checkOut,
      adults,
    })
  }

  return (
    <form className="search-form" onSubmit={handleSubmit}>
      <div className="form-row">
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
          <label>체크인</label>
          <input
            type="date"
            value={checkIn}
            onChange={e => setCheckIn(e.target.value)}
            min={today}
            required
          />
        </div>
        <div className="form-group">
          <label>체크아웃</label>
          <input
            type="date"
            value={checkOut}
            onChange={e => setCheckOut(e.target.value)}
            min={checkIn || today}
            required
          />
        </div>
        <div className="form-group">
          <label>인원</label>
          <select value={adults} onChange={e => setAdults(Number(e.target.value))}>
            {[1,2,3,4].map(n => (
              <option key={n} value={n}>{n}명</option>
            ))}
          </select>
        </div>
      </div>

      <button type="submit" className="search-btn" disabled={loading || !checkIn || !checkOut}>
        {loading ? '검색 중...' : '호텔 검색'}
      </button>
    </form>
  )
}

export default HotelForm
