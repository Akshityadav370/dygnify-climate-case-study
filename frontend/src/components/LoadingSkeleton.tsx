export function LoadingSkeleton() {
  return (
    <div className="loading" aria-busy="true">
      <p className="muted">Fetching 45 years of daily data and detecting heatwaves… The first request for a region takes a few seconds.</p>
      <div className="cards">{[0, 1, 2, 3].map((i) => <div key={i} className="card skeleton" />)}</div>
      <div className="card skeleton tall" />
    </div>
  )
}
