// @vitest-environment node
/** The second entry of the web (#877): BasketLab Talent is built from the same project with ``vite build --mode market`` (the Vercel project ``basketlab-talent``, root ``frontend``).
 *  The Analytics build must stay as it was; the Talent one must leave an ``index.html`` in ``dist`` so the rewrite of vercel.json and the host's default document keep working. */
import { mkdtempSync, readdirSync, readFileSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { pathToFileURL } from 'node:url'
import { describe, expect, it } from 'vitest'

const ROOT = join(__dirname, '..', '..')
interface Plugin { name?: string; writeBundle?: (this: object, options: { dir?: string }, bundle: object) => void }
interface Built { build: { rollupOptions?: { input?: string } }; plugins: Array<Plugin | Plugin[]> }
type Config = (env: { mode: string; command: string }) => Built

/** The config is read with a dynamic import by path: it belongs to the node project of tsconfig, not to the one of src/. */
const loadBuild = async (mode: string): Promise<Built> => {
  const { default: config } = (await import(/* @vite-ignore */ pathToFileURL(join(ROOT, 'vite.config.ts')).href)) as { default: Config }
  return config({ mode, command: 'build' })
}

describe('market.html', () => {
  const html = readFileSync(join(ROOT, 'market.html'), 'utf8')
  it('is the page of BasketLab Talent and loads the entry of the market, not the one of Analytics', () => {
    expect(html).toContain('<title>BasketLab Talent')
    expect(html).toContain('src="/src/market/main.tsx"')
    expect(html).not.toContain('/src/main.tsx')
    expect(html).toContain('lang="es"')
  })
  it('sets the theme before the first paint with the same key as the web (one preference for the whole suite)', () => {
    expect(html).toContain("localStorage.getItem('basketlab-web-theme')")
  })
})

describe('vite build', () => {
  it('builds index.html for Analytics and market.html only for --mode market', async () => {
    expect((await loadBuild('production')).build.rollupOptions?.input).toBeUndefined()
    expect(String((await loadBuild('market')).build.rollupOptions?.input)).toMatch(/market\.html$/)
  })

  it('leaves index.html (and no market.html) in dist after writing the Talent bundle, regression: the hook of the first version ran before Vite emitted the page', async () => {
    const plugin = async (mode: string) => (await loadBuild(mode)).plugins.flat().find(p => p.name === 'talent-index')
    expect(await plugin('production')).toBeUndefined()
    const dir = mkdtempSync(join(tmpdir(), 'talent-'))
    writeFileSync(join(dir, 'market.html'), '<html>talent</html>')
    writeFileSync(join(dir, 'other.js'), '//')
    ;(await plugin('market'))!.writeBundle!.call({}, { dir }, {})
    expect(readdirSync(dir).sort()).toEqual(['index.html', 'other.js'])
    expect(readFileSync(join(dir, 'index.html'), 'utf8')).toBe('<html>talent</html>')
  })

  it('does nothing when the bundle has no market.html', async () => {
    const dir = mkdtempSync(join(tmpdir(), 'talent-'))
    writeFileSync(join(dir, 'index.html'), '<html>keep</html>')
    ;(await (await loadBuild('market')).plugins.flat().find(p => p.name === 'talent-index'))!.writeBundle!.call({}, { dir }, {})
    expect(readFileSync(join(dir, 'index.html'), 'utf8')).toBe('<html>keep</html>')
  })
})
