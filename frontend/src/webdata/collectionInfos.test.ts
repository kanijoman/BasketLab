import { beforeEach, describe, expect, it } from 'vitest'
import { loadWebCollectionInfos, resetWebData, setDataBase } from './client'
import { collectionList } from '@/localdata/collections'
import { FEB, FBCYL, readPublished, serveWebData, WEB_BASE, type WebDataHost } from '@/test/webDataHost'

// What the manifest says of each competition has to reach the selector whole: the category (#914), the age group, the name people read and the group as the site writes it. It was dropped on the way
// (only the collection, the league, the games and the gender passed), so the web said «Sénior» and the raw code for every competition of the published manifest, the 442 of formación included.
let host: WebDataHost
beforeEach(() => { resetWebData(); setDataBase(WEB_BASE); host = serveWebData() })

const withRow = (collection: string, extra: Record<string, unknown>) => {
  const manifest = JSON.parse(readPublished('index.json'))
  manifest.rows = manifest.rows.map((row: { collection: string }) => (row.collection === collection ? { ...row, ...extra } : row))
  host.override['index.json'] = JSON.stringify(manifest)
}

describe('the competitions the manifest lists, as the selector gets them', () => {
  it('keep the category the exporter wrote', async () => {
    const infos = await loadWebCollectionInfos()
    expect(infos.find(i => i.collection === FEB)).toMatchObject({ league: 'feb', games: 12, gender: 'F', category: 'senior' })
    expect(infos.find(i => i.collection === FBCYL)).toMatchObject({ league: 'fbcyl', category: 'senior' })
  })

  it('keep the age group, the name people read and the group of a youth competition', async () => {
    withRow(FEB, { category: 'formacion', age_group: 'U16', competition_label: 'Selecciones autonómicas · Cadete femenino', group_label: 'Fase final' })
    const info = (await loadWebCollectionInfos()).find(i => i.collection === FEB)
    expect(info).toMatchObject({ category: 'formacion', age_group: 'U16', competition_label: 'Selecciones autonómicas · Cadete femenino', group_label: 'Fase final' })
  })

  it('leave out what the manifest does not say, so an older publication is read as before', async () => {
    const info = (await loadWebCollectionInfos()).find(i => i.collection === FBCYL)!
    expect(Object.keys(info).sort()).toEqual(['category', 'collection', 'games', 'gender', 'league'])
  })

  it('reach the list of competitions: a youth competition is under Formación with its own name', async () => {
    withRow(FEB, { category: 'formacion', age_group: 'U18', competition_label: 'Liga Júnior', group_label: 'Grupo A' })
    const row = collectionList(await loadWebCollectionInfos()).find(c => c.name === FEB)
    expect(row).toMatchObject({ category: 'formacion', age_group: 'U18', competition_label: 'Liga Júnior', group_label: 'Grupo A' })
  })
})
