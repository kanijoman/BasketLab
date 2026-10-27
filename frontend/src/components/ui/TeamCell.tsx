/**
 * The team of a row (issue #184, from the possessions table of #182): the FEB crest and the name in up to two lines, whole in its tooltip
 * (never cut without a hint). `teamColumn()` is the team column of every table, with its width, so no page writes its own. Guide: docs/UI.md.
 */
import { useState } from 'react'
import type { ColumnDef } from '@tanstack/react-table'
import { FEB_LOGO } from '@/lib/teamLogo'

export const TEAM_COLUMN_SIZE = 240
const COMPACT_SIZE = 42

interface Props {
  name: string
  teamId?: string | number | null
  /** The crest only (the name in its tooltip): next to a player, where the room is for the figures */
  compact?: boolean
}

export default function TeamCell({ name, teamId, compact = false }: Props) {
  const [failed, setFailed] = useState(false)
  const logo = teamId != null && teamId !== '' && !failed
  if (compact) {
    return logo
      ? <img src={FEB_LOGO(teamId)} alt={name} title={name} className="mx-auto block h-7 max-w-[42px] object-contain" onError={() => setFailed(true)} />
      : <span title={name} className="text-xs text-ink-muted">{name.slice(0, 3).toUpperCase()}</span>
  }
  return (
    <span className="flex min-w-0 items-center gap-2">
      {logo && <img src={FEB_LOGO(teamId)} alt="" className="h-5 w-5 shrink-0 rounded-sm object-contain" onError={() => setFailed(true)} />}
      <span title={name} className="line-clamp-2 break-words font-medium leading-tight text-ink">{name}</span>
    </span>
  )
}

/** The team column of a table whose rows have `team_name` (and `team_id` for the crest). */
export function teamColumn<T extends { team_name: string; team_id?: string | number | null }>(
  { compact = false }: { compact?: boolean } = {},
): ColumnDef<T, unknown> {
  return {
    id: 'team_name',
    accessorKey: 'team_name',
    header: compact ? '' : 'Equipo',
    size: compact ? COMPACT_SIZE : TEAM_COLUMN_SIZE,
    enableSorting: true,
    meta: { label: 'Equipo' },
    cell: ({ getValue, row }) => <TeamCell name={getValue() as string} teamId={row.original.team_id} compact={compact} />,
  }
}
