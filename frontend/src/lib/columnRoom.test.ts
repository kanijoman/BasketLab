import { describe, expect, it } from 'vitest'
import { BADGE_ROOM, roomForBadges } from './columnRoom'

describe('roomForBadges', () => {
  it('keeps the width of a column that has no badge and adds the room of each one that can sit next to the figure', () => {
    expect(roomForBadges(60, {})).toBe(60)
    expect(roomForBadges(60, { cv: true })).toBe(60 + BADGE_ROOM.cv)
    expect(roomForBadges(60, { trend: true })).toBe(60 + BADGE_ROOM.trend)
    expect(roomForBadges(60, { cv: true, trend: true })).toBe(60 + BADGE_ROOM.cv + BADGE_ROOM.trend)
  })
})
