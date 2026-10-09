/**
 * PossessionsPage
 * Tabla de ritmo/eficiencia con cuartiles (3 vistas: resumen, estilo propio, rival) + scatter Ritmo × OER
 * + scatter % Rápidas × OER Rápidas. Los scatter muestran el logo FEB de cada equipo.
 */
import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Activity } from 'lucide-react'

import { useCollection } from '@/context/CollectionContext'
import { getPossessionQualityExportUrl, getPossessionStats, getPossessionsExportUrl, getTeamConsistency, type PossessionStat, type CVMap } from '@/api/client'
import PageTransition from '@/components/ui/PageTransition'
import DataTable from '@/components/ui/DataTable'
import ScatterCard from './possessions/ScatterCard'
import {
  NUMERIC_COLUMN_SIZE, REVERSE_COLS, VIEWS, buildCols, buildQuartileMap, csvColumns, type PossessionView,
} from './possessions/columns'

// -- Component ----------------------------------------------------------------

type Tab = 'table' | 'scatter' | 'scatter2'

export default function PossessionsPage() {
  const { collection } = useCollection()
  const [tab, setTab] = useState<Tab>('table')
  const [view, setView] = useState<PossessionView>('summary')

  const { data: stats = [], isLoading } = useQuery<PossessionStat[]>({
    queryKey: ['possessions', collection?.name],
    queryFn: () => getPossessionStats(collection!.name),
    enabled: Boolean(collection),
    staleTime: 5 * 60_000,
    refetchOnMount: 'always',
  })

  const { data: consistencyRaw } = useQuery({
    queryKey:  ['team-consistency-v2', collection?.name],
    queryFn:   () => getTeamConsistency(collection!.name),
    enabled:   Boolean(collection),
    staleTime: 30 * 60_000,
  })
  const consistencyByName: CVMap | null = consistencyRaw?.own ?? null

  const cols = useMemo(() => buildCols(view, consistencyByName), [view, consistencyByName])
  const quartileMap = useMemo(() => buildQuartileMap(stats), [stats])

  // Fast-possession scatter — filter teams without PBP data
  const statsWithPBP = useMemo(
    () => stats.filter(d => d.pct_fast != null && d.oer_fast != null),
    [stats],
  )

  const TABS: [Tab, string][] = [
    ['table',    'Tabla'],
    ['scatter',  'Scatter Ritmo × OER'],
    ['scatter2', 'Scatter % Rápidas × OER'],
  ]

  return (
    <PageTransition>
      <div className="space-y-4">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div>
            <h1 className="text-2xl font-bold text-ink-primary">Análisis de Posesiones</h1>
            <p className="text-ink-secondary text-sm mt-0.5">{collection?.label}</p>
          </div>
          <div className="flex items-center gap-2">
            {collection && (
              <>
                <a
                  href={getPossessionsExportUrl(collection.name)}
                  download
                  className="px-3 py-1.5 text-sm font-medium rounded-lg border border-surface-border text-ink-secondary hover:bg-surface-hover transition-colors"
                >
                  Exportar CSV
                </a>
                <a
                  href={getPossessionQualityExportUrl(collection.name)}
                  download
                  className="px-3 py-1.5 text-sm font-medium rounded-lg border border-surface-border text-ink-secondary hover:bg-surface-hover transition-colors"
                >
                  Calidad PBP CSV
                </a>
              </>
            )}
          {/* Tab toggle */}
          <div className="flex rounded-lg overflow-hidden border border-surface-border text-sm">
            {TABS.map(([key, lbl]) => (
              <button
                key={key}
                onClick={() => setTab(key)}
                className={`px-4 py-1.5 font-medium transition-colors ${
                  tab === key ? 'bg-accent-500 text-white' : 'text-ink-secondary hover:bg-surface-hover'
                }`}
              >
                {lbl}
              </button>
            ))}
          </div>
          </div>
        </div>

        {isLoading ? (
          <div className="card p-16 flex justify-center">
            <div className="w-8 h-8 border-2 border-accent-400 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : stats.length === 0 ? (
          <div className="card p-10 flex flex-col items-center gap-3 text-center">
            <Activity className="w-10 h-10 text-accent-400 opacity-40" />
            <p className="text-ink-secondary text-sm">Sin datos de posesiones para esta colección</p>
          </div>
        ) : tab === 'table' ? (
          <div className="space-y-3">
            <div role="group" aria-label="Vista de la tabla" className="inline-flex rounded-lg overflow-hidden border border-surface-border text-sm">
              {VIEWS.map(v => (
                <button
                  key={v.key}
                  onClick={() => setView(v.key)}
                  aria-pressed={view === v.key}
                  className={`px-4 py-1.5 font-medium transition-colors ${
                    view === v.key ? 'bg-accent-500 text-white' : 'text-ink-secondary hover:bg-surface-hover'
                  }`}
                >
                  {v.label}
                </button>
              ))}
            </div>
            <DataTable
              columns={cols}
              data={stats}
              quartiles={quartileMap}
              reverseColumns={REVERSE_COLS}
              defaultColumnSize={NUMERIC_COLUMN_SIZE}
              searchable
              searchPlaceholder="Buscar equipo…"
              exportOptions={{
                filename: `posesiones_${collection?.name}`,
                csvHeaders: csvColumns(),
                csvData: stats,
              }}
            />
          </div>
        ) : tab === 'scatter' ? (
          <ScatterCard
            xKey="pace"
            yKey="oer"
            xLabel="Ritmo (pos/P)"
            yLabel="OER"
            description="Ritmo (posesiones/partido) × OER (eficiencia ofensiva · pts/100 pos.) — líneas discontinuas = mediana de la liga"
            data={stats}
            mode="pace"
          />
        ) : (
          <ScatterCard
            xKey="pct_fast"
            yKey="oer_fast"
            xLabel="% Posesiones Rápidas (≤8s)"
            yLabel="OER Rápidas"
            description="% de posesiones rápidas (≤8s) × eficiencia ofensiva en esas posesiones — líneas discontinuas = mediana de la liga"
            data={statsWithPBP}
            mode="fast"
          />
        )}
      </div>
    </PageTransition>
  )
}
