import { describe, expect, it } from 'vitest'
import { pruneRecents, type RecentCollection } from './recents'

const recent = (name: string): RecentCollection => ({ name, label: name, isFbcyl: false, accessedAt: '2026-10-09T10:00:00Z' })

describe('pruneRecents', () => {
  it('drops the recent collections that no longer exist in the database', () => {
    const kept = pruneRecents([recent('A'), recent('GONE'), recent('B')], [{ name: 'A' }, { name: 'B' }])
    expect(kept.map(r => r.name)).toEqual(['A', 'B'])
  })

  it('keeps the order and everything when all of them still exist', () => {
    const all = [recent('B'), recent('A')]
    expect(pruneRecents(all, [{ name: 'A' }, { name: 'B' }])).toEqual(all)
  })

  it('an empty list of collections empties the recents', () => {
    expect(pruneRecents([recent('A')], [])).toEqual([])
  })
})
