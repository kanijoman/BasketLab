import { describe, expect, it } from 'vitest'
import type { NextMatch } from '../package/upcoming'
import { planReminders, reminderId, DEFAULT_LEAD_MIN } from './schedule'

const next = (code: string, start: string | null, fav = 'LEONESA', ownId = '1008857'): NextMatch => ({
  favorite: { teamId: ownId, name: fav },
  round: { collection: 'SEGUNDA_A', round: 4, file: 'f', sha256: 'x', bytes: 1, club: false, matches: [],
    competition: { key: 'k', label: 'SEGUNDA FEB · Liga Regular "A"', competition: 'SEGUNDA FEB', group: 'Liga Regular "A"', season: '2026/2027', level: 3, gender: 'M' } },
  match: { code, start, home: { id: ownId, name: fav }, away: { id: '2', name: 'ZAMORA' }, own_id: ownId, is_club: false },
  ownId, rival: { id: '2', name: 'ZAMORA' },
})
const NOW = new Date('2026-10-22T12:00:00')

describe('the reminders of the matches of the teams of interest (issue #482)', () => {
  it('one reminder per match, 30 minutes before the kick-off, with the teams, the time and the competition', () => {
    const [r] = planReminders([next('1', '2026-10-24T19:30')], NOW)
    expect(DEFAULT_LEAD_MIN).toBe(30)
    expect(r.at).toEqual(new Date('2026-10-24T19:00:00'))
    expect(r.title).toBe('LEONESA juega en 30 min')
    expect(r.body).toContain('LEONESA – ZAMORA')
    expect(r.body).toContain('19:30')
    expect(r.body).toContain('SEGUNDA FEB')
    expect(r.code).toBe('1')
  })

  it('the lead time is a setting', () => {
    expect(planReminders([next('1', '2026-10-24T19:30')], NOW, 60)[0].at).toEqual(new Date('2026-10-24T18:30:00'))
    expect(planReminders([next('1', '2026-10-24T19:30')], NOW, 60)[0].title).toBe('LEONESA juega en 60 min')
  })

  it('a match that already started, or whose reminder time has passed, is not reminded', () => {
    expect(planReminders([next('1', '2026-10-22T11:00'), next('2', '2026-10-22T12:20')], NOW)).toEqual([])
    expect(planReminders([next('3', '2026-10-22T12:30')], NOW)).toHaveLength(1)           // exactly the lead time away: still in the future
  })

  it('a match without a date cannot be reminded', () => {
    expect(planReminders([next('1', null)], NOW)).toEqual([])
  })

  it('the id of a reminder is the same for the same match and team and different otherwise (so it can be replaced, not duplicated)', () => {
    const a = reminderId('1', '1008857')
    expect(reminderId('1', '1008857')).toBe(a)
    expect(new Set([a, reminderId('2', '1008857'), reminderId('1', '1008978')]).size).toBe(3)
    expect(Number.isInteger(a) && a > 0 && a < 2 ** 31).toBe(true)                    // Android notification ids are 32-bit
  })

  it('two teams of interest in the same match give two reminders', () => {
    const rs = planReminders([next('1', '2026-10-24T19:30', 'LEONESA', '1008857'), next('1', '2026-10-24T19:30', 'ZAMORA', '2')], NOW)
    expect(rs.map(r => r.title)).toEqual(['LEONESA juega en 30 min', 'ZAMORA juega en 30 min'])
    expect(new Set(rs.map(r => r.id)).size).toBe(2)
  })
})
