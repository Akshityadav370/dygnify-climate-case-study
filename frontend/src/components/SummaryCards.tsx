import type { Analysis } from '../api/types'
import { formatChange, formatP, mean, trendBadge } from '../lib/format'

export function SummaryCards({ analysis }: { analysis: Analysis }) {
  const usable = analysis.yearly.filter((r) => !r.low_quality)
  const avgDays = mean(usable.map((r) => r.HWF))
  const avgEvents = mean(usable.map((r) => r.HWN))
  const longest = analysis.events.reduce<Analysis['events'][number] | null>(
    (best, e) => (best === null || e.days > best.days ? e : best), null)
  const trend = analysis.trends.HWF
  const badge = trendBadge(trend)

  return (
    <div className="cards">
      <div className="card stat">
        <span className="stat-label">Heatwave days / year</span>
        <span className="stat-value">{avgDays === null ? '—' : avgDays.toFixed(1)}</span>
      </div>
      <div className="card stat">
        <span className="stat-label">Events / year</span>
        <span className="stat-value">{avgEvents === null ? '—' : avgEvents.toFixed(1)}</span>
      </div>
      <div className="card stat">
        <span className="stat-label">Longest heatwave</span>
        <span className="stat-value">{longest ? `${longest.days} days` : '—'}</span>
        {longest && <span className="stat-sub">{longest.start.slice(0, 4)}</span>}
      </div>
      <div className={`card stat tone-${badge.tone}`}>
        <span className="stat-label">Trend in heatwave days</span>
        <span className="stat-value small">{badge.label}</span>
        <span className="stat-sub">{formatChange(trend, 'days')} · {formatP(trend.mk_p)}</span>
      </div>
    </div>
  )
}
