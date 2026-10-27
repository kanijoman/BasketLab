/** The Boxscore tab (issue #593): the box score of one team at a time, normal or advanced, the player's name fixed while the figures scroll sideways, the players on court
 *  marked, each figure tinted by how far it is from the average of its player, and the last action that changed a box score highlighted like the score is. */
import { useRef, useState, type CSSProperties } from 'react'
import type { BoxscoreEntry, Snapshot, TeamRef } from '../../engine/types'
import { orderTeams } from '../teams'
import { ADVANCED_COLUMNS, NORMAL_COLUMNS, cellText, deviationOf, highlightFor, playerRowLabel, playerRows, teamRows, type Column, type Mode, type Row } from './model'

interface Props {
  snapshot?: Snapshot | null
  entries?: Record<string, BoxscoreEntry>
  own: TeamRef
  rival: TeamRef
  /** Local team id from the engine. */
  homeId?: string | null
}

/** Beyond this the figure is far from his average: it also gets an arrow, so the colour is not the only sign. */
const FAR = 0.75

function Option({ checked, onClick, label, news }: { checked: boolean; onClick: () => void; label: string; news?: boolean }) {
  return (
    <button role="radio" aria-checked={checked} className={checked ? 'segment selected' : 'segment'} onClick={onClick}>
      <span className="segment-text">{label}</span>
      {news && <span className="bx-news" aria-hidden="false"><span className="sr-only">novedad</span></span>}
    </button>
  )
}

function Cell({ column, row, hit, seq }: { column: Column; row: Row; hit: boolean; seq: number | null }) {
  const dev = deviationOf(column, row)
  const side = dev === null || dev === 0 ? null : dev > 0 ? 'up' : 'down'
  const words = side === 'up' ? 'por encima de su media' : 'por debajo de su media'
  const style = side ? ({ '--dev-abs': Number(Math.abs(dev as number).toFixed(2)) } as CSSProperties) : undefined
  return (
    <td key={hit ? `${column.id}-${seq}` : column.id} data-col={column.id} data-dev={side ?? undefined} style={style} title={side ? `${column.title}: ${words}` : column.title}
      className={hit ? 'bump' : undefined}>
      {cellText(column, row)}
      {side && Math.abs(dev as number) >= FAR && <span className="bx-arrow" aria-hidden="true">{side === 'up' ? '▲' : '▼'}</span>}
      {side && <span className="sr-only"> {words}</span>}
    </td>
  )
}

export default function BoxscoreTab({ snapshot, entries, own, rival, homeId }: Props) {
  const { home, away } = orderTeams(own, rival, homeId ?? snapshot?.home_id)
  const [teamId, setTeamId] = useState(own.id)
  const [mode, setMode] = useState<Mode>('normal')
  const [viewed, setViewed] = useState<Record<string, number>>({})
  const last = snapshot?.last_stat ?? null
  const first = useRef(last?.seq)          // what was already there when the tab opened is not news
  const fresh = last !== null && last.seq !== first.current
  const shown = teamId === home.id ? home : away
  if (!snapshot || !snapshot.players || Object.keys(snapshot.players).length === 0) {
    return <section className="bx"><p className="detail">Sin partido todavía: el boxscore aparece en cuanto empieza.</p></section>
  }
  const rows = playerRows(snapshot, shown.id, entries)
  const { team, totals } = teamRows(snapshot, shown.id, rows)
  const columns = mode === 'normal' ? NORMAL_COLUMNS : ADVANCED_COLUMNS
  const news = (id: string) => fresh && last.team_id === id && id !== shown.id && last.seq !== viewed[id]
  const choose = (id: string) => { setTeamId(id); setViewed(v => ({ ...v, [id]: last?.seq ?? 0 })) }
  const body = (row: Row) => {
    const light = fresh && row.kind === 'player' ? highlightFor(last, row.id) : null
    return (
      <tr key={row.id} className={[row.kind !== 'player' ? `bx-${row.kind}` : '', light ? 'bx-hit' : ''].filter(Boolean).join(' ') || undefined}>
        <th scope="row" className="bx-name" title={playerRowLabel(row)}>
          {row.onCourt && <span className="bx-on" role="img" aria-label="En pista">●</span>}
          <span className="bx-player">{playerRowLabel(row)}</span>
        </th>
        {columns.map(column => <Cell key={column.id} column={column} row={row} hit={!!light?.cell(column)} seq={fresh ? last.seq : null} />)}
      </tr>
    )
  }
  return (
    <section className="bx" aria-label="Boxscore">
      <div className="bx-controls">
        <div className="segmented" role="radiogroup" aria-label="Equipo">
          {[home, away].map(t => <Option key={t.id} checked={t.id === shown.id} label={t.name} news={news(t.id)} onClick={() => choose(t.id)} />)}
        </div>
        <div className="segmented" role="radiogroup" aria-label="Estadística">
          <Option checked={mode === 'normal'} label="Normal" onClick={() => setMode('normal')} />
          <Option checked={mode === 'advanced'} label="Avanzada" onClick={() => setMode('advanced')} />
        </div>
      </div>
      <div className="bx-scroll">
        <table className="bx-table">
          <caption className="sr-only">Boxscore de {shown.name}</caption>
          <thead>
            <tr>
              <th scope="col" className="bx-name">Jugador</th>
              {columns.map(c => <th key={c.id} scope="col" title={c.title}>{c.label}</th>)}
            </tr>
          </thead>
          <tbody>
            {rows.map(body)}
            {mode === 'normal' && body(team)}
            {body(totals)}
          </tbody>
        </table>
      </div>
      <p className="detail bx-legend">Verde: mejor que su media esperada por los minutos jugados; rojo: peor (en pérdidas y faltas, más es peor). Sin color: sin media con la que comparar.</p>
    </section>
  )
}
