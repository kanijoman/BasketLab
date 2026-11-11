import { describe, expect, it } from 'vitest'
import * as client from './client'

// The Administration page is gone (issue #724, step towards a server that takes no writes): the data is loaded by the scheduled refresh of the archive (`archive-refresh.yml`), a competition
// is removed with the purge (`archive-purge.yml`) and the server no longer takes writes from the web. So the web has no call for them. The old predictive analysis (Ridge models,
// Monte Carlo per statistic, player prediction, backtesting, HISTORICAL) is gone too (#852): the preview and the league simulation are computed in the browser (`forecast/`).
const RETIRED = [
  'postScrapeStart', 'getScrapeProgress', 'postHistoricalIngest', 'getHistoricalProgress', 'getHistoricalSummary', 'postCompetitionIngest', 'deleteCollection',
  'getFebCompetitions', 'getFebSeasons', 'getFebGroups', 'getFbcylInit', 'getFbcylCategories', 'getFbcylCompetitions',
  // the old predictive analysis (#852)
  'getHistoricalSeasons', 'getHistoricalTeams', 'postTrainElasticity', 'getElasticityModels', 'getElasticityPredict', 'getElasticityPredictLive', 'postMonteCarlo',
  'getBacktesting', 'getBacktestingLive', 'postGamePrediction', 'getPlayerPrediction', 'getSeasonProjection',
]

describe('the API of the web without the Administration', () => {
  it.each(RETIRED)('has no %s', name => {
    expect((client as Record<string, unknown>)[name]).toBeUndefined()
  })

  it('keeps what other pages read and the predictive analysis shared: the rival-adjusted figures and the names of the teams of a competition', () => {
    expect(typeof client.getRivalAdjusted).toBe('function')
    expect(typeof client.getLiveTeamNames).toBe('function')
  })
})
