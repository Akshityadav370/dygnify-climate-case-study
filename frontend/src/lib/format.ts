import type { Trend } from '../api/types'

const MINUS = '−'

export function formatChange(trend: Trend, unit: string): string {
  if (trend.change_kind === null || trend.change_value === null) return '—'
  const v = trend.change_value
  const sign = v > 0 ? '+' : v < 0 ? MINUS : ''
  if (trend.change_kind === 'pct') return `${sign}${Math.abs(Math.round(v))}%`
  return `${sign}${Math.abs(v).toFixed(1)} ${unit}`
}

export function formatP(p: number | null): string {
  if (p === null) return '—'
  return p < 0.001 ? 'p < 0.001' : `p = ${p.toFixed(3)}`
}

export function trendBadge(trend: Trend): { label: string; tone: 'up' | 'down' | 'flat' | 'na' } {
  if (trend.reason || trend.sen_per_decade === null) return { label: 'Not enough years', tone: 'na' }
  if (!trend.significant) return { label: 'No significant trend', tone: 'flat' }
  // A consistent tendency whose typical (median) change is zero is not an increase or decrease.
  if (trend.sen_per_decade === 0) return { label: 'Significant but negligible', tone: 'flat' }
  return trend.sen_per_decade > 0
    ? { label: '▲ Significant increase', tone: 'up' }
    : { label: '▼ Significant decrease', tone: 'down' }
}

export function mean(values: (number | null)[]): number | null {
  const present = values.filter((v): v is number => v !== null)
  return present.length ? present.reduce((a, b) => a + b, 0) / present.length : null
}
