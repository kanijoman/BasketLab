/** Loading screen of the engine (Pyodide takes from a second to several): the mark, the name and what is going on (issue #311). */
import markUrl from '@design/brand/live-mark.svg'

export default function Splash() {
  return (
    <main className="splash" role="status">
      <img src={markUrl} alt="" width={112} height={112} aria-hidden="true" className="splash-mark" />
      <h1>BasketLab <strong>Live</strong></h1>
      <p>Cargando motor…</p>
      <div className="splash-progress" aria-hidden="true"><span /></div>
    </main>
  )
}
