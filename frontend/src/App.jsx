import { useState, useEffect } from 'react'
import SearchForm from './components/SearchForm'
import FlightResults from './components/FlightResults'
import CheapestForm from './components/CheapestForm'
import CheapestResults from './components/CheapestResults'
import HotelForm from './components/HotelForm'
import HotelResults from './components/HotelResults'
import ActivityForm from './components/ActivityForm'
import ActivityResults from './components/ActivityResults'
import './App.css'

const API = 'http://localhost:8000/api'

function useSearch(url) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [searched, setSearched] = useState(false)

  const search = async (params) => {
    setLoading(true)
    setError(null)
    setSearched(true)
    try {
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(params),
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || '검색 중 오류가 발생했습니다')
      }
      setData(await res.json())
    } catch (e) {
      setError(e.message)
      setData(null)
    } finally {
      setLoading(false)
    }
  }

  return { data, loading, error, searched, search }
}

function App() {
  const [airports, setAirports] = useState({ origins: {}, destinations: {} })
  const [tab, setTab] = useState('search')

  const flights = useSearch(`${API}/flights/search`)
  const cheapest = useSearch(`${API}/flights/cheapest-destinations`)
  const hotels = useSearch(`${API}/hotels/search`)
  const activities = useSearch(`${API}/activities/search`)

  useEffect(() => {
    fetch(`${API}/airports`)
      .then(res => res.json())
      .then(setAirports)
      .catch(() => {})
  }, [])

  const tabs = [
    { id: 'search', label: '항공편' },
    { id: 'cheapest', label: '최저가 목적지' },
    { id: 'hotels', label: '호텔' },
    { id: 'activities', label: '액티비티' },
  ]

  return (
    <div className="app">
      <header className="header">
        <h1>여행 검색</h1>
        <p>한국 출발 해외여행 항공편, 숙박, 액티비티를 한번에</p>
      </header>

      <div className="tabs">
        {tabs.map(t => (
          <button
            key={t.id}
            className={`tab ${tab === t.id ? 'tab-active' : ''}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      <main>
        {tab === 'search' && (
          <>
            <SearchForm airports={airports} onSearch={flights.search} loading={flights.loading} />
            {flights.error && <div className="error-msg">{flights.error}</div>}
            {flights.loading && <div className="loading">항공편을 검색하고 있습니다... (최대 3회 시도)</div>}
            {!flights.loading && flights.searched && flights.data?.message && (
              <div className="error-msg">{flights.data.message}</div>
            )}
            {!flights.loading && flights.searched && (
              <FlightResults flights={flights.data?.flights || []} bookingLinks={flights.data?.booking_links} />
            )}
          </>
        )}

        {tab === 'cheapest' && (
          <>
            <CheapestForm airports={airports} onSearch={cheapest.search} loading={cheapest.loading} />
            {cheapest.error && <div className="error-msg">{cheapest.error}</div>}
            {cheapest.loading && <div className="loading">25개 도시 최저가를 비교하고 있습니다...</div>}
            {!cheapest.loading && cheapest.searched && (
              <CheapestResults destinations={cheapest.data?.destinations || []} />
            )}
          </>
        )}

        {tab === 'hotels' && (
          <>
            <HotelForm airports={airports} onSearch={hotels.search} loading={hotels.loading} />
            {hotels.error && <div className="error-msg">{hotels.error}</div>}
            {hotels.loading && <div className="loading">호텔을 검색하고 있습니다...</div>}
            {!hotels.loading && hotels.searched && (
              <HotelResults hotels={hotels.data?.hotels || []} />
            )}
          </>
        )}

        {tab === 'activities' && (
          <>
            <ActivityForm airports={airports} onSearch={activities.search} loading={activities.loading} />
            {activities.error && <div className="error-msg">{activities.error}</div>}
            {activities.loading && <div className="loading">액티비티를 검색하고 있습니다...</div>}
            {!activities.loading && activities.searched && (
              <ActivityResults activities={activities.data?.activities || []} />
            )}
          </>
        )}
      </main>
    </div>
  )
}

export default App
