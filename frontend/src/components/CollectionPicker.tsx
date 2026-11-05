/**
 * The four selectors of a competition (issue #761): Ámbito → Temporada → Competición → Grupo, each filtered by the previous ones (`lib/collectionPicker`).
 * All four are shown, the group too when it is the only one (it names the phase: «Liga Regular») unless it has nothing to say (no phase, no group); in `compact` mode (the header) every level with a single option is hidden. It reports the resolved selection and its collection.
 */
import { Select } from '@/components/ui/Field'
import type { CollectionInfo } from '@/api/client'
import { pickCollection, type Selection } from '@/lib/collectionPicker'

interface Props {
  list: CollectionInfo[]
  value: Selection
  onChange: (selection: Required<Selection>, collection: CollectionInfo | null) => void
  compact?: boolean
}

export default function CollectionPicker({ list, value, onChange, compact = false }: Props) {
  const picker = pickCollection(list, value)
  const levels: { key: keyof Selection; label: string; options: string[]; always: boolean }[] = [
    { key: 'ambito', label: 'Ámbito', options: picker.ambitos, always: true },
    { key: 'season', label: 'Temporada', options: picker.seasons, always: true },
    { key: 'competition', label: 'Competición', options: picker.competitions, always: true },
    { key: 'group', label: 'Grupo', options: picker.groups, always: true },
  ]
  function change(key: keyof Selection, next: string) {
    const picked = pickCollection(list, { ...picker.selection, [key]: next })
    onChange(picked.selection, picked.collection)
  }
  return (
    <>
      {levels.filter(l => l.options.length > 1 || (l.always && !compact && l.options.some(Boolean))).map(l => (
        <label key={l.key} className={compact ? 'min-w-0' : 'flex min-w-0 flex-col gap-1 text-xs font-medium text-ink-muted'}>
          {!compact && l.label}
          <Select
            aria-label={l.label}
            value={picker.selection[l.key]}
            onChange={e => change(l.key, e.target.value)}
            options={l.options.map(o => ({ value: o, label: o || '—' }))}
            className={compact ? 'max-w-[10rem] truncate py-1 text-xs' : undefined}
          />
        </label>
      ))}
    </>
  )
}
