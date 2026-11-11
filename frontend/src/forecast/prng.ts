// The random numbers of the simulation of the league (#848): seeded, so that a page reloaded shows the same numbers and a test can know them.

/** FNV-1a over the UTF-16 units of a text, as an unsigned 32-bit number: the seed of a competition is the hash of its name. */
export function hashSeed(text: string): number {
  let h = 0x811c9dc5
  for (let i = 0; i < text.length; i++) {
    h ^= text.charCodeAt(i)
    h = Math.imul(h, 0x01000193)
  }
  return h >>> 0
}

/** mulberry32: a small 32-bit generator of uniform numbers in [0, 1). */
export function mulberry32(seed: number): () => number {
  let a = seed >>> 0
  return () => {
    a = (a + 0x6d2b79f5) >>> 0
    let t = a
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

/** Standard normal numbers from a uniform generator (Box-Muller, keeping the second number of each pair). */
export function normalSampler(uniform: () => number): () => number {
  let spare: number | null = null
  return () => {
    if (spare !== null) {
      const z = spare
      spare = null
      return z
    }
    const u = 1 - uniform()                  // (0, 1]: its logarithm is finite
    const v = uniform()
    const radius = Math.sqrt(-2 * Math.log(u))
    spare = radius * Math.sin(2 * Math.PI * v)
    return radius * Math.cos(2 * Math.PI * v)
  }
}
