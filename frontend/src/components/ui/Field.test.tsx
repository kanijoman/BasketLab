import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { Field, Input, Select } from './Field'

// Issue #190: one input and one select (there were 38 selects and 28 inputs with local styles: selectCls, inputCls…).
describe('Field, Input and Select (issue #190)', () => {
  it('a field names its control, and says its hint and its error', () => {
    render(<Field label="Mín. minutos" hint="Por partido" error="Debe ser positivo"><Input type="number" defaultValue={-1} /></Field>)
    const input = screen.getByLabelText('Mín. minutos')
    expect(input).toHaveClass('input')
    expect(input).toHaveAttribute('aria-invalid', 'true')
    expect(input).toHaveAccessibleDescription('Por partido Debe ser positivo')
    expect(screen.getByText('Debe ser positivo')).toHaveClass('text-bad')
  })

  it('a select is the native one, styled, with its options and a chevron that does not take the clicks', () => {
    const change = vi.fn()
    const { container } = render(
      <Field label="Temporada">
        <Select value="2025" onChange={e => change(e.target.value)} options={[{ value: '2025', label: '2025/26' }, { value: '2024', label: '2024/25' }]} />
      </Field>,
    )
    const select = screen.getByLabelText('Temporada')
    expect(select.tagName).toBe('SELECT')
    expect(select).toHaveClass('select')
    expect(screen.getAllByRole('option').map(o => o.textContent)).toEqual(['2025/26', '2024/25'])
    fireEvent.change(select, { target: { value: '2024' } })
    expect(change).toHaveBeenCalledWith('2024')
    expect(container.querySelector('svg')).toHaveClass('pointer-events-none')
  })

  it('a select also takes its options as children', () => {
    render(<Select aria-label="Equipo"><option value="">— Todos —</option><option value="1">León</option></Select>)
    expect(screen.getByRole('combobox', { name: 'Equipo' })).toHaveDisplayValue('— Todos —')
  })
})
