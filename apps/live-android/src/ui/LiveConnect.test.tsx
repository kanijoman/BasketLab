import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import LiveConnect from './LiveConnect'
import type { FeedState } from '../feed/liveFeed'

const NOW = new Date('2026-10-17T18:30:00Z').getTime()
beforeEach(() => { vi.useFakeTimers(); vi.setSystemTime(NOW) })
afterEach(() => vi.useRealTimers())

function view(state: FeedState, over: Partial<Parameters<typeof LiveConnect>[0]> = {}) {
  const onStart = vi.fn()
  const onStop = vi.fn()
  render(<LiveConnect matchCode="2524475" state={state} running={false} onStart={onStart} onStop={onStop} {...over} />)
  return { onStart, onStop }
}

describe('LiveConnect', () => {
  it('offers to connect to the match of the package', () => {
    const { onStart } = view({ kind: 'idle' })
    expect(screen.getByText(/2524475/)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /conectar con feb/i }))
    expect(onStart).toHaveBeenCalledWith('2524475')
  })

  it('asks for the match code when the package does not carry one, and only accepts digits', () => {
    const { onStart } = view({ kind: 'idle' }, { matchCode: null })
    const connect = screen.getByRole('button', { name: /conectar con feb/i })
    expect(connect).toBeDisabled()
    fireEvent.change(screen.getByLabelText(/código del partido/i), { target: { value: 'abc' } })
    expect(connect).toBeDisabled()
    fireEvent.change(screen.getByLabelText(/código del partido/i), { target: { value: ' 2524470 ' } })
    fireEvent.click(connect)
    expect(onStart).toHaveBeenCalledWith('2524470')
  })

  it('shows what the connection is doing in plain words', () => {
    const { rerender } = render(<LiveConnect matchCode="1" state={{ kind: 'connecting' }} running onStart={vi.fn()} onStop={vi.fn()} />)
    expect(screen.getByText(/conectando con feb/i)).toBeTruthy()
    rerender(<LiveConnect matchCode="1" state={{ kind: 'waiting' }} running onStart={vi.fn()} onStop={vi.fn()} />)
    expect(screen.getByText(/esperando el inicio del partido/i)).toBeTruthy()
    rerender(<LiveConnect matchCode="1" state={{ kind: 'finished' }} running={false} onStart={vi.fn()} onStop={vi.fn()} />)
    expect(screen.getByText(/partido finalizado/i)).toBeTruthy()
  })

  it('live: says how long ago the last data arrived and keeps counting', () => {
    view({ kind: 'live', lastOkAt: NOW - 12_000 }, { running: true })
    expect(screen.getByText(/en directo.*hace 12 s/i)).toBeTruthy()
    act(() => { vi.advanceTimersByTime(3000) })
    expect(screen.getByText(/hace 15 s/i)).toBeTruthy()
  })

  it('a gap says FEB is not answering and that the last state is kept (real 404 of the middle of the match)', () => {
    view({ kind: 'gap', lastOkAt: NOW - 70_000, message: 'FEB no responde (BoxScore 404)' }, { running: true })
    expect(screen.getByText(/FEB no responde \(BoxScore 404\)/)).toBeTruthy()
    expect(screen.getByText(/se mantiene el último estado/i)).toBeTruthy()
    expect(screen.getByText(/último dato hace 1 min/i)).toBeTruthy()
  })

  it('while connected the button disconnects', () => {
    const { onStop } = view({ kind: 'live', lastOkAt: NOW }, { running: true })
    expect(screen.queryByRole('button', { name: /conectar con feb/i })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: /desconectar/i }))
    expect(onStop).toHaveBeenCalled()
  })
})
