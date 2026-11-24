/** Player picker: name search + team filter + player dropdown (IN/OUT page). */
import { useMemo, useState } from 'react'
import type { PlayerStat } from '@/api/client'
import { playerKey } from '@/lib/playerKey'
import { Input, Select } from '@/components/ui/Field'
import { useLeftPlayers } from '@/lib/useLeftPlayers'

export type TeamOption = { id: string; name: string }

export default function PlayerSelect({
  label, value, onChange, players, teams: teamsProp, collection,
}: { label: string; value: string; onChange: (v: string) => void; players: PlayerStat[]; teams?: TeamOption[]; collection?: string }) {
  const [nameFilter, setNameFilter] = useState('')
  const [teamFilter, setTeamFilter] = useState('')
  const left = useLeftPlayers(collection, teamFilter)           // #1082: choosing a team hides who has left it; with «Todos los equipos» the list keeps everybody

  // Derive {id, name} pairs from the loaded players when no independent list is available
  const derivedTeams = useMemo((): TeamOption[] => {
    const map = new Map<string, string>()
    for (const p of players) {
      const id = String(p.team_id ?? '')
      const name = (p.team_name ?? '').trim()
      if (id && name) map.set(id, name)
    }
    return Array.from(map.entries())
      .map(([id, name]) => ({ id, name }))
      .sort((a, b) => a.name.localeCompare(b.name))
  }, [players])

  // Prefer independent team list (from getTeamStats) to decouple dropdown
  // availability from full player load
  const teams = teamsProp && teamsProp.length > 0 ? teamsProp : derivedTeams

  const filtered = useMemo(
    () => players.filter(p => {
      // Use team_id for stable matching — team names can change during the season
      const matchesTeam = teamFilter === '' || String(p.team_id ?? '') === teamFilter
      const matchesName = nameFilter === '' || p.player_name.toLowerCase().includes(nameFilter.toLowerCase())
      return matchesTeam && matchesName && !(teamFilter !== '' && left.has(String(p.player_id)))
    }),
    [players, teamFilter, nameFilter, left],
  )

  return (
    <div className="flex flex-col gap-2">
      <label className="text-xs text-ink-muted font-medium uppercase tracking-wide">{label}</label>
      <div className="flex gap-2">
        <Input
          type="text"
          aria-label={`${label}: buscar por nombre`}
          placeholder="Buscar nombre…"
          value={nameFilter}
          onChange={e => setNameFilter(e.target.value)}
          className="min-w-0 flex-1"
        />
        <div className="min-w-0 max-w-[50%] flex-1">
          <Select aria-label={`${label}: filtrar por equipo`} className="min-w-0" value={teamFilter} onChange={e => setTeamFilter(e.target.value)}>
            <option value="">Todos los equipos</option>
            {teams.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
          </Select>
        </div>
      </div>
      <Select aria-label={label} className="w-full min-w-0" value={value} onChange={e => onChange(e.target.value)}>
        <option value="">— Selecciona jugador —</option>
        {filtered.map((p, idx) => (
          <option key={`${playerKey(p)}_${(p.team_name ?? '').trim()}_${idx}`} value={playerKey(p)}>
            {p.player_name} ({(p.team_name ?? '').trim() || '—'})
          </option>
        ))}
      </Select>
    </div>
  )
}
