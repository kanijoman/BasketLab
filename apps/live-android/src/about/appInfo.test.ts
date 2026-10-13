import { describe, expect, it } from 'vitest'
import { buildInfo, getInstalledVersion } from './appInfo'

describe('installed version (issues #226 and #227)', () => {
  it('on the device it is what the APK says: versionName and versionCode', async () => {
    const v = await getInstalledVersion({
      native: () => true,
      getInfo: async () => ({ name: 'BasketLab Live', id: 'es.basketlab.live', build: '52', version: '0.3.0' }),
      env: { VITE_BUILT_AT: '2026-10-16T07:30:00Z' },
    })
    expect(v).toEqual({ name: '0.3.0', build: 52, builtAt: '2026-10-16T07:30:00Z', native: true })
  })

  it('in a browser it is the version the workflow compiled into the web build', async () => {
    const v = await getInstalledVersion({
      native: () => false,
      getInfo: async () => { throw new Error('not available outside the app') },
      env: { VITE_APP_VERSION: '0.3.0', VITE_APP_BUILD: '52', VITE_BUILT_AT: '2026-10-16T07:30:00Z' },
    })
    expect(v).toEqual({ name: '0.3.0', build: 52, builtAt: '2026-10-16T07:30:00Z', native: false })
  })

  it('without any information it says «dev» and no build number, so it never looks outdated', async () => {
    const v = await getInstalledVersion({ native: () => false, getInfo: async () => { throw new Error('x') }, env: {} })
    expect(v).toEqual({ name: 'dev', build: null, builtAt: null, native: false })
  })

  it('a failing native call falls back to the compiled version instead of breaking the app', async () => {
    const v = await getInstalledVersion({
      native: () => true,
      getInfo: async () => { throw new Error('plugin missing') },
      env: { VITE_APP_VERSION: '0.3.0', VITE_APP_BUILD: '7' },
    })
    expect(v).toMatchObject({ name: '0.3.0', build: 7, native: true })
  })

  it('an unreadable build number is none, not NaN', async () => {
    const v = await getInstalledVersion({
      native: () => true, getInfo: async () => ({ name: 'x', id: 'y', build: 'abc', version: '1.0.0' }), env: {},
    })
    expect(v.build).toBeNull()
  })

  it('buildInfo reads the three compiled values', () => {
    expect(buildInfo({ VITE_APP_VERSION: '1.2.3', VITE_APP_BUILD: '9', VITE_BUILT_AT: 'now' }))
      .toEqual({ name: '1.2.3', build: 9, builtAt: 'now' })
  })
})
