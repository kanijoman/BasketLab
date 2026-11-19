// The shots by zone of the row of the profile (#994): the ten zones of the engine with made, attempted and percentage, and the league percentage beside it. The file of the competition is opened only
// here (the search never needs it) and with the same key as the rows. A player without shots in it, or a competition without the file, is said, never drawn as zeros. Rules in `zones.ts`.
import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import Card from '@/components/ui/Card'
import Spinner from '@/components/ui/Spinner'
import { loadCompetitionZones } from './data'
import type { SearchRow } from './search'
import { zoneLines, zoneTotal } from './zones'

const dash = <span className="text-ink-faint" title="Sin dato">—</span>
const one = (v: number | null) => (v === null ? dash : v.toFixed(1))

export default function PlayerZones({ row }: { row: SearchRow }) {
  const zones = useQuery({ queryKey: ['talent-zones', row.comp_key], queryFn: () => loadCompetitionZones(row.comp_key), retry: false })
  const lines = useMemo(() => (zones.data ? zoneLines(zones.data, row.person_id, row.team_id) : null), [zones.data, row.person_id, row.team_id])
  const total = lines ? zoneTotal(lines) : null
  return (
    <Card title="Zonas de tiro">
      {zones.isLoading && <Spinner size="sm" label="Cargando las zonas" />}
      {zones.isError && <p className="text-sm text-ink-muted">Esta competición no tiene datos de zonas publicados.</p>}
      {zones.isSuccess && !lines && <p className="text-sm text-ink-muted">Sin tiros registrados de este jugador en {row.competition} {row.season_label}.</p>}
      {lines && total && (
        <>
          <p className="mb-2 text-xs text-ink-muted">{row.season_label} · {row.competition} · {row.team_name}. El porcentaje de la liga es el de todos los tiros de la competición en esa zona.</p>
          <div role="region" tabIndex={0} aria-label="Tabla de zonas de tiro, desplazable" className="overflow-x-auto">
            <table aria-label="Tiros por zona" className="w-full border-collapse text-xs sm:text-sm">
              <thead>
                <tr className="text-left text-xs text-ink-muted">
                  <th scope="col" className="px-1.5 py-2 sm:px-2 font-medium">Zona</th><th scope="col" title="Acertados" className="px-1.5 py-2 sm:px-2 font-medium">Anot.</th><th scope="col" title="Intentos" className="px-1.5 py-2 sm:px-2 font-medium">Int.</th>
                  <th scope="col" className="px-1.5 py-2 sm:px-2 font-medium">%</th><th scope="col" className="px-1.5 py-2 sm:px-2 font-medium">% liga</th>
                </tr>
              </thead>
              <tbody>
                {lines.map(l => (
                  <tr key={l.key} className="border-t border-line/50">
                    <th scope="row" className="px-1.5 py-2 sm:px-2 text-left font-normal text-ink">{l.label}</th>
                    <td className="px-1.5 py-2 sm:px-2 tabular-nums">{l.made}</td><td className="px-1.5 py-2 sm:px-2 tabular-nums">{l.att}</td>
                    <td className="px-1.5 py-2 sm:px-2 tabular-nums">{one(l.pct)}</td><td className="px-1.5 py-2 sm:px-2 tabular-nums text-ink-muted">{one(l.leaguePct)}</td>
                  </tr>
                ))}
                <tr className="border-t-2 border-line font-medium">
                  <th scope="row" className="px-1.5 py-2 sm:px-2 text-left">Total</th><td className="px-1.5 py-2 sm:px-2 tabular-nums">{total.made}</td><td className="px-1.5 py-2 sm:px-2 tabular-nums">{total.att}</td>
                  <td className="px-1.5 py-2 sm:px-2 tabular-nums">{one(total.att ? (100 * total.made) / total.att : null)}</td><td className="px-1.5 py-2 sm:px-2">{dash}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </>
      )}
    </Card>
  )
}
