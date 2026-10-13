import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from './api/client'
import type { AnalyzeSelection, Selection } from './api/types'
import { HazardSelect } from './components/HazardSelect'
import { RegionPicker } from './components/RegionPicker'
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
        <p className="muted">How have heatwaves changed where you live? Data: NASA POWER, 1981 onward.</p>
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
          {submitted ? <pre>{JSON.stringify(submitted, null, 2)}</pre> : <p className="muted">Pick a region and press Analyze.</p>}
        </section>
      </main>
    </div>
  )
}
