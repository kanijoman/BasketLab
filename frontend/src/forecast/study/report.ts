// The report of the walk-forward evaluation (#851): markdown in Spanish (the language of docs/evaluaciones) from the results of `walkForward`, with the decimal comma.
import { brier, calibrationTable, logLoss, Scores } from './metrics'
import type { HeadlineRow, LeverRecord, PreviewStudy, SeasonRow } from './walkForward'

export interface CompetitionResult {
  name: string
  gender: string
  games: number
  headline: HeadlineRow[]
  previews: PreviewStudy
  season: SeasonRow[]
}

const num = (x: number, digits = 3): string => (Number.isFinite(x) ? x.toFixed(digits).replace('.', ',') : '—')
const pc = (x: number, digits = 1): string => (Number.isFinite(x) ? `${(x * 100).toFixed(digits).replace('.', ',')} %` : '—')
const table = (head: string[], rows: (string | number)[][]): string => [`| ${head.join(' | ')} |`, `| ${head.map(() => '---').join(' | ')} |`, ...rows.map(r => `| ${r.join(' | ')} |`)].join('\n')
const mean = (xs: number[]): number => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : NaN)

const BUCKETS: [string, (played: number) => boolean][] = [['0-2', n => n <= 2], ['3-5', n => n >= 3 && n <= 5], ['6-9', n => n >= 6 && n <= 9], ['10+', n => n >= 10]]

function headlineScores(rows: HeadlineRow[]): Scores {
  const s = new Scores()
  for (const r of rows.filter(x => x.y !== 0.5)) s.add({ hit: r.p > 0.5 === (r.y === 1), logLoss: logLoss(r.p, r.y), baseLoss: logLoss(r.baseline, r.y), brier: brier(r.p, r.y), baseBrier: brier(r.baseline, r.y) })
  return s
}

function headlineSection(results: CompetitionResult[]): string {
  const all = results.flatMap(r => r.headline)
  const row = (label: string, rows: HeadlineRow[]): (string | number)[] => {
    const s = headlineScores(rows)
    return [label, s.n, pc(s.rate('hit')), num(s.mean('logLoss')), num(s.mean('baseLoss')), num(s.mean('brier')), num(s.mean('baseBrier'))]
  }
  const head = ['', 'Partidos', 'Acierto', 'Log loss', 'Log loss «gana el local»', 'Brier', 'Brier «gana el local»']
  return [
    '## Pronóstico del partido',
    'La probabilidad de victoria del equipo local con solo lo jugado antes de cada partido (rating bayesiano, ventaja de campo de la familia y ritmo del emparejamiento), frente a «el local gana tantas veces como lleva ganando».',
    '### Por partidos previos del equipo menos conocido', table(['Previos', ...head.slice(1)], BUCKETS.map(([label, inside]) => row(label, all.filter(r => inside(r.played))) as (string | number)[])),
    '### Por competición', table(['Competición', ...head.slice(1)], [...results.map(r => row(r.name, r.headline)), row('Todas', all)]),
  ].join('\n\n')
}

function scenariosSection(results: CompetitionResult[]): string {
  const samples = results.flatMap(r => r.previews.samples)
  const buckets = results.map(r => r.previews.buckets).filter(b => b.n)
  const weighted = (key: 'brier' | 'brierBaseline' | 'logScore' | 'logScoreBaseline'): number => buckets.reduce((s, b) => s + b[key] * b.n, 0) / buckets.reduce((s, b) => s + b.n, 0)
  return [
    '## Escenarios',
    'La bolsa de escenarios (un escenario por partido y lado de la temporada hasta ese día), anclada para dar exactamente la probabilidad del pronóstico.',
    table(['Partidos previsualizados', 'Fallos de anclaje', 'Dispersión de los escenarios (pts)', 'Núcleo σ_u (pts)', '|μ* − μ| medio (pts)'],
      [[samples.length, results.reduce((s, r) => s + r.previews.anchoredFailures, 0), num(mean(samples.map(s => s.residualSd)), 2), num(mean(samples.map(s => s.sigmaU)), 2), num(mean(samples.map(s => Math.abs(s.muShift))), 2)]]),
    '### Los cuatro tramos de margen frente a lo que pasó',
    table(['', 'Brier (4 clases)', 'Log score'], [['Previa', num(weighted('brier')), num(weighted('logScore'))], ['Reparto histórico de la competición', num(weighted('brierBaseline')), num(weighted('logScoreBaseline'))]]),
  ].join('\n\n')
}

const SIDES: [string, (l: LeverRecord) => boolean][] = [['Todos', () => true], ['Ataque', l => l.side === 'attack'], ['Defensa', l => l.side === 'defence'], ['Ritmo', l => l.side === 'pace']]

function leversSection(results: CompetitionResult[]): string {
  const levers = results.flatMap(r => r.previews.levers)
  const rows = SIDES.map(([label, inside]) => {
    const mine = levers.filter(inside)
    const met = mine.filter(l => l.met)
    const missed = mine.filter(l => !l.met)
    return [label, mine.length, pc(met.length / (mine.length || NaN), 0), pc(mean(met.map(l => l.pWin))), pc(mean(met.map(l => l.y))), pc(mean(missed.map(l => l.y))),
      num(mean(met.map(l => brier(l.pWin, l.y)))), num(mean(met.map(l => brier(l.headline, l.y))))]
  })
  const calibration = calibrationTable(levers.filter(l => l.met).map(l => ({ p: l.pWin, y: l.y })), 5)
  return [
    '## Objetivos del partido',
    'Cada objetivo (hasta tres de ataque, tres de defensa y el ritmo) se comprueba desde el lado de los dos equipos: ¿lo alcanzó el partido que se jugó?, ¿ganó el equipo del objetivo? Lo que se evalúa es **la probabilidad condicional** («si pasa, ganamos tanto»): coincide con la frecuencia real de los partidos en que pasó cuando está calibrada.',
    table(['', 'Objetivos', 'Alcanzados', 'P(victoria) prevista si se alcanza', 'Victorias reales si se alcanza', 'Victorias reales si no', 'Brier de la prevista', 'Brier del pronóstico'], rows),
    '### Calibración de la probabilidad prevista cuando se alcanza el objetivo',
    table(['Prevista', 'Objetivos', 'Prevista (media)', 'Real'], calibration.map(b => [`${pc(b.from, 0)}–${pc(b.to, 0)}`, b.n, pc(b.predicted), pc(b.actual)])),
  ].join('\n\n')
}

function seasonSection(results: CompetitionResult[]): string {
  return [
    '## Simulación de la liga',
    'La simulación (2.000 temporadas) tras el 25, el 50 y el 75 % de la temporada, con los partidos del resto de la temporada como calendario, frente a la clasificación final. Línea base: «el orden de la tabla ese día se mantiene». RPS: error de la distribución del puesto final (menos es mejor); Brier de ser primero y de acabar entre los cuatro primeros.',
    ...results.flatMap(r => [`### ${r.name}`, table(['Corte', 'Partidos jugados', 'RPS', 'RPS orden actual', 'Brier 1.º', 'Brier 1.º orden actual', 'Brier top 4', 'Brier top 4 orden actual', 'Tiempo (ms)'],
      r.season.map(s => [pc(s.cut, 0), s.played, num(s.rps), num(s.rpsBaseline), num(s.brierFirst), num(s.brierFirstBaseline), num(s.brierTop4), num(s.brierTop4Baseline), Math.round(s.ms)]))]),
  ].join('\n\n')
}

const LIMITS = [
  'Los niveles de cada equipo (lo que hace y lo que deja hacer) se calculan con los partidos hasta ese día pero los escenarios usan esos niveles sobre los mismos partidos que los forman: los residuos son algo más estrechos de lo que serán; por eso el núcleo `σ_u` completa la dispersión.',
  'Que un objetivo «se alcance» depende del propio partido: la probabilidad condicional describe lo que pasa en esos partidos, no que forzar el objetivo durante el partido cambie el resultado (el estudio de octubre no encontró evidencia de eso).',
  'El calendario de la simulación son los partidos que de hecho se jugaron después del corte: es el calendario real de la temporada ya terminada, sin aplazamientos ni cambios de última hora.',
  'No se modelan ascensos, descensos ni playoffs, ni el desempate recursivo de la federación (el genérico: victorias, partidos entre los empatados, diferencia de la liga y sorteo).',
  'Las temporadas evaluadas son las que hay en la base local; si solo hay ligas masculinas completas, las femeninas y FBCYL no están evaluadas aquí.',
]

export function formatReport(results: CompetitionResult[], date: string): string {
  const intro = [
    `# Evaluación walk-forward de la previa y la simulación (${date})`,
    'Cada pronóstico se hace **solo con los partidos anteriores al que se juzga** (sin fugas: lo comprueba `walkForward.test.ts`). Se reproduce con `npm run study:forecast` (`frontend/src/forecast/study/backtest.study.ts`) sobre `python run_local_export.py`.',
    table(['Competición', 'Familia', 'Partidos'], results.map(r => [r.name, r.gender === 'F' ? 'femenina' : 'masculina', `${r.games} partidos`])),
  ]
  return [...intro, headlineSection(results), scenariosSection(results), leversSection(results), seasonSection(results), '## Límites', LIMITS.map(l => `- ${l}`).join('\n')].join('\n\n') + '\n'
}
