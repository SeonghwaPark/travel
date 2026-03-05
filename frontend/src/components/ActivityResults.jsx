function formatPrice(price) {
  return Number(price).toLocaleString('ko-KR')
}

function ActivityResults({ activities }) {
  if (activities.length === 0) {
    return <div className="no-results">검색 결과가 없습니다</div>
  }

  return (
    <div>
      <h2 className="results-header">액티비티 검색 결과 ({activities.length}건)</h2>
      <div className="activity-grid">
        {activities.map((act, idx) => (
          <div key={idx} className="activity-card">
            {act.picture && (
              <div className="activity-img">
                <img src={act.picture} alt={act.name} />
              </div>
            )}
            <div className="activity-body">
              <div className="activity-name">{act.name}</div>
              {act.description && (
                <div className="activity-desc">{act.description}</div>
              )}
              <div className="activity-meta">
                {act.rating && <span>평점 {act.rating}</span>}
                {act.review_count > 0 && <span>리뷰 {act.review_count}건</span>}
                {act.duration && <span>{act.duration}</span>}
              </div>
              <div className="activity-bottom">
                <div className="activity-price">
                  <span className="price">{formatPrice(act.price.amount)}</span>
                  <span className="currency"> {act.price.currency}</span>
                </div>
                {act.booking_link && (
                  <a
                    className="booking-link"
                    href={act.booking_link}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    예약하기
                  </a>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default ActivityResults
