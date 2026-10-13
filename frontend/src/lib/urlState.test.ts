import { describe, expect, it } from 'vitest'
import { DEFAULT_SELECTION, paramsToSelection, selectionToParams } from './urlState'
import type { Selection } from '../api/types'

describe('url state', () => {
  it('round-trips a point selection', () => {
    const sel: Selection = {
      hazard: 'heatwave',
      region: { type: 'point', lat: 28.61, lon: 77.21, label: 'Delhi, India' },
      startYear: 1990,
      endYear: 2020,
    }
    expect(paramsToSelection(selectionToParams(sel))).toEqual(sel)
  })

  it('round-trips a box selection', () => {
    const sel: Selection = {
      hazard: 'heatwave',
      region: { type: 'box', south: 20, west: 70, north: 25, east: 75, label: 'Custom box' },
      startYear: 2000,
      endYear: 2010,
    }
    expect(paramsToSelection(selectionToParams(sel))).toEqual(sel)
  })

  it('falls back to defaults for garbage', () => {
    const params = new URLSearchParams('type=point&lat=abc&lon=1&from=x&to=2020')
    expect(paramsToSelection(params)).toEqual({ ...DEFAULT_SELECTION, endYear: 2020 })
  })
})
