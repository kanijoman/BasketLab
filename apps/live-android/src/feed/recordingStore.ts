/** The recordings of the matches followed live, kept on the device (issue #416): the same format as the CI recorder's, gzipped, so the
 *  file the staff shares goes straight into ``tests/recordings`` and replays like any other. A few kilobytes each, but only the latest. */
import { IndexedDbKeyedStore, memoryKeyedStore, safeKeyedStore, type KeyedStore } from './keyedStore'

export interface SavedRecording {
  /** FEB match code. */
  code: string
  title: string
  savedAt: string
  /** The match reached its end (a recording of a disconnection halfway is kept too). */
  complete: boolean
  /** Documents recorded. */
  frames: number
  /** ``gzip`` (the normal case) or ``raw`` text when the platform cannot compress. */
  encoding: 'gzip' | 'raw'
  bytes: Uint8Array
  /** ``REPLAY_COMPAT`` it was saved under (issue #562); absent before 0.4.1. */
  compat?: number
}

export type RecordingStore = KeyedStore<SavedRecording>

export const MAX_RECORDINGS = 5

export class IndexedDbRecordingStore extends IndexedDbKeyedStore<SavedRecording> {
  constructor(name = 'basketlab-live-recordings') { super(name, 'recordings', MAX_RECORDINGS) }
}

export const memoryRecordingStore = (initial: SavedRecording[] = []): RecordingStore => memoryKeyedStore(MAX_RECORDINGS, initial)
export const safeRecordingStore = (inner: RecordingStore): RecordingStore => safeKeyedStore(inner)

async function through(stream: ReadableWritablePair<Uint8Array, Uint8Array>, bytes: Uint8Array): Promise<Uint8Array> {
  const writer = stream.writable.getWriter()
  void writer.write(bytes).then(() => writer.close())
  return new Uint8Array(await new Response(stream.readable).arrayBuffer())
}

export async function encodeRecording(text: string): Promise<Pick<SavedRecording, 'encoding' | 'bytes'>> {
  const raw = new TextEncoder().encode(text)
  if (typeof CompressionStream === 'undefined') return { encoding: 'raw', bytes: raw }
  return { encoding: 'gzip', bytes: await through(new CompressionStream('gzip') as never, raw) }
}

export async function decodeRecording({ encoding, bytes }: Pick<SavedRecording, 'encoding' | 'bytes'>): Promise<string> {
  const raw = encoding === 'gzip' ? await through(new DecompressionStream('gzip') as never, bytes) : bytes
  return new TextDecoder().decode(raw)
}
