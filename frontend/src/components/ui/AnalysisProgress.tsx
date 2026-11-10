/** «Analizando partidos…» with the percentage and a bar, while a long analysis (lineups, rotations) is fetched. ``progress`` is 0–100, or null when unknown. */
export default function AnalysisProgress({ progress }: { progress: number | null | undefined }) {
  return (
    <div className="flex flex-col gap-2 card p-4 text-ink-muted text-sm">
      <div className="flex items-center gap-3">
        <span className="inline-block w-4 h-4 border-2 border-secondary-text border-t-transparent rounded-full animate-spin flex-shrink-0" />
        Analizando partidos…
        {progress != null && <span className="ml-auto text-xs text-ink-faint font-mono">{progress}%</span>}
      </div>
      {progress != null && (
        <div className="h-1.5 bg-surface-raised rounded-full overflow-hidden">
          <div className="h-full bg-secondary rounded-full transition-all duration-300" style={{ width: `${progress}%` }} />
        </div>
      )}
    </div>
  )
}
