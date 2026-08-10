function formatPrice(price) {
  return Number(price).toLocaleString('ko-KR')
}

function formatDate(dateStr) {
  const d = new Date(dateStr)
  const days = ['일', '월', '화', '수', '목', '금', '토']
  return `${d.getMonth() + 1}/${d.getDate()} (${days[d.getDay()]})`
}

function stopsText(stops) {
  if (typeof stops === 'number') {
    return stops === 0 ? '직항' : `경유 ${stops}회`
  }
  return stops || ''
}

function BestDatesResults({ data }) {
  if (!data || data.count === 0) {
    return <div className="no-results">해당 기간에 항공편을 찾지 못했습니다. 날짜 범위를 바꿔서 다시 시도해보세요.</div>
  }

  const results = data.results
  const maxPrice = Math.max(...results.map(r => Number(r.price.total)))
  const minPrice = Number(results[0].price.total)

  return (
    <div>
      <h2 className="results-header">
        {data.destination_name} {data.nights}박 {data.nights + 1}일 · 출발일별 최저가 ({data.count}개 날짜)
      </h2>
      <div className="price-source-notice">
        Google Flights 왕복 기준 가격입니다. 실제 예약 시 가격이 다를 수 있으니 각 사이트에서 확인하세요.
        {data.truncated && ' 날짜 범위가 길어 앞쪽 14일만 조회했습니다.'}
      </div>

      {data.cheapest && (
        <div className="best-date-banner">
          <div className="best-date-label">가장 저렴한 출발일</div>
          <div className="best-date-main">
            {formatDate(data.cheapest.departure_date)} 출발 → {formatDate(data.cheapest.return_date)} 귀국
          </div>
          <div className="best-date-price">₩{formatPrice(data.cheapest.price.total)}</div>
          {data.average_price && minPrice < data.average_price && (
            <div className="best-date-save">
              기간 평균(₩{formatPrice(data.average_price)})보다 ₩{formatPrice(data.average_price - minPrice)} 저렴
            </div>
          )}
        </div>
      )}

      <div className="dest-list">
        {results.map((r, idx) => (
          <div key={r.departure_date} className="dest-card">
            <div className="dest-rank">
              <span className={`rank-number rank-${idx < 3 ? idx + 1 : 'other'}`}>
                {idx + 1}
              </span>
            </div>
            <div className="dest-info">
              <div className="dest-name">
                {formatDate(r.departure_date)} 출발
                <span className="dest-country">{formatDate(r.return_date)} 귀국</span>
              </div>
              <div className="dest-detail">
                {r.airline ? <span>{r.airline}</span> : <span style={{color:'#999'}}>항공사 정보 없음</span>}
                {r.duration && <span>{r.duration}</span>}
                {r.departure && r.arrival && <span>{r.departure} → {r.arrival}</span>}
                <span>{stopsText(r.stops)}</span>
              </div>
              <div className="price-bar-track">
                <div
                  className="price-bar-fill"
                  style={{ width: `${Math.max(8, (Number(r.price.total) / maxPrice) * 100)}%` }}
                />
              </div>
              {r.booking_links && (
                <div className="booking-links">
                  <a className="booking-link" href={r.booking_links.google_flights} target="_blank" rel="noopener noreferrer">
                    Google Flights에서 확인
                  </a>
                  {r.booking_links.naver_flights && (
                    <a className="booking-link" href={r.booking_links.naver_flights} target="_blank" rel="noopener noreferrer">
                      네이버 항공에서 확인
                    </a>
                  )}
                  {r.booking_links.kayak && (
                    <a className="booking-link" href={r.booking_links.kayak} target="_blank" rel="noopener noreferrer">
                      Kayak에서 확인
                    </a>
                  )}
                  {r.booking_links.trip_com && (
                    <a className="booking-link" href={r.booking_links.trip_com} target="_blank" rel="noopener noreferrer">
                      Trip.com에서 확인
                    </a>
                  )}
                </div>
              )}
            </div>
            <div className="dest-price">
              <div className="price-source">Google Flights</div>
              <div className="price">₩{formatPrice(r.price.total)}</div>
              <div className="currency">왕복 기준</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default BestDatesResults
