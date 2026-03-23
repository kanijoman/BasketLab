import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'
import IQRBar from './IQRBar'

describe('IQRBar - basic rendering', () => {
  it('renders without crashing for valid data', () => {
    const { container } = render(
      <IQRBar value={75} min={50} q1={65} q3={85} max={100} />,
    )
    expect(container.firstChild).not.toBeNull()
  })

  it('returns null when range is zero', () => {
    const { container } = render(
      <IQRBar value={50} min={50} q1={50} q3={50} max={50} />,
    )
    expect(container.firstChild).toBeNull()
  })

  it('renders with correct title containing range and IQR', () => {
    const { container } = render(
      <IQRBar value={75} min={50} q1={60} q3={90} max={100} />,
    )
    const bar = container.firstChild as HTMLElement
    expect(bar?.title).toContain('50')
    expect(bar?.title).toContain('100')
    expect(bar?.title).toContain('60')
    expect(bar?.title).toContain('90')
  })
})

describe('IQRBar - value clamping', () => {
  it('does not crash when value is below min', () => {
    const { container } = render(
      <IQRBar value={10} min={50} q1={60} q3={90} max={100} />,
    )
    expect(container.firstChild).not.toBeNull()
  })

  it('does not crash when value is above max', () => {
    const { container } = render(
      <IQRBar value={999} min={50} q1={60} q3={90} max={100} />,
    )
    expect(container.firstChild).not.toBeNull()
  })
})

describe('IQRBar - className forwarding', () => {
  it('applies custom className to root span', () => {
    const { container } = render(
      <IQRBar value={75} min={0} q1={25} q3={75} max={100} className="test-class" />,
    )
    expect(container.firstChild).toHaveClass('test-class')
  })
})

describe('IQRBar - reverse prop', () => {
  it('renders without errors in reverse mode', () => {
    const { container } = render(
      <IQRBar value={30} min={10} q1={20} q3={40} max={60} reverse />,
    )
    expect(container.firstChild).not.toBeNull()
  })

  it('uses amber IQR colour in reverse mode', () => {
    const { container } = render(
      <IQRBar value={30} min={10} q1={20} q3={40} max={60} reverse />,
    )
    // In reverse mode the class is bg-slate-500/40
    const iqrBand = container.querySelector('.bg-slate-500\\/40')
    expect(iqrBand).not.toBeNull()
  })

  it('uses brand IQR colour in normal mode', () => {
    const { container } = render(
      <IQRBar value={70} min={10} q1={40} q3={80} max={100} />,
    )
    const iqrBand = container.querySelector('.bg-brand-500\\/40')
    expect(iqrBand).not.toBeNull()
  })
})
