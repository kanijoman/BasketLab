import { FEB_LOGO } from '@/pages/possessions/ScatterCard'

/** Team name with its FEB logo; wraps to two lines and keeps the full name in the tooltip (never cut silently). */
export default function TeamCell({ name, teamId }: { name: string; teamId?: string }) {
  return (
    <span className="flex items-center gap-2 min-w-0">
      {teamId && (
        <img
          src={FEB_LOGO(teamId)}
          alt=""
          className="w-5 h-5 shrink-0 object-contain rounded-sm"
          onError={e => { (e.currentTarget as HTMLImageElement).style.display = 'none' }}
        />
      )}
      <span title={name} className="font-medium text-ink leading-tight line-clamp-2 break-words">{name}</span>
    </span>
  )
}
