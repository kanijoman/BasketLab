/** The mark and the name of the app at the top of the screen (issue #311). */
import markUrl from '@design/brand/live-mark.svg'

export default function BrandHeader() {
  return (
    <header className="brand-header">
      <img src={markUrl} alt="" width={28} height={28} aria-hidden="true" />
      <span className="brand-name">BasketLab <strong>Live</strong></span>
    </header>
  )
}
