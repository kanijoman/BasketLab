import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'

/**
 * One key of the cache of React Query is ONE answer: two places that use the same key with a different function (or shape) read each other's data, which depends on the
 * order the pages were visited in and disappears when the browser is refreshed (issue #605: the teams were missing in Evolución until a refresh, because Jugadores had
 * left a list of strings under the key of the lists of {id, name}). So a name of key (its first element) belongs to ONE ``queryFn``.
 */
const SRC = join(__dirname, '..')

function files(dir: string): string[] {
  return readdirSync(dir).flatMap(name => {
    const path = join(dir, name)
    if (statSync(path).isDirectory()) return files(path)
    return /\.tsx?$/.test(name) && !/\.test\./.test(name) ? [path] : []
  })
}

function balanced(text: string, start: number): string {
  let depth = 0
  for (let i = start; i < text.length; i++) {
    if (text[i] === '[') depth++
    else if (text[i] === ']' && --depth === 0) return text.slice(start, i + 1)
  }
  return text.slice(start, start + 80)
}

interface Use { file: string; key: string; fn: string; select: boolean }

function uses(): Use[] {
  const out: Use[] = []
  for (const file of files(SRC)) {
    const text = readFileSync(file, 'utf8')
    for (const m of text.matchAll(/queryKey:\s*\[/g)) {
      const start = (m.index ?? 0) + m[0].length - 1
      const key = balanced(text, start)
      const rest = text.slice(start + key.length, start + key.length + 500)
      const own = rest.indexOf('queryKey:') < 0 ? rest : rest.slice(0, rest.indexOf('queryKey:'))
      const call = /queryFn:\s*(?:async\s*)?(?:\(\)\s*=>\s*)?([\w.]+)/.exec(own)
      // a query that only invalidates (no queryFn) holds no data; one that reshapes the answer inside its queryFn (``.then(...)``) holds a shape of its own
      const reshaped = /queryFn:[^]*?\.then\(/.test(own.split('enabled:')[0])
      out.push({ file: file.slice(SRC.length + 1), key: key.replace(/\s+/g, ' '), fn: call ? call[1] + (reshaped ? ' (reshaped by .then)' : '') : '?', select: /\bselect\s*:/.test(own) })
    }
  }
  return out
}

describe('the keys of the cache of the queries (issue #605)', () => {
  const all = uses()
  const byName = new Map<string, Use[]>()
  for (const u of all) {
    const name = /\[\s*'([^']+)'/.exec(u.key)?.[1] ?? u.key
    byName.set(name, [...(byName.get(name) ?? []), u])
  }

  it('finds the queries of the app (the check looks at something)', () => {
    expect(all.length).toBeGreaterThan(30)
    expect(byName.get('team-list')?.length).toBeGreaterThanOrEqual(5)
  })

  it('every name of key is read with ONE function: the same key never holds two shapes', () => {
    const clashes = [...byName.entries()]
      .map(([name, list]) => ({ name, fns: [...new Set(list.filter(u => u.fn !== '?').map(u => u.fn))], where: list.map(u => `${u.file} ${u.key} -> ${u.fn}`) }))
      .filter(c => c.fns.length > 1)
    expect(clashes).toEqual([])
  })
})
