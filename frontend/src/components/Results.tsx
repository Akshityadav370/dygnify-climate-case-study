import type { Analysis } from '../api/types'
import { EventsTable } from './EventsTable'
import { ExportButtons } from './ExportButtons'
import { InsightPanel } from './InsightPanel'
import { MetricChart } from './MetricChart'
import { SummaryCards } from './SummaryCards'
import { ThresholdChart } from './ThresholdChart'

export function Results({ analysis }: { analysis: Analysis }) {
  const noEvents = analysis.events.length === 0
  return (
    <>
      <div className="results-head">
        <h2>{analysis.region.label}</h2>
        <p className="muted">
          {analysis.years.start}–{analysis.years.end} · Heatwave · {analysis.cached ? 'served from cache' : 'freshly computed'}
        </p>
      </div>
      <SummaryCards analysis={analysis} />
      <InsightPanel analysis={analysis} />
      {noEvents ? (
        <p className="banner info">No heatwaves were detected in this period, so there is nothing to chart. Try a longer range or another region.</p>
      ) : (
        <MetricChart analysis={analysis} />
      )}
      <ThresholdChart thresholds={analysis.threshold_by_doy} baseline={analysis.params.baseline} />
      {!noEvents && <EventsTable events={analysis.events} />}
      <ExportButtons id={analysis.id} />
    </>
  )
}
