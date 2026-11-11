/** How the preview is made, in plain words (issue #849): what it is built from and what it is not. */
export default function HowItWorks({ poolSize }: { poolSize: number | null }) {
  return (
    <details className="card p-4 text-sm text-ink-muted">
      <summary className="cursor-pointer font-medium text-ink">Cómo se calcula</summary>
      <div className="mt-2 space-y-2">
        <p>
          <strong className="text-ink">Pronóstico.</strong> Cada equipo tiene una puntuación que se actualiza con cada resultado de la competición (contando a quién se ha ganado y con qué margen) y la
          ventaja de campo propia de la competición. De la diferencia sale la probabilidad de victoria y la diferencia de puntos que se espera.
        </p>
        <p>
          <strong className="text-ink">Escenarios.</strong> Cada partido jugado de la competición se repite con estos dos equipos: lo que hizo cada lado frente a lo que se esperaba de él, el ritmo y cómo
          salió el marcador{poolSize !== null ? ` (${poolSize} situaciones)` : ''}. Se ajustan para que den exactamente la probabilidad del pronóstico.
        </p>
        <p>
          <strong className="text-ink">Objetivos.</strong> Para cada cosa que se puede hacer (acertar, cuidar el balón, rebotear, ir a la línea, y lo mismo del rival), el objetivo es el valor desde el que
          empieza el cuarto de los partidos como este que mejor salen. Se cuenta cuántas veces se gana en ellos y cómo fue la temporada en nuestros partidos.
        </p>
        <p>
          <strong className="text-ink">Qué no es.</strong> Es una descripción de lo que pasa en los partidos, no una garantía: que un objetivo se cumpla suele ir con ganar, pero no hay evidencia de que
          forzarlo durante el partido cambie lo que viene después. Con pocos partidos jugados, la confianza es baja.
        </p>
      </div>
    </details>
  )
}
