// The datasets of the web (issues #329, #334, #1199): which published answer a page reads. The web reads the published files and NOTHING else since the API was retired
// (epic #1199): there is no switch, no `?data=` and no fallback; when the files cannot answer, `datasource/resolve` gives a clear error.

/** What a page reads, by the answer it needs (the pages that share an answer share its dataset). Which pages read what: docs/ARCHITECTURE.md. */
export const DATASETS = ['collections', 'team-stats', 'player-stats', 'team-comparison', 'multi-phase', 'evolution', 'pbp', 'shots', 'rotations', 'lineups', 'inout', 'player-consistency', 'rival-adjusted', 'assist-connections', 'matches', 'possessions', 'team-report', 'report-teams', 'scouting', 'weekly-report', 'forecast'] as const
export type Dataset = (typeof DATASETS)[number]
