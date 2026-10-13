import { useEffect, useState } from 'react'
import type { BoxRegion, Region } from '../api/types'

type Props = { region: Region | null; onChange: (region: BoxRegion) => void }
const KEYS = ['south', 'west', 'north', 'east'] as const

export function BoxInputs({ region, onChange }: Props) {
  const [draft, setDraft] = useState<Record<(typeof KEYS)[number], string>>({ south: '', west: '', north: '', east: '' })

  useEffect(() => {
    if (region?.type === 'box') {
      setDraft({ south: String(region.south), west: String(region.west), north: String(region.north), east: String(region.east) })
    }
  }, [region])

  function update(key: (typeof KEYS)[number], value: string) {
    const next = { ...draft, [key]: value }
    setDraft(next)
    const nums = KEYS.map((k) => Number(next[k]))
    if (KEYS.every((k) => next[k].trim() !== '') && nums.every(Number.isFinite)) {
      const [south, west, north, east] = nums
      onChange({ type: 'box', south, west, north, east, label: 'Custom box' })
    }
  }

  return (
    <div className="box-inputs">
      {KEYS.map((k) => (
        <label key={k}>
          <span>{k}</span>
          <input type="number" step="0.01" value={draft[k]} onChange={(e) => update(k, e.target.value)} />
        </label>
      ))}
    </div>
  )
}
