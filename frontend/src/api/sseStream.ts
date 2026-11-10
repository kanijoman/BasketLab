/** Reads an analysis the API streams over SSE: progress frames, then a closing frame with the result or an error (lineups, rotations; issue #452). */
export function streamResult<T>(url: string, onProgress?: (pct: number, current: number, total: number) => void): Promise<T> {
  return new Promise((resolve, reject) => {
    const es = new EventSource(url)

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.done) {
          es.close()
          if (data.error) reject(new Error(data.error))
          else resolve(data.result as T)
        } else if (data.progress !== undefined && onProgress) {
          onProgress(data.progress as number, data.current as number, data.total as number)
        }
      } catch {
        // ignore malformed frames
      }
    }

    es.onerror = () => {
      es.close()
      reject(new Error('SSE connection error'))
    }
  })
}
