/**
 * AdminPage — panel de administración de colecciones y descarga de datos.
 *
 * Tab 1 "Colecciones": lista las colecciones disponibles en MongoDB con opción de eliminar.
 * Tab 2 "Descargar FEB": dropdowns en cascada + scraping con barra de progreso.
 * Tab 3 "Descargar FBCYL": ídem para FBCYL.
 * Tab 4 "Histórico": temporadas pasadas FEB en la colección HISTORICAL.
 * Tab 5 "Modelos predictivos": elasticidades y validación.
 * Cada pestaña vive en `./admin/` (issue #195).
 */
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ChevronRight } from 'lucide-react'
import PageTransition from '@/components/ui/PageTransition'
import PageHeader from '@/components/ui/PageHeader'
import Tabs from '@/components/ui/Tabs'
import AdminKeyField from '@/components/AdminKeyField'
import { CollectionsTab } from './admin/CollectionsTab'
import { FBCYLDownloadTab, FEBDownloadTab } from './admin/DownloadTabs'
import { HistoricalTab } from './admin/HistoricalTab'
import { ModelsTab } from './admin/ModelsTab'

type Tab = 'collections' | 'feb' | 'fbcyl' | 'historical' | 'models'

const TABS: { id: Tab; label: string }[] = [
  { id: 'collections', label: 'Colecciones' },
  { id: 'feb',         label: 'Descargar FEB' },
  { id: 'fbcyl',       label: 'Descargar FBCYL' },
  { id: 'historical',  label: 'Histórico' },
  { id: 'models',      label: 'Modelos predictivos' },
]

export default function AdminPage() {
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState<Tab>('collections')

  return (
    <PageTransition>
      <div className="space-y-6 max-w-3xl mx-auto">
        <PageHeader title="Administración" subtitle="Gestión de colecciones y descarga de datos" />

        <AdminKeyField />

        <Tabs label="Secciones de administración" tabs={TABS} value={activeTab} onChange={setActiveTab} />

        <div>
          {activeTab === 'collections' && <CollectionsTab onOpen={name => navigate(`/${encodeURIComponent(name)}`)} />}
          {activeTab === 'feb'         && <FEBDownloadTab />}
          {activeTab === 'fbcyl'       && <FBCYLDownloadTab />}
          {activeTab === 'historical'  && <HistoricalTab />}
          {activeTab === 'models'      && <ModelsTab />}
        </div>

        <div className="pt-4 border-t border-line text-xs text-ink-faint space-y-1">
          <p><span className="font-medium">FEB:</span> Descarga partidos de las ligas nacionales FEB (L.F.2, EBA, etc.).</p>
          <p><span className="font-medium">FBCYL:</span> Descarga partidos de las ligas de Castilla y León.</p>
          <p><span className="font-medium">Histórico:</span> Descarga temporadas pasadas en la colección unificada HISTORICAL para modelos predictivos.</p>
          <p><span className="font-medium">Modelos:</span> Entrenamiento Ridge/GBM y validación walk-forward de los modelos predictivos.</p>
          <p className="flex items-center gap-1">
            <ChevronRight className="w-3 h-3" aria-hidden="true" />
            Los datos nuevos incluyen metadatos de competición para análisis cruzado futuro.
          </p>
        </div>
      </div>
    </PageTransition>
  )
}
