/** Shared HTTP helpers of the API client (issue #201): the base URL, the error detail and the two verbs. */
export const BASE = (import.meta.env.VITE_API_BASE ?? '') + '/api/v1'
/** For API modules split out of this (already oversized) file. */
export const API_BASE = BASE

function _fmtDetail(detail: unknown, status: number): string {
  if (Array.isArray(detail))
    return (detail as { msg?: string; loc?: unknown[] }[])
      .map(e => {
        const field = Array.isArray(e.loc) ? String(e.loc[e.loc.length - 1]) : ''
        return field ? `${e.msg ?? JSON.stringify(e)} (campo: ${field})` : (e.msg ?? JSON.stringify(e))
      })
      .join('; ')
  if (typeof detail === 'string') return detail
  return `HTTP ${status}`
}

export async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(_fmtDetail(body.detail, res.status))
  }
  return res.json() as Promise<T>
}

export async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const b = await res.json().catch(() => ({}))
    throw new Error(_fmtDetail(b.detail, res.status))
  }
  return res.json() as Promise<T>
}

/** The body of a download, or the error the server says (a fallback when it says none). */
export async function downloadBlob(res: Response, fallback: string): Promise<Blob> {
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? fallback)
  }
  return res.blob()
}
