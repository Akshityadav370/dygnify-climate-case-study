import { Line } from 'react-chartjs-2'

const LABELS = Array.from({ length: 365 }, (_, i) =>
  new Date(Date.UTC(2001, 0, i + 1)).toLocaleDateString('en', { month: 'short', day: 'numeric', timeZone: 'UTC' }))

export function ThresholdChart({ thresholds, baseline }: { thresholds: (number | null)[]; baseline: number[] }) {
  return (
    <div className="card">
      <h3>What counts as "hot" here</h3>
      <p className="hint">
        95th percentile of daily maximum temperature for each day of the year ({baseline[0]}–{baseline[1]} baseline).
        A heatwave is 3+ days in a row above this line.
      </p>
      <div className="chart-box small">
        <Line
          data={{ labels: LABELS, datasets: [{ label: 'Threshold (°C)', data: thresholds, borderColor: '#d9622b', pointRadius: 0, borderWidth: 2 }] }}
          options={{
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: { x: { ticks: { maxTicksLimit: 12 } }, y: { title: { display: true, text: '°C' } } },
          }}
        />
      </div>
    </div>
  )
}
