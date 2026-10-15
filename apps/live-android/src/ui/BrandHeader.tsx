/** The mark and the name of the app at the top of the screen (issue #311), and the quick switch between light and dark (issue #322). */
import { Moon, Sun } from 'lucide-react'
import markUrl from '@design/brand/live-mark.svg'
import { useTheme } from './useTheme'

export default function BrandHeader() {
  const { theme, toggle } = useTheme()
  const next = theme === 'dark' ? 'claro' : 'oscuro'
  return (
    <header className="brand-header">
      <img src={markUrl} alt="" width={28} height={28} aria-hidden="true" />
      <span className="brand-name">BasketLab <strong>Live</strong></span>
      <button type="button" className="icon-button secondary theme-toggle" aria-label={`Cambiar a modo ${next}`} onClick={toggle}>
        {theme === 'dark' ? <Sun size={20} aria-hidden="true" /> : <Moon size={20} aria-hidden="true" />}
      </button>
    </header>
  )
}
