/** Where to choose the theme of the web (issue #188): light (the default), dark or the device's. */
import { Monitor, Moon, Sun } from 'lucide-react'
import SegmentedControl from '@/components/ui/SegmentedControl'
import { useTheme, type ThemePreference } from '@/lib/theme'

const OPTIONS: { value: ThemePreference; label: string; icon: typeof Sun }[] = [
  { value: 'light', label: 'Claro', icon: Sun },
  { value: 'dark', label: 'Oscuro', icon: Moon },
  { value: 'system', label: 'Sistema', icon: Monitor },
]

export default function ThemeControl() {
  const { preference, setPreference } = useTheme()
  return <SegmentedControl label="Tema" iconOnly options={OPTIONS} value={preference} onChange={setPreference} />
}
