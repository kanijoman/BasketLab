import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import NoCollection from './NoCollection'

describe('NoCollection', () => {
  it('asks to pick a collection', () => {
    render(<NoCollection />)
    expect(screen.getByText('Selecciona una colección para continuar.')).toBeInTheDocument()
  })
})
