import type { Analysis, AnalyzeSelection, GeocodeResult, MetaResponse } from './types'

const BASE = (import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000').replace(/\/$/, '')

export class ApiError extends Error {
  status: number
  code: string
  retryAfter: number | null
  details: string[]

  constructor(status: number, code: string, message: string, retryAfter: number | null, details: string[] = []) {
    super(message)
    this.status = status
    this.code = code
    this.retryAfter = retryAfter
    this.details = details
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${BASE}${path}`, init)
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') throw err
    throw new ApiError(0, 'NETWORK_ERROR', 'Could not reach the server. Check your connection and try again.', null)
  }
  if (!response.ok) {
    let code = `HTTP_${response.status}`
    let message = `Request failed (${response.status}).`
    let details: string[] = []
    try {
      const body = await response.json()
      if (body?.error) {
        code = body.error.code
        message = body.error.message
        details = (body.error.details ?? []).map((d: { msg: string }) => d.msg)
      }
    } catch {
      // non-JSON error body; keep the generic message
    }
    const retryAfter = response.headers.get('Retry-After')
    throw new ApiError(response.status, code, message, retryAfter ? Number(retryAfter) : null, details)
  }
  return (await response.json()) as T
}

export const api = {
  meta: () => request<MetaResponse>('/api/hazards'),
  geocode: (q: string, kind: 'city' | 'state', signal?: AbortSignal) =>
    request<{ results: GeocodeResult[] }>(`/api/geocode?${new URLSearchParams({ q, kind })}`, { signal }),
  analyze: (sel: AnalyzeSelection) =>
    request<Analysis>('/api/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ hazard: sel.hazard, region: sel.region, start_year: sel.startYear, end_year: sel.endYear }),
    }),
  exportUrl: (id: string, kind: 'csv' | 'pdf') =>
    `${BASE}/api/analyses/${id}/${kind === 'csv' ? 'export.csv' : 'report.pdf'}`,
}
