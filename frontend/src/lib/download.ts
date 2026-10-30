/** Hands a file to the browser as a download (a link to an object URL clicked once). */
export function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const a = Object.assign(document.createElement('a'), { href: url, download: filename })
  a.click()
  // Releasing the URL right after the click cancels the download in some browsers.
  setTimeout(() => URL.revokeObjectURL(url), 60_000)
}
