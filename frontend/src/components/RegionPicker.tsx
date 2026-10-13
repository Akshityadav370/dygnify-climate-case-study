import { useState } from 'react'
import type { Region } from '../api/types'
import { boxProblem } from '../lib/region'
import { BoxInputs } from './BoxInputs'
import { PlaceSearch } from './PlaceSearch'
import { RegionMap } from './RegionMap'

type Mode = 'city' | 'state' | 'box'
type Props = { region: Region | null; onChange: (region: Region) => void }

const TABS: { id: Mode; label: string }[] = [
  { id: 'city', label: 'City' },
  { id: 'state', label: 'State' },
  { id: 'box', label: 'Draw box' },
]

export function RegionPicker({ region, onChange }: Props) {
  const [mode, setMode] = useState<Mode>(region?.type === 'box' ? 'box' : 'city')
  const [note, setNote] = useState<string | null>(null)
  const problem = boxProblem(region)

  return (
    <fieldset className="field">
      <legend className="field-label">Region</legend>
      <div className="tabs" role="tablist">
        {TABS.map((t) => (
          <button key={t.id} type="button" role="tab" aria-selected={mode === t.id}
            className={mode === t.id ? 'tab active' : 'tab'} onClick={() => { setMode(t.id); setNote(null) }}>
            {t.label}
          </button>
        ))}
      </div>

      {mode === 'city' && (
        <>
          <PlaceSearch kind="city" onSelect={(r) => onChange({ type: 'point', lat: r.lat, lon: r.lon, label: r.label })} />
          <p className="hint">…or click anywhere on the map.</p>
        </>
      )}
      {mode === 'state' && (
        <PlaceSearch
          kind="state"
          onSelect={(r) => {
            if (!r.bbox) return
            onChange({ type: 'box', ...r.bbox, label: r.label })
            setNote(r.clipped ? 'This state is larger than 5° × 5°, so a 5° × 5° box around its centre is analysed.' : null)
          }}
        />
      )}
      {mode === 'box' && (
        <>
          <BoxInputs region={region} onChange={onChange} />
          <p className="hint">Drag on the map to draw a box (max 5° × 5°).</p>
        </>
      )}

      <RegionMap
        region={region}
        mode={mode}
        onPoint={(lat, lon) => onChange({ type: 'point', lat, lon, label: `${lat.toFixed(2)}, ${lon.toFixed(2)}` })}
        onBox={(b) => onChange({ type: 'box', ...b, label: 'Custom box' })}
      />
      {note && <p className="hint">{note}</p>}
      {region && <p className="hint">Selected: <strong>{region.label}</strong></p>}
      {problem && <p className="error-text">{problem}</p>}
    </fieldset>
  )
}
