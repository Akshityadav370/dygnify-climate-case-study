import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import './charts/setup'
import { api } from './api/client'
import type { AnalyzeSelection, Selection } from './api/types'
import { ErrorBanner } from './components/ErrorBanner'
import { HazardSelect } from './components/HazardSelect'
import { LoadingSkeleton } from './components/LoadingSkeleton'
import { RegionPicker } from './components/RegionPicker'
import { Results } from './components/Results'
import { YearRange } from './components/YearRange'
import { selectionProblem } from './lib/region'
import { paramsToSelection, selectionToParams } from './lib/urlState'

export default function App() {
  const meta = useQuery({ queryKey: ['meta'], queryFn: api.meta, staleTime: Infinity })
  const minYear = meta.data?.years.min ?? 1981
  const maxYear = meta.data?.years.max ?? new Date().getFullYear() - 1

  const [initial] = useState(() => paramsToSelection(new URLSearchParams(window.location.search)))
  const [selection, setSelection] = useState<Selection>(initial)
  const [submitted, setSubmitted] = useState<AnalyzeSelection | null>(() =>
    initial.region ? { ...initial, region: initial.region } : null,
  )
  const analysis = useQuery({
    queryKey: ['analysis', submitted],
    queryFn: () => api.analyze(submitted!),
    enabled: submitted !== null,
    staleTime: Infinity,
    retry: false,
  })
  const problem = selectionProblem(selection, minYear, maxYear)

  function runAnalysis() {
    if (problem || !selection.region) return
    const next = { ...selection, region: selection.region }
    setSubmitted(next)
    window.history.replaceState(null, '', `?${selectionToParams(next)}`)
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>Climate Hazard Trend Analyzer</h1>
        <p className="muted">How have heatwaves changed where you live? Data: Open-Meteo (ERA5), NASA POWER fallback, 1981 onward.</p>
      </header>
      <main className="layout">
        <aside className="controls">
          <HazardSelect hazards={meta.data?.hazards ?? []} value={selection.hazard} onChange={(hazard) => setSelection({ ...selection, hazard })} />
          <RegionPicker region={selection.region} onChange={(region) => setSelection({ ...selection, region })} />
          <YearRange min={minYear} max={maxYear} start={selection.startYear} end={selection.endYear}
            onChange={(startYear, endYear) => setSelection({ ...selection, startYear, endYear })} />
          <button type="button" className="primary" disabled={problem !== null} onClick={runAnalysis}>Analyze</button>
          {problem && selection.region && <p className="hint">{problem}</p>}
        </aside>
        <section className="results">
          {!submitted && (
            <div className="card empty">
              <h2>Pick a region to begin</h2>
              <p className="muted">Search a city or state, click the map, or draw a box, then press Analyze.</p>
            </div>
          )}
          {submitted && analysis.isPending && <LoadingSkeleton />}
          {analysis.isError && <ErrorBanner error={analysis.error} onRetry={() => analysis.refetch()} />}
          {analysis.data && <Results analysis={analysis.data} />}
        </section>
      </main>
    </div>
  )
}
