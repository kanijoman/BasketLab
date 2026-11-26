/**
 * The navigation of a collection (issue #191, U4): ONE definition for the sidebar, the menu of the phone and the cards of the summary.
 * Pages are grouped by what the staff does with them. `subPath` is the route under `/:collection` ('' is the summary); a test keeps this list
 * and the routes of App.tsx equal, so a page cannot be added without its place in the menu.
 */
import type { ComponentType } from 'react'
import type { Dataset } from '@/datasource/switch'
import {
  Activity, ArrowLeftRight, BarChart2, ClipboardList, Crosshair, FileSearch, FileText, Layers, LayoutDashboard, ListOrdered, Microscope, RotateCcw,
  Scale, Share2, Swords, Target, TrendingUp, Trophy, Users, Users2,
} from 'lucide-react'

type Icon = ComponentType<{ className?: string }>

/** A page that needs a section of the publication (`web-data`) for the competition: without it the page is hidden (issue #780). `dataset` is its switch (`datasource/switch`). */
export interface PageRequirement {
  section: Section
  dataset: Dataset
}

/** The sections of a competition in the manifest of `web-data` (what the exporter publishes; docs/ARCHITECTURE.md): a page needs one of them (#1100). */
export type Section = 'rows' | 'derived' | 'shots' | 'rotations' | 'matches' | 'possessions' | 'lineups' | 'inout' | 'assist_connections' | 'calendar' | 'reports'

const needs = (section: Section, dataset: Dataset): PageRequirement => ({ section, dataset })

export interface NavItem {
  subPath: string
  /** Name in the menu */
  label: string
  /** Title of its card in the summary (defaults to the label) */
  title?: string
  description: string
  icon: Icon
  /** Hidden until the competition has this section published. */
  requires?: PageRequirement
}

export interface NavGroup {
  label: string
  items: NavItem[]
}

/** The pages of the forecast need the calendar of the competition to be published. */
const CALENDAR = needs('calendar', 'forecast')

export const SUMMARY: NavItem = { subPath: '', label: 'Resumen', description: 'Cifras clave de la competición y acceso a todos los módulos', icon: LayoutDashboard }

export const NAV_GROUPS: NavGroup[] = [
  { label: 'Equipos', items: [
    { subPath: 'teams', label: 'Equipo', title: 'Estadísticas de equipo', description: 'Básicas y avanzadas con cuartiles y tendencias', icon: BarChart2, requires: needs('rows', 'team-stats') },
    { subPath: 'comparativas', label: 'Comparativas', description: 'Local vs visitante, ganados vs perdidos y un tramo vs el resto', icon: Scale, requires: needs('rows', 'team-comparison') },
    { subPath: 'possessions', label: 'Posesiones', description: 'Ritmo, OER/DER y análisis de posesiones', icon: Activity, requires: needs('possessions', 'possessions') },
    { subPath: 'pbp', label: 'Análisis pbp', description: 'Lo que añade el play-by-play: puntos por origen, por cuarto, situaciones y efecto de los tiempos muertos', icon: Microscope, requires: needs('derived', 'pbp') },
    { subPath: 'multiphase', label: 'Multifase', title: 'Estadísticas multifase', description: 'Totales acumulados entre las fases de la temporada que elijas', icon: Layers, requires: needs('rows', 'multi-phase') },
    { subPath: 'evolution', label: 'Evolución', title: 'Evolución temporal', description: 'Progresión de métricas a lo largo de la temporada', icon: TrendingUp, requires: needs('rows', 'evolution') },
  ] },
  { label: 'Jugadores', items: [
    { subPath: 'players', label: 'Individual', title: 'Estadísticas individuales', description: 'Jugadores con radar, comparativa y trends', icon: Users, requires: needs('rows', 'player-stats') },
    { subPath: 'rankings', label: 'Rankings', description: 'Clasificación de jugadores por cualquier métrica', icon: Trophy, requires: needs('rows', 'player-stats') },
    { subPath: 'shots', label: 'Gráficos de tiro', description: 'Mapa de calor FIBA interactivo por zonas', icon: Target, requires: needs('shots', 'shots') },
    { subPath: 'inout', label: 'IN/OUT', description: 'Impacto por jugador dentro y fuera de la cancha', icon: ArrowLeftRight, requires: needs('inout', 'inout') },
    { subPath: 'lineups', label: 'Combinaciones', description: 'Mejores y peores combinaciones de jugadores por estadística', icon: Users2, requires: needs('lineups', 'lineups') },
    { subPath: 'rotaciones', label: 'Rotaciones', title: 'Análisis de rotaciones', description: 'Distribución de minutos por jugadora, titularidades y amplitud de la rotación', icon: RotateCcw, requires: needs('rotations', 'rotations') },
    { subPath: 'conexiones', label: 'Conexiones', title: 'Conexiones de asistencia', description: 'Quién da las asistencias, quién las recibe y desde qué zonas anota con y sin asistencia', icon: Share2, requires: { section: 'assist_connections', dataset: 'assist-connections' } },
  ] },
  { label: 'Partido', items: [
    { subPath: 'previa', label: 'Previa del partido', description: 'Elige tu equipo y un partido de su calendario: pronóstico, escenarios y objetivos del partido', icon: Crosshair, requires: CALENDAR },
    { subPath: 'matches', label: 'Análisis de partido', description: 'Un partido concreto: marcador y comparativa de estadísticas de los dos equipos', icon: Swords, requires: needs('matches', 'matches') },
  ] },
  { label: 'Competición', items: [
    { subPath: 'simulacion', label: 'Simulación de la liga', description: 'Cómo puede acabar la liga: puestos finales sobre el calendario real, con las líneas de corte que tú marques', icon: ListOrdered, requires: CALENDAR },
  ] },
  { label: 'Live', items: [
    { subPath: 'scouting-rival', label: 'Scouting del rival', description: 'PDF de cualquier equipo con lo que ve el motor: claves, jugadoras, zonas y plan', icon: FileSearch, requires: needs('reports', 'scouting') },
  ] },
  { label: 'Informes', items: [
    { subPath: 'report', label: 'Informe semanal', description: 'Report builder con PDF y DOCX exportable', icon: FileText, requires: needs('rows', 'weekly-report') },
    { subPath: 'team-report', label: 'Informe de equipo', description: 'Análisis propio por reglas · PDF (para un rival, usa Scouting del rival)', icon: ClipboardList, requires: needs('reports', 'team-report') },
  ] },
]

export const NAV_ITEMS: NavItem[] = [SUMMARY, ...NAV_GROUPS.flatMap(g => g.items)]
