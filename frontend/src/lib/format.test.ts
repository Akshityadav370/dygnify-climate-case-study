import { describe, expect, it } from 'vitest'
import { formatChange, formatP, mean, trendBadge } from './format'
import type { Trend } from '../api/types'

const base: Trend = {
  n_years: 30, sen_per_decade: 4.2, mk_p: 0.003, significant: true, ols_slope: 0.4,
  ols_intercept: -800, change_kind: 'pct', change_value: 120, reason: null,
}

describe('format', () => {
  it('formats percent and absolute changes', () => {
    expect(formatChange(base, 'days')).toBe('+120%')
    expect(formatChange({ ...base, change_kind: 'abs', change_value: -2.34 }, 'days')).toBe('−2.3 days')
    expect(formatChange({ ...base, change_kind: null, change_value: null }, 'days')).toBe('—')
  })

  it('formats p-values', () => {
    expect(formatP(0.0004)).toBe('p < 0.001')
    expect(formatP(0.0312)).toBe('p = 0.031')
    expect(formatP(null)).toBe('—')
  })

  it('labels trend badges', () => {
    expect(trendBadge(base)).toEqual({ label: '▲ Significant increase', tone: 'up' })
    expect(trendBadge({ ...base, sen_per_decade: -1 })).toEqual({ label: '▼ Significant decrease', tone: 'down' })
    expect(trendBadge({ ...base, significant: false })).toEqual({ label: 'No significant trend', tone: 'flat' })
    expect(trendBadge({ ...base, reason: 'insufficient_years' })).toEqual({ label: 'Not enough years', tone: 'na' })
  })

  it('averages ignoring nulls', () => {
    expect(mean([1, null, 3])).toBe(2)
    expect(mean([null])).toBeNull()
  })
})

describe('trend badge edge cases', () => {
  it('does not call a zero-slope significant trend an increase or decrease', () => {
    const t: Trend = { ...base, sen_per_decade: 0, change_kind: 'abs', change_value: 0 }
    expect(trendBadge(t)).toEqual({ label: 'Significant but negligible', tone: 'flat' })
  })
})
