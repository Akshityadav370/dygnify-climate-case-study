import type { HazardInfo } from '../api/types'

type Props = { hazards: HazardInfo[]; value: string; onChange: (id: 'heatwave') => void }

export function HazardSelect({ hazards, value, onChange }: Props) {
  const options = hazards.length ? hazards : [{ id: 'heatwave', name: 'Heatwave', status: 'available' as const, definition: null }]
  return (
    <label className="field">
      <span className="field-label">Hazard</span>
      <select value={value} onChange={(e) => onChange(e.target.value as 'heatwave')}>
        {options.map((h) => (
          <option key={h.id} value={h.id} disabled={h.status !== 'available'}>
            {h.name}{h.status !== 'available' ? ' (coming soon)' : ''}
          </option>
        ))}
      </select>
    </label>
  )
}
