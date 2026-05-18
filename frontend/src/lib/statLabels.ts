/**
 * statLabels — abbreviation → human-readable label + description.
 *
 * Covers ALL column headers used across TeamStats, PlayerStats, Possessions,
 * Lineups, ShotChart and Rankings pages.  Used by tippedHeader() to generate
 * accessible tooltip annotations on column heads.
 */

export interface StatLabel {
  /** Short human-readable name (used in tooltip title) */
  label: string
  /** Full description shown in tooltip body */
  description: string
}

export const STAT_LABELS: Record<string, StatLabel> = {
  // ── Games / time ────────────────────────────────────────────────────────────
  PJ:      { label: 'Partidos Jugados',   description: 'Número total de partidos disputados en la temporada/período seleccionado.' },
  L:       { label: 'Local',              description: 'Partidos jugados como equipo local.' },
  V:       { label: 'Visitante',          description: 'Partidos jugados como equipo visitante.' },
  MIN:     { label: 'Minutos',            description: 'Minutos jugados por partido.' },

  // ── Scoring ─────────────────────────────────────────────────────────────────
  PPP:     { label: 'Puntos Por Partido', description: 'Media de puntos anotados por partido.' },
  PPC:     { label: 'Puntos en Contra/Partido', description: 'Media de puntos recibidos por partido. Menor es mejor.' },
  PTS:     { label: 'Puntos',             description: 'Media de puntos anotados por partido.' },
  PF:      { label: 'Puntos a Favor',     description: 'Puntos totales anotados en el período de quinteto analizado.' },
  PC:      { label: 'Puntos en Contra',   description: 'Puntos totales recibidos en el período de quinteto analizado.' },
  Pts:     { label: 'Puntos por Zona',    description: 'Puntos anotados en esta zona de tiro.' },

  // ── Shooting percentages ─────────────────────────────────────────────────────
  '%T2':   { label: '% Tiros de 2',       description: 'Porcentaje de acierto en tiros de 2 puntos.' },
  '%T3':   { label: '% Triples',          description: 'Porcentaje de acierto en tiros de 3 puntos.' },
  '%TL':   { label: '% Tiros Libres',     description: 'Porcentaje de acierto en tiros libres.' },

  // ── Shooting volume ──────────────────────────────────────────────────────────
  T2M:     { label: 'T2 Anotados',        description: 'Total de tiros de 2 anotados en la temporada.' },
  T2I:     { label: 'T2 Intentados',      description: 'Total de tiros de 2 intentados en la temporada.' },
  T3M:     { label: 'Triples Anotados',   description: 'Total de triples anotados en la temporada.' },
  T3I:     { label: 'Triples Intentados', description: 'Total de triples intentados en la temporada.' },

  // ── Shot zone table headers ──────────────────────────────────────────────────
  'T.I.':  { label: 'Tiros Intentados',   description: 'Intentos de campo en esta zona de la cancha.' },
  'T.A.':  { label: 'Tiros Anotados',     description: 'Canastas anotadas en esta zona de la cancha.' },
  '%TF':   { label: '% Tiro de Campo',    description: 'Porcentaje de acierto en tiros de campo en esta zona.' },

  // ── Rebounds ────────────────────────────────────────────────────────────────
  Reb:     { label: 'Rebotes',            description: 'Media de rebotes totales (ofensivos + defensivos) por partido.' },
  REB:     { label: 'Rebotes',            description: 'Media de rebotes totales (ofensivos + defensivos) por partido.' },
  RO:      { label: 'Rebotes Ofensivos',  description: 'Media de rebotes ofensivos por partido. Generan segundas oportunidades.' },
  RD:      { label: 'Rebotes Defensivos', description: 'Media de rebotes defensivos por partido. Limitan las segundas oportunidades rivales.' },

  // ── Assists / steals / turnovers / blocks / fouls ───────────────────────────
  Ast:     { label: 'Asistencias',        description: 'Media de asistencias por partido.' },
  AST:     { label: 'Asistencias',        description: 'Media de asistencias por partido.' },
  Rob:     { label: 'Robos',              description: 'Media de balones robados (recuperaciones) por partido.' },
  ROB:     { label: 'Robos',              description: 'Media de balones robados (recuperaciones) por partido.' },
  Perd:    { label: 'Pérdidas',           description: 'Media de pérdidas de balón por partido. Menor es mejor.' },
  PER:     { label: 'Pérdidas',           description: 'Media de pérdidas de balón por partido. Menor es mejor.' },
  Tap:     { label: 'Tapones',            description: 'Media de tapones por partido.' },
  TAP:     { label: 'Tapones',            description: 'Media de tapones por partido.' },
  FP:      { label: 'Faltas Personales',  description: 'Media de faltas personales cometidas por partido. Menor es mejor.' },

  // ── Valuation / plus-minus ────────────────────────────────────────────────
  VAL:     { label: 'Valoración FEB',     description: 'Índice de valoración oficial FEB. Combina estadísticas positivas y negativas en una sola cifra.' },
  '+/-':   { label: 'Plus/Minus',         description: 'Diferencia de puntos del equipo cuando este jugador está en pista.' },

  // ── Team efficiency ratings ──────────────────────────────────────────────────
  OER:     { label: 'Eficiencia Ofensiva', description: 'Puntos anotados por cada 100 posesiones (Offensive Efficiency Rating). Mayor es mejor.' },
  DER:     { label: 'Eficiencia Defensiva', description: 'Puntos recibidos por cada 100 posesiones (Defensive Efficiency Rating). Menor es mejor.' },
  Net:     { label: 'Net Rating',          description: 'Diferencia entre eficiencia ofensiva y defensiva. Positivo indica mejor ataque que defensa.' },
  'Net Rtg': { label: 'Net Rating Quinteto', description: 'Diferencia de puntos por cada 100 posesiones de este quinteto en pista.' },

  // ── Possessions & pace ───────────────────────────────────────────────────────
  Pos:     { label: 'Posesiones/Partido', description: 'Estimación del número de posesiones por partido.' },
  'Pos/P': { label: 'Posesiones/Partido', description: 'Estimación del número de posesiones por partido.' },
  Ritmo:   { label: 'Ritmo de Juego',     description: 'Posesiones de ambos equipos por partido normalizado a 40 min. Mide la velocidad del partido.' },

  // ── Advanced shooting percentages ────────────────────────────────────────────
  'eFG%':   { label: 'eFG% — Tiro Efectivo',       description: 'Porcentaje de tiro ajustado: pondera los triples por su mayor valor.' },
  'TS%':    { label: 'TS% — Porcentaje Real',       description: 'Eficiencia de tiro incluyendo tiros libres. El indicador de eficiencia ofensiva más completo.' },
  '3Pr%':   { label: '3Pr% — Tasa de Triple',       description: 'Proporción de intentos de campo que son triples. Mide la orientación exterior del ataque.' },
  'FTr%':   { label: 'FTr% — Tasa de Tiro Libre',   description: 'Tiros libres por intento de campo. Mide la agresividad atacando el aro.' },
  'AST/FG': { label: 'AST/FG — Asistencias por Canasta', description: 'Porcentaje de canastas del equipo precedidas de una asistencia.' },
  'AST%':   { label: 'AST% — Tasa de Asistencia',   description: 'Porcentaje de posesiones que acaban en asistencia. Mide la dependencia del juego colectivo.' },
  'TOV%':   { label: 'TOV% — Tasa de Pérdidas',     description: 'Porcentaje de posesiones que acaban en pérdida. Menor es mejor.' },
  'ROB%':   { label: 'ROB% — Tasa de Robo',         description: 'Porcentaje de posesiones defensivas que acaban en robo de balón.' },
  'TAP%':   { label: 'TAP% — Tasa de Tapón',        description: 'Porcentaje de intentos de campo rivales en que el equipo consigue un tapón.' },
  'ORB%':   { label: 'ORB% — Rebote Ofensivo',      description: 'Porcentaje de rebotes ofensivos disponibles que el equipo captura.' },
  'RD%':    { label: 'RD% — Rebote Defensivo',      description: 'Porcentaje de rebotes defensivos disponibles que el equipo captura.' },

  // ── Player individual advanced ratings ───────────────────────────────────────
  'Usg%':   { label: 'Usg% — Tasa de Uso',          description: 'Porcentaje de posesiones del equipo utilizadas por el jugador mientras está en pista.' },
  'ORtg':   { label: 'ORtg — Rating Ofensivo',       description: 'Puntos producidos por cada 100 posesiones individuales. Mide la eficiencia ofensiva del jugador.' },
  'DRtg':   { label: 'DRtg — Rating Defensivo',      description: 'Puntos permitidos por cada 100 posesiones cuando el jugador está en pista. Menor es mejor.' },
  'NetRtg': { label: 'NetRtg — Net Rating Individual', description: 'Diferencia entre el Rating Ofensivo y el Defensivo. Indica el impacto neto del jugador.' },
  'PIE%':   { label: 'PIE% — Player Impact Estimate', description: 'Estimación del impacto relativo del jugador en el partido. Cuanto mayor, más influye en el resultado. Los valores varían según categoría y competición; compara jugadores dentro de la misma liga.' },
  '%AST':   { label: '%AST — % Asistencias',         description: 'Porcentaje de canastas del equipo procedidas de asistencia del jugador mientras está en pista.' },
  '%TO':    { label: '%TO — % Pérdidas',             description: 'Porcentaje de posesiones del jugador que acaban en pérdida. Menor es mejor.' },
  '%ROB':   { label: '%ROB — % Robos',               description: 'Porcentaje de posesiones defensivas del rival en que el jugador consigue robo.' },
  '%TAP':   { label: '%TAP — % Tapones',             description: 'Porcentaje de intentos de campo rivales tapados por el jugador mientras está en pista.' },
  '%RD':    { label: '%RD — % Rebote Defensivo',     description: 'Porcentaje de rebotes defensivos disponibles capturados por el jugador.' },
  '%RO':    { label: '%RO — % Rebote Ofensivo',      description: 'Porcentaje de rebotes ofensivos disponibles capturados por el jugador.' },
  'FTr':    { label: 'FTr — Tasa de Tiro Libre',     description: 'Tiros libres intentados por intento de campo. Mide la agresividad atacando el aro.' },
  '3Pr':    { label: '3Pr — Tasa de Triple',         description: 'Proporción de intentos de campo que son triples. Mide la orientación exterior del ataque.' },

  // ── Projection columns (×30 min) ─────────────────────────────────────────────
  'PTS×30': { label: 'Puntos × 30 min',       description: 'Proyección de puntos si jugara 30 minutos por partido (escala proporcional a los minutos reales).' },
  'REB×30': { label: 'Rebotes × 30 min',      description: 'Proyección de rebotes totales si jugara 30 minutos por partido.' },
  'AST×30': { label: 'Asistencias × 30 min',  description: 'Proyección de asistencias si jugara 30 minutos por partido.' },
  'ROB×30': { label: 'Robos × 30 min',        description: 'Proyección de robos si jugara 30 minutos por partido.' },
  'PER×30': { label: 'Pérdidas × 30 min',     description: 'Proyección de pérdidas si jugara 30 minutos por partido. Menor es mejor.' },
  'TAP×30': { label: 'Tapones × 30 min',      description: 'Proyección de tapones si jugara 30 minutos por partido.' },
  'VAL×30': { label: 'Valoración × 30 min',   description: 'Proyección de valoración FEB si jugara 30 minutos por partido.' },
  '+/-×30': { label: '+/- × 30 min',          description: 'Proyección de plus/minus si jugara 30 minutos por partido.' },

  // ── Elasticity model stats (snake_case keys from HISTORICAL schema) ──────────
  'net_rtg':  { label: 'Net Rating',             description: 'Diferencia entre el rating ofensivo y defensivo por 100 posesiones. Indicador global de rendimiento.' },
  'ortg':     { label: 'Rating Ofensivo',        description: 'Puntos anotados por cada 100 posesiones.' },
  'drtg':     { label: 'Rating Defensivo',       description: 'Puntos encajados por cada 100 posesiones. Menor es mejor.' },
  'efg_pct':  { label: 'eFG%',                   description: 'Porcentaje de tiro efectivo: pondera los triples por su mayor valor.' },
  'tov_rate': { label: 'Tasa de Pérdida',        description: 'Pérdidas por cada 100 posesiones. Menor es mejor.' },
  'oreb_pct': { label: 'ORB% — Rebote Ofensivo', description: 'Porcentaje de rebotes ofensivos disponibles capturados.' },
}
