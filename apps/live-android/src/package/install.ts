/** Shared by the file import and the download: validate with the engine, then keep the package on the device. */
import type { EngineApi } from '../engine/client'
import type { PackageStore } from './storage'
import { summarizePackage, type PackageSummary } from './summary'

export async function installPackage(engine: EngineApi, store: PackageStore, plaintext: string): Promise<PackageSummary> {
  await engine.start(plaintext) // the engine validates checksum and schema version
  await store.save({ plaintext, savedAt: new Date().toISOString() })
  return summarizePackage(plaintext)
}
