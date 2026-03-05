import { useState } from 'react'

function formatPrice(price) {
  return Number(price).toLocaleString('ko-KR')
}

function stopsText(stops) {
  if (typeof stops === 'number') {
    return stops === 0 ? '직항' : `경유 ${stops}회`
  }
  return stops || ''
}

function CheapestResults({ destinations }) {
  const [expanded, setExpanded] = useState({})

  if (destinations.length === 0) {
    return <div className="no-results">검색 결과가 없습니다</div>
  }

  const toggle = (code) => {
    setExpanded(prev => ({ ...prev, [code]: !prev[code] }))
  }

  return (
    <div>
      <h2 className="results-header">
        최저가 목적지 순위 ({destinations.length}개 도시)
      </h2>
      <div className="price-source-notice">
        Google Flights 왕복 기준 가격입니다. 실제 예약 시 가격이 다를 수 있으니 각 사이트에서 확인하세요.
      </div>
      <div className="dest-list">
        {destinations.map((dest, idx) => (
          <div key={dest.destination_code} className="dest-card">
            <div className="dest-rank">
              <span className={`rank-number rank-${idx < 3 ? idx + 1 : 'other'}`}>
                {idx + 1}
              </span>
            </div>
            <div className="dest-info">
              <div className="dest-name">
                {dest.destination_name}
                <span className="dest-country">{dest.country}</span>
                <span className="dest-code">{dest.destination_code}</span>
              </div>
              <div className="dest-detail">
                {dest.airline ? <span>{dest.airline}</span> : <span style={{color:'#999'}}>항공사 정보 없음</span>}
                {dest.duration && <span>{dest.duration}</span>}
                {dest.departure && dest.arrival && (
                  <span>{dest.departure} → {dest.arrival}</span>
                )}
                <span>{stopsText(dest.stops)}</span>
              </div>

              {dest.alternatives && dest.alternatives.length > 1 && (
                <button
                  className="alt-toggle"
                  onClick={() => toggle(dest.destination_code)}
                >
                  {expanded[dest.destination_code]
                    ? '접기 ▲'
                    : `다른 항공편 ${dest.alternatives.length - 1}개 더보기 ▼`}
                </button>
              )}

              {expanded[dest.destination_code] && dest.alternatives && (
                <div className="alt-list">
                  {dest.alternatives.slice(1).map((alt, i) => (
                    <div key={i} className="alt-item">
                      <span className="alt-price">₩{formatPrice(alt.price)}</span>
                      <span className="alt-airline">{alt.airline || '-'}</span>
                      {alt.duration && <span>{alt.duration}</span>}
                      {alt.departure && alt.arrival && (
                        <span>{alt.departure} → {alt.arrival}</span>
                      )}
                      <span>{stopsText(alt.stops)}</span>
                    </div>
                  ))}
                </div>
              )}

              {dest.booking_links && (
                <div className="booking-links">
                  <a className="booking-link" href={dest.booking_links.google_flights} target="_blank" rel="noopener noreferrer">
                    Google Flights에서 확인
                  </a>
                  <a className="booking-link" href={dest.booking_links.kayak} target="_blank" rel="noopener noreferrer">
                    Kayak에서 확인
                  </a>
                  <a className="booking-link" href={dest.booking_links.trip_com} target="_blank" rel="noopener noreferrer">
                    Trip.com에서 확인
                  </a>
                </div>
              )}
            </div>
            <div className="dest-price">
              <div className="price-source">Google Flights</div>
              <div className="price">₩{formatPrice(dest.price.total)}</div>
              <div className="currency">왕복 기준</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default CheapestResults
