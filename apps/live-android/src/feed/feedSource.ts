/** Which league a match of the live mode belongs to, from its code (issue #446): FEB codes are digits (`2524475`), the ones of FBCYL are `fbcyl-<idMatch>` (the publisher writes them so: `scraper/fbcyl_calendar`). */
export type FeedSource = 'FEB' | 'FBCYL'

const FBCYL_CODE = /^fbcyl-(\d+)$/

export const isFbcylCode = (code: string): boolean => FBCYL_CODE.test(code)

export const sourceOf = (code: string): FeedSource => (isFbcylCode(code) ? 'FBCYL' : 'FEB')

/** The `idMatch` of a FBCYL code (the match in the calendar of the federation); null for any other code. */
export const fbcylMatchId = (code: string): string | null => FBCYL_CODE.exec(code)?.[1] ?? null

/** The code as the staff know it: the number the federation shows (FEB: the code itself; FBCYL: the `idMatch` without the prefix). */
export const shownCode = (code: string): string => fbcylMatchId(code) ?? code

/** What a code the user types or a package carries must look like to connect: digits (FEB) or a FBCYL code. */
export const isConnectable = (code: string): boolean => /^\d+$/.test(code) || isFbcylCode(code)
