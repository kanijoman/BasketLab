import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import Select from './Select'

const OPTIONS = [{ value: '', label: 'Todas' }, { value: 'a', label: 'Competición A con un nombre larguísimo que no cabe' }, { value: 'b', label: 'Competición B' }]

function show(value = '', onChange = vi.fn()) {
  render(<Select label="Competición" value={value} options={OPTIONS} onChange={onChange} />)
  return onChange
}
const box = () => screen.getByRole('combobox', { name: 'Competición' })

afterEach(cleanup)

describe('Select (issue #571: the system list of radio buttons is replaced by one that fits the app)', () => {
  it('shows the chosen option and nothing else until it is opened', () => {
    show('b')
    expect(box().textContent).toContain('Competición B')
    expect(box().getAttribute('aria-expanded')).toBe('false')
    expect(screen.queryByRole('listbox')).toBeNull()
  })

  it('opens a list with every option, the chosen one marked, and choosing one reports it and closes', () => {
    const onChange = show('b')
    fireEvent.click(box())
    const options = screen.getAllByRole('option')
    expect(options.map(o => o.textContent)).toEqual(OPTIONS.map(o => o.label))
    expect(options.map(o => o.getAttribute('aria-selected'))).toEqual(['false', 'false', 'true'])
    fireEvent.click(options[1])
    expect(onChange).toHaveBeenCalledWith('a')
    expect(screen.queryByRole('listbox')).toBeNull()
  })

  it('closes with Escape and with a touch outside, without choosing', () => {
    const onChange = show()
    fireEvent.click(box())
    fireEvent.keyDown(box(), { key: 'Escape' })
    expect(screen.queryByRole('listbox')).toBeNull()
    fireEvent.click(box())
    fireEvent.mouseDown(document.body)
    expect(screen.queryByRole('listbox')).toBeNull()
    expect(onChange).not.toHaveBeenCalled()
  })

  it('works with the keyboard: arrows move, Enter chooses', () => {
    const onChange = show('')
    fireEvent.keyDown(box(), { key: 'ArrowDown' })              // opens on the chosen option
    fireEvent.keyDown(box(), { key: 'ArrowDown' })
    fireEvent.keyDown(box(), { key: 'Enter' })
    expect(onChange).toHaveBeenCalledWith('a')
    expect(screen.queryByRole('listbox')).toBeNull()
  })

  it('the options carry their value, for the tests of the screens that use it', () => {
    show()
    fireEvent.click(box())
    expect(screen.getByRole('option', { name: 'Competición B' }).getAttribute('data-value')).toBe('b')
  })
})
