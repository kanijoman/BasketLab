/** Messages between the UI thread and the engine Web Worker. */

export type WorkerRequest =
  | { id: number; type: 'start'; payload: string }
  | { id: number; type: 'loadReplay'; payload: string }
  | { id: number; type: 'replay'; payload: number }
  | { id: number; type: 'update'; payload: string }

export type WorkerResponse =
  | { id: number; ok: true; result: unknown }
  | { id: number; ok: false; error: string }
