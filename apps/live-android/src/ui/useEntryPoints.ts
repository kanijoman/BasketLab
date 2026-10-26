/** What can open the app on a given tab from outside: a tapped reminder (issue #482) and an invitation link (issue #410). */
import { useEffect, useState } from 'react'
import { listenInviteLinks } from '../package/inviteLink'
import { capacitorReminderPlugin, onReminderTapped } from '../notify/reminders'
import type { TabId } from './useTab'

/** Returns the message of the invitation that opened the app, if any. */
export function useEntryPoints(setTab: (tab: TabId) => void): string | null {
  // a reminder of a match of a team of interest was tapped: the app opens on the list of matches
  useEffect(() => {
    let stop: () => void = () => undefined
    let gone = false
    void capacitorReminderPlugin().then(plugin => plugin && onReminderTapped(plugin, () => setTab('paquetes')).then(s => { if (gone) s(); else stop = s }))
    return () => { gone = true; stop() }
  }, [setTab])
  // an invitation link opened the app: its right is kept, the list of matches is shown and says what happened
  const [inviteNotice, setInviteNotice] = useState<string | null>(null)
  useEffect(() => listenInviteLinks(result => {
    setInviteNotice(result.ok ? `Invitación aceptada: ${result.scope}.` : result.message)
    setTab('paquetes')
  }), [setTab])
  return inviteNotice
}
