/** The matches kept on the device: the finished live matches (issue #407) and the recordings of the feed (issue #416), with the clean-up of the first start under a new REPLAY_COMPAT (#562). */
import { useCallback, useEffect, useState, type MutableRefObject } from 'react'
import type { LoggedAlert, SessionMeta } from '../engine/types'
import { competitionLabel } from '../package/remote'
import { summarizePackage } from '../package/summary'
import { purgeStale } from '../feed/compatMigration'
import { REPLAY_COMPAT } from '../feed/replayCompat'
import { encodeRecording, type RecordingStore, type SavedRecording } from '../feed/recordingStore'
import type { FinishedMatch, FinishedStore } from '../feed/finishedStore'

export interface FollowedMatch {
  /** The package the engine was started with: what a match followed is kept with (the store may already hold the next one, #557). */
  plaintext: MutableRefObject<string | null>
  meta: MutableRefObject<SessionMeta | null>
  /** Every alert of the match being followed (the annex of the post-match report, #409). */
  alerts: MutableRefObject<LoggedAlert[]>
  title: MutableRefObject<string | null>
}

interface Deps {
  finishedStore: FinishedStore
  recordingStore: RecordingStore
  followed: FollowedMatch
  shareFile: (bytes: Uint8Array, fileName: string, title: string, mime: string) => Promise<void>
  record: (line: string) => void
}

export function useStoredMatches({ finishedStore, recordingStore, followed, shareFile, record }: Deps) {
  const [finishedMatches, setFinishedMatches] = useState<FinishedMatch[]>([])
  const [recordings, setRecordings] = useState<SavedRecording[]>([])
  const [purgedNotice, setPurgedNotice] = useState<string | null>(null)

  // the first start under a new REPLAY_COMPAT clears what an older version kept and says so (#562); the lists are read after it
  useEffect(() => {
    void purgeStale(finishedStore, recordingStore).then(async purged => {
      const count = purged.finished.length + purged.recordings.length
      if (count > 0) setPurgedNotice(`Se han eliminado ${count} ${count === 1 ? 'partido guardado' : 'partidos guardados'} con una versión anterior de la app (ya no se podían revisar con fiabilidad): ${[...purged.finished, ...purged.recordings].join(', ')}.`)
      setFinishedMatches(await finishedStore.list())
      setRecordings(await recordingStore.list())
    })
  }, [finishedStore, recordingStore])

  /** The match ended: keep it on the device so it can be reviewed afterwards (issue #407). */
  const keepFinished = useCallback(async (game: string, code: string, complete: boolean) => {
    const plaintext = followed.plaintext.current, current = followed.meta.current, alerts = [...followed.alerts.current]      // taken now: a new package may be loaded while this is saved (#557)
    if (!plaintext || !current) { record(`Partido ${code}: no se pudo guardar para revisarlo (sin paquete cargado)`); return }
    const match: FinishedMatch = {
      code, title: `${current.team.name} – ${current.rival.name}`, savedAt: new Date().toISOString(), ownId: current.team.id,
      competition: competitionLabel(summarizePackage(plaintext).collection) || undefined,
      alerts, plaintext, game, complete, compat: REPLAY_COMPAT,
    }
    await finishedStore.save(match)
    setFinishedMatches(await finishedStore.list())
    if (complete) record(`Partido ${code} finalizado y guardado para revisarlo`)
  }, [finishedStore, followed, record])

  /** The engine kept a recording of the feed (issue #416): it is saved, gzipped, whether the match ended or the staff disconnected. */
  const keepRecording = useCallback(async ({ code, recording, complete }: { code: string; recording: unknown; complete: boolean }) => {
    const title = followed.title.current ?? code
    const { encoding, bytes } = await encodeRecording(JSON.stringify(recording))
    await recordingStore.save({
      code, title, savedAt: new Date().toISOString(), complete,
      frames: (recording as { frames?: unknown[] }).frames?.length ?? 0, encoding, bytes, compat: REPLAY_COMPAT,
    })
    setRecordings(await recordingStore.list())
    record(`Grabación del partido ${code} guardada (${complete ? 'completa' : 'incompleta'})`)
  }, [recordingStore, followed, record])

  /** Shares the file of a recording: the one the repository keeps in ``tests/recordings`` (issue #416). */
  const shareRecording = useCallback(async (code: string) => {
    const saved = await recordingStore.load(code)
    if (!saved) return
    const gz = saved.encoding === 'gzip'
    await shareFile(saved.bytes, `grabacion-${code}.rec.json${gz ? '.gz' : ''}`, `Grabación del partido ${saved.title}`, gz ? 'application/gzip' : 'application/json')
    record(`Grabación del partido ${code} compartida`)
  }, [recordingStore, shareFile, record])

  /** Deletes a saved match or a recording from the device (issue #512). */
  const removeFinished = useCallback(async (code: string) => {
    await finishedStore.remove(code)
    setFinishedMatches(await finishedStore.list())
    record(`Partido finalizado ${code} eliminado`)
  }, [finishedStore, record])
  const removeRecording = useCallback(async (code: string) => {
    await recordingStore.remove(code)
    setRecordings(await recordingStore.list())
    record(`Grabación ${code} eliminada`)
  }, [recordingStore, record])

  return { finishedMatches, recordings, purgedNotice, keepFinished, keepRecording, shareRecording, removeFinished, removeRecording }
}
