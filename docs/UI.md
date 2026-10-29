# UI de la web — sistema de diseño

Guía de la épica #187 para la web (`frontend/`). Tokens, marca y tema son de la suite (`design/`, ver [design/README.md](../design/README.md)); los componentes viven en `frontend/src/components/ui` (la app live tiene los suyos con los mismos tokens).

## Principios
- **Tema claro por defecto**, oscuro o del sistema (selector en la cabecera). Todo se prueba en los dos.
- **Ningún color suelto**: solo el vocabulario del preset. Lo vigila `frontend/src/designTokens.test.ts` (hex, `rgb()`, paleta de Tailwind, nombres que no existen, `dark:`, texto blanco sin relleno de color).
- **Ningún control a mano** en una página nueva: los componentes de abajo. Lo vigila `frontend/src/rawControls.test.ts` (trinquete: ningún fichero suma `<button>`, `<select>`, `<input>` ni `<h1>` crudos; al migrar una página, se baja su línea base). **Migradas (U5b, #193)**: Evolución, Informes, Análisis de partido y Análisis predictivo, también sin controles crudos (`Checkbox` para las series; `IconButton` con su nombre para quitar un equipo; el selector de fuente de datos y el de temporada del modelo, `SegmentedControl`). **Migradas (U5a, #192)**: Estadísticas de equipo, de jugadores, Rankings, Posesiones y Multifase, sin ningún control crudo: `PageHeader` (su única `h1`), `Tabs` para las vistas (con el teclado), `SegmentedControl` para elegir una opción de pocas, `Field`+`Select`/`Input` para los filtros con nombre y `Button` con `aria-pressed` para lo que se activa y desactiva (fases a combinar, estadísticas de la tendencia, la del ranking).
- Textos en español; código y comentarios en inglés.

## Vocabulario de color (preset de `design/`)
| Clase | Para |
|---|---|
| `canvas` · `surface` · `surface-raised` · `line` | fondo de página · tarjetas · hover, inputs · bordes |
| `ink` · `ink-muted` · `ink-faint` | texto · secundario · pistas y placeholders |
| `accent` · `accent-text` · `accent-solid`/`accent-hover` + `accent-ink` | naranja de marca: selección y acciones · texto naranja · botón relleno y su texto |
| `secondary` · `secondary-text` | azul: la otra liga (FBCYL), enlaces, información |
| `ok` · `warn` · `bad` | **datos** buenos, al límite y malos (nunca la urgencia de un aviso) |
| `q1`–`q4` (`table-cell-q*`) · `chart-1`–`8` | cuartiles (Q1 verde … Q4 rojo) · series de gráfico |
| `focus` | anillo de foco |

Gráficos (recharts, SVG): `useChartTheme()` de `lib/chartTheme.ts` (colores ya resueltos del tema activo; nunca `var(--x)` en un atributo SVG, una exportación lo perdería).

**Exportaciones** (`ExportButton`): PNG y PDF salen **en el tema activo** (#617): la captura con el fondo del tema, el gráfico exportado desde su SVG sobre ese fondo (no transparente) y cada página del PDF con el fondo, el título (`--text`) y la fecha (`--text-muted`) del tema; en claro, el PDF es claro de borde a borde. Un color para jsPDF también sale de los tokens: el guarda rechaza `setFillColor(13, 17, 23)` y similares.

## Componentes (`components/ui`)
| Componente | Cuándo | Ejemplo |
|---|---|---|
| `PageHeader` | la cabecera de cada página: su único `h1`, el subtítulo (la competición) y las acciones | `<PageHeader title="Estadísticas de Equipo" subtitle={collection.label} actions={<ExportButton …/>} />` |
| `Button` | toda acción; `variant` `primary` (una por vista) · `secondary` · `ghost` · `danger`; `size="sm"`; `icon`; `loading` para lo que tarda (deshabilita y lo dice) | `<Button icon={Download} loading={busy} onClick={…}>Generar DOCX</Button>` |
| `IconButton` | acción con solo icono; `label` es obligatorio (nombre y tooltip) | `<IconButton icon={Trash2} label="Eliminar colección" variant="danger" />` |
| `Field` + `Input` / `Select` | formularios: `Field` pone la etiqueta, la ayuda y el error con sus `aria-*`; `Select` es el nativo con chevron (`options` o `<option>`) | `<Field label="Temporada"><Select value={s} onChange={…} options={seasons} /></Field>` |
| `Checkbox` | una opción que se activa o desactiva (las series de un gráfico, un filtro): la caja con su texto, que también la activa | `<Checkbox label="Por partido" checked={on} onChange={e => setOn(e.target.checked)} />` |
| `SegmentedControl` | elegir una de pocas opciones **dentro de una vista** (local/visitante, básico/avanzado, tema); `iconOnly` | `<SegmentedControl label="Campo" options={…} value={v} onChange={setV} />` |
| `Tabs` | cambiar **la vista entera** de una página; `trailing` para un control al final de la fila | `<Tabs label="Vistas" tabs={TABS} value={tab} onChange={setTab} />` |
| `Card` | un panel; `title` (h2), `actions`, `padding="none"` para tablas y gráficos a sangre | `<Card title="Estadísticas por zona">…</Card>` |
| `EmptyState` | no hay nada que enseñar: qué falta y qué hacer | `<EmptyState icon={Users} title="Sin combinaciones" description="Selecciona un equipo…" />` |
| `Spinner` · `Skeleton` | carga: `Spinner` lo anuncia (`role="status"`); `Skeleton` dibuja la forma (oculto al lector) | `<Spinner label="Generando DOCX" />` · `<Skeleton lines={3} />` |
| `Badge` · `StatCard` | etiqueta y cifra destacada con un **tono** del sistema (`components/ui/tone.ts`: `neutral`, `accent`, `secondary`, `ok`, `warn`, `bad`) | `<Badge tone="secondary">FBCYL</Badge>` · `<StatCard label="OER" value="107" tone="ok" />` |
| `DataTable` | tablas con orden, búsqueda, cuartiles, columna fija y cabeceras agrupadas; `density` (`compact`/`normal`/`comfortable`), `emptyMessage`, `Spinner` al cargar y **en un móvil (< 640 px) cada fila es una tarjeta** (la primera columna de título y el resto «etiqueta: valor»; la etiqueta es la cabecera o `meta.label`) | `<DataTable columns={cols} data={rows} quartiles={q} density="compact" />` |
| `teamColumn()` · `TeamCell` | **la columna de equipo de cualquier tabla** (#184): logo FEB, nombre en dos líneas como mucho y entero en el tooltip, 240 px; `{ compact: true }` solo el logo, junto a un jugador. Ninguna página escribe la suya (lo vigila `TeamCell.test.tsx`) | `[teamColumn<TeamStat>(), ...cols]` |

**La pista de tiro (U6, #196)** no tiene colores propios: suelo, líneas, aro, calor, aciertos y fallos salen del tema activo (`useChartTheme`) y las zonas se colorean con `zoneColours(tema)` (`ok`/`warn`/`bad` según el rating contra la liga); la tinta sobre una burbuja es `--on-data`.

**Informe de equipo y scouting del rival (#627)**: el scouting de un rival tiene su página completa («Scouting del rival», solo FEB). «Informe de equipo» es el análisis propio y, en FEB, enlaza a ella; solo en FBCYL conserva el modo «Scouting rival» (versión por reglas) hasta que el scouting completo llegue a esa liga.

## Accesibilidad (U7, #197)
Objetivo: WCAG 2.1 AA. **Contraste**: `designTokens.test.ts` mide en los dos temas el texto (`--text`, `-muted`, `-faint`) sobre la página, las tarjetas, las filas con hover y las insignias, el texto naranja sobre el tinte del enlace activo y la tinta de los botones rellenos (`--accent-ink` sobre `--accent-solid`, blanco sobre `--secondary-solid`); el azul de un botón relleno es `bg-secondary-solid`, nunca `bg-secondary` con texto blanco. **Controles con nombre**: todo `select`/`input` lleva su etiqueta (`Field` o `aria-label`); las tablas son una región enfocable (`role="region"`, `tabIndex=0`, `ariaLabel`) para poder desplazarlas con el teclado. **Teclado**: primer enlace «Saltar al contenido» (`main#contenido`) y anillo de foco `focus` en todo. **Movimiento**: con `prefers-reduced-motion` ninguna animación ni transición pasa de 0,01 ms (CSS global y `MotionConfig reducedMotion="user"`). **Pruebas**: `e2e/a11y.spec.ts` pasa axe (reglas WCAG 2.0/2.1 A y AA) sobre 11 páginas en claro y oscuro a 390 y 1280 px sin violaciones (la auditoría de 28/10/2026 encontró 197 antes de los arreglos) y comprueba el movimiento reducido; `e2e/visual.spec.ts` captura seis páginas en los dos temas a 390, 768 y 1280 px y el CI las guarda como artefacto `web-visual-captures` (sin comparar todavía: las líneas base con `toHaveScreenshot` se generarán en Linux cuando las páginas se estabilicen).

## Shell y navegación (U4, #191)
`lib/nav.ts` es la **única definición de las páginas de una competición**, en grupos (Equipos, Jugadores, Partido, Live, Informes) con icono y descripción; la usan la barra lateral, el menú del móvil y las tarjetas del resumen, y `lib/nav.test.ts` la mantiene igual que las rutas de `App.tsx` (una página nueva sin su sitio en el menú falla). `Sidebar` es la columna de escritorio (plegable a iconos); en un móvil (< 768 px) no hay barra fija: un botón de menú abre `MobileNav` (cajón modal: Escape, fondo y su botón lo cierran, elegir página lo cierra, el foco entra). `CollectionSwitcher` cambia de competición desde la cabecera manteniendo la misma página (con una sola competición no se pinta). La portada lleva un hero con degradado del acento. **Una página debe caber a 390 px**: el smoke e2e comprueba que 9 páginas no se salen por los lados; si una se sale, se arregla (`flex-wrap`, `overflow-x-auto` en su fila de pestañas, `max-w-full`).

Accesibilidad mínima de todos: rol y nombre (`radiogroup`/`radio`, `tablist`/`tab`, `status`), foco visible (`focus`), teclado (flechas en segmentos y pestañas; Inicio/Fin en pestañas) y objetivos de pulsación suficientes.

## Tests
Cada componente tiene el suyo junto a él (`*.test.tsx`: variantes, roles, `aria-*`, teclado). Una página que se migra a los componentes baja su línea en `rawControls.test.ts`; una página nueva no entra en esa lista.
