// The rows of one competition, as the exporter writes them (`src/local_data/export.py`): what the season tables are computed from on the device. They come
// sealed from the publication (`webdata/client.loadWebRows`) or, in development, from the manual export (`local-data/`).
import type { FbcylPlayerGameRow } from './aggregatePlayersFbcyl'
import type { PlayerGameRow } from './aggregatePlayers'
import type { GameRow } from './aggregateTeams'

export interface Competition {
  format: number
  collection: string
  league: 'feb' | 'fbcyl'
  games: number
  team_rows: GameRow[]
  player_rows: PlayerGameRow[] | FbcylPlayerGameRow[] | null
}
