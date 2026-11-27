import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import DiffBadge, { formatDiff } from './DiffBadge'
import { TONE_PILL } from './tone'

describe('formatDiff (issue #608)', () => {
  it('says the real difference with its sign and the decimals of the figure', () => {
    expect(formatDiff(78.4, 76.3)).toBe('+2.1')
    expect(formatDiff(70, 72.55, 2)).toBe('-2.55')
    expect(formatDiff(10, 10)).toBe('0.0')
  })

  it('does not say -0.0: a difference that rounds to nothing is a zero without a sign', () => {
    expect(formatDiff(10.01, 10.04)).toBe('0.0')
    expect(formatDiff(10.04, 10.01)).toBe('0.0')
  })

  it('has nothing to say when a figure is missing', () => {
    expect(formatDiff(null, 5)).toBeNull()
    expect(formatDiff(5, undefined)).toBeNull()
    expect(formatDiff(Number.NaN, 5)).toBeNull()
  })

  it('a zero is a figure, not a missing one', () => {
    expect(formatDiff(0, 3)).toBe('-3.0')
    expect(formatDiff(3, 0)).toBe('+3.0')
  })
})

describe('DiffBadge (issue #608)', () => {
  it('shows the difference and no arrow of trend', () => {
    render(<DiffBadge recent={78.4} season={76.3} />)
    expect(screen.getByText('+2.1')).toBeInTheDocument()
    expect(document.body.textContent).not.toMatch(/[⇈↑≈↓⇊]/)
  })

  it('is good when it rises and bad when it falls', () => {
    const { rerender } = render(<DiffBadge recent={80} season={70} />)
    expect(screen.getByText('+10.0').className).toMatch(/text-ok/)
    rerender(<DiffBadge recent={60} season={70} />)
    expect(screen.getByText('-10.0').className).toMatch(/text-bad/)
  })

  it('is the other way round where less is better (turnovers, defensive rating)', () => {
    const { rerender } = render(<DiffBadge recent={10} season={14} reverse />)
    expect(screen.getByText('-4.0').className).toMatch(/text-ok/)
    rerender(<DiffBadge recent={16} season={14} reverse />)
    expect(screen.getByText('+2.0').className).toMatch(/text-bad/)
  })

  it('a difference that is nothing is neither good nor bad', () => {
    render(<DiffBadge recent={5} season={5} />)
    expect(screen.getByText('0.0').className).toMatch(/text-ink-muted/)
  })

  it('says both figures in the tooltip and renders nothing without them', () => {
    const { container, rerender } = render(<DiffBadge recent={78.4} season={76.3} />)
    expect(screen.getByText('+2.1').getAttribute('title')).toBe('78.4 frente a 76.3')
    rerender(<DiffBadge recent={null} season={76.3} />)
    expect(container).toBeEmptyDOMElement()
  })

  // A difference sits in cells painted with the colour of their quartile: green or red text straight on them does not reach WCAG AA (axe on /comparativas, #1199). The badge is the pill of
  // its tone (`TONE_PILL`, measured at AA over every surface by designTokens.test.ts, #856) over an opaque surface of its own, so it reads whatever colour the cell has.
  it.each([
    [80, 70, false, 'ok'],
    [60, 70, false, 'bad'],
    [16, 14, true, 'bad'],
    [5, 5, false, 'neutral'],
  ] as const)('recent %s against %s (reverse %s) is the %s pill over an opaque surface', (recent, season, reverse, tone) => {
    render(<DiffBadge recent={recent} season={season} reverse={reverse} />)
    const pill = screen.getByText(formatDiff(recent, season)!)
    for (const cls of TONE_PILL[tone].split(' ')) expect(pill.className.split(' ')).toContain(cls)
    expect(pill.parentElement!.className).toMatch(/(^|\s)bg-surface(\s|$)/)
  })

  it('uses the decimals it is given', () => {
    render(<DiffBadge recent={1.234} season={1} decimals={2} />)
    expect(screen.getByText('+0.23')).toBeInTheDocument()
  })
})
