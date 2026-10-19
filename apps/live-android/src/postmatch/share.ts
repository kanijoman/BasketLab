/** Gives the PDF to the staff (issue #409): on the tablet through the share sheet (WhatsApp, mail, Drive...), in a browser as a download. */
import { Capacitor } from '@capacitor/core'

export interface ShareDeps {
  native: boolean
  /** Writes the file to the app cache and returns its uri. */
  writeFile(name: string, base64: string): Promise<string>
  share(title: string, uri: string): Promise<void>
  download(name: string, bytes: Uint8Array): void
}

function toBase64(bytes: Uint8Array): string {
  let binary = ''
  for (let i = 0; i < bytes.length; i += 0x8000) binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000))
  return btoa(binary)
}

const defaults: ShareDeps = {
  get native() { return Capacitor.isNativePlatform() },
  async writeFile(name, base64) {
    const { Filesystem, Directory } = await import('@capacitor/filesystem')
    return (await Filesystem.writeFile({ path: name, data: base64, directory: Directory.Cache })).uri
  },
  async share(title, uri) {
    const { Share } = await import('@capacitor/share')
    await Share.share({ title, url: uri, dialogTitle: title })
  },
  download(name, bytes) {
    const url = URL.createObjectURL(new Blob([bytes as BlobPart], { type: 'application/pdf' }))
    const link = Object.assign(document.createElement('a'), { href: url, download: name })
    document.body.appendChild(link)
    link.click()
    link.remove()
    setTimeout(() => URL.revokeObjectURL(url), 10_000)
  },
}

export async function sharePdf(bytes: Uint8Array, fileName: string, title: string, deps: ShareDeps = defaults): Promise<void> {
  if (deps.native) await deps.share(title, await deps.writeFile(fileName, toBase64(bytes)))
  else deps.download(fileName, bytes)
}

/** ``informe-<own>-<rival>-<code>.pdf`` in lowercase ASCII. */
export function fileNameFor(own: string, rival: string, code: string): string {
  const slug = (text: string) => text.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')
  return `informe-${slug(own)}-${slug(rival)}-${slug(code)}.pdf`
}
