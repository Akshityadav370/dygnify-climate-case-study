import { describe, expect, it } from 'vitest'
import { boundsFrom, boxProblem, selectionProblem, wrapLon } from './region'

describe('region helpers', () => {
  it('wraps longitudes into [-180, 180)', () => {
    expect(wrapLon(190)).toBe(-170)
    expect(wrapLon(-181)).toBe(179)
    expect(wrapLon(45)).toBe(45)
  })

  it('builds rounded bounds from two corners in any order', () => {
    expect(boundsFrom({ lat: 25.123, lng: 75.456 }, { lat: 20.001, lng: 70.009 })).toEqual({
      south: 20, west: 70.01, north: 25.12, east: 75.46,
    })
  })

  it('reports box problems', () => {
    expect(boxProblem({ type: 'box', south: 0, west: 0, north: 6, east: 1, label: 'b' })).toMatch(/at most 5°/)
    expect(boxProblem({ type: 'box', south: 2, west: 0, north: 1, east: 1, label: 'b' })).toMatch(/north/)
    expect(boxProblem({ type: 'box', south: 0, west: 0, north: 5, east: 5, label: 'b' })).toBeNull()
    expect(boxProblem({ type: 'point', lat: 0, lon: 0, label: 'p' })).toBeNull()
  })

  it('reports selection problems', () => {
    const region = { type: 'point' as const, lat: 0, lon: 0, label: 'p' }
    expect(selectionProblem({ hazard: 'heatwave', region: null, startYear: 1990, endYear: 2020 }, 1981, 2025)).toMatch(/region/)
    expect(selectionProblem({ hazard: 'heatwave', region, startYear: 2020, endYear: 1990 }, 1981, 2025)).toMatch(/Start year/)
    expect(selectionProblem({ hazard: 'heatwave', region, startYear: 1970, endYear: 1990 }, 1981, 2025)).toMatch(/1981/)
    expect(selectionProblem({ hazard: 'heatwave', region, startYear: 1990, endYear: 2020 }, 1981, 2025)).toBeNull()
  })
})

describe('state labels', () => {
  it('marks clipped states in the label', async () => {
    const { stateLabel } = await import('./region')
    expect(stateLabel('Rajasthan, India', true)).toBe('Rajasthan, India (central 5°×5° box)')
    expect(stateLabel('Goa, India', false)).toBe('Goa, India')
  })
})
