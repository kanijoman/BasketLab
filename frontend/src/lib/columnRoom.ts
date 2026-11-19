/**
 * The room a numeric column needs for the badges that sit next to its figure (the σ dispersion badge of `CVBadge`, the trend of `DiffBadge`).
 * The tables have fixed-layout columns and cut what overflows the cell (on screen and, worse, in the PNG/PDF export), so a column that can carry a badge
 * is widened by what the badge measures; the cell also wraps as a last resort. Widths in px, measured on the 10 px badges of the web.
 */
export const BADGE_ROOM = { cv: 44, trend: 54 } as const

/** ``size`` plus the room of each badge the column can show. */
export const roomForBadges = (size: number, badges: { cv?: boolean; trend?: boolean }): number =>
  size + (badges.cv ? BADGE_ROOM.cv : 0) + (badges.trend ? BADGE_ROOM.trend : 0)
