import { beforeEach, describe, expect, it } from 'vitest'
import { loadWebCollectionInfos, resetWebData, setDataBase, setExtDataBase } from '@/webdata/client'
import { collectionList } from '@/localdata/collections'
import { pickCollection } from './collectionPicker'
import { EXT_BASE, FBCYL, FEB, FIBA, NCAA, serveBoth, WEB_BASE, type TwoHosts } from '@/test/webDataHost'

// The external sources in the selector (#884, PR C), with the competitions of the two REAL publications: the ámbito is the source, the competition is the name of the catalogue («NCAA D1») and the conference is the
// group. Gender and division go inside the name of the competition, as they already do in FEB («LF Endesa», «Primera FEB»): the five levels stay as they were.
let hosts: TwoHosts
beforeEach(() => { resetWebData(); setDataBase(WEB_BASE); setExtDataBase(EXT_BASE); hosts = serveBoth() })

describe('the selector with the external sources', () => {
  it('has one ámbito per source next to FEB and FBCYL, with the same levels as ever', async () => {
    const list = collectionList(await loadWebCollectionInfos())
    expect(pickCollection(list, {}).ambitos).toEqual(['FEB', 'FBCYL', 'FIBA', 'NCAA'])
  })

  it('names an NCAA competition by its catalogue name, with the conference as the group', async () => {
    const picked = pickCollection(collectionList(await loadWebCollectionInfos()), { ambito: 'NCAA' })
    expect(picked.selection).toMatchObject({ ambito: 'NCAA', category: 'Sénior', competition: 'NCAA D1', group: 'SEC' })
    expect(picked.competitions).toEqual(['NCAA D1'])
    expect(picked.groups).toEqual(['SEC'])
    expect(picked.collection?.name).toBe(NCAA)
  })

  it('names a FIBA competition by its catalogue name, with no group when the source has no conferences', async () => {
    const picked = pickCollection(collectionList(await loadWebCollectionInfos()), { ambito: 'FIBA' })
    expect(picked.selection).toMatchObject({ ambito: 'FIBA', competition: 'FIBA U18 EuroBasket' })
    expect(picked.collection?.name).toBe(FIBA)
    expect(picked.groups.filter(Boolean)).toEqual([])
  })

  it('does not disturb FEB and FBCYL: they are chosen as before', async () => {
    const list = collectionList(await loadWebCollectionInfos())
    expect(pickCollection(list, { ambito: 'FEB' }).collection?.name).toBe(FEB)
    expect(pickCollection(list, { ambito: 'FBCYL' }).collection?.name).toBe(FBCYL)
  })

  it('is the list of FEB and FBCYL alone, with the same ámbitos as before, while the external publication is down', async () => {
    hosts.ext.override['index.json'] = null
    const picker = pickCollection(collectionList(await loadWebCollectionInfos()), {})
    expect(picker.ambitos).toEqual(['FEB', 'FBCYL'])
    expect(picker.collection?.name).toBe(FEB)
  })
})
