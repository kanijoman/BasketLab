# Contraste y accesibilidad de la app live (30/10/2026)

Cierra la parte de la app de la auditoría de accesibilidad U7 ([#197](https://github.com/kanijoman/BasketLab/issues/197)); issue [#633](https://github.com/kanijoman/BasketLab/issues/633). Criterio: WCAG 2.1 AA (4,5:1 para texto, 3:1 para componentes y foco).

## Resumen
1. **Los tokens compartidos con la app ya cumplían en el tema oscuro** casi sin excepción; los fallos estaban en el **claro**, y sobre todo en los textos de severidad y de categoría **dentro de su propio fondo tintado** (el fondo de una alerta es el 8–14 % de su color).
2. **El naranja de la marca se usaba como texto** (`--accent`, 3,2–3,6:1 en claro) y **como relleno con tinta blanca** (3,6:1). La web ya tenía los tokens para eso (`--accent-text`, `--accent-solid`); la app los adopta.
3. **Se ajustan 9 colores** (3–11 % más oscuros en claro, un 3 % más claro el rojo del oscuro), se cambian 9 líneas de `styles.css` y se añade el anillo de foco. `ui/contrast.test.ts` lo mide en los dos temas y vigila el CSS.
4. **Sin cambios de lógica ni vectores**: ningún vector de capturas fija estos colores. Los cambios de `design/` van en la release semanal del viernes.

## Pares medidos y arreglos
Medidos con la luminancia relativa de WCAG sobre `--bg`, `--surface` y `--surface-raised`, y sobre el tinte que pinta `styles.css` (`rgb(token / alfa)` sobre la página y sobre la tarjeta).

| Token | Dónde falla | Antes | Ahora |
|---|---|---|---|
| `--accent` (claro) como texto | pestaña activa, opción elegida, marca: 3,2–3,6 | texto con `--accent` | texto con `--accent-text` (≥ 5,4 también sobre su tinte) |
| `--accent` (claro) como relleno | segmento y veredicto elegidos con tinta blanca: 3,6 | `--accent` | `--accent-solid` (5,2) |
| `--sev-critical` | claro sobre su tinte 12–14 %: 4,0–4,4; oscuro sobre tarjeta 14 %: 4,39 | `#cf222e` / `#f85149` | `#be1f2a` / `#f8564e` |
| `--sev-warning` (claro) | tinte 8–14 %: 3,8–4,4; sobre elevada: 4,37 | `#9a6700` | `#895c00` |
| `--sev-info` (claro) | tinte 12 %: 4,1–4,4 | `#0969da` | `#0863cd` |
| `--cat-faltas` | tinte 12 % en claro | `#bf3989` | `#b0347e` |
| `--cat-rival` | ídem | `#bc4c00` | `#ad4600` |
| `--cat-ritmo` | ídem | `#1a7f4b` | `#187545` |
| `--cat-alineacion` | ídem | `#0f766e` | `#0f726b` |
| `--cat-resumen` | ídem; elevada: 4,42 | `#a16207` | `#935906` |

Cumplían ya, en los dos temas: `--text`, `--text-muted`, `--ok`, `--dev-bad`, `--pace-*`, `--cat-juego`, `--cat-rotacion`, `--cat-descanso`, `--cat-probabilidad`, `--sev-warning`/`--sev-info` en oscuro y `--accent-text` sobre su tinte.

## Accesibilidad de la app (lo que ya estaba y lo que faltaba)
- **Objetivos táctiles**: los botones, campos y resúmenes tienen `min-height: 44px` (`--touch`); las casillas son de 22 px pero viven en filas de 44 px. Sin cambios.
- **Movimiento**: `prefers-reduced-motion` ya paraba las animaciones y las transiciones de los botones; faltaba la de `.team`. Añadida.
- **Foco**: no había ninguna regla propia, solo el aro del navegador. Ahora todo lo enfocable por teclado (o por el mando de una tablet) lleva el anillo `--focus` (2 px), que lee 4,6–11 sobre la página y las tarjetas en los dos temas; un test impide apagarlo (`outline: none`).
- **Nombres de controles**: los botones de segmento, pestañas y veredictos llevan rol y estado (`radio`/`aria-checked`, `tab`/`aria-selected`, `aria-pressed`). No se encontraron botones sin nombre entre los revisados por búsqueda; una pasada con lector de pantalla en la tablet sigue pendiente.

## Reproducir
`cd apps/live-android && npx vitest run src/ui/contrast.test.ts`. Para medir otro par basta añadirlo a las listas de ese test.
