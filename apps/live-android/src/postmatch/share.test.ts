import { describe, expect, it, vi } from 'vitest'
import { fileNameFor, sharePdf, type ShareDeps } from './share'

const BYTES = new Uint8Array([37, 80, 68, 70, 45])

function deps(native: boolean): ShareDeps & { calls: string[] } {
  const calls: string[] = []
  return {
    calls, native,
    writeFile: vi.fn(async (name: string, base64: string) => { calls.push(`write:${name}:${base64}`); return `file:///cache/${name}` }),
    share: vi.fn(async (title: string, uri: string) => { calls.push(`share:${title}:${uri}`) }),
    download: vi.fn((name: string, bytes: Uint8Array) => { calls.push(`download:${name}:${bytes.length}`) }),
  }
}

describe('sharePdf (issue #409)', () => {
  it('on the tablet it writes the file to the cache and opens the share sheet with it', async () => {
    const d = deps(true)
    await sharePdf(BYTES, 'informe.pdf', 'Informe del partido', d)
    expect(d.calls).toEqual(['write:informe.pdf:JVBERi0=', 'share:Informe del partido:file:///cache/informe.pdf'])
    expect(d.download).not.toHaveBeenCalled()
  })

  it('in a browser it downloads the file', async () => {
    const d = deps(false)
    await sharePdf(BYTES, 'informe.pdf', 'Informe del partido', d)
    expect(d.calls).toEqual(['download:informe.pdf:5'])
    expect(d.share).not.toHaveBeenCalled()
  })

  it('names the file after the match, without characters a file name cannot have', () => {
    expect(fileNameFor('MIPELLETYMAS B.F. LEON', 'RECOLETAS ZAMORA', '2524470')).toBe('informe-mipelletymas-b-f-leon-recoletas-zamora-2524470.pdf')
    expect(fileNameFor('Ñandú / A', 'B: C', '1')).toBe('informe-nandu-a-b-c-1.pdf')
  })
})
