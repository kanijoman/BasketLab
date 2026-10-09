import { describe, expect, it } from 'vitest'
import { EngineClient } from './client'
import type { WorkerRequest, WorkerResponse } from './protocol'

class FakeWorker {
  sent: WorkerRequest[] = []
  terminated = false
  onmessage: ((e: { data: WorkerResponse }) => void) | null = null
  onerror: ((e: { message: string }) => void) | null = null
  postMessage(msg: WorkerRequest) { this.sent.push(msg) }
  terminate() { this.terminated = true }
  reply(msg: WorkerResponse) { this.onmessage?.({ data: msg }) }
}

function setup() {
  const worker = new FakeWorker()
  return { worker, client: new EngineClient(() => worker as never) }
}

describe('EngineClient', () => {
  it('sends a typed request and resolves with the matching response', async () => {
    const { worker, client } = setup()
    const p = client.start('PKG')
    expect(worker.sent[0]).toMatchObject({ type: 'start', payload: 'PKG' })
    worker.reply({ id: worker.sent[0].id, ok: true, result: { team: { id: '1', name: 'A' } } })
    await expect(p).resolves.toMatchObject({ team: { name: 'A' } })
  })

  it('correlates concurrent requests by id, whatever the order of the replies', async () => {
    const { worker, client } = setup()
    const a = client.replay(10)
    const b = client.replay(20)
    worker.reply({ id: worker.sent[1].id, ok: true, result: 'B' })
    worker.reply({ id: worker.sent[0].id, ok: true, result: 'A' })
    await expect(a).resolves.toBe('A')
    await expect(b).resolves.toBe('B')
  })

  it('rejects with the engine error message', async () => {
    const { worker, client } = setup()
    const p = client.start('bad')
    worker.reply({ id: worker.sent[0].id, ok: false, error: 'Package checksum mismatch' })
    await expect(p).rejects.toThrow('Package checksum mismatch')
  })

  it('fails every pending request when the worker crashes', async () => {
    const { worker, client } = setup()
    const p = client.replay(5)
    worker.onerror?.({ message: 'boom' })
    await expect(p).rejects.toThrow(/boom/)
  })

  it('terminates the worker on dispose and rejects later calls', async () => {
    const { worker, client } = setup()
    client.dispose()
    expect(worker.terminated).toBe(true)
    await expect(client.replay(1)).rejects.toThrow(/disposed/i)
  })

  it('ignores responses without a pending request', () => {
    const { worker } = setup()
    expect(() => worker.reply({ id: 999, ok: true, result: null })).not.toThrow()
  })
})
