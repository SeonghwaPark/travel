import { useState, useEffect } from 'react'
import SearchForm from './components/SearchForm'
import FlightResults from './components/FlightResults'
import CheapestForm from './components/CheapestForm'
import CheapestResults from './components/CheapestResults'
import HotelForm from './components/HotelForm'
import HotelResults from './components/HotelResults'
import ActivityForm from './components/ActivityForm'
import ActivityResults from './components/ActivityResults'
import DomesticForm from './components/DomesticForm'
import DomesticResults from './components/DomesticResults'
import AirlineDeals from './components/AirlineDeals'
import SpotSearch from './components/SpotSearch'
import TripPlanner from './components/TripPlanner'
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
  const [domesticSearch, setDomesticSearch] = useState(null)
  const [tab, setTab] = useState('search')

  const flights = useSearch(`${API}/flights/search`)
  const cheapest = useSearch(`${API}/flights/cheapest-destinations`)
  const hotels = useSearch(`${API}/hotels/search`)
  const activities = useSearch(`${API}/activities/search`)

  useEffect(() => {
    fetch(`${API}/airports`).then(r => r.json()).then(setAirports).catch(() => {})
  }, [])

  const tabs = [
    { id: 'search', label: '항공편' },
    { id: 'cheapest', label: '최저가 목적지' },
    { id: 'hotels', label: '해외 호텔' },
    { id: 'activities', label: '해외 액티비티' },
    { id: 'domestic', label: '국내여행' },
    { id: 'airline-deals', label: '항공사 특가' },
    { id: 'spots', label: '맛집·관광지' },
    { id: 'planner', label: '여행 일정' },
  ]

  return (
    <div className="app">
      <header className="header">
        <h1>Travel Search</h1>
        <p>항공편, 숙박, 맛집, 일정까지 한번에 검색하세요</p>
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
              <CheapestResults destinations={cheapest.data?.destinations || []} mode={cheapest.data?.mode || 'international'} />
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

        {tab === 'domestic' && (
          <>
            <DomesticForm onSearch={setDomesticSearch} loading={false} />
            {domesticSearch && (
              <DomesticResults
                regionName={domesticSearch.regionName}
                keyword={domesticSearch.keyword}
                checkIn={domesticSearch.check_in}
                checkOut={domesticSearch.check_out}
                adults={domesticSearch.adults}
              />
            )}
          </>
        )}

        {tab === 'airline-deals' && (
          <AirlineDeals />
        )}

        {tab === 'spots' && (
          <SpotSearch />
        )}

        {tab === 'planner' && (
          <TripPlanner />
        )}
      </main>
    </div>
  )
}

export default App
