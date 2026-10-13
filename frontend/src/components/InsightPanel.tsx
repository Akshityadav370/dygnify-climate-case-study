import type { Analysis } from '../api/types'

export function InsightPanel({ analysis }: { analysis: Analysis }) {
  const q = analysis.data_quality
  return (
    <div className="card">
      <h3>Insights</h3>
      <ul className="insights">
        {analysis.insights.map((s) => <li key={s}>{s}</li>)}
      </ul>
      <details>
        <summary>Method, data quality and caveats</summary>
        <ul className="caveats">
          {analysis.caveats.map((c) => <li key={c}>{c}</li>)}
          <li>
            {q.days.toLocaleString()} days analysed; {q.removed} impossible values removed; {q.interpolated} short gaps
            filled by interpolation.
          </li>
        </ul>
      </details>
    </div>
  )
}
