// Statistics the scouting matchup covers (issue #751). It is the catalog of the report engine (`src/report_engine/catalog.py`, same keys, labels, groups and direction):
// `scoutingCompare.test.ts` fails if it drifts from the Python one (tests/local_vectors/scouting_compare.json).
export interface StatDef {
  key: string
  label: string
  group: string
  /** `null` = neutral (it depends on the style: tempo, shot mix, bench share). */
  higher_is_better: boolean | null
  pct: boolean
}

export const STAT_CATALOG: StatDef[] = [
  { key: "points_per_game", label: "Puntos por partido", group: "Básicas", higher_is_better: true, pct: false },
  { key: "points_against_per_game", label: "Puntos recibidos por partido", group: "Básicas", higher_is_better: false, pct: false },
  { key: "rebounds_per_game", label: "Rebotes por partido", group: "Básicas", higher_is_better: true, pct: false },
  { key: "offensive_rebounds_per_game", label: "Rebotes ofensivos por partido", group: "Básicas", higher_is_better: true, pct: false },
  { key: "defensive_rebounds_per_game", label: "Rebotes defensivos por partido", group: "Básicas", higher_is_better: true, pct: false },
  { key: "assists_per_game", label: "Asistencias por partido", group: "Básicas", higher_is_better: true, pct: false },
  { key: "steals_per_game", label: "Robos por partido", group: "Básicas", higher_is_better: true, pct: false },
  { key: "turnovers_per_game", label: "Pérdidas por partido", group: "Básicas", higher_is_better: false, pct: false },
  { key: "blocks_per_game", label: "Tapones por partido", group: "Básicas", higher_is_better: true, pct: false },
  { key: "possessions_per_game", label: "Posesiones por partido", group: "Básicas", higher_is_better: null, pct: false },
  { key: "fg2_percentage", label: "% tiros de 2", group: "Tiro", higher_is_better: true, pct: true },
  { key: "fg3_percentage", label: "% triples", group: "Tiro", higher_is_better: true, pct: true },
  { key: "ft_percentage", label: "% tiros libres", group: "Tiro", higher_is_better: true, pct: true },
  { key: "three_point_rate", label: "Tasa de triples (3PA/FGA)", group: "Tiro", higher_is_better: null, pct: true },
  { key: "efg_percentage", label: "eFG%", group: "Four Factors", higher_is_better: true, pct: true },
  { key: "true_shooting", label: "TS%", group: "Four Factors", higher_is_better: true, pct: true },
  { key: "turnover_rate", label: "TOV%", group: "Four Factors", higher_is_better: false, pct: true },
  { key: "offensive_rebound_rate", label: "ORB%", group: "Four Factors", higher_is_better: true, pct: true },
  { key: "free_throw_rate", label: "FTr", group: "Four Factors", higher_is_better: true, pct: true },
  { key: "assist_rate", label: "Ratio de asistencias", group: "Juego colectivo", higher_is_better: true, pct: true },
  { key: "assist_fg_rate", label: "% canastas asistidas", group: "Juego colectivo", higher_is_better: true, pct: true },
  { key: "steal_rate", label: "Ratio de robos", group: "Juego colectivo", higher_is_better: true, pct: true },
  { key: "block_rate", label: "Ratio de tapones", group: "Juego colectivo", higher_is_better: true, pct: true },
  { key: "defensive_rebound_rate", label: "DRB%", group: "Juego colectivo", higher_is_better: true, pct: true },
  { key: "offensive_rating", label: "Rating ofensivo (ORtg)", group: "Eficiencia", higher_is_better: true, pct: false },
  { key: "defensive_rating", label: "Rating defensivo (DRtg)", group: "Eficiencia", higher_is_better: false, pct: false },
  { key: "net_rating", label: "Net Rating", group: "Eficiencia", higher_is_better: true, pct: false },
  { key: "pts_off_tov_per_game", label: "Puntos tras pérdida rival por partido", group: "Origen de los puntos", higher_is_better: true, pct: false },
  { key: "opp_pts_off_tov_per_game", label: "Puntos concedidos tras pérdida propia", group: "Origen de los puntos", higher_is_better: false, pct: false },
  { key: "pts_second_chance_per_game", label: "Puntos de 2ª oportunidad por partido", group: "Origen de los puntos", higher_is_better: true, pct: false },
  { key: "opp_pts_second_chance_per_game", label: "Puntos de 2ª oportunidad concedidos", group: "Origen de los puntos", higher_is_better: false, pct: false },
  { key: "pts_paint_per_game", label: "Puntos en la pintura por partido", group: "Origen de los puntos", higher_is_better: true, pct: false },
  { key: "opp_pts_paint_per_game", label: "Puntos en la pintura concedidos", group: "Origen de los puntos", higher_is_better: false, pct: false },
  { key: "bench_pct", label: "% de puntos del banquillo", group: "Origen de los puntos", higher_is_better: null, pct: true },
]
