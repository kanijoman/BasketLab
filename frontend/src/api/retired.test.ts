import { describe, expect, it } from 'vitest'
import * as client from './client'

// The Administration page is gone (issue #724, step towards a server that takes no writes): the data is loaded by the scheduled refresh of the archive (`archive-refresh.yml`), a competition
// is removed with the purge (`archive-purge.yml`) and the server no longer takes writes from the web. So the web has no call for them. What the kept predictive code needs
// (`getHistoricalSeasons`, `getHistoricalTeams`) stays.
const RETIRED = [
  'postScrapeStart', 'getScrapeProgress', 'postHistoricalIngest', 'getHistoricalProgress', 'getHistoricalSummary', 'postCompetitionIngest', 'deleteCollection',
  'getFebCompetitions', 'getFebSeasons', 'getFebGroups', 'getFbcylInit', 'getFbcylCategories', 'getFbcylCompetitions',
]

describe('the API of the web without the Administration', () => {
  it.each(RETIRED)('has no %s', name => {
    expect((client as Record<string, unknown>)[name]).toBeUndefined()
  })

  it('keeps what the kept predictive code reads', () => {
    expect(typeof client.getHistoricalSeasons).toBe('function')
    expect(typeof client.getHistoricalTeams).toBe('function')
  })
})
