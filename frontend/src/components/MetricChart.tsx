import { useState } from 'react'
import { Chart } from 'react-chartjs-2'
import type { ChartData, ChartOptions } from 'chart.js'
import type { Analysis, MetricKey } from '../api/types'
import { formatChange, formatP } from '../lib/format'

const METRICS: { key: MetricKey; label: string; unit: string }[] = [
  { key: 'HWF', label: 'Heatwave days', unit: 'days' },
  { key: 'HWN', label: 'Events', unit: 'events' },
  { key: 'HWD', label: 'Longest event', unit: 'days' },
  { key: 'HWM', label: 'Mean intensity', unit: '°C above threshold' },
  { key: 'HWA', label: 'Peak temperature', unit: '°C' },
]

export function MetricChart({ analysis }: { analysis: Analysis }) {
  const [metric, setMetric] = useState<MetricKey>('HWF')
  const info = METRICS.find((m) => m.key === metric)!
  const series = analysis.chart.series[metric]
  const years = analysis.chart.years
  const lowQuality = new Set(analysis.data_quality.low_quality_years)
  const trend = analysis.trends[metric]

  const data: ChartData<'bar' | 'line', (number | null)[], number> = {
    labels: years,
    datasets: [
      {
        type: 'bar', label: info.label, data: series.values, order: 3,
        backgroundColor: years.map((y) => (lowQuality.has(y) ? 'rgba(217, 98, 43, 0.25)' : 'rgba(217, 98, 43, 0.85)')),
      },
      { type: 'line', label: '5-year average', data: series.rolling5, borderColor: '#7a2e0e', pointRadius: 0, tension: 0.3, spanGaps: true, order: 1 },
      { type: 'line', label: 'Linear trend', data: series.trendline, borderColor: '#1f2328', borderDash: [6, 4], pointRadius: 0, order: 2 },
    ],
  }
  const options: ChartOptions<'bar' | 'line'> = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    scales: { y: { beginAtZero: metric !== 'HWA', title: { display: true, text: info.unit } } },
    plugins: {
      tooltip: {
        callbacks: {
          footer: (items) => (items.length && lowQuality.has(Number(items[0].label)) ? 'Low data quality: excluded from trend' : ''),
        },
      },
    },
  }

  return (
    <div className="card">
      <div className="chart-head">
        <h3>Yearly {info.label.toLowerCase()}</h3>
        <div className="segmented" role="group" aria-label="Metric">
          {METRICS.map((m) => (
            <button key={m.key} type="button" className={m.key === metric ? 'active' : ''} onClick={() => setMetric(m.key)}>
              {m.label}
            </button>
          ))}
        </div>
      </div>
      <div className="chart-box">
        <Chart type="bar" data={data} options={options} />
      </div>
      <p className="hint">
        {trend.reason
          ? 'Not enough complete years to assess a trend.'
          : `Sen's slope ${trend.sen_per_decade! > 0 ? '+' : ''}${trend.sen_per_decade} ${info.unit}/decade · change ${formatChange(trend, info.unit)} · ${formatP(trend.mk_p)} · ${trend.significant ? 'statistically significant' : 'not significant'}`}
      </p>
    </div>
  )
}
