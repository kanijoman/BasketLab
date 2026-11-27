import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join, sep } from 'node:path'
import { describe, expect, it } from 'vitest'

// The API is retired (epic #1199): the web reads the published files and NOTHING else. No module of the app may know the API's address, ask a server for data or offer the
// `?data=api` mode; if a page cannot be answered by the files, the reader gets the clear error of `datasource/resolve`.
const SRC = __dirname
const isSource = (name: string) => /\.tsx?$/.test(name) && !/\.test\.tsx?$/.test(name)
const files = (dir: string): string[] =>
  readdirSync(dir).flatMap(name => {
    const path = join(dir, name)
    if (statSync(path).isDirectory()) return path.endsWith(`${sep}test`) ? [] : files(path)
    return isSource(name) ? [path] : []
  })

describe('the web without the API', () => {
  const sources = files(SRC).map(path => ({ path: path.slice(SRC.length + 1), text: readFileSync(path, 'utf8') }))

  it.each([
    ['the address of the API', /\/api\/v1|VITE_API_BASE|\bAPI_BASE\b/],
    ['the data=api mode', /data=api|=== 'api'|!== 'local'/],
    ['a fallback to the server in fromSource', /fromSource\([^)]*\(\)\s*=>\s*get</],
    ['the HTTP helpers of the API client', /import \{[^}]*\b(get|post|downloadBlob)\b[^}]*\} from '\.\/http'/],
  ])('no module mentions %s', (_name, pattern) => {
    const offenders = sources.filter(s => pattern.test(s.text)).map(s => s.path)
    expect(offenders).toEqual([])
  })
})
