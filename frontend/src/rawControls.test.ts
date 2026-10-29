/// <reference types="node" />
import { readdirSync, readFileSync } from 'node:fs'
import { join, relative } from 'node:path'
import { describe, expect, it } from 'vitest'

// Issue #190: the base components (components/ui: Button, Field/Input/Select, SegmentedControl, Tabs, PageHeader…) replace the raw
// controls that every page styled its own way. A ratchet: no file may get more raw ones than it has today, a new file none, and when a
// page is moved to the components (U5) its number goes down here too, so the list only shrinks. Guide: docs/UI.md.
const SRC = __dirname
const RAW: [string, RegExp][] = [['button', /<button\b/g], ['select', /<select\b/g], ['input', /<input\b/g], ['h1', /<h1\b/g]]

/** Raw controls of each file today (button / select / input / h1). */
const BASELINE: Record<string, [number, number, number, number]> = {
  'components/AdminKeyField.tsx': [2, 0, 1, 0],
  'components/Layout.tsx': [1, 0, 0, 0],
  'components/PlayerSelect.tsx': [0, 2, 1, 0],
  'components/Sidebar.tsx': [1, 0, 0, 0],
  'pages/AdminPage.tsx': [12, 1, 1, 1],
  'pages/ComparativasPage.tsx': [3, 0, 2, 1],
  'pages/HomePage.tsx': [4, 0, 0, 1],
  'pages/InOutPage.tsx': [1, 0, 0, 1],
  'pages/LineupsPage.tsx': [3, 0, 0, 1],
  'pages/LivePrepPage.tsx': [2, 2, 3, 1],
  'pages/PbpAnalysisPage.tsx': [1, 0, 0, 1],
  'pages/RotacionesPage.tsx': [1, 0, 0, 1],
  'pages/ScoutingRivalPage.tsx': [2, 2, 0, 1],
  'pages/ShotChartPage.tsx': [4, 1, 0, 1],
}

function sources(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap(entry => {
    const path = join(dir, entry.name)
    if (entry.isDirectory()) return entry.name === 'test' ? [] : sources(path)
    return entry.name.endsWith('.tsx') && !entry.name.endsWith('.test.tsx') ? [path] : []
  })
}

function counts(): Record<string, [number, number, number, number]> {
  return Object.fromEntries(sources(SRC)
    .map(file => [relative(SRC, file).replace(/\\/g, '/'), file] as const)
    .filter(([name]) => !name.startsWith('components/ui/'))                       // the components themselves are made of them
    .map(([name, file]) => {
      const code = readFileSync(file, 'utf8')
      return [name, RAW.map(([, re]) => code.match(re)?.length ?? 0) as [number, number, number, number]] as const
    })
    .filter(([, n]) => n.some(Boolean)))
}

describe('raw controls (issue #190)', () => {
  const now = counts()

  it('no page gets more raw controls than it had, and a new one has none: use the components of components/ui', () => {
    const grown = Object.entries(now).flatMap(([name, n]) => RAW.flatMap(([what], i) =>
      n[i] > (BASELINE[name]?.[i] ?? 0) ? [`${name}: ${n[i]} <${what}> (máximo ${BASELINE[name]?.[i] ?? 0})`] : []))
    expect(grown).toEqual([])
  })

  it('the baseline goes down with every page moved to the components (lower it here)', () => {
    const lower = Object.entries(BASELINE).flatMap(([name, base]) => RAW.flatMap(([what], i) =>
      (now[name]?.[i] ?? 0) < base[i] ? [`${name}: ${now[name]?.[i] ?? 0} <${what}> (la línea base dice ${base[i]})`] : []))
    expect(lower).toEqual([])
  })
})
