import { useState } from 'react'
import type { HeatwaveEvent } from '../api/types'

type SortKey = 'start' | 'days' | 'peak_tmax'

export function EventsTable({ events }: { events: HeatwaveEvent[] }) {
  const [sort, setSort] = useState<{ key: SortKey; desc: boolean }>({ key: 'start', desc: true })
  const sorted = [...events].sort((a, b) => {
    const cmp = sort.key === 'start' ? a.start.localeCompare(b.start) : a[sort.key] - b[sort.key]
    return sort.desc ? -cmp : cmp
  })
  const header = (key: SortKey, label: string) => (
    <th aria-sort={sort.key === key ? (sort.desc ? 'descending' : 'ascending') : 'none'}>
      <button type="button" onClick={() => setSort({ key, desc: sort.key === key ? !sort.desc : true })}>
        {label}{sort.key === key ? (sort.desc ? ' ↓' : ' ↑') : ''}
      </button>
    </th>
  )

  return (
    <div className="card">
      <h3>Detected heatwaves ({events.length})</h3>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>{header('start', 'Start')}<th>End</th>{header('days', 'Days')}{header('peak_tmax', 'Peak °C')}<th>Avg °C above threshold</th></tr>
          </thead>
          <tbody>
            {sorted.map((e) => (
              <tr key={e.start}>
                <td>{e.start}</td><td>{e.end}</td><td>{e.days}</td><td>{e.peak_tmax.toFixed(1)}</td><td>{e.mean_exceedance.toFixed(1)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
