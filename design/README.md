# design/ — look & feel compartido de la suite BasketLab

Fuente única de los **tokens de diseño** (y, más adelante, de la marca) para la app Android (`apps/live-android`) y la web (`frontend/`). Decisión (2026-10-13, issues #228 y #187): **tokens y marca compartidos, componentes propios por app**. La app móvil fue el banco de pruebas; la web los usa desde U0 (#188, 27/10/2026).

| Fichero | Qué es |
|---|---|
| `tokens.css` | Variables CSS: superficies, texto, acento naranja, escalas de radio / espaciado / tipografía, paleta de **severidad** y de **categoría** de alertas; para la web (#188) también texto tenue, acento de texto y de botón relleno, azul secundario, datos buenos / malos / al límite (`ok`, `bad`, `warn`), cuartiles `q1`–`q4`, series `chart-1`–`8`, sombras y la fuente de títulos (Space Grotesk). Oscuro por defecto; claro con `prefers-color-scheme` o `data-theme="light|dark"` en `<html>`. |
| `tailwind-preset.cjs` | Preset de Tailwind sobre esos tokens: **el vocabulario de color de la web** (`canvas`, `surface`, `surface-raised`, `line`, `ink`/`-muted`/`-faint`, `accent`/`-text`/`-solid`/`-hover`/`-ink`, `secondary`, `focus`, `ok`/`bad`/`warn`, `q1`–`q4`, `chart-1`–`8`). Los colores llevan canales `--x-rgb` para soportar `bg-surface/50`. Sin radios: la web conserva su geometría. |
| `theme.ts` | Almacén del tema claro / oscuro / sistema, sin framework (`createThemeStore(clave, por defecto)`): la app (`basketlab-live-theme`, sigue al sistema) y la web (`basketlab-web-theme`, **claro por defecto**) lo envuelven en su `useTheme`. |
| `brand/` | Marca de la **app live** (#311): `live-mark.svg` (balón con el pulso del directo, sin fondo), `live-icon.svg` (sobre la baldosa azul marino `#1A2744`) y `live-foreground.svg` (primer plano del icono adaptable de Android). **Web** (#189, #613): el mismo balón con **una tendencia ascendente** (línea blanca con flecha, el trazo del pulso de la app, con un contorno azul marino para verse en claro) en lugar del pulso del directo: `web-mark.svg` (sin baldosa: cabecera, portada y favicon, como la app muestra la suya), `web-icon.svg` (sobre la baldosa azul marino, solo donde la plataforma pide un cuadrado: icono de Apple y del manifest) y `web-mono.svg` (un color, `currentColor`). `cd frontend && npm run brand` escribe en `public/` el favicon SVG e ICO, el icono de Apple, los del manifest y la imagen de los enlaces compartidos (1200×630); `src/brand.test.tsx` vigila que sigan la marca. |

## Cómo se usa
- **App Android**: `src/main.tsx` importa `@design/tokens.css` (alias de Vite a esta carpeta) antes de `styles.css`; los estilos solo usan `var(--…)`.
- **Web**: `tailwind.config.js` usa el preset; `src/main.tsx` importa `@design/tokens.css` (alias de Vite y de TypeScript) y las fuentes autoalojadas (`@fontsource-variable`). Los gráficos toman los colores ya resueltos del tema activo con `lib/chartTheme.ts` (recharts los escribe como atributos SVG y las exportaciones copian el DOM: `var(--x)` se perdería). El guarda `frontend/src/designTokens.test.ts` falla con colores fuera de los tokens, nombres que no existen en el preset y texto blanco sin relleno de color; excepciones: la pista FIBA y sus zonas, oscuras en los dos temas hasta U6 (#196).

## Reglas
1. **Nunca colores sueltos** (`#f59e0b`, `gray-500`…) en componentes: se añade un token si hace falta.
2. **Severidad ≠ categoría**: la severidad dice cuán urgente es (crítica = rojo, aviso = ámbar, info = azul) y se muestra con barra, tinte y etiqueta; la categoría dice de qué trata (faltas, rotación, rival, juego, ritmo) y se muestra con icono y acento. No se reutiliza una escala para la otra.
3. Los colores del ritmo (más rápido / más lento) son neutros, no «bueno/malo».
4. Objetivos táctiles ≥ `--touch` (44 px). Probar siempre en claro y en oscuro.
5. Cada token de color tiene su versión `--x-rgb`; se mantienen sincronizadas.
