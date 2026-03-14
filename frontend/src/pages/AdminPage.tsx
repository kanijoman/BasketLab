/**
 * AdminPage — Fase 5
 * Panel de administración: gestión de colecciones, scraper con WebSocket y control de usuarios.
 * Requiere rol "admin".
 */
import { Settings } from 'lucide-react'
import PageTransition from '@/components/ui/PageTransition'

export default function AdminPage() {
  return (
    <PageTransition>
      <div className="space-y-4">
        <div>
          <h1 className="text-2xl font-bold text-ink-primary">Administración</h1>
          <p className="text-ink-secondary text-sm mt-1">Gestión de colecciones y scraper</p>
        </div>
        <div className="card p-10 flex flex-col items-center gap-3 text-center">
          <Settings className="w-10 h-10 text-ink-muted opacity-60" />
          <p className="text-ink-primary font-medium">En desarrollo — Fase 5</p>
          <p className="text-ink-secondary text-sm max-w-sm">
            Panel de colecciones con historial de scraping, lanzamiento de nuevas descargas
            con progreso en tiempo real (WebSocket) y gestión de usuarios/roles.
          </p>
        </div>
      </div>
    </PageTransition>
  )
}
