import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import type { GeocodeResult } from '../api/types'
import { useDebouncedValue } from '../lib/useDebouncedValue'

type Props = { kind: 'city' | 'state'; onSelect: (result: GeocodeResult) => void }

export function PlaceSearch({ kind, onSelect }: Props) {
  const [text, setText] = useState('')
  const [open, setOpen] = useState(false)
  const q = useDebouncedValue(text.trim(), 350)
  const results = useQuery({
    queryKey: ['geocode', kind, q],
    queryFn: ({ signal }) => api.geocode(q, kind, signal),
    enabled: q.length >= 2,
    staleTime: 5 * 60_000,
    retry: false,
  })

  return (
    <div className="search">
      <input
        type="search"
        value={text}
        maxLength={100}
        aria-label={kind === 'city' ? 'Search city' : 'Search state'}
        placeholder={kind === 'city' ? 'Search a city, e.g. Delhi' : 'Search a state, e.g. Rajasthan'}
        onChange={(e) => { setText(e.target.value); setOpen(true) }}
      />
      {open && q.length >= 2 && (
        <ul className="search-results">
          {results.isFetching && <li className="muted">Searching…</li>}
          {results.error && <li className="error-text">{(results.error as Error).message}</li>}
          {results.data?.results.length === 0 && <li className="muted">No matches</li>}
          {results.data?.results.map((r) => (
            <li key={`${r.label}-${r.lat}-${r.lon}`}>
              <button type="button" onClick={() => { onSelect(r); setText(r.label); setOpen(false) }}>
                {r.label}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
