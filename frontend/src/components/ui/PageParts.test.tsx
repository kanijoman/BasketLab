import { render, screen } from '@testing-library/react'
import { Users } from 'lucide-react'
import { describe, expect, it } from 'vitest'
import Badge from './Badge'
import Card from './Card'
import EmptyState from './EmptyState'
import PageHeader from './PageHeader'
import Skeleton from './Skeleton'
import Spinner from './Spinner'
import StatCard from './StatCard'

// Issue #190: the parts every page repeats (21 titles, 10 texts of «no data», 31 spinners and 16 skeletons, each its own way).
describe('page parts (issue #190)', () => {
  it('PageHeader: one title per page, its subtitle and its actions', () => {
    render(<PageHeader title="Estadísticas de Equipo" subtitle="LF2 2025/26" actions={<button>Exportar</button>} />)
    expect(screen.getByRole('heading', { level: 1, name: 'Estadísticas de Equipo' })).toBeInTheDocument()
    expect(screen.getByText('LF2 2025/26')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Exportar' })).toBeInTheDocument()
  })

  it('Card: a panel with an optional title and actions', () => {
    const { container } = render(<Card title="Estadísticas por zona" actions={<button>Ver</button>}>contenido</Card>)
    expect(container.firstChild).toHaveClass('card')
    expect(screen.getByRole('heading', { level: 2, name: 'Estadísticas por zona' })).toBeInTheDocument()
    expect(screen.getByText('contenido')).toBeInTheDocument()
  })

  it('EmptyState: says what is missing and what to do', () => {
    render(<EmptyState icon={Users} title="Sin combinaciones" description="Selecciona un equipo y pulsa «Analizar»." action={<button>Analizar</button>} />)
    expect(screen.getByText('Sin combinaciones')).toBeInTheDocument()
    expect(screen.getByText('Selecciona un equipo y pulsa «Analizar».')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Analizar' })).toBeInTheDocument()
  })

  it('Spinner says it is loading; Skeleton is hidden from the screen reader', () => {
    render(<><Spinner label="Generando DOCX" /><Skeleton lines={3} /></>)
    expect(screen.getByRole('status', { name: 'Generando DOCX' })).toBeInTheDocument()
    const skeleton = document.querySelector('[aria-hidden="true"].animate-pulse')
    expect(skeleton?.children).toHaveLength(3)
  })

  // Badge and StatCard speak the same tones as the rest of the system (accent, secondary, ok, warn, bad)
  it.each([['accent', 'text-accent-text'], ['secondary', 'text-secondary-text'], ['ok', 'text-ok'], ['warn', 'text-warn'], ['bad', 'text-bad']] as const)(
    'Badge tone %s', (tone, cls) => {
      render(<Badge tone={tone}>FEB</Badge>)
      expect(screen.getByText('FEB')).toHaveClass(cls)
    })

  it('StatCard tone ok', () => {
    const { container } = render(<StatCard label="OER" value="107" tone="ok" />)
    expect((container.firstChild as HTMLElement).className).toMatch(/border-ok/)
  })
})
