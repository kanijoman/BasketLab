/** The matches a team has left, to choose the one to analyse (issue #849): one button each, with the round, the day, where it is played and the rival. */
import type { TeamFixture } from '@/forecast/fixtures'
import Badge from '@/components/ui/Badge'
import Button from '@/components/ui/Button'
import { cn } from '@/lib/utils'
import { courtText, whenText } from './format'

export default function TeamFixtures({ fixtures, selected, onSelect }: { fixtures: TeamFixture[]; selected: string | null; onSelect: (code: string) => void }) {
  return (
    <ul aria-label="Próximos partidos" className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
      {fixtures.map(f => (
        <li key={f.code}>
          <Button
            data-testid="fixture" variant="ghost" aria-pressed={f.code === selected} onClick={() => onSelect(f.code)}
            className={cn('w-full justify-start gap-2 text-left border', f.code === selected ? 'border-accent bg-accent/10' : 'border-line')}
          >
            <span className="flex min-w-0 flex-col items-start gap-0.5">
              <span className="text-xs text-ink-muted">Jornada {f.round} · {f.live ? 'En juego' : whenText(f.start)}</span>
              <span className="flex flex-wrap items-center gap-1.5">
                <Badge tone={f.court === 'own' ? 'accent' : 'outline'}>{courtText(f.court)}</Badge>
                <span className="truncate text-sm font-medium text-ink">{f.rivalName}</span>
              </span>
            </span>
          </Button>
        </li>
      ))}
    </ul>
  )
}
