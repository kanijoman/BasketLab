# design/ — look & feel compartido de la suite BasketLab

Fuente única de los **tokens de diseño** (y, más adelante, de la marca) para la app Android (`apps/live-android`) y la web (`frontend/`). Decisión (2026-10-13, issues #228 y #187): **tokens y marca compartidos, componentes propios por app**. La app móvil es el banco de pruebas; la web los adopta en U0 (#188).

| Fichero | Qué es |
|---|---|
| `tokens.css` | Variables CSS: superficies, texto, acento naranja, escalas de radio / espaciado / tipografía, paleta de **severidad** y de **categoría** de alertas. Oscuro por defecto; claro con `prefers-color-scheme` o `data-theme="light|dark"` en `<html>`. |
| `tailwind-preset.cjs` | Preset de Tailwind sobre esos tokens (la web lo usará en U0). Los colores llevan canales `--x-rgb` para soportar `bg-surface/50`. |
| `brand/` | Marca de la **app live** (#311): `live-mark.svg` (balón con el pulso del directo, sin fondo), `live-icon.svg` (sobre la baldosa azul marino `#1A2744`) y `live-foreground.svg` (primer plano del icono adaptable de Android). El logo de la web (U1 #189) sigue pendiente. |

## Cómo se usa
- **App Android**: `src/main.tsx` importa `@design/tokens.css` (alias de Vite a esta carpeta) antes de `styles.css`; los estilos solo usan `var(--…)`.
- **Web**: `presets: [require('../design/tailwind-preset.cjs')]` y `import '../../design/tokens.css'` (U0).

## Reglas
1. **Nunca colores sueltos** (`#f59e0b`, `gray-500`…) en componentes: se añade un token si hace falta.
2. **Severidad ≠ categoría**: la severidad dice cuán urgente es (crítica = rojo, aviso = ámbar, info = azul) y se muestra con barra, tinte y etiqueta; la categoría dice de qué trata (faltas, rotación, rival, juego, ritmo) y se muestra con icono y acento. No se reutiliza una escala para la otra.
3. Los colores del ritmo (más rápido / más lento) son neutros, no «bueno/malo».
4. Objetivos táctiles ≥ `--touch` (44 px). Probar siempre en claro y en oscuro.
5. Cada token de color tiene su versión `--x-rgb`; se mantienen sincronizadas.
