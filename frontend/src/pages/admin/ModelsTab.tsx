/** Tab "Modelos predictivos": the technical tabs of the predictive analysis, as tabs of their own (issue #195). */
import { useState } from 'react'
import Tabs from '@/components/ui/Tabs'
import { ElasticityTab } from '../predictive/ElasticityTab'
import { ValidationTab } from '../predictive/ValidationTab'

const SUBTABS = [{ id: 'elasticity', label: 'Elasticidades' }, { id: 'validation', label: 'Validación' }] as const

export function ModelsTab() {
  const [subTab, setSubTab] = useState<(typeof SUBTABS)[number]['id']>('elasticity')
  return (
    <div className="mt-4 space-y-4">
      <Tabs label="Modelos predictivos" tabs={[...SUBTABS]} value={subTab} onChange={setSubTab} />
      <div className="bg-canvas/50 rounded-xl border border-line/50 p-6">
        {subTab === 'elasticity' && <ElasticityTab />}
        {subTab === 'validation' && <ValidationTab />}
      </div>
    </div>
  )
}
