import { useState } from 'react'

function ActivityForm({ airports, onSearch, loading }) {
  const [destination, setDestination] = useState('NRT')

  const handleSubmit = (e) => {
    e.preventDefault()
    onSearch({ destination })
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

      <button type="submit" className="search-btn" disabled={loading}>
        {loading ? '검색 중...' : '액티비티 검색'}
      </button>
    </form>
  )
}

export default ActivityForm
