import { describe, expect, it } from 'vitest'
import { hashSeed, mulberry32, normalSampler } from './prng'

// The random numbers of the simulation of the league: seeded, so that a page reloaded shows the same numbers and a test can know them.
describe('hashSeed', () => {
  it('is FNV-1a over the characters (the known value of "a"), the same for the same text and different for another', () => {
    expect(hashSeed('a')).toBe(0xe40c292c)
    expect(hashSeed('LF_CHALLENGE_2026_2027_Liga_Regular_Único')).toBe(hashSeed('LF_CHALLENGE_2026_2027_Liga_Regular_Único'))
    expect(hashSeed('A')).not.toBe(hashSeed('B'))
    expect(hashSeed('')).toBe(0x811c9dc5)
  })
})

describe('mulberry32', () => {
  it('gives the same sequence for the same seed and another for another one', () => {
    const [a, b, c] = [mulberry32(7), mulberry32(7), mulberry32(8)]
    const seq = (r: () => number) => Array.from({ length: 5 }, r)
    expect(seq(a)).toEqual(seq(b))
    expect(seq(mulberry32(7))).not.toEqual(seq(c))
  })

  it('is uniform in [0, 1): the mean and the quartiles of 100,000 numbers', () => {
    const r = mulberry32(2026)
    const xs = Array.from({ length: 100000 }, r).sort((x, y) => x - y)
    expect(xs[0]).toBeGreaterThanOrEqual(0)
    expect(xs[xs.length - 1]).toBeLessThan(1)
    expect(xs.reduce((s, x) => s + x, 0) / xs.length).toBeCloseTo(0.5, 2)
    expect(xs[25000]).toBeCloseTo(0.25, 2)
    expect(xs[75000]).toBeCloseTo(0.75, 2)
  })
})

describe('normalSampler', () => {
  it('has mean 0, deviation 1 and the tails of a normal over 200,000 draws', () => {
    const z = normalSampler(mulberry32(11))
    const xs = Array.from({ length: 200000 }, z)
    const mean = xs.reduce((s, x) => s + x, 0) / xs.length
    const sd = Math.sqrt(xs.reduce((s, x) => s + (x - mean) ** 2, 0) / xs.length)
    expect(mean).toBeCloseTo(0, 1)
    expect(sd).toBeCloseTo(1, 1)
    expect(xs.filter(x => x > 1.96).length / xs.length).toBeCloseTo(0.025, 2)
    expect(xs.every(Number.isFinite)).toBe(true)
  })

  it('is reproducible from the seed of the generator', () => {
    const seq = (seed: number) => { const z = normalSampler(mulberry32(seed)); return Array.from({ length: 6 }, z) }
    expect(seq(5)).toEqual(seq(5))
  })
})
