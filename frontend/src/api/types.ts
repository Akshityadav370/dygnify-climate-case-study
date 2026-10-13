export type MetricKey = 'HWN' | 'HWF' | 'HWD' | 'HWM' | 'HWA'

export type PointRegion = { type: 'point'; lat: number; lon: number; label: string }
export type BoxRegion = { type: 'box'; south: number; west: number; north: number; east: number; label: string }
export type Region = PointRegion | BoxRegion
export type Bounds = { south: number; west: number; north: number; east: number }

export type Selection = { hazard: 'heatwave'; region: Region | null; startYear: number; endYear: number }
export type AnalyzeSelection = Selection & { region: Region }

export type YearlyRow = {
  year: number; HWN: number; HWF: number; HWD: number; HWM: number | null; HWA: number | null; low_quality: boolean
}
export type HeatwaveEvent = { start: string; end: string; days: number; peak_tmax: number; mean_exceedance: number }
export type Trend = {
  n_years: number
  sen_per_decade: number | null
  mk_p: number | null
  significant: boolean
  ols_slope: number | null
  ols_intercept: number | null
  change_kind: 'pct' | 'abs' | null
  change_value: number | null
  reason: string | null
}
export type ChartSeries = { values: (number | null)[]; rolling5: (number | null)[]; trendline: (number | null)[] }

export type Analysis = {
  id: string
  cached: boolean
  hazard: string
  algo_version: string
  region: { type: 'point' | 'box'; label: string; bbox: Bounds | null; points: number[][] }
  sources_used: string[]
  years: { start: number; end: number }
  params: { percentile: number; min_days: number; window: number; baseline: number[] }
  yearly: YearlyRow[]
  events: HeatwaveEvent[]
  threshold_by_doy: (number | null)[]
  trends: Record<MetricKey, Trend>
  insights: string[]
  caveats: string[]
  data_quality: { days: number; removed: number; interpolated: number; low_quality_years: number[] }
  chart: { years: number[]; series: Record<MetricKey, ChartSeries> }
  created_at: string
}

export type GeocodeResult = {
  kind: 'city' | 'state'; name: string; label: string; lat: number; lon: number; bbox: Bounds | null; clipped: boolean
}
export type HazardInfo = { id: string; name: string; status: 'available' | 'coming_soon'; definition: string | null }
export type MetaResponse = { hazards: HazardInfo[]; years: { min: number; max: number } }
