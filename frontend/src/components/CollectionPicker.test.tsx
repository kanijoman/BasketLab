import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { CollectionInfo } from '@/api/client'
import CollectionPicker from './CollectionPicker'

const c = (name: string, league: string, competition: string, season: string, group = ''): CollectionInfo =>
  ({ name, league, competition, season, group, game_count: 10 }) as CollectionInfo
const LIST = [c('A25', 'FEB', 'LF2', '2025', 'A'), c('B25', 'FEB', 'LF2', '2025', 'B'), c('F25', 'FBCYL', 'U16', '2025')]

describe('CollectionPicker (issue #761)', () => {
  it('shows the four levels, and hides the group when there is only one', () => {
    const { rerender } = render(<CollectionPicker list={LIST} value={{ ambito: 'FEB' }} onChange={() => {}} />)
    for (const name of ['Ámbito', 'Temporada', 'Competición', 'Grupo']) expect(screen.getByRole('combobox', { name })).toBeInTheDocument()
    rerender(<CollectionPicker list={LIST} value={{ ambito: 'FBCYL' }} onChange={() => {}} />)
    expect(screen.queryByRole('combobox', { name: 'Grupo' })).toBeNull()
  })

  it('reports the resolved selection when a level changes', () => {
    const onChange = vi.fn()
    render(<CollectionPicker list={LIST} value={{ ambito: 'FEB' }} onChange={onChange} />)
    fireEvent.change(screen.getByRole('combobox', { name: 'Ámbito' }), { target: { value: 'FBCYL' } })
    expect(onChange).toHaveBeenCalledWith({ ambito: 'FBCYL', season: '2025', competition: 'U16', group: '' }, expect.objectContaining({ name: 'F25' }))
  })

  it('compact mode hides every level with a single option', () => {
    render(<CollectionPicker list={[LIST[0], LIST[1]]} value={{}} onChange={() => {}} compact />)
    expect(screen.getAllByRole('combobox').map(s => s.getAttribute('aria-label'))).toEqual(['Grupo'])
  })
})
