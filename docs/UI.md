# UI de la web — sistema de diseño

Guía de la épica #187 para la web (`frontend/`). Tokens, marca y tema son de la suite (`design/`, ver [design/README.md](../design/README.md)); los componentes viven en `frontend/src/components/ui` (la app live tiene los suyos con los mismos tokens).

## Principios
- **Tema claro por defecto**, oscuro o del sistema (selector en la cabecera). Todo se prueba en los dos.
- **Ningún color suelto**: solo el vocabulario del preset. Lo vigila `frontend/src/designTokens.test.ts` (hex, `rgb()`, paleta de Tailwind, nombres que no existen, `dark:`, texto blanco sin relleno de color).
- **Ningún control a mano** en una página nueva: los componentes de abajo. Lo vigila `frontend/src/rawControls.test.ts` (trinquete: ningún fichero suma `<button>`, `<select>`, `<input>` ni `<h1>` crudos; al migrar una página, se baja su línea base).
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

## Componentes (`components/ui`)
| Componente | Cuándo | Ejemplo |
|---|---|---|
| `PageHeader` | la cabecera de cada página: su único `h1`, el subtítulo (la competición) y las acciones | `<PageHeader title="Estadísticas de Equipo" subtitle={collection.label} actions={<ExportButton …/>} />` |
| `Button` | toda acción; `variant` `primary` (una por vista) · `secondary` · `ghost` · `danger`; `size="sm"`; `icon`; `loading` para lo que tarda (deshabilita y lo dice) | `<Button icon={Download} loading={busy} onClick={…}>Generar DOCX</Button>` |
| `IconButton` | acción con solo icono; `label` es obligatorio (nombre y tooltip) | `<IconButton icon={Trash2} label="Eliminar colección" variant="danger" />` |
| `Field` + `Input` / `Select` | formularios: `Field` pone la etiqueta, la ayuda y el error con sus `aria-*`; `Select` es el nativo con chevron (`options` o `<option>`) | `<Field label="Temporada"><Select value={s} onChange={…} options={seasons} /></Field>` |
| `SegmentedControl` | elegir una de pocas opciones **dentro de una vista** (local/visitante, básico/avanzado, tema); `iconOnly` | `<SegmentedControl label="Campo" options={…} value={v} onChange={setV} />` |
| `Tabs` | cambiar **la vista entera** de una página; `trailing` para un control al final de la fila | `<Tabs label="Vistas" tabs={TABS} value={tab} onChange={setTab} />` |
| `Card` | un panel; `title` (h2), `actions`, `padding="none"` para tablas y gráficos a sangre | `<Card title="Estadísticas por zona">…</Card>` |
| `EmptyState` | no hay nada que enseñar: qué falta y qué hacer | `<EmptyState icon={Users} title="Sin combinaciones" description="Selecciona un equipo…" />` |
| `Spinner` · `Skeleton` | carga: `Spinner` lo anuncia (`role="status"`); `Skeleton` dibuja la forma (oculto al lector) | `<Spinner label="Generando DOCX" />` · `<Skeleton lines={3} />` |
| `Badge` · `StatCard` | etiqueta y cifra destacada con un **tono** del sistema (`components/ui/tone.ts`: `neutral`, `accent`, `secondary`, `ok`, `warn`, `bad`) | `<Badge tone="secondary">FBCYL</Badge>` · `<StatCard label="OER" value="107" tone="ok" />` |
| `DataTable` | tablas con orden, búsqueda, cuartiles, columna fija y cabeceras agrupadas; `density` (`compact`/`normal`/`comfortable`), `emptyMessage`, `Spinner` al cargar y **en un móvil (< 640 px) cada fila es una tarjeta** (la primera columna de título y el resto «etiqueta: valor»; la etiqueta es la cabecera o `meta.label`) | `<DataTable columns={cols} data={rows} quartiles={q} density="compact" />` |
| `teamColumn()` · `TeamCell` | **la columna de equipo de cualquier tabla** (#184): logo FEB, nombre en dos líneas como mucho y entero en el tooltip, 240 px; `{ compact: true }` solo el logo, junto a un jugador. Ninguna página escribe la suya (lo vigila `TeamCell.test.tsx`) | `[teamColumn<TeamStat>(), ...cols]` |

Accesibilidad mínima de todos: rol y nombre (`radiogroup`/`radio`, `tablist`/`tab`, `status`), foco visible (`focus`), teclado (flechas en segmentos y pestañas; Inicio/Fin en pestañas) y objetivos de pulsación suficientes.

## Tests
Cada componente tiene el suyo junto a él (`*.test.tsx`: variantes, roles, `aria-*`, teclado). Una página que se migra a los componentes baja su línea en `rawControls.test.ts`; una página nueva no entra en esa lista.
