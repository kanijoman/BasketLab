// Advanced player figures (USG%, ORtg, DRtg, PIE…) on the device: a line-by-line port of `src/live_core/advanced_stats.py` and
// `advanced_ratings.py` (Basketball Reference formulas) so that the local player tables agree with the API (issue #327). Parity is enforced
// by `aggregatePlayers.test.ts`; change the Python and the vectors first.
type Totals = Record<string, number | undefined>
const v = (o: Totals, key: string, fallback = 0) => o[key] ?? fallback

/** Minutes the five players of the team have played: 200 per game in the season totals. */
const teamMinutes = (t: Totals) => v(t, 'team_minutes') || v(t, 'total_games', 1) * 200

const fga = (p: Totals, a = 'total_p2a', b = 'total_p3a') => v(p, a) + v(p, b)
const teamFga = (t: Totals) => fga(t, 'fg2_attempted', 'fg3_attempted')

export function usagePercentage(p: Totals, team: Totals): number {
  const mp = v(p, 'total_minutes')
  const tMp = teamMinutes(team)
  if (mp === 0 || tMp === 0) return 0
  const plays = fga(p) + 0.44 * v(p, 'total_p1a') + v(p, 'total_to')
  const teamPlays = teamFga(team) + 0.44 * v(team, 'ft_attempted') + v(team, 'turnovers')
  if (teamPlays === 0) return 0
  return Math.min((100 * (plays * (tMp / 5))) / (mp * teamPlays), 100)
}

export function assistPercentage(p: Totals, team: Totals): number {
  const mp = v(p, 'total_minutes')
  const tMp = teamMinutes(team)
  if (mp === 0 || tMp === 0) return 0
  const fg = v(p, 'total_p2m') + v(p, 'total_p3m')
  const teamFg = v(team, 'fg2_made') + v(team, 'fg3_made')
  const denominator = (mp / (tMp / 5)) * teamFg - fg
  return denominator <= 0 ? 0 : (100 * v(p, 'total_assist')) / denominator
}

export function turnoverPercentage(p: Totals): number {
  const denominator = fga(p) + 0.44 * v(p, 'total_p1a') + v(p, 'total_to')
  return denominator === 0 ? 0 : (100 * v(p, 'total_to')) / denominator
}

export function stealPercentage(p: Totals, team: Totals, opp: Totals): number {
  const mp = v(p, 'total_minutes')
  const tMp = teamMinutes(team)
  if (mp === 0 || tMp === 0) return 0
  const oppPerGame = v(opp, 'possessions_per_game', 100) || 100
  const oppPoss = oppPerGame * v(team, 'total_games', 1)
  return oppPoss === 0 ? 0 : (100 * (v(p, 'total_st') * (tMp / 5))) / (mp * oppPoss)
}

export function blockPercentage(p: Totals, team: Totals, opp: Totals): number {
  const mp = v(p, 'total_minutes')
  const tMp = teamMinutes(team)
  if (mp === 0 || tMp === 0) return 0
  const denominator = mp * (teamFga(opp) - v(opp, 'fg3_attempted'))
  return denominator === 0 ? 0 : (100 * (v(p, 'total_bs') * (tMp / 5))) / denominator
}

export function reboundPercentage(p: Totals, team: Totals, opp: Totals, offensive: boolean): number {
  const mp = v(p, 'total_minutes')
  const tMp = teamMinutes(team)
  if (mp === 0 || tMp === 0) return 0
  const reb = offensive ? v(p, 'total_ro') : v(p, 'total_rd')
  const pool = offensive ? v(team, 'rebounds_off') + v(opp, 'rebounds_def') : v(team, 'rebounds_def') + v(opp, 'rebounds_off')
  const denominator = mp * pool
  return denominator === 0 ? 0 : (100 * (reb * (tMp / 5))) / denominator
}

export function offensiveRating(p: Totals, team: Totals, opp: Totals): number {
  const mp = v(p, 'total_minutes')
  const pts = v(p, 'total_pts')
  const fgm = v(p, 'total_p2m') + v(p, 'total_p3m')
  const fgA = fga(p)
  const threePm = v(p, 'total_p3m')
  const ftm = v(p, 'total_p1m')
  const fta = v(p, 'total_p1a')
  const orb = v(p, 'total_ro')
  const ast = v(p, 'total_assist')
  const tov = v(p, 'total_to')
  const tMp = teamMinutes(team)
  const tPts = v(team, 'points_scored')
  const tFgm = v(team, 'fg2_made') + v(team, 'fg3_made')
  const tFga = teamFga(team)
  const tThreePm = v(team, 'fg3_made')
  const tFtm = v(team, 'ft_made')
  const tFta = v(team, 'ft_attempted')
  const tOrb = v(team, 'rebounds_off')
  const tAst = v(team, 'assists')
  const tTov = v(team, 'turnovers')
  const oppDrb = v(opp, 'total_rebounds') - v(opp, 'rebounds_off')
  if (mp === 0 || tMp === 0 || tFta === 0 || tFga === 0) return 100

  const term1 = tFgm > 0 ? (mp / (tMp / 5)) * (1.14 * ((tAst - ast) / tFgm)) : 0
  const term2Num = (tAst / tMp) * mp * 5 - ast
  const term2Den = (tFgm / tMp) * mp * 5 - fgm
  const term2 = term2Den !== 0 ? (term2Num / term2Den) * (1 - mp / (tMp / 5)) : 0
  const qAst = term1 + term2
  const teamScoringPoss = tFgm + (1 - (1 - tFtm / tFta) ** 2) * tFta * 0.4
  const teamOrbPct = tOrb + oppDrb > 0 ? tOrb / (tOrb + oppDrb) : 0
  const playDen = tFga + tFta * 0.4 + tTov
  const teamPlayPct = playDen > 0 ? teamScoringPoss / playDen : 0
  const weightDen = (1 - teamOrbPct) * teamPlayPct + teamOrbPct * (1 - teamPlayPct)
  const teamOrbWeight = weightDen > 0 ? ((1 - teamOrbPct) * teamPlayPct) / weightDen : 0

  const fgPart = fgA > 0 ? fgm * (1 - 0.5 * ((pts - ftm) / (2 * fgA)) * qAst) : 0
  const astPart = tFga - fgA > 0 ? 0.5 * ((tPts - tFtm - (pts - ftm)) / (2 * (tFga - fgA))) * ast : 0
  const ftPart = fta > 0 ? (1 - (1 - ftm / fta) ** 2) * 0.4 * fta : 0
  const orbPart = orb * teamOrbWeight * teamPlayPct
  const scPoss = teamScoringPoss > 0
    ? (fgPart + astPart + ftPart) * (1 - (tOrb / teamScoringPoss) * teamOrbWeight * teamPlayPct) + orbPart
    : 0
  const fgxPoss = (fgA - fgm) * (1 - 1.07 * teamOrbPct)
  const ftxPoss = fta > 0 ? (1 - ftm / fta) ** 2 * 0.4 * fta : 0
  const totPoss = scPoss + fgxPoss + ftxPoss + tov
  if (totPoss === 0) return 100

  const pprodFgPart = fgA > 0 ? 2 * (fgm + 0.5 * threePm) * (1 - 0.5 * ((pts - ftm) / (2 * fgA)) * qAst) : 0
  const pprodAstPart = tFgm - fgm > 0 && tFga - fgA > 0
    ? 2 * ((tFgm - fgm + 0.5 * (tThreePm - threePm)) / (tFgm - fgm)) * 0.5 * ((tPts - tFtm - (pts - ftm)) / (2 * (tFga - fgA))) * ast
    : 0
  const ptsPerScoringPoss = tFgm + (1 - (1 - tFtm / tFta) ** 2) * 0.4 * tFta
  const pprodOrbPart = ptsPerScoringPoss > 0 ? orb * teamOrbWeight * teamPlayPct * (tPts / ptsPerScoringPoss) : 0
  const pprod = teamScoringPoss > 0
    ? (pprodFgPart + pprodAstPart + ftm) * (1 - (tOrb / teamScoringPoss) * teamOrbWeight * teamPlayPct) + pprodOrbPart
    : 0
  return 100 * (pprod / totPoss)
}

export function defensiveRating(p: Totals, team: Totals, opp: Totals): number {
  const mp = v(p, 'total_minutes')
  const stl = v(p, 'total_st')
  const blk = v(p, 'total_bs')
  const drb = v(p, 'total_rd')
  const pf = v(p, 'total_pf')
  const tMp = teamMinutes(team)
  const tDrb = v(team, 'rebounds_def')
  const tBlk = v(team, 'blocks')
  const tStl = v(team, 'steals')
  const tPf = v(team, 'personal_fouls')                              // the team table has no such field: 0, as in Python
  const oPts = v(opp, 'points_scored')
  const oFgm = v(opp, 'fg2_made') + v(opp, 'fg3_made')
  const oFga = teamFga(opp)
  const oFtm = v(opp, 'ft_made')
  const oFta = v(opp, 'ft_attempted')
  const oOrb = v(opp, 'rebounds_off')
  const oTov = v(opp, 'turnovers')
  if (mp === 0 || tMp === 0 || oFga === 0 || oFta === 0) return 100

  let teamPoss = oOrb + tDrb > 0 ? oFga + 0.4 * oFta - 1.07 * (oOrb / (oOrb + tDrb)) * (oFga - oFgm) + oTov : 100
  teamPoss = teamPoss > 0 ? teamPoss : 100
  const dorPct = oOrb + tDrb > 0 ? oOrb / (oOrb + tDrb) : 0
  const dfgPct = oFga > 0 ? oFgm / oFga : 0
  const fmWtDen = dfgPct * (1 - dorPct) + (1 - dfgPct) * dorPct
  const fmWt = fmWtDen > 0 ? (dfgPct * (1 - dorPct)) / fmWtDen : 0.6
  const stops1 = stl + blk * fmWt * (1 - 1.07 * dorPct) + drb * (1 - fmWt)
  const stops2Term1 = ((oFga - oFgm - tBlk) / tMp) * fmWt * (1 - 1.07 * dorPct)
  const stops2Term2 = (oTov - tStl) / tMp
  const stops2Term3 = tPf > 0 && oFta > 0 ? (pf / tPf) * 0.4 * oFta * (1 - oFtm / oFta) ** 2 : 0
  const stops = stops1 + (stops2Term1 + stops2Term2) * mp + stops2Term3
  const stopPct = teamPoss * mp > 0 ? (stops * tMp) / (teamPoss * mp) : 0
  const teamDrtg = 100 * (oPts / teamPoss)
  const oppScPoss = oFta > 0 ? oFgm + (1 - (1 - oFtm / oFta) ** 2) * oFta * 0.4 : oFgm
  const dPtsPerScPoss = oppScPoss > 0 ? oPts / oppScPoss : 1
  return teamDrtg + 0.2 * (100 * dPtsPerScPoss * (1 - stopPct) - teamDrtg)
}

export function netRating(p: Totals, team: Totals, opp: Totals): number {
  const ortg = offensiveRating(p, team, opp)
  const drtg = defensiveRating(p, team, opp)
  return ortg === 100 && drtg === 100 ? 0 : ortg - drtg
}

// PTS + FGM + FTM - FGA - FTA + DRB + 0.5 ORB + AST + STL + 0.5 BLK - PF - TOV, of a player or of a team (whose fouls are not in the table: 0)
const playerImpact = (s: Totals) =>
  v(s, 'total_pts') + v(s, 'total_p2m') + v(s, 'total_p3m') + v(s, 'total_p1m') - fga(s) - v(s, 'total_p1a') + v(s, 'total_rd')
  + 0.5 * v(s, 'total_ro') + v(s, 'total_assist') + v(s, 'total_st') + 0.5 * v(s, 'total_bs') - v(s, 'total_pf') - v(s, 'total_to')

const teamImpact = (s: Totals) =>
  v(s, 'points_scored') + v(s, 'fg2_made') + v(s, 'fg3_made') + v(s, 'ft_made') - teamFga(s) - v(s, 'ft_attempted') + v(s, 'rebounds_def')
  + 0.5 * v(s, 'rebounds_off') + v(s, 'assists') + v(s, 'steals') + 0.5 * v(s, 'blocks') - v(s, 'personal_fouls') - v(s, 'turnovers')

export function pie(p: Totals, team: Totals, opp: Totals): number {
  const gameImpact = teamImpact(team) + teamImpact(opp)
  return gameImpact === 0 ? 0 : 100 * (playerImpact(p) / gameImpact)
}
