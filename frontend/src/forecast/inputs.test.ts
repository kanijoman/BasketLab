import { beforeEach, describe, expect, it } from 'vitest'
import { DATA_FLAG_KEY } from '@/datasource/switch'
import { resetLocalData } from '@/localdata/source'
import { resetWebData, setDataBase } from '@/webdata/client'
import { getForecastInputs } from '@/api/forecast'
import { localForecastInputs } from './inputs'
import { FBCYL, FEB, readPublished, serveWebData, WEB_BASE, type WebDataHost } from '@/test/webDataHost'

// What the preview and the simulation read of a competition: its rows, its calendar (the competition may have none published) and its gender, from the REAL publication of the exporter
// (tests/local_vectors/web_data). Without the published files there is nothing to read and the pages say so: the API has no predictive any more.
let host: WebDataHost
beforeEach(() => { localStorage.clear(); resetWebData(); resetLocalData(); setDataBase(WEB_BASE); host = serveWebData() })

describe('the inputs of a competition', () => {
  it('are its rows, its calendar and its gender', async () => {
    const inputs = (await localForecastInputs(FEB))!
    expect(inputs.collection).toBe(FEB)
    expect(inputs.competition.team_rows.length).toBe(24)
    expect(inputs.calendar!.games).toBe(18)
    expect(inputs.gender).toBe('F')
  })

  it('of FBCYL too, with the ids of its rows as numbers and those of its calendar as texts', async () => {
    const inputs = (await localForecastInputs(FBCYL))!
    expect(inputs.calendar!.league).toBe('fbcyl')
    expect(typeof inputs.competition.team_rows[0].team_id).toBe('number')
    expect(typeof inputs.calendar!.matches[0].home.id).toBe('string')
  })

  it('have no calendar when the publication has none for the competition (the preview still has the games of the rows)', async () => {
    const manifest = JSON.parse(readPublished('index.json'))
    manifest.calendar = []
    host.override['index.json'] = JSON.stringify(manifest)
    const inputs = (await localForecastInputs(FEB))!
    expect(inputs.calendar).toBeNull()
    expect(inputs.competition.team_rows.length).toBe(24)
  })

  it('have no gender when the manifest does not say it', async () => {
    const manifest = JSON.parse(readPublished('index.json'))
    for (const row of manifest.rows) delete row.gender
    host.override['index.json'] = JSON.stringify(manifest)
    expect((await localForecastInputs(FEB))!.gender).toBeUndefined()
  })

  it('are nothing for a competition that is not published', async () => {
    expect(await localForecastInputs('NO_SUCH_COMPETITION')).toBeNull()
  })
})

describe('getForecastInputs', () => {
  it('reads the published files', async () => {
    expect((await getForecastInputs(FEB)).gender).toBe('F')
  })

  it('says it needs the published data when a competition has none (never the API: it has no predictive)', async () => {
    await expect(getForecastInputs('NO_SUCH_COMPETITION')).rejects.toThrow(/no están disponibles/)
  })

  it('says so with the API as the source too: the preview and the simulation only work with the published data', async () => {
    localStorage.setItem(DATA_FLAG_KEY, 'api')
    await expect(getForecastInputs(FEB)).rejects.toThrow('La previa y la simulación solo funcionan con los datos publicados.')
  })
})
