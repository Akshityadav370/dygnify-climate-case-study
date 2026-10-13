type Props = { min: number; max: number; start: number; end: number; onChange: (start: number, end: number) => void }

export function YearRange({ min, max, start, end, onChange }: Props) {
  const years = Array.from({ length: max - min + 1 }, (_, i) => min + i)
  return (
    <fieldset className="field">
      <legend className="field-label">Years</legend>
      <div className="row">
        <select aria-label="Start year" value={start} onChange={(e) => onChange(Number(e.target.value), end)}>
          {years.map((y) => <option key={y} value={y}>{y}</option>)}
        </select>
        <span>–</span>
        <select aria-label="End year" value={end} onChange={(e) => onChange(start, Number(e.target.value))}>
          {years.map((y) => <option key={y} value={y}>{y}</option>)}
        </select>
      </div>
      {end - start + 1 < 10 && <p className="hint warn">Fewer than 10 years: trends can't be assessed.</p>}
    </fieldset>
  )
}
