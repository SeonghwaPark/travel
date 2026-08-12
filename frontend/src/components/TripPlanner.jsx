import { useState } from 'react'

const API = 'http://localhost:8000/api'
const today = new Date().toISOString().slice(0, 10)
const in3days = new Date(Date.now() + 3 * 86400000).toISOString().slice(0, 10)

const DESTINATIONS = [
  { group: '제주', items: ['제주 전체', '제주시', '서귀포'] },
  { group: '남부', items: ['부산', '남해', '통영', '여수', '경주', '거제'] },
  { group: '강원', items: ['속초', '강릉', '양양', '춘천', '평창'] },
  { group: '전라', items: ['전주', '목포', '담양', '순천'] },
  { group: '충청', items: ['대전', '단양', '보령'] },
  { group: '수도권', items: ['서울', '인천', '가평'] },
]

const CATEGORY_COLORS = {
  '관광지': { bg: '#ebf8ff', color: '#2b6cb0' },
  '맛집': { bg: '#fff5f5', color: '#e53e3e' },
  '카페': { bg: '#fefcbf', color: '#975a16' },
  '숙소': { bg: '#f0fff4', color: '#276749' },
  '이동': { bg: '#f7fafc', color: '#718096' },
  '체험': { bg: '#faf5ff', color: '#6b46c1' },
}

function TripPlanner() {
  const [destination, setDestination] = useState('제주 전체')
  const [startDate, setStartDate] = useState(today)
  const [endDate, setEndDate] = useState(in3days)
  const [travelers, setTravelers] = useState('성인 2명')
  const [preferences, setPreferences] = useState('')
  const [plan, setPlan] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [expandedDay, setExpandedDay] = useState(null)

  const handleGenerate = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    setPlan(null)
    try {
      const res = await fetch(`${API}/trip/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          destination,
          start_date: startDate,
          end_date: endDate,
          travelers,
          preferences,
        }),
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || '일정 생성 실패')
      }
      const data = await res.json()
      if (data.error) throw new Error(data.error)
      setPlan(data)
      setExpandedDay(0)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      {/* 입력 폼 */}
      <form className="search-form" onSubmit={handleGenerate}>
        <div style={{ marginBottom: '14px' }}>
          <p style={{ color: '#718096', fontSize: '0.88rem', lineHeight: 1.5 }}>
            여행지와 기간만 정하면 AI가 동선, 맛집, 숙소까지 포함한 완벽한 여행 코스를 짜드립니다.
          </p>
        </div>
        <div className="form-row">
          <div className="form-group" style={{ flex: 2 }}>
            <label>여행지</label>
            <select value={destination} onChange={e => setDestination(e.target.value)}>
              {DESTINATIONS.map(g => (
                <optgroup key={g.group} label={g.group}>
                  {g.items.map(d => (
                    <option key={d} value={d}>{d}</option>
                  ))}
                </optgroup>
              ))}
            </select>
          </div>
          <div className="form-group">
            <label>시작일</label>
            <input type="date" value={startDate} onChange={e => setStartDate(e.target.value)} />
          </div>
          <div className="form-group">
            <label>종료일</label>
            <input type="date" value={endDate} min={startDate} onChange={e => setEndDate(e.target.value)} />
          </div>
        </div>
        <div className="form-row">
          <div className="form-group">
            <label>인원</label>
            <select value={travelers} onChange={e => setTravelers(e.target.value)}>
              <option>성인 1명</option>
              <option>성인 2명</option>
              <option>성인 2명 + 아이 1명</option>
              <option>성인 2명 + 아이 2명</option>
              <option>성인 3명</option>
              <option>성인 4명</option>
              <option>가족 3인 (부모+아이)</option>
              <option>가족 4인 (부모+아이2)</option>
              <option>친구 3~4명</option>
            </select>
          </div>
          <div className="form-group" style={{ flex: 2 }}>
            <label>선호사항 (선택)</label>
            <input
              type="text"
              placeholder="예: 해산물 좋아함, 아이가 5살, 사진 맛집 위주, 느긋한 일정"
              value={preferences}
              onChange={e => setPreferences(e.target.value)}
            />
          </div>
        </div>
        <button type="submit" className="search-btn" disabled={loading}>
          {loading ? 'AI가 여행 코스를 짜고 있습니다...' : 'AI 여행 일정 만들기'}
        </button>
      </form>

      {/* 로딩 */}
      {loading && (
        <div style={{
          textAlign: 'center', padding: '40px 20px',
          background: 'white', borderRadius: '16px',
          boxShadow: '0 2px 12px rgba(0,0,0,0.06)',
        }}>
          <div style={{ fontSize: '2rem', marginBottom: '12px', animation: 'pulse 1.5s infinite' }}>
            ✈
          </div>
          <p style={{ color: '#667eea', fontWeight: 700, fontSize: '1.05rem' }}>
            AI가 최적의 여행 코스를 짜고 있어요...
          </p>
          <p style={{ color: '#a0aec0', fontSize: '0.85rem', marginTop: '6px' }}>
            동선, 맛집, 숙소까지 꼼꼼하게 준비 중 (10~20초 소요)
          </p>
          <style>{`@keyframes pulse { 0%,100%{transform:scale(1)} 50%{transform:scale(1.2)} }`}</style>
        </div>
      )}

      {/* 에러 */}
      {error && <div className="error-msg">{error}</div>}

      {/* 결과 */}
      {plan && (
        <div>
          {/* 여행 요약 헤더 */}
          <div style={{
            background: 'linear-gradient(135deg, #667eea, #764ba2)',
            borderRadius: '16px', padding: '24px 28px', marginBottom: '16px',
            color: 'white', boxShadow: '0 4px 20px rgba(102,126,234,0.3)',
          }}>
            <h2 style={{ fontSize: '1.4rem', fontWeight: 800, marginBottom: '6px' }}>
              {plan.title}
            </h2>
            <p style={{ opacity: 0.9, fontSize: '0.92rem' }}>{plan.summary}</p>
            <div style={{ display: 'flex', gap: '8px', marginTop: '12px', flexWrap: 'wrap' }}>
              <span style={{ background: 'rgba(255,255,255,0.2)', borderRadius: '8px', padding: '4px 12px', fontSize: '0.82rem', fontWeight: 600 }}>
                {plan.days?.length || 0}일 코스
              </span>
              <span style={{ background: 'rgba(255,255,255,0.2)', borderRadius: '8px', padding: '4px 12px', fontSize: '0.82rem', fontWeight: 600 }}>
                {travelers}
              </span>
              {plan.budget_summary?.total && (
                <span style={{ background: 'rgba(255,255,255,0.2)', borderRadius: '8px', padding: '4px 12px', fontSize: '0.82rem', fontWeight: 600 }}>
                  예상 {plan.budget_summary.total}
                </span>
              )}
            </div>
          </div>

          {/* 날짜별 일정 */}
          {plan.days?.map((day, idx) => (
            <div key={idx} style={{
              background: 'white', borderRadius: '14px', marginBottom: '12px',
              boxShadow: '0 2px 8px rgba(0,0,0,0.05)', border: '1px solid rgba(0,0,0,0.04)',
              overflow: 'hidden',
            }}>
              {/* 날짜 헤더 (클릭으로 토글) */}
              <div
                onClick={() => setExpandedDay(expandedDay === idx ? null : idx)}
                style={{
                  padding: '16px 20px', cursor: 'pointer',
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  background: expandedDay === idx ? '#f7fafc' : 'white',
                  transition: 'background 0.15s',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <span style={{
                    display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                    width: '36px', height: '36px', borderRadius: '50%',
                    background: idx === 0 ? 'linear-gradient(135deg, #667eea, #764ba2)' : '#e2e8f0',
                    color: idx === 0 ? 'white' : '#4a5568',
                    fontWeight: 800, fontSize: '0.82rem',
                  }}>
                    {day.label || `D${idx + 1}`}
                  </span>
                  <div>
                    <div style={{ fontWeight: 700, color: '#2d3748', fontSize: '1rem' }}>
                      {day.date}
                    </div>
                    {day.theme && (
                      <div style={{ fontSize: '0.82rem', color: '#718096', marginTop: '2px' }}>
                        {day.theme}
                      </div>
                    )}
                  </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <span style={{ fontSize: '0.78rem', color: '#a0aec0' }}>
                    {day.items?.length || 0}개 일정
                  </span>
                  <span style={{
                    transition: 'transform 0.2s',
                    transform: expandedDay === idx ? 'rotate(180deg)' : 'rotate(0)',
                    color: '#a0aec0', fontSize: '0.9rem',
                  }}>
                    ▼
                  </span>
                </div>
              </div>

              {/* 일정 상세 */}
              {expandedDay === idx && (
                <div style={{ padding: '0 20px 20px' }}>
                  {/* 아이템 목록 */}
                  {day.items?.map((item, iIdx) => {
                    const catStyle = CATEGORY_COLORS[item.category] || { bg: '#f7fafc', color: '#718096' }
                    return (
                      <div key={iIdx} style={{
                        display: 'flex', gap: '14px', padding: '14px 0',
                        borderBottom: iIdx < day.items.length - 1 ? '1px solid #f0f4f8' : 'none',
                      }}>
                        {/* 시간 */}
                        <div style={{
                          minWidth: '52px', textAlign: 'center', paddingTop: '2px',
                        }}>
                          <div style={{ fontWeight: 700, color: '#667eea', fontSize: '0.88rem' }}>
                            {item.time}
                          </div>
                        </div>
                        {/* 세로 타임라인 */}
                        <div style={{
                          display: 'flex', flexDirection: 'column', alignItems: 'center',
                          minWidth: '20px',
                        }}>
                          <div style={{
                            width: '10px', height: '10px', borderRadius: '50%',
                            background: catStyle.color, marginTop: '5px', flexShrink: 0,
                          }} />
                          {iIdx < day.items.length - 1 && (
                            <div style={{ width: '2px', flex: 1, background: '#e2e8f0', marginTop: '4px' }} />
                          )}
                        </div>
                        {/* 내용 */}
                        <div style={{ flex: 1 }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px', flexWrap: 'wrap' }}>
                            <span style={{ fontWeight: 700, color: '#2d3748', fontSize: '0.95rem' }}>
                              {item.title}
                            </span>
                            <span style={{
                              fontSize: '0.7rem', fontWeight: 700,
                              background: catStyle.bg, color: catStyle.color,
                              padding: '2px 8px', borderRadius: '6px',
                            }}>
                              {item.category}
                            </span>
                          </div>
                          <p style={{ fontSize: '0.84rem', color: '#718096', lineHeight: 1.5, margin: '0 0 6px' }}>
                            {item.description}
                          </p>
                          <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', fontSize: '0.76rem', color: '#a0aec0' }}>
                            {item.duration && <span>{item.duration}</span>}
                            {item.cost && <span>{item.cost}</span>}
                            {item.address && <span>{item.address}</span>}
                          </div>
                        </div>
                      </div>
                    )
                  })}

                  {/* 숙소 추천 */}
                  {day.accommodation && (
                    <div style={{
                      marginTop: '16px', padding: '14px 18px',
                      background: 'linear-gradient(135deg, #f0fff4, #ebf8ff)',
                      borderRadius: '12px', border: '1px solid #c6f6d5',
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                        <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#276749', background: '#c6f6d5', padding: '2px 8px', borderRadius: '6px' }}>
                          숙소
                        </span>
                        <span style={{ fontWeight: 700, color: '#2d3748', fontSize: '0.95rem' }}>
                          {day.accommodation.name}
                        </span>
                        {day.accommodation.type && (
                          <span style={{ fontSize: '0.75rem', color: '#718096' }}>
                            ({day.accommodation.type})
                          </span>
                        )}
                      </div>
                      <p style={{ fontSize: '0.82rem', color: '#4a5568', margin: '0 0 4px' }}>
                        {day.accommodation.reason}
                      </p>
                      {day.accommodation.price_range && (
                        <span style={{ fontSize: '0.78rem', color: '#e53e3e', fontWeight: 600 }}>
                          {day.accommodation.price_range}
                        </span>
                      )}
                    </div>
                  )}

                  {/* 팁 */}
                  {day.tip && (
                    <div style={{
                      marginTop: '12px', padding: '10px 14px',
                      background: '#fffbeb', borderRadius: '10px', border: '1px solid #f6e05e',
                      fontSize: '0.82rem', color: '#975a16',
                    }}>
                      <strong>TIP:</strong> {day.tip}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}

          {/* 예산 요약 */}
          {plan.budget_summary && (
            <div style={{
              background: 'white', borderRadius: '14px', padding: '20px 24px',
              marginBottom: '12px', boxShadow: '0 2px 8px rgba(0,0,0,0.05)',
              border: '1px solid rgba(0,0,0,0.04)',
            }}>
              <h3 style={{ fontSize: '1rem', fontWeight: 700, color: '#2d3748', marginBottom: '12px' }}>
                예상 비용
              </h3>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: '10px' }}>
                {[
                  { label: '숙박', value: plan.budget_summary.accommodation },
                  { label: '식비', value: plan.budget_summary.food },
                  { label: '관광/체험', value: plan.budget_summary.activities },
                  { label: '교통', value: plan.budget_summary.transport },
                ].filter(b => b.value).map(b => (
                  <div key={b.label} style={{
                    background: '#f7fafc', borderRadius: '10px', padding: '12px',
                    textAlign: 'center',
                  }}>
                    <div style={{ fontSize: '0.75rem', color: '#a0aec0', marginBottom: '4px', fontWeight: 600 }}>
                      {b.label}
                    </div>
                    <div style={{ fontSize: '0.95rem', fontWeight: 700, color: '#2d3748' }}>
                      {b.value}
                    </div>
                  </div>
                ))}
              </div>
              {plan.budget_summary.total && (
                <div style={{
                  marginTop: '12px', textAlign: 'center', padding: '12px',
                  background: 'linear-gradient(135deg, #667eea11, #764ba211)',
                  borderRadius: '10px',
                }}>
                  <span style={{ fontSize: '0.82rem', color: '#718096' }}>총 예상 비용: </span>
                  <span style={{ fontSize: '1.2rem', fontWeight: 800, color: '#667eea' }}>
                    {plan.budget_summary.total}
                  </span>
                </div>
              )}
            </div>
          )}

          {/* 준비물 & 주의사항 */}
          {(plan.packing_tips?.length > 0 || plan.warnings?.length > 0) && (
            <div style={{
              display: 'grid', gridTemplateColumns: plan.packing_tips?.length > 0 && plan.warnings?.length > 0 ? '1fr 1fr' : '1fr',
              gap: '12px', marginBottom: '12px',
            }}>
              {plan.packing_tips?.length > 0 && (
                <div style={{
                  background: 'white', borderRadius: '14px', padding: '18px 22px',
                  boxShadow: '0 2px 8px rgba(0,0,0,0.05)', border: '1px solid rgba(0,0,0,0.04)',
                }}>
                  <h4 style={{ fontSize: '0.88rem', fontWeight: 700, color: '#2d3748', marginBottom: '10px' }}>
                    준비물
                  </h4>
                  <ul style={{ margin: 0, paddingLeft: '18px', fontSize: '0.84rem', color: '#4a5568', lineHeight: 1.8 }}>
                    {plan.packing_tips.map((tip, i) => <li key={i}>{tip}</li>)}
                  </ul>
                </div>
              )}
              {plan.warnings?.length > 0 && (
                <div style={{
                  background: '#fffbeb', borderRadius: '14px', padding: '18px 22px',
                  border: '1px solid #f6e05e',
                }}>
                  <h4 style={{ fontSize: '0.88rem', fontWeight: 700, color: '#975a16', marginBottom: '10px' }}>
                    주의사항
                  </h4>
                  <ul style={{ margin: 0, paddingLeft: '18px', fontSize: '0.84rem', color: '#975a16', lineHeight: 1.8 }}>
                    {plan.warnings.map((w, i) => <li key={i}>{w}</li>)}
                  </ul>
                </div>
              )}
            </div>
          )}

          {/* 다시 만들기 */}
          <button
            onClick={handleGenerate}
            disabled={loading}
            style={{
              width: '100%', padding: '12px', background: 'white', color: '#667eea',
              border: '2px solid #667eea', borderRadius: '10px', fontSize: '0.95rem',
              fontWeight: 700, cursor: 'pointer', fontFamily: 'inherit',
              transition: 'all 0.15s',
            }}
            onMouseEnter={e => { e.currentTarget.style.background = '#667eea'; e.currentTarget.style.color = 'white' }}
            onMouseLeave={e => { e.currentTarget.style.background = 'white'; e.currentTarget.style.color = '#667eea' }}
          >
            다른 코스로 다시 만들기
          </button>
        </div>
      )}
    </div>
  )
}

export default TripPlanner
