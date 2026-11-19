import { describe, it, expect } from 'vitest'
import { EXPORT_HIDE_ATTR, EXPORT_ONLY_ATTR, prepareCloneForExport } from './exportDom'

describe('prepareCloneForExport', () => {
  function makeDoc() {
    document.body.innerHTML = `
      <span id="photo" ${EXPORT_HIDE_ATTR}><img src="https://cdn.example/p.png" /></span>
      <span id="initials" ${EXPORT_ONLY_ATTR} style="display:none">AB</span>
      <span id="other">x</span>`
    return document
  }

  it('hides cross-origin photos and reveals the initials chip in the clone', () => {
    const doc = makeDoc()
    prepareCloneForExport(doc)
    expect(doc.getElementById('photo')!.style.display).toBe('none')
    expect(doc.getElementById('initials')!.style.display).toBe('inline-flex')
  })

  it('leaves unmarked elements untouched', () => {
    const doc = makeDoc()
    prepareCloneForExport(doc)
    expect(doc.getElementById('other')!.style.display).toBe('')
  })

  it('shows a clamped text whole in the clone: html2canvas cuts a line-clamp box at the height of the cell (regression: long team names in exported tables)', () => {
    document.body.innerHTML = '<table><tr><td><span id="name" class="line-clamp-2 break-words" style="display:-webkit-box;overflow:hidden;max-height:2.5em">Club Deportivo Baloncesto Muy Largo de la Ciudad Autónoma</span></td></tr></table><span id="plain" style="overflow:hidden">x</span>'
    prepareCloneForExport(document)
    const name = document.getElementById('name')!
    expect([name.style.display, name.style.overflow, name.style.maxHeight]).toEqual(['block', 'visible', 'none'])
    expect(document.getElementById('plain')!.style.overflow).toBe('hidden')               // only the clamped ones change
  })
})
