// The REAL competitions the forecast is tested on (#847, #848): captured from the local database and the federation by `scripts/capture_forecast_fixtures.py` into `tests/fixtures/forecast/`.
// The team rows are exactly what the exporter publishes (`export_collection`, without player rows) and the calendar is the payload of `calendar_export` as it was the day it was captured.
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { gunzipSync } from 'node:zlib'
import type { Competition } from '@/localdata/competition'
import type { Calendar } from '@/webdata/calendar'

const DIR = join(__dirname, '../../../tests/fixtures/forecast')
const read = <T>(name: string): T => JSON.parse(gunzipSync(readFileSync(join(DIR, `${name}.json.gz`))).toString('utf-8')) as T

export type Fixture = Competition & { gender: 'F' | 'M' }

/** A complete men's season: Primera FEB 2025-26, 271 games, 18 teams. */
export const primera = (): Fixture => read<Fixture>('primera_feb_2025_2026')
/** An early women's season: LF Challenge 2026-27 on 9/11/2026, 39 games of 16 teams (and its calendar has 8 more results). */
export const lfChallenge = (): Fixture => read<Fixture>('lf_challenge_2026_2027')
/** The calendar of the LF Challenge the same day: 240 matches, 47 results (8 not in the archive) and 193 still to play. */
export const lfChallengeCalendar = (): Calendar => read<Calendar>('lf_challenge_2026_2027.calendar')
/** An early FBCYL group (1ª División Femenina, group A-1): 17 games, one of them tied. */
export const fbcyl = (): Fixture => read<Fixture>('fbcyl_a1_2026')
