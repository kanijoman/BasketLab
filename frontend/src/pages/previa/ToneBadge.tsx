/**
 * A quiet badge with the tone in a dot: the border and the muted text of the `outline` badge and a coloured dot. The tinted pills of the system (`ok`, `bad`, `warn`, `neutral`) do not reach the
 * contrast AA at 12 px in the light theme (axe, 11/11/2026), so the preview says its tones with a dot and leaves the text in the ink of the page.
 */
import type { ReactNode } from 'react'
import Badge from '@/components/ui/Badge'
import type { Tone } from '@/components/ui/tone'

const DOT: Record<Tone, string> = { neutral: 'bg-ink-faint', accent: 'bg-accent', secondary: 'bg-secondary', ok: 'bg-ok', warn: 'bg-warn', bad: 'bg-bad' }

export default function ToneBadge({ tone, children }: { tone: Tone; children: ReactNode }) {
  return (
    <Badge tone="outline" className="gap-1.5">
      <span aria-hidden="true" className={`h-2 w-2 shrink-0 rounded-full ${DOT[tone]}`} />
      {children}
    </Badge>
  )
}
