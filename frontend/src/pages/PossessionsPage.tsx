/**
 * PossessionsPage
 * Tabla de ritmo/eficiencia con cuartiles (3 vistas: resumen, estilo propio, rival) + scatter Ritmo × OER
 * + scatter % Rápidas × OER Rápidas. Los scatter muestran el logo FEB de cada equipo.
 */
import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Activity } from 'lucide-react'

import { useCollection } from '@/context/CollectionContext'
import { fetchPossessionQualityCsv, fetchPossessionsCsv, getPossessionStats, getTeamConsistency, type PossessionStat, type CVMap } from '@/api/client'
import PageTransition from '@/components/ui/PageTransition'
import PageHeader from '@/components/ui/PageHeader'
import Button from '@/components/ui/Button'
import { saveBlob } from '@/lib/download'
import Tabs from '@/components/ui/Tabs'
import SegmentedControl from '@/components/ui/SegmentedControl'
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
  const [exporting, setExporting] = useState<'possessions' | 'quality' | null>(null)
  const [exportError, setExportError] = useState<string | null>(null)

  /** Makes one of the two CSV files (from the published text or the API's file) and hands it to the browser. */
  async function exportCsv(kind: 'possessions' | 'quality') {
    if (!collection) return
    setExporting(kind); setExportError(null)
    try {
      const blob = await (kind === 'possessions' ? fetchPossessionsCsv : fetchPossessionQualityCsv)(collection.name)
      saveBlob(blob, `${kind === 'possessions' ? 'posesiones' : 'calidad_pbp'}_${collection.name}.csv`)
    } catch (error) {
      setExportError(error instanceof Error ? error.message : 'No se pudo descargar el fichero')
    } finally {
      setExporting(null)
    }
  }

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
        <PageHeader title="Análisis de Posesiones" subtitle={collection?.label}
          actions={collection && (
            <>
              <Button variant="secondary" loading={exporting === 'possessions'} onClick={() => void exportCsv('possessions')}>Exportar CSV</Button>
              <Button variant="secondary" loading={exporting === 'quality'} onClick={() => void exportCsv('quality')}>Calidad PBP CSV</Button>
            </>
          )} />
        {exportError && <p role="alert" className="text-sm text-bad">{exportError}</p>}
        <Tabs label="Partes del análisis de posesiones" tabs={TABS.map(([id, label]) => ({ id, label }))} value={tab} onChange={setTab} />

        {isLoading ? (
          <div className="card p-16 flex justify-center">
            <div className="w-8 h-8 border-2 border-secondary-text border-t-transparent rounded-full animate-spin" />
          </div>
        ) : stats.length === 0 ? (
          <div className="card p-10 flex flex-col items-center gap-3 text-center">
            <Activity className="w-10 h-10 text-secondary-text opacity-40" />
            <p className="text-ink-muted text-sm">Sin datos de posesiones para esta colección</p>
          </div>
        ) : tab === 'table' ? (
          <div className="space-y-3">
            <SegmentedControl label="Vista de la tabla" size="md" value={view} onChange={setView}
              options={VIEWS.map(v => ({ value: v.key, label: v.label }))} />
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
