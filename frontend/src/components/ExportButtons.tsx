import { api } from '../api/client'

export function ExportButtons({ id }: { id: string }) {
  return (
    <div className="row">
      <a className="button-link" href={api.exportUrl(id, 'csv')} download>Download CSV</a>
      <a className="button-link" href={api.exportUrl(id, 'pdf')} download>Download PDF report</a>
    </div>
  )
}
