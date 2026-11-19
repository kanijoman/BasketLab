import { describe, expect, it } from 'vitest'
import { initialsOf, playerPhotoUrl } from './playerPhoto'

describe('the photo of a player (#1010)', () => {
  it('is the one FEB publishes for his idPlayer, and nothing for who has no FEB id', () => {
    expect(playerPhotoUrl('feb:10100')).toBe('https://imagenes.feb.es/foto.aspx?c=10100')
    expect(playerPhotoUrl('fbcyl:34001-00')).toBeNull()                  // FBCYL has no public photo address (it is asked with a token): initials
    expect(playerPhotoUrl('feb:')).toBeNull()
    expect(playerPhotoUrl('feb:no-es-un-numero')).toBeNull()
    expect(playerPhotoUrl('')).toBeNull()
  })

  it('says its initials: the first letters of the first two words, in capitals, whatever the accents or blanks', () => {
    expect(initialsOf('ANA BEATRIZ CASTRO')).toBe('AB')
    expect(initialsOf('  álvaro   núñez ')).toBe('ÁN')
    expect(initialsOf('Cher')).toBe('C')
    expect(initialsOf('')).toBe('?')
  })
})
