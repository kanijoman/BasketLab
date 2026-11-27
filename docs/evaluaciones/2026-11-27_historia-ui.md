# Historia de UI
Texto movido tal cual desde [UI.md](../UI.md) (27/11/2026): migraciones y transiciones ya hechas, que no son el contrato de hoy.

## Migraciones de páginas a los componentes (U5a a U5e, #192-#195, #666), historial
**Migradas (U5e, #666) — ya no queda ninguna página con controles a mano**: Inicio (las competiciones y los recientes son enlaces, `PageHeader align="center"` para el hero), Comparativas, Scouting del rival y Análisis PBP, más `Layout` (el inicio del migas es un enlace), `Sidebar` y `PlayerSelect`; la línea base del trinquete está vacía, solo vigila que no entren nuevos. **Preparación live se retiró (#667)**: la app descarga los paquetes publicados. **Migradas (U5d, #195)**: Administración (**retirada después, #724**) (partida en `pages/admin/`, un fichero por pestaña; las temporadas a ingerir son `Checkbox`, los niveles en cascada `Field`+`Select`, los botones que lanzan una descarga `Button` con `loading`) (Preparación live se retiró, #667), sin ningún control crudo: **Migradas (U5c, #194)**: IN/OUT, Combinaciones, Rotaciones y Tiros, sin controles crudos (`PageHeader`, `Tabs`, `SegmentedControl` para ver por/visualización/resultado del tiro, `IconButton` para cerrar un panel o quitar al jugador, `Button` con `loading` para Analizar). **Migradas (U5b, #193)**: Evolución, Informes y Análisis de partido (el Análisis predictivo se retiró, #852), también sin controles crudos (`Checkbox` para las series; `IconButton` con su nombre para quitar un equipo). **Migradas (U5a, #192)**: Estadísticas de equipo, de jugadores, Rankings, Posesiones y Multifase, sin ningún control crudo: `PageHeader` (su única `h1`), `Tabs` para las vistas (con el teclado), `SegmentedControl` para elegir una opción de pocas, `Field`+`Select`/`Input` para los filtros con nombre y `Button` con `aria-pressed` para lo que se activa y desactiva (fases a combinar, estadísticas de la tendencia, la del ranking).

## zonas de la web: el sistema antiguo, resumen de la transición
; la web tenía otro (`feb_zones`: `paint`, `mid_left/center/right`, `corner_left`, `wing_left`, `top_three`…) y solo el 64 % de la media pista caía en zonas equivalentes

## zonas de la web: comprobación previa a quitar el sistema antiguo
tras comprobar que los 75 ficheros de `shots/` publicados llevaban `zone_system: "engine"` y ninguna clave antigua (se abrieron con la clave abierta del manifiesto), se quitaron `LEGACY_CENTERS` y `LEGACY_ZONES`:

## PassZoneCourt: antes copiaba la burbuja
: el anillo de `PassZoneCourt` salía siempre completo porque era una copia sin el arco

## guarda de insignias: primera versión
; la primera versión de la guarda medía una insignia neutra que ningún componente dibujaba y no vio los fallos

## auditoría axe del 28/10/2026
(la auditoría de 28/10/2026 encontró 197 antes de los arreglos)
