function HotelResults({ hotels }) {
  if (hotels.length === 0) {
    return <div className="no-results">검색 결과가 없습니다</div>
  }

  return (
    <div>
      <h2 className="results-header">호텔 예약 사이트 ({hotels.length}곳)</h2>
      {hotels.map((hotel, idx) => (
        <div key={hotel.hotel_id || idx} className="hotel-card">
          <div className="hotel-info">
            <div className="hotel-name">{hotel.name}</div>
            <div className="hotel-detail">
              <span>{hotel.check_in} ~ {hotel.check_out}</span>
            </div>
            {hotel.description && (
              <div className="hotel-desc">{hotel.description}</div>
            )}
            {hotel.booking_link && (
              <a className="booking-link" href={hotel.booking_link} target="_blank" rel="noopener noreferrer">
                검색하러 가기
              </a>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}

export default HotelResults
