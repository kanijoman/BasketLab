/**
 * FilterBar tests — regression coverage for the date preset bug.
 *
 * Bug: pressing a quick-date preset (7d / 15d / 30d / 60d) called setParam
 * twice with separate URLSearchParams snapshots. The second call (clearing
 * 'to') overwrote the first (setting 'from'), leaving the URL unchanged.
 *
 * Fix: both mutations are now combined in a single setParams() call.
 */
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, useSearchParams } from 'react-router-dom'
import FilterBar from './FilterBar'

// Helper component that exposes current search params to the DOM
function ParamsDisplay() {
  const [params] = useSearchParams()
  return <pre data-testid="params">{params.toString()}</pre>
}

function renderFilterBar() {
  return render(
    <MemoryRouter>
      <FilterBar showDate />
      <ParamsDisplay />
    </MemoryRouter>,
  )
}

function getParams(container: HTMLElement): URLSearchParams {
  const raw = container.querySelector('[data-testid="params"]')?.textContent ?? ''
  return new URLSearchParams(raw)
}

/** ISO date string for N days ago */
function daysAgo(n: number): string {
  const d = new Date()
  d.setDate(d.getDate() - n)
  return d.toISOString().slice(0, 10)
}

// ---------------------------------------------------------------------------

describe('FilterBar — quick date presets', () => {
  it('pressing 7d sets from_date and does NOT set to_date', async () => {
    const { container } = renderFilterBar()
    await userEvent.click(screen.getByText('7d'))
    const params = getParams(container)
    expect(params.get('from')).toBe(daysAgo(7))
    expect(params.get('to')).toBeNull()
  })

  it('pressing 30d sets from_date to correct date', async () => {
    const { container } = renderFilterBar()
    await userEvent.click(screen.getByText('30d'))
    const params = getParams(container)
    expect(params.get('from')).toBe(daysAgo(30))
    expect(params.get('to')).toBeNull()
  })

  it('pressing 60d sets from_date to correct date', async () => {
    const { container } = renderFilterBar()
    await userEvent.click(screen.getByText('60d'))
    const params = getParams(container)
    expect(params.get('from')).toBe(daysAgo(60))
  })
})

describe('FilterBar — regression: preset preserves existing filters', () => {
  it('selecting venue then pressing 7d keeps both params', async () => {
    const { container } = renderFilterBar()

    // Set venue first
    await userEvent.click(screen.getByText('Local'))
    expect(getParams(container).get('venue')).toBe('home')

    // Then apply date preset — venue must survive
    await userEvent.click(screen.getByText('7d'))
    const params = getParams(container)
    expect(params.get('venue')).toBe('home')
    expect(params.get('from')).toBe(daysAgo(7))
    expect(params.get('to')).toBeNull()
  })

  it('selecting result + venue then preset keeps all three', async () => {
    const { container } = renderFilterBar()

    await userEvent.click(screen.getByText('Local'))
    await userEvent.click(screen.getByText('Victoria'))
    await userEvent.click(screen.getByText('15d'))

    const params = getParams(container)
    expect(params.get('venue')).toBe('home')
    expect(params.get('result')).toBe('won')
    expect(params.get('from')).toBe(daysAgo(15))
  })
})

describe('FilterBar — clear button', () => {
  it('removes all params when Borrar is clicked', async () => {
    const { container } = renderFilterBar()

    await userEvent.click(screen.getByText('Local'))
    await userEvent.click(screen.getByText('7d'))
    expect(getParams(container).toString()).not.toBe('')

    await userEvent.click(screen.getByText('Borrar'))
    expect(getParams(container).toString()).toBe('')
  })
})
