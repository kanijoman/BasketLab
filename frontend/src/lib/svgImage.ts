import { PAPER } from '@design/paper'

// An SVG as a PNG (issue #717, 17c): the charts of the DOCX are drawn as SVG and the document holds images. The browser draws the SVG on a canvas (white first, as a PNG with a
// transparent background goes black in some viewers) at `scale` times its size, so that it stays sharp on paper.

/** The size an SVG declares (`width`/`height`, or its `viewBox`), `null` when it declares none. */
export function svgSize(svg: string): { width: number; height: number } | null {
  const head = /<svg\b[^>]*>/.exec(svg)?.[0] ?? ''
  const width = Number(/\swidth="([\d.]+)"/.exec(head)?.[1]), height = Number(/\sheight="([\d.]+)"/.exec(head)?.[1])
  if (width > 0 && height > 0) return { width, height }
  const box = /viewBox="[\d.]+ [\d.]+ ([\d.]+) ([\d.]+)"/.exec(head)
  return box ? { width: Number(box[1]), height: Number(box[2]) } : null
}

export async function svgToPng(svg: string, scale = 2): Promise<Uint8Array> {
  const size = svgSize(svg)
  if (!size) throw new Error('El gráfico no declara su tamaño.')
  const image = new Image()
  const loaded = new Promise<void>((resolve, reject) => {
    image.onload = () => resolve()
    image.onerror = () => reject(new Error('El navegador no pudo dibujar el gráfico.'))
  })
  image.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`
  await loaded
  const canvas = document.createElement('canvas')
  canvas.width = Math.round(size.width * scale)
  canvas.height = Math.round(size.height * scale)
  const context = canvas.getContext('2d')
  if (!context) throw new Error('El navegador no puede crear la imagen del gráfico.')
  context.fillStyle = PAPER.surface
  context.fillRect(0, 0, canvas.width, canvas.height)
  context.drawImage(image, 0, 0, canvas.width, canvas.height)
  const blob = await new Promise<Blob | null>(resolve => canvas.toBlob(resolve, 'image/png'))
  if (!blob) throw new Error('El navegador no generó el PNG del gráfico.')
  return new Uint8Array(await blob.arrayBuffer())
}
