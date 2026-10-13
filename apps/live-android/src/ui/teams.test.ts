import { describe, expect, it } from 'vitest'
import { initials, orderTeams } from './teams'

const OWN = { id: '1008631', name: 'MIPELLETYMAS B.F. LEON' }
const RIVAL = { id: '1008898', name: 'RECOLETAS ZAMORA' }

describe('orderTeams (the local team goes on the left, the visitor on the right)', () => {
  it('puts the rival on the left when it plays at home (Zamora - Leon)', () => {
    expect(orderTeams(OWN, RIVAL, '1008898')).toEqual({ home: RIVAL, away: OWN, ownIsHome: false })
  })

  it('puts our team on the left when it plays at home', () => {
    expect(orderTeams(OWN, RIVAL, '1008631')).toEqual({ home: OWN, away: RIVAL, ownIsHome: true })
  })

  it('without information about who is local, our team stays on the left (the previous behaviour)', () => {
    expect(orderTeams(OWN, RIVAL, null).home).toEqual(OWN)
    expect(orderTeams(OWN, RIVAL, undefined).home).toEqual(OWN)
  })

  it('an unknown id (neither team) is treated as no information', () => {
    expect(orderTeams(OWN, RIVAL, '999').home).toEqual(OWN)
  })
})

describe('initials', () => {
  it('uses the first letters of the first two significant words, skipping "B.F." style abbreviations', () => {
    expect(initials('MIPELLETYMAS B.F. LEON')).toBe('ML')
    expect(initials('RECOLETAS ZAMORA')).toBe('RZ')
  })

  it('a single word gives its first two letters', () => {
    expect(initials('Unicaja')).toBe('UN')
  })

  it('never crashes on an empty name', () => {
    expect(initials('')).toBe('?')
  })
})
