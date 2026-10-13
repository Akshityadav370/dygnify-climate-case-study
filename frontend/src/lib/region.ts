import type { Bounds, Region, Selection } from '../api/types'

export const MAX_BOX_DEGREES = 5

const round2 = (v: number) => Math.round(v * 100) / 100

export function wrapLon(lon: number): number {
  return ((((lon + 180) % 360) + 360) % 360) - 180
}

export function boundsFrom(a: { lat: number; lng: number }, b: { lat: number; lng: number }): Bounds {
  const clampLat = (v: number) => Math.max(-90, Math.min(90, v))
  return {
    south: round2(clampLat(Math.min(a.lat, b.lat))),
    north: round2(clampLat(Math.max(a.lat, b.lat))),
    west: round2(wrapLon(Math.min(a.lng, b.lng))),
    east: round2(wrapLon(Math.max(a.lng, b.lng))),
  }
}

export function boxProblem(region: Region | null): string | null {
  if (!region || region.type !== 'box') return null
  const height = region.north - region.south
  const width = region.east - region.west
  if (height <= 0 || width <= 0) return 'The box needs north > south and east > west.'
  if (height > MAX_BOX_DEGREES || width > MAX_BOX_DEGREES) {
    return `The box can be at most 5° × 5° (currently ${height.toFixed(1)}° × ${width.toFixed(1)}°).`
  }
  return null
}

export function selectionProblem(sel: Selection, minYear: number, maxYear: number): string | null {
  if (!sel.region) return 'Choose a region: search a city or state, click the map, or draw a box.'
  const box = boxProblem(sel.region)
  if (box) return box
  if (sel.startYear > sel.endYear) return 'Start year must be before or equal to end year.'
  if (sel.startYear < minYear || sel.endYear > maxYear) return `Years must be between ${minYear} and ${maxYear}.`
  return null
}

export function stateLabel(label: string, clipped: boolean): string {
  return clipped ? `${label} (central 5°×5° box)` : label
}
