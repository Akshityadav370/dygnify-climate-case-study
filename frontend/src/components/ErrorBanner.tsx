import { ApiError } from '../api/client'

function messageFor(error: unknown): string {
  if (!(error instanceof ApiError)) return 'Something unexpected went wrong.'
  if (error.status === 429) return `Too many requests. Please retry in ${error.retryAfter ?? 60} seconds.`
  if (error.status === 422) return `Please check your selection. ${error.details.join(' ') || error.message}`
  if (error.status === 502 || error.status === 504) return 'The weather data provider is unavailable right now. Please try again shortly.'
  return error.message
}

export function ErrorBanner({ error, onRetry }: { error: unknown; onRetry: () => void }) {
  return (
    <div role="alert" className="banner error">
      <span>{messageFor(error)}</span>
      <button type="button" onClick={onRetry}>Retry</button>
    </div>
  )
}
