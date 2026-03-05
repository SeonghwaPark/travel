function formatPrice(price) {
  return Number(price).toLocaleString('ko-KR')
}

function stopsText(stops) {
  if (stops === 0) return '직항'
  return `경유 ${stops}회`
}

function FlightResults({ flights, bookingLinks }) {
  if (flights.length === 0) {
    return (
      <div className="no-results">
        <p>검색 결과가 없습니다</p>
        {bookingLinks && (
          <div style={{ marginTop: '12px' }}>
            <p>외부 사이트에서 직접 검색해보세요:</p>
            <div className="booking-links" style={{ marginTop: '8px' }}>
              <a className="booking-link" href={bookingLinks.google_flights} target="_blank" rel="noopener noreferrer">Google Flights</a>
              <a className="booking-link" href={bookingLinks.kayak} target="_blank" rel="noopener noreferrer">Kayak</a>
              <a className="booking-link" href={bookingLinks.trip_com} target="_blank" rel="noopener noreferrer">Trip.com</a>
            </div>
          </div>
        )}
      </div>
    )
  }

  return (
    <div>
      <h2 className="results-header">검색 결과 ({flights.length}건)</h2>
      <div className="price-source-notice">
        Google Flights 왕복 기준 가격입니다. 실제 예약 시 가격이 다를 수 있으니 아래 링크에서 확인하세요.
      </div>
      {flights.map((flight, idx) => (
        <div key={flight.id || idx} className="flight-card">
          <div className="flight-info">
            {flight.itineraries.map((itin, i) => (
              <div key={i} className="itinerary-section">
                <div className="flight-route">
                  <span className="flight-airport">
                    {itin.segments[0].departure_airport}
                  </span>
                  <span className="flight-arrow">→</span>
                  <span className="flight-airport">
                    {itin.segments[itin.segments.length - 1].arrival_airport}
                  </span>
                  <span className={`stops-badge stops-${Math.min(itin.stops, 2)}`}>
                    {stopsText(itin.stops)}
                  </span>
                </div>
                {itin.segments[0].departure_time && (
                  <div className="flight-time">
                    {itin.segments[0].departure_time} → {itin.segments[itin.segments.length - 1].arrival_time}
                  </div>
                )}
                <div className="flight-meta">
                  {itin.duration && <span>{itin.duration}</span>}
                  {itin.segments[0].carrier && (
                    <span>{itin.segments[0].carrier}</span>
                  )}
                </div>
              </div>
            ))}
            {flight.booking_links && (
              <div className="booking-links">
                <a className="booking-link" href={flight.booking_links.google_flights} target="_blank" rel="noopener noreferrer">
                  Google Flights에서 확인
                </a>
                <a className="booking-link" href={flight.booking_links.kayak} target="_blank" rel="noopener noreferrer">
                  Kayak에서 확인
                </a>
                <a className="booking-link" href={flight.booking_links.trip_com} target="_blank" rel="noopener noreferrer">
                  Trip.com에서 확인
                </a>
              </div>
            )}
          </div>
          <div className="flight-price">
            <div className="price-source">Google Flights</div>
            <div className="price">₩{formatPrice(flight.price.total)}</div>
            <div className="currency">왕복 기준</div>
          </div>
        </div>
      ))}
    </div>
  )
}

export default FlightResults
