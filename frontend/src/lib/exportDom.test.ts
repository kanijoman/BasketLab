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
})
