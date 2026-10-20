import type { TeamRef } from '../engine/types'

/** The package in use was prepared for another match (issue #417): the alerts about a rival that is not playing would mislead. */
interface Props {
  /** The teams FEB serves, by name. */
  match: string[]
  /** The teams the package was prepared for. */
  own: TeamRef
  rival: TeamRef
  onPackages: () => void
}

export default function PackageMismatch({ match, own, rival, onPackages }: Props) {
  return (
    <section role="alert" aria-label="Paquete de otro partido" className="notice warn">
      <p>
        <strong>Este paquete no corresponde a este partido.</strong> FEB sirve {match.join(' – ')} y el paquete está preparado para{' '}
        {own.name.trim()} – {rival.name.trim()}. Mientras no cargues el paquete correcto no se muestran alertas ni análisis.
      </p>
      <button className="secondary link-button" onClick={onPackages}>Ir a Partidos</button>
    </section>
  )
}
