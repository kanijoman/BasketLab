# UI de la web — sistema de diseño

Guía de la épica #187 para la web (`frontend/`). Tokens, marca y tema son de la suite (`design/`, ver [design/README.md](../design/README.md)); los componentes viven en `frontend/src/components/ui` (la app live tiene los suyos con los mismos tokens).

## Mapa del documento
- `## Principios` (y `## Tests`) -> reglas: tema claro, ningún color suelto ni control a mano (guardas `designTokens.test.ts`, `rawControls.test.ts`)
- `## Vocabulario de color` -> qué token de color usar y gráficos (`useChartTheme`)
- `## Rankings y exportaciones` -> mínimo de volumen de Rankings (#763), qué ventanas exportan, PNG/PDF en el tema activo
- `## Componentes` -> cuándo usar cada componente de `components/ui` (tabla + `### Detalle de componentes`)
- `## Pista de tiro y zonas` -> pista, zonas del motor, burbujas por zona, scouting del rival
- `## Accesibilidad` -> contraste, controles con nombre, teclado, app live, movimiento, pruebas
- `## Shell y navegación` -> `lib/nav.ts`, selector de competición y sus niveles, fuentes externas
- `## Previa del partido` -> `PreviaPage`: flujo, secciones, «¿Y si…?», lenguaje
- `## Simulación de la liga` -> `SimulacionPage`, líneas de corte
- `## Política de privacidad` -> `PrivacyPage` y su guarda

## Principios
- **Tema claro por defecto**, oscuro o del sistema (selector en la cabecera). Todo se prueba en los dos.
- **Ningún color suelto**: solo el vocabulario del preset. Lo vigila `frontend/src/designTokens.test.ts` (hex, `rgb()`, paleta de Tailwind, nombres que no existen, `dark:`, texto blanco sin relleno de color).
- **Ningún control a mano** en una página nueva: los componentes de abajo. Lo vigila `frontend/src/rawControls.test.ts` (trinquete: ningún fichero suma `<button>`, `<select>`, `<input>` ni `<h1>` crudos; al migrar una página, se baja su línea base).
- Ya no queda ninguna página con controles a mano (U5, #666): la línea base del trinquete está vacía y solo vigila que no entren nuevos; historial de las migraciones en [evaluaciones/2026-11-27_historia-ui.md](evaluaciones/2026-11-27_historia-ui.md).
- Lo que se activa y desactiva (fases a combinar, estadísticas de la tendencia) es un `Button` con `aria-pressed`; las series de un gráfico, un `Checkbox`; ver y quitar con `IconButton` con su nombre.
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

## Rankings y exportaciones

### Rankings: mínimo de volumen (#763, 05/11/2026)
- **Rankings: mínimo de volumen (#763, 05/11/2026)**: una tasa (un porcentaje de tiro, un rating, un promedio por partido) se falsea con quien tiene muy poco volumen detrás (un 100 % con 2 intentos).
  - Todas las estadísticas de «Rankings» aplican la **misma regla, relativa a la competición**: entra quien alcanza al menos **la mitad de la mediana de volumen por partido del equipo** (la mediana, sobre las jugadoras con ≥ 3 partidos; las que no tiran cuentan en ella).
  - El volumen es lo que respalda la estadística: los intentos de su categoría (% TL, % T2, % T3), los tiros de campo (eFG %, FTr, 3PAr), los tiros de campo y libres (TS %) y los **minutos** para todo lo demás (promedios por partido y avanzadas: USG %, ORtg, DRtg, Net Rtg, Ast %, TO %, Stl %, Blk %, ROF %, RDef %, PIE).
  - `lib/rankingMinimum.ts`; la página dice «Mínimo: N … por partido del equipo» y cuántas jugadoras quedan fuera, y el CSV es el mismo ranking que la pantalla.
  - Con una temporada completa deja fuera a ≈ 23 % de las jugadoras con ≥ 3 partidos en las de minutos y a ≈ 25-35 % en las de tiro.

### Qué ventanas exportan (#759, 05/11/2026)
- **Qué ventanas exportan (#759, 05/11/2026)**: todas las que muestran resultados ofrecen CSV, PNG y PDF con el mismo `ExportButton` —dentro de `DataTable` con `exportOptions`, o en las `actions` del `PageHeader`—
  - las que no tienen tabla (IN/OUT, Rankings) sacan el CSV de las mismas cifras que se ven (`lib/inoutExport.ts`; el ranking completo bajo los filtros, no solo las 30 visibles) y capturan los resultados para PNG y PDF.
- No exportan el Resumen (solo navega) ni los informes, que descargan sus propios PDF/DOCX.

### Exportaciones (`ExportButton`): PNG y PDF en el tema activo (#617)
- **Exportaciones** (`ExportButton`): PNG y PDF salen **en el tema activo** (#617): la captura con el fondo del tema, el gráfico exportado desde su SVG sobre ese fondo (no transparente) y cada página del PDF con el fondo, el título (`--text`) y la fecha (`--text-muted`) del tema; en claro, el PDF es claro de borde a borde.
- Un color para jsPDF también sale de los tokens: el guarda rechaza `setFillColor(13, 17, 23)` y similares.

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
| `ProgressBar` | progreso de una tarea larga (#215): barra `role="progressbar"` con «mensaje (paso/total)»; detalle abajo | `<ProgressBar step={3} total={12} message="Gráficos" />` |
| `AnalysisProgress` | análisis largo que llega por SSE (Combinaciones, Rotaciones; #452): «Analizando partidos…» con el porcentaje y una barra; sin porcentaje conocido solo el mensaje | `<AnalysisProgress progress={progress} />` |
| `NoCollection` | la página necesita una colección y no hay ninguna elegida (#452) | `if (!collection) return <NoCollection />` |
| `Badge` · `StatCard` | etiqueta y cifra destacada con un **tono** del sistema (`components/ui/tone.ts`: `neutral`, `accent`, `secondary`, `ok`, `warn`, `bad`) | `<Badge tone="secondary">FBCYL</Badge>` · `<StatCard label="OER" value="107" tone="ok" />` |
| `DataTable` | tablas con orden (detalle abajo), búsqueda, cuartiles, columna fija y cabeceras agrupadas; `density` (`compact`/`normal`/`comfortable`), `emptyMessage`, `Spinner` al cargar y tarjetas en un móvil (detalle abajo) | `<DataTable columns={cols} data={rows} quartiles={q} density="compact" />` |
| `teamColumn()` · `TeamCell` | **la columna de equipo de cualquier tabla** (#184): logo FEB, nombre en dos líneas como mucho y entero en el tooltip, 240 px; `{ compact: true }` solo el logo, junto a un jugador. Ninguna página escribe la suya (lo vigila `TeamCell.test.tsx`) | `[teamColumn<TeamStat>(), ...cols]` |

### Detalle de componentes
- `ProgressBar`: el ZIP del informe semanal y el DOCX del scouting individual (que informa por jugador: «Gráficos de los jugadores (3/12)», luego «Montando el documento»; el servidor no da progreso).
- `DataTable`, orden: **cada cabecera ordenable es un botón dentro del `<th>` con `aria-sort`: se enfoca con Tab y ordena con Enter o Espacio, #777; en las pruebas se pulsa el botón, no el `<th>`**.
- `DataTable`, móvil: **en un móvil (< 640 px) cada fila es una tarjeta** (la primera columna de título y el resto «etiqueta: valor»; la etiqueta es la cabecera o `meta.label`).

## Pista de tiro y zonas

### La pista de tiro (U6, #196)
- **La pista de tiro (U6, #196)** no tiene colores propios: suelo, líneas, aro, calor, aciertos y fallos salen del tema activo (`useChartTheme`) y las zonas se colorean con `zoneColours(tema)` (`ok`/`warn`/`bad` según el rating contra la liga); la tinta sobre una burbuja es `--on-data`.

### Zonas de la web = zonas del motor (#452)
- **Zonas de la web = zonas del motor (#452, bloque 2, decidido el 09/11/2026)**: hay un solo sistema de zonas, el de `live_core.zones` (aro, zona, media distancia corta/media/larga, 2 esquinas, 2 alas y centro del arco), el que dicen la app y los informes de scouting. **Transición en tres PRs, primero el que lee** (protocolo de despliegue):
  - 1) el frontend lee los dos sistemas: `lib/engineZones.json` (orden, etiqueta, puntos y ancla en metros de cada zona del motor; `tests/test_zone_anchors.py` comprueba que cada ancla cae **dentro** de su zona según el clasificador y que ninguna burbuja queda encima de otra) y `localdata/shots.ts` elige la lista de zonas por `zone_system` del fichero (`engine`; ausente = sistema antiguo)
  - 2) **hecho**: el backend clasifica con el motor (`feb_zones.classify_zone`/`ZONE_META`/`feb_to_fiba` delegan en `live_core.zones`; `tests/test_web_zones_are_the_engine_zones.py` compara las dos clasificaciones en **cada punto de la media pista** cada 10 cm) y `shots/` lleva `zone_system: "engine"`
    - una consecuencia de la geometría única: un tiro **detrás del tablero** (a menos de 1,2 m de la línea de fondo) ya no es «área restringida» sino «zona», como en el motor
  - 3) **hecho el 09/11/2026**: la web solo conoce las zonas del motor, un fichero sin `zone_system` se cuenta como las del motor y un tiro con una clave que no es de ellas no cuenta para ninguna zona.
    - El campo se sigue escribiendo: es la versión del sistema de zonas por si algún día cambia otra vez.
  - Las zonas del motor son anillos y columnas, no manchas: la media corta son dos franjas junto al aro, así que su burbuja es **una por zona, anclada a mano** (a un lado la corta, delante del aro la media y la larga) y el centroide caería fuera.

### Pistas de burbujas por zona (#773, #803)
- **Pistas de burbujas por zona (#773, #803)**: `components/ZoneBubbleCourt` dibuja **una sola vez** la burbuja de zona —tamaño por `sqrt` del total, anillo en arco desde arriba en sentido horario con la parte `share` sobre una pista tenue del círculo entero, y la cifra pequeña—
  - y `AssistZoneCourt` (canastas con y sin asistencia) y `PassZoneCourt` (a dónde llegan las asistencias del pasador) solo le dan datos, textos y leyenda.
  - Una pista nueva de este estilo se hace con ese componente, no copiándolo.
  - El test de `PassZoneCourt` comprueba la geometría del arco, no solo los textos.

### Informe de equipo y scouting del rival (#627)
- **Informe de equipo y scouting del rival (#627)**: el scouting de un rival tiene su página completa («Scouting del rival», en FEB y, desde #635, en FBCYL). «Informe de equipo» es el análisis propio, en las dos ligas, y enlaza a ella (el modo «Scouting rival» por reglas que solo tenía FBCYL se retiró).

## Accesibilidad (U7, #197)
- Objetivo: WCAG 2.1 AA.

### Contraste
- **Contraste**: `designTokens.test.ts` mide en los dos temas **las insignias tal como se dibujan** (`TONE_PILL`: el texto de cada tono sobre su propio tinte y sobre las tres superficies; #856: el texto de `ok`, `warn` y `bad` es su token `ok-text`/`warn-text`/`bad-text` —un matiz más oscuro en el tema claro y más claro en el rojo del oscuro—, `--secondary-text` claro es `#0550ae` y la insignia neutra es `bg-line/50`)
  - y el texto (`--text`, `-muted`, `-faint`) sobre la página, las tarjetas, las filas con hover y las insignias, el texto naranja sobre el tinte del enlace activo y la tinta de los botones rellenos (`--accent-ink` sobre `--accent-solid`, blanco sobre `--secondary-solid`)
  - el azul de un botón relleno es `bg-secondary-solid`, nunca `bg-secondary` con texto blanco.

### Controles con nombre y teclado
- **Controles con nombre**: todo `select`/`input` lleva su etiqueta (`Field` o `aria-label`); las tablas son una región enfocable (`role="region"`, `tabIndex=0`, `ariaLabel`) para poder desplazarlas con el teclado.
- **Teclado**: primer enlace «Saltar al contenido» (`main#contenido`) y anillo de foco `focus` en todo.

### La app live (#633)
- **La app live (#633)**: `contrast.test.ts` de la app (`apps/live-android`, carpeta `ui` de su `src`) mide en los dos temas lo que solo dibuja la app (severidad y categoría de una alerta sobre su tinte, ritmo, el naranja de texto `--accent-text` y el relleno `--accent-solid` con su tinta)
  - y vigila `styles.css` (nada de texto en `--accent`, anillo de foco `--focus` que nadie apaga, movimiento reducido)
  - informe en [evaluaciones/2026-10-30_contraste-y-accesibilidad-de-la-app.md](evaluaciones/2026-10-30_contraste-y-accesibilidad-de-la-app.md).

### Movimiento y pruebas
- **Movimiento**: con `prefers-reduced-motion` ninguna animación ni transición pasa de 0,01 ms (CSS global y `MotionConfig reducedMotion="user"`).
- **Pruebas**: `e2e/a11y.spec.ts` pasa axe (reglas WCAG 2.0/2.1 A y AA) sobre 11 páginas en claro y oscuro a 390 y 1280 px sin violaciones
  - y comprueba el movimiento reducido
  - `e2e/visual.spec.ts` captura seis páginas en los dos temas a 390, 768 y 1280 px y el CI las guarda como artefacto `web-visual-captures` (sin comparar todavía: las líneas base con `toHaveScreenshot` se generarán en Linux cuando las páginas se estabilicen).

## Shell y navegación (U4, #191)

### Navegación (`lib/nav.ts`, `Sidebar`, `MobileNav`)
- `lib/nav.ts` es la **única definición de las páginas de una competición**, en grupos (Equipos, Jugadores, Partido, Competición, Live, Informes) con icono y descripción; la usan la barra lateral, el menú del móvil y las tarjetas del resumen, y `lib/nav.test.ts` la mantiene igual que las rutas de `App.tsx` (una página nueva sin su sitio en el menú falla).
  - `Sidebar` es la columna de escritorio (plegable a iconos); en un móvil (< 768 px) no hay barra fija: un botón de menú abre `MobileNav` (cajón modal: Escape, fondo y su botón lo cierran, elegir página lo cierra, el foco entra).

### Selector de competición (`CollectionSwitcher`, `CollectionPicker`)
- `CollectionSwitcher` cambia de competición desde la cabecera manteniendo la misma página
  - con los niveles de datos **ámbito → temporada (solo los años: 2026/2027; un nombre con un solo año —FBCYL— da el año en que empieza la temporada, el `_season` 2026 de sus partidos de octubre es la 2026/2027) → competición (su nombre: PRIMERA FEB, LF ENDESA…) → grupo (la fase y el grupo: «Liga Regular A», «Play-offs 1/2 Final»)** de `components/CollectionPicker` y `lib/collectionPicker` (#761
    - `levelsOf` los saca de lo que dan los nombres de las colecciones —el `season` de `parseComponents` trae el año y la fase juntos— sin cambiar `parseComponents`, que comparten Multifase y los vectores
    - «Único» no se muestra
    - las competiciones de FBCYL, que solo traen un código, tienen su nombre en una tabla de `lib/collectionPicker.ts` (`1ª` = «1ª División Femenina»; un código que no esté se ve como llega: se añade al publicarse)
    - la lógica es pura: cada nivel ofrece solo lo que permiten los anteriores, una elección que no existe en el nivel nuevo vuelve al valor por defecto —la última temporada, la primera competición y grupo—, el ámbito sale de la `league` de los datos con FEB y FBCYL primero, y el grupo se muestra aunque sea único (dice la fase: «Liga Regular») salvo que no diga nada
    - en la cabecera se ocultan los niveles con una sola opción salvo el grupo, que dice la fase; con una sola competición no se pinta).
  - El Inicio usa los mismos selectores y enlaza a la competición elegida.
  - **Los selectores de competición (`CollectionPicker`, también el de la cabecera `CollectionSwitcher`) muestran siempre los mismos niveles** —Ámbito, **Categoría (Sénior / Formación, #914)**, Temporada, Competición y Grupo cuando hay fase o grupo que nombrar—, aunque haya una sola opción: la interfaz no cambia según la liga (#912).
  - En la cabecera caben en una fila desde 1280 px; por debajo, de `md` a `xl`, pasan a una segunda fila para que se lean.

### Orden y nombres de grupos (#908)
- **Orden y nombres (#908)**: la formación es su propia **categoría** (la da el catálogo, no el nombre) y sus competiciones llevan el nombre legible del catálogo («Selecciones autonómicas · Cadete femenino»)
  - los grupos van primera fase, segunda fase, eliminatorias por puestos y de mayor a menor ronda (1/8, 1/4, 1/2, final), clasificación (3º-4º…) y el resto
  - una etiqueta que repite fase y grupo cuenta una vez
  - «1 2» es 1/2 solo con numerador 1 («1-8 1 2 Final» son los puestos 1-8).
  - La formación no es un ámbito propio sino un nivel entre Ámbito y Temporada: así FBCYL y FIBA tendrán su formación bajo su ámbito (#915).
  - En la cabecera, con cinco selectores, siguen cabiendo en una fila desde 1280 px (se ve a 768 y 1280 px).

### Portada y ancho a 390 px
- La portada lleva un hero con degradado del acento.
- **Una página debe caber a 390 px**: el smoke e2e comprueba que 9 páginas no se salen por los lados; si una se sale, se arregla (`flex-wrap`, `overflow-x-auto` en su fila de pestañas, `max-w-full`).

### Fuentes externas en el selector (#884)
- **Fuentes externas en la web (#884)**: el selector no cambia de forma —los cinco niveles de siempre—: el **ámbito es la fuente** (FEB, FBCYL, ACB, FIBA, NCAA), la **competición** es el nombre del catálogo («NCAA D1», «FIBA U18 EuroBasket»; el género y la división van dentro del nombre, como ya pasa con «LF Endesa» o «Primera FEB») y, en NCAA, la **conferencia es el grupo**.
  - Si una fuente falla o se retrasa, `components/SourceFreshnessNotice` (montado en `Layout`, encima de la página) lo dice con un aviso discreto de tono `warn`: «Datos de NCAA del 17/11: la última actualización falló.» —también «Datos de NCAA del 15/11.» cuando el último dato bueno tiene más de día y medio (`lib/sourceFreshness`, 36 h; la fecha es la UTC para que no dependa de la zona horaria)—.
  - Solo sale en las páginas de una competición externa (a una de FEB o de FBCYL ni se le pregunta la frescura) y si no se puede leer la frescura no dice nada.
  - `e2e/fuentes-externas.spec.ts` lo comprueba en el navegador a 390 px sin desbordar, con el selector y con axe en los dos temas.

### Accesibilidad mínima de todos
Accesibilidad mínima de todos: rol y nombre (`radiogroup`/`radio`, `tablist`/`tab`, `status`), foco visible (`focus`), teclado (flechas en segmentos y pestañas; Inicio/Fin en pestañas) y objetivos de pulsación suficientes.

## Previa del partido (#849)
- Página `PreviaPage` (ruta `previa`, grupo «Partido»; **solo aparece si la competición tiene el calendario publicado**: `requires: {section: 'calendar', dataset: 'forecast'}`).

### Flujo de tres pasos
- Flujo de tres pasos, que es el de quien la usa: **1)** elegir equipo (`Select`; es el punto de vista propio y se recuerda por competición en `localStorage`)
  - **2)** su calendario de partidos pendientes (`TeamFixtures`: un botón por partido con jornada, día y hora, «En casa»/«Fuera» y el rival; en el móvil una columna)
  - **3)** elegir el partido, del que salen el rival y el campo, y debajo el análisis.
- El equipo y el partido van en la dirección (`?equipo=&partido=`) para compartir o recargar; por defecto queda elegido el próximo partido.

### Secciones de la página
- Secciones: *Pronóstico* (`StatCard` de probabilidad, margen esperado y rango habitual; insignia de confianza)
  - *Escenarios* (gráfico de la diferencia de puntos con `useChartTheme`, verde para ganar y rojo para perder, y cuatro tarjetas «cómo se llega»)
  - *Objetivos del partido* (ataque y defensa, con la cifra de la proyección del partido, #941
    - el **ritmo es información**: tarjeta «Ritmo (informativo)» con el ritmo esperado y cómo fue la temporada a ritmo lento y alto, **sin probabilidad de ganar** porque la evaluación del 11/11/2026 —12 ligas, masculinas y femeninas— no le encontró respaldo, #857
    - **y nuestras pérdidas también**: «Nuestras pérdidas (informativo)», lo esperado y la temporada con pocas y con muchas, porque la evaluación del 16/11/2026 las encontró calibradas pero no mejores que el pronóstico
    - ya no hay objetivo «Cuidar el balón»)

### ¿Y si…? Probabilidad con condiciones (#940)
- ***¿Y si…? Probabilidad con condiciones*** (#940, `previa/ProjectionCard.tsx` + `ConditionRow.tsx`: hasta 3 condiciones —`Select` de la variable agrupado en Nosotros / Rival / Partido, `SegmentedControl` «menos de» / «más de» y `Input` con el valor como lo escribe la página, porcentajes y tiros libres por cada 100 tiros, con lo esperado como pista y «Escribe un número» si no lo es—
- y una **tarjeta completa, sin plegables, para que el PDF la recoja entera**: el título une las condiciones con «y»
  - la insignia «N % de victorias» solo si hay cifra
  - la frase «Pasa en X de cada 100 partidos como este. En esos partidos ganamos el Y % (en general, el Z %)», o la de rara (< 5 de cada 100) o la de sin respaldo («No damos cifra de victorias: la evaluación no la ha respaldado para…»)
  - el **balance de la temporada de los dos equipos** —el nuestro y el del rival **en la misma situación, con su rival en nuestro lugar** (las condiciones vistas desde su lado), con los marcadores si son tres o menos—
  - la tabla «Cómo son esos partidos» de las 13 variables (lo habitual frente a en esos partidos; **`<table>` simple y no `DataTable`**, para que en el móvil siga siendo una tabla de tres columnas y no trece tarjetas, como el mapa de calor de la simulación; ▲/▼ en las dos que más se mueven, sin contar lo elegido)
  - y de dónde salen los puntos de cada lado (ritmo frente a eficiencia, con un decimal para que sumen).
- Empieza con «Nuestros puntos: más de lo esperado»; las condiciones van en la dirección, `?si=own.points.gt.70_rival.efg.lt.40` (`si=` vacío: ninguna), y en el CSV (`previa/csv.ts`).
- Comprobada a mano a 390 y 1280 px en los dos temas con axe sobre la publicación real: el e2e no la ve porque su publicación de prueba tiene menos escenarios de los necesarios)

### Emparejamiento, lenguaje y umbral
- *Emparejamiento* (`DataTable`) y «Cómo se calcula» (plegable).
- **Regla de lenguaje**: un objetivo se dice siempre como lo que pasa en esos partidos («en esos partidos ganamos el 46 % (en general, el 38 %)»), nunca como promesa ni como «+N %»: el estudio de octubre no encontró evidencia de que corregir un factor durante el partido cambie lo que viene después; lo guarda `forecast/copy.test.ts`.
- Los tonos de la previa (confianza, ventaja del emparejamiento, campo) usan las insignias del sistema (`Badge`), ya a contraste AA (#856, abajo).
- Con menos de 30 escenarios solo se muestra el pronóstico.

## Simulación de la liga (#850)
- Página `SimulacionPage` (ruta `simulacion`, grupo «Competición»; como la previa, **solo aparece con el calendario publicado**).
  - La simulación (10.000 temporadas sobre el calendario real, `forecast/seasonSim`) se hace **después de pintar la página** (`useSeasonSim`: un `Spinner` mientras tanto; ≈ 0,26 s en un PC).
  - Contenido: aviso de que **no se modelan ascensos, descensos ni playoffs** (las reglas cambian con la competición y la temporada)
    - *Clasificación proyectada* (`DataTable` con `teamColumn`: puesto actual, PJ, G-P, diferencia, victorias esperadas, puesto medio, probabilidad de ser 1.º y una columna por cada línea de corte)
    - *Puestos finales* (mapa de calor: `<table>` con `caption`, cabeceras por fila y columna, el porcentaje exacto en `data-p` y en el `title`; relleno del acento al 60 % como máximo para que la tinta de la página mantenga el contraste; envuelto en una región con nombre y foco para que se pueda desplazar con el teclado en el móvil)
    - y *Partidos decisivos* del equipo propio.
  - **Líneas de corte** (`CutLines`): «Primeros n» o «Últimos n», entre 1 y equipos − 1, sin repetir y como mucho cuatro; se recuerdan **solo en el navegador** de quien las dibuja, por competición (`forecast/storage`, `localStorage` con `try/catch`): no hay configuración de ascensos ni descensos en el repositorio.
  - El equipo propio es el mismo que el de la previa.
  - Con la liga terminada se muestra la clasificación final y nada más.

## Política de privacidad (#834)
- Página `PrivacyPage` en la ruta `/privacidad` (fuera de cualquier competición: se declara **antes** de `/:collection` y `nav.test.ts` la excluye como `OUTSIDE_A_COLLECTION`).
  - **Su dirección es la de la ficha de Google Play: no cambiarla.**
  - Dice qué usa la app, qué guarda en el dispositivo, con quién se comunica (cada dominio al que llama el código de `apps/live-android/src`), los permisos, que no hay anuncios ni seguimiento, y cómo contactar.
  - Está hecha con `PageHeader` y `Card`, sin controles a mano.
  - **Guarda anti-desfase** (`PrivacyPage.test.tsx`): el test recorre las fuentes de la app y exige que cada dominio externo que aparezca esté nombrado en la página, y que los permisos de los plugins (notificaciones, pantalla encendida) se mencionen; un dominio nuevo en la app sin tocar la política rompe el test.
  - Entra en la auditoría axe de `a11y.spec.ts`.

## Tests
- Cada componente tiene el suyo junto a él (`*.test.tsx`: variantes, roles, `aria-*`, teclado).
  - Una página que se migra a los componentes baja su línea en `rawControls.test.ts`; una página nueva no entra en esa lista.
