import { describe, expect, it } from 'vitest'
import { layoutProblems, type Box } from './layoutCheck'

const box = (id: string, left: number, top: number, right: number, bottom: number, over: Partial<Box> = {}): Box =>
  ({ id, left, top, right, bottom, text: id, parent: null, ...over })

describe('layoutProblems: what the e2e checks on every screen (issue #508)', () => {
  it('a clean layout has no problems', () => {
    const boxes = [box('title', 10, 10, 200, 30), box('button', 10, 40, 120, 84)]
    expect(layoutProblems(boxes, 412)).toEqual([])
  })

  it('an element that goes out of the screen to the right is reported', () => {
    expect(layoutProblems([box('wide', 10, 10, 500, 30)], 412)).toEqual([expect.stringContaining('wide')])
  })

  it('two texts or a button over a text are reported (the «Informe PDF» button over the name of the teams)', () => {
    const problems = layoutProblems([box('teams', 10, 10, 300, 30), box('Informe PDF', 200, 15, 330, 59, { button: true })], 412)
    expect(problems).toHaveLength(1)
    expect(problems[0]).toContain('Informe PDF')
    expect(problems[0]).toContain('teams')
  })

  it('an element inside another one is not an overlap (a label in its card, a button in its row)', () => {
    const boxes = [box('card', 0, 0, 300, 100, { text: '' }), box('label', 10, 10, 100, 30, { parent: 'card' })]
    expect(layoutProblems(boxes, 412)).toEqual([])
  })

  it('touching edges and tiny overlaps (borders, rounding) do not count', () => {
    expect(layoutProblems([box('a', 0, 0, 100, 30), box('b', 100, 0, 200, 30), box('c', 0, 30, 100, 60)], 412)).toEqual([])
    expect(layoutProblems([box('a', 0, 0, 100, 30), box('b', 99, 29, 200, 60)], 412)).toEqual([])
  })

  it('boxes without size (hidden) are ignored', () => {
    expect(layoutProblems([box('hidden', 600, 0, 600, 0), box('x', 0, 0, 10, 10)], 412)).toEqual([])
  })
})
