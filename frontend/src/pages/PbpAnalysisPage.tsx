/**
 * PbpAnalysisPage — «Análisis pbp» (#359): what the play-by-play adds to the team stats, FEB only.
 * Four tables with the usual quartile colours: points by origin (own and conceded), figures by quarter, situations (after
 * timeouts, first possessions, first / last two minutes) and the effect of the timeouts.
 */
import { useMemo, useState } from 'react'
import { Microscope } from 'lucide-react'

import { useByPeriod, usePointsByOrigin, useSituations, useTimeoutEffects } from '@/api/pbpExtended'
import DataTable from '@/components/ui/DataTable'
import PageTransition from '@/components/ui/PageTransition'
import { useCollection } from '@/context/CollectionContext'
import { computeQuartileMap } from '@/lib/quartiles'
import {
  NUMERIC_COLUMN_SIZE, ORIGIN_KEYS, ORIGIN_REVERSE, ORIGIN_VIEWS, PERIODS, PERIOD_KEYS, PERIOD_REVERSE, SITUATION_KEYS, SITUATION_REVERSE,
  TIMEOUT_KEYS, TIMEOUT_REVERSE, flattenPeriod, flattenSituations, flattenTimeouts, originColumns, periodColumns, situationColumns,
  timeoutColumns, type OriginView,
} from './pbpAnalysis/columns'

type Tab = 'origin' | 'period' | 'situations' | 'timeouts'

const TABS: [Tab, string, string][] = [
  ['origin', 'Por origen', 'Puntos según cómo empezó la posesión, del banquillo y en la pintura, por partido. Definición por posesión: más generosa que la que usa la FEB en su PDF (que no se puede reproducir desde el play-by-play). El contraataque es una estimación propia (canasta en ≤ 6 s tras pérdida rival, con o sin robo, o rebote defensivo): se queda de media 0,6 puntos por debajo de la FEB.'],
  ['period', 'Por cuarto', 'Puntos, posesiones, ratings, ritmo y factores por equipo y periodo (la prórroga agrupa todas).'],
  ['situations', 'Situaciones', 'Puntos por posesión tras un tiempo muerto propio o del rival, en la primera posesión de cada periodo, y el rating neto en los primeros y últimos 2:00 frente al resto del periodo.'],
  ['timeouts', 'Tiempos muertos', 'Rating neto en las 5 posesiones de cada equipo antes y después de cada tiempo muerto, y % tras los que mejora quien lo pidió. Quedan fuera los del último minuto del periodo (umbrales provisionales).'],
]

function Pills<T extends string>({ items, value, onChange, label }: { items: { key: T; label: string }[]; value: T; onChange: (v: T) => void; label: string }) {
  return (
    <div role="group" aria-label={label} className="inline-flex rounded-lg overflow-hidden border border-surface-border text-sm">
      {items.map(i => (
        <button
          key={i.key}
          onClick={() => onChange(i.key)}
          aria-pressed={value === i.key}
          className={`px-4 py-1.5 font-medium transition-colors ${value === i.key ? 'bg-accent-500 text-white' : 'text-ink-secondary hover:bg-surface-hover'}`}
        >
          {i.label}
        </button>
      ))}
    </div>
  )
}

function Notice({ children }: { children: React.ReactNode }) {
  return (
    <div className="card p-10 flex flex-col items-center gap-3 text-center">
      <Microscope className="w-10 h-10 text-accent-400 opacity-40" />
      <p className="text-ink-secondary text-sm max-w-2xl">{children}</p>
    </div>
  )
}

function Table<T extends object>({ data, columns, keys, reverse, filename }: {
  data: T[]; columns: Parameters<typeof DataTable<T>>[0]['columns']; keys: string[]; reverse: string[]; filename: string
}) {
  const quartiles = useMemo(() => computeQuartileMap(data, keys), [data, keys])
  const csvHeaders = useMemo(() => Object.keys(data[0] ?? {}).filter(k => typeof (data[0] as Record<string, unknown>)[k] !== 'object')
    .map(key => ({ key, label: key })), [data])
  return (
    <DataTable
      columns={columns}
      data={data}
      quartiles={quartiles}
      reverseColumns={reverse}
      defaultColumnSize={NUMERIC_COLUMN_SIZE}
      searchable
      searchPlaceholder="Buscar equipo…"
      exportOptions={{ filename, csvHeaders, csvData: data as unknown as Record<string, unknown>[] }}
    />
  )
}

export default function PbpAnalysisPage() {
  const { collection } = useCollection()
  const name = collection && !collection.isFbcyl ? collection.name : undefined
  const [tab, setTab] = useState<Tab>('origin')
  const [originView, setOriginView] = useState<OriginView>('own')
  const [period, setPeriod] = useState('1')

  const origin = usePointsByOrigin(name)
  const periods = useByPeriod(name)
  const situations = useSituations(name)
  const timeouts = useTimeoutEffects(name)
  const current = { origin, period: periods, situations, timeouts }[tab]

  const periodRows = useMemo(() => flattenPeriod(periods.data ?? [], period), [periods.data, period])
  const situationRows = useMemo(() => flattenSituations(situations.data ?? []), [situations.data])
  const timeoutRows = useMemo(() => flattenTimeouts(timeouts.data ?? []), [timeouts.data])
  const originCols = useMemo(() => originColumns(originView), [originView])
  const periodCols = useMemo(() => periodColumns(), [])
  const situationCols = useMemo(() => situationColumns(), [])
  const timeoutCols = useMemo(() => timeoutColumns(), [])
  const originKeys = originView === 'opp' ? ORIGIN_KEYS.filter(k => k.startsWith('opp_')) : ORIGIN_KEYS.filter(k => !k.startsWith('opp_'))

  let body: React.ReactNode
  if (collection?.isFbcyl) {
    body = <Notice>El análisis del play-by-play solo está disponible para FEB por ahora.</Notice>
  } else if (current.isLoading) {
    body = <div className="card p-16 flex justify-center"><div className="w-8 h-8 border-2 border-accent-400 border-t-transparent rounded-full animate-spin" /></div>
  } else if (current.isError) {
    body = <Notice>No se han podido cargar los datos: {(current.error as Error | null)?.message ?? 'error desconocido'}</Notice>
  } else if (!current.data || current.data.length === 0) {
    body = (
      <Notice>
        Sin datos del play-by-play para esta colección. Solo los partidos de FEB con el campo DERIVED de la versión actual tienen
        estas cifras: se rellena solo tras cada actualización de Atlas, o con <code>python run_backfill_derived.py</code> en local.
      </Notice>
    )
  } else if (tab === 'origin') {
    body = (
      <div className="space-y-3">
        <Pills items={ORIGIN_VIEWS} value={originView} onChange={setOriginView} label="Puntos propios o concedidos" />
        <Table data={origin.data!} columns={originCols} keys={originKeys} reverse={ORIGIN_REVERSE[originView]} filename={`pbp_origen_${collection?.name}`} />
      </div>
    )
  } else if (tab === 'period') {
    body = (
      <div className="space-y-3">
        <Pills items={PERIODS} value={period} onChange={setPeriod} label="Periodo" />
        {periodRows.length === 0
          ? <Notice>Ningún equipo ha jugado este periodo en los partidos con datos.</Notice>
          : <Table data={periodRows} columns={periodCols} keys={PERIOD_KEYS} reverse={PERIOD_REVERSE} filename={`pbp_cuarto_${period}_${collection?.name}`} />}
      </div>
    )
  } else if (tab === 'situations') {
    body = <Table data={situationRows} columns={situationCols} keys={SITUATION_KEYS} reverse={SITUATION_REVERSE} filename={`pbp_situaciones_${collection?.name}`} />
  } else {
    body = <Table data={timeoutRows} columns={timeoutCols} keys={TIMEOUT_KEYS} reverse={TIMEOUT_REVERSE} filename={`pbp_tiempos_muertos_${collection?.name}`} />
  }

  return (
    <PageTransition>
      <div className="space-y-4">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div>
            <h1 className="text-2xl font-bold text-ink-primary">Análisis pbp</h1>
            <p className="text-ink-secondary text-sm mt-0.5">{collection?.label}</p>
          </div>
          <Pills items={TABS.map(([key, label]) => ({ key, label }))} value={tab} onChange={setTab} label="Sección" />
        </div>
        <p className="text-ink-secondary text-sm max-w-4xl">{TABS.find(([key]) => key === tab)![2]}</p>
        {body}
      </div>
    </PageTransition>
  )
}
