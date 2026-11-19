/** The photo of a player (#1010): FEB publishes one by his `idPlayer` (the same id as `feb:<id>`); FBCYL has no public address for it (the federation's service asks for a token), so a FBCYL player is shown by his initials. */
export const playerPhotoUrl = (personId: string): string | null => {
  const id = /^feb:(\d+)$/.exec(personId)?.[1]
  return id ? `https://imagenes.feb.es/foto.aspx?c=${id}` : null
}

/** The first letters of the first two words of a name, in capitals (``?`` for nothing). */
export const initialsOf = (name: string): string =>
  name.trim().split(/\s+/).filter(Boolean).slice(0, 2).map(w => w.charAt(0).toLocaleUpperCase('es')).join('') || '?'
