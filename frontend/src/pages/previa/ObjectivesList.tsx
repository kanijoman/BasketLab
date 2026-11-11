/** The objectives of the match (issue #849): what to do with the target, how often it happens, how often we win when it does and how the season went. Conditional, never a promise. */
import { leverDetail, leverEvidence, leverTitle, pct } from '@/forecast/copy'
import type { Lever } from '@/forecast/levers'
import type { PreviewDetail } from '@/forecast/preview'
import Badge from '@/components/ui/Badge'
import Card from '@/components/ui/Card'

function Group({ title, levers, headline }: { title: string; levers: Lever[]; headline: number }) {
  if (!levers.length) return null
  return (
    <Card title={title} padding="md">
      <ul className="space-y-4">
        {levers.map(l => (
          <li key={`${l.side}-${l.factor ?? 'pace'}`} className="space-y-1">
            <p className="flex flex-wrap items-center gap-2 font-medium text-ink">
              {leverTitle(l)}
              <Badge tone="accent">{pct(l.pWin, 0)} de victorias</Badge>
            </p>
            <p className="text-sm text-ink-muted">{leverDetail(l, headline)}</p>
            <p className="text-sm text-ink-muted">{leverEvidence(l)}</p>
          </li>
        ))}
      </ul>
    </Card>
  )
}

export default function ObjectivesList({ detail, headline }: { detail: PreviewDetail; headline: number }) {
  const { attack, defence, pace } = detail.levers
  const none = !attack.length && !defence.length && !pace
  return (
    <section aria-label="Objetivos del partido" className="space-y-3">
      <h2 className="text-lg font-semibold text-ink">Objetivos del partido</h2>
      <p className="text-sm text-ink-muted">
        Lo que más separa los partidos que acabamos ganando de los que no, para este emparejamiento. Describe lo que pasa en esos partidos: no asegura que conseguirlo dé la victoria.
      </p>
      {none && <p className="text-sm text-ink-muted">Ningún objetivo separa lo bastante los partidos que se ganan de los que se pierden.</p>}
      <div className="grid gap-3 lg:grid-cols-2">
        <Group title="Ataque" levers={attack} headline={headline} />
        <Group title="Defensa" levers={defence} headline={headline} />
        {pace && <Group title="Ritmo" levers={[pace]} headline={headline} />}
      </div>
    </section>
  )
}
