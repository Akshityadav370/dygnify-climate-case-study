import type { Region, Selection } from '../api/types'

export const DEFAULT_SELECTION: Selection = { hazard: 'heatwave', region: null, startYear: 1990, endYear: 2020 }

export function selectionToParams(sel: Selection): URLSearchParams {
  const p = new URLSearchParams({ hazard: sel.hazard, from: String(sel.startYear), to: String(sel.endYear) })
  const r = sel.region
  if (r?.type === 'point') {
    p.set('type', 'point'); p.set('lat', String(r.lat)); p.set('lon', String(r.lon)); p.set('label', r.label)
  } else if (r?.type === 'box') {
    p.set('type', 'box'); p.set('s', String(r.south)); p.set('w', String(r.west))
    p.set('n', String(r.north)); p.set('e', String(r.east)); p.set('label', r.label)
  }
  return p
}

function num(params: URLSearchParams, key: string): number | null {
  const raw = params.get(key)
  if (raw === null || raw.trim() === '') return null
  const value = Number(raw)
  return Number.isFinite(value) ? value : null
}

export function paramsToSelection(params: URLSearchParams): Selection {
  const label = (params.get('label') ?? '').slice(0, 100)
  let region: Region | null = null
  if (params.get('type') === 'point') {
    const lat = num(params, 'lat')
    const lon = num(params, 'lon')
    if (lat !== null && lon !== null) region = { type: 'point', lat, lon, label: label || 'Selected point' }
  } else if (params.get('type') === 'box') {
    const [south, west, north, east] = ['s', 'w', 'n', 'e'].map((k) => num(params, k))
    if (south !== null && west !== null && north !== null && east !== null) {
      region = { type: 'box', south, west, north, east, label: label || 'Custom box' }
    }
  }
  return {
    hazard: 'heatwave',
    region,
    startYear: num(params, 'from') ?? DEFAULT_SELECTION.startYear,
    endYear: num(params, 'to') ?? DEFAULT_SELECTION.endYear,
  }
}
