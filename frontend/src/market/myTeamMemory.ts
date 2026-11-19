// The team the staff chose in «Mi equipo» (#882): remembered in THIS browser (`localStorage`, always in try/catch: blocked storage must not break the page) until there are accounts (#896) and it goes to the
// space of the club. The address is the first truth of the page (it is shared and reloaded); this only fills it in when it says nothing.
const KEY = 'talent-my-team'

export interface ChosenTeam { comp: string; team: string }

/** The remembered team, or null (nothing, or a value that is not one). */
export function recallTeam(): ChosenTeam | null {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(KEY) ?? 'null')
    const v = value as Partial<ChosenTeam> | null
    return v && typeof v === 'object' && typeof v.comp === 'string' && typeof v.team === 'string' ? { comp: v.comp, team: v.team } : null
  } catch { return null }
}

/** Remember the team (null forgets it). */
export function rememberTeam(team: ChosenTeam | null): void {
  try { if (team) localStorage.setItem(KEY, JSON.stringify(team)); else localStorage.removeItem(KEY) } catch { /* blocked storage: only this page */ }
}
