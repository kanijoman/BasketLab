/**
 * The navigation of a collection (issue #191, U4): ONE definition for the sidebar, the menu of the phone and the cards of the summary.
 * Pages are grouped by what the staff does with them. `subPath` is the route under `/:collection` ('' is the summary); a test keeps this list
 * and the routes of App.tsx equal, so a page cannot be added without its place in the menu.
 */
import type { ComponentType } from 'react'
import {
  Activity, ArrowLeftRight, BarChart2, BrainCircuit, ClipboardList, FileSearch, FileText, Layers, LayoutDashboard, Microscope, RotateCcw,
  Scale, Swords, Target, TrendingUp, Trophy, Users, Users2,
} from 'lucide-react'

type Icon = ComponentType<{ className?: string }>

export interface NavItem {
  subPath: string
  /** Name in the menu */
  label: string
  /** Title of its card in the summary (defaults to the label) */
  title?: string
  description: string
  icon: Icon
}

export interface NavGroup {
  label: string
  items: NavItem[]
}

export const SUMMARY: NavItem = { subPath: '', label: 'Resumen', description: 'Cifras clave de la competición y acceso a todos los módulos', icon: LayoutDashboard }

export const NAV_GROUPS: NavGroup[] = [
  { label: 'Equipos', items: [
    { subPath: 'teams', label: 'Equipo', title: 'Estadísticas de equipo', description: 'Básicas y avanzadas con cuartiles y tendencias', icon: BarChart2 },
    { subPath: 'comparativas', label: 'Comparativas', description: 'Local vs visitante, ganados vs perdidos y un tramo vs el resto', icon: Scale },
    { subPath: 'possessions', label: 'Posesiones', description: 'Ritmo, OER/DER y análisis de posesiones', icon: Activity },
    { subPath: 'pbp', label: 'Análisis pbp', description: 'Lo que añade el play-by-play: puntos por origen, por cuarto, situaciones y efecto de los tiempos muertos', icon: Microscope },
    { subPath: 'multiphase', label: 'Multifase', title: 'Estadísticas multifase', description: 'Totales acumulados entre las fases de la temporada que elijas', icon: Layers },
    { subPath: 'evolution', label: 'Evolución', title: 'Evolución temporal', description: 'Progresión de métricas a lo largo de la temporada', icon: TrendingUp },
  ] },
  { label: 'Jugadores', items: [
    { subPath: 'players', label: 'Individual', title: 'Estadísticas individuales', description: 'Jugadores con radar, comparativa y trends', icon: Users },
    { subPath: 'rankings', label: 'Rankings', description: 'Clasificación de jugadores por cualquier métrica', icon: Trophy },
    { subPath: 'shots', label: 'Gráficos de tiro', description: 'Mapa de calor FIBA interactivo por zonas', icon: Target },
    { subPath: 'inout', label: 'IN/OUT', description: 'Impacto por jugador dentro y fuera de la cancha', icon: ArrowLeftRight },
    { subPath: 'lineups', label: 'Combinaciones', description: 'Mejores y peores combinaciones de jugadores por estadística', icon: Users2 },
    { subPath: 'rotaciones', label: 'Rotaciones', title: 'Análisis de rotaciones', description: 'Distribución de minutos por jugadora, titularidades y amplitud de la rotación', icon: RotateCcw },
  ] },
  { label: 'Partido', items: [
    { subPath: 'matches', label: 'Análisis de partido', description: 'Un partido concreto: marcador y comparativa de estadísticas de los dos equipos', icon: Swords },
    { subPath: 'predictive', label: 'Análisis predictivo', description: 'Elasticidades Ridge, Monte Carlo y predicción de partido', icon: BrainCircuit },
  ] },
  { label: 'Live', items: [
    { subPath: 'scouting-rival', label: 'Scouting del rival', description: 'PDF de cualquier equipo con lo que ve el motor: claves, jugadoras, zonas y plan', icon: FileSearch },
  ] },
  { label: 'Informes', items: [
    { subPath: 'report', label: 'Informe semanal', description: 'Report builder con PDF y DOCX exportable', icon: FileText },
    { subPath: 'team-report', label: 'Informe de equipo', description: 'Análisis propio por reglas · PDF (en FBCYL también scouting del rival; en FEB, usa Scouting del rival)', icon: ClipboardList },
  ] },
]

export const NAV_ITEMS: NavItem[] = [SUMMARY, ...NAV_GROUPS.flatMap(g => g.items)]
