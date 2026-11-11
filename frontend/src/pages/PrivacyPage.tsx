/**
 * Privacy policy of BasketLab Live and of this web (issue #834). Google Play asks for a public address even if the app is only for the staff: it is part of the store listing,
 * so the route (`/privacidad`) must not change. What it says is checked against the code (`PrivacyPage.test.tsx`: every host the app talks to is named here).
 */
import { ExternalLink } from 'lucide-react'
import PageTransition from '@/components/ui/PageTransition'
import PageHeader from '@/components/ui/PageHeader'
import Card from '@/components/ui/Card'

const UPDATED = '11 de noviembre de 2026'
const ISSUES_URL = 'https://github.com/kanijoman/BasketLab/issues'

/** Who the app asks for what: nothing the person types, only public data and the packages of the matches. */
const HOSTS: { host: string; who: string; what: string }[] = [
  { host: 'raw.githubusercontent.com', who: 'GitHub', what: 'los paquetes de preparación de partido que se publican para el cuerpo técnico' },
  { host: 'github.com', who: 'GitHub', what: 'comprobar si hay una versión nueva (solo la app que se instala desde GitHub; la de Google Play se actualiza desde Google Play y no lo hace)' },
  { host: 'baloncestoenvivo.feb.es', who: 'Federación Española de Baloncesto', what: 'el calendario y la página del partido en directo' },
  { host: 'intrafeb.feb.es', who: 'Federación Española de Baloncesto', what: 'las jugadas y las estadísticas del partido en directo' },
  { host: 'imagenes.feb.es', who: 'Federación Española de Baloncesto', what: 'los escudos de los equipos' },
  { host: 'streaming.optimalwayconsulting.com', who: 'servicios de estadísticas de la Federación de Baloncesto de Castilla y León', what: 'el partido en directo de sus competiciones' },
  { host: 'msstats.optimalwayconsulting.com', who: 'servicios de estadísticas de la Federación de Baloncesto de Castilla y León', what: 'las estadísticas de sus partidos' },
  { host: 'esb.optimalwayconsulting.com', who: 'servicios de estadísticas de la Federación de Baloncesto de Castilla y León', what: 'el calendario de sus competiciones' },
]

const ON_DEVICE = [
  'los paquetes de partido que descargas',
  'tus equipos de interés, los filtros y los recordatorios que eliges',
  'los ajustes (apariencia, modo de alertas)',
  'la valoración de las alertas (seguida, descartada o ya hecha), por partido, para que el cuerpo técnico pueda revisarla',
  'las invitaciones que pegas o abres desde un enlace',
  'un registro corto de la sesión, que sirve para explicar un problema',
]

export default function PrivacyPage() {
  return (
    <PageTransition>
      <div className="mx-auto max-w-3xl space-y-4">
        <PageHeader title="Política de privacidad" subtitle={`BasketLab Live (app Android) y esta web · actualizada el ${UPDATED}`} />

        <Card title="Qué datos usa la app">
          <div className="space-y-2 text-sm text-ink">
            <p>
              BasketLab Live es una herramienta para el cuerpo técnico de un equipo de baloncesto: durante un partido muestra alertas y propuestas
              que se calculan en el propio dispositivo. Usa datos públicos de las competiciones (calendarios, resultados, estadísticas y jugadas de
              los partidos, con los nombres que publican las federaciones) y los paquetes de preparación de partido que se publican para el equipo.
            </p>
            <p>No hay cuentas ni registro, y la app no te pide ningún dato personal.</p>
          </div>
        </Card>

        <Card title="Qué se guarda en tu dispositivo">
          <div className="space-y-2 text-sm text-ink">
            <p>La app guarda en el dispositivo, y solo ahí:</p>
            <ul className="list-disc space-y-1 pl-5">{ON_DEVICE.map(item => <li key={item}>{item}</li>)}</ul>
            <p>
              Esta información no se envía a ningún servidor nuestro. La ves y la borras desinstalando la app o borrando sus datos desde los ajustes de Android.
              Un informe o una grabación sale del dispositivo solo si tú lo compartes (con la hoja de compartir de Android).
            </p>
          </div>
        </Card>

        <Card title="Con quién se comunica">
          <div className="space-y-2 text-sm text-ink">
            <p>
              La app solo hace peticiones de lectura por internet (HTTPS) a estos servicios. No les envía nada que hayas escrito ni lo que se guarda en el
              dispositivo; como en cualquier petición, el servicio que responde ve la dirección IP de la conexión y se rige por su propia política.
            </p>
            <ul className="space-y-1">
              {HOSTS.map(h => (
                <li key={h.host}><strong className="font-semibold">{h.host}</strong> ({h.who}): {h.what}.</li>
              ))}
            </ul>
          </div>
        </Card>

        <Card title="Permisos de la app">
          <ul className="list-disc space-y-1 pl-5 text-sm text-ink">
            <li><strong className="font-semibold">Internet y estado de la red</strong>: para descargar los paquetes y leer el partido en directo.</li>
            <li><strong className="font-semibold">Notificaciones, alarmas y arranque</strong>: para los recordatorios de partido de tus equipos de interés, que se programan en el dispositivo (sin servidor ni mensajes push) y se mantienen si lo reinicias. Puedes desactivarlos en la app o en Android.</li>
            <li><strong className="font-semibold">Mantener la pantalla encendida</strong>: durante el modo en directo, para que la tablet no se apague en pleno partido.</li>
          </ul>
          <p className="mt-2 text-sm text-ink-muted">La app no pide ubicación, cámara, micrófono, contactos ni acceso al almacenamiento del dispositivo.</p>
        </Card>

        <Card title="Anuncios y seguimiento">
          <p className="text-sm text-ink">
            La app no tiene anuncios, ni analítica, ni seguimiento, ni herramientas de medición de terceros, y no vende ni comparte datos. Esta web tampoco usa
            cookies de seguimiento: guarda en tu navegador solo tus preferencias (tema, competiciones recientes, equipo elegido). El alojamiento de la web
            (Vercel) puede registrar la dirección IP de las visitas, como cualquier servidor.
          </p>
        </Card>

        <Card title="Cambios">
          <p className="text-sm text-ink">Si esta política cambia, se actualiza en esta misma dirección y se cambia la fecha de arriba.</p>
        </Card>

        <Card title="Contacto">
          <p className="text-sm text-ink">
            Para cualquier duda sobre tus datos o esta política, escríbenos abriendo un aviso en{' '}
            <a href={ISSUES_URL} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-accent-text underline">
              GitHub <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
              <span className="sr-only">(se abre en una pestaña nueva)</span>
            </a>.
          </p>
        </Card>
      </div>
    </PageTransition>
  )
}
