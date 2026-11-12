// The static host of `talent-data` for tests (#878): serves the files of the REAL publication of the exporter (`tests/local_vectors/talent_data`, made by `generate_talent_data.py`).
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { serveDirectory, type WebDataHost } from './webDataHost'

export const TALENT_DATA_DIR = join(__dirname, '../../../tests/local_vectors/talent_data')
export const TALENT_BASE = 'https://talent.test/'
export const LF2_KEY = 'feb|lf2|2025'
export const FBCYL_KEY = 'fbcyl|1129-1|2026'

export const readTalent = (file: string) => readFileSync(join(TALENT_DATA_DIR, file), 'utf-8')
export const serveTalentData = (): WebDataHost => serveDirectory(TALENT_DATA_DIR, TALENT_BASE)
